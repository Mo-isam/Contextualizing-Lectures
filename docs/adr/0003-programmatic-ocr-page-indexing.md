# ADR 0003: Programmatic OCR Slide Page Indexing

*   **Status**: Accepted
*   **Date**: 2026-06-25

---

## Context

During the PDF slide parsing phase, the system extracts text and generates images for each slide page.
*   **The Problem**:
    1.  If the LLM was asked to identify the slide's page number based on the slide's OCR text or visual contents, it frequently hallucinated. For example, if a slide discussed "Step 5 of the algorithm," the LLM might classify it as "Slide 5" even if it was actually page 3.
    2.  If the PDF had blank slides or slides containing only diagrams, the LLM might omit them, causing index gaps.
    3.  When using Gemini Structured Output schemas, returning out-of-bounds slide page numbers (or numbers that did not exist in the slide set) would fail validation, causing the pipeline job to reject the response and abort the run.

---

## Decision

We moved slide numbering entirely to a **Programmatic Assignment** model:
1.  During the PDF rendering phase ([render_pdf_to_images](file:///s:/WorkSpace/Git%20Workspace/AI%20Project/Contextualizing-Lectures/core/pdf_processor.py)), slide page numbers are assigned sequentially (1-based index) based on the actual page structure of the PDF file.
2.  During LLM alignment, the prompt is injected with the exact range of programmatically valid slide numbers (e.g. `1 to N`).
3.  On the backend, any LLM output that is out-of-bounds or non-numeric is coerced to `0` (representing "off-topic" or "no slide matched") instead of throwing a validation error.

---

## Consequences

### Positive
*   **Zero Validation Crashes**: Out-of-bounds slide indices are coerced to 0, ensuring that Pydantic validation checks consistently pass.
*   **Halts LLM Hallucinations**: Eliminates errors where numbers within slide headings or body text were misidentified as slide page numbers.
*   **Reliable UI Rendering**: The frontend timeline can guarantee that slide indices strictly map to the loaded array of rendered slide images.
