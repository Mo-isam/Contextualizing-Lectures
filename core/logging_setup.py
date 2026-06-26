"""
logging_setup.py
----------------
Custom logging infrastructure for the lecture processing pipeline.
Provides labeled log records and stdout-based configuration.
"""
import logging
import sys


class ProcessLabelFilter(logging.Filter):
    """Attach a short process label to each log record for cleaner console output."""
    def filter(self, record):
        name = record.name
        if "audio_processor" in name:
            record.process_label = "Audio"
        elif "video_processor" in name:
            record.process_label = "Video"
        elif "ai_aligner" in name:
            record.process_label = "Alignment"
        elif "llm_service" in name:
            record.process_label = "LLM"
        elif "pipeline" in name:
            record.process_label = "Pipeline"
        elif "server" in name or name == "__main__":
            record.process_label = "Server"
        elif "uvicorn" in name:
            record.process_label = "Server"
        else:
            # Fallback to general submodule name
            record.process_label = name.split(".")[-1].capitalize()
        return True


def configure_root_logger():
    """Configure the root logger with stdout handler and ProcessLabelFilter."""
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.addFilter(ProcessLabelFilter())
    stdout_handler.setFormatter(
        logging.Formatter("[%(process_label)s] %(levelname)s: %(message)s")
    )

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    # Clear existing handlers if any
    for h in list(root_logger.handlers):
        root_logger.removeHandler(h)
    root_logger.addHandler(stdout_handler)
