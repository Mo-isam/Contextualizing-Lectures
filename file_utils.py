"""
file_utils.py
-------------
Pure backend file I/O operations.
Contains no Streamlit dependencies or UI logic.
"""
import os

SUPPORTED_MEDIA_EXT = {".mp4", ".mp3", ".wav"}

def save_file(file_bytes: bytes, file_name: str, target_dir: str) -> str:
    """
    Save raw bytes to disk and return its absolute path.
    """
    os.makedirs(target_dir, exist_ok=True)
    file_path = os.path.join(target_dir, file_name)
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
        powerpoint = comtypes.client.CreateObject("Powerpoint.Application")
        pres = powerpoint.Presentations.Open(abs_pptx, WithWindow=False)
        pres.SaveAs(abs_pdf, 32)
        pres.Close()
        powerpoint.Quit()
    except Exception as e:
        raise RuntimeError(f"PowerPoint COM conversion failed: {e}")
    finally:
        comtypes.CoUninitialize()