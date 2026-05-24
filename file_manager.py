"""
file_manager.py
---------------
Handles file uploads via Streamlit and persists them to a
temporary working directory for the rest of the pipeline.
"""

import os
import tempfile
import shutil
import streamlit as st

# ── Supported mime/extension sets ──────────────────────────────────────────────
SUPPORTED_PDF_TYPES   = ["application/pdf"]
SUPPORTED_MEDIA_TYPES = ["video/mp4", "audio/mpeg", "audio/wav",
                          "audio/x-wav", "audio/mp3"]
SUPPORTED_MEDIA_EXT   = {".mp4", ".mp3", ".wav"}


def get_or_create_temp_dir() -> str:
    """
    Return (and cache in session_state) a single persistent temp directory
    that lives for the duration of the Streamlit session.
    """
    if "temp_dir" not in st.session_state:
        st.session_state["temp_dir"] = tempfile.mkdtemp(prefix="ctx_lectures_")
    return st.session_state["temp_dir"]


def save_upload(uploaded_file, subdir: str = "") -> str:
    """
    Save a Streamlit UploadedFile to disk and return its absolute path.

    Args:
        uploaded_file : The object returned by st.file_uploader().
        subdir        : Optional sub-folder name inside the temp directory.

    Returns:
        Absolute path to the saved file.
    """
    base_dir = get_or_create_temp_dir()
    target_dir = os.path.join(base_dir, subdir) if subdir else base_dir
    os.makedirs(target_dir, exist_ok=True)

    file_path = os.path.join(target_dir, uploaded_file.name)
    with open(file_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return file_path


def cleanup_temp_dir():
    """Remove the entire temp directory (called on session reset)."""
    temp_dir = st.session_state.get("temp_dir")
    if temp_dir and os.path.exists(temp_dir):
        shutil.rmtree(temp_dir, ignore_errors=True)
        del st.session_state["temp_dir"]


def render_upload_ui() -> tuple:
    """
    Render the Streamlit file-upload widgets.

    Returns:
        (pdf_path, media_path) — absolute paths after saving to disk,
        or (None, None) if uploads are incomplete.
    """
    st.markdown("### 📂 Upload Your Files")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📄 Lecture PDF (Slides)**")
        pdf_file = st.file_uploader(
            label="Upload PDF",
            type=["pdf"],
            key="pdf_uploader",
            help="Upload the lecture slide deck in PDF format.",
            label_visibility="collapsed",
        )

    with col2:
        st.markdown("**🎥 Lecture Video / Audio**")
        media_file = st.file_uploader(
            label="Upload Media",
            type=["mp4", "mp3", "wav"],
            key="media_uploader",
            help="Upload the professor's recorded lecture (MP4 / MP3 / WAV).",
            label_visibility="collapsed",
        )

    # ── Validate and persist uploads ───────────────────────────────────────────
    pdf_path   = None
    media_path = None

    if pdf_file is not None:
        ext = os.path.splitext(pdf_file.name)[1].lower()
        if ext != ".pdf":
            st.error("❌ Please upload a valid PDF file.")
        else:
            pdf_path = save_upload(pdf_file, subdir="pdf")
            st.success(f"✅ PDF saved: `{pdf_file.name}`")

    if media_file is not None:
        ext = os.path.splitext(media_file.name)[1].lower()
        if ext not in SUPPORTED_MEDIA_EXT:
            st.error("❌ Unsupported media format. Use MP4, MP3, or WAV.")
        else:
            media_path = save_upload(media_file, subdir="media")
            st.success(f"✅ Media saved: `{media_file.name}`")

    return pdf_path, media_path
