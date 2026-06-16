"""
file_utils.py
-------------
Pure backend file I/O operations.
Contains no Streamlit dependencies or UI logic.
"""
import os
import json
import hashlib
import threading

SUPPORTED_MEDIA_EXT = {".mp4", ".mp3", ".wav"}

# Global lock to prevent COM apartment-thread collisions when multiple PPTX files are converted concurrently.
_pptx_lock = threading.Lock()

def save_file(file_bytes: bytes, file_name: str, target_dir: str, use_registry: bool = True) -> str:
    """
    Save raw bytes to disk cleanly. Uses a JSON registry for invisible deduplication 
    to preserve clean filenames while preventing identical files from duplicating.
    """
    os.makedirs(target_dir, exist_ok=True)
    
    if not use_registry:
        # Simple fallback for temporary files (e.g., transient PPTX conversions)
        file_path = os.path.join(target_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return file_path

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    # Locate data_storage dynamically (root/core/.. -> root/data_storage)
    root_dir = os.path.dirname(os.path.dirname(__file__))
    data_storage_dir = os.path.join(root_dir, "data_storage")
    registry_path = os.path.join(data_storage_dir, "file_registry.json")
    
    # 1. Load Registry
    registry = {}
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            pass

    # 2. Exact Match Deduplication
    if file_hash in registry:
        existing_path = registry[file_hash]
        if os.path.exists(existing_path):
            return existing_path

    # 3. Clean Filename Generation (Handle naming collisions)
    base_name, ext = os.path.splitext(file_name)
    # Allow spaces in names for better UX, but strip weird characters
    clean_base = "".join([c if c.isalnum() or c in ("-", "_", " ") else "_" for c in base_name]).strip()
    
    final_path = os.path.join(target_dir, f"{clean_base}{ext.lower()}")
    counter = 1
    
    # If name exists but hash is different (e.g., Biology 'lecture.pdf' vs Physics 'lecture.pdf')
    while os.path.exists(final_path):
        final_path = os.path.join(target_dir, f"{clean_base} ({counter}){ext.lower()}")
        counter += 1

    # 4. Save and Register
    with open(final_path, "wb") as f:
        f.write(file_bytes)
        
    registry[file_hash] = final_path
    os.makedirs(data_storage_dir, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    return final_path

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