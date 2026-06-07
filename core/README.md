# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rules
1. **UI Separation:** **Under no circumstances should `import streamlit as st` exist in this folder.** All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.
2. **Provider Isolation (Facade Pattern):** **Under no circumstances should `google.genai` be imported anywhere except `llm_service.py`.** All AI provider logic, including cloud file uploads and generation configurations, must be routed through this central service so the core processors remain 100% provider-agnostic.

### 🧩 Key Components
* **`models.py`**: The strict source of truth for data structures (e.g., `AlignedNote`, `LectureSession`). By enforcing `LectureSession`, we completely decouple the backend from Streamlit's arbitrary session state.
* **`llm_service.py`**: The centralized AI API gateway and Facade. It completely abstracts the `google-genai` SDK, manages cloud media storage, formats JSON schemas, and utilizes a proactive pacing dictionary to maintain exact RPMs without freezing the UI.
* **`storage.py`**: Handles writing objects to disk using OS-level atomic writes and `uuid.uuid4()` filenames, mathematically guaranteeing zero file-collision race conditions when the UI reloads rapidly.
* **`ai_aligner.py`**: The semantic mapping engine. It uses a Variable Semantic Chunker to slice transcripts, and utilizes `<previous_context>` injection alongside Chain-of-Thought JSON Schema generation to achieve highly accurate, non-linear transcript-to-slide mapping.