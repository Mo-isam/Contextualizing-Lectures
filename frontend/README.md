# 🎨 Frontend — Lecture AI Studio

A **React 19 SPA** that provides the desktop studio environment for the Contextualizing Lectures pipeline. Built with Vite, TypeScript, Tailwind CSS 4, and WaveSurfer.js.

---

## 🧱 Architecture

```text
frontend/
├── src/
│   ├── views/               # Route-level view pages
│   │   ├── HomeView.tsx          # Landing page with action cards
│   │   ├── LibraryView.tsx       # Saved sessions browser & search
│   │   ├── CreateSessionView.tsx # Upload wizard + config form
│   │   ├── ProcessingView.tsx    # Real-time pipeline progress dashboard
│   │   └── StudioView.tsx        # Aligned session player & viewer
│   ├── components/          # Reusable UI components
│   │   ├── AudioPlayer.tsx       # WaveSurfer audio player wrapper
│   │   ├── NoteCard.tsx          # Transcript + AI insight card
│   │   ├── SettingsModal.tsx     # Full configuration modal (LLM, audio, video)
│   │   ├── SlideJumpPills.tsx    # Slide boundary quick-jump pills
│   │   ├── SlideTimeline.tsx     # Visual timeline with slide regions
│   │   └── SlideViewer.tsx       # PDF slide image viewer
│   ├── hooks/
│   │   └── useWaveSurfer.ts # Custom hook wrapping WaveSurfer.js
│   ├── services/
│   │   └── api.ts           # Centralised HTTP & WebSocket API client
│   ├── types/
│   │   └── index.ts         # TypeScript data contracts (LectureSession, AlignedNote, etc.)
│   ├── utils/
│   │   └── boundaries.ts    # Slide boundary computation & time formatting
│   ├── App.tsx              # View router & global state
│   ├── main.tsx             # React DOM entry point
│   └── index.css            # Tailwind CSS v4 entry + custom styles
├── public/
│   ├── favicon.svg
│   └── icons.svg
├── index.html
├── package.json
├── vite.config.ts           # Vite config with FastAPI reverse proxy
├── tsconfig.json
├── tsconfig.app.json
└── eslint.config.js
```

### View Routing

The app is a single-page application with **5 view states** managed via a `useState<AppStep>` in `App.tsx` — no React Router dependency:

| Step | View | Purpose |
|---|---|---|
| `home` | `HomeView` | Landing page with "New Session" and "Open Library" CTAs |
| `library` | `LibraryView` | Browse, search, and load previously saved sessions |
| `create-session` | `CreateSessionView` | Upload PDF/media, configure pipeline mode & model |
| `processing` | `ProcessingView` | Real-time WebSocket pipeline progress with model status |
| `studio` | `StudioView` | Aligned session playback, slide viewer, and note inspection |

---

## 🚀 Development

### Prerequisites

- Node.js >= 18
- Python backend server running (see root `README.md`)

### Setup

```bash
cd frontend
npm install
```

### Dev Server

```bash
npm run dev
```

Starts the Vite dev server at **`http://localhost:5173`** with hot module replacement (HMR).
API requests to `/api`, `/data`, and `/tmp` are **reverse-proxied** to the FastAPI backend at `http://127.0.0.1:8000` (configured in `vite.config.ts`).

### Production Build

```bash
npm run build
```

Output is written to `frontend/dist/` and can be served by the FastAPI backend directly.

### Lint

```bash
npm run lint
```

---

## 🧩 Key Components

### `AudioPlayer` (Component)
Wraps WaveSurfer.js with play/pause, mute, seek controls. Displays the waveform with slide region overlays when boundaries are provided.

### `SlideTimeline` (Component)
Renders a horizontal timeline bar with coloured blocks representing each slide's time region. Highlights the currently-active slide as the playhead moves.

### `SlideJumpPills` (Component)
Pill-shaped buttons at the top of the timeline that snap the audio playhead to the start of each slide — useful for quick navigation during review.

### `SlideViewer` (Component)
Displays individual PDF slide images rendered server-side (via PyMuPDF). Supports left/right navigation and syncs with the current playhead position.

### `NoteCard` (Component)
A card showing the aligned transcript snippet and its corresponding AI-generated insight for a specific slide. Handles both on-topic notes and off-topic tangent flags.

### `SettingsModal` (Component)
Full configuration modal exposing all pipeline settings: LLM model choice, Whisper model size, PDF engine, video matching strategy, RPM limits, and paid/free API tier.

### `useWaveSurfer` (Hook)
Custom React hook that manages a WaveSurfer.js instance with peaks preloading, playback state, time tracking, and lifecycle cleanup. Returns `containerRef`, `togglePlay`, `seekToTime`, `currentTime`, `duration`, and playback state flags.

---

## 📡 API Integration

All API calls go through `src/services/api.ts` (`ApiService`), which provides typed methods for:

- `getSessions()` / `getSession(filename)` — CRUD for saved sessions
- `saveSession(payload)` / `deleteSession(filename)` — persistence
- `updateSessionMetadata(filename, name, desc)` — rename/edit
- `getConfig()` / `saveConfig(payload)` / `resetConfig()` — configuration
- `getStoredFiles()` — list uploaded PDF/media files
- `uploadFile(file, fileType)` — upload PDF or media (PPTX auto-converted to PDF)
- `getWebSocketUrl()` — returns the correct WS URL via the Vite proxy
- `getDataUrl(path)` / `getTmpUrl(path)` — resolve relative paths to full URLs

The processing pipeline communicates over a **WebSocket** (`/api/process/stream`), sending JSON progress updates with stage, progress %, messages, model status, and dead-model tracking.

---

## 🎨 Tech Stack

| Dependency | Purpose |
|---|---|
| **React 19** | UI framework |
| **TypeScript ~6.0** | Type safety |
| **Vite 8** | Build tool & dev server |
| **Tailwind CSS 4** | Utility-first styling |
| **WaveSurfer.js 7** | Audio waveform visualization |
| **Lucide React** | Icons |
| **ESLint 10** | Code linting |

---

## 📁 Data Flow

1. **Upload** — User uploads a PDF (or PPTX → auto-converted) and a media file via `CreateSessionView`
2. **Pipeline Launch** — Config sent over WebSocket to FastAPI backend
3. **Progress Streaming** — `ProcessingView` receives real-time `ProgressUpdate` messages (stage, progress %, model status, dead models)
4. **Result** — On completion, the server sends a `"complete"` payload with transcript segments, slides, aligned notes, and slide image paths
5. **Studio** — `StudioView` renders the aligned session: audio waveform, slide timeline, slide viewer, and per-note AI insights
6. **Save** — User can save the session to disk, returning to it later via `LibraryView`
