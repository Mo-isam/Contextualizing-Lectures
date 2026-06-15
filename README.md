# 🎓 Contextualizing Lectures · AI

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded audio or video lectures. It features a **Dual-Pipeline Architecture**:
1. **Audio-Only Pipeline:** Uses LLMs to semantically map spoken words to slide content via variable chunking.
2. **Video-Visual Pipeline:** Uses deterministic Computer Vision (SSIM & ORB/RANSAC) to track on-screen slides, drastically reducing AI hallucination and API costs.

## 🏗️ Architecture

This project follows a strict modular architecture separating the user interface from backend processing. Key features include:
* **Deterministic Visual Alignment (New):** For video uploads, it uses Gaussian-blurred SSIM for cut detection and RANSAC spatial verification to map video frames to PDF slides geometrically.
* **Temporal Smoothing & Semantic Filtering (New):** "Slide build-up" animations are flawlessly grouped via 2-Pass Back-fill Smoothing. A Boolean LLM Filter is then used to expertly extract off-topic tangents and interleave them into the UI chronologically as visually distinct "Tangent" cards.
* **Immersive Studio UI:** A widescreen, native-scrolling desktop experience featuring asymmetric columns (60/40 split) ensuring the slide remains permanently visible ("sticky") while scrolling through long transcripts.
* **SPA "Wizard" State Machine:** The frontend uses a dynamic router (`app.py`), replacing cluttered sidebars with a clean, step-by-step flow (Home → Upload → Processing → Studio).
* **Per-User Proactive API Pacing & Fallback:** The pipeline dynamically reads rate limits from a YAML config, injecting micro-sleeps to avoid limits, and gracefully falls back through a priority list of models. Blacklists "dead" models mid-run to prevent quota spam.
* **O(1) Storage & Deduplication:** Uploads are hashed (SHA-256) for instant deduplication. Sessions save pipeline metadata (`pipeline_type`) locally and load instantly without duplicating media files.

```text
.
├── app.py                # Main Streamlit SPA Router (State Machine)
├── config.yaml           # Auto-generated user configuration
├── requirements.txt      # Python dependencies (OpenCV, PyMuPDF, etc.)
├── ui/                   # Frontend views, modals, CSS, and JS
│   ├── dialogs.py        # Settings and Save Session modals
├── core/                 # Pure backend logic (No Streamlit allowed here)
│   ├── config.py         # YAML Configuration Engine
│   ├── video_processor.py# CV Engine (SSIM, ORB, RANSAC, Temporal Smoothing)
```

## 🚀 Installation & Usage

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You must have FFmpeg installed on your system PATH for audio extraction).*

2. **Run the application:**
   ```bash
   streamlit run app.py
   ```

3. **Get an API Key:** 
   You will need a free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/) to run the semantic alignment.

