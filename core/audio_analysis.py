"""
audio_analysis.py
-----------------
Audio analysis utilities: waveform peak extraction for the UI visualizer.
"""
import logging
import shutil
import subprocess

logger = logging.getLogger(__name__)


def generate_peaks(media_path: str, num_peaks: int = 1200) -> list[float]:
    """
    Extracts audio envelope peaks from any media file using FFmpeg and downsamples them.
    Returns a list of normalized float values between 0.0 and 1.0.
    """
    import numpy as np

    if not shutil.which("ffmpeg"):
        logger.warning("FFmpeg executable not found. Skipping peak generation.")
        return []

    # Run FFmpeg to extract mono 8kHz 16-bit PCM raw data on stdout
    cmd = [
        "ffmpeg",
        "-i", media_path,
        "-f", "s16le",
        "-ac", "1",
        "-ar", "8000",
        "-y",
        "-"
    ]

    try:
        # Run FFmpeg and pipe stdout
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=180
        )
        if result.returncode != 0:
            err = result.stderr.decode("utf-8", errors="replace")
            logger.warning(f"FFmpeg failed to extract peaks (code {result.returncode}):\n{err}")
            return []

        # Parse buffer as int16
        samples = np.frombuffer(result.stdout, dtype=np.int16)
        if len(samples) == 0:
            return []

        # Focus on absolute amplitudes
        amplitudes = np.abs(samples)

        # Calculate size of each sampling bin
        bin_size = max(1, len(amplitudes) // num_peaks)

        # Extract maximum peak in each bin
        peaks = []
        for i in range(num_peaks):
            start = i * bin_size
            end = min(start + bin_size, len(amplitudes))
            if start < len(amplitudes):
                peaks.append(float(np.max(amplitudes[start:end])))
            else:
                peaks.append(0.0)

        # Normalize peaks to a [0.0, 1.0] scale
        max_val = max(peaks) if peaks else 0
        if max_val > 0:
            peaks = [round(p / max_val, 4) for p in peaks]

        return peaks

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout expired while generating peaks for: {media_path}")
        return []
    except Exception as e:
        logger.error(f"Error generating peaks: {e}")
        return []
