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
    
    # Optional fallback for older saved JSON sessions
    spoken_notes: str = ""