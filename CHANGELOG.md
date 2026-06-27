# Changelog

All notable changes to this project are documented in this file.

---

## [Unreleased]

## [1.1.4] - 2026-06-27
### Added
- Added `.agents/AGENTS.md` containing global guidelines for AI coding agents.
- Added `docs/architecture.md` outlining decoupled components, schemas, and WaveSurfer timeline sync hooks.
- Added Architectural Decision Records (ADRs) under `docs/adr/` for Streamlit-to-FastAPI migration, Dual-Pipeline design, and programmatic slide indexing.

---

## [1.1.3] - 2026-06-26
### Changed
- Added `.reasonix/` to `.gitignore` to prevent local IDE state files from entering git tracking.

## [1.1.2] - 2026-06-26
### Refactored
- Simplified logging thread initialization and console startup routine in `run.py`.

## [1.1.1] - 2026-06-25
### Changed
- Added `.agents` directory to `.gitignore`.

## [1.1.0] - 2026-06-25
### Added
- Implemented deliberate visual delays and a red diagnostic theme in the UI for failed model fallback swaps.

---

## [1.0.0] - 2026-06-23
### Added (Major Release)
- **Decoupled Architecture**: Migrated from a monolithic synchronous Streamlit application to a decoupled **FastAPI backend** and **React SPA frontend**.
- Implemented stateful WebSockets (`/api/pipeline/run`) for streaming alignment telemetry logs.
- Added a thread-safe, early-cancelable `PipelineJob` executor controlled via threading events.
- Created Vite reverse proxy setups to serve rendered PDF slide images and stream media assets natively.

---

## [0.7.1-legacy] - 2026-06-20
### Added
- Introduced the frontend "Follow Mode" studio timeline engine.

## [0.7.0] - 2026-06-20
### Removed
- Cleaned up obsolete timeline bridge Python integration scripts.

## [0.6.0] - 2026-06-17
### Added
- Implemented an invisible registry model and fast-boot architecture for rapid server warm-ups.

## [0.5.0] - 2026-06-16
### Added (Major Release)
- **Dual-Pipeline Support**: Introduced the visual pipeline leveraging deterministic Computer Vision to match video frames to slides.
- Configured **SSIM (Structural Similarity Index)** for keyframe transition/scene-cut detection.
- Configured **ORB & RANSAC** for pixel-accurate slide-to-frame matching.

---

## [0.4.0] - 2026-06-13
### Added
- Added React SPA routing, modal configuration dialogs, and processing step tracking elements.

## [0.3.0] - 2026-06-06
### Added
- Implemented the core configuration engine (`config.yaml`), storage serialization library, and transient memory handlers.

## [0.2.1] - 2026-06-06
### Added
- Bypassed temporary folders for media uploads and enabled direct streaming of MP4 assets in the timeline interface.

## [0.2.0] - 2026-06-06
### Refactored
- Structured the LLM API layer around **Provider Isolation (Facade Pattern)** to support the new Google Generative AI SDK architecture.

---

## [0.1.4] - 2026-06-06
### Added
- Implemented tier-aware model listings to prevent rate-limit failures for free tier keys.

## [0.1.3] - 2026-06-06
### Refactored
- Patched deprecated Streamlit widgets to clean console warnings.

## [0.1.2] - 2026-06-06
### Added
- Configured overlapping chunk context and UUID session serialization.

## [0.1.1] - 2026-06-06
### Added
- Implemented semantic audio segment chunking and proactive pacing controls.

## [0.1.0] - 2026-06-06
### Added
- Initial repository setup, module documentation, and basic Streamlit alignment prototype.
