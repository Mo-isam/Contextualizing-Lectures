"""
audio_processor.py
------------------
Handles two tasks:
  1. Extract audio from a video file using FFmpeg.
  2. Transcribe audio with OpenAI Whisper (local) producing a
     timestamped JSON array of segments.
"""

import os
import json
import subprocess
import time
import logging
import shutil

from core.llm_service import generate_content_with_fallback, SafetyFilterError, AllModelsFailedError
from core.models import TranscriptSegment

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False

# Lazy-import Whisper so the app loads even if torch isn't installed yet.
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# ── Constants ──────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE = "base"   # Change to "small" / "medium" for better accuracy
AUDIO_SAMPLE_RATE  = 16000    # Whisper expects 16 kHz mono

# Global cache to prevent VRAM thrashing and slow re-loads on repeat runs
_whisper_model_cache = None


# ── 1. Audio Extraction ────────────────────────────────────────────────────────

def extract_audio_from_video(video_path: str, output_dir: str) -> str:
    """
    Use FFmpeg (via subprocess) to strip the audio track from a video file
    and save it as a 16 kHz mono WAV — the format Whisper prefers.

    Args:
        video_path : Absolute path to the input video (e.g., .mp4).
        output_dir : Directory where the extracted WAV will be saved.

    Returns:
        Absolute path to the extracted WAV file.

    Raises:
        RuntimeError: If FFmpeg is not found or the extraction fails.
    """
    os.makedirs(output_dir, exist_ok=True)
    base_name  = os.path.splitext(os.path.basename(video_path))[0]
    audio_path = os.path.join(output_dir, f"{base_name}_audio.wav")

    # Build the FFmpeg command:
    #   -i            : input file
    #   -vn           : no video output
    #   -acodec pcm_s16le : uncompressed PCM for Whisper compatibility
    #   -ar 16000     : resample to 16 kHz
    #   -ac 1         : downmix to mono
    #   -y            : overwrite output without prompting
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg executable not found. Please install FFmpeg and ensure it is on your system PATH.")

    cmd = [
        "ffmpeg",
        "-i", video_path,
        "-vn",
        "-acodec", "pcm_s16le",
        "-ar", str(AUDIO_SAMPLE_RATE),
        "-ac", "1",
        "-y",
        audio_path,
    ]

    try:
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=3600,   # 60-minute hard limit for massive lectures
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(f"FFmpeg error (code {result.returncode}):\n{err}")
    except FileNotFoundError:
        raise RuntimeError(
            "FFmpeg executable not found. "
            "Please install FFmpeg and ensure it is on your system PATH."
        )

    return audio_path


# ── 2. Whisper Transcription ───────────────────────────────────────────────────

def transcribe_audio(audio_path: str) -> list[TranscriptSegment]:
    """
    Transcribe an audio file with the local OpenAI Whisper model.

    Returns a list of segment dicts, each containing:
        {
            "id"   : int,
            "start": float,   # seconds
            "end"  : float,   # seconds
            "text" : str,
        }

    Args:
        audio_path : Absolute path to the audio file (WAV / MP3).

    Raises:
        ImportError : If the `whisper` package is not installed.
        FileNotFoundError : If the audio file does not exist.
    """
    if not WHISPER_AVAILABLE:
        raise ImportError(
            "openai-whisper is not installed. Run: pip install openai-whisper"
        )

    if not os.path.exists(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    global _whisper_model_cache
    if _whisper_model_cache is None:
        # Load the Whisper model into memory once per application lifecycle
        _whisper_model_cache = whisper.load_model(WHISPER_MODEL_SIZE)

    # transcribe() returns a dict with a "segments" key.
    result = _whisper_model_cache.transcribe(
        audio_path,
        verbose=False,
        # word_timestamps=True can be enabled for finer granularity.
    )

    # Normalise output — keep only the fields we need.
    segments = []
    for seg in result.get("segments", []):
        segments.append(TranscriptSegment(
            id=seg["id"],
            start=round(seg["start"], 2),
            end=round(seg["end"], 2),
            text=seg["text"].strip(),
        ))

    return segments


# ── 3. AI Audio Transcription (Gemini) ─────────────────────────────────────────

def transcribe_audio_ai(audio_path: str, temp_dir: str, api_key: str, models_to_try: list[str], is_paid: bool = False, progress_cb=None) -> list[TranscriptSegment]:
    """Transcribe audio using Gemini, with hot-swapping for quotas and chunking for token limits."""
    if not GENAI_AVAILABLE:
        raise ImportError("google-generativeai is not installed.")
        
    genai.configure(api_key=api_key.strip())
    
    schema = {
        "type": "OBJECT",
        "properties": {
            "segments": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "text": {"type": "STRING"},
                        "start": {"type": "NUMBER"},
                        "end": {"type": "NUMBER"}
                    },
                    "required": ["text", "start", "end"]
                }
            }
        },
        "required": ["segments"]
    }
    
    config = genai.GenerationConfig(
        temperature=0.0, # Zero creativity, exact transcription
        response_mime_type="application/json",
        response_schema=schema
    )

    # 1. Chunk the audio into 5-minute pieces using FFmpeg
    chunk_dir = os.path.join(temp_dir, "audio_chunks")
    os.makedirs(chunk_dir, exist_ok=True)
    chunk_pattern = os.path.join(chunk_dir, "chunk_%03d.wav")
    
    if progress_cb: progress_cb(0.0, "✂️ Splitting audio into 5-minute chunks for AI...")
    
    cmd = [
        "ffmpeg", "-i", audio_path,
        "-f", "segment", "-segment_time", "300", "-c", "copy",
        chunk_pattern, "-y"
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    chunks = sorted([os.path.join(chunk_dir, f) for f in os.listdir(chunk_dir) if f.endswith(".wav")])
    total_chunks = len(chunks)
    
    all_segments = []
    global_id = 0
    
    for i, c_path in enumerate(chunks):
        time_offset = i * 300.0  # 5 minutes per chunk
        if progress_cb: progress_cb(i/total_chunks, f"☁️ Uploading & Transcribing chunk {i+1}/{total_chunks}...")
        
        # Upload to Gemini
        gemini_file = genai.upload_file(c_path)
        
        # Wait for API processing (audio needs a few seconds to be "ACTIVE")
        wait_start = time.time()
        while gemini_file.state.name == "PROCESSING":
            if time.time() - wait_start > 300:
                raise TimeoutError(f"Gemini API timed out processing audio chunk {i+1} after 5 minutes.")
            time.sleep(2)
            gemini_file = genai.get_file(gemini_file.name)
            
        chunk_success = False
        try:
            prompt = "Transcribe this audio exactly. Do not summarize."
            response_text = generate_content_with_fallback(
                contents=[gemini_file, prompt],
                generation_config=config,
                models_to_try=models_to_try,
                api_key=api_key,
                is_paid=is_paid,
                log_context=f"audio chunk {i+1}",
                progress_cb=progress_cb,
                progress_idx=i / total_chunks,
                max_retries=3
            )
            data = json.loads(response_text)
            
            for seg in data.get("segments", []):
                all_segments.append(TranscriptSegment(
                    id=global_id,
                    start=round(seg["start"] + time_offset, 2),
                    end=round(seg["end"] + time_offset, 2),
                    text=seg["text"].strip()
                ))
                global_id += 1
                
            chunk_success = True
            
        except SafetyFilterError:
            all_segments.append(TranscriptSegment(
                id=global_id, 
                start=time_offset, 
                end=time_offset + 300.0,
                text="[Audio transcription blocked by AI safety filter]"
            ))
            global_id += 1
            chunk_success = True # Bypass success
            
        except AllModelsFailedError:
            chunk_success = False
            
        except Exception as e:
            msg = f"⚠️ Parse error on audio chunk {i+1}: {str(e)}"
            logger.error(msg)
            if progress_cb: progress_cb(i / total_chunks, msg)
            chunk_success = False
            
        finally:
            genai.delete_file(gemini_file.name) # Clean up cloud storage regardless of success

    return all_segments


# ── 4. Orchestration Helper ────────────────────────────────────────────────────

def process_media_file(media_path: str, temp_dir: str, engine: str = "local", api_key: str = "", models_to_try: list = None, is_paid: bool = False, progress_cb=None) -> list[TranscriptSegment]:
    ext = os.path.splitext(media_path)[1].lower()
    audio_dir = os.path.join(temp_dir, "audio")

    if ext == ".mp4":
        if progress_cb: progress_cb(0.0, "🎬 Extracting audio from video...")
        audio_path = extract_audio_from_video(media_path, audio_dir)
    else:
        audio_path = media_path

    if engine == "ai":
        if not api_key: raise ValueError("API Key required for AI Transcription.")
        segments = transcribe_audio_ai(audio_path, temp_dir, api_key, models_to_try, is_paid, progress_cb)
    else:
        if progress_cb: progress_cb(0.5, "🎙️ Transcribing locally with Whisper...")
        segments = transcribe_audio(audio_path)

    return segments
