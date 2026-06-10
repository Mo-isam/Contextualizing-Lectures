# 🎨 UI Module

This folder isolates all frontend layout, styling, and widget rendering from the backend business logic.

### 🧩 Components
* **`dialogs.py`**: Contains Streamlit modal popups (`@st.dialog`) for Settings and Saving Sessions, keeping the main UI clean and uncluttered.
* **`components.py`**: Contains reusable Streamlit layout blocks (e.g., `render_note_card`, `render_audio_player`, `render_library_card`). These functions accept dataclasses from `/core` and format them for the user.
* **`assets.py`**: A utility that reads raw CSS and JS files and cleanly injects them into the Streamlit DOM.
* **`styles.css` & `scripts.js`**: Raw web assets kept separate from Python code. Includes aggressive CSS selectors to override native Streamlit UI quirks (like hiding multi-file upload buttons).

### 🚦 The SPA Router
Instead of a single long script, `app.py` acts as a **State Machine Router**. It reads `st.session_state.step` and dynamically mounts one of four views:
1. `view_home()`
2. `view_load_session()`
3. `view_upload()`
4. `view_studio()`