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
import logging

from core.llm_service import generate_content_with_fallback, SafetyFilterError, AllModelsFailedError
from core.models import TranscriptSegment, Slide, AlignedNote

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# ── Configuration ──────────────────────────────────────────────────────────────
MIN_CHUNK_DURATION_SEC = 180      # 3-minute minimum accumulation
MAX_CHUNK_DURATION_SEC = 300      # 5-minute absolute maximum limit
INTER_CHUNK_SLEEP_SEC  = 20       # seconds to wait between API calls (Removed in Phase 4)

GEMINI_MODEL_PRIORITY = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def _chunk_segments(segments: list[TranscriptSegment]) -> list[list[TranscriptSegment]]:
    """
    Group Whisper segments into semantic chunks based on natural conversational pauses.
    Accumulates at least MIN_CHUNK_DURATION_SEC, then looks for a safe cut point 
    (silence > 1.5s or strong punctuation) up to MAX_CHUNK_DURATION_SEC.
    """
    chunks = []
    current_chunk = []
    chunk_start = 0.0

    for i, seg in enumerate(segments):
        if not current_chunk:
            chunk_start = seg.start
            
        current_chunk.append(seg)
        duration = seg.end - chunk_start
        
        # 1. If we haven't hit the minimum duration, keep accumulating
        if duration < MIN_CHUNK_DURATION_SEC:
            continue
            
        # 2. If we hit the absolute maximum, force a cut to protect context limits
        if duration >= MAX_CHUNK_DURATION_SEC:
            chunks.append(current_chunk)
            current_chunk = []
            continue
            
        # 3. We are in the "sweet spot" (MIN < duration < MAX). Look for a semantic break.
        is_semantic_break = False
        
        # Condition A: Punctuation break (end of a complete thought)
        if seg.text.strip().endswith((".", "?", "!")):
            is_semantic_break = True
            
        # Condition B: Silence break (professor paused to change slide, breathe, etc.)
        if i + 1 < len(segments):
            next_seg = segments[i+1]
            if (next_seg.start - seg.end) > 1.5:
                is_semantic_break = True
        else:
            is_semantic_break = True # Always break on the final segment
            
        if is_semantic_break:
            chunks.append(current_chunk)
            current_chunk = []

    if current_chunk:
        chunks.append(current_chunk)

    return chunks

def _format_chunk_for_prompt(chunk: list[TranscriptSegment]) -> str:
    lines = []
    for seg in chunk:
        lines.append(f"[ID: {seg.id}] {seg.text}")
    return "\n".join(lines)


def _fmt_seconds(s: float) -> str:
    m   = int(s) // 60
    sec = int(s) % 60
    return f"{m:02d}:{sec:02d}"


def _build_prompt(slides_text: str, chunk_transcript: str) -> str:
    return f"""
You are an expert academic assistant specializing in lecture analysis and precise semantic alignment.

## YOUR TASK
You will receive:
1. **Slide Text Array** — the text content of every slide in the lecture presentation.
2. **Transcript Chunk** — a portion of the spoken lecture, where each sentence has a unique [ID: X].

Your job is to MAP the spoken Segment IDs to the most relevant slide number.

## ALIGNMENT RULES (CRITICAL)
1. **Rigorous Text Matching**: Carefully compare the transcript text with each slide's content to find matches.
2. **Sequential Progression**: Assume the lecture progresses chronologically. Segment IDs should generally move forward alongside slide numbers. Only map non-sequential IDs if the speaker explicitly refers back to a previous topic.
3. **Segment Mapping**: Return a list of all Segment IDs that belong to a specific slide.
4. **General Fallback**: If a segment does not match any slide (e.g., greetings, admin, off-topic), map it to slide_number 0.
5. **AI Insight**: If the professor explains something vital that is NOT written on the slide, summarize it in `ai_insight` (1-2 sentences). Otherwise, leave it as an empty string.

## SLIDE TEXT ARRAY
{slides_text}

## TRANSCRIPT CHUNK
{chunk_transcript}
""".strip()


def _process_structured_response(response_text: str, segment_dict: dict[int, TranscriptSegment], slide_dict: dict[int, str]) -> list[AlignedNote]:
    """Parse the Structured Output JSON and mathematically group IDs into continuous timestamp blocks."""
    data = json.loads(response_text)
    alignments = data.get("alignments", [])
    
    final_notes = []
    for item in alignments:
        s_num = item.get("slide_number", 0)
        s_title = slide_dict.get(s_num, f"Slide {s_num}")
        insight = item.get("ai_insight", "").strip()
        ids = sorted(item.get("segment_ids", []))
        
        if not ids: continue
        
        # Group non-consecutive IDs into continuous sequential blocks
        blocks = []
        current = [ids[0]]
        for i in range(1, len(ids)):
            if ids[i] == current[-1] + 1:
                current.append(ids[i])
            else:
                blocks.append(current)
                current = [ids[i]]
        blocks.append(current)
        
        # For each continuous block, calculate perfect timestamps and stitch the exact transcript
        for block in blocks:
            valid_segs = [segment_dict[vid] for vid in block if vid in segment_dict]
            if not valid_segs: continue
            
            t_start = valid_segs[0].start
            t_end = valid_segs[-1].end
            transcript_text = " ".join([seg.text for seg in valid_segs])
            
            final_notes.append(AlignedNote(
                slide_number=s_num,
                slide_title=s_title,
                exact_transcript=transcript_text,
                ai_insight=insight,
                timestamp_start=t_start,
                timestamp_end=t_end
            ))
            
    return final_notes


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
    segments    : list[TranscriptSegment],
    slides      : list[Slide],
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

    # ── Prepare context and mapping dictionaries ──────────────────────────────
    from core.pdf_processor import format_slides_for_prompt
    slides_text = format_slides_for_prompt(slides)
    
    # O(1) lookup dictionaries for post-processing
    segment_dict = {seg.id: seg for seg in segments}
    slide_dict = {s.page_number: s.title for s in slides}
    slide_dict[0] = "General / Off-topic"

    # ── Split transcript into chunks ──────────────────────────────────────────
    chunks = _chunk_segments(segments)
    total  = len(chunks)

    if progress_cb:
        progress_cb(0.0, f"Starting alignment — {total} chunk(s) to process…")

    all_results: list[AlignedNote] = []

    for idx, chunk in enumerate(chunks):
        chunk_start = chunk[0].start
        chunk_end   = chunk[-1].end
        chunk_label = f"Chunk {idx + 1}/{total} ({_fmt_seconds(chunk_start)}–{_fmt_seconds(chunk_end)})"

        if progress_cb:
            progress_cb(idx / total, f"🤖 Processing {chunk_label}…")

        chunk_transcript = _format_chunk_for_prompt(chunk)
        prompt           = _build_prompt(slides_text, chunk_transcript)

        # Strict JSON Schema Definition
        structured_schema = {
            "type": "OBJECT",
            "properties": {
                "alignments": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "slide_number": {"type": "INTEGER"},
                            "segment_ids": {
                                "type": "ARRAY",
                                "items": {"type": "INTEGER"}
                            },
                            "ai_insight": {"type": "STRING"}
                        },
                        "required": ["slide_number", "segment_ids", "ai_insight"]
                    }
                }
            },
            "required": ["alignments"]
        }
        
        gen_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=structured_schema
        )

        # ── Generate Content via Centralized LLM Service ──────────────────────
        try:
            response_text = generate_content_with_fallback(
                contents=prompt,
                generation_config=gen_config,
                models_to_try=models_to_try,
                log_context=chunk_label,
                progress_cb=progress_cb,
                progress_idx=idx / total
            )
            # Process the structured JSON response into notes
            chunk_results = _process_structured_response(response_text, segment_dict, slide_dict)
            all_results.extend(chunk_results)
            
        except SafetyFilterError:
            # The LLM service already logged the warning. 
            # We safely skip this chunk.
            pass
        except AllModelsFailedError:
            # The LLM service already logged the failure.
            # We safely skip this chunk.
            pass
        except Exception as e:
            # Catch internal parsing errors (e.g., malformed JSON from the model)
            msg = f"⚠️ Failed to parse output for {chunk_label}: {str(e)}"
            logger.error(msg)
            if progress_cb: progress_cb(idx / total, msg)

        # ── Rate-limit throttle between chunks ────────────────────────────────
        # This inter-chunk sleep is the primary defense against per-minute
        # quota limits. Even if a single call succeeds, waiting INTER_CHUNK_SLEEP_SEC
        # before the next call keeps us well within the RPM limit.
        if idx < total - 1:
            if progress_cb:
                for sec in range(INTER_CHUNK_SLEEP_SEC, 0, -1):
                    progress_cb(
                        (idx + 1) / total,
                        f"⏳ Waiting {sec}s before next chunk to respect API limits…"
                    )
                    time.sleep(1)
            else:
                time.sleep(INTER_CHUNK_SLEEP_SEC)

    # ── Merge & sort by timestamp ──────────────────────────────────────────────
    all_results.sort(key=lambda x: x.timestamp_start)

    if progress_cb:
        progress_cb(1.0, f"✅ Alignment complete — {len(all_results)} note(s) generated.")

    return all_results
