# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rule
**Under no circumstances should `import streamlit as st` exist in this folder.** 
All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.

### 🧩 Key Components
* **`models.py`**: The strict source of truth for data structures (e.g., `AlignedNote`). We do not support fallback schemas.
* **`llm_service.py`**: The centralized Gemini API gateway. It utilizes a proactive pacing algorithm (`max(0, interval - elapsed)`) to maintain exact RPMs, completely bypassing 429 errors.
* **`storage.py`**: Handles writing objects to disk using OS-level atomic writes (`.tmp` to `.json`) to prevent race conditions when the UI reloads.
* **`ai_aligner.py`**: The semantic mapping engine. It uses a Variable Semantic Chunker to slice transcripts based on actual silences (> 1.5s) and punctuation, preserving complete thoughts for the LLM.