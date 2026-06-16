"""
app.py
------
Contextualizing Lectures — Main Streamlit Application

This file acts strictly as a lightweight SPA (Single Page Application) Router.
All heavy libraries and backend processors have been decoupled and moved into 
ui/views.py where they are lazy-loaded ONLY when their specific UI state requires them.
This ensures an instantaneous (< 1s) initial boot time.
"""
import streamlit as st
from core.config import app_config
from ui.assets import load_css

# Import the decoupled views
from ui.views import view_home, view_load_session, view_upload, view_studio

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
    
    target_model_id = app_config.get("ui_defaults", "default_model", "gemini-3.5-flash")
    default_model_options = app_config.get("llm", "model_options", {"Auto (try all, best quota)": ""})
    
    default_model_label = list(default_model_options.keys())[0] if default_model_options else "Auto"
    for label, model_id in default_model_options.items():
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
        "dynamic_model_options": list(default_model_options.keys()),
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
# STATE MACHINE ROUTER
# ═══════════════════════════════════════════════════════════════════════════════
if st.session_state.step == "home":
    view_home()
elif st.session_state.step == "load":
    view_load_session()
elif st.session_state.step == "upload":
    view_upload()
elif st.session_state.step == "studio":
    view_studio()