# ADR 0002: Dual-Pipeline Architecture (Audio vs. Video-Visual)

*   **Status**: Accepted
*   **Date**: 2026-06-16

---

## Context

Initially, the project only supported an **Audio-Only Alignment Pipeline**. The pipeline functioned by:
1.  Transcribing the lecture audio using Whisper.
2.  Grouping the transcript into semantic paragraphs (chunks).
3.  Sending the transcript chunks and the full text of all PDF slides to Google Gemini to "align" them semantically.

While this approach works for highly text-dense slides and scripted lectures, it suffers from major weaknesses:
*   **High API Costs**: Sending massive slide decks and transcript context windows to LLMs for every alignment operation incurs high API consumption.
*   **Hallucinations & Swapping**: If slides contain minimal text (e.g. diagrams, images, mathematical formulas) or share highly repetitive headers, the LLM struggles to align them correctly, leading to incorrect slide index jumps.
*   **Poor Temporal Accuracy**: LLMs cannot pinpoint pixel-perfect boundaries for exactly *when* a presenter flipped a slide.

---

## Decision

We introduced a **Dual-Pipeline Architecture** supporting two execution modes selectable by the user:

```text
                  ┌──────────────────────┐
                  │ User Media Upload    │
                  └──────────┬───────────┘
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
       [ Audio Pipeline ]            [ Visual Pipeline ]
       - Local Whisper Loader        - Local Whisper Loader
       - Semantic Aligner (LLM)      - CV SSIM Cut Detection (OpenCV)
                                     - ORB & RANSAC Matcher (OpenCV)
                                     - Temporal Fusion Aligner (LLM)
```

1.  **Audio-Only Pipeline**: Maintains the semantic alignment model for legacy support, audio files (MP3/WAV), or lectures without visible slides.
2.  **Video-Visual Pipeline**: Leverage deterministic local Computer Vision (CV) to track slide changes in MP4 files:
    *   **Transition Cut Detection**: Compare frames at a set rate using the **Structural Similarity Index (SSIM)** to detect exact cut timestamps.
    *   **Geometric Slide Matching**: Apply **ORB (Oriented FAST and Rotated BRIEF)** feature detection and **RANSAC (Random Sample Consensus)** filtering to map extracted video frames directly to rendered PDF slide images.
    *   **Temporal Fusion**: Feed the local CV transition boundaries and Whisper transcripts into the LLM as structured cues. The LLM only performs light semantic summarization and out-of-topic filtering, rather than raw alignment.

---

## Consequences

### Positive
*   **Drastic Hallucination Reduction**: Slide indices are pinned by local Computer Vision. The LLM cannot hallucinate slide transitions that did not occur on-screen.
*   **Millisecond Accuracy**: Slide jump boundaries match the exact frame transition in the video player.
*   **API Cost Control**: LLM prompts are shorter and more targeted, reducing token consumption.

### Neutral / Negative
*   **Local Hardware Requirements**: Requires OpenCV and NumPy libraries on the backend server. However, these libraries are lightweight and run efficiently on standard CPU architectures without needing a dedicated GPU.
