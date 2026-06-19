"""
components.py
-------------
Reusable Streamlit UI components for rendering notes, PDF viewers, and audio players.
"""
import os
import base64
import html as html_module
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
      <button class="cp-sync" title="Browsing — click to sync slides with audio">🔓</button>
      <button class="cp-vol" title="Mute / Unmute">🔊</button>
    </div>
    <div class="resync-pill" style="display:none;"></div>
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


def render_all_slides_html():
    """
    Pre-render ALL slide images as hidden HTML panels with JS-driven navigation.
    Only the active slide is visible; JS toggles visibility without Streamlit reruns.
    """
    images = st.session_state.get("slide_images", [])
    if not images:
        st.info("No slide images available.")
        return

    num_pages = len(images)
    if "active_slide" not in st.session_state or st.session_state.active_slide is None:
        st.session_state.active_slide = 1
    st.session_state.active_slide = max(1, min(st.session_state.active_slide, num_pages))
    active = st.session_state.active_slide

    # Build all slide panels with base64-embedded images
    panels = []
    for i, img_path in enumerate(images):
        sn = i + 1
        cls = "slide-panel active" if sn == active else "slide-panel"
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
        ext = os.path.splitext(img_path)[1].lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"
        panels.append(
            f'<div class="{cls}" data-slide="{sn}">'
            f'<img src="data:{mime};base64,{b64}" alt="Slide {sn}" style="width:100%;border-radius:8px;">'
            f'<div class="slide-caption">Showing slide {sn} of {num_pages}</div>'
            f'</div>'
        )

    # Build dropdown options
    opts = []
    for i in range(1, num_pages + 1):
        sel = ' selected' if i == active else ''
        opts.append(f'<option value="{i}"{sel}>Slide {i} / {num_pages}</option>')

    html = (
        f'<div class="slide-viewer" data-active="{active}" data-total="{num_pages}">'
        + ''.join(panels)
        + '<div class="slide-nav">'
        + '<button class="slide-prev" title="Previous Page">◀ Previous Page</button>'
        + f'<select class="slide-select">{"" .join(opts)}</select>'
        + '<button class="slide-next" title="Next Page">Next Page ▶</button>'
        + '</div>'
        + '</div>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _note_card_html(note: AlignedNote, idx) -> str:
    """Return the HTML string for a single note card (no st.markdown call)."""
    slide_num = note.slide_number
    title     = html_module.escape(note.slide_title)
    t_start   = note.timestamp_start
    t_end     = note.timestamp_end
    ts_label  = f"⏱ {seconds_to_hms(t_start)} → {seconds_to_hms(t_end)}"

    exact_transcript = html_module.escape(note.exact_transcript)
    ai_insight       = html_module.escape(note.ai_insight)
    is_off_topic     = getattr(note, "is_off_topic", False)

    if is_off_topic:
        badge_html = f'<span class="note-slide-badge" style="background:rgba(139,148,158,0.15); border-color:rgba(139,148,158,0.3); color:#8b949e;">💬 Tangent</span>'
        body_html = f'<div class="note-body" style="font-style: italic; border-left: 2px solid #8b949e; padding-left: 10px; margin-bottom: 12px; color: #8b949e;">"{exact_transcript}"</div>'
    else:
        badge_html = f'<span class="note-slide-badge">Slide {slide_num}</span>'
        body_html = f'<div class="note-body" style="font-style: italic; border-left: 2px solid #64b0ff; padding-left: 10px; margin-bottom: 12px; color: #c9d1d9;">"{exact_transcript}"</div>'
        if ai_insight:
            body_html += f'<div style="font-size: 0.8rem; color: #a8c4f0; background: rgba(100,176,255,0.08); padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; border: 1px solid rgba(100,176,255,0.15);">💡 <b>AI Insight:</b> {ai_insight}</div>'

    return (
        f'<div class="note-card" id="note-card-{idx}">'
        f'{badge_html}'
        f'<div class="note-title">{title}</div>'
        f'{body_html}'
        f'<div style="display:flex; align-items:center; justify-content:space-between; flex-wrap:wrap; gap:6px;">'
        f'<span class="note-ts">{ts_label}</span>'
        f'<button class="jump-btn" data-time="{t_start}">▶&nbsp;Play at {seconds_to_hms(t_start)}</button>'
        f'</div></div>'
    )


def render_note_card(note: AlignedNote, idx: int):
    """Render a single note card."""
    st.markdown(_note_card_html(note, idx), unsafe_allow_html=True)


def render_all_notes_html(notes: list, active_slide: int, search_query: str = ""):
    """
    Pre-render ALL note cards grouped by slide number as hidden HTML panels.
    JS toggles visibility in sync with the slide viewer.
    """
    if not notes:
        return

    # Determine full range of slide numbers (excluding 0 = general)
    slide_nums = sorted({n.slide_number for n in notes if n.slide_number > 0})
    # Also include slides from images that may have no notes
    num_images = len(st.session_state.get("slide_images", []))
    all_slides = sorted(set(slide_nums) | set(range(1, num_images + 1)))

    q = search_query.strip().lower() if search_query else ""

    groups = []
    for sn in all_slides:
        cls = "notes-group active" if sn == active_slide else "notes-group"
        slide_notes = [n for n in notes if n.slide_number == sn]

        # Apply search filter
        if q:
            slide_notes = [
                n for n in slide_notes
                if q in n.slide_title.lower()
                or q in n.exact_transcript.lower()
                or q in n.ai_insight.lower()
            ]

        count = len(slide_notes)
        header = (
            f'<div class="col-label" style="margin-top:10px;">'
            f'🧠 Slide {sn} Notes &nbsp;'
            f'<span style="color:#484f58;font-weight:400;font-size:0.72rem;text-transform:none;">{count} insight(s)</span>'
            f'</div>'
        )

        if slide_notes:
            cards = ''.join(_note_card_html(n, f"s{sn}_{i}") for i, n in enumerate(slide_notes))
        else:
            cards = (
                f'<div style="background:rgba(255,255,255,0.01); border:1px dashed rgba(100,160,255,0.15); '
                f'border-radius:14px; padding:3rem 1.5rem; text-align:center; color:#8b949e;">'
                f'<div style="font-size:2rem; margin-bottom:0.5rem;">🧠</div>'
                f'<strong style="color:#58a6ff;">No Specific Verbal Insights</strong><br>'
                f'<span style="font-size:0.85rem; color:#484f58; display:block; margin-top:6px; line-height:1.5;">'
                f'The professor did not explain verbal-only insights for Slide {sn} in this chunk.</span></div>'
            )

        groups.append(f'<div class="{cls}" data-slide="{sn}">{header}{cards}</div>')

    html = f'<div class="notes-viewer" data-active="{active_slide}">{"" .join(groups)}</div>'
    st.markdown(html, unsafe_allow_html=True)


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