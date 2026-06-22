# 🎓 Contextualizing Lectures · AI (React Studio Edition)

An AI-powered pipeline that bridges static PDF slides with dynamic verbal insights from recorded audio or video lectures. It features a **Dual-Pipeline Architecture**:
1. **Audio-Only Pipeline:** Uses LLMs to semantically map spoken words to slide content via variable chunking.
2. **Video-Visual Pipeline:** Uses deterministic Computer Vision (SSIM & ORB/RANSAC) to track on-screen slides, drastically reducing AI hallucination and API costs.

---

## 🏗️ Architecture

This project is built using a decoupled, highly modular **FastAPI + React SPA** architecture:
*   **FastAPI REST & WebSocket Server (`server.py`)**: Serves session lists, downloads, saves, config persistence, and handles heavy alignment workloads asynchronously over WebSockets.
*   **Decoupled Core Processing (`core/`)**: Houses deterministic CV estimators, OCR engines, Whisper loaders, and LLM aligners. The heavy execution pipeline is encapsulated in a thread-safe, cancelable job scheduler (`core/pipeline.py`).
*   **Vite-Powered React SPA (`frontend/`)**: Renders the desktop studio environment, file uploader wizard, saved session library, and configuration panels.
*   **Client-Side WaveSurfer Orchestrator**: Incorporates a custom `useWaveSurfer` hook and sub-components (`SlideTimeline` and `SlideJumpPills`) to drive timelines, visual slide boundaries, hover timecards, and slide-snapping features client-side.

### Directory Structure

```text
Contextualizing-Lectures-React/
├── core/
│   ├── pipeline.py         # Thread-safe cancelable alignment scheduler
│   ├── ai_aligner.py       # LLM transcript-to-slide alignment
│   ├── video_processor.py  # Computer Vision SSIM transition detector & ORB matcher
│   ├── audio_processor.py  # local Whisper / Gemini AI audio transcribers
│   ├── pdf_processor.py    # PyMuPDF and AI slide parsing
│   ├── system_loader.py    # Lazy dependency pre-warming checks
│   └── storage.py          # Session loading/saving serializer
├── frontend/
│   ├── src/
│   │   ├── services/
│   │   │   └── api.ts      # Centralized HTTP/WS Api Client
│   │   ├── hooks/
│   │   │   └── useWaveSurfer.ts # Custom WaveSurfer player hook
│   │   ├── components/     # UI Sub-components (Timeline, Pills, Viewer)
│   │   ├── views/          # Views (Home, Library, Upload, Processing, Studio)
│   │   └── App.tsx         # Client SPA view router
│   ├── package.json        # Node configuration
│   └── vite.config.ts      # Vite dev server with reverse proxy settings
├── data_storage/           # Local session library database (JSON)
├── server.py               # FastAPI server entrypoint
└── requirements.txt        # Python backend dependencies
```

---

## 🚀 Installation & Usage

### 1. Prerequisites
Ensure you have **FFmpeg** installed on your system's PATH. This is required for extracting audio from video files and chunking media.

### 2. Backend Setup
Install Python dependencies:
```bash
pip install -r requirements.txt
```

### 3. Running the Development Servers

You can run both the FastAPI backend and the React frontend dev servers concurrently with a single command from the project root:
```bash
python run.py
```
*(This script will automatically verify that frontend dependencies are installed, boot both servers, merge their console outputs with color-coded prefixes, and safely terminate all background processes on **Ctrl+C**).*

---

### 💡 Alternative Manual Setup
If you prefer running the servers in separate terminals for debugging, follow these steps:

#### A. Start the Backend Server
```bash
python server.py
```
*(The API server runs on `http://127.0.0.1:8000`)*

#### B. Start the Frontend Server
1. Navigate to the frontend directory and install dependencies:
   ```bash
   cd frontend
   npm install
   ```
2. Start the Vite React dev server:
   ```bash
   npm run dev
   ```
   *(Access the app at `http://localhost:5173`. Requests to `/api`, `/data`, and `/tmp` are proxied to the backend automatically).*

### 4. API Credentials
You will need a Gemini API key from [Google AI Studio](https://aistudio.google.com/) to run the semantic layout alignment pipeline.
