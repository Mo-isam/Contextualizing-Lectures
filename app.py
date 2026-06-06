"""
app.py
------
Contextualizing Lectures — Main Streamlit Application

Layout:
  • Sidebar  : API key input + pipeline controls
  • Main area: split-screen PDF viewer (left) | Notes cards (right)
  • Custom HTML audio player injected at the top of the main area

Pipeline stages (each stored in st.session_state):
  1. Files uploaded      → pdf_path, media_path
  2. Audio processed     → transcript_segments
  3. PDF parsed          → slides
  4. AI aligned          → final_output
"""

import os
import base64
import json
import time
import streamlit as st
import streamlit.components.v1 as components
import shutil

# ── Local modules ──────────────────────────────────────────────────────────────
import tempfile
from core.file_utils      import save_file, convert_pptx_to_pdf, SUPPORTED_MEDIA_EXT
from core.audio_processor import process_media_file
from core.pdf_processor   import extract_slide_text, get_pdf_info, render_pdf_to_images, extract_slide_text_ai
from core.ai_aligner      import align_transcript_to_slides, discover_available_models, GEMINI_MODEL_PRIORITY

# ── Local Storage Modules ──────────────────────────────────────────────────────
from core.models import LectureSession
from core.storage import save_session, load_session, list_saved_sessions, FILES_DIR, SESSIONS_DIR
from ui.assets import load_css, inject_jump_script
from ui.components import render_audio_player, render_pdf_viewer_images, render_note_card, step_badge

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Contextualizing Lectures · AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load External CSS
load_css()


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE DEFAULTS
# ═══════════════════════════════════════════════════════════════════════════════
def _init_state():
    defaults = {
        "pdf_path"            : None,
        "media_path"          : None,
        "transcript_segments" : None,
        "slides"              : None,
        "final_output"        : None,
        "pipeline_running"    : False,
        "audio_path"          : None,
        "discovered_models"   : [],
        "last_api_key"        : None,
        "slide_images"        : None,
        "active_slide"        : 1,
        "tx_engine"           : "Local Whisper (CPU) - Private",
        "pdf_engine"          : "Native (PyMuPDF) - Fast",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_or_create_temp_dir() -> str:
    """Return (and cache) a persistent temp directory for the session."""
    if "temp_dir" not in st.session_state:
        st.session_state["temp_dir"] = tempfile.mkdtemp(prefix="ctx_lectures_")
    return st.session_state["temp_dir"]

def cleanup_temp_dir():
    """Remove the entire temp directory on session reset."""
    temp_dir = st.session_state.get("temp_dir")
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except (PermissionError, OSError):
            pass # Windows occasionally holds active locks on media/pdf files
        del st.session_state["temp_dir"]

def render_upload_ui() -> tuple:
    """Render Streamlit file-upload widgets and process inputs."""
    st.markdown("### 📂 Upload Your Files")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📄 Lecture Slides (PDF or PPTX)**")
        pdf_file = st.file_uploader("Upload Slides", type=["pdf", "pptx", "ppt"], key="pdf_uploader", label_visibility="collapsed")

    with col2:
        st.markdown("**🎥 Lecture Video / Audio**")
        media_file = st.file_uploader("Upload Media", type=["mp4", "mp3", "wav"], key="media_uploader", label_visibility="collapsed")

    pdf_path = None
    media_path = None
    temp_dir = get_or_create_temp_dir()

    if pdf_file is not None:
        ext = os.path.splitext(pdf_file.name)[1].lower()
        if ext not in [".pdf", ".pptx", ".ppt"]:
            st.error("❌ Please upload a valid PDF or PowerPoint file.")
        else:
            target_dir = os.path.join(temp_dir, "presentation" if ext in [".pptx", ".ppt"] else "pdf")
            saved_path = save_file(pdf_file.getbuffer(), pdf_file.name, target_dir)
            
            if ext in [".pptx", ".ppt"]:
                pdf_name = os.path.splitext(pdf_file.name)[0] + ".pdf"
                pdf_path = os.path.join(temp_dir, "pdf", pdf_name)
                with st.spinner("⏳ Converting PowerPoint to PDF..."):
                    try:
                        convert_pptx_to_pdf(saved_path, pdf_path)
                        st.success(f"✅ Converted PowerPoint to PDF: `{pdf_name}`")
                    except Exception as e:
                        st.error(f"❌ PowerPoint conversion failed: {e}")
                        pdf_path = None
            else:
                pdf_path = saved_path
                st.success(f"✅ PDF saved: `{pdf_file.name}`")

    if media_file is not None:
        ext = os.path.splitext(media_file.name)[1].lower()
        if ext not in SUPPORTED_MEDIA_EXT:
            st.error("❌ Unsupported media format. Use MP4, MP3, or WAV.")
        else:
            media_path = save_file(media_file.getbuffer(), media_file.name, os.path.join(temp_dir, "media"))
            st.success(f"✅ Media saved: `{media_file.name}`")

    return pdf_path, media_path

# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 1rem 0 0.5rem;">
      <div style="font-size:2.2rem;">🎓</div>
      <div style="font-size:1.1rem; font-weight:700; color:#58a6ff;">Contextualizing Lectures</div>
      <div style="font-size:0.75rem; color:#484f58; margin-top:4px;">AI-Powered Lecture Intelligence</div>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── API Key ──────────────────────────────────────────────────────────────
    st.markdown("**🔑 Gemini API Key**")
    api_key = st.text_input(
        "API Key",
        type="password",
        placeholder="AIza…",
        label_visibility="collapsed",
        help="Get your free key at https://aistudio.google.com/",
    )
    if api_key:
        st.markdown('<span style="color:#3fb950;font-size:0.8rem;">✅ Key entered</span>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<span style="color:#f0883e;font-size:0.8rem;">⚠️ Required for AI alignment</span>',
                    unsafe_allow_html=True)

    st.divider()

    # ── API Tier ──────────────────────────────────────────────────────────────
    st.markdown("**💸 API Quota Tier**")
    is_paid_api = st.checkbox("💎 Paid / Tier-1 API Key (Disable Pacing)", value=False, help="Check this if you have a paid Google AI account to bypass all artificial rate limiting and run at maximum speed.")
    
    st.divider()

    # ── Model selector ────────────────────────────────────────────────────────
    st.markdown("**🤖 Gemini Model**")

    # Dynamic model discovery
    discovered_models = []
    if api_key and api_key.strip():
        # Cache discovered models in session state so we don't query the API on every single rerun
        if not st.session_state.discovered_models or st.session_state.get("last_api_key") != api_key.strip():
            with st.spinner("🔍 Discovering available models..."):
                try:
                    models = discover_available_models(api_key)
                    if models:
                        st.session_state.discovered_models = models
                        st.session_state.last_api_key = api_key.strip()
                except Exception:
                    pass
        discovered_models = st.session_state.discovered_models

    if discovered_models:
        # Build nice options dynamically based on the 2026 model lineup
        MODEL_OPTIONS = {"Auto (try all, best quota)": ""}
        for m in discovered_models:
            label = m
            if "3.5-flash" in m:
                label += " ✦ Latest Generative AI"
            elif "3.1-flash-lite" in m or "2.5-flash-lite" in m:
                label += " ✦ Fast & Lightweight"
            elif "3-flash-preview" in m:
                label += " ✦ Preview Build"
            elif "2.5-flash" in m:
                label += " ✦ Stable Production"
            elif "gemma" in m:
                label += " ✦ Open Weights"
            
            MODEL_OPTIONS[label] = m
    else:
        # Fallback dictionary if API discovery fails
        MODEL_OPTIONS = {
            "Auto (try all, best quota)"                : "",
            "Gemini 3.5 Flash ✦ Latest"                 : "gemini-3.5-flash",
            "Gemini 3.1 Flash Lite ✦ Fast"              : "gemini-3.1-flash-lite",
            "Gemini 3.0 Flash Preview"                  : "gemini-3-flash-preview",
            "Gemini 2.5 Flash ✦ Stable"                 : "gemini-2.5-flash",
            "Gemini 2.5 Flash Lite"                     : "gemini-2.5-flash-lite",
            "Gemma 4 (31B) ✦ Open Weights"              : "gemma-4-31b-it",
            "Gemma 4 (26B A4B) ✦ Optimized"             : "gemma-4-26b-a4b-it",
        }

    model_label = st.selectbox(
        "Model",
        options=list(MODEL_OPTIONS.keys()),
        index=0,
        label_visibility="collapsed",
        help=(
            "If you see 429 quota errors, try switching models or wait for the daily reset (midnight Pacific)."
        ),
    )
    selected_model = MODEL_OPTIONS[model_label]

    # Free-tier quota reference card
    st.markdown("""
    <div style="background:rgba(74,144,226,0.06);border:1px solid rgba(74,144,226,0.15);
                border-radius:8px;padding:10px 12px;font-size:0.75rem;color:#8b949e;
                margin-top:6px;">
      <strong style="color:#58a6ff;">Free-tier limits (2026)</strong><br>
      • <b>Gemini 3.x Flash</b>: 15 req/min · 1.5M tok/day<br>
      • <b>Gemini 3.1 Flash Lite</b>: 30 req/min · 2M tok/day<br>
      • <b>Gemini 2.5 Flash</b>: 15 req/min · 1.5M tok/day<br>
      <span style="color:#484f58;">Quota resets midnight PT daily.</span>
    </div>
    """, unsafe_allow_html=True)

    # ── Pipeline Settings ─────────────────────────────────────────────────────
    st.markdown("**⚙️ Pipeline Settings**")
    st.session_state.pdf_engine = st.selectbox(
        "Slide Extraction",
        options=["Native (PyMuPDF) - Fast", "AI Vision (Gemini) - High Accuracy"],
        index=0,
        help="Use AI Vision if your PDF contains images of text instead of raw text."
    )
    st.session_state.tx_engine = st.selectbox(
        "Audio Transcription",
        options=["Local Whisper (CPU) - Private", "AI Audio (Gemini) - Fast/Cloud"],
        index=0,
        help="AI Audio is significantly faster on standard PCs but uses API quota."
    )

    st.divider()

    # ── Pipeline status ───────────────────────────────────────────────────────
    st.markdown("**📊 Pipeline Status**")

    s1 = "done"    if st.session_state.pdf_path and st.session_state.media_path else "pending"
    s2 = "done"    if st.session_state.transcript_segments                       else ("running" if s1 == "done" and st.session_state.pipeline_running else "pending")
    s3 = "done"    if st.session_state.slides                                    else "pending"
    s4 = "done"    if st.session_state.final_output                              else "pending"

    st.markdown(
        step_badge("Files Uploaded",   s1) + "<br>" +
        step_badge("Audio Transcribed", s2) + "<br>" +
        step_badge("PDF Parsed",        s3) + "<br>" +
        step_badge("AI Aligned",        s4),
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    if st.session_state.final_output:
        from dataclasses import asdict
        export_data = [asdict(n) for n in st.session_state.final_output]
        json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ Export Notes JSON",
            data=json_str,
            file_name="lecture_notes.json",
            mime="application/json",
            width="stretch",
        )
    # ── Persistent Storage panel ──────────────────────────────────────────────
    st.divider()
    st.markdown("**💾 Saved Sessions**")
    
    # 1. Load Session Dropdown
    sessions = list_saved_sessions()
    if sessions:
        session_options = {"-- Select a saved session --": ""}
        for s in sessions:
            dt = time.strftime("%Y-%m-%d %H:%M", time.localtime(s["timestamp"]))
            label = f"{s['name']} ({dt})"
            session_options[label] = s["filename"]
            
        selected_session_label = st.selectbox(
            "Load Past Lecture",
            options=list(session_options.keys()),
            index=0,
            key="load_session_dropdown"
        )
        selected_session_file = session_options[selected_session_label]
        
        if selected_session_file:
            if st.button("Load Selected Session", width="stretch"):
                with st.spinner("⏳ Loading session..."):
                    try:
                        session_data = load_session(selected_session_file)
                        st.session_state.pdf_path = session_data.pdf_path
                        st.session_state.media_path = session_data.media_path
                        st.session_state.audio_path = session_data.audio_path
                        st.session_state.transcript_segments = session_data.transcript_segments
                        st.session_state.slides = session_data.slides
                        st.session_state.final_output = session_data.final_output

                        with st.spinner("🎨 Rendering slide images for display..."):
                            temp_dir = get_or_create_temp_dir()
                            img_dir = os.path.join(temp_dir, "slide_images")
                            st.session_state.slide_images = render_pdf_to_images(session_data.pdf_path, img_dir)
                        st.session_state.active_slide = 1
                        st.success("🎉 Lecture reloaded successfully!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to load session: {e}")
    else:
        st.caption("No saved lectures found.")

    # 2. Save Session Action
    if st.session_state.final_output:
        st.divider()
        st.markdown("**💾 Save Current Session**")
        save_name = st.text_input(
            "Session Name",
            placeholder="e.g. Lecture 1 - Intro",
            key="save_session_name"
        )
        if st.button("💾 Save Session", width="stretch"):
            if not save_name.strip():
                st.warning("Please enter a name for the session.")
            else:
                with st.spinner("⏳ Saving session..."):
                    try:
                        session_data = LectureSession(
                            session_name=save_name.strip(),
                            pdf_path=st.session_state.get("pdf_path"),
                            media_path=st.session_state.get("media_path"),
                            audio_path=st.session_state.get("audio_path"),
                            transcript_segments=st.session_state.get("transcript_segments"),
                            slides=st.session_state.get("slides"),
                            final_output=st.session_state.get("final_output")
                        )
                        save_session(
                            session_data=session_data, 
                            temp_dir=st.session_state.get("temp_dir")
                        )
                        st.success(f"✅ Saved as '{save_name}'!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save session: {e}")

    st.divider()

    # ── Reset ─────────────────────────────────────────────────────────────────
    if st.button("🔄 Reset Session", width="stretch"):
        cleanup_temp_dir()
        st.session_state.clear()
        st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN AREA
# ═══════════════════════════════════════════════════════════════════════════════

# ── Hero header ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero-header">
  <div class="hero-title">🎓 Contextualizing Lectures</div>
  <div class="hero-sub">
    Bridge static PDF slides with dynamic verbal insights from recorded lectures — powered by Whisper &amp; Gemini AI
  </div>
</div>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 1 — FILE UPLOAD
# ═══════════════════════════════════════════════════════════════════════════════
with st.expander("📂 Step 1 · Upload Files", expanded=(st.session_state.pdf_path is None)):
    pdf_path, media_path = render_upload_ui()
    if pdf_path:
        st.session_state.pdf_path = pdf_path
    if media_path:
        st.session_state.media_path = media_path


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 2 — RUN PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════
files_ready = st.session_state.pdf_path and st.session_state.media_path

if files_ready and st.session_state.final_output is None:
    st.divider()
    col_run, col_info = st.columns([1, 3])

    with col_run:
        run_clicked = st.button("🚀 Run Full Pipeline", width="stretch",
                                disabled=not api_key)
    with col_info:
        if not api_key:
            st.warning("Please enter your Gemini API key in the sidebar before running.")

    if run_clicked:
        st.session_state.pipeline_running = True
        temp_dir = get_or_create_temp_dir()

        # Build dynamic model priority list for all AI tasks
        models_to_try = [selected_model] if selected_model else []
        for m in discovered_models:
            if m not in models_to_try: models_to_try.append(m)
        for m in GEMINI_MODEL_PRIORITY:
            if m not in models_to_try: models_to_try.append(m)

        # ── Stage 2a: Transcription ────────────────────────────────────────
        with st.status("🎙️ Processing audio…", expanded=True) as status_box:
            try:
                audio_prog = st.progress(0.0)
                def audio_cb(frac, msg): 
                    audio_prog.progress(min(frac, 1.0))
                    status_box.update(label=msg)
                    
                engine = "ai" if "AI Audio" in st.session_state.tx_engine else "local"
                
                segments = process_media_file(
                    st.session_state.media_path, temp_dir,
                    engine=engine, api_key=api_key, models_to_try=models_to_try, is_paid=is_paid_api, progress_cb=audio_cb
                )
                audio_prog.empty() # clean up bar when done
                st.session_state.transcript_segments = segments
                status_box.update(label=f"✅ {len(segments)} segments transcribed.", state="complete")
            except Exception as e:
                status_box.update(label="❌ Audio processing failed", state="error")
                st.error(f"Audio error: {e}")
                st.stop()

        # ── Stage 2b: PDF Parsing ──────────────────────────────────────────
        with st.status("📄 Parsing PDF slides…", expanded=True) as status_box:
            try:
                # Always render images first (needed for both Native display and AI Vision OCR)
                status_box.update(label="🎨 Rendering slide pages to crisp images...")
                img_dir = os.path.join(temp_dir, "slide_images")
                st.session_state.slide_images = render_pdf_to_images(st.session_state.pdf_path, img_dir)
                st.session_state.active_slide = 1

                if "Native" in st.session_state.pdf_engine:
                    status_box.update(label="📄 Extracting text natively...")
                    slides = extract_slide_text(st.session_state.pdf_path)
                    
                    # ── Check for Image-Only PDFs ──
                    empty_count = sum(1 for s in slides if "(No text found" in s["text"])
                    if empty_count > 0:
                        st.warning(f"⚠️ {empty_count} out of {len(slides)} slides had no readable text (likely an image-based PDF). If alignment fails, switch 'Slide Extraction' to 'AI Vision' in the sidebar and rerun.")
                else:
                    if not api_key: raise ValueError("API Key required for AI Vision.")
                    pdf_prog = st.progress(0.0)
                    def slide_cb(frac, msg): 
                        pdf_prog.progress(min(frac, 1.0))
                        status_box.update(label=msg)
                        
                    slides = extract_slide_text_ai(st.session_state.slide_images, api_key, models_to_try, is_paid=is_paid_api, progress_cb=slide_cb)
                    pdf_prog.empty()

                st.session_state.slides = slides
                status_box.update(label=f"✅ {len(slides)} slides processed.", state="complete")
            except Exception as e:
                status_box.update(label="❌ PDF parsing failed", state="error")
                st.error(f"PDF error: {e}")
                st.stop()

        # ── Stage 2c: Setup audio path for player ───────────────────────────────
        try:
            ext = os.path.splitext(st.session_state.media_path)[1].lower()
            if ext in [".mp3", ".wav"]:
                st.session_state.audio_path = st.session_state.media_path
            else:
                base_name = os.path.splitext(os.path.basename(st.session_state.media_path))[0]
                st.session_state.audio_path = os.path.join(temp_dir, "audio", f"{base_name}_audio.wav")
        except Exception as e:
            st.warning(f"⚠️ Could not set up audio for player: {e}")

        # ── Stage 2d: AI Alignment ─────────────────────────────────────────
        progress_bar = st.progress(0, text="Starting AI alignment…")
        status_text  = st.empty()

        def _progress_cb(frac: float, msg: str):
            progress_bar.progress(min(frac, 1.0), text=msg)
            status_text.markdown(
                f'<span style="color:#8b949e;font-size:0.85rem;">{msg}</span>',
                unsafe_allow_html=True,
            )

        try:
            final_output = align_transcript_to_slides(
                segments    = st.session_state.transcript_segments,
                slides      = st.session_state.slides,
                api_key     = api_key,
                model_name  = selected_model,   # "" → auto-fallback through priority list
                is_paid     = is_paid_api,
                progress_cb = _progress_cb,
            )
            st.session_state.final_output    = final_output
            st.session_state.pipeline_running = False
            progress_bar.progress(1.0, text="✅ Done!")
            st.success(f"🎉 Pipeline complete! {len(final_output)} notes generated.")
            time.sleep(1)
            st.rerun()
        except Exception as e:
            st.error(f"AI alignment error: {e}")
            st.stop()


# ═══════════════════════════════════════════════════════════════════════════════
# STAGE 3 — RESULTS VIEW (split screen)
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.final_output:
    st.divider()

    # ── Custom audio player (full width above the split) ─────────────────────
    st.markdown('<div class="section-label">🎵 Audio Player — click any note card to jump</div>',
                unsafe_allow_html=True)
    render_audio_player()

    st.divider()

    # ── Split screen ──────────────────────────────────────────────────────────
    col_pdf, col_notes = st.columns([1, 1], gap="large")

    # LEFT — PDF viewer
    with col_pdf:
        st.markdown('<div class="col-label">📄 Lecture Slides</div>', unsafe_allow_html=True)
        info = get_pdf_info(st.session_state.pdf_path)
        st.caption(f"📑 {info['page_count']} pages · {os.path.basename(st.session_state.pdf_path)}")
        render_pdf_viewer_images()

    # RIGHT — Notes cards (Strict 1-to-1 sync with active slide)
    with col_notes:
        active_slide = st.session_state.get("active_slide", 1)
        notes = st.session_state.final_output
        
        # --- NEW: Catch and display Slide 0 (General/Off-topic) notes ---
        general_notes = [n for n in notes if n.slide_number == 0]
        if general_notes:
            with st.expander(f"🗣️ General / Off-Slide Discussion ({len(general_notes)})", expanded=False):
                for i, note in enumerate(general_notes):
                    render_note_card(note, f"gen_{i}")
        # ----------------------------------------------------------------

        # Filter notes for the active slide
        filtered = [n for n in notes if n.slide_number == active_slide]
        
        st.markdown(
            f'<div class="col-label" style="margin-top: 10px;">🧠 Slide {active_slide} Notes &nbsp;<span style="color:#484f58;font-weight:400;font-size:0.72rem;text-transform:none;">{len(filtered)} insight(s)</span></div>',
            unsafe_allow_html=True,
        )

        search_q = st.text_input("🔍 Search within this slide's notes", placeholder="Type to filter…",
                                 label_visibility="collapsed")
        
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [n for n in filtered
                        if q in n.slide_title.lower()
                        or q in n.exact_transcript.lower()
                        or q in n.ai_insight.lower()]

        # Render note cards
        st.markdown('<div class="notes-panel">', unsafe_allow_html=True)
        if filtered:
            for i, note in enumerate(filtered):
                render_note_card(note, i)
        else:
            # Elegant placeholder for slides without specific verbal notes
            st.markdown(
                f"""
                <div style="background:rgba(255,255,255,0.01); border:1px dashed rgba(100,160,255,0.15);
                            border-radius:14px; padding:3rem 1.5rem; text-align:center; color:#8b949e;">
                  <div style="font-size:2rem; margin-bottom:0.5rem;">🧠</div>
                  <strong style="color:#58a6ff;">No Specific Verbal Insights</strong><br>
                  <span style="font-size:0.85rem; color:#484f58; display:block; margin-top:6px; line-height:1.5;">
                    The professor did not explain verbal-only slides or hidden insights for Slide {active_slide} in this chunk.
                    Play the lecture audio to listen to the general discussion.
                  </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)
        inject_jump_script()

    # ── Raw JSON preview ──────────────────────────────────────────────────────
    with st.expander("🗂️ View Raw Output JSON"):
        from dataclasses import asdict
        st.json([asdict(n) for n in st.session_state.final_output])

# ── Empty state ───────────────────────────────────────────────────────────────
elif not files_ready:
    st.markdown("""
    <div style="text-align:center; padding: 4rem 2rem; color: #484f58;">
      <div style="font-size:3rem; margin-bottom:1rem;">📂</div>
      <div style="font-size:1.1rem; font-weight:600; color:#8b949e; margin-bottom:0.5rem;">
        Upload your files to get started
      </div>
      <div style="font-size:0.85rem;">
        Expand <strong style="color:#58a6ff;">Step 1 · Upload Files</strong> above,
        then enter your Gemini API key in the sidebar and click <strong style="color:#58a6ff;">Run Full Pipeline</strong>.
      </div>
    </div>
    """, unsafe_allow_html=True)
