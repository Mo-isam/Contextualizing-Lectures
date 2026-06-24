"""
pdf_processor.py
----------------
Parses a PDF lecture slide deck using PyMuPDF (fitz) and returns a
structured mapping of page numbers to their text content.
"""

import os
import json
import time
import logging
from PIL import Image

from core.llm_service import generate_content_with_fallback, SafetyFilterError, AllModelsFailedError
from core.models import Slide
from core.config import app_config

logger = logging.getLogger(__name__)


def extract_slide_text(pdf_path: str) -> list[Slide]:
    """
    Extract text from every page of a PDF and return a Slide Text Array.

    Each element in the returned list represents one slide / page:
        {
            "page_number" : int,          # 1-indexed
            "title"       : str,          # first non-empty line (heuristic)
            "text"        : str,          # full page text
        }

    Args:
        pdf_path : Absolute path to the PDF file.

    Returns:
        List of slide dicts ordered by page number.

    Raises:
        FileNotFoundError : If the PDF does not exist.
        ValueError        : If the file is not a readable PDF.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    slides = []

    try:
        doc = fitz.open(pdf_path)
    except Exception as exc:
        raise ValueError(f"Cannot open PDF '{pdf_path}': {exc}") from exc

    for page_index in range(len(doc)):
        page   = doc[page_index]
        # get_text("text") returns the raw text ordered top-to-bottom.
        raw_text = page.get_text("text").strip()

        # ── Heuristic title extraction ──────────────────────────────────────
        # Treat the first non-empty line as the slide title.
        lines = [ln.strip() for ln in raw_text.splitlines() if ln.strip()]
        title = lines[0] if lines else f"Slide {page_index + 1}"

        # Truncate extremely long titles (some PDFs embed full paragraphs).
        if len(title) > 120:
            title = title[:117] + "…"

        slides.append(Slide(
            page_number=page_index + 1,
            title=title,
            text=raw_text if raw_text else "(No text found on this slide)"
        ))

    doc.close()
    return slides


def format_slides_for_prompt(slides: list[Slide]) -> str:
    """
    Serialise the Slide Text Array into a compact, readable string
    that can be injected directly into a Gemini prompt.

    Format:
        [Slide 1 | Title: Introduction to AI]
        <page text …>

        [Slide 2 | Title: Machine Learning Overview]
        <page text …>
        …
    """
    parts = []
    for slide in slides:
        # Note the change from dictionary access to dot-notation attributes
        header = f"[Slide {slide.page_number} | Title: {slide.title}]"
        parts.append(f"{header}\n{slide.text}")
    return "\n\n".join(parts)


def render_pdf_to_images(pdf_path: str, output_dir: str) -> list[str]:
    """
    Render all pages of a PDF as high-resolution PNG images.
    Returns a list of absolute paths to the generated images.
    """
    import os
    import fitz
    fitz.TOOLS.mupdf_display_errors(False)
    doc = fitz.open(pdf_path)
    image_paths = []
    
    os.makedirs(output_dir, exist_ok=True)
    
    # Zoom ensures crisp text without making file sizes too large
    zoom = float(app_config.get("pdf", "render_zoom", 2.0))
    mat = fitz.Matrix(zoom, zoom)
    
    try:
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            pix = page.get_pixmap(matrix=mat)
            img_path = os.path.join(output_dir, f"slide_{page_idx + 1}.png")
            pix.save(img_path)
            image_paths.append(img_path)
            
            # Explicitly delete objects to force immediate C-level garbage collection
            del pix
            del page
    finally:
        doc.close()
        
    return image_paths


def get_pdf_info(pdf_path: str) -> dict:
    """
    Return basic metadata about the PDF without full text extraction.
    Used for quick UI display.
    """
    try:
        import fitz
        doc  = fitz.open(pdf_path)
        info = {
            "page_count" : len(doc),
            "title"      : doc.metadata.get("title", "Unknown"),
            "author"     : doc.metadata.get("author", "Unknown"),
        }
        doc.close()
        return info
    except Exception as e:
        logger.error(f"Failed to read PDF info for '{pdf_path}': {e}")
        return {"page_count": 0, "title": "Unknown", "author": "Unknown"}


def extract_slide_text_ai(image_paths: list[str], api_key: str, models_to_try: list[str], is_paid: bool = False, progress_cb=None) -> list[Slide]:
    """
    Extract text from slide PNGs using Gemini Vision. 
    Includes multi-model quota hot-swapping and copyright/safety filter bypass.
    """
    schema = {
        "type": "OBJECT",
        "properties": {
            "extracted_slides": {
                "type": "ARRAY",
                "items": {
                    "type": "OBJECT",
                    "properties": {
                        "title": {"type": "STRING"},
                        "text": {"type": "STRING"}
                    },
                    "required": ["title", "text"]
                }
            }
        },
        "required": ["extracted_slides"]
    }
    
    BATCH_SIZE = 5
    all_slides = []
    total_images = len(image_paths)
    
    for i in range(0, total_images, BATCH_SIZE):
        batch_paths = image_paths[i:i + BATCH_SIZE]
        pct = i / total_images
        start_page = i + 1
        end_page   = min(i + BATCH_SIZE, total_images)
        if progress_cb:
            progress_cb(pct, f"👁️ AI reading slides {start_page} to {end_page} (out of {total_images} total)...")
            
        # Load images for Gemini
        images = [Image.open(p) for p in batch_paths]
        prompt = ["You are a highly accurate OCR system. Extract the exact text from these slides. Do not hallucinate or summarize."] + images
        
        chunk_success = False
        
        try:
            response_text = generate_content_with_fallback(
                contents=prompt,
                models_to_try=models_to_try,
                api_key=api_key,
                schema=schema,
                temperature=0.0,
                is_paid=is_paid,
                log_context=f"slides {start_page}-{end_page}",
                progress_cb=progress_cb,
                progress_idx=i / total_images,
                max_retries=3
            )
            data = json.loads(response_text)
            extracted = data.get("extracted_slides", [])
            
            # Map LLM results by index to assign correct, sequential page numbers
            for idx in range(len(batch_paths)):
                page_num = start_page + idx
                if idx < len(extracted):
                    s = extracted[idx]
                    title = s.get("title", f"Slide {page_num}").strip()
                    text = s.get("text", "").strip()
                else:
                    logger.warning(f"Gemini returned fewer slides than sent for pages {start_page}-{end_page}. Using placeholder for page {page_num}.")
                    title = f"Slide {page_num}"
                    text = "(Text extraction incomplete)"
                
                all_slides.append(Slide(
                    page_number=page_num,
                    title=title,
                    text=text if text else "(No text found on this slide)"
                ))
            chunk_success = True
            
        except SafetyFilterError:
            # If AI refuses to read due to copyright/safety, inject placeholders
            for p in range(start_page, end_page + 1):
                all_slides.append(Slide(
                    page_number=p, 
                    title=f"Slide {p}", 
                    text="(Text extraction blocked by AI safety/copyright filter)"
                ))
            chunk_success = True # Treated as a successful bypass
            
        except AllModelsFailedError:
            logger.error(f"All models failed for slides {start_page}-{end_page}. Injecting placeholders.")
            for p in range(start_page, end_page + 1):
                all_slides.append(Slide(
                    page_number=p,
                    title=f"Slide {p}",
                    text="(Text extraction failed due to rate limits)"
                ))
            chunk_success = False
            
        except Exception as e:
            msg = f"⚠️ Parse error on slides {start_page}-{end_page}: {str(e)}. Injecting placeholders."
            logger.error(msg)
            if progress_cb: progress_cb(i / total_images, msg)
            for p in range(start_page, end_page + 1):
                all_slides.append(Slide(
                    page_number=p,
                    title=f"Slide {p}",
                    text="(Text extraction failed due to error)"
                ))
            chunk_success = False
            
    # Ensure correct page numbering and sorting
    all_slides.sort(key=lambda x: x.page_number)
    return all_slides
