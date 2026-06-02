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
from file_utils      import save_file, convert_pptx_to_pdf, SUPPORTED_MEDIA_EXT
from audio_processor import process_media_file
from pdf_processor   import extract_slide_text, get_pdf_info
from ai_aligner      import align_transcript_to_slides

# ── Persistent Local Storage Helpers ───────────────────────────────────────────
DATA_STORAGE_DIR = os.path.join(os.path.dirname(__file__), "data_storage")
SESSIONS_DIR = os.path.join(DATA_STORAGE_DIR, "sessions")
FILES_DIR = os.path.join(DATA_STORAGE_DIR, "files")

def save_session(session_name: str, state: dict) -> str:
    """Save the current processed lecture session to local storage."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)
    os.makedirs(FILES_DIR, exist_ok=True)

    slug = "".join([c if c.isalnum() or c in ("-", "_") else "_" for c in session_name]).strip()
    session_id = f"{slug}_{int(time.time())}"

    pdf_path = state.get("pdf_path")
    media_path = state.get("media_path")
    
    saved_pdf_path = None
    saved_media_path = None

    if pdf_path and os.path.exists(pdf_path):
        pdf_ext = os.path.splitext(pdf_path)[1]
        saved_pdf_path = os.path.join(FILES_DIR, f"{session_id}{pdf_ext}")
        shutil.copy2(pdf_path, saved_pdf_path)
        # Store only relative filename
        saved_pdf_path = f"files/{session_id}{pdf_ext}"

    if media_path and os.path.exists(media_path):
        media_ext = os.path.splitext(media_path)[1]
        saved_media_path = os.path.join(FILES_DIR, f"{session_id}{media_ext}")
        shutil.copy2(media_path, saved_media_path)
        # Store only relative filename
        saved_media_path = f"files/{session_id}{media_ext}"

        # --- NEW: Save the lightweight extracted .wav if it's a video ---
        if media_ext.lower() == ".mp4" and "temp_dir" in st.session_state:
            base_name = os.path.splitext(os.path.basename(media_path))[0]
            temp_audio_path = os.path.join(st.session_state["temp_dir"], "audio", f"{base_name}_audio.wav")
            if os.path.exists(temp_audio_path):
                saved_audio_path = os.path.join(FILES_DIR, f"{session_id}_audio.wav")
                shutil.copy2(temp_audio_path, saved_audio_path)
                saved_audio_path = f"files/{session_id}_audio.wav"
        elif media_ext.lower() in [".mp3", ".wav"]:
            saved_audio_path = saved_media_path

    metadata = {
        "session_name"        : session_name,
        "session_id"          : session_id,
        "pdf_path"            : saved_pdf_path,
        "media_path"          : saved_media_path,
        "audio_path"          : locals().get('saved_audio_path', None),
        "transcript_segments" : state.get("transcript_segments"),
        "slides"              : state.get("slides"),
        "final_output"        : state.get("final_output"),
        "timestamp"           : time.time(),
    }

    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(session_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    return session_file


def list_saved_sessions() -> list[dict]:
    """List all saved sessions from the local storage folder."""
    if not os.path.exists(SESSIONS_DIR):
        return []
    
    sessions = []
    for f in os.listdir(SESSIONS_DIR):
        if f.endswith(".json"):
            try:
                with open(os.path.join(SESSIONS_DIR, f), "r", encoding="utf-8") as file:
                    data = json.load(file)
                    sessions.append({
                        "name": data.get("session_name", f),
                        "id": data.get("session_id"),
                        "filename": f,
                        "timestamp": data.get("timestamp", 0)
                    })
            except Exception:
                pass
    sessions.sort(key=lambda x: x["timestamp"], reverse=True)
    return sessions


def load_session(filename: str) -> dict:
    """Load session data and dynamically resolve relative paths to absolute runtime paths."""
    path = os.path.join(SESSIONS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
        
    for key in ["pdf_path", "media_path", "audio_path"]:
        val = data.get(key)
        if val and val.startswith("files/"):
            file_name = os.path.basename(val)
            data[key] = os.path.join(FILES_DIR, file_name)
            
    return data

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
    font-family: inherit;
    outline: none;
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
        shutil.rmtree(temp_dir, ignore_errors=True)
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


def _seconds_to_hms(s: float) -> str:
    """Convert raw seconds to H:MM:SS or M:SS string."""
    s   = max(0, int(s))
    h   = s // 3600
    m   = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def _render_audio_player():
    """Render Streamlit's highly optimized native audio streaming player."""
    if st.session_state.get("audio_path") and os.path.exists(st.session_state.audio_path):
        st.audio(st.session_state.audio_path)


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
        if st.button("◀ Previous Page", width="stretch", key="prev_slide_btn"):
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
            key=f"slide_select_box_{st.session_state.active_slide}"
        )
        # Check if changed
        selected_page = int(selected_option.split()[1])
        if selected_page != st.session_state.active_slide:
            st.session_state.active_slide = selected_page
            st.rerun()

    with col_next:
        if st.button("Next Page ▶", width="stretch", key="next_slide_btn"):
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


def _inject_jump_script():
    """
    Injects a highly efficient event-delegation script into the parent document.
    It survives Streamlit UI refreshes and satisfies browser autoplay security 
    because it fires directly from the user's click gesture.
    """
    js_code = """
    <script>
    (function() {
        try {
            // Get the main Streamlit document safely
            var parentDoc = window.parent.document || document;
            
            // Safety Check: Only attach this master listener ONCE per session.
            if (parentDoc.__jumpScriptAdded) return;
            parentDoc.__jumpScriptAdded = true;

            // Master Click Listener attached to the entire page
            parentDoc.body.addEventListener('click', function(e) {
                // Check if what the user clicked (or its parent) is a jump button
                var btn = e.target.closest('.jump-btn');
                if (!btn) return; // If it's not a jump button, ignore the click

                e.preventDefault();
                e.stopPropagation();

                var time = parseFloat(btn.getAttribute('data-time'));
                var audioEl = parentDoc.querySelector('audio'); // Find Streamlit's native audio

                if (audioEl && !isNaN(time)) {
                    audioEl.currentTime = time;
                    
                    // Call play directly inside the click event to bypass security blocks
                    var playPromise = audioEl.play();
                    if (playPromise !== undefined) {
                        playPromise.catch(function(error) {
                            console.warn("Autoplay warning (usually ignorable):", error);
                        });
                    }
                }
            });
        } catch(e) {
            console.error("Failed to initialize jump script:", e);
        }
    })();
    </script>
    """
    import streamlit.components.v1 as components
    components.html(js_code, height=0, width=0)

def _render_note_card(note: dict, idx: int):
    """
    Render a single note card. Gracefully handles both legacy JSON ('spoken_notes') 
    and the new transcript-driven architecture ('exact_transcript' + 'ai_insight').
    """
    slide_num = note.get("slide_number", "?")
    title     = note.get("slide_title",  "Untitled")
    t_start   = note.get("timestamp_start", 0)
    t_end     = note.get("timestamp_end",   0)
    ts_label  = f"⏱ {_seconds_to_hms(t_start)} → {_seconds_to_hms(t_end)}"

    # Data Extractors
    exact_transcript = note.get("exact_transcript", "")
    legacy_notes     = note.get("spoken_notes", "")
    ai_insight       = note.get("ai_insight", "")

    # HTML Body Assembly
    if legacy_notes and not exact_transcript:
        # Backward compatibility for old JSON saves
        body_html = f'<div class="note-body">{legacy_notes}</div>'
    else:
        # New Architecture layout
        body_html = f'<div class="note-body" style="font-style: italic; border-left: 2px solid #64b0ff; padding-left: 10px; margin-bottom: 12px; color: #c9d1d9;">"{exact_transcript}"</div>'
        if ai_insight:
            body_html += f'<div style="font-size: 0.8rem; color: #a8c4f0; background: rgba(100,176,255,0.08); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; border: 1px solid rgba(100,176,255,0.15);">💡 <b>AI Insight:</b> {ai_insight}</div>'

    card_html = f"""
    <div class="note-card" id="note-card-{idx}">
      <span class="note-slide-badge">Slide {slide_num}</span>
      <div class="note-title">{title}</div>
      {body_html}
      <div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">
        <span class="note-ts">{ts_label}</span>
        <button class="jump-btn" data-time="{t_start}">
          ▶&nbsp;Play at {_seconds_to_hms(t_start)}
        </button>
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
                        data = load_session(selected_session_file)
                        st.session_state.pdf_path = data.get("pdf_path")
                        st.session_state.media_path = data.get("media_path")
                        st.session_state.transcript_segments = data.get("transcript_segments")
                        st.session_state.slides = data.get("slides")
                        st.session_state.final_output = data.get("final_output")
                        
                        st.session_state.media_path = data.get("media_path")
                        st.session_state.audio_path = data.get("audio_path")

                        # --- UPGRADE LEGACY SESSIONS PERMANENTLY ---
                        if not st.session_state.audio_path or not os.path.exists(st.session_state.audio_path):
                            if st.session_state.media_path and st.session_state.media_path.endswith(".mp4"):
                                with st.spinner("⏳ Upgrading Legacy Session: Extracting audio permanently..."):
                                    from audio_processor import extract_audio_from_video
                                    
                                    base_name = os.path.splitext(os.path.basename(st.session_state.media_path))[0]
                                    perm_audio_path = os.path.join(FILES_DIR, f"{base_name}_audio.wav")
                                    
                                    if not os.path.exists(perm_audio_path):
                                        extract_audio_from_video(st.session_state.media_path, FILES_DIR)
                                    
                                    st.session_state.audio_path = perm_audio_path
                                    
                                    # Update the JSON so it never has to do this again
                                    data["audio_path"] = f"files/{os.path.basename(perm_audio_path)}"
                                    full_json_path = os.path.join(SESSIONS_DIR, selected_session_file)
                                    with open(full_json_path, "w", encoding="utf-8") as f:
                                        json.dump(data, f, ensure_ascii=False, indent=2)
                            else:
                                st.session_state.audio_path = st.session_state.media_path

                        st.session_state.slide_images = None  # regenerate on-the-fly
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
                        save_session(save_name.strip(), st.session_state)
                        st.success(f"✅ Saved as '{save_name}'!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as e:
                        st.error(f"Failed to save session: {e}")

    st.divider()

    # ── Reset ─────────────────────────────────────────────────────────────────
    if st.button("🔄 Reset Session", width="stretch"):
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
        run_clicked = st.button("🚀 Run Full Pipeline", width="stretch",
                                disabled=not api_key)
    with col_info:
        if not api_key:
            st.warning("Please enter your Gemini API key in the sidebar before running.")

    if run_clicked:
        st.session_state.pipeline_running = True
        temp_dir = get_or_create_temp_dir()

        # Build dynamic model priority list for all AI tasks
        from ai_aligner import GEMINI_MODEL_PRIORITY
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
                    engine=engine, api_key=api_key, models_to_try=models_to_try, progress_cb=audio_cb
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
                from pdf_processor import render_pdf_to_images, extract_slide_text_ai
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
                        
                    slides = extract_slide_text_ai(st.session_state.slide_images, api_key, models_to_try, slide_cb)
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

    # RIGHT — Notes cards (Strict 1-to-1 sync with active slide)
    with col_notes:
        active_slide = st.session_state.get("active_slide", 1)
        notes = st.session_state.final_output
        
        # --- NEW: Catch and display Slide 0 (General/Off-topic) notes ---
        general_notes = [n for n in notes if n.get("slide_number") == 0]
        if general_notes:
            with st.expander(f"🗣️ General / Off-Slide Discussion ({len(general_notes)})", expanded=False):
                for i, note in enumerate(general_notes):
                    _render_note_card(note, f"gen_{i}")
        # ----------------------------------------------------------------

        # Filter notes for the active slide
        filtered = [n for n in notes if n.get("slide_number") == active_slide]
        
        st.markdown(
            f'<div class="col-label" style="margin-top: 10px;">🧠 Slide {active_slide} Notes &nbsp;<span style="color:#484f58;font-weight:400;font-size:0.72rem;text-transform:none;">{len(filtered)} insight(s)</span></div>',
            unsafe_allow_html=True,
        )

        search_q = st.text_input("🔍 Search within this slide's notes", placeholder="Type to filter…",
                                 label_visibility="collapsed")
        
        if search_q.strip():
            q = search_q.strip().lower()
            filtered = [n for n in filtered
                        if q in n.get("spoken_notes", "").lower()
                        or q in n.get("slide_title", "").lower()]

        # Render note cards
        st.markdown('<div class="notes-panel">', unsafe_allow_html=True)
        if filtered:
            for i, note in enumerate(filtered):
                _render_note_card(note, i)
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
        _inject_jump_script()

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
