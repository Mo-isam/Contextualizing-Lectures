"""
models.py
---------
Data transfer objects (DTOs) for the application.
Enforces strict typing and data contracts across UI, storage, and processors.
"""
from dataclasses import dataclass

@dataclass
class TranscriptSegment:
    """Represents a single chunk of spoken audio with timestamps."""
    id: int
    start: float
    end: float
    text: str


@dataclass
class Slide:
    """Represents a single page from a presentation."""
    page_number: int
    title: str
    text: str


@dataclass
class AlignedNote:
    """Represents the final mapping of spoken audio to a specific slide."""
    slide_number: int
    slide_title: str
    exact_transcript: str
    ai_insight: str
    timestamp_start: float
    timestamp_end: float


@dataclass
class LectureSession:
    """Strict data contract for saving and loading lecture state, decoupling UI from backend."""
    session_name: str
    pdf_path: str | None
    media_path: str | None
    transcript_segments: list[TranscriptSegment] | None
    slides: list[Slide] | None
    final_output: list[AlignedNote] | None
    session_description: str | None = None
    session_id: str | None = None
    timestamp: float = 0.0