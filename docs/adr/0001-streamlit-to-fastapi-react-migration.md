# ADR 0001: Streamlit to FastAPI + React Decoupled Architecture Migration

*   **Status**: Accepted
*   **Date**: 2026-06-23

---

## Context

Initially, the project was developed as a synchronous Streamlit application. While Streamlit allowed rapid prototyping of the alignment pipeline script, its architectural model introduced significant barriers as features grew:
1.  **Rigid Execution Loop**: Streamlit executes the entire Python script from top to bottom on any user interaction (e.g., clicking a button, moving a slider). Managing complex UI states (e.g., custom waveform playback, timeline zoom levels, slide previews) became extremely fragile.
2.  **Synchronous/Blocking Execution**: Streamlit's model made running long, CPU/GPU-heavy processing pipelines (Whisper transcribing, OCR rendering, LLM calls) difficult to run asynchronously. Starting a job would block UI interactions entirely or require hacky caching solutions.
3.  **Real-Time Feedback Constraints**: Displaying granular processing steps (e.g. "Step 2 of 4: Transcribing audio - 25% complete") in real time to the user is difficult without WebSocket integration, which Streamlit does not naturally support in a decoupled way.

---

## Decision

We migrated the application to a decoupled, modern web architecture:
*   **Backend**: A FastAPI REST and WebSocket server (`server.py`).
*   **Frontend**: A Vite-powered React Single Page Application (SPA) (`frontend/`).

### Processing Workloads & Concurrency Model
To execute heavy processing tasks without blocking the backend:
1.  **Thread Pool Executor**: Long-running alignment pipelines are encapsulated in [PipelineJob](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/pipeline.py#L15) instances and dispatched to a background thread using `loop.run_in_executor(None, job.run)`.
2.  **WebSocket Progress Logging**: The background thread reports progress updates back to the client using a thread-safe callback that dispatches messages to the active WebSocket channel via `asyncio.run_coroutine_threadsafe(websocket.send_json(...), loop)`.
3.  **Early Cancellation**: A separate async task (`monitor_disconnect`) monitors the WebSocket connection. If the client disconnects or closes the tab, a `threading.Event()` cancellation flag is set. The background job periodically checks this flag and aborts early via `PipelineCancelledError`.

---

## Consequences

### Positive
*   **State Isolation**: The frontend handles UI state natively (playback position, audio waveforms, navigation panel visibility) without server-side re-runs.
*   **Responsive UI**: The browser remains highly responsive while alignment runs in the background. Users can browse their saved libraries or adjust settings.
*   **Clean Cancellation**: Disconnecting immediately halts Whisper, OpenCV, or LLM execution, preventing runaway API costs and CPU waste.

### Neutral / Negative
*   **Multiple Servers**: Developers must run both a FastAPI server and a React Vite dev server. To mitigate this complexity, a centralized [run.py](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/run.py) script was introduced to start, monitor, and clean up both servers with one command.
