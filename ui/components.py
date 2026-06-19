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


def _get_audio_duration(media_path: str) -> float:
    """Get total audio duration in seconds. Tries mutagen, then ffprobe, then notes fallback."""
    # Try mutagen (optional dependency)
    try:
        import mutagen
        audio_info = mutagen.File(media_path)
        if audio_info and audio_info.info:
            return audio_info.info.length
    except Exception:
        pass
    # Try ffprobe via subprocess (available if ffmpeg is installed)
    try:
        import subprocess
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", media_path],
            capture_output=True, text=True, timeout=10
        )
        dur = float(result.stdout.strip())
        if dur > 0:
            return dur
    except Exception:
        pass
    # Fallback: estimate from final_output max timestamp + small buffer
    notes = st.session_state.get("final_output", [])
    if notes:
        return max(n.timestamp_end for n in notes) * 1.02
    return 0.0


def _compute_slide_boundaries(notes, total_duration: float) -> list[dict]:
    """
    Compute contiguous slide segments from AlignedNote list.
    Returns a list of dicts: {slide_number, start, end, label}
    """
    if not notes or total_duration <= 0:
        return []

    # Group notes by slide_number, find min start and max end per slide
    slide_ranges = {}
    for n in notes:
        s = n.slide_number
        if s == 0:  # skip general/off-slide notes
            continue
        if s not in slide_ranges:
            slide_ranges[s] = {"start": n.timestamp_start, "end": n.timestamp_end}
        else:
            slide_ranges[s]["start"] = min(slide_ranges[s]["start"], n.timestamp_start)
            slide_ranges[s]["end"] = max(slide_ranges[s]["end"], n.timestamp_end)

    if not slide_ranges:
        return []

    # Sort by start time and build ordered segment list
    segments = []
    for slide_num in sorted(slide_ranges, key=lambda s: slide_ranges[s]["start"]):
        r = slide_ranges[slide_num]
        segments.append({
            "slide_number": slide_num,
            "start": r["start"],
            "end": r["end"],
        })

    return segments


def render_audio_player():
    """Render a custom audio player with slide-boundary tick marks built into the seek bar."""
    media_path = st.session_state.get("media_path")
    
    if not media_path or not os.path.exists(media_path):
        st.warning("⚠️ Audio file could not be found. The 'Play at' buttons will not work.")
        return

    # Fetch restore state for audio player, pop them so they only apply once after a rerun
    seek_time = st.session_state.pop("_seek_time", -1.0)
    auto_play = "true" if st.session_state.pop("_auto_play", False) else "false"

    st.audio(media_path)

    # Build tick marks from final_output
    notes = st.session_state.get("final_output", [])
    total_dur = _get_audio_duration(media_path) if notes else 0
    segments = _compute_slide_boundaries(notes, total_dur) if notes and total_dur > 0 else []

    ticks_html = ""
    for seg in segments:
        left_pct = (seg["start"] / total_dur) * 100
        width_pct = ((seg["end"] - seg["start"]) / total_dur) * 100
        label_left = left_pct + (width_pct / 2)
        sn = seg["slide_number"]
        ticks_html += f'<div class="cp-tick" style="left:{left_pct:.2f}%" data-time="{seg["start"]}" data-slide="{sn}"></div>'
        ticks_html += f'<div class="cp-label" style="left:{label_left:.2f}%">S{sn}</div>'

    dur_display = seconds_to_hms(total_dur) if total_dur > 0 else "0:00"

    player_html = f"""
    <div class="custom-player" data-duration="{total_dur:.1f}" data-seek="{seek_time}" data-autoplay="{auto_play}">
      <button class="cp-play" title="Play / Pause">▶</button>
      <span class="cp-time"><span class="cp-current">0:00</span> / <span class="cp-duration">{dur_display}</span></span>
      <div class="cp-track">
        <div class="cp-fill"></div>
        <div class="cp-handle"></div>
        {ticks_html}
      </div>
      <button class="cp-vol" title="Mute / Unmute">🔊</button>
    </div>
    """
    st.markdown(player_html, unsafe_allow_html=True)


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