"""
ai_aligner.py
-------------
Maps Whisper transcript segments to PDF slides using the Gemini API.

Key design decisions:
  • CHUNKING  — the full transcript is split into 3-5 minute chunks before
    being sent to Gemini, so each API call stays well within the context-
    window and token-rate limits.
  • BATCHING  — a configurable sleep() is inserted between API calls to
    respect Gemini Flash's per-minute request quota.
  • SMART 429 HANDLING — when a 429 is received, the code parses the
    retry_delay field from the error message and sleeps exactly that long
    (+ a small buffer), rather than using a fixed backoff that may be too
    short or unnecessarily long.
  • MERGING   — results from every chunk are merged into a single, sorted
    FINAL OUTPUT JSON.
"""

import os
import json
import time
import re
import streamlit as st

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# ── Configuration ──────────────────────────────────────────────────────────────
CHUNK_DURATION_SECONDS = 240      # 4-minute chunks  (tune: 180–300)
INTER_CHUNK_SLEEP_SEC  = 20       # seconds to wait between Gemini API calls

# Free-tier model priority list — tried top-to-bottom if the primary fails.
# gemini-1.5-flash-latest has the most generous free-tier quota (15 RPM / 1M TPD).
# gemini-2.0-flash-lite is a lighter fallback with its own quota bucket.
GEMINI_MODEL_PRIORITY = [
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash-8b",
]

MAX_RETRIES           = 4         # retry count on transient API errors
RETRY_BUFFER_SEC      = 5         # extra seconds added on top of API-specified retry delay
MAX_WAIT_SEC          = 120       # cap on any single sleep to avoid blocking forever


# ── Helpers ────────────────────────────────────────────────────────────────────

def _extract_retry_delay(exc_str: str) -> int:
    """
    Parse the retry delay (in seconds) from a 429 error message.

    Gemini 429 responses contain text like:
        'retry_delay { seconds: 28 }'
    or the simpler:
        'Please retry in 28.7s'

    We try both patterns and return the delay + RETRY_BUFFER_SEC.
    Falls back to a default of 60 s if nothing is found.
    """
    # Pattern 1: proto format  "retry_delay { seconds: N }"
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", exc_str)
    if m:
        return int(m.group(1)) + RETRY_BUFFER_SEC

    # Pattern 2: human-readable  "Please retry in 28.7s"
    m = re.search(r"retry in\s+([\d.]+)\s*s", exc_str, re.IGNORECASE)
    if m:
        return int(float(m.group(1))) + RETRY_BUFFER_SEC

    # Pattern 3: just a bare number of seconds in the message
    m = re.search(r"(\d{2,3})\s*second", exc_str, re.IGNORECASE)
    if m:
        return int(m.group(1)) + RETRY_BUFFER_SEC

    return 60   # safe fallback


def _is_quota_exhausted(exc_str: str) -> bool:
    """
    Returns True if the error is a hard quota exhaustion (daily limit hit)
    rather than a transient per-minute rate limit.
    Daily exhaustion is indicated by 'limit: 0' in the 429 body.
    """
    return "limit: 0" in exc_str and "GenerateRequestsPerDay" in exc_str


def _chunk_segments(segments: list[dict], chunk_duration: int) -> list[list[dict]]:
    """
    Group Whisper segments into time-based chunks of ~chunk_duration seconds.
    A segment is never split — it belongs entirely to one chunk.
    """
    chunks        = []
    current_chunk = []
    chunk_start   = 0.0

    for seg in segments:
        if current_chunk and (seg["start"] - chunk_start) >= chunk_duration:
            chunks.append(current_chunk)
            current_chunk = []
            chunk_start   = seg["start"]
        current_chunk.append(seg)

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def _format_chunk_for_prompt(chunk: list[dict]) -> str:
    lines = []
    for seg in chunk:
        lines.append(f"[{_fmt_seconds(seg['start'])} → {_fmt_seconds(seg['end'])}] {seg['text']}")
    return "\n".join(lines)


def _fmt_seconds(s: float) -> str:
    m   = int(s) // 60
    sec = int(s) % 60
    return f"{m:02d}:{sec:02d}"


def _build_prompt(slides_text: str, chunk_transcript: str,
                  chunk_start: float, chunk_end: float) -> str:
    return f"""
You are an expert academic assistant specializing in lecture analysis.

## YOUR TASK
You will receive:
1. **Slide Text Array** — the text content of every slide in a lecture PDF.
2. **Transcript Chunk** — a portion of the professor's spoken lecture with timestamps.

Your job is to MAP each spoken idea to the most relevant slide number and extract
"hidden insights" — concepts the professor explained verbally that are NOT written
on the slides.

## SLIDE TEXT ARRAY
{slides_text}

## TRANSCRIPT CHUNK (time window: {_fmt_seconds(chunk_start)} → {_fmt_seconds(chunk_end)})
{chunk_transcript}

## OUTPUT FORMAT (STRICT)
Return ONLY a valid JSON array. No markdown, no commentary, no code fences.
Each element must follow this exact schema:
{{
  "slide_number"   : <integer>,
  "slide_title"    : "<string — title of the matched slide>",
  "spoken_notes"   : "<string — key insights / explanation from the professor for this slide>",
  "timestamp_start": <float — start time in seconds>,
  "timestamp_end"  : <float — end time in seconds>
}}

Rules:
- If the professor discusses multiple slides in this chunk, create one entry per slide.
- If a segment does not match any slide, use slide_number 0 and slide_title "General".
- spoken_notes must be a meaningful summary in 1-3 sentences — NOT a verbatim transcript.
- All timestamps must be real values from the transcript chunk above.
- Output ONLY the JSON array, starting with [ and ending with ].
""".strip()


def _parse_gemini_response(response_text: str) -> list[dict]:
    """Safely parse the JSON array returned by Gemini, stripping any markdown fences."""
    text = response_text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```$", "", text)

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            raise ValueError("Gemini did not return a JSON array.")
        return data
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON parse error from Gemini response: {exc}\n\nRaw:\n{text}")


def discover_available_models(api_key: str) -> list[str]:
    """
    Dynamically discover all models available for the provided API key
    that support 'generateContent'.
    Returns a list of model names (e.g. ['gemini-1.5-flash', 'gemini-1.5-pro', ...])
    without the 'models/' prefix.
    """
    if not GENAI_AVAILABLE:
        return []
    if not api_key or not api_key.strip():
        return []
    try:
        genai.configure(api_key=api_key.strip())
        available = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name
                if name.startswith("models/"):
                    name = name[7:]  # Strip 'models/' prefix
                available.append(name)
        return available
    except Exception as e:
        # Avoid crashing Streamlit; just log/return empty so fallback handles it
        print(f"Error listing models: {e}")
        return []


# ── Main Alignment Function ────────────────────────────────────────────────────

def align_transcript_to_slides(
    segments    : list[dict],
    slides      : list[dict],
    api_key     : str,
    model_name  : str  = "",          # overrides GEMINI_MODEL_PRIORITY[0] if set
    progress_cb         = None,
) -> list[dict]:
    """
    Orchestrate the full chunking → Gemini → merging pipeline.

    Args:
        segments    : Whisper transcript segments (from audio_processor.py).
        slides      : Slide Text Array (from pdf_processor.py).
        api_key     : Gemini API key.
        model_name  : Specific model to use. Falls back to priority list.
        progress_cb : Optional callback(float, str) for Streamlit progress bars.

    Returns:
        FINAL OUTPUT JSON — merged, sorted list of alignment dicts.
    """
    if not GENAI_AVAILABLE:
        raise ImportError("google-generativeai is not installed. Run: pip install google-generativeai")

    if not api_key or api_key.strip() == "":
        raise ValueError("Gemini API key is missing. Please enter your key in the sidebar.")

    # ── Configure Gemini ───────────────────────────────────────────────────────
    genai.configure(api_key=api_key.strip())

    # Build model priority list: user pick first, then discovered models, then defaults
    models_to_try = [model_name.strip()] if model_name.strip() else []
    
    discovered = []
    try:
        discovered = discover_available_models(api_key)
    except Exception:
        pass

    for m in discovered:
        if m not in models_to_try:
            models_to_try.append(m)

    for m in GEMINI_MODEL_PRIORITY:
        if m not in models_to_try:
            models_to_try.append(m)

    # ── Prepare slide context ─────────────────────────────────────────────────
    from pdf_processor import format_slides_for_prompt
    slides_text = format_slides_for_prompt(slides)

    # ── Split transcript into chunks ──────────────────────────────────────────
    chunks = _chunk_segments(segments, CHUNK_DURATION_SECONDS)
    total  = len(chunks)

    if progress_cb:
        progress_cb(0.0, f"Starting alignment — {total} chunk(s) to process…")

    all_results: list[dict] = []

    for idx, chunk in enumerate(chunks):
        chunk_start = chunk[0]["start"]
        chunk_end   = chunk[-1]["end"]
        chunk_label = f"Chunk {idx + 1}/{total} ({_fmt_seconds(chunk_start)}–{_fmt_seconds(chunk_end)})"

        if progress_cb:
            progress_cb(idx / total, f"🤖 Processing {chunk_label}…")

        chunk_transcript = _format_chunk_for_prompt(chunk)
        prompt           = _build_prompt(slides_text, chunk_transcript,
                                          chunk_start, chunk_end)

        # ── Model + retry loop ────────────────────────────────────────────────
        # Strategy:
        #   1. Try current model up to MAX_RETRIES times.
        #   2. On 429, parse the API-specified retry delay and sleep exactly
        #      that long (capped at MAX_WAIT_SEC) before retrying.
        #   3. If the daily quota is fully exhausted (limit: 0), skip to the
        #      next model in the priority list immediately — no point retrying.
        #   4. If all models fail, log a warning and continue to the next chunk.
        chunk_success = False

        for model_id in models_to_try:
            if chunk_success:
                break

            model = genai.GenerativeModel(model_id)
            last_error = None

            for attempt in range(1, MAX_RETRIES + 1):
                try:
                    response      = model.generate_content(prompt)
                    chunk_results = _parse_gemini_response(response.text)
                    all_results.extend(chunk_results)
                    last_error    = None
                    chunk_success = True
                    break   # ✅ success — stop retrying this model

                except Exception as exc:
                    exc_str    = str(exc)
                    last_error = exc

                    # ── Model not found/supported (404) → try next model ──
                    if "404" in exc_str:
                        msg = (f"⚠️ Model [{model_id}] not found or not supported. "
                               f"Switching to next model…")
                        if progress_cb:
                            progress_cb(idx / total, msg)
                        st.warning(msg)
                        break   # break retry loop, outer loop picks next model

                    # ── Hard daily quota exhausted → try next model ────────
                    if _is_quota_exhausted(exc_str):
                        msg = (f"⚠️ Daily quota exhausted for [{model_id}]. "
                               f"Switching to next model…")
                        if progress_cb:
                            progress_cb(idx / total, msg)
                        st.warning(msg)
                        break   # break retry loop, outer loop picks next model

                    # ── Transient 429 → parse delay and wait ──────────────
                    if "429" in exc_str:
                        wait = min(_extract_retry_delay(exc_str), MAX_WAIT_SEC)
                        msg  = (f"⏳ [{model_id}] rate limited "
                                f"(attempt {attempt}/{MAX_RETRIES}). "
                                f"Sleeping {wait}s as requested by API…")
                    else:
                        # Other error (5xx, parse error) — fixed backoff
                        wait = min(30 * attempt, MAX_WAIT_SEC)
                        msg  = (f"⚠️ [{model_id}] attempt {attempt} failed: "
                                f"{exc_str[:120]}. Retrying in {wait}s…")

                    if progress_cb:
                        progress_cb(idx / total, msg)
                    st.warning(msg)
                    time.sleep(wait)

            # Log if this model ran out of retries without success
            if not chunk_success and last_error is not None:
                st.warning(
                    f"⚠️ [{model_id}] gave up on {chunk_label} "
                    f"after {MAX_RETRIES} attempts: {str(last_error)[:200]}"
                )

        if not chunk_success:
            st.error(
                f"❌ All models failed for {chunk_label}. "
                f"This chunk will be skipped. Check your API quota at "
                f"https://ai.dev/rate-limit"
            )

        # ── Rate-limit throttle between chunks ────────────────────────────────
        # This inter-chunk sleep is the primary defense against per-minute
        # quota limits. Even if a single call succeeds, waiting INTER_CHUNK_SLEEP_SEC
        # before the next call keeps us well within the RPM limit.
        if idx < total - 1:
            if progress_cb:
                progress_cb(
                    (idx + 1) / total,
                    f"⏳ Waiting {INTER_CHUNK_SLEEP_SEC}s before next chunk…"
                )
            time.sleep(INTER_CHUNK_SLEEP_SEC)

    # ── Merge & sort by timestamp ──────────────────────────────────────────────
    all_results.sort(key=lambda x: x.get("timestamp_start", 0))

    if progress_cb:
        progress_cb(1.0, f"✅ Alignment complete — {len(all_results)} note(s) generated.")

    return all_results
