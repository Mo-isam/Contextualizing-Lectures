"""
components.py
-------------
Reusable Streamlit UI components for rendering notes, PDF viewers, and audio players.
"""
import os
import streamlit as st
from core.models import AlignedNote

def seconds_to_hms(s: float) -> str:
    """Convert raw seconds to H:MM:SS or M:SS string."""
    s   = max(0, int(s))
    h   = s // 3600
    m   = (s % 3600) // 60
    sec = s % 60
    if h:
        return f"{h}:{m:02d}:{sec:02d}"
    return f"{m:02d}:{sec:02d}"


def render_audio_player():
    """Render Streamlit's highly optimized native audio streaming player."""
    audio_path = st.session_state.get("audio_path")
    media_path = st.session_state.get("media_path")
    
    # Fallback: If the extracted .wav was deleted, play the original .mp4 / .mp3
    target_path = audio_path if (audio_path and os.path.exists(audio_path)) else media_path
    
    if target_path and os.path.exists(target_path):
        st.audio(target_path)
    else:
        st.warning("⚠️ Audio file could not be found. The 'Play at' buttons will not work.")


def render_pdf_viewer_images(temp_dir: str):
    """
    Renders high-quality PNG slide images with clean controls.
    Includes Previous, Next, and Page-jump dropdown inputs.
    """
    if not st.session_state.get("slide_images"):
        if st.session_state.get("pdf_path"):
            img_dir = os.path.join(temp_dir, "slide_images")
            from core.pdf_processor import render_pdf_to_images
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
        
    st.session_state.active_slide = max(1, min(st.session_state.active_slide, num_pages))
    active_idx = st.session_state.active_slide - 1

    col_prev, col_num, col_next = st.columns([1, 2, 1])
    
    with col_prev:
        if st.button("◀ Previous Page", width="stretch", key="prev_slide_btn"):
            if st.session_state.active_slide > 1:
                st.session_state.active_slide -= 1
                st.rerun()
                
    with col_num:
        page_options = [f"Slide {i} / {num_pages}" for i in range(1, num_pages + 1)]
        selected_option = st.selectbox(
            "Go to page",
            options=page_options,
            index=active_idx,
            label_visibility="collapsed",
            key=f"slide_select_box_{st.session_state.active_slide}"
        )
        selected_page = int(selected_option.split()[1])
        if selected_page != st.session_state.active_slide:
            st.session_state.active_slide = selected_page
            st.rerun()

    with col_next:
        if st.button("Next Page ▶", width="stretch", key="next_slide_btn"):
            if st.session_state.active_slide < num_pages:
                st.session_state.active_slide += 1
                st.rerun()

    active_img_path = images[active_idx]
    st.image(
        active_img_path,
        use_container_width=True,
        caption=f"Showing slide {st.session_state.active_slide} of {num_pages}"
    )


def render_note_card(note: AlignedNote, idx: int):
    """Render a single note card. Handles both legacy and exact_transcript architectures."""
    slide_num = note.slide_number
    title     = note.slide_title
    t_start   = note.timestamp_start
    t_end     = note.timestamp_end
    ts_label  = f"⏱ {seconds_to_hms(t_start)} → {seconds_to_hms(t_end)}"

    exact_transcript = note.exact_transcript
    legacy_notes     = note.spoken_notes
    ai_insight       = note.ai_insight

    if legacy_notes and not exact_transcript:
        body_html = f'<div class="note-body">{legacy_notes}</div>'
    else:
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
          ▶&nbsp;Play at {seconds_to_hms(t_start)}
        </button>
      </div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def step_badge(label: str, status: str) -> str:
    """Returns an HTML badge for the pipeline status indicator."""
    css = {"done": "step-done", "running": "step-running", "pending": "step-pending"}
    icon = {"done": "✅", "running": "⏳", "pending": "○"}
    c = css.get(status, "step-pending")
    i = icon.get(status, "○")
    return f'<span class="step-badge {c}">{i} {label}</span>'