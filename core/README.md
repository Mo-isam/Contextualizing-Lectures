# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rules
1. **UI Separation:** **Under no circumstances should `import streamlit as st` exist in this folder.** All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.
2. **Provider Isolation (Facade Pattern):** **Under no circumstances should `google.genai` be imported anywhere except `llm_service.py`.** All AI provider logic, including cloud file uploads and generation configurations, must be routed through this central service so the core processors remain 100% provider-agnostic.

### 🧩 Key Components
* **`config.py`**: The centralized Configuration Engine. It auto-generates and reads `config.yaml`, completely eliminating hardcoded "magic numbers" (like Whisper models, LLM RPM limits, and UI defaults) from the codebase.
* **`models.py`**: The strict source of truth for data structures (e.g., `AlignedNote`, `LectureSession`). By enforcing `LectureSession`, we completely decouple the backend from Streamlit's arbitrary session state.
* **`llm_service.py`**: The centralized AI API gateway and Facade. It completely abstracts the `google-genai` SDK, manages cloud media storage, handles transient JSON parsing, and utilizes `config.yaml` to dynamically apply proactive RPM pacing and fallback routing.
* **`storage.py`**: Handles O(1) instantaneous session saving. It writes strictly-typed JSON metadata that points to deduplicated, SHA-256 hashed files, permanently solving massive disk bloat.
* **`audio_processor.py`**: Manages FFmpeg media extractions and Whisper/Gemini routing. It strictly enforces transient memory limits, ensuring massive uncompressed `.wav` files are securely deleted the moment transcription completes.
* **`ai_aligner.py`**: The semantic mapping engine. It uses a Variable Semantic Chunker to slice transcripts, and utilizes `<previous_context>` injection alongside Chain-of-Thought JSON Schema generation to achieve highly accurate, non-linear transcript-to-slide mapping.