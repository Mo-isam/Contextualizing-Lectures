"""
config.py
---------
Centralized configuration manager. 
Auto-generates a user-friendly config.yaml file if it doesn't exist.
"""
import os
import yaml
import logging

logger = logging.getLogger(__name__)

ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
CONFIG_PATH = os.path.join(ROOT_DIR, "config.yaml")

DEFAULT_YAML = """# 🎓 Contextualizing Lectures · AI Configuration

llm:
  # Priority order for fallback models if rate limits or 503s occur
  model_priority:
    - "gemini-3.5-flash"
    - "gemini-3.1-flash-lite"
    - "gemini-3-flash-preview"
    - "gemini-2.5-flash"
    - "gemini-2.5-flash-lite"
    - "gemma-4-31b-it"
    - "gemma-4-26b-a4b-it"

  # Dictionary mapping UI display names to model IDs
  model_options:
    "Auto (try all, best quota)": ""
    "Gemini 3.5 Flash ✦ Latest": "gemini-3.5-flash"
    "Gemini 3.1 Flash Lite ✦ Fast": "gemini-3.1-flash-lite"
    "Gemini 3.0 Flash Preview": "gemini-3-flash-preview"
    "Gemini 2.5 Flash ✦ Stable": "gemini-2.5-flash"
    "Gemini 2.5 Flash Lite": "gemini-2.5-flash-lite"
    "Gemma 4 (31B) ✦ Open Weights": "gemma-4-31b-it"
    "Gemma 4 (26B A4B) ✦ Optimized": "gemma-4-26b-a4b-it"

  # Free-tier limits for proactive UI pacing (Requests Per Minute)
  rpm_limits:
    gemini-3.5-flash: 5
    gemini-3.1-flash-lite: 15
    gemini-3-flash-preview: 5
    gemini-2.5-flash: 5
    gemini-2.5-flash-lite: 15
    gemma-4-31b-it: 5
    gemma-4-26b-a4b-it: 5
    default: 5

audio:
  # OpenAI Whisper model size: "tiny", "base", "small", "medium", "large"
  whisper_model_size: "base"
  # Whisper natively expects 16kHz mono audio
  sample_rate: 16000

alignment:
  # Minimum seconds of audio to accumulate before attempting an AI chunk split
  min_chunk_duration_sec: 180
  # Maximum seconds of audio to allow in a single chunk (protects context limits)
  max_chunk_duration_sec: 300

pdf:
  # Resolution zoom for slide image rendering (1.0 = standard, 2.0 = crisp/high-res)
  render_zoom: 2.0

ui_defaults:
  # Default API tier (true = Paid, false = Free)
  is_paid_api: false
  # Default model selection (must match a value in model_options)
  default_model: "gemini-3.5-flash"
  # Default slide extraction engine: "Native (PyMuPDF) - Fast" or "AI Vision (Gemini) - High Accuracy"
  pdf_engine: "Native (PyMuPDF) - Fast"
  # Default audio transcription engine: "Local Whisper (CPU) - Private" or "AI Audio (Gemini) - Fast/Cloud"
  tx_engine: "Local Whisper (CPU) - Private"
"""

class AppConfig:
    def __init__(self):
        self.config = self._load_config()

    def _load_config(self) -> dict:
        if not os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                f.write(DEFAULT_YAML)
            logger.info(f"Generated default config.yaml at {CONFIG_PATH}")
        
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.error(f"Failed to load config.yaml: {e}")
            return {}

    def get(self, section: str, key: str, default=None):
        """Safely fetch a nested configuration value."""
        return self.config.get(section, {}).get(key, default)

# Singleton instance to be imported across the app
app_config = AppConfig()