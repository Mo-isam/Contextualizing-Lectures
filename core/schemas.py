"""
schemas.py
----------
Pydantic request/response schemas for the REST API.
"""
from typing import List, Optional
from pydantic import BaseModel


class AlignedNoteSchema(BaseModel):
    slide_number: int
    slide_title: str
    exact_transcript: str
    timestamp_start: float
    timestamp_end: float
    ai_insight: str
    is_off_topic: bool = False


class SlideSchema(BaseModel):
    page_number: int
    title: str
    text: str


class TranscriptSegmentSchema(BaseModel):
    id: int
    start: float
    end: float
    text: str


class SaveSessionSchema(BaseModel):
    session_name: str
    session_description: str
    pdf_path: str
    media_path: str
    transcript_segments: List[TranscriptSegmentSchema]
    slides: List[SlideSchema]
    final_output: List[AlignedNoteSchema]
    pipeline_type: str = "audio"
    peaks: Optional[List[float]] = None
    session_id: Optional[str] = None


class UpdateMetadataSchema(BaseModel):
    session_name: str
    session_description: str


class ConfigUpdateSchema(BaseModel):
    is_paid_api: Optional[bool] = None
    default_model: Optional[str] = None
    pdf_engine: Optional[str] = None
    tx_engine: Optional[str] = None
    whisper_model_size: Optional[str] = None
    sample_rate: Optional[int] = None
    min_chunk_duration_sec: Optional[int] = None
    max_chunk_duration_sec: Optional[int] = None
    render_zoom: Optional[float] = None
    matching_strategy: Optional[str] = None
    frame_sample_rate: Optional[int] = None
    ssim_threshold: Optional[float] = None
    model_priority: Optional[List[str]] = None
