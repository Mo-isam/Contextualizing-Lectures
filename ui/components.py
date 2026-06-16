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
    media_path = st.session_state.get("media_path")
    
    # Smart Playback: The browser handles MP4/MP3 streaming natively via range requests
    if media_path and os.path.exists(media_path):
        st.audio(media_path)
    else:
        st.warning("⚠️ Audio file could not be found. The 'Play at' buttons will not work.")


def render_pdf_viewer_images():
    """
    Renders high-quality PNG slide images with clean controls.
    Includes Previous, Next, and Page-jump dropdown inputs.
    """
    images = st.session_state.get("slide_images", [])
    if not images:
        st.info("No slide images available.")
        return

    num_pages = len(images)
    if "active_slide" not in st.session_state or st.session_state.active_slide is None:
        st.session_state.active_slide = 1
        
    st.session_state.active_slide = max(1, min(st.session_state.active_slide, num_pages))
    active_idx = st.session_state.active_slide - 1

    # 1. Render the image FIRST
    active_img_path = images[active_idx]
    st.image(
        active_img_path,
        width="stretch",
        caption=f"Showing slide {st.session_state.active_slide} of {num_pages}"
    )

    # 2. Render the controls BELOW the image
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


def render_note_card(note: AlignedNote, idx: int):
    """Render a single note card."""
    slide_num = note.slide_number
    title     = note.slide_title
    t_start   = note.timestamp_start
    t_end     = note.timestamp_end
    ts_label  = f"⏱ {seconds_to_hms(t_start)} → {seconds_to_hms(t_end)}"

    exact_transcript = note.exact_transcript
    ai_insight       = note.ai_insight
    is_off_topic     = getattr(note, "is_off_topic", False)

    if is_off_topic:
        # Grey Tangent Theme
        badge_html = f'<span class="note-slide-badge" style="background:rgba(139,148,158,0.15); border-color:rgba(139,148,158,0.3); color:#8b949e;">💬 Tangent</span>'
        body_html = f'<div class="note-body" style="font-style: italic; border-left: 2px solid #8b949e; padding-left: 10px; margin-bottom: 12px; color: #8b949e;">"{exact_transcript}"</div>'
        # Tangents don't have insights by definition
    else:
        # Standard Blue Theme
        badge_html = f'<span class="note-slide-badge">Slide {slide_num}</span>'
        body_html = f'<div class="note-body" style="font-style: italic; border-left: 2px solid #64b0ff; padding-left: 10px; margin-bottom: 12px; color: #c9d1d9;">"{exact_transcript}"</div>'
        if ai_insight:
            body_html += f'<div style="font-size: 0.8rem; color: #a8c4f0; background: rgba(100,176,255,0.08); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; border: 1px solid rgba(100,176,255,0.15);">💡 <b>AI Insight:</b> {ai_insight}</div>'

    card_html = f"""
    <div class="note-card" id="note-card-{idx}">
      {badge_html}
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


def render_library_card(session_info: dict, key_suffix: str) -> bool:
    """Render a card for a saved session in the library. Returns True if clicked."""
    import time
    name = session_info.get("name", "Untitled")
    desc = session_info.get("description", "")
    pipeline_type = session_info.get("pipeline_type", "audio")
    
    if not desc:
        desc = "No description provided."
        
    ts = session_info.get("timestamp", 0)
    dt_str = time.strftime("%b %d, %Y", time.localtime(ts))
    
    # Dynamic iconography based on pipeline context
    icon = "🎞️" if pipeline_type == "visual" else "🎙️"
    
    with st.container(border=True):
        st.markdown(f"<h4 style='margin-top: 0.5rem;'>{icon} {name}</h4>", unsafe_allow_html=True)
        st.caption(f"📅 Edited: {dt_str}")
        st.markdown(f"<div style='min-height: 45px; font-size: 0.95rem; color: #8b949e;'>{desc}</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)
        return st.button("Open Session", key=f"load_btn_{key_suffix}", type="primary", use_container_width=True)