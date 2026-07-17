# ADR 0004: Use `uv` for Project Dependency Management

*   **Status**: Accepted
*   **Date**: 2026-07-09

---

## Context

The project previously relied on a global Python environment with dependencies defined in a flat `requirements.txt` file. This introduced several problems:
1.  **Environment Pollution**: Installing packages globally (or in an unmanaged user environment) can cause conflicts with other Python projects on the same machine.
2.  **No Package Locking**: `requirements.txt` only specified minimum versions (e.g. `fastapi>=0.110.0`). This meant that subsequent environments created from it could pull in different, potentially breaking sub-dependencies.
3.  **CPU-Only PyTorch Overhead**: PyTorch (`torch`) is a primary dependency for Whisper and OpenCV matching logic. By default, PyPI installs GPU-enabled builds of PyTorch containing CUDA binaries, which are several gigabytes in size. This is unnecessary since the project is targeted for CPU-only environments.
4.  **Local Non-Python Binaries**: While toolkits like `pixi` can automatically package and download non-Python binaries (such as `ffmpeg` and `node`), the developer already has these utilities installed globally on their system, making additional binary cache isolation redundant.

---

## Decision

We migrate package management from a flat `requirements.txt` to `uv` using a PEP 621 compliant `pyproject.toml` file.

### Dependency Specification & CPU Routing
*   We declare dependencies inside `pyproject.toml` to leverage standard Python packaging conventions.
*   To keep environment sizes small and install fast on CPU hosts, we configure a custom PyTorch CPU index mapping using `uv`'s source routing rules:
    ```toml
    [[tool.uv.index]]
    name = "pytorch-cpu"
    url = "https://download.pytorch.org/whl/cpu"
    explicit = true

    [tool.uv.sources]
    torch = { index = "pytorch-cpu" }
    ```
    This directs `uv` to resolve and install the lightweight, CPU-optimized build of PyTorch from the official PyTorch wheel directory rather than the massive GPU build on PyPI.

### Virtual Environment Isolation & Cache Matching
*   We use `uv sync` to generate a local virtual environment (`.venv/`) and write a deterministic `uv.lock` file.
*   To enable `uv`'s native file hardlinking (which dramatically improves install speed and saves disk space), we configure a localized cache directory on the same drive partition:
    ```toml
    [tool.uv]
    cache-dir = "S:\\.cache\\uv"
    ```
    This avoids cross-drive file copies and suppresses fallback warnings.
*   Developers run the system by prefixing commands with `uv run` (e.g., `uv run python run.py`) or activating the `.venv` directory, guaranteeing that local Python calls route through the isolated environment.

---

## Consequences

### Positive
*   **Deterministic Environments**: The `uv.lock` file guarantees that every developer or environment setup uses the exact same sub-dependency versions, eliminating "works on my machine" issues.
*   **Speed**: Rust-powered dependency resolution and caching makes virtual environment synchronization extremely fast.
*   **Reduced Environment Footprint**: By explicit routing of `torch` to the CPU-only package registry, we avoid multi-gigabyte downloads.
*   **Developer Simplicity**: Since `run.py` resolves execution via `sys.executable`, running the centralized dev script via `uv run python run.py` naturally propagates the virtual environment context to the FastAPI server processes without manual activation.

### Neutral / Negative
*   **Manual External Tooling**: Developers must still ensure `ffmpeg` and `node` are installed globally on their host system (unlike with `pixi` which installs them isolated in `.pixi`). Since these tools are already present on developer workstations, this introduces zero additional friction.
