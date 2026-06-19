# 🎓 Contextualizing Lectures · AI

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded audio or video lectures. It features a **Dual-Pipeline Architecture**:
1. **Audio-Only Pipeline:** Uses LLMs to semantically map spoken words to slide content via variable chunking.
2. **Video-Visual Pipeline:** Uses deterministic Computer Vision (SSIM & ORB/RANSAC) to track on-screen slides, drastically reducing AI hallucination and API costs.

## 🏗️ Architecture

This project follows a strict modular architecture separating the user interface from backend processing. Key features include:
* **Deterministic Visual Alignment (New):** For video uploads, it uses Gaussian-blurred SSIM for cut detection and RANSAC spatial verification to map video frames to PDF slides geometrically.
* **Temporal Smoothing & Semantic Filtering (New):** "Slide build-up" animations are flawlessly grouped via 2-Pass Back-fill Smoothing. A Boolean LLM Filter is then used to expertly extract off-topic tangents and interleave them into the UI chronologically as visually distinct "Tangent" cards.
* **Client-Side Follow Mode Engine (New):** A synchronized "Follow Mode" seamlessly auto-advances lecture slides and note cards during audio/video playback via an independent, client-side JS visibility engine, completely eliminating server-side reruns. Includes auto-sync toggle buttons, cross-slide search, and floating re-sync affordances.
* **Immersive Studio UI:** A widescreen, native-scrolling desktop experience featuring asymmetric columns (60/40 split) ensuring the slide remains permanently visible ("sticky") while scrolling through long transcripts.
* **SPA "Wizard" State Machine:** The frontend uses a dynamic router (`app.py`), decoupling all heavy logic into `ui/views.py` to achieve sub-second app startup times.
* **Smart System Loader:** Dependencies (PyTorch, OpenCV, PyMuPDF) are intelligently lazy-loaded via a pre-flight checklist only when a specific pipeline requires them, saving massive amounts of RAM.
* **Per-User Proactive API Pacing & Fallback:** The pipeline dynamically reads rate limits from a YAML config, injecting micro-sleeps to avoid limits, and gracefully falls back through a priority list of models.
* **Invisible Deduplication Registry:** Uploads retain pristine, human-readable filenames and are automatically routed to `documents/` or `media/` folders. An invisible background SHA-256 registry (`file_registry.json`) ensures files are deduplicated instantly without bloating the disk.

```text
.
├── app.py                # Ultra-lightweight Streamlit SPA Router
├── config.yaml           # Auto-generated user configuration
├── requirements.txt      # Python dependencies
├── ui/                   # Frontend UI layer
│   ├── views.py          # Decoupled SPA views (Home, Upload, Processing, Studio)
│   ├── dialogs.py        # Modals for Settings and Saving
├── core/                 # Pure backend logic (No Streamlit allowed here)
│   ├── system_loader.py  # Smart Dependency Pre-warming Engine
│   ├── config.py         # YAML Configuration Engine
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

