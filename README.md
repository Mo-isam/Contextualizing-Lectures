# 🎓 Contextualizing Lectures · AI

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded lectures. It uses local Whisper models (or Gemini Audio) to transcribe lectures, Gemini Vision to read slides, and LLMs to semantically map the spoken word to the exact slide being presented.

## 🏗️ Architecture

This project follows a strict modular architecture to separate the user interface from the backend processing and LLM network logic.

```text
.
├── app.py                # Main Streamlit orchestrator
├── requirements.txt      # Python dependencies
├── ui/                   # Frontend layout, CSS, JS, and Streamlit widgets
├── core/                 # Pure backend logic (No Streamlit allowed here)
│   ├── models.py         # Strict Dataclass blueprints (Slide, TranscriptSegment)
│   ├── llm_service.py    # Centralized Gemini API rate-limiting & retry engine
│   ├── storage.py        # Local JSON session saving/loading
│   └── ...processors.py  # Audio, PDF, and Alignment logic
└── data_storage/         # Ephemeral local storage for files and sessions
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