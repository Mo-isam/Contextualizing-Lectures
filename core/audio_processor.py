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
import threading
import warnings

# Suppress expected PyTorch CPU FP16 warnings
warnings.filterwarnings("ignore", message="FP16 is not supported on CPU")

from core.llm_service import generate_content_with_fallback, SafetyFilterError, AllModelsFailedError, upload_and_wait_for_file, delete_cloud_file
from core.models import TranscriptSegment

logger = logging.getLogger(__name__)

# Check for Whisper without physically importing heavy PyTorch into memory yet.
import importlib.util
WHISPER_AVAILABLE = importlib.util.find_spec("whisper") is not None


from core.config import app_config

# ── Constants ──────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE = app_config.get("audio", "whisper_model_size", "base")
AUDIO_SAMPLE_RATE  = app_config.get("audio", "sample_rate", 16000)

# Global cache to prevent VRAM thrashing and slow re-loads on repeat runs
_whisper_model_cache = None
_whisper_lock = threading.Lock()


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

def transcribe_audio(audio_path: str, progress_cb=None) -> list[TranscriptSegment]:
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
    with _whisper_lock:
        if _whisper_model_cache is None:
            if progress_cb: progress_cb(0.05, f"📥 Loading Whisper '{WHISPER_MODEL_SIZE}' model into memory...")
            import whisper
            _whisper_model_cache = whisper.load_model(WHISPER_MODEL_SIZE)

        if progress_cb: progress_cb(0.1, "🎙️ Whisper model active. Preparing audio frames...")

        # Directly monkey-patch the global tqdm module to capture Whisper's live frames
        import tqdm
        original_tqdm = tqdm.tqdm

        class WhisperTqdm(original_tqdm):
            def __init__(self, *args, **kwargs):
                # Redirect output to devnull to avoid terminal logging noise
                kwargs['file'] = open(os.devnull, 'w')
                super().__init__(*args, **kwargs)
                self.last_logged_decile = -1
            def update(self, n=1):
                super().update(n)
                total = getattr(self, "total", 0)
                if total > 0:
                    pct = int((self.n / total) * 100)
                    decile = pct // 10
                    # Log progress to the terminal console at clean 10% increments
                    if decile > self.last_logged_decile or pct == 100:
                        self.last_logged_decile = decile
                        logger.info(f"Transcribing audio: {pct}% complete ({self.n}/{total} frames)")
                    
                    if progress_cb:
                        # Map tqdm's 0-100% to our remaining 10% to 100% UI bar
                        frac = self.n / total
                        scaled_frac = 0.1 + (frac * 0.9)
                        progress_cb(scaled_frac, f"🎙️ Processing audio frames ({self.n}/{total})...")

        tqdm.tqdm = WhisperTqdm

        try:
            result = _whisper_model_cache.transcribe(
                audio_path,
                verbose=False,
            )
        finally:
            tqdm.tqdm = original_tqdm  # Restore original tqdm safely so other modules aren't affected

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
        pct = i / total_chunks
        if progress_cb: progress_cb(pct, f"☁️ Uploading & Transcribing AI Chunk {i+1}/{total_chunks}...")
        
        # Upload and wait for cloud processing
        gemini_file = upload_and_wait_for_file(c_path, api_key)
            
        chunk_success = False
        try:
            prompt = "Transcribe this audio exactly. Do not summarize."
            response_text = generate_content_with_fallback(
                contents=[gemini_file, prompt],
                models_to_try=models_to_try,
                api_key=api_key,
                schema=schema,
                temperature=0.0,
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
            delete_cloud_file(gemini_file.name, api_key) # Clean up cloud storage regardless of success

    # Transient cleanup: Delete local chunks
    if os.path.exists(chunk_dir):
        shutil.rmtree(chunk_dir, ignore_errors=True)

    return all_segments


# ── 4. Orchestration Helper ────────────────────────────────────────────────────

def process_media_file(media_path: str, temp_dir: str, engine: str = "local", api_key: str = "", models_to_try: list = None, is_paid: bool = False, progress_cb=None) -> list[TranscriptSegment]:
    ext = os.path.splitext(media_path)[1].lower()
    audio_dir = os.path.join(temp_dir, "audio")
    extracted_wav = False

    if ext == ".mp4":
        if progress_cb: progress_cb(0.0, "🎬 Extracting audio from video...")
        audio_path = extract_audio_from_video(media_path, audio_dir)
        extracted_wav = True
    else:
        audio_path = media_path

    try:
        if engine == "ai":
            if not api_key: raise ValueError("API Key required for AI Transcription.")
            segments = transcribe_audio_ai(audio_path, temp_dir, api_key, models_to_try, is_paid, progress_cb)
        else:
            if progress_cb: progress_cb(0.05, "🎙️ Preparing local Whisper transcription...")
            segments = transcribe_audio(audio_path, progress_cb)
    finally:
        # Transient WAV cleanup: Delete massive uncompressed .wav immediately after transcription
        if extracted_wav and os.path.exists(audio_path):
            try:
                os.remove(audio_path)
            except Exception as e:
                logger.warning(f"Could not delete transient wav file {audio_path}: {e}")

    return segments