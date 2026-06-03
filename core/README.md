# ⚙️ Core Module

This folder contains the pure backend logic, data transformation, and LLM networking for the application.

### 🚨 The Golden Rule
**Under no circumstances should `import streamlit as st` exist in this folder.** 
All errors, warnings, and progress updates must be emitted using standard Python `logging` or by passing messages to a `progress_cb` (callback) function.

### 🧩 Key Components
* **`models.py`**: The source of truth for data structures. Processors must return these dataclasses, not raw dictionaries.
* **`llm_service.py`**: The master gateway to the Gemini API. It handles 429 rate limit parsing, safety filter bypasses, and model hot-swapping automatically.
* **`storage.py`**: Handles writing objects to disk and upgrading legacy JSON files back into `models.py` dataclasses.