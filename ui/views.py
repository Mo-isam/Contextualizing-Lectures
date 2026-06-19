### `ui/views.py`
import os
import json
import time
import shutil
import streamlit as st

# ── Lightweight Imports ONLY ──
from core.file_utils import save_file, convert_pptx_to_pdf
from core.storage import load_session, list_saved_sessions, FILES_DIR
from core.config import app_config

from ui.components import render_audio_player, render_pdf_viewer_images, render_all_slides_html, render_note_card, render_all_notes_html, render_library_card
from ui.dialogs import settings_modal, save_session_modal
from ui.assets import inject_jump_script

# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
def get_or_create_temp_dir() -> str:
    if "temp_dir" not in st.session_state:
        import uuid
        tmp_path = os.path.join(os.path.dirname(FILES_DIR), "tmp", f"session_{uuid.uuid4().hex[:8]}")
        os.makedirs(tmp_path, exist_ok=True)
        st.session_state["temp_dir"] = tmp_path
    return st.session_state["temp_dir"]

def cleanup_temp_dir():
    temp_dir = st.session_state.get("temp_dir")
    if temp_dir and os.path.exists(temp_dir):
        try:
            shutil.rmtree(temp_dir, ignore_errors=True)
        except (PermissionError, OSError):
            pass
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
                            # ── Late Import ──
                            from core.pdf_processor import render_pdf_to_images
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
                        
                        # Phase 1 Clean Storage Logic
                        temp_dir = get_or_create_temp_dir()
                        docs_dir = os.path.join(FILES_DIR, "documents")
                        media_dir = os.path.join(FILES_DIR, "media")
                        
                        ext = os.path.splitext(pdf_file.name)[1].lower()
                        if ext in [".pptx", ".ppt"]:
                            temp_pptx_dir = os.path.join(temp_dir, "presentation")
                            saved_pptx_path = save_file(pdf_file.getbuffer(), pdf_file.name, temp_pptx_dir, use_registry=False)
                            temp_pdf_path = os.path.join(temp_pptx_dir, "converted.pdf")
                            convert_pptx_to_pdf(saved_pptx_path, temp_pdf_path)
                            with open(temp_pdf_path, "rb") as f:
                                converted_bytes = f.read()
                            pdf_name = os.path.splitext(pdf_file.name)[0] + ".pdf"
                            st.session_state.pdf_path = save_file(converted_bytes, pdf_name, docs_dir, use_registry=True)
                        else:
                            st.session_state.pdf_path = save_file(pdf_file.getbuffer(), pdf_file.name, docs_dir, use_registry=True)
                        
                        st.session_state.media_path = save_file(media_file.getbuffer(), media_file.name, media_dir, use_registry=True)
                        st.session_state.pipeline_mode = pipeline_mode
                        
                        # Instantly transition the UI state and rerun
                        change_step("processing")
                        st.rerun()

def view_processing():
    """Dedicated view for pipeline execution and pre-warming."""
    st.markdown("<br><br><div class='hero-title' style='font-size: 2.5rem;'>🤖 Analyzing Lecture...</div>", unsafe_allow_html=True)
    st.markdown("<br>", unsafe_allow_html=True)
    
    def flex_header(title, pct=0.0):
        return f"""<div style='display: flex; justify-content: space-between; font-weight: 600; margin-bottom: 8px;'>
                     <span>{title}</span>
                     <span style='color:#58a6ff;'>{int(pct*100)}%</span>
                   </div>"""

    is_visual = st.session_state.get("pipeline_mode") == "visual"
    
    # 1. Paint the layout FIRST
    _, col_proc, _ = st.columns([1, 2, 1])
    
    with col_proc:
        with st.container(border=True):
            
            # Put the preflight placeholder nicely centered at the top of the card
            preflight_placeholder = st.empty()
            
            # Draw the 0% progress bars immediately
            header1 = st.empty(); header1.markdown(flex_header("📄 Extracting Text from Slides..."), unsafe_allow_html=True)
            p1 = st.progress(0.0); lbl1 = st.empty(); st.markdown("<br>", unsafe_allow_html=True)
            
            if is_visual:
                header_v = st.empty(); header_v.markdown(flex_header("🎞️ Matching Video to Slides..."), unsafe_allow_html=True)
                p_v = st.progress(0.0); lbl_v = st.empty(); st.markdown("<br>", unsafe_allow_html=True)
                
            header2 = st.empty(); header2.markdown(flex_header("🎙️ Transcribing Audio..."), unsafe_allow_html=True)
            p2 = st.progress(0.0); lbl2 = st.empty(); st.markdown("<br>", unsafe_allow_html=True)
            
            header3 = st.empty()
            header3.markdown(flex_header("🧮 Fusing Math & Generating Insights..." if is_visual else "🧠 Aligning Insights using Gemini..."), unsafe_allow_html=True)
            p3 = st.progress(0.0); lbl3 = st.empty(); st.markdown("<br>", unsafe_allow_html=True)
            
            if st.button("Cancel / Restart", use_container_width=True):
                change_step("home")
                st.rerun()

    # 2. Define the callback to update the placeholder beautifully
    def preflight_cb(msg):
        preflight_placeholder.markdown(
            f"<div style='text-align: center; color: #8b949e; background: rgba(139,148,158,0.1); padding: 10px; border-radius: 8px; margin-bottom: 1.5rem;'>⚙️ <b>System Pre-flight:</b> {msg}</div>", 
            unsafe_allow_html=True
        )

    # 3. Run the heavy imports
    from core.system_loader import preload_dependencies
    preload_dependencies(
        pipeline_mode=st.session_state.get("pipeline_mode", "audio"),
        pdf_engine=st.session_state.get("pdf_engine", "Native"),
        tx_engine=st.session_state.get("tx_engine", "Local"),
        status_callback=preflight_cb
    )
    
    # 4. Show success, wait a split second, then erase the preflight banner
    preflight_placeholder.markdown(
        "<div style='text-align: center; color: #3fb950; background: rgba(46,160,67,0.1); padding: 10px; border-radius: 8px; margin-bottom: 1.5rem;'>✅ <b>Systems Ready!</b> Starting pipeline...</div>", 
        unsafe_allow_html=True
    )
    time.sleep(0.6)
    preflight_placeholder.empty()

    # ── Execute Real Backend Logic ──
    try:
        from core.llm_service import discover_available_models, GEMINI_MODEL_PRIORITY
        from core.pdf_processor import render_pdf_to_images, extract_slide_text, extract_slide_text_ai, format_slides_for_prompt
        from core.video_processor import extract_and_detect_transitions, match_keyframes_to_slides
        from core.audio_processor import process_media_file
        from core.ai_aligner import align_transcript_to_slides, align_video_to_slides

        temp_dir = get_or_create_temp_dir()
        api_key = st.session_state.api_key
        is_paid_api = st.session_state.get("is_paid_api", False)
        
        default_model_options = app_config.get("llm", "model_options", {})
        model_label = st.session_state.get("selected_model_label", list(default_model_options.keys())[0] if default_model_options else "Auto")
        selected_model = default_model_options.get(model_label, "gemini-3.5-flash")
        
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

        # STAGE 1: PDF
        def pdf_cb(frac, msg): 
            pct = min(max(frac, 0.0), 1.0)
            header1.markdown(flex_header("📄 Extracting Text from Slides...", pct), unsafe_allow_html=True)
            p1.progress(pct); lbl1.caption(msg)
            
        pdf_cb(0.0, "🎨 Rendering slide pages to crisp images...")
        img_dir = os.path.join(temp_dir, "slide_images")
        st.session_state.slide_images = render_pdf_to_images(st.session_state.pdf_path, img_dir)
        st.session_state.active_slide = 1

        if "Native" in st.session_state.pdf_engine:
            pdf_cb(0.5, "📄 Extracting text natively...")
            slides = extract_slide_text(st.session_state.pdf_path)
            empty_count = sum(1 for s in slides if "(No text found" in s["text"])
            if empty_count > 0: st.warning(f"⚠️ {empty_count} slides had no readable text. If alignment fails, switch 'Slide Extraction' to 'AI Vision' in Settings.")
        else:
            def ai_pdf_cb(frac, msg): pdf_cb(0.1 + (frac * 0.9), msg)
            slides = extract_slide_text_ai(st.session_state.slide_images, api_key, models_to_try, is_paid=is_paid_api, progress_cb=ai_pdf_cb)
        
        st.session_state.slides = slides
        pdf_cb(1.0, f"✅ {len(slides)} slides processed.")

        # STAGE 2: VIDEO
        if is_visual:
            def video_cb(frac, msg): 
                pct = min(max(frac, 0.0), 1.0)
                header_v.markdown(flex_header("🎞️ Matching Video to Slides...", pct), unsafe_allow_html=True)
                p_v.progress(pct); lbl_v.caption(msg)
                
            slides_text = format_slides_for_prompt(st.session_state.slides)
            video_frames_dir = os.path.join(temp_dir, "video_frames")
            chapters = extract_and_detect_transitions(st.session_state.media_path, video_frames_dir, progress_cb=video_cb)
            
            def match_cb(frac, msg): video_cb(0.5 + (frac * 0.5), msg)
            st.session_state.visual_chapters = match_keyframes_to_slides(chapters, st.session_state.slide_images, slides_text, api_key=api_key, progress_cb=match_cb)
            video_cb(1.0, "✅ Video structural mapping complete.")

        # STAGE 3: AUDIO
        def audio_cb(frac, msg): 
            pct = min(max(frac, 0.0), 1.0)
            header2.markdown(flex_header("🎙️ Transcribing Audio...", pct), unsafe_allow_html=True)
            p2.progress(pct); lbl2.caption(msg)
            
        engine = "ai" if "AI Audio" in st.session_state.tx_engine else "local"
        st.session_state.transcript_segments = process_media_file(
            st.session_state.media_path, temp_dir, engine=engine, api_key=api_key, models_to_try=models_to_try, is_paid=is_paid_api, progress_cb=audio_cb
        )
        audio_cb(1.0, f"✅ {len(st.session_state.transcript_segments)} segments transcribed.")

        # STAGE 4: ALIGNMENT
        def align_cb(frac, msg): 
            pct = min(max(frac, 0.0), 1.0)
            header3.markdown(flex_header("🧮 Fusing Math & Generating Insights..." if is_visual else "🧠 Aligning Insights using Gemini...", pct), unsafe_allow_html=True)
            p3.progress(pct); lbl3.caption(msg)
        
        if is_visual:
            final_output = align_video_to_slides(st.session_state.transcript_segments, st.session_state.visual_chapters, st.session_state.slides, api_key, models_to_try, is_paid_api, align_cb)
        else:
            final_output = align_transcript_to_slides(st.session_state.transcript_segments, st.session_state.slides, api_key, selected_model, is_paid_api, align_cb)
            
        st.session_state.final_output = final_output
        align_cb(1.0, f"✅ Pipeline complete! {len(final_output)} notes generated.")
        
        # Give user time to read the success message, then transition
        time.sleep(1.0)
        preflight_placeholder.empty()
        change_step("studio")
        st.rerun()
        
    except Exception as e:
        st.error(f"❌ Pipeline Failed: {e}")

def view_studio():
    col_back, col_settings, col_save, col_export = st.columns([2, 2, 2, 2], vertical_alignment="center")
    with col_back: st.button("Back to Home", on_click=change_step, args=("home",), use_container_width=True)
    with col_settings: 
        if st.button("⚙️ Settings", use_container_width=True): settings_modal()
    with col_save:
        if st.button("💾 Save Session", type="primary", use_container_width=True): save_session_modal()
    with col_export:
        if st.session_state.final_output:
            import json
            from dataclasses import asdict
            export_data = [asdict(n) for n in st.session_state.final_output]
            json_str = json.dumps(export_data, indent=2, ensure_ascii=False)
            st.download_button("Export JSON", json_str, "notes.json", use_container_width=True)
        
    st.divider()

    # Hidden bridge input for timeline → Python slide switching
    # JS sets this value when a timeline segment is clicked, triggering a Streamlit rerun
    st.markdown('<style>[data-testid="stTextInput"]:has(input[aria-label="_timeline_slide_bridge"]) { position:absolute; opacity:0; z-index:-100; pointer-events:none; height:0; margin:0; }</style>', unsafe_allow_html=True)
    _tl_bridge = st.text_input("_timeline_slide_bridge", value="", key="_tl_slide_bridge", label_visibility="collapsed")
    if _tl_bridge:
        try:
            parts = _tl_bridge.split(":")
            target_slide = int(parts[0])
            target_time = float(parts[1]) if len(parts) > 1 else -1.0
            
            # Always restore audio position after the rerun, even for same-slide seeks
            if target_time >= 0:
                st.session_state._seek_time = target_time
                st.session_state._auto_play = True

            slide_changed = target_slide != st.session_state.get("active_slide")
            if slide_changed:
                st.session_state.active_slide = target_slide
            
            # Rerun to render the player with the new data-seek/data-autoplay attributes
            st.rerun()
        except Exception:
            pass

    st.markdown('<div class="section-label">🎵 Audio Player — click any note card to jump</div>', unsafe_allow_html=True)
    render_audio_player()
    st.divider()
    
    col_pdf, col_notes = st.columns([1.5, 1], gap="large")
    with col_pdf:
        st.markdown('<div class="col-label">📄 Lecture Slides</div>', unsafe_allow_html=True)
        from core.pdf_processor import get_pdf_info
        info = get_pdf_info(st.session_state.pdf_path) if st.session_state.pdf_path else {"page_count": 0}
        st.caption(f"📑 {info.get('page_count', 0)} pages")
        render_all_slides_html()
        
    with col_notes:
        active_slide = st.session_state.get("active_slide", 1)
        notes = st.session_state.get("final_output", [])
        
        general_notes = [n for n in notes if n.slide_number == 0]
        if general_notes:
            mode = st.session_state.get("pipeline_mode", "audio")
            expander_title = "🎬 Unmapped Video (Intro / Outro)" if mode == "visual" else "🗣️ General / Off-Slide Discussion"
            with st.expander(f"{expander_title} ({len(general_notes)})", expanded=False):
                for i, note in enumerate(general_notes): render_note_card(note, f"gen_{i}")

        search_q = st.text_input("🔍 Search within this slide's notes", placeholder="Type to filter…", label_visibility="collapsed")

        with st.container(height=700, border=False):
            render_all_notes_html(notes, active_slide, search_query=search_q)
                    
        inject_jump_script()