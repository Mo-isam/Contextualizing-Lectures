# 🎓 Contextualizing Lectures · AI

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded lectures. It uses local Whisper models (or Gemini Audio) to transcribe lectures, Gemini Vision to read slides, and LLMs to semantically map the spoken word to the exact slide being presented.

## 🏗️ Architecture

This project follows a strict modular architecture separating the user interface from backend processing. Key intelligent features include:
* **Variable Semantic Chunking & Overlapping Context:** Audio is sliced dynamically based on natural pauses. The AI Aligner passes the end of the previous chunk into the next prompt as `<previous_context>`, ensuring the LLM never loses the conversational thread during boundary splits.
* **Chain-of-Thought Alignment:** The AI uses a strict JSON schema that forces it to explain its reasoning step-by-step *before* mapping IDs, drastically reducing hallucinations.
* **Per-User Proactive API Pacing:** Instead of reactive blocking, the pipeline calculates exact target RPMs per API key, injecting 1-second UI-yielding micro-sleeps only when necessary. Paid API users can bypass this via the UI.

```text
.
├── app.py                # Main Streamlit orchestrator
├── requirements.txt      # Python dependencies
├── ui/                   # Frontend layout, CSS, JS, and Streamlit widgets
├── core/                 # Pure backend logic (No Streamlit allowed here)
│   ├── models.py         # Strict Dataclass blueprints (Slide, TranscriptSegment)
│   ├── llm_service.py    # Proactive API pacing and retry engine
│   ├── storage.py        # Atomic local JSON session saving/loading
│   └── ...processors.py  # Audio, PDF, and Semantic Alignment logic
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

