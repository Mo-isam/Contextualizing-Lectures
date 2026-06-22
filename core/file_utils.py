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
        
        # Resolve to current data_storage_dir to support worktrees and portability
        if os.path.isabs(existing_path):
            norm_path = os.path.normpath(existing_path)
            parts = norm_path.split(os.sep)
            if "data_storage" in parts:
                idx = parts.index("data_storage")
                rel_path = os.path.join(*parts[idx+1:])
            elif "files" in parts:
                idx = parts.index("files")
                rel_path = os.path.join(*parts[idx:])
            else:
                rel_path = os.path.basename(existing_path)
        else:
            rel_path = existing_path
            
        resolved_path = os.path.normpath(os.path.join(data_storage_dir, rel_path))
        
        # Ensure parent directory exists
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        
        if not os.path.exists(resolved_path):
            # Save the file to the resolved path since it doesn't exist in the current workspace
            with open(resolved_path, "wb") as f:
                f.write(file_bytes)
                
        # Update registry with relative path for future portability
        portable_path = rel_path.replace("\\", "/")
        if registry[file_hash] != portable_path:
            registry[file_hash] = portable_path
            try:
                with open(registry_path, "w", encoding="utf-8") as f:
                    json.dump(registry, f, indent=2)
            except Exception:
                pass
                
        return resolved_path

    # 3. Clean Filename Generation (Handle naming collisions & reuse identical physical files)
    base_name, ext = os.path.splitext(file_name)
    # Allow spaces in names for better UX, but strip weird characters
    clean_base = "".join([c if c.isalnum() or c in ("-", "_", " ") else "_" for c in base_name]).strip()
    
    final_path = os.path.join(target_dir, f"{clean_base}{ext.lower()}")
    counter = 1
    
    # If name exists, check if the physical file content is identical (reuse it if it is)
    while os.path.exists(final_path):
        try:
            with open(final_path, "rb") as f:
                existing_bytes = f.read()
            existing_hash = hashlib.sha256(existing_bytes).hexdigest()
        except Exception:
            existing_hash = None
            
        if existing_hash == file_hash:
            # The physical file on disk has identical content. We can register and reuse it!
            rel_final_path = os.path.relpath(final_path, data_storage_dir).replace("\\", "/")
            registry[file_hash] = rel_final_path
            os.makedirs(data_storage_dir, exist_ok=True)
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
            return final_path
            
        final_path = os.path.join(target_dir, f"{clean_base} ({counter}){ext.lower()}")
        counter += 1

    # 4. Save and Register
    with open(final_path, "wb") as f:
        f.write(file_bytes)
        
    rel_final_path = os.path.relpath(final_path, data_storage_dir).replace("\\", "/")
    registry[file_hash] = rel_final_path
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