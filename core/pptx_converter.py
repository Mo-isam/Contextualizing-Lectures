"""
pptx_converter.py
-----------------
PowerPoint-to-PDF conversion using Windows COM (PowerPoint application).
Only supported on Windows.
"""
import os
import sys
import threading

# Global lock to prevent COM apartment-thread collisions when multiple
# PPTX files are converted concurrently.
_pptx_lock = threading.Lock()


def convert_pptx_to_pdf(pptx_path: str, pdf_path: str):
    """
    Convert a PowerPoint file (.pptx or .ppt) to a PDF using PowerPoint's COM interface on Windows.
    Uses comtypes for clean, lightweight COM wrapping.
    """
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
