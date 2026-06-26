import os
import sys
import json
import uuid
import time
import logging
import asyncio
import threading
from pathlib import Path
from typing import List, Dict, Any, Optional

if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import core modules
from core.storage import save_session, load_session, list_saved_sessions, resolve_data_path, DATA_STORAGE_DIR, FILES_DIR
from core.file_utils import save_file, convert_pptx_to_pdf
from core.models import TranscriptSegment, Slide, AlignedNote, LectureSession
from core.config import app_config
from core.pipeline import PipelineJob, PipelineCancelledError

# Custom logging filter and formatter to categorize processes
class ProcessLabelFilter(logging.Filter):
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

# Initialize stdout handler
stdout_handler = logging.StreamHandler(sys.stdout)
stdout_handler.addFilter(ProcessLabelFilter())
stdout_handler.setFormatter(logging.Formatter("[%(process_label)s] %(levelname)s: %(message)s"))

# Configure root logger
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)
# Clear existing handlers if any
for h in list(root_logger.handlers):
    root_logger.removeHandler(h)
root_logger.addHandler(stdout_handler)

logger = logging.getLogger(__name__)

app = FastAPI(title="Contextualizing Lectures · API Server")

# Enable CORS for React Dev Server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict this to ["http://localhost:5173"] in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ensure directories exist
os.makedirs(DATA_STORAGE_DIR, exist_ok=True)
os.makedirs(FILES_DIR, exist_ok=True)
os.makedirs(os.path.join(FILES_DIR, "documents"), exist_ok=True)
os.makedirs(os.path.join(FILES_DIR, "media"), exist_ok=True)

# Mount Static Directories for direct file serving (no base64 overhead)
app.mount("/data", StaticFiles(directory=DATA_STORAGE_DIR), name="data")

# Mount temp dir if it exists, otherwise create it first
TMP_DIR = os.path.join(os.path.dirname(FILES_DIR), "tmp")
os.makedirs(TMP_DIR, exist_ok=True)
app.mount("/tmp", StaticFiles(directory=TMP_DIR), name="tmp")


# ═══════════════════════════════════════════════════════════════════════════════
# MODELS & SCHEMAS
# ═══════════════════════════════════════════════════════════════════════════════
class AlignedNoteSchema(BaseModel):
    slide_number: int
    slide_title: str
    exact_transcript: str
    timestamp_start: float
    timestamp_end: float
    ai_insight: str
    is_off_topic: bool = False

class SlideSchema(BaseModel):
    page_number: int
    title: str
    text: str

class TranscriptSegmentSchema(BaseModel):
    id: int
    start: float
    end: float
    text: str

class SaveSessionSchema(BaseModel):
    session_name: str
    session_description: str
    pdf_path: str
    media_path: str
    transcript_segments: List[TranscriptSegmentSchema]
    slides: List[SlideSchema]
    final_output: List[AlignedNoteSchema]
    pipeline_type: str = "audio"
    peaks: Optional[List[float]] = None
    session_id: Optional[str] = None

class UpdateMetadataSchema(BaseModel):
    session_name: str
    session_description: str

class ConfigUpdateSchema(BaseModel):
    is_paid_api: Optional[bool] = None
    default_model: Optional[str] = None
    pdf_engine: Optional[str] = None
    tx_engine: Optional[str] = None
    whisper_model_size: Optional[str] = None
    sample_rate: Optional[int] = None
    min_chunk_duration_sec: Optional[int] = None
    max_chunk_duration_sec: Optional[int] = None
    render_zoom: Optional[float] = None
    matching_strategy: Optional[str] = None
    frame_sample_rate: Optional[int] = None
    ssim_threshold: Optional[float] = None
    model_priority: Optional[List[str]] = None


# ═══════════════════════════════════════════════════════════════════════════════
# REST API ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/sessions")
def get_sessions():
    """List all saved sessions in the local library."""
    try:
        return list_saved_sessions()
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/session/{filename}")
def get_session(filename: str):
    """Retrieve and deserialize a specific session."""
    try:
        session = load_session(filename)
        
        # Serialize dataclasses manually to JSON-friendly format
        def to_dict_list(items):
            if not items: return []
            return [item.__dict__ if hasattr(item, "__dict__") else item for item in items]

        # Convert back absolute paths to portable relative paths for frontend usage
        def to_rel_path(abs_path):
            if not abs_path: return ""
            return Path(abs_path).relative_to(DATA_STORAGE_DIR).as_posix()

        # Render slide PDF to images for display in React viewer
        from core.pdf_processor import render_pdf_to_images
        sess_id = session.session_id or uuid.uuid4().hex[:8]
        session_temp_dir = Path(TMP_DIR) / f"session_{sess_id}"
        session_temp_dir.mkdir(parents=True, exist_ok=True)
        img_dir = session_temp_dir / "slide_images"
        
        slide_images = []
        if session.pdf_path and Path(session.pdf_path).exists():
            slide_images = render_pdf_to_images(session.pdf_path, str(img_dir))
        rel_slide_images = [Path(p).relative_to(TMP_DIR).as_posix() for p in slide_images]

        # On-demand legacy session peak generation upgrade
        if not session.peaks and session.media_path and Path(session.media_path).exists():
            try:
                from core.audio_processor import generate_peaks
                logger.info(f"Generating missing peaks for legacy session: {session.session_name}")
                session.peaks = generate_peaks(session.media_path)
                # Re-save session with peaks to cache it
                save_session(session)
            except Exception as e:
                logger.warning(f"Failed to generate peaks on-demand for legacy session: {e}")

        return {
            "session_name": session.session_name,
            "session_description": session.session_description,
            "session_id": sess_id,
            "pdf_path": to_rel_path(session.pdf_path),
            "media_path": to_rel_path(session.media_path),
            "transcript_segments": to_dict_list(session.transcript_segments),
            "slides": to_dict_list(session.slides),
            "final_output": to_dict_list(session.final_output),
            "timestamp": session.timestamp,
            "pipeline_type": session.pipeline_type,
            "slide_images": rel_slide_images,
            "peaks": session.peaks
        }
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Session file not found.")
    except Exception as e:
        logger.error(f"Error loading session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/session/save")
def post_save_session(payload: SaveSessionSchema):
    """Save session details to persistent storage."""
    try:
        # Convert relative paths back to absolute paths
        abs_pdf = resolve_data_path(payload.pdf_path)
        abs_media = resolve_data_path(payload.media_path)

        # Reconstruct dataclasses
        segments = [TranscriptSegment(**s.model_dump()) for s in payload.transcript_segments]
        slides = [Slide(**s.model_dump()) for s in payload.slides]
        notes = [AlignedNote(**n.model_dump()) for n in payload.final_output]

        session = LectureSession(
            session_name=payload.session_name,
            session_description=payload.session_description,
            session_id=payload.session_id,  # Reuse existing session_id if provided by the client
            pdf_path=abs_pdf,
            media_path=abs_media,
            transcript_segments=segments,
            slides=slides,
            final_output=notes,
            timestamp=time.time(),
            pipeline_type=payload.pipeline_type,
            peaks=payload.peaks
        )
        
        session_file = save_session(session)
        return {"status": "success", "filename": os.path.basename(session_file)}
    except Exception as e:
        logger.error(f"Error saving session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.patch("/api/session/{filename}/metadata")
def update_session_metadata(filename: str, payload: UpdateMetadataSchema):
    """Update only the title and description of a session file."""
    try:
        from core.storage import SESSIONS_DIR
        file_path = os.path.join(SESSIONS_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Session file not found.")
            
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        data["session_name"] = payload.session_name
        data["session_description"] = payload.session_description
        data["timestamp"] = time.time()
        
        # Write back atomically
        tmp_file = f"{file_path}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_file, file_path)
        
        return {"status": "success", "message": "Session metadata updated."}
    except Exception as e:
        logger.error(f"Error updating session metadata: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/session/{filename}")
def delete_session(filename: str):
    """Delete a specific session JSON file from storage."""
    try:
        from core.storage import SESSIONS_DIR
        file_path = os.path.join(SESSIONS_DIR, filename)
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="Session file not found.")
        os.remove(file_path)
        return {"status": "success", "message": "Session deleted."}
    except Exception as e:
        logger.error(f"Error deleting session: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/config")
def get_config():
    """Retrieve all configuration settings."""
    try:
        model_options = app_config.get("llm", "model_options", {})
        model_labels = list(model_options.keys())
        default_model = app_config.get("ui_defaults", "default_model", "gemini-3.5-flash")
        
        selected_model_label = model_labels[0] if model_labels else "Auto"
        for label, model_id in model_options.items():
            if model_id == default_model:
                selected_model_label = label
                break

        return {
            "ui_defaults": {
                "is_paid_api": app_config.get("ui_defaults", "is_paid_api", False),
                "default_model": default_model,
                "selected_model_label": selected_model_label,
                "pdf_engine": app_config.get("ui_defaults", "pdf_engine", "Native (PyMuPDF) - Fast"),
                "tx_engine": app_config.get("ui_defaults", "tx_engine", "Local Whisper (CPU) - Private"),
            },
            "audio": {
                "whisper_model_size": app_config.get("audio", "whisper_model_size", "base"),
                "sample_rate": app_config.get("audio", "sample_rate", 16000),
            },
            "alignment": {
                "min_chunk_duration_sec": app_config.get("alignment", "min_chunk_duration_sec", 180),
                "max_chunk_duration_sec": app_config.get("alignment", "max_chunk_duration_sec", 300),
            },
            "pdf": {
                "render_zoom": app_config.get("pdf", "render_zoom", 2.0),
            },
            "video": {
                "matching_strategy": app_config.get("video", "matching_strategy", "hybrid"),
                "frame_sample_rate": app_config.get("video", "frame_sample_rate", 1),
                "ssim_threshold": app_config.get("video", "ssim_threshold", 0.85),
            },
            "model_options": model_options,
            "model_priority": app_config.get("llm", "model_priority", []),
            "rpm_limits": app_config.get("llm", "rpm_limits", {}),
        }
    except Exception as e:
        logger.error(f"Error fetching configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config")
def post_config(payload: ConfigUpdateSchema):
    """Save configuration updates persistently."""
    try:
        if payload.is_paid_api is not None:
            app_config.set("ui_defaults", "is_paid_api", payload.is_paid_api)
        if payload.default_model is not None:
            app_config.set("ui_defaults", "default_model", payload.default_model)
        if payload.pdf_engine is not None:
            app_config.set("ui_defaults", "pdf_engine", payload.pdf_engine)
        if payload.tx_engine is not None:
            app_config.set("ui_defaults", "tx_engine", payload.tx_engine)
            
        if payload.whisper_model_size is not None:
            app_config.set("audio", "whisper_model_size", payload.whisper_model_size)
        if payload.sample_rate is not None:
            app_config.set("audio", "sample_rate", payload.sample_rate)
            
        if payload.min_chunk_duration_sec is not None:
            app_config.set("alignment", "min_chunk_duration_sec", payload.min_chunk_duration_sec)
        if payload.max_chunk_duration_sec is not None:
            app_config.set("alignment", "max_chunk_duration_sec", payload.max_chunk_duration_sec)
            
        if payload.render_zoom is not None:
            app_config.set("pdf", "render_zoom", payload.render_zoom)
            
        if payload.matching_strategy is not None:
            app_config.set("video", "matching_strategy", payload.matching_strategy)
        if payload.frame_sample_rate is not None:
            app_config.set("video", "frame_sample_rate", payload.frame_sample_rate)
        if payload.ssim_threshold is not None:
            app_config.set("video", "ssim_threshold", payload.ssim_threshold)

        if payload.model_priority is not None:
            app_config.set("llm", "model_priority", payload.model_priority)

        app_config.save()
        return {"status": "success", "message": "Configuration saved successfully."}
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/config/reset")
def reset_config():
    """Reset configuration back to factory defaults."""
    try:
        app_config.reset_defaults()
        return {"status": "success", "message": "Configuration reset to factory defaults successfully."}
    except Exception as e:
        logger.error(f"Error resetting configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _list_files_in_dir(directory: str, extensions: tuple, exclude_suffix: str = None) -> list[dict]:
    """Helper to retrieve, format and sort files in a directory."""
    if not os.path.exists(directory):
        return []
    files = []
    for f in os.listdir(directory):
        f_path = os.path.join(directory, f)
        if os.path.isfile(f_path) and f.lower().endswith(extensions):
            if exclude_suffix and f.lower().endswith(exclude_suffix):
                continue
            stat = os.stat(f_path)
            files.append({
                "name": f,
                "relative_path": Path(f_path).relative_to(DATA_STORAGE_DIR).as_posix(),
                "size_bytes": stat.st_size,
                "modified_time": stat.st_mtime
            })
    files.sort(key=lambda x: x["modified_time"], reverse=True)
    return files


@app.get("/api/files")
def get_stored_files():
    """Retrieve lists of existing documents and media in files/ directories."""
    try:
        docs_dir = os.path.join(FILES_DIR, "documents")
        media_dir = os.path.join(FILES_DIR, "media")
        
        return {
            "documents": _list_files_in_dir(docs_dir, ('.pdf', '.pptx', '.ppt')),
            "media": _list_files_in_dir(media_dir, ('.mp4', '.mp3', '.wav'), exclude_suffix='_audio.wav')
        }
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    file_type: str = Form(...)  # "pdf" or "media"
):
    """Upload PDF or media file, including auto-converting PPTX to PDF."""
    try:
        contents = await file.read()
        
        if file_type == "pdf":
            target_dir = os.path.join(FILES_DIR, "documents")
            ext = os.path.splitext(file.filename)[1].lower()
            
            if ext in [".pptx", ".ppt"]:
                # Save presentation temporarily
                temp_pptx_dir = os.path.join(TMP_DIR, f"pptx_{uuid.uuid4().hex[:6]}")
                saved_pptx = save_file(contents, file.filename, temp_pptx_dir, use_registry=False)
                
                # Convert to PDF
                temp_pdf = os.path.join(temp_pptx_dir, "converted.pdf")
                convert_pptx_to_pdf(saved_pptx, temp_pdf)
                
                # Read converted PDF and register it
                with open(temp_pdf, "rb") as f:
                    pdf_bytes = f.read()
                pdf_name = os.path.splitext(file.filename)[0] + ".pdf"
                saved_path = save_file(pdf_bytes, pdf_name, target_dir, use_registry=True)
            else:
                saved_path = save_file(contents, file.filename, target_dir, use_registry=True)
        else:
            target_dir = os.path.join(FILES_DIR, "media")
            saved_path = save_file(contents, file.filename, target_dir, use_registry=True)

        rel_path = Path(saved_path).relative_to(DATA_STORAGE_DIR).as_posix()
        return {
            "filename": file.filename,
            "absolute_path": saved_path,
            "relative_path": rel_path
        }
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ═══════════════════════════════════════════════════════════════════════════════
# PIPELINE EXECUTION ENGINE (WEBSOCKET)
# ═══════════════════════════════════════════════════════════════════════════════

@app.websocket("/api/process/stream")
async def websocket_process_stream(websocket: WebSocket):
    await websocket.accept()
    logger.info("WebSocket connection established for processing pipeline.")

    # 1. Receive configuration payload first
    try:
        config_data = await websocket.receive_text()
        config = json.loads(config_data)
    except Exception as e:
        logger.error(f"Failed to receive config payload: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
        return

    # 2. Setup cancellation event and disconnect monitoring task
    cancellation_event = threading.Event()

    async def monitor_disconnect():
        try:
            while not cancellation_event.is_set():
                # Keep reading to check if client disconnected
                await websocket.receive_text()
        except WebSocketDisconnect:
            logger.info("WebSocket client disconnected, signalling cancellation.")
            cancellation_event.set()
        except Exception as e:
            logger.info(f"WebSocket read error: {e}, signalling cancellation.")
            cancellation_event.set()

    monitor_task = asyncio.create_task(monitor_disconnect())

    try:
        # Config fields
        pdf_path = config.get("pdf_path")
        media_path = config.get("media_path")
        pipeline_mode = config.get("pipeline_mode", "audio")
        pdf_engine = config.get("pdf_engine", "Native")
        tx_engine = config.get("tx_engine", "Local")
        selected_model = config.get("selected_model", "gemini-3.5-flash")
        api_key = config.get("api_key", "")
        is_paid_api = config.get("is_paid_api", False)

        loop = asyncio.get_running_loop()

        # Thread-safe async callback builder
        def send_status(
            stage: str, 
            progress: float, 
            msg: str, 
            models_list=None, 
            active_model=None, 
            model_status=None, 
            model_message=None, 
            dead_models=None,
            model_call_stats=None
        ):
            if cancellation_event.is_set():
                raise PipelineCancelledError("Pipeline run aborted because the client disconnected.")
            
            payload = {
                "status": "processing",
                "stage": stage,
                "progress": progress,
                "message": msg,
                "models_list": models_list,
                "active_model": active_model,
                "model_status": model_status,
                "model_message": model_message,
                "dead_models": dead_models,
                "model_call_stats": model_call_stats
            }

            asyncio.run_coroutine_threadsafe(
                websocket.send_json(payload),
                loop
            )

        # Initialize the decoupled job
        job = PipelineJob(
            pdf_path=pdf_path,
            media_path=media_path,
            pipeline_mode=pipeline_mode,
            pdf_engine=pdf_engine,
            tx_engine=tx_engine,
            selected_model=selected_model,
            api_key=api_key,
            is_paid_api=is_paid_api,
            status_callback=send_status,
            cancellation_event=cancellation_event
        )

        # Run blocking thread pipeline run
        result = await loop.run_in_executor(None, job.run)

        # Return final data payload over WS
        await websocket.send_json({
            "status": "complete",
            "data": result
        })

    except PipelineCancelledError:
        logger.info("Pipeline execution cancelled: client disconnected.")
    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        if cancellation_event.is_set():
            logger.info("Pipeline run aborted due to cancellation event.")
        else:
            logger.error(f"Error in pipeline process WebSocket: {e}")
            try:
                await websocket.send_json({
                    "status": "error",
                    "message": str(e)
                })
            except Exception:
                pass
    finally:
        cancellation_event.set()  # Ensure event is set to break monitor loop
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    import sys

    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    # Modify uvicorn logging config to route to stdout and use custom formatting
    log_config = uvicorn.config.LOGGING_CONFIG
    if "handlers" in log_config:
        if "default" in log_config["handlers"]:
            log_config["handlers"]["default"]["stream"] = "ext://sys.stdout"
            
        # Define formatter and filter for uvicorn
        log_config["filters"] = log_config.get("filters", {})
        log_config["filters"]["process_label"] = {
            "()": lambda: ProcessLabelFilter()
        }
        
        log_config["formatters"] = log_config.get("formatters", {})
        log_config["formatters"]["custom_uvicorn"] = {
            "()": "logging.Formatter",
            "fmt": "[%(process_label)s] %(levelname)s: %(message)s"
        }
        
        # Apply filter and custom formatter to handlers
        if "default" in log_config["handlers"]:
            log_config["handlers"]["default"]["filters"] = log_config["handlers"]["default"].get("filters", []) + ["process_label"]
            log_config["handlers"]["default"]["formatter"] = "custom_uvicorn"
            
        if "access" in log_config["handlers"]:
            log_config["handlers"]["access"]["filters"] = log_config["handlers"]["access"].get("filters", []) + ["process_label"]
            log_config["handlers"]["access"]["formatter"] = "custom_uvicorn"

    config = uvicorn.Config(app=app, host="0.0.0.0", port=8000, loop="asyncio", log_config=log_config)
    server = uvicorn.Server(config)

    try:
        if sys.platform == 'win32':
            # Manually create and set the Selector loop to bypass Uvicorn loop overrides
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(server.serve())
        else:
            uvicorn.run(app, host="0.0.0.0", port=8000)
    except KeyboardInterrupt:
        logger.info("Server stopped by user keyboard interrupt.")
        try:
            sys.exit(0)
        except SystemExit:
            os._exit(0)
