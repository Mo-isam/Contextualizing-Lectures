import os
import uuid
import logging
import threading
from typing import Callable, Optional

from core.storage import TMP_DIR, resolve_data_path

logger = logging.getLogger(__name__)

class PipelineCancelledError(BaseException):
    """Exception raised when the pipeline execution is cancelled by client disconnect."""
    pass

class PipelineJob:
    def __init__(
        self,
        pdf_path: str,
        media_path: str,
        pipeline_mode: str,
        pdf_engine: str,
        tx_engine: str,
        selected_model: str,
        api_key: str,
        is_paid_api: bool,
        status_callback: Callable,
        cancellation_event: threading.Event
    ):
        self.pdf_path = pdf_path
        self.media_path = media_path
        self.pipeline_mode = pipeline_mode
        self.pdf_engine = pdf_engine
        self.tx_engine = tx_engine
        self.selected_model = selected_model
        self.api_key = api_key
        self.is_paid_api = is_paid_api
        self.status_callback = status_callback
        self.cancellation_event = cancellation_event
        
        # Model status tracking attributes
        self.models_to_try = []
        self.active_model = None
        self.model_status = None
        self.model_message = None
        self.dead_models = []
        self.model_call_stats = {}

    def send_status(self, stage: str, progress: float, msg: str, **kwargs):
        if self.cancellation_event.is_set():
            raise PipelineCancelledError("Pipeline run aborted because the client disconnected.")
            
        # Dynamically update any passed model metadata fields
        if "active_model" in kwargs:
            self.active_model = kwargs["active_model"]
        if "model_status" in kwargs:
            self.model_status = kwargs["model_status"]
        if "model_message" in kwargs:
            self.model_message = kwargs["model_message"]
        if "dead_models" in kwargs:
            self.dead_models = kwargs["dead_models"]
        if "model_call_stats" in kwargs:
            self.model_call_stats = kwargs["model_call_stats"]
            
        if self.status_callback:
            try:
                self.status_callback(
                    stage, 
                    progress, 
                    msg,
                    models_list=self.models_to_try,
                    active_model=self.active_model,
                    model_status=self.model_status,
                    model_message=self.model_message,
                    dead_models=self.dead_models,
                    model_call_stats=self.model_call_stats
                )
            except Exception as e:
                logger.warning(f"Error in status callback: {e}")

    def run(self) -> dict:
        # Check cancellation at the very beginning
        if self.cancellation_event.is_set():
            raise PipelineCancelledError("Pipeline run aborted because the client disconnected.")

        # Late imports inside the run function to conserve boot RAM
        from core.system_loader import preload_dependencies
        from core.llm_service import discover_available_models, GEMINI_MODEL_PRIORITY
        from core.pdf_processor import render_pdf_to_images, extract_slide_text, extract_slide_text_ai, format_slides_for_prompt
        from core.video_processor import extract_and_detect_transitions, match_keyframes_to_slides
        from core.audio_processor import process_media_file
        from core.ai_aligner import align_transcript_to_slides, align_video_to_slides

        # Resolve paths to absolute paths
        abs_pdf_path = resolve_data_path(self.pdf_path)
        abs_media_path = resolve_data_path(self.media_path)

        # Create session temp folder
        session_temp_dir = os.path.join(TMP_DIR, f"session_{uuid.uuid4().hex[:8]}")
        os.makedirs(session_temp_dir, exist_ok=True)

        # STAGE 0: Preflight checks
        self.send_status("preflight", 0.05, "Performing pre-flight checklist...")
        preload_dependencies(
            pipeline_mode=self.pipeline_mode,
            pdf_engine=self.pdf_engine,
            tx_engine=self.tx_engine,
            status_callback=lambda msg: self.send_status("preflight", 0.1, msg)
        )
        self.send_status("preflight", 1.0, "Ready!")

        # Model prioritization mapping (Curated from config.yaml model priority list)
        models_to_try = [self.selected_model] if self.selected_model else []
        for m in GEMINI_MODEL_PRIORITY:
            if m not in models_to_try:
                models_to_try.append(m)
        self.models_to_try = models_to_try

        # STAGE 1: PDF Processing
        self.send_status("pdf", 0.05, "Rendering slide PDF to images...")
        img_dir = os.path.join(session_temp_dir, "slide_images")
        slide_images = render_pdf_to_images(abs_pdf_path, img_dir)
        
        # Send image folder name relative to tmp so frontend can serve them directly
        rel_slide_images = [os.path.relpath(p, TMP_DIR).replace("\\", "/") for p in slide_images]

        self.send_status("pdf", 0.3, "Extracting text content from slides...")
        if "Native" in self.pdf_engine:
            slides = extract_slide_text(abs_pdf_path)
        else:
            slides = extract_slide_text_ai(
                slide_images, self.api_key, models_to_try, 
                is_paid=self.is_paid_api, 
                progress_cb=lambda frac, msg, **kwargs: self.send_status("pdf", 0.3 + frac * 0.7, msg, **kwargs)
            )
        self.send_status("pdf", 1.0, f"Extracted text from {len(slides)} slides.")

        # STAGE 2: Video Transition Detection (if applicable)
        visual_chapters = []
        if self.pipeline_mode == "visual":
            self.send_status("video", 0.05, "Analyzing video timeline for slide cuts...")
            video_frames_dir = os.path.join(session_temp_dir, "video_frames")
            
            chapters = extract_and_detect_transitions(
                abs_media_path, video_frames_dir,
                progress_cb=lambda frac, msg: self.send_status("video", 0.05 + frac * 0.45, msg)
            )
            
            self.send_status("video", 0.5, "Geometric matching keyframes to PDF slides...")
            slides_text = format_slides_for_prompt(slides)
            visual_chapters = match_keyframes_to_slides(
                chapters, slide_images, slides_text, api_key=self.api_key,
                models_to_try=models_to_try,
                progress_cb=lambda frac, msg, **kwargs: self.send_status("video", 0.5 + frac * 0.5, msg, **kwargs)
            )
            self.send_status("video", 1.0, "Video keyframe transition mapping complete.")

        # STAGE 3: Audio Transcription
        self.send_status("audio", 0.05, "Starting audio transcribing...")
        engine_mode = "ai" if "AI Audio" in self.tx_engine else "local"
        
        transcript_segments = process_media_file(
            abs_media_path, session_temp_dir, 
            engine=engine_mode, api_key=self.api_key, 
            models_to_try=models_to_try, is_paid=self.is_paid_api,
            progress_cb=lambda frac, msg, **kwargs: self.send_status("audio", frac, msg, **kwargs)
        )
        self.send_status("audio", 1.0, "Transcribing complete.")

        # STAGE 4: Fusion & Alignment
        self.send_status("alignment", 0.05, "Fusing temporal cues and generating semantic note alignments...")
        
        if self.pipeline_mode == "visual":
            final_output = align_video_to_slides(
                transcript_segments, visual_chapters, slides, 
                self.api_key, models_to_try, self.is_paid_api,
                progress_cb=lambda frac, msg, **kwargs: self.send_status("alignment", frac, msg, **kwargs)
            )
        else:
            final_output = align_transcript_to_slides(
                transcript_segments, slides, self.api_key, models_to_try, self.is_paid_api,
                progress_cb=lambda frac, msg, **kwargs: self.send_status("alignment", frac, msg, **kwargs)
            )
        # Generate audio peaks for visualizer waveform rendering
        self.send_status("alignment", 0.95, "Generating audio visualizer waveform peaks...")
        try:
            from core.audio_analysis import generate_peaks
            peaks = generate_peaks(abs_media_path)
        except Exception as e:
            logger.warning(f"Failed to generate peaks during pipeline: {e}")
            peaks = []

        self.send_status("alignment", 1.0, "Alignment complete!")

        return {
            "transcript_segments": [t.__dict__ for t in transcript_segments],
            "slides": [s.__dict__ for s in slides],
            "final_output": [n.__dict__ for n in final_output],
            "slide_images": rel_slide_images,
            "peaks": peaks
        }
