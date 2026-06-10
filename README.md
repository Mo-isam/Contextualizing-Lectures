# 🎓 Contextualizing Lectures · AI

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded lectures. It uses local Whisper models (or Gemini Audio) to transcribe lectures, Gemini Vision to read slides, and LLMs to semantically map the spoken word to the exact slide being presented.

## 🏗️ Architecture

This project follows a strict modular architecture separating the user interface from backend processing. Key features include:
* **SPA "Wizard" State Machine:** The frontend uses a dynamic router (`app.py`), replacing cluttered sidebars with a clean, step-by-step Single-Page Application flow (Home → Upload → Processing → Studio) with dedicated modal dialogs.
* **Live, Precise Progress Tracking:** The UI patches local CPU-bound processes (like Whisper's `tqdm`) to pipe real-time frame progression directly into elegant, right-aligned Streamlit progress bars.
* **Variable Semantic Chunking & Overlapping Context:** Audio is sliced dynamically based on natural pauses. The AI Aligner passes the end of the previous chunk into the next prompt as `<previous_context>`, ensuring the LLM never loses context.
* **Chain-of-Thought Alignment:** The AI uses a strict JSON schema that forces it to explain its reasoning step-by-step *before* mapping IDs, drastically reducing hallucinations.
* **Per-User Proactive API Pacing & Fallback:** The pipeline dynamically reads rate limits from a YAML config, injecting micro-sleeps to avoid limits, and gracefully falls back through a priority list of models.
* **O(1) Storage & Deduplication:** Uploads are hashed (SHA-256) for instant deduplication. Sessions (with custom titles and descriptions) are saved locally and load instantly without duplicating media files.

```text
.
├── app.py                # Main Streamlit SPA Router (State Machine)
├── config.yaml           # Auto-generated user configuration
├── requirements.txt      # Python dependencies
├── ui/                   # Frontend views, modals, CSS, and JS
│   ├── dialogs.py        # Settings and Save Session modals
├── core/                 # Pure backend logic (No Streamlit allowed here)
│   ├── config.py         # YAML Configuration Engine
```

## 🚀 Installation & Usage

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
   *(Note: You must have FFmpeg installed on your system PATH for audio extraction).*

2. **Run the application:**
   ```bash
   streamlit run app.py
   ```

3. **Get an API Key:** 
   You will need a free Google Gemini API key from [Google AI Studio](https://aistudio.google.com/) to run the semantic alignment.

