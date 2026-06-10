### `ui/dialogs.py` (New File)
import time
import streamlit as st
from core.models import LectureSession
from core.storage import save_session

@st.dialog("⚙️ Settings")
def settings_modal():
    st.markdown("Configure your AI models, slide processing, and transcription engines.")
    
    # 1. API Tier Checkbox
    new_is_paid = st.checkbox("💎 Paid / Tier-1 API Key (Disable Pacing)", value=st.session_state.get("is_paid_api", False))
    
    # 2. Model Selection (Reads from dynamic options if they exist)
    from core.llm_service import DEFAULT_MODEL_OPTIONS
    opts = st.session_state.get("dynamic_model_options", list(DEFAULT_MODEL_OPTIONS.keys()))
    current_m = st.session_state.get("selected_model_label", opts[0])
    m_idx = opts.index(current_m) if current_m in opts else 0
    new_model = st.selectbox("Model", opts, index=m_idx)
    
    # 3. PDF Engine
    pdf_opts = ["Native (PyMuPDF) - Fast", "AI Vision (Gemini) - High Accuracy"]
    pdf_idx = pdf_opts.index(st.session_state.get("pdf_engine", pdf_opts[0])) if st.session_state.get("pdf_engine") in pdf_opts else 0
    new_pdf_engine = st.selectbox("PDF Engine", pdf_opts, index=pdf_idx)
    
    # 4. Audio Transcription
    tx_opts = ["Local Whisper (CPU) - Private", "AI Audio (Gemini) - Fast/Cloud"]
    tx_idx = tx_opts.index(st.session_state.get("tx_engine", tx_opts[0])) if st.session_state.get("tx_engine") in tx_opts else 0
    new_tx_engine = st.selectbox("Audio Transcription", tx_opts, index=tx_idx)
    
    if st.button("Save & Close", use_container_width=True, type="primary"):
        st.session_state.is_paid_api = new_is_paid
        st.session_state.selected_model_label = new_model
        st.session_state.pdf_engine = new_pdf_engine
        st.session_state.tx_engine = new_tx_engine
        st.rerun()

@st.dialog("💾 Save Session")
def save_session_modal():
    st.markdown("Add a description and title to save this session to your local library.")
    
    # Generate a default title from the PDF filename if available
    default_title = "Untitled Session"
    if st.session_state.get("pdf_path"):
        import os
        default_title = os.path.splitext(os.path.basename(st.session_state.pdf_path))[0]
        
    title = st.text_input("Lecture Title", value=default_title)
    description = st.text_area("Session Description", placeholder="Enter a brief summary of the key concepts discussed...")
    
    col_c1, col_c2 = st.columns(2)
    with col_c1:
        if st.button("Cancel", use_container_width=True):
            st.rerun()
    with col_c2:
        if st.button("Save", type="primary", use_container_width=True):
            if not title.strip():
                st.warning("Please enter a title.")
            else:
                session_data = LectureSession(
                    session_name=title.strip(),
                    session_description=description.strip(),
                    pdf_path=st.session_state.get("pdf_path"),
                    media_path=st.session_state.get("media_path"),
                    transcript_segments=st.session_state.get("transcript_segments"),
                    slides=st.session_state.get("slides"),
                    final_output=st.session_state.get("final_output")
                )
                save_session(
                    session_data=session_data, 
                    temp_dir=st.session_state.get("temp_dir")
                )
                st.success("Session saved successfully!")
                time.sleep(0.8)
                st.rerun()