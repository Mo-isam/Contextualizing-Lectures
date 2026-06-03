# 🎨 UI Module

This folder isolates all frontend layout, styling, and widget rendering from the backend business logic.

### 🧩 Components
* **`assets.py`**: A utility that reads raw CSS and JS files and cleanly injects them into the Streamlit DOM.
* **`components.py`**: Contains reusable Streamlit layout blocks (e.g., `render_note_card`, `render_audio_player`). These functions accept dataclasses from `/core` and format them for the user.
* **`styles.css` & `scripts.js`**: Raw web assets kept separate from Python code for readability and maintainability.