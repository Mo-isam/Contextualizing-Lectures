"""
storage.py
----------
Handles local file system storage for processed sessions, 
allowing users to save and reload previous lectures.
"""
import os
import json
import time
import shutil
import logging
from dataclasses import asdict

from core.models import TranscriptSegment, Slide, AlignedNote

logger = logging.getLogger(__name__)

# Move up one directory from /core to reach the root project folder
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_STORAGE_DIR = os.path.join(ROOT_DIR, "data_storage")
SESSIONS_DIR = os.path.join(DATA_STORAGE_DIR, "sessions")
FILES_DIR = os.path.join(DATA_STORAGE_DIR, "files")


def save_session(session_name: str, state: dict, temp_dir: str = None) -> str:
    """Save the current processed lecture session to local storage."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)

    slug = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in session_name]).strip()
    session_id = f"{slug}_{int(time.time())}"

    pdf_path = state.get("pdf_path")
    media_path = state.get("media_path")
    
    saved_pdf_path = None
    saved_media_path = None
    saved_audio_path = None

    if pdf_path and os.path.exists(pdf_path):
        pdf_ext = os.path.splitext(pdf_path)[1]
        saved_pdf_path = os.path.join(FILES_DIR, f"{session_id}{pdf_ext}")
        shutil.copy2(pdf_path, saved_pdf_path)
        # Store only relative filename
        saved_pdf_path = f"files/{session_id}{pdf_ext}"

    if media_path and os.path.exists(media_path):
        media_ext = os.path.splitext(media_path)[1]
        saved_media_path = os.path.join(FILES_DIR, f"{session_id}{media_ext}")
        shutil.copy2(media_path, saved_media_path)
        # Store only relative filename
        saved_media_path = f"files/{session_id}{media_ext}"

        # --- Save the lightweight extracted .wav if it's a video ---
        if media_ext.lower() == ".mp4" and temp_dir:
            base_name = os.path.splitext(os.path.basename(media_path))[0]
            temp_audio_path = os.path.join(temp_dir, "audio", f"{base_name}_audio.wav")
            if os.path.exists(temp_audio_path):
                disk_audio_path = os.path.join(FILES_DIR, f"{session_id}_audio.wav")
                shutil.copy2(temp_audio_path, disk_audio_path)
                saved_audio_path = f"files/{session_id}_audio.wav"
        elif media_ext.lower() in [".mp3", ".wav"]:
            saved_audio_path = saved_media_path

    def _to_dict(obj_list):
        if not obj_list: return None
        return [asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in obj_list]

    metadata = {
        "session_name"        : session_name,
        "session_id"          : session_id,
        "pdf_path"            : saved_pdf_path,
        "media_path"          : saved_media_path,
        "audio_path"          : saved_audio_path,
        "transcript_segments" : _to_dict(state.get("transcript_segments")),
        "slides"              : _to_dict(state.get("slides")),
        "final_output"        : _to_dict(state.get("final_output")),
        "timestamp"           : time.time(),
    }

    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    tmp_file = f"{session_file}.tmp"
    
    # Atomic write: write to temp file first, then replace
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, session_file)

    return session_file


def list_saved_sessions() -> list[dict]:
    """List all saved sessions from the local storage folder."""
    if not os.path.exists(SESSIONS_DIR):
        return []
    
    sessions = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(SESSIONS_DIR, f), "r", encoding="utf-8") as file:
                    data = json.load(file)
                    sessions.append({
                        "name": data.get("session_name", f),
                        "id": data.get("session_id"),
                        "filename": f,
                        "timestamp": data.get("timestamp", 0)
                    })
            except Exception as e:
                logger.error(f"Failed to read session file {f}: {e}")
    sessions.sort(key=lambda x: x["timestamp"], reverse=True)
    return sessions


def load_session(filename: str) -> dict:
    """Load session data and dynamically resolve relative paths to absolute runtime paths."""
    path = os.path.join(SESSIONS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for key in ["pdf_path", "media_path", "audio_path"]:
        val = data.get(key)
        if val and val.startswith("files/"):
            file_name = os.path.basename(val)
            data[key] = os.path.join(FILES_DIR, file_name)
            
    # Upgrade JSON dicts back to Dataclass objects for the rest of the app
    if data.get("transcript_segments"):
        data["transcript_segments"] = [TranscriptSegment(**item) for item in data["transcript_segments"]]
    if data.get("slides"):
        data["slides"] = [Slide(**item) for item in data["slides"]]
    if data.get("final_output"):
        # Relies on strict kwargs matching; will correctly throw TypeError if an old session is loaded
        data["final_output"] = [AlignedNote(**item) for item in data["final_output"]]
            
    return data