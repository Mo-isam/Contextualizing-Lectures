"""
pdf_processor.py
----------------
Parses a PDF lecture slide deck using PyMuPDF (fitz) and returns a
structured mapping of page numbers to their text content.
"""

import os
import fitz          # PyMuPDF
import streamlit as st


def extract_slide_text(pdf_path: str) -> list[dict]:
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

        slides.append({
            "page_number": page_index + 1,
            "title"      : title,
            "text"       : raw_text if raw_text else "(No text found on this slide)",
        })

    doc.close()
    return slides


def format_slides_for_prompt(slides: list[dict]) -> str:
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
        header = f"[Slide {slide['page_number']} | Title: {slide['title']}]"
        parts.append(f"{header}\n{slide['text']}")
    return "\n\n".join(parts)


def render_pdf_to_images(pdf_path: str, output_dir: str) -> list[str]:
    """
    Render all pages of a PDF as high-resolution PNG images.
    Returns a list of absolute paths to the generated images.
    """
    import os
    doc = fitz.open(pdf_path)
    image_paths = []
    
    os.makedirs(output_dir, exist_ok=True)
    
    # 2.0 zoom ensures crisp text without making file sizes too large
    zoom = 2.0
    mat = fitz.Matrix(zoom, zoom)
    
    for page_idx in range(len(doc)):
        page = doc[page_idx]
        pix = page.get_pixmap(matrix=mat)
        img_path = os.path.join(output_dir, f"slide_{page_idx + 1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
        
    doc.close()
    return image_paths


def get_pdf_info(pdf_path: str) -> dict:
    """
    Return basic metadata about the PDF without full text extraction.
    Used for quick UI display.
    """
    try:
        doc  = fitz.open(pdf_path)
        info = {
            "page_count" : len(doc),
            "title"      : doc.metadata.get("title", "Unknown"),
            "author"     : doc.metadata.get("author", "Unknown"),
        }
        doc.close()
        return info
    except Exception:
        return {"page_count": 0, "title": "Unknown", "author": "Unknown"}
