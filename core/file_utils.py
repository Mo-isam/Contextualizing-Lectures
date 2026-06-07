"""
file_utils.py
-------------
Pure backend file I/O operations.
Contains no Streamlit dependencies or UI logic.
"""
import os
import threading

SUPPORTED_MEDIA_EXT = {".mp4", ".mp3", ".wav"}

# Global lock to prevent COM apartment-thread collisions when multiple PPTX files are converted concurrently.
_pptx_lock = threading.Lock()

import hashlib

def save_file(file_bytes: bytes, file_name: str, target_dir: str) -> str:
    """
    Save raw bytes to disk using a readable name with a deduplication hash.
    Returns the absolute path to the saved file.
    """
    os.makedirs(target_dir, exist_ok=True)
    
    # Calculate short hash for deduplication
    file_hash = hashlib.sha256(file_bytes).hexdigest()[:8]
    
    base_name, ext = os.path.splitext(file_name)
    # Sanitize base name
    clean_base = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in base_name]).strip()
    
    smart_file_name = f"{clean_base}_{file_hash}{ext.lower()}"
    file_path = os.path.join(target_dir, smart_file_name)
    
    # Instant deduplication: skip writing if exact file already exists
    if not os.path.exists(file_path):
        with open(file_path, "wb") as f:
            f.write(file_bytes)
            
    return file_path

def convert_pptx_to_pdf(pptx_path: str, pdf_path: str):
    """
    Convert a PowerPoint file (.pptx or .ppt) to a PDF using PowerPoint's COM interface on Windows.
    Uses comtypes for clean, lightweight COM wrapping.
    """
    import sys
    import comtypes.client

    if sys.platform != "win32":
        raise NotImplementedError("PPTX-to-PDF conversion is only supported on Windows.")

    abs_pptx = os.path.abspath(pptx_path)
    abs_pdf = os.path.abspath(pdf_path)

    comtypes.CoInitialize()
    try:
        with _pptx_lock:
            powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        pres = powerpoint.Presentations.Open(abs_pptx, WithWindow=False)
        pres.SaveAs(abs_pdf, 32)
        pres.Close()
        powerpoint.Quit()
    except Exception as e:
        raise RuntimeError(f"PowerPoint COM conversion failed: {e}")
    finally:
        comtypes.CoUninitialize()