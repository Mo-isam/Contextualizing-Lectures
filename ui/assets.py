"""
assets.py
---------
Utility to load external CSS and JS files and inject them into the Streamlit frontend.
"""
import os
import streamlit as st

UI_DIR = os.path.dirname(__file__)

def load_css():
    """Reads styles.css and injects it into Streamlit."""
    css_path = os.path.join(UI_DIR, "styles.css")
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
        st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)

def inject_jump_script():
    """Reads scripts.js and injects it as an invisible HTML component."""
    js_path = os.path.join(UI_DIR, "scripts.js")
    if os.path.exists(js_path):
        with open(js_path, "r", encoding="utf-8") as f:
            js = f.read()
        # Streamlit 1.40+ strictly forbids width=0 and height=0.
        # We use width="content" and height=1 to bypass validation natively.
        # Since <script> has no physical DOM, it takes up zero actual UI space!
        st.iframe(f"<script>\n{js}\n</script>", height=1, width="content")