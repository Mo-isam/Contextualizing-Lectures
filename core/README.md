# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rules
1. **UI Separation:** **Under no circumstances should `import streamlit as st` exist in this folder.** All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.
2. **Provider Isolation (Facade Pattern):** **Under no circumstances should `google.genai` be imported anywhere except `llm_service.py`.** All AI provider logic, including cloud file uploads and generation configurations, must be routed through this central service so the core processors remain 100% provider-agnostic.

### 🧩 Key Components
* **`config.py`**: The centralized Configuration Engine. It auto-generates and reads `config.yaml`, completely eliminating hardcoded "magic numbers" (like Whisper models, LLM RPM limits, and UI defaults) from the codebase.
* **`models.py`**: The strict source of truth for data structures (e.g., `AlignedNote`, `LectureSession`). Includes flags like `is_off_topic` and `pipeline_type` to dictate UI rendering behaviors.
* **`llm_service.py`**: The centralized AI API gateway and Facade. It manages proactive RPM pacing, fallback routing, and dynamically blacklists `_dead_models` mid-run to prevent quota spam loops.
* **`storage.py`**: Handles O(1) instantaneous session saving. It writes strictly-typed JSON metadata that points to deduplicated, SHA-256 hashed files, permanently solving massive disk bloat.
* **`audio_processor.py`**: Manages FFmpeg media extractions and Whisper/Gemini routing. It directly intercepts and patches the global `tqdm` module to stream live, frame-by-frame progress to the UI.
* **`video_processor.py`**: The Computer Vision engine. Extracts video frames and detects structural cuts using Gaussian-blurred SSIM. Matches frames to PDF slides using ORB feature detection and RANSAC spatial verification, utilizing 2-Pass Temporal Smoothing to perfectly handle slide build-up animations without AI.
* **`ai_aligner.py`**: The alignment engine supporting dual pipelines:
  * **Audio Pipeline:** Uses a Variable Semantic Chunker and `<previous_context>` injection.
  * **Video Pipeline:** Uses deterministic midpoint math to fuse audio with visual CV chapters, followed by a Boolean JSON LLM filter to extract off-topic tangents.