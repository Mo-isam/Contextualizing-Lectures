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
import streamlit as st

# Lazy-import Whisper so the app loads even if torch isn't installed yet.
try:
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


# ── Constants ──────────────────────────────────────────────────────────────────
WHISPER_MODEL_SIZE = "base"   # Change to "small" / "medium" for better accuracy
AUDIO_SAMPLE_RATE  = 16000    # Whisper expects 16 kHz mono


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
            timeout=300,   # 5-minute hard limit
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

def transcribe_audio(audio_path: str) -> list[dict]:
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

    # Load the Whisper model (cached by Whisper internally after first load).
    model = whisper.load_model(WHISPER_MODEL_SIZE)

    # transcribe() returns a dict with a "segments" key.
    result = model.transcribe(
        audio_path,
        verbose=False,
        # word_timestamps=True can be enabled for finer granularity.
    )

    # Normalise output — keep only the fields we need.
    segments = []
    for seg in result.get("segments", []):
        segments.append({
            "id"   : seg["id"],
            "start": round(seg["start"], 2),
            "end"  : round(seg["end"],   2),
            "text" : seg["text"].strip(),
        })

    return segments


# ── 3. Orchestration Helper ────────────────────────────────────────────────────

def process_media_file(media_path: str, temp_dir: str) -> list[dict]:
    """
    Top-level helper called by app.py.
    Automatically decides whether to run FFmpeg first (video input)
    or pass the file directly to Whisper (audio input).

    Args:
        media_path : Path to the uploaded media file.
        temp_dir   : Session temp directory for intermediate files.

    Returns:
        List of Whisper segment dicts with start / end timestamps.
    """
    ext = os.path.splitext(media_path)[1].lower()
    audio_dir = os.path.join(temp_dir, "audio")

    if ext == ".mp4":
        st.info("🎬 Extracting audio from video… this may take a moment.")
        audio_path = extract_audio_from_video(media_path, audio_dir)
        st.success("✅ Audio extracted successfully.")
    else:
        # Already an audio file — use as-is.
        audio_path = media_path

    st.info("🎙️ Transcribing audio with Whisper… please wait.")
    segments = transcribe_audio(audio_path)
    st.success(f"✅ Transcription complete — {len(segments)} segments found.")

    return segments
