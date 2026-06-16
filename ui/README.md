# 🎨 UI Module

This folder isolates all frontend layout, styling, and widget rendering from the backend business logic.

### 🧩 Components
* **`dialogs.py`**: Contains Streamlit modal popups (`@st.dialog`) for Settings and Saving Sessions, keeping the main UI clean and uncluttered.
* **`components.py`**: Contains reusable Streamlit layout blocks (e.g., `render_note_card`, `render_audio_player`, `render_library_card`). These functions accept dataclasses from `/core` and format them for the user.
* **`assets.py`**: A utility that reads raw CSS and JS files and cleanly injects them into the Streamlit DOM.
* **`styles.css` & `scripts.js`**: Raw web assets kept separate from Python code. Includes aggressive CSS selectors to override native Streamlit UI quirks (like hiding multi-file upload buttons).

### 🚦 The SPA Router & View Decoupling
To achieve sub-second startup times, the UI architecture is split in two:
1. **`app.py`**: An ultra-lightweight **State Machine Router**. It imports no heavy backend physics. It simply checks `st.session_state.step` and mounts the correct view.
2. **`ui/views.py`**: Contains the actual view logic (`view_home`, `view_upload`, `view_processing`, `view_studio`). Heavy backend imports are pushed entirely *inside* the execution blocks of these functions so they only load when the user physically clicks a trigger button.