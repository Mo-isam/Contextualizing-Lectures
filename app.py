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

# ── Local modules ──────────────────────────────────────────────────────────────
from file_manager    import render_upload_ui, get_or_create_temp_dir, cleanup_temp_dir
from audio_processor import process_media_file
from pdf_processor   import extract_slide_text, get_pdf_info
from ai_aligner      import align_transcript_to_slides

# ═══════════════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="Contextualizing Lectures · AI",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ═══════════════════════════════════════════════════════════════════════════════
# GLOBAL CSS — Premium Dark Theme
# ═══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  /* ── Base ─────────────────────────────────────────────────────────────── */
  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
  }

  .stApp {
    background: linear-gradient(160deg, #0d1117 0%, #0f1922 50%, #0d1117 100%);
    color: #c9d1d9;
  }

  /* ── Sidebar ──────────────────────────────────────────────────────────── */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #161b22 0%, #0d1117 100%) !important;
    border-right: 1px solid rgba(255,255,255,0.06);
  }

  [data-testid="stSidebar"] * { color: #c9d1d9 !important; }

  /* ── Hero header ──────────────────────────────────────────────────────── */
  .hero-header {
    text-align: center;
    padding: 2rem 1rem 1.5rem;
    background: linear-gradient(135deg,
      rgba(74,144,226,0.08) 0%,
      rgba(123,94,167,0.08) 50%,
      rgba(100,176,255,0.08) 100%);
    border: 1px solid rgba(100,160,255,0.12);
    border-radius: 20px;
    margin-bottom: 2rem;
  }

  .hero-title {
    font-size: 2.4rem;
    font-weight: 700;
    background: linear-gradient(135deg, #4a90e2, #9b6dff, #64b0ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    line-height: 1.2;
    margin-bottom: 0.5rem;
  }

  .hero-sub {
    color: #8b949e;
    font-size: 1rem;
    font-weight: 400;
  }

  /* ── Section labels ───────────────────────────────────────────────────── */
  .section-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #4a90e2;
    margin-bottom: 0.6rem;
    display: flex;
    align-items: center;
    gap: 6px;
  }

  /* ── Note card ────────────────────────────────────────────────────────── */
  .note-card {
    background: linear-gradient(135deg,
      rgba(22,33,62,0.9) 0%,
      rgba(15,26,60,0.9) 100%);
    border: 1px solid rgba(100,160,255,0.15);
    border-radius: 14px;
    padding: 16px 18px;
    margin-bottom: 14px;
    transition: all 0.22s ease;
    position: relative;
    overflow: hidden;
  }

  .note-card::before {
    content: '';
    position: absolute;
    left: 0; top: 0; bottom: 0;
    width: 3px;
    background: linear-gradient(180deg, #4a90e2, #9b6dff);
    border-radius: 3px 0 0 3px;
  }

  .note-card:hover {
    border-color: rgba(100,160,255,0.35);
    box-shadow: 0 8px 30px rgba(74,144,226,0.15);
    transform: translateY(-2px);
  }

  .note-slide-badge {
    display: inline-block;
    background: rgba(74,144,226,0.18);
    border: 1px solid rgba(74,144,226,0.35);
    color: #4a90e2;
    font-size: 0.72rem;
    font-weight: 700;
    padding: 2px 10px;
    border-radius: 20px;
    margin-bottom: 6px;
    letter-spacing: 0.05em;
  }

  .note-title {
    font-size: 0.95rem;
    font-weight: 600;
    color: #e6edf3;
    margin-bottom: 6px;
  }

  .note-body {
    font-size: 0.875rem;
    color: #8b949e;
    line-height: 1.6;
    margin-bottom: 10px;
  }

  .note-ts {
    font-size: 0.75rem;
    color: #484f58;
    font-variant-numeric: tabular-nums;
  }

  /* ── Jump button ──────────────────────────────────────────────────────── */
  .jump-btn {
    display: inline-flex;
    align-items: center;
    gap: 5px;
    background: linear-gradient(135deg, rgba(74,144,226,0.2), rgba(123,94,167,0.2));
    border: 1px solid rgba(100,160,255,0.3);
    border-radius: 20px;
    color: #64b0ff !important;
    font-size: 0.78rem;
    font-weight: 600;
    padding: 4px 12px;
    cursor: pointer;
    text-decoration: none;
    transition: all 0.18s ease;
  }

  .jump-btn:hover {
    background: linear-gradient(135deg, rgba(74,144,226,0.4), rgba(123,94,167,0.4));
    border-color: rgba(100,160,255,0.6);
    color: #fff !important;
  }

  /* ── Pipeline step badges ─────────────────────────────────────────────── */
  .step-badge {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 600;
    margin-bottom: 6px;
  }

  .step-done    { background: rgba(46,160,67,0.15);  border: 1px solid rgba(46,160,67,0.3);  color: #3fb950; }
  .step-pending { background: rgba(139,148,158,0.1); border: 1px solid rgba(139,148,158,0.2); color: #8b949e; }
  .step-running { background: rgba(74,144,226,0.15); border: 1px solid rgba(74,144,226,0.3); color: #58a6ff; }

  /* ── PDF column label ─────────────────────────────────────────────────── */
  .col-label {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    color: #58a6ff;
    margin-bottom: 8px;
  }

  /* ── Export JSON box ──────────────────────────────────────────────────── */
  .export-box {
    background: rgba(13,17,23,0.8);
    border: 1px solid rgba(100,160,255,0.15);
    border-radius: 10px;
    padding: 12px 16px;
    font-size: 0.78rem;
    color: #8b949e;
    margin-top: 1rem;
  }

  /* ── Streamlit button overrides ───────────────────────────────────────── */
  .stButton > button {
    background: linear-gradient(135deg, #1f6feb, #388bfd) !important;
    border: none !important;
    border-radius: 8px !important;
    color: white !important;
    font-weight: 600 !important;
    transition: all 0.2s ease !important;
  }

  .stButton > button:hover {
    box-shadow: 0 4px 20px rgba(56,139,253,0.4) !important;
    transform: translateY(-1px) !important;
  }

  /* ── Divider ──────────────────────────────────────────────────────────── */
  hr { border-color: rgba(255,255,255,0.06) !important; }

  /* ── Scrollable notes panel ───────────────────────────────────────────── */
  .notes-panel {
    max-height: 68vh;
    overflow-y: auto;
    padding-right: 4px;
  }

  .notes-panel::-webkit-scrollbar       { width: 4px; }
  .notes-panel::-webkit-scrollbar-track { background: transparent; }
  .notes-panel::-webkit-scrollbar-thumb { background: rgba(100,160,255,0.25); border-radius: 2px; }
</style>
""", unsafe_allow_html=True)


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
        "audio_b64"           : None,
        "audio_mime"          : None,
        "discovered_models"   : [],
        "last_api_key"        : None,
        "slide_images"        : None,
        "active_slide"        : 1,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()


# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _seconds_to_hms(s: float) -> str:
    """Convert raw seconds to H:MM:SS or M:SS string."""
    s   = max(0, int(s))
    h   = s // 3600
    m   = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _load_audio_b64(media_path: str) -> tuple[str, str]:
    """
    Read the audio/video file and return (base64_string, mime_type).
    For MP4 we extract the raw bytes and declare audio/mp4.
    """
    ext  = os.path.splitext(media_path)[1].lower()
    mime_map = {".mp3": "audio/mpeg", ".wav": "audio/wav",
                ".mp4": "audio/mp4"}
    mime = mime_map.get(ext, "audio/wav")

    # For video files, try to find the extracted WAV first.
    if ext == ".mp4":
        temp_dir  = get_or_create_temp_dir()
        wav_candidates = [
            f for f in os.listdir(os.path.join(temp_dir, "audio"))
            if f.endswith("_audio.wav")
        ] if os.path.isdir(os.path.join(temp_dir, "audio")) else []

        if wav_candidates:
            media_path = os.path.join(temp_dir, "audio", wav_candidates[0])
            mime       = "audio/wav"

    with open(media_path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    return b64, mime


def _render_audio_player():
    """Inject the custom HTML audio player into the Streamlit page."""
    if st.session_state.audio_b64 is None:
        return

    html_template_path = os.path.join(os.path.dirname(__file__), "custom_audio.html")

    try:
        with open(html_template_path, "r", encoding="utf-8") as f:
            html = f.read()
    except FileNotFoundError:
        st.error("❌ custom_audio.html not found. Make sure it is in the same directory as app.py.")
        return

    html = html.replace("{{AUDIO_B64}}", st.session_state.audio_b64)
    html = html.replace("{{AUDIO_MIME}}", st.session_state.audio_mime)

    components.html(html, height=145, scrolling=False)


def _render_pdf_viewer_images():
    """
    Renders high-quality PNG slide images with clean controls.
    Includes Previous, Next, and Page-jump dropdown inputs.
    """
    # Ensure slide images are rendered if they aren't in session state
    if not st.session_state.get("slide_images"):
        if st.session_state.pdf_path:
            temp_dir = get_or_create_temp_dir()
            img_dir = os.path.join(temp_dir, "slide_images")
            from pdf_processor import render_pdf_to_images
            try:
                with st.spinner("🎨 Rendering slide images for display..."):
                    st.session_state.slide_images = render_pdf_to_images(st.session_state.pdf_path, img_dir)
                    st.session_state.active_slide = 1
            except Exception as e:
                st.error(f"⚠️ Could not render PDF to images: {e}")
                return

    images = st.session_state.get("slide_images", [])
    if not images:
        st.info("No slide images available.")
        return

    num_pages = len(images)
    if "active_slide" not in st.session_state or st.session_state.active_slide is None:
        st.session_state.active_slide = 1
        
    # Ensure bounds
    st.session_state.active_slide = max(1, min(st.session_state.active_slide, num_pages))
    active_idx = st.session_state.active_slide - 1

    # Render navigation bar above image
    col_prev, col_num, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("◀ Previous Page", use_container_width=True, key="prev_slide_btn"):
            if st.session_state.active_slide > 1:
                st.session_state.active_slide -= 1
                st.rerun()
                
    with col_num:
        # Beautiful centered select box for jumping pages
        page_options = [f"Slide {i} / {num_pages}" for i in range(1, num_pages + 1)]
        selected_option = st.selectbox(
            "Go to page",
            options=page_options,
            index=active_idx,
            label_visibility="collapsed",
            key="slide_select_box"
        )
        # Check if changed
        selected_page = int(selected_option.split()[1])
        if selected_page != st.session_state.active_slide:
            st.session_state.active_slide = selected_page
            st.rerun()

    with col_next:
        if st.button("Next Page ▶", use_container_width=True, key="next_slide_btn"):
            if st.session_state.active_slide < num_pages:
                st.session_state.active_slide += 1
                st.rerun()

    # Render the active slide image
    active_img_path = images[active_idx]
    st.image(
        active_img_path,
        use_container_width=True,
        caption=f"Showing slide {st.session_state.active_slide} of {num_pages}"
    )


def _render_note_card(note: dict, idx: int):
    """
    Render a single note card with a JS-powered timestamp-jump button.

    The button uses an onclick that posts a message to any sibling iframes
    containing the audio player, and also tries parent.jumpTo() for the
    case where both components share a window context.
    """
    slide_num = note.get("slide_number", "?")
    title     = note.get("slide_title",  "Untitled")
    body      = note.get("spoken_notes", "")
    t_start   = note.get("timestamp_start", 0)
    t_end     = note.get("timestamp_end",   0)
    ts_label  = f"⏱ {_seconds_to_hms(t_start)} → {_seconds_to_hms(t_end)}"

    # JavaScript snippet: broadcast the jump command to all iframes on the page
    # and also attempt parent-window access (works in some Streamlit setups).
    js_jump = (
        f"(function(){{"
        f"  var t={t_start};"
        f"  var frames=window.parent.document.querySelectorAll('iframe');"
        f"  frames.forEach(function(fr){{"
        f"    try{{ fr.contentWindow.jumpTo(t); }}catch(e){{}}"
        f"  }});"
        f"  try{{ window.parent.jumpTo(t); }}catch(e){{}}"
        f"}})()"
    )

    card_html = f"""
    <div class="note-card" id="note-card-{idx}">
      <span class="note-slide-badge">Slide {slide_num}</span>
      <div class="note-title">{title}</div>
      <div class="note-body">{body}</div>
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
        <span class="note-ts">{ts_label}</span>
        <a href="javascript:void(0);"
           class="jump-btn"
           onclick="{js_jump}">
          ▶&nbsp;Play at {_seconds_to_hms(t_start)}
        </a>
      </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _step_badge(label: str, status: str) -> str:
    css = {"done": "step-done", "running": "step-running", "pending": "step-pending"}
    icon = {"done": "✅", "running": "⏳", "pending": "○"}
    c = css.get(status, "step-pending")
    i = icon.get(status, "○")
    return f'<span class="step-badge {c}">{i} {label}</span>'


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

    # ── Model selector ────────────────────────────────────────────────────────
    st.markdown("**🤖 Gemini Model**")

    # Dynamic model discovery
    discovered_models = []
    if api_key and api_key.strip():
        # Cache discovered models in session state so we don't query the API on every single rerun
        if not st.session_state.discovered_models or st.session_state.get("last_api_key") != api_key.strip():
            with st.spinner("🔍 Discovering available models..."):
                try:
                    from ai_aligner import discover_available_models
                    models = discover_available_models(api_key)
                    if models:
                        st.session_state.discovered_models = models
                        st.session_state.last_api_key = api_key.strip()
                except Exception:
                    pass
        discovered_models = st.session_state.discovered_models

    if discovered_models:
        # Build nice options dynamically
        MODEL_OPTIONS = {"Auto (try all, best quota)": ""}
        for m in discovered_models:
            label = m
            if "1.5-flash" in m:
                label += " ✦ Best free tier"
            elif "2.0-flash-lite" in m:
                label += " ✦ Lightweight"
            elif "1.5-pro" in m:
                label += " ✦ High Reasoning"
            elif "2.0-flash" in m:
                label += " ✦ Next-gen Flash"
            elif "8b" in m:
                label += " ✦ Smallest"
            
            MODEL_OPTIONS[label] = m
    else:
        MODEL_OPTIONS = {
            "Auto (try all, best quota)"   : "",
            "gemini-1.5-flash ✦ Production"            : "gemini-1.5-flash",
            "gemini-1.5-flash-latest ✦ Best free tier" : "gemini-1.5-flash-latest",
            "gemini-2.0-flash-lite ✦ Lightweight"      : "gemini-2.0-flash-lite",
            "gemini-2.0-flash"                          : "gemini-2.0-flash",
            "gemini-1.5-flash-8b ✦ Smallest"           : "gemini-1.5-flash-8b",
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
      <strong style="color:#58a6ff;">Free-tier limits</strong><br>
      • <b>1.5-flash-latest</b>: 15 req/min · 1M tok/day<br>
      • <b>2.0-flash-lite</b>: 30 req/min · 1.5M tok/day<br>
      • <b>2.0-flash</b>: 15 req/min · 1.5M tok/day<br>
      <span style="color:#484f58;">Quota resets midnight PT daily.</span>
    </div>
    """, unsafe_allow_html=True)

    st.divider()

    # ── Pipeline status ───────────────────────────────────────────────────────
    st.markdown("**📊 Pipeline Status**")

    s1 = "done"    if st.session_state.pdf_path and st.session_state.media_path else "pending"
    s2 = "done"    if st.session_state.transcript_segments                       else ("running" if s1 == "done" and st.session_state.pipeline_running else "pending")
    s3 = "done"    if st.session_state.slides                                    else "pending"
    s4 = "done"    if st.session_state.final_output                              else "pending"

    st.markdown(
        _step_badge("Files Uploaded",   s1) + "<br>" +
        _step_badge("Audio Transcribed", s2) + "<br>" +
        _step_badge("PDF Parsed",        s3) + "<br>" +
        _step_badge("AI Aligned",        s4),
        unsafe_allow_html=True,
    )

    st.divider()

    # ── Export ────────────────────────────────────────────────────────────────
    if st.session_state.final_output:
        json_str = json.dumps(st.session_state.final_output, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ Export Notes JSON",
            data=json_str,
            file_name="lecture_notes.json",
            mime="application/json",
            use_container_width=True,
        )

    st.divider()

    # ── Reset ─────────────────────────────────────────────────────────────────
    if st.button("🔄 Reset Session", use_container_width=True):
        cleanup_temp_dir()
        for k in list(st.session_state.keys()):
            del st.session_state[k]
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
        run_clicked = st.button("🚀 Run Full Pipeline", use_container_width=True,
                                disabled=not api_key)
    with col_info:
        if not api_key:
            st.warning("Please enter your Gemini API key in the sidebar before running.")

    if run_clicked:
        st.session_state.pipeline_running = True
        temp_dir = get_or_create_temp_dir()

        # ── Stage 2a: Transcription ────────────────────────────────────────
        with st.status("🎙️ Processing audio…", expanded=True) as status_box:
            try:
                st.write("Loading Whisper model and transcribing…")
                segments = process_media_file(st.session_state.media_path, temp_dir)
                st.session_state.transcript_segments = segments
                st.write(f"✅ {len(segments)} segments transcribed.")
            except Exception as e:
                status_box.update(label="❌ Audio processing failed", state="error")
                st.error(f"Audio error: {e}")
                st.stop()

        # ── Stage 2b: PDF Parsing ──────────────────────────────────────────
        with st.status("📄 Parsing PDF slides…", expanded=True) as status_box:
            try:
                slides = extract_slide_text(st.session_state.pdf_path)
                st.session_state.slides = slides
                st.write(f"✅ {len(slides)} slides extracted.")
                
                # Render slides to PNG images
                st.write("🎨 Rendering slide pages to crisp images...")
                img_dir = os.path.join(temp_dir, "slide_images")
                from pdf_processor import render_pdf_to_images
                st.session_state.slide_images = render_pdf_to_images(st.session_state.pdf_path, img_dir)
                st.session_state.active_slide = 1
                st.write(f"✅ {len(st.session_state.slide_images)} slides rendered as images.")
            except Exception as e:
                status_box.update(label="❌ PDF parsing failed", state="error")
                st.error(f"PDF error: {e}")
                st.stop()

        # ── Stage 2c: Load audio for player ───────────────────────────────
        try:
            b64, mime = _load_audio_b64(st.session_state.media_path)
            st.session_state.audio_b64  = b64
            st.session_state.audio_mime = mime
        except Exception as e:
            st.warning(f"⚠️ Could not pre-load audio for player: {e}")

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
    _render_audio_player()

    st.divider()

    # ── Split screen ──────────────────────────────────────────────────────────
    col_pdf, col_notes = st.columns([1, 1], gap="large")

    # LEFT — PDF viewer
    with col_pdf:
        st.markdown('<div class="col-label">📄 Lecture Slides</div>', unsafe_allow_html=True)
        info = get_pdf_info(st.session_state.pdf_path)
        st.caption(f"📑 {info['page_count']} pages · {os.path.basename(st.session_state.pdf_path)}")
        _render_pdf_viewer_images()

    # RIGHT — Notes cards
    with col_notes:
        notes = st.session_state.final_output
        st.markdown(
            f'<div class="col-label">🧠 AI-Generated Notes &nbsp;<span style="color:#484f58;font-weight:400;font-size:0.72rem;text-transform:none;">{len(notes)} insight(s)</span></div>',
            unsafe_allow_html=True,
        )

        # Filter controls
        filter_col1, filter_col2 = st.columns([2, 1])
        with filter_col1:
            search_q = st.text_input("🔍 Search notes", placeholder="Type to filter…",
                                     label_visibility="collapsed")
        with filter_col2:
            slide_nums = sorted(set(n.get("slide_number", 0) for n in notes))
            slide_filter = st.selectbox(
                "Slide",
                options=["All"] + [f"Slide {s}" for s in slide_nums],
                label_visibility="collapsed",
            )

        # Apply filters
        filtered = notes
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [n for n in filtered
                        if q in n.get("spoken_notes", "").lower()
                        or q in n.get("slide_title", "").lower()]
        if slide_filter != "All":
            target_num = int(slide_filter.split()[1])
            filtered = [n for n in filtered if n.get("slide_number") == target_num]

        # Render note cards
        st.markdown('<div class="notes-panel">', unsafe_allow_html=True)
        if filtered:
            for i, note in enumerate(filtered):
                _render_note_card(note, i)
        else:
            st.markdown(
                '<div style="text-align:center;color:#484f58;padding:3rem 0;">No notes match your filter.</div>',
                unsafe_allow_html=True,
            )
        st.markdown('</div>', unsafe_allow_html=True)

    # ── Raw JSON preview ──────────────────────────────────────────────────────
    with st.expander("🗂️ View Raw Output JSON"):
        st.json(st.session_state.final_output)

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
