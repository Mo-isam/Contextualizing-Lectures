import os
import json
import uuid
import time
import logging
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Import core modules
from core.storage import save_session, load_session, list_saved_sessions, DATA_STORAGE_DIR, FILES_DIR
from core.file_utils import save_file, convert_pptx_to_pdf
from core.models import TranscriptSegment, Slide, AlignedNote, LectureSession
from core.config import app_config

logging.basicConfig(level=logging.INFO)
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
    slide_number: int
    text: str

class TranscriptSegmentSchema(BaseModel):
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
            return os.path.relpath(abs_path, DATA_STORAGE_DIR).replace("\\", "/")

        # Render slide PDF to images for display in React viewer
        from core.pdf_processor import render_pdf_to_images
        sess_id = session.session_id or uuid.uuid4().hex[:8]
        session_temp_dir = os.path.join(TMP_DIR, f"session_{sess_id}")
        os.makedirs(session_temp_dir, exist_ok=True)
        img_dir = os.path.join(session_temp_dir, "slide_images")
        
        slide_images = []
        if session.pdf_path and os.path.exists(session.pdf_path):
            slide_images = render_pdf_to_images(session.pdf_path, img_dir)
        rel_slide_images = [os.path.relpath(p, TMP_DIR).replace("\\", "/") for p in slide_images]

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
            "slide_images": rel_slide_images
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
        abs_pdf = os.path.join(DATA_STORAGE_DIR, os.path.normpath(payload.pdf_path))
        abs_media = os.path.join(DATA_STORAGE_DIR, os.path.normpath(payload.media_path))

        # Reconstruct dataclasses
        segments = [TranscriptSegment(**s.dict()) for s in payload.transcript_segments]
        slides = [Slide(**s.dict()) for s in payload.slides]
        notes = [AlignedNote(**n.dict()) for n in payload.final_output]

        session = LectureSession(
            session_name=payload.session_name,
            session_description=payload.session_description,
            session_id=None,
            pdf_path=abs_pdf,
            media_path=abs_media,
            transcript_segments=segments,
            slides=slides,
            final_output=notes,
            timestamp=time.time(),
            pipeline_type=payload.pipeline_type
        )
        
        session_file = save_session(session)
        return {"status": "success", "filename": os.path.basename(session_file)}
    except Exception as e:
        logger.error(f"Error saving session: {e}")
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

        app_config.save()
        return {"status": "success", "message": "Configuration saved successfully."}
    except Exception as e:
        logger.error(f"Error saving configuration: {e}")
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

        rel_path = os.path.relpath(saved_path, DATA_STORAGE_DIR).replace("\\", "/")
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

    try:
        # Receive configuration payload
        config_data = await websocket.receive_text()
        config = json.loads(config_data)

        # Config fields
        pdf_path = config.get("pdf_path")
        media_path = config.get("media_path")
        pipeline_mode = config.get("pipeline_mode", "audio")
        pdf_engine = config.get("pdf_engine", "Native")
        tx_engine = config.get("tx_engine", "Local")
        selected_model = config.get("selected_model", "gemini-3.5-flash")
        api_key = config.get("api_key", "")
        is_paid_api = config.get("is_paid_api", False)

        # Resolve paths to absolute paths
        abs_pdf_path = os.path.join(DATA_STORAGE_DIR, os.path.normpath(pdf_path))
        abs_media_path = os.path.join(DATA_STORAGE_DIR, os.path.normpath(media_path))

        loop = asyncio.get_running_loop()

        # Thread-safe async callback builder
        def send_status(stage: str, progress: float, msg: str):
            asyncio.run_coroutine_threadsafe(
                websocket.send_json({
                    "status": "processing",
                    "stage": stage,
                    "progress": progress,
                    "message": msg
                }),
                loop
            )

        # Blocking pipeline runner to run in thread pool
        def run_pipeline():
            # Late imports inside the worker thread to conserve boot RAM
            from core.system_loader import preload_dependencies
            from core.llm_service import discover_available_models, GEMINI_MODEL_PRIORITY
            from core.pdf_processor import render_pdf_to_images, extract_slide_text, extract_slide_text_ai, format_slides_for_prompt
            from core.video_processor import extract_and_detect_transitions, match_keyframes_to_slides
            from core.audio_processor import process_media_file
            from core.ai_aligner import align_transcript_to_slides, align_video_to_slides

            # Create session temp folder
            session_temp_dir = os.path.join(TMP_DIR, f"session_{uuid.uuid4().hex[:8]}")
            os.makedirs(session_temp_dir, exist_ok=True)

            # STAGE 0: Preflight checks
            send_status("preflight", 0.05, "Performing pre-flight checklist...")
            preload_dependencies(
                pipeline_mode=pipeline_mode,
                pdf_engine=pdf_engine,
                tx_engine=tx_engine,
                status_callback=lambda msg: send_status("preflight", 0.1, msg)
            )
            send_status("preflight", 1.0, "Ready!")

            # Model prioritization mapping
            discovered_models = []
            if is_paid_api and api_key:
                try:
                    discovered_models = discover_available_models(api_key)
                except Exception:
                    pass
            models_to_try = [selected_model] if selected_model else []
            for m in discovered_models:
                if m not in models_to_try: models_to_try.append(m)
            for m in GEMINI_MODEL_PRIORITY:
                if m not in models_to_try: models_to_try.append(m)

            # STAGE 1: PDF Processing
            send_status("pdf", 0.05, "Rendering slide PDF to images...")
            img_dir = os.path.join(session_temp_dir, "slide_images")
            slide_images = render_pdf_to_images(abs_pdf_path, img_dir)
            
            # Send image folder name relative to tmp so frontend can serve them directly
            rel_img_dir = os.path.relpath(img_dir, TMP_DIR).replace("\\", "/")
            rel_slide_images = [os.path.relpath(p, TMP_DIR).replace("\\", "/") for p in slide_images]

            send_status("pdf", 0.3, "Extracting text content from slides...")
            if "Native" in pdf_engine:
                slides = extract_slide_text(abs_pdf_path)
            else:
                slides = extract_slide_text_ai(
                    slide_images, api_key, models_to_try, 
                    is_paid=is_paid_api, 
                    progress_cb=lambda frac, msg: send_status("pdf", 0.3 + frac * 0.7, msg)
                )
            send_status("pdf", 1.0, f"Extracted text from {len(slides)} slides.")

            # STAGE 2: Video Transition Detection (if applicable)
            visual_chapters = []
            if pipeline_mode == "visual":
                send_status("video", 0.05, "Analyzing video timeline for slide cuts...")
                video_frames_dir = os.path.join(session_temp_dir, "video_frames")
                
                chapters = extract_and_detect_transitions(
                    abs_media_path, video_frames_dir,
                    progress_cb=lambda frac, msg: send_status("video", 0.05 + frac * 0.45, msg)
                )
                
                send_status("video", 0.5, "Geometric matching keyframes to PDF slides...")
                slides_text = format_slides_for_prompt(slides)
                visual_chapters = match_keyframes_to_slides(
                    chapters, slide_images, slides_text, api_key=api_key,
                    progress_cb=lambda frac, msg: send_status("video", 0.5 + frac * 0.5, msg)
                )
                send_status("video", 1.0, "Video keyframe transition mapping complete.")

            # STAGE 3: Audio Transcription
            send_status("audio", 0.05, "Starting audio transcribing...")
            engine_mode = "ai" if "AI Audio" in tx_engine else "local"
            
            transcript_segments = process_media_file(
                abs_media_path, session_temp_dir, 
                engine=engine_mode, api_key=api_key, 
                models_to_try=models_to_try, is_paid=is_paid_api,
                progress_cb=lambda frac, msg: send_status("audio", frac, msg)
            )
            send_status("audio", 1.0, "Transcribing complete.")

            # STAGE 4: Fusion & Alignment
            send_status("alignment", 0.05, "Fusing temporal cues and generating semantic note alignments...")
            
            if pipeline_mode == "visual":
                final_output = align_video_to_slides(
                    transcript_segments, visual_chapters, slides, 
                    api_key, models_to_try, is_paid_api,
                    progress_cb=lambda frac, msg: send_status("alignment", frac, msg)
                )
            else:
                final_output = align_transcript_to_slides(
                    transcript_segments, slides, api_key, selected_model, is_paid_api,
                    progress_cb=lambda frac, msg: send_status("alignment", frac, msg)
                )
            send_status("alignment", 1.0, "Alignment complete!")

            return {
                "transcript_segments": [t.__dict__ for t in transcript_segments],
                "slides": [s.__dict__ for s in slides],
                "final_output": [n.__dict__ for n in final_output],
                "slide_images": rel_slide_images
            }

        # Run blocking thread pipeline run
        result = await loop.run_in_executor(None, run_pipeline)

        # Return final data payload over WS
        await websocket.send_json({
            "status": "complete",
            "data": result
        })

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception as e:
        logger.error(f"Error in pipeline process WebSocket: {e}")
        try:
            await websocket.send_json({
                "status": "error",
                "message": str(e)
            })
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
