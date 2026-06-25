"""
ai_aligner.py
-------------
Maps Whisper transcript segments to PDF slides using the Gemini API.

Key design decisions:
  • VARIABLE SEMANTIC CHUNKING — rather than rigid math, the transcript is 
    sliced dynamically based on natural pauses (silences > 1.5s) and strong 
    punctuation. This ensures the LLM receives complete thoughts.
  • SEQUENTIAL BIAS — the prompt explicitly directs the LLM to follow the 
    chronological flow of the lecture, reducing hallucinated segment jumps.
  • MERGING — results from every chunk are merged into a single, sorted
    FINAL OUTPUT JSON representing the exact transcript to slide alignment.
"""

import os
import json
import time
import re
import logging

from core.llm_service import generate_content_with_fallback, SafetyFilterError, AllModelsFailedError, discover_available_models, GEMINI_MODEL_PRIORITY
from core.models import TranscriptSegment, Slide, AlignedNote

logger = logging.getLogger(__name__)

from core.config import app_config

# ── Configuration ──────────────────────────────────────────────────────────────
MIN_CHUNK_DURATION_SEC = app_config.get("alignment", "min_chunk_duration_sec", 180)
MAX_CHUNK_DURATION_SEC = app_config.get("alignment", "max_chunk_duration_sec", 300)


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


def _group_consecutive_ids(ids: list[int]) -> list[list[int]]:
    """Group non-consecutive segment IDs into continuous sequential blocks."""
    if not ids:
        return []
    blocks = []
    current = [ids[0]]
    for idx in ids[1:]:
        if idx == current[-1] + 1:
            current.append(idx)
        else:
            blocks.append(current)
            current = [idx]
    blocks.append(current)
    return blocks


def _build_prompt(slides_text: str, chunk_transcript: str, max_slide_number: int, previous_context: str = "") -> str:
    prev_block = ""
    if previous_context:
        prev_block = f"\n<previous_context>\n[Do not map this. Provided for conversational flow only]\n{previous_context}\n</previous_context>\n"

    return f"""
You are an expert academic assistant specializing in lecture analysis and precise semantic alignment.

## YOUR TASK
You will receive:
1. **Slide Text Array** — the text content of every slide in the lecture presentation.
2. **Transcript Chunk** — a portion of the spoken lecture, where each sentence has a unique [ID: X].{prev_block}

Your job is to MAP the spoken Segment IDs located in the <current_chunk_to_map> to the most relevant slide number.

## ALIGNMENT RULES (CRITICAL)
1. **Rigorous Text Matching**: Carefully compare the transcript text with each slide's content to find matches.
2. **Chain of Thought Reasoning**: For each slide mapping, provide a brief `step_by_step_reasoning` explaining why these IDs belong to this slide.
3. **Sequential Progression**: Assume the lecture progresses chronologically.
4. **Segment Mapping**: Return a list of all Segment IDs that belong to a specific slide.
5. **General Fallback**: If a segment does not match any slide (e.g., greetings, admin, off-topic), map it to slide_number 0.
6. **Valid Slide Numbers**: The only valid slide numbers you can use are from 1 to {max_slide_number}, inclusive. You MUST NOT map segments to any slide number outside this range. If a segment does not match any valid slide, map it to slide_number 0.
7. **AI Insight**: If the professor explains something vital that is NOT written on the slide, summarize it in `ai_insight` (1-2 sentences).

## SLIDE TEXT ARRAY
{slides_text}

## TRANSCRIPT CHUNK
<current_chunk_to_map>
{chunk_transcript}
</current_chunk_to_map>
""".strip()


def _process_structured_response(response_text: str, segment_dict: dict[int, TranscriptSegment], slide_dict: dict[int, str]) -> list[AlignedNote]:
    """Parse the Structured Output JSON and mathematically group IDs into continuous timestamp blocks."""
    data = json.loads(response_text)
    alignments = data.get("alignments", [])
    
    final_notes = []
    for item in alignments:
        s_num = item.get("slide_number", 0)
        if s_num not in slide_dict:
            logger.warning(f"LLM returned slide_number {s_num} which does not exist in presentation slides. Coercing to 0 (General/Off-topic).")
            s_num = 0
            
        s_title = slide_dict.get(s_num, "General / Off-topic")
        insight = item.get("ai_insight", "").strip()
        ids = sorted(item.get("segment_ids", []))
        
        if not ids: continue
        
        # Group non-consecutive IDs into continuous sequential blocks
        blocks = _group_consecutive_ids(ids)
        
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
                timestamp_end=t_end,
                is_off_topic=(s_num == 0)
            ))
            
    return final_notes


# ── Main Alignment Function ────────────────────────────────────────────────────

def align_transcript_to_slides(
    segments      : list[TranscriptSegment],
    slides        : list[Slide],
    api_key       : str,
    models_to_try : list[str] = None,
    is_paid       : bool = False,
    progress_cb           = None,
) -> list[dict]:
    """
    Orchestrate the full chunking → Gemini → merging pipeline.

    Args:
        segments    : Whisper transcript segments (from audio_processor.py).
        slides      : Slide Text Array (from pdf_processor.py).
        api_key     : Gemini API key.
        models_to_try: Priority list of model IDs to attempt.
        progress_cb : Optional callback(float, str) for progress tracking.

    Returns:
        FINAL OUTPUT JSON — merged, sorted list of alignment dicts.
    """
    if not api_key or api_key.strip() == "":
        raise ValueError("Gemini API key is missing. Please enter your key in the sidebar.")

    # Use the passed fallback list, or defaults if not provided
    if not models_to_try:
        models_to_try = GEMINI_MODEL_PRIORITY

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
    total_minutes = _fmt_seconds(segments[-1].end) if segments else "00:00"

    if progress_cb:
        progress_cb(0.0, f"Starting alignment — {total} chunk(s) to process…")

    all_results: list[AlignedNote] = []
    previous_context_text = ""

    for idx, chunk in enumerate(chunks):
        chunk_start = chunk[0].start
        chunk_end   = chunk[-1].end
        pct = idx / total
        chunk_label = f"🤖 Processing Chunk {idx + 1}/{total} ({_fmt_seconds(chunk_start)}–{_fmt_seconds(chunk_end)} out of {total_minutes} total)"

        if progress_cb:
            progress_cb(pct, chunk_label)

        max_slide_number = len(slides)
        chunk_transcript = _format_chunk_for_prompt(chunk)
        prompt           = _build_prompt(slides_text, chunk_transcript, max_slide_number, previous_context_text)

        # Extract the last 3 segments for the NEXT chunk's context. 
        # Note: seg.text does NOT contain the ID, which is exactly what we want.
        overlap_segs = chunk[-3:] if len(chunk) >= 3 else chunk
        previous_context_text = " ".join([seg.text for seg in overlap_segs])

        # Strict JSON Schema Definition
        structured_schema = {
            "type": "OBJECT",
            "properties": {
                "alignments": {
                    "type": "ARRAY",
                    "items": {
                        "type": "OBJECT",
                        "properties": {
                            "step_by_step_reasoning": {"type": "STRING"},
                            "slide_number": {"type": "INTEGER"},
                            "segment_ids": {
                                "type": "ARRAY",
                                "items": {"type": "INTEGER"}
                            },
                            "ai_insight": {"type": "STRING"}
                        },
                        "required": ["step_by_step_reasoning", "slide_number", "segment_ids", "ai_insight"]
                    }
                }
            },
            "required": ["alignments"]
        }
        
        # ── Generate Content via Centralized LLM Service ──────────────────────
        try:
            response_text = generate_content_with_fallback(
                contents=prompt,
                models_to_try=models_to_try,
                api_key=api_key,
                schema=structured_schema,
                temperature=0.0,
                is_paid=is_paid,
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

    # ── Merge & sort by timestamp ──────────────────────────────────────────────
    all_results.sort(key=lambda x: x.timestamp_start)

    if progress_cb:
        progress_cb(1.0, f"✅ Alignment complete — {len(all_results)} note(s) generated.")

    return all_results


def align_video_to_slides(
    segments: list[TranscriptSegment],
    keyframes: list[dict],
    slides: list[Slide],
    api_key: str,
    models_to_try: list[str],
    is_paid: bool = False,
    progress_cb = None
) -> list[AlignedNote]:
    """
    Deterministic Audio-Visual Fusion with Semantic Filtering.
    Maps segments to visual chapters, then uses an LLM Boolean filter 
    to extract off-topic tangents and generate targeted insights.
    """
    if progress_cb: progress_cb(0.0, "🧮 Fusing audio transcripts to visual timeline...")
    
    # 1. Group segments into CV visual blocks based on temporal midpoint
    cv_blocks = []
    current_block = {"slide_number": -1, "segments": []}
    
    for seg in segments:
        midpoint = (seg.start + seg.end) / 2.0
        
        matched_slide = 0 # Default to General
        for kf in keyframes:
            end_t = kf.get("end_time") or float('inf')
            if kf["start_time"] <= midpoint <= end_t:
                matched_slide = kf.get("matched_slide", 0)
                break
        
        if matched_slide != current_block["slide_number"]:
            if current_block["segments"]:
                cv_blocks.append(current_block)
            current_block = {"slide_number": matched_slide, "segments": [seg]}
        else:
            current_block["segments"].append(seg)
            
    if current_block["segments"]:
        cv_blocks.append(current_block)

    # 2. Semantically Filter and Build Final Notes
    final_notes = []
    slide_dict = {s.page_number: s for s in slides}
    total_blocks = len(cv_blocks)
    
    # Strict JSON Schema for Boolean Semantic Filter
    schema = {
        "type": "OBJECT",
        "properties": {
            "step_by_step_reasoning": {"type": "STRING"},
            "evaluations": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "segment_id": {"type": "INTEGER"},
                        "is_on_topic": {"type": "BOOLEAN"}
                    },
                    "required": ["segment_id", "is_on_topic"]
                }
            },
            "ai_insight": {"type": "STRING"}
        },
        "required": ["step_by_step_reasoning", "evaluations", "ai_insight"]
    }

    for idx, block in enumerate(cv_blocks):
        s_num = block["slide_number"]
        block_segs = block["segments"]
        
        slide_text = slide_dict[s_num].text if s_num in slide_dict else ""
        chunk_transcript = "\n".join([f"[ID: {seg.id}] {seg.text}" for seg in block_segs])
        
        ai_insight = ""
        on_topic_ids = [seg.id for seg in block_segs] # Assume all on-topic by default
        off_topic_ids = []
        
        # Only query LLM if there is transcript text and it's an actual slide (>0)
        if chunk_transcript.strip() and s_num > 0 and api_key:
            pct = idx / total_blocks
            if progress_cb: progress_cb(pct, f"🧠 Semantically filtering Slide {s_num}...")
            
            prompt = (
                "You are an expert academic assistant specializing in lecture analysis.\n\n"
                "## YOUR TASK\n"
                "You will receive:\n"
                f"1. **Slide Text** — the text content currently shown on the screen (Slide {s_num}).\n"
                "2. **Transcript Chunk** — the spoken lecture that occurred while this slide was visible. Each sentence has a unique [ID: X].\n\n"
                "Your job is to evaluate the transcript and filter out off-topic remarks.\n\n"
                "## RULES (CRITICAL)\n"
                "1. **Chain of Thought Reasoning**: Provide a brief `step_by_step_reasoning` of your evaluation.\n"
                "2. **Boolean Evaluation**: For EVERY segment ID in the transcript, determine if it is discussing the slide content (`is_on_topic`: true) or if it is a tangent, admin remark, or off-topic story (`is_on_topic`: false).\n"
                "3. **AI Insight**: If the professor explains something vital that is NOT written on the slide, summarize it in `ai_insight` (1-2 sentences). If they just read the slide or go off-topic, leave it empty.\n\n"
                f"--- SLIDE TEXT ---\n{slide_text}\n\n"
                f"--- TRANSCRIPT CHUNK ---\n{chunk_transcript}"
            )
            
            try:
                response_text = generate_content_with_fallback(
                    contents=[prompt],
                    models_to_try=models_to_try,
                    api_key=api_key,
                    schema=schema,
                    temperature=0.0,
                    is_paid=is_paid,
                    log_context=f"semantic filter for slide {s_num}",
                    progress_cb=progress_cb,
                    progress_idx=pct,
                    max_retries=2
                )
                data = json.loads(response_text)
                ai_insight = data.get("ai_insight", "").strip()
                evaluations = data.get("evaluations", [])
                
                on_topic_ids = []
                off_topic_ids = []
                
                # Process the LLM's true/false routing
                for eval_item in evaluations:
                    seg_id = eval_item.get("segment_id")
                    if eval_item.get("is_on_topic", True):
                        on_topic_ids.append(seg_id)
                    else:
                        off_topic_ids.append(seg_id)
                        
                # Fallback: keep any un-evaluated segments on-topic to prevent data loss
                evaluated_ids = set(on_topic_ids + off_topic_ids)
                for seg in block_segs:
                    if seg.id not in evaluated_ids:
                        on_topic_ids.append(seg.id)
                        
            except SafetyFilterError:
                pass # Already logged by fallback service
            except AllModelsFailedError:
                pass # Already logged by fallback service
            except Exception as e:
                logger.error(f"Failed to generate insight/filter for slide {s_num}: {e}")
                
        elif s_num == 0:
            # If CV explicitly mapped this to Slide 0, everything is automatically off-topic
            on_topic_ids = []
            off_topic_ids = [seg.id for seg in block_segs]

        # ── Helper to group IDs into continuous blocks and create Notes ──
        def _append_notes(target_slide_num, target_ids, target_insight, is_tangent=False):
            if not target_ids: return
            target_ids.sort()
            
            blocks_of_ids = _group_consecutive_ids(target_ids)
            
            segment_dict = {seg.id: seg for seg in block_segs}
            
            for b in blocks_of_ids:
                valid_segs = [segment_dict[vid] for vid in b if vid in segment_dict]
                if not valid_segs: continue
                
                t_start = valid_segs[0].start
                t_end = valid_segs[-1].end
                transcript_text = " ".join([seg.text for seg in valid_segs])
                
                # Fix the Title Bug: Use actual slide title, or fallback to Slide X
                if target_slide_num == 0:
                    s_title = "General / Off-topic"
                else:
                    s_title = slide_dict[target_slide_num].title if target_slide_num in slide_dict else f"Slide {target_slide_num}"
                
                final_notes.append(AlignedNote(
                    slide_number=target_slide_num,
                    slide_title=s_title,
                    exact_transcript=transcript_text,
                    ai_insight=target_insight,
                    timestamp_start=t_start,
                    timestamp_end=t_end,
                    is_off_topic=is_tangent
                ))

        # Reconstruct the notes based on the filter
        _append_notes(s_num, on_topic_ids, ai_insight, is_tangent=False)
        # Keep off-topic on the active slide, but flag it as a tangent!
        _append_notes(s_num, off_topic_ids, "", is_tangent=True)
        
    # Re-sort everything by chronological start time
    final_notes.sort(key=lambda x: x.timestamp_start)
        
    if progress_cb: progress_cb(1.0, f"✅ Video alignment complete — {len(final_notes)} notes generated.")
    
    return final_notes