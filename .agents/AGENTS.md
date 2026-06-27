# AI Agent Instructions & Guardrails

Welcome! This repository has been structured for optimal agent execution. To prevent regressions, follow these guidelines strictly.

---

## 🧭 Repository Navigation

*   **Single Source of Truth**: Before planning or making changes, read the central architecture document: [docs/architecture.md](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/docs/architecture.md).
*   **Historical Decisions**: Check the Architecture Decision Records (ADRs) under [docs/adr/](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/docs/adr/) to understand *why* complex choices were made.
*   **Changelog**: View [CHANGELOG.md](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/CHANGELOG.md) to see version milestones.

---

## ⚠️ Development Guardrails & Constraints

1.  **Asynchronous Concurrency**:
    *   Do **NOT** write synchronous, blocking code for long-running workflows.
    *   All heavy alignment processing belongs in the thread-safe cancelable job executor [PipelineJob](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/pipeline.py#L15).
    *   Always use `asyncio.run_coroutine_threadsafe` when reporting status from the executor thread back to WebSockets (see [server.py](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/server.py)).
    *   Never reuse deprecated Streamlit components.

2.  **Dual-Pipeline Integrity**:
    *   Respect the boundary between the `audio` (semantic alignment via LLMs) and `visual` (deterministic transition mapping via SSIM & ORB keyframe matching) pipelines.
    *   Do **NOT** introduce LLM API queries for visual keyframe comparisons. Let CV handle transitions deterministically.

3.  **Slide Indexing & OCR**:
    *   Slide indices and page numbers are programmatically assigned during the OCR loading phase to prevent LLM hallucinations.
    *   Never ask the LLM to guess page numbers in the prompts; refer to programmatic properties.

4.  **Path Portability**:
    *   Always resolve database paths and temporary directories using [resolve_data_path](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/storage.py) and [TMP_DIR](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/storage.py). This ensures portable path resolution across different developer/agent systems.

---

## 🔄 Self-Documenting Requirements

To keep documentation from drifting:
*   If you modify **Pydantic schemas** in [core/schemas.py](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/schemas.py), you **MUST** update [docs/architecture.md](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/docs/architecture.md).
*   If you add **new API endpoints** in [server.py](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/server.py), update the API routing overview in [docs/architecture.md](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/docs/architecture.md).
*   Whenever a change is successfully validated, append a record under the unreleased section of [CHANGELOG.md](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/CHANGELOG.md).
