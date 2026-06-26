"""
system_loader.py
----------------
Smart pre-flight dependency loader for the processing pipeline.

Uses a Strategy Pattern to parse user settings and lazy-load
heavy dependencies (PyTorch, OpenCV, PyMuPDF) only when the
user has explicitly chosen a configuration that requires them.
"""
import time

def _load_llm_client():
    """Loads the Google GenAI SDK and its dependencies."""
    import google.genai

def _load_native_pdf_engine():
    """Loads PyMuPDF (fitz) for fast local PDF text extraction."""
    import fitz

def _load_local_audio_engine():
    """Loads OpenAI Whisper and its PyTorch backend."""
    import whisper

def _load_visual_engine():
    """Loads OpenCV and Scikit-Image for video transition detection."""
    import cv2
    from skimage.metrics import structural_similarity

def preload_dependencies(pipeline_mode: str, pdf_engine: str, tx_engine: str, status_callback):
    """
    Acts as a smart pre-flight checklist. 
    Only loads the heavy libraries required for the user's specific configuration.
    """
    # 1. Always load the LLM client (used by Semantic AI, AI PDF, AI Audio, and Insights)
    status_callback("Loading LLM Client...")
    _load_llm_client()
    
    # 2. Check PDF Extraction method
    if "Native" in pdf_engine:
        status_callback("Loading Native PDF Engine...")
        _load_native_pdf_engine()
        
    # 3. Check Audio Transcription method
    if "Local" in tx_engine:
        status_callback("Loading Local Audio Engine (PyTorch/Whisper)...")
        _load_local_audio_engine()
        
    # 4. Check Pipeline Mode
    if pipeline_mode == "visual":
        status_callback("Loading Visual CV Engine (OpenCV)...")
        _load_visual_engine()
        
    # Brief pause just to let the UI breathe and show completion
    time.sleep(0.2)