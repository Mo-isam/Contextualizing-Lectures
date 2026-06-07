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
import uuid
from dataclasses import asdict

from core.models import TranscriptSegment, Slide, AlignedNote, LectureSession

logger = logging.getLogger(__name__)

# Move up one directory from /core to reach the root project folder
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_STORAGE_DIR = os.path.join(ROOT_DIR, "data_storage")
SESSIONS_DIR = os.path.join(DATA_STORAGE_DIR, "sessions")
FILES_DIR = os.path.join(DATA_STORAGE_DIR, "files")


def save_session(session_data: LectureSession, temp_dir: str = None) -> str:
    """Save the current processed lecture session to local storage."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)

    slug = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in session_data.session_name]).strip()
    # Replace low-resolution timestamp with UUID to guarantee no file collisions
    session_id = f"{slug}_{uuid.uuid4().hex[:8]}"

    # Files are now natively saved to data_storage/files on upload,
    # so we just extract the relative path for portable JSON storage.
    saved_pdf_path = None
    if session_data.pdf_path:
        saved_pdf_path = f"files/{os.path.basename(session_data.pdf_path)}"
        
    saved_media_path = None
    if session_data.media_path:
        saved_media_path = f"files/{os.path.basename(session_data.media_path)}"

    def _to_dict(obj_list):
        if not obj_list: return None
        return [asdict(item) if hasattr(item, '__dataclass_fields__') else item for item in obj_list]

    metadata = {
        "session_name"        : session_data.session_name,
        "session_id"          : session_id,
        "pdf_path"            : saved_pdf_path,
        "media_path"          : saved_media_path,
        "transcript_segments" : _to_dict(session_data.transcript_segments),
        "slides"              : _to_dict(session_data.slides),
        "final_output"        : _to_dict(session_data.final_output),
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


def load_session(filename: str) -> LectureSession:
    """Load session data and return a strictly typed LectureSession object."""
    path = os.path.join(SESSIONS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for key in ["pdf_path", "media_path"]:
        val = data.get(key)
        if val and val.startswith("files/"):
            file_name = os.path.basename(val)
            data[key] = os.path.join(FILES_DIR, file_name)
            
    # Upgrade JSON dicts back to Dataclass objects
    segments = [TranscriptSegment(**item) for item in data.get("transcript_segments", [])] if data.get("transcript_segments") else None
    slides = [Slide(**item) for item in data.get("slides", [])] if data.get("slides") else None
    final_output = [AlignedNote(**item) for item in data.get("final_output", [])] if data.get("final_output") else None
            
    return LectureSession(
        session_name=data.get("session_name", "Untitled"),
        session_id=data.get("session_id"),
        pdf_path=data.get("pdf_path"),
        media_path=data.get("media_path"),
        transcript_segments=segments,
        slides=slides,
        final_output=final_output,
        timestamp=data.get("timestamp", 0.0)
    )