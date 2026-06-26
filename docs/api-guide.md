# 📡 API Guide — Contextualizing Lectures

This document describes the REST and WebSocket API endpoints exposed by the FastAPI backend (`server.py`).

> **Auto-generated OpenAPI docs** are available at `http://localhost:8000/docs` when the server is running.

---

## Base URL

When running locally:

| Component | URL |
|---|---|
| Backend API | `http://127.0.0.1:8000` |
| Vite Dev Proxy | `http://localhost:5173` (proxied to backend) |
| Swagger UI | `http://localhost:8000/docs` |

All endpoints are prefixed with `/api` except static file mounts.

---

## REST Endpoints

### Sessions

#### `GET /api/sessions`
List all saved sessions in the local library.

**Response:** `Array<SavedSessionInfo>`
```json
[
  {
    "name": "Aligned Session - Lecture1",
    "description": "Processed alignment session using visual pipeline",
    "id": "a1b2c3d4",
    "filename": "session_a1b2c3d4.json",
    "timestamp": 1719000000.0,
    "pipeline_type": "visual"
  }
]
```

#### `GET /api/session/{filename}`
Retrieve and deserialize a specific session by filename (e.g. `session_a1b2c3d4.json`).

**Response includes:**
- `session_name`, `session_description`, `session_id`
- `pdf_path`, `media_path` (relative to `data_storage/`)
- `transcript_segments` — array of `{ id, start, end, text }`
- `slides` — array of `{ page_number, title, text }`
- `final_output` — array of `{ slide_number, slide_title, exact_transcript, ai_insight, timestamp_start, timestamp_end, is_off_topic }`
- `slide_images` — relative paths to rendered PDF slide PNGs
- `peaks` — waveform peak data for the audio visualizer

#### `POST /api/session/save`
Save a session to persistent storage.

**Request body:** `SaveSessionSchema`
```json
{
  "session_name": "Aligned Session - Lecture1",
  "session_description": "...",
  "pdf_path": "files/documents/lecture.pdf",
  "media_path": "files/media/lecture.mp4",
  "transcript_segments": [...],
  "slides": [...],
  "final_output": [...],
  "pipeline_type": "visual"
}
```

**Response:** `{ "status": "success", "filename": "session_abc123.json" }`

#### `PATCH /api/session/{filename}/metadata`
Update only the title and description of a session file.

**Request body:** `{ "session_name": "...", "session_description": "..." }`

#### `DELETE /api/session/{filename}`
Delete a session JSON file from storage.

---

### Configuration

#### `GET /api/config`
Retrieve all application configuration settings.

**Response fields:**
- `ui_defaults` — `is_paid_api`, `default_model`, `selected_model_label`, `pdf_engine`, `tx_engine`
- `audio` — `whisper_model_size`, `sample_rate`
- `alignment` — `min_chunk_duration_sec`, `max_chunk_duration_sec`
- `pdf` — `render_zoom`
- `video` — `matching_strategy`, `frame_sample_rate`, `ssim_threshold`
- `model_options` — label-to-model-ID mapping
- `model_priority` — ordered fallback list
- `rpm_limits` — per-model rate limit map

#### `POST /api/config`
Save configuration updates. Accepts any subset of config fields.

**Request body:** `ConfigUpdateSchema` (all fields optional)

#### `POST /api/config/reset`
Reset configuration to factory defaults.

**Response:** `{ "status": "success", "message": "..." }`

---

### Files & Uploads

#### `GET /api/files`
List stored documents and media files.

**Response:** `{ documents: [...], media: [...] }`
Each entry: `{ name, relative_path, size_bytes, modified_time }`

#### `POST /api/upload`
Upload a PDF or media file (multipart form).

**Parameters:**
- `file` — the file binary
- `file_type` — `"pdf"` or `"media"`

**Notes:**
- PPTX/PPT files uploaded as `file_type=pdf` are auto-converted to PDF via Windows PowerPoint COM interface
- Files are SHA-256 deduplicated via `file_registry.json`
- Media files with an accompanying `_audio.wav` extract are excluded from listings

**Response:** `{ filename, absolute_path, relative_path }`

---

## WebSocket Pipeline

### `ws://host/api/process/stream`

The processing pipeline runs over a single WebSocket connection:

1. **Client sends** a JSON config payload (after connection is accepted)
2. **Server streams** progress messages as JSON
3. **Server sends** a final `"complete"` or `"error"` message
4. **Connection closes**

### Client → Server (initial config)

```json
{
  "pdf_path": "files/documents/lecture.pdf",
  "media_path": "files/media/lecture.mp4",
  "pipeline_mode": "audio",
  "pdf_engine": "Native (PyMuPDF) - Fast",
  "tx_engine": "Local Whisper (CPU) - Private",
  "selected_model": "gemini-3.5-flash",
  "api_key": "",
  "is_paid_api": false
}
```

### Server → Client (progress)

```json
{
  "status": "processing",
  "stage": "pdf",
  "progress": 0.45,
  "message": "Extracting slide text...",
  "models_list": ["gemini-3.5-flash", "gemini-3.1-flash-lite"],
  "active_model": "gemini-3.5-flash",
  "model_status": "active",
  "model_message": null,
  "dead_models": [],
  "model_call_stats": {
    "gemini-3.5-flash": { "success": 3, "failure": 0 }
  }
}
```

### Stages

| Stage | Description |
|---|---|
| `preflight` | Dependency loading, environment checks |
| `pdf` | PDF text extraction / slide parsing |
| `video` | Video frame extraction and CV matching (visual pipeline only) |
| `audio` | Audio transcription (Whisper / Gemini) |
| `alignment` | Semantic alignment of transcript to slides |

### Completion payload

```json
{
  "status": "complete",
  "data": {
    "transcript_segments": [...],
    "slides": [...],
    "final_output": [...],
    "slide_images": ["session_abc/slide_images/page_1.png", ...],
    "peaks": [0.0, 0.15, 0.42, ...]
  }
}
```

### Cancellation

If the WebSocket client disconnects mid-pipeline, the server detects the disconnect and sets an internal cancellation event that gracefully stops processing.

---

## Static File Mounts

| Mount | Directory | Purpose |
|---|---|---|
| `/data` | `data_storage/` | Session JSON files, uploaded documents, media files |
| `/tmp` | `data_storage/tmp/` | Rendered slide images, temporary conversions |

---

## Data Contracts

### `AlignedNote`
```typescript
{
  slide_number: number;      // 1-indexed slide page
  slide_title: string;
  exact_transcript: string;  // The section of transcript that maps to this slide
  ai_insight: string;        // AI-generated explanation/summary
  timestamp_start: number;   // Start time in seconds
  timestamp_end: number;     // End time in seconds
  is_off_topic: boolean;     // True if this note is flagged as a tangent
}
```

### `TranscriptSegment`
```typescript
{
  id: number;                // Sequential segment ID
  start: number;             // Start time in seconds
  end: number;               // End time in seconds
  text: string;              // Transcribed text
}
```

### `Slide`
```typescript
{
  page_number: number;       // 1-indexed page number
  title: string;             // Slide title (extracted or LLM-generated)
  text: string;              // Full slide text content
}
```
