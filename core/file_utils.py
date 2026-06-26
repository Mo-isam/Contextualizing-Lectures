"""
file_utils.py
-------------
Pure backend file I/O operations.
Contains no Streamlit dependencies or UI logic.
"""
import os
import json
import hashlib

SUPPORTED_MEDIA_EXT = {".mp4", ".mp3", ".wav"}


def save_file(file_bytes: bytes, file_name: str, target_dir: str, use_registry: bool = True) -> str:
    """
    Save raw bytes to disk cleanly. Uses a JSON registry for invisible deduplication 
    to preserve clean filenames while preventing identical files from duplicating.
    """
    os.makedirs(target_dir, exist_ok=True)
    
    if not use_registry:
        file_path = os.path.join(target_dir, file_name)
        with open(file_path, "wb") as f:
            f.write(file_bytes)
        return file_path

    file_hash = hashlib.sha256(file_bytes).hexdigest()
    
    root_dir = os.path.dirname(os.path.dirname(__file__))
    data_storage_dir = os.path.join(root_dir, "data_storage")
    registry_path = os.path.join(data_storage_dir, "file_registry.json")
    
    registry = {}
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry = json.load(f)
        except Exception:
            pass

    if file_hash in registry:
        existing_path = registry[file_hash]
        
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
        os.makedirs(os.path.dirname(resolved_path), exist_ok=True)
        
        if not os.path.exists(resolved_path):
            with open(resolved_path, "wb") as f:
                f.write(file_bytes)
                
        portable_path = rel_path.replace("\\", "/")
        if registry[file_hash] != portable_path:
            registry[file_hash] = portable_path
            try:
                with open(registry_path, "w", encoding="utf-8") as f:
                    json.dump(registry, f, indent=2)
            except Exception:
                pass
                
        return resolved_path

    base_name, ext = os.path.splitext(file_name)
    clean_base = "".join([c if c.isalnum() or c in ("-", "_", " ") else "_" for c in base_name]).strip()
    
    final_path = os.path.join(target_dir, f"{clean_base}{ext.lower()}")
    counter = 1
    
    while os.path.exists(final_path):
        try:
            with open(final_path, "rb") as f:
                existing_bytes = f.read()
            existing_hash = hashlib.sha256(existing_bytes).hexdigest()
        except Exception:
            existing_hash = None
            
        if existing_hash == file_hash:
            rel_final_path = os.path.relpath(final_path, data_storage_dir).replace("\\", "/")
            registry[file_hash] = rel_final_path
            os.makedirs(data_storage_dir, exist_ok=True)
            with open(registry_path, "w", encoding="utf-8") as f:
                json.dump(registry, f, indent=2)
            return final_path
            
        final_path = os.path.join(target_dir, f"{clean_base} ({counter}){ext.lower()}")
        counter += 1

    with open(final_path, "wb") as f:
        f.write(file_bytes)
        
    rel_final_path = os.path.relpath(final_path, data_storage_dir).replace("\\", "/")
    registry[file_hash] = rel_final_path
    os.makedirs(data_storage_dir, exist_ok=True)
    with open(registry_path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2)
        
    return final_path
