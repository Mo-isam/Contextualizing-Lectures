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
import shutil

# ── Local modules ──────────────────────────────────────────────────────────────
from core.file_utils      import save_file, convert_pptx_to_pdf, SUPPORTED_MEDIA_EXT
from core.audio_processor import process_media_file
from core.pdf_processor   import extract_slide_text, get_pdf_info, render_pdf_to_images, extract_slide_text_ai
from core.ai_aligner      import align_transcript_to_slides, align_video_to_slides
from core.video_processor import extract_and_detect_transitions, match_keyframes_to_slides
from core.llm_service     import discover_available_models, GEMINI_MODEL_PRIORITY, DEFAULT_MODEL_OPTIONS
from core.config          import app_config

# ── Local Storage Modules ──────────────────────────────────────────────────────
from core.models import LectureSession
from core.storage import save_session, load_session, list_saved_sessions, FILES_DIR, SESSIONS_DIR
from ui.assets import load_css, inject_jump_script
from ui.components import render_audio_player, render_pdf_viewer_images, render_note_card, step_badge, render_library_card
from ui.dialogs import settings_modal, save_session_modal

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
    pdf_opts = ["Native (PyMuPDF) - Fast", "AI Vision (Gemini) - High Accuracy"]
    tx_opts = ["Local Whisper (CPU) - Private", "AI Audio (Gemini) - Fast/Cloud"]
    
    # Determine defaults from config
    target_model_id = app_config.get("ui_defaults", "default_model", "gemini-3.5-flash")
    default_model_label = list(DEFAULT_MODEL_OPTIONS.keys())[0]
    for label, model_id in DEFAULT_MODEL_OPTIONS.items():
        if model_id == target_model_id:
            default_model_label = label
            break

    defaults = {
        "step"                : "home",
        "api_key"             : "",
        "pdf_path"            : None,
        "media_path"          : None,
        "transcript_segments" : None,
        "slides"              : None,
        "final_output"        : None,
        "pipeline_running"    : False,
        "discovered_models"   : [],
        "last_api_key"        : None,
        "slide_images"        : None,
        "active_slide"        : 1,
        "dynamic_model_options": list(DEFAULT_MODEL_OPTIONS.keys()),
        "selected_model_label": default_model_label,
        "is_paid_api"         : app_config.get("ui_defaults", "is_paid_api", False),
        "tx_engine"           : app_config.get("ui_defaults", "tx_engine", tx_opts[0]),
        "pdf_engine"          : app_config.get("ui_defaults", "pdf_engine", pdf_opts[0]),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_or_create_temp_dir() -> str:
    """Return (and cache) a persistent temp directory inside data_storage/tmp."""
    if "temp_dir" not in st.session_state:
        import uuid
        tmp_path = os.path.join(os.path.dirname(FILES_DIR), "tmp", f"session_{uuid.uuid4().hex[:8]}")
        os.makedirs(tmp_path, exist_ok=True)
        st.session_state["temp_dir"] = tmp_path
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

def change_step(new_step):
    st.session_state.step = new_step

# ═══════════════════════════════════════════════════════════════════════════════
# VIEWS
# ═══════════════════════════════════════════════════════════════════════════════

def view_home():
    st.markdown("<div class='hero-title'>Contextualizing Lectures</div>", unsafe_allow_html=True)
    st.markdown("<div class='hero-subtitle'>Bridge static slides with dynamic verbal insights using AI.</div>", unsafe_allow_html=True)
    
    _, col1, col2, _ = st.columns([0.5, 3, 3, 0.5], gap="large")
    
    with col1:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; margin-top: 0.5rem;'>✨ New Lecture</h3>", unsafe_allow_html=True)
            st.markdown("<div class='card-description'>Upload a PDF and Audio file to analyze a new lecture from scratch.</div>", unsafe_allow_html=True)
            if st.button("Create New Session", use_container_width=True, type="primary"):
                cleanup_temp_dir()
                # Clear previous session data safely
                for k in ["pdf_path", "media_path", "transcript_segments", "slides", "final_output", "slide_images"]:
                    st.session_state[k] = None
                st.session_state.active_slide = 1
                change_step("upload")
                st.rerun()

    with col2:
        with st.container(border=True):
            st.markdown("<h3 style='text-align: center; margin-top: 0.5rem;'>📂 Saved Library</h3>", unsafe_allow_html=True)
            st.markdown("<div class='card-description'>Load a previously analyzed lecture from your local persistent storage.</div>", unsafe_allow_html=True)
            if st.button("Load Past Session", use_container_width=True):
                change_step("load")
                st.rerun()


def view_load_session():
    st.button("Back to Home", on_click=change_step, args=("home",))
    st.markdown("<div class='hero-title' style='font-size: 2.5rem;'>📂 Saved Library</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    sessions = list_saved_sessions()
    if not sessions:
        st.info("No saved sessions found in your library.")
        return

    # Render sessions in a 2-column grid
    cols = st.columns(2, gap="medium")
    for i, s in enumerate(sessions):
        col = cols[i % 2]
        with col:
            if render_library_card(s, str(i)):
                with st.spinner("⏳ Loading session..."):
                    try:
                        session_data = load_session(s["filename"])
                        st.session_state.pdf_path = session_data.pdf_path
                        st.session_state.media_path = session_data.media_path
                        st.session_state.transcript_segments = session_data.transcript_segments
                        st.session_state.slides = session_data.slides
                        st.session_state.final_output = session_data.final_output
                        st.session_state.pipeline_mode = getattr(session_data, "pipeline_type", "audio")

                        with st.spinner("🎨 Rendering slide images for display..."):
                            temp_dir = get_or_create_temp_dir()
                            img_dir = os.path.join(temp_dir, "slide_images")
                            st.session_state.slide_images = render_pdf_to_images(session_data.pdf_path, img_dir)
                            
                        st.session_state.active_slide = 1
                        change_step("studio")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to load session: {e}")


def view_upload():
    upload_ui_placeholder = st.empty()
    run_pipeline_clicked = False
    
    with upload_ui_placeholder.container():
        col_back, col_settings, _ = st.columns([2, 2, 8], vertical_alignment="center")
        with col_back:
            st.button("Back to Home", on_click=change_step, args=("home",), use_container_width=True)
        with col_settings:
            if st.button("⚙️ Settings", use_container_width=True):
                settings_modal()

        st.markdown("<div class='hero-title' style='font-size: 2.5rem;'>📄 Upload Materials</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        
        _, col, _ = st.columns([1, 2, 1])
        with col:
            with st.container(border=True):
                key_input = st.text_input(
                    "1. Enter Gemini API Key", 
                    type="password", 
                    value=st.session_state.api_key,
                    placeholder="AIzaSy... (Kept locally in memory)"
                )
                
                pdf_file = st.file_uploader("2. Upload Lecture Slides (PDF/PPTX)", type=["pdf", "pptx", "ppt"])
                media_file = st.file_uploader("3. Upload Lecture Audio/Video", type=["mp4", "mp3", "wav"])
                
                pipeline_mode = "audio"
                if media_file and media_file.name.lower().endswith(".mp4"):
                    st.info("🎬 Video detected! You can use the new Visual Pipeline to precisely map audio to on-screen slides.")
                    pipeline_mode = st.radio(
                        "Select Pipeline Mode",
                        options=["visual", "audio"],
                        format_func=lambda x: "🎞️ Visual Pipeline (Deterministic & Fast)" if x == "visual" else "🎙️ Audio-Only Pipeline (Semantic AI)",
                        horizontal=True
                    )
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if st.button("Run Pipeline", type="primary", use_container_width=True):
                    if not key_input:
                        st.error("Please provide a Gemini API Key to run the alignment pipeline.")
                    elif not pdf_file or not media_file:
                        st.error("Please upload both slides and media.")
                    else:
                        st.session_state.api_key = key_input
                        
                        # --- Immediate File Saving Logic ---
                        temp_dir = get_or_create_temp_dir()
                        # PDF Handling
                        ext = os.path.splitext(pdf_file.name)[1].lower()
                        target_dir = os.path.join(temp_dir, "presentation") if ext in [".pptx", ".ppt"] else FILES_DIR
                        saved_path = save_file(pdf_file.getbuffer(), pdf_file.name, target_dir)
                        if ext in [".pptx", ".ppt"]:
                            pdf_name = os.path.splitext(pdf_file.name)[0] + ".pdf"
                            st.session_state.pdf_path = save_file(b"", pdf_name, FILES_DIR)
                            convert_pptx_to_pdf(saved_path, st.session_state.pdf_path)
                        else:
                            st.session_state.pdf_path = saved_path
                        
                        # Media Handling
                        st.session_state.media_path = save_file(media_file.getbuffer(), media_file.name, FILES_DIR)
                        st.session_state.pipeline_mode = pipeline_mode
                        
                        run_pipeline_clicked = True

    if run_pipeline_clicked:
        upload_ui_placeholder.empty() # BOOM. The old page is deleted from the DOM instantly.
        
        with st.container():
            st.markdown("<br><br><div class='hero-title' style='font-size: 2.5rem;'>🤖 Analyzing Lecture...</div>", unsafe_allow_html=True)
            st.markdown("<br>", unsafe_allow_html=True)
            
            def flex_header(title, pct=0.0):
                return f"""<div style='display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 8px;'>
                             <span>{title}</span>
                             <span style='color:#58a6ff;'>{int(pct*100)}%</span>
                           </div>"""

            is_visual = st.session_state.get("pipeline_mode") == "visual"

            _, col_proc, _ = st.columns([1, 2, 1])
            with col_proc:
                with st.container(border=True):
                    header1 = st.empty()
                    header1.markdown(flex_header("📄 Extracting Text from Slides..."), unsafe_allow_html=True)
                    p1 = st.progress(0.0)
                    lbl1 = st.empty()
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    if is_visual:
                        header_v = st.empty()
                        header_v.markdown(flex_header("🎞️ Matching Video to Slides..."), unsafe_allow_html=True)
                        p_v = st.progress(0.0)
                        lbl_v = st.empty()
                        st.markdown("<br>", unsafe_allow_html=True)
                        
                    header2 = st.empty()
                    header2.markdown(flex_header("🎙️ Transcribing Audio..."), unsafe_allow_html=True)
                    p2 = st.progress(0.0)
                    lbl2 = st.empty()
                    st.markdown("<br>", unsafe_allow_html=True)
                    
                    header3 = st.empty()
                    if is_visual:
                        header3.markdown(flex_header("🧮 Fusing Math & Generating Insights..."), unsafe_allow_html=True)
                    else:
                        header3.markdown(flex_header("🧠 Aligning Insights using Gemini..."), unsafe_allow_html=True)
                    p3 = st.progress(0.0)
                    lbl3 = st.empty()
                    
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Cancel / Restart", use_container_width=True):
                        change_step("home")
                        st.rerun()

            # ── Execute Real Backend Logic ──
            try:
                temp_dir = get_or_create_temp_dir()
                api_key = st.session_state.api_key
                is_paid_api = st.session_state.get("is_paid_api", False)
                
                # Retrieve actual model ID from the UI label
                from core.llm_service import DEFAULT_MODEL_OPTIONS
                model_label = st.session_state.get("selected_model_label", list(DEFAULT_MODEL_OPTIONS.keys())[0])
                selected_model = DEFAULT_MODEL_OPTIONS.get(model_label, "gemini-3.5-flash")
                
                # Dynamic discovery (done inline here instead of in the sidebar)
                discovered_models = st.session_state.get("discovered_models", [])
                if is_paid_api and not discovered_models:
                    try:
                        discovered_models = discover_available_models(api_key)
                        st.session_state.discovered_models = discovered_models
                    except Exception:
                        pass
                        
                models_to_try = [selected_model] if selected_model else []
                for m in discovered_models:
                    if m not in models_to_try: models_to_try.append(m)
                for m in GEMINI_MODEL_PRIORITY:
                    if m not in models_to_try: models_to_try.append(m)

                # --- STAGE 1: PDF ---
                def pdf_cb(frac, msg): 
                    pct = min(max(frac, 0.0), 1.0)
                    header1.markdown(flex_header("📄 Extracting Text from Slides...", pct), unsafe_allow_html=True)
                    p1.progress(pct)
                    lbl1.caption(msg)
                    
                pdf_cb(0.0, "🎨 Rendering slide pages to crisp images...")
                img_dir = os.path.join(temp_dir, "slide_images")
                st.session_state.slide_images = render_pdf_to_images(st.session_state.pdf_path, img_dir)
                st.session_state.active_slide = 1

                if "Native" in st.session_state.pdf_engine:
                    pdf_cb(0.5, "📄 Extracting text natively...")
                    slides = extract_slide_text(st.session_state.pdf_path)
                    empty_count = sum(1 for s in slides if "(No text found" in s["text"])
                    if empty_count > 0:
                        st.warning(f"⚠️ {empty_count} slides had no readable text. If alignment fails, switch 'Slide Extraction' to 'AI Vision' in Settings.")
                else:
                    def ai_pdf_cb(frac, msg):
                        # Math: Map the AI's 0.0->1.0 to a smooth 10%->100% (0.1 -> 1.0)
                        scaled_frac = 0.1 + (frac * 0.9)
                        pdf_cb(scaled_frac, msg)
                        
                    slides = extract_slide_text_ai(st.session_state.slide_images, api_key, models_to_try, is_paid=is_paid_api, progress_cb=ai_pdf_cb)
                
                st.session_state.slides = slides
                pdf_cb(1.0, f"✅ {len(slides)} slides processed.")

                # --- STAGE 2: VIDEO (NEW) ---
                if is_visual:
                    def video_cb(frac, msg): 
                        pct = min(max(frac, 0.0), 1.0)
                        header_v.markdown(flex_header("🎞️ Matching Video to Slides...", pct), unsafe_allow_html=True)
                        p_v.progress(pct)
                        lbl_v.caption(msg)
                        
                    from core.pdf_processor import format_slides_for_prompt
                    slides_text = format_slides_for_prompt(st.session_state.slides)
                    video_frames_dir = os.path.join(temp_dir, "video_frames")
                    
                    # Phase 1: Extract frames & cuts
                    chapters = extract_and_detect_transitions(st.session_state.media_path, video_frames_dir, progress_cb=video_cb)
                    
                    # Phase 2: Match to slides
                    def match_cb(frac, msg):
                        video_cb(0.5 + (frac * 0.5), msg)
                        
                    st.session_state.visual_chapters = match_keyframes_to_slides(
                        chapters, 
                        st.session_state.slide_images, 
                        slides_text, 
                        api_key=api_key, 
                        progress_cb=match_cb
                    )
                    video_cb(1.0, "✅ Video structural mapping complete.")

                # --- STAGE 3: AUDIO ---
                def audio_cb(frac, msg): 
                    pct = min(max(frac, 0.0), 1.0)
                    header2.markdown(flex_header("🎙️ Transcribing Audio...", pct), unsafe_allow_html=True)
                    p2.progress(pct)
                    lbl2.caption(msg)
                    
                engine = "ai" if "AI Audio" in st.session_state.tx_engine else "local"
                st.session_state.transcript_segments = process_media_file(
                    st.session_state.media_path, temp_dir,
                    engine=engine, api_key=api_key, models_to_try=models_to_try, is_paid=is_paid_api, progress_cb=audio_cb
                )
                audio_cb(1.0, f"✅ {len(st.session_state.transcript_segments)} segments transcribed.")

                # --- STAGE 4: ALIGNMENT ---
                def align_cb(frac, msg): 
                    pct = min(max(frac, 0.0), 1.0)
                    title = "🧮 Fusing Math & Generating Insights..." if is_visual else "🧠 Aligning Insights using Gemini..."
                    header3.markdown(flex_header(title, pct), unsafe_allow_html=True)
                    p3.progress(pct)
                    lbl3.caption(msg)
                
                if is_visual:
                    final_output = align_video_to_slides(
                        segments      = st.session_state.transcript_segments,
                        keyframes     = st.session_state.visual_chapters,
                        slides        = st.session_state.slides,
                        api_key       = api_key,
                        models_to_try = models_to_try,
                        is_paid       = is_paid_api,
                        progress_cb   = align_cb,
                    )
                else:
                    final_output = align_transcript_to_slides(
                        segments      = st.session_state.transcript_segments,
                        slides        = st.session_state.slides,
                        api_key       = api_key,
                        model_name    = selected_model,
                        is_paid       = is_paid_api,
                        progress_cb   = align_cb,
                    )
                    
                st.session_state.final_output = final_output
                align_cb(1.0, f"✅ Pipeline complete! {len(final_output)} notes generated.")
                
                # Smooth transition to Studio
                time.sleep(1.2)
                change_step("studio")
                st.rerun()

            except Exception as e:
                st.error(f"❌ Pipeline Failed: {e}")


def view_studio():
    col_back, col_settings, col_save, col_export = st.columns([2, 2, 2, 2], vertical_alignment="center")
    with col_back:
        st.button("Back to Home", on_click=change_step, args=("home",), use_container_width=True)
    with col_settings:
        if st.button("⚙️ Settings", use_container_width=True):
            settings_modal()
    with col_save:
        if st.button("💾 Save Session", type="primary", use_container_width=True):
            save_session_modal()
    with col_export:
        if st.session_state.final_output:
            from dataclasses import asdict
            export_data = [asdict(n) for n in st.session_state.final_output]
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            st.download_button("Export JSON", json_str, "notes.json", use_container_width=True)
        
    st.divider()

    # Main Studio Layout
    st.markdown('<div class="section-label">🎵 Audio Player — click any note card to jump</div>', unsafe_allow_html=True)
    render_audio_player()
    st.divider()
    
    # 1.5 to 1 ratio gives the PDF ~60% of the screen width
    col_pdf, col_notes = st.columns([1.5, 1], gap="large")
    with col_pdf:
        st.markdown('<div class="col-label">📄 Lecture Slides</div>', unsafe_allow_html=True)
        info = get_pdf_info(st.session_state.pdf_path) if st.session_state.pdf_path else {"page_count": 0}
        st.caption(f"📑 {info.get('page_count', 0)} pages")
        render_pdf_viewer_images()
        
    with col_notes:
        active_slide = st.session_state.get("active_slide", 1)
        notes = st.session_state.get("final_output", [])
        
        # General notes block (Slide 0)
        general_notes = [n for n in notes if n.slide_number == 0]
        if general_notes:
            # Dynamically rename the expander based on the pipeline source
            mode = st.session_state.get("pipeline_mode", "audio")
            expander_title = "🎬 Unmapped Video (Intro / Outro)" if mode == "visual" else "🗣️ General / Off-Slide Discussion"
            
            with st.expander(f"{expander_title} ({len(general_notes)})", expanded=False):
                for i, note in enumerate(general_notes):
                    render_note_card(note, f"gen_{i}")
                    
        filtered = [n for n in notes if n.slide_number == active_slide]
        st.markdown(
            f'<div class="col-label" style="margin-top: 10px;">🧠 Slide {active_slide} Notes &nbsp;<span style="color:#484f58;font-weight:400;font-size:0.72rem;text-transform:none;">{len(filtered)} insight(s)</span></div>',
            unsafe_allow_html=True,
        )

        search_q = st.text_input("🔍 Search within this slide's notes", placeholder="Type to filter…", label_visibility="collapsed")
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [n for n in filtered if q in n.slide_title.lower() or q in n.exact_transcript.lower() or q in n.ai_insight.lower()]

        # Native scrollable container!
        with st.container(height=700, border=False):
            if filtered:
                for i, note in enumerate(filtered):
                    render_note_card(note, i)
            else:
                st.markdown(
                    f"""<div style="background:rgba(255,255,255,0.01); border:1px dashed rgba(100,160,255,0.15); border-radius:14px; padding:3rem 1.5rem; text-align:center; color:#8b949e;">
                      <div style="font-size:2rem; margin-bottom:0.5rem;">🧠</div>
                      <strong style="color:#58a6ff;">No Specific Verbal Insights</strong><br>
                      <span style="font-size:0.85rem; color:#484f58; display:block; margin-top:6px; line-height:1.5;">
                        The professor did not explain verbal-only slides or hidden insights for Slide {active_slide} in this chunk.
                      </span>
                    </div>""", unsafe_allow_html=True)
                    
        inject_jump_script()


# ═══════════════════════════════════════════════════════════════════════════════
# ROUTER
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.step == "home":
    view_home()
elif st.session_state.step == "load":
    view_load_session()
elif st.session_state.step == "upload":
    view_upload()
elif st.session_state.step == "studio":
    view_studio()