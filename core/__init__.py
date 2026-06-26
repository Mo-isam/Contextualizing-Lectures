"""
core
====
Decoupled backend processing module for the Contextualizing Lectures pipeline.

Contains all heavy execution logic — Computer Vision estimators, OCR engines,
Whisper audio transcribers, LLM alignment, and the thread-safe cancelable job
scheduler. Every module in this package is 100% UI-agnostic (no Streamlit, no
FastAPI, no frontend imports) and communicates via standard Python logging and
optional callback functions.
"""
