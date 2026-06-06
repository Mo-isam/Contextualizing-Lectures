# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rule
**Under no circumstances should `import streamlit as st` exist in this folder.** 
All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.

### 🧩 Key Components
* **`models.py`**: The strict source of truth for data structures (e.g., `AlignedNote`, `LectureSession`). By enforcing `LectureSession`, we completely decouple the backend from Streamlit's arbitrary session state.
* **`llm_service.py`**: The centralized Gemini API gateway. It utilizes a per-API-key proactive pacing dictionary to maintain exact RPMs. It supports yielding sleep loops (to keep the UI responsive) and bypass flags for Paid API tiers.
* **`storage.py`**: Handles writing objects to disk using OS-level atomic writes and `uuid.uuid4()` filenames, mathematically guaranteeing zero file-collision race conditions when the UI reloads rapidly.
* **`ai_aligner.py`**: The semantic mapping engine. It uses a Variable Semantic Chunker to slice transcripts, and utilizes `<previous_context>` injection alongside Chain-of-Thought JSON Schema generation to achieve highly accurate, non-linear transcript-to-slide mapping.