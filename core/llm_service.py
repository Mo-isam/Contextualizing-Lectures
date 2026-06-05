"""
llm_service.py
--------------
Centralized service for handling all Gemini API interactions.
Manages rate limiting (429 parsing), safety filter exceptions, 
model hot-swapping, and retry loops.
"""
import re
import time
import logging

logger = logging.getLogger(__name__)

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class SafetyFilterError(Exception):
    """Raised when the AI blocks the prompt due to copyright or safety filters."""
    pass

class AllModelsFailedError(Exception):
    """Raised when all models in the fallback list exhaust their retries."""
    pass


# ── Global State for Proactive Rate Limiting ─────────────────────────────────
_last_api_call_time = 0.0

# Free tier limits (can be adjusted for paid tiers)
MODEL_RPM_LIMITS = {
    "gemini-3.1-flash-lite": 30,
    "gemini-2.5-flash-lite": 30,
    "default": 15
}

def _apply_proactive_pacing(model_id: str, progress_cb, progress_idx: float):
    """Pace requests perfectly to avoid hitting 429 errors entirely."""
    global _last_api_call_time
    
    rpm = MODEL_RPM_LIMITS.get(model_id, MODEL_RPM_LIMITS["default"])
    required_interval = 60.0 / rpm
    
    elapsed = time.time() - _last_api_call_time
    sleep_time = required_interval - elapsed
    
    if sleep_time > 0:
        if progress_cb and sleep_time > 1.0:
            progress_cb(progress_idx, f"⏳ Pacing API to maintain {rpm} RPM ({sleep_time:.1f}s)...")
        time.sleep(sleep_time)
        
    _last_api_call_time = time.time()


# ── Helper Functions ───────────────────────────────────────────────────────────

def extract_retry_delay(exc_str: str, buffer_sec: int = 5) -> int:
    """Parse the retry delay (in seconds) from a 429 error message."""
    m = re.search(r"retry_delay\s*\{\s*seconds:\s*(\d+)", exc_str)
    if m: return int(m.group(1)) + buffer_sec

    m = re.search(r"retry in\s+([\d.]+)\s*s", exc_str, re.IGNORECASE)
    if m: return int(float(m.group(1))) + buffer_sec

    m = re.search(r"(\d{2,3})\s*second", exc_str, re.IGNORECASE)
    if m: return int(m.group(1)) + buffer_sec

    return 60  # Safe fallback


def is_quota_exhausted(exc_str: str) -> bool:
    """Check if the error is a hard daily quota exhaustion."""
    return "limit: 0" in exc_str and "GenerateRequestsPerDay" in exc_str


# ── Core Generation Function ───────────────────────────────────────────────────

def generate_content_with_fallback(
    contents: list,
    generation_config,
    models_to_try: list[str],
    log_context: str = "LLM request",
    progress_cb=None,
    progress_idx: float = 0.0,
    max_retries: int = 4,
    max_wait_sec: int = 120
) -> str:
    """
    Attempt to generate content using a priority list of models.
    Handles transient errors, rate limits, and safety filters automatically.
    
    Returns:
        The raw response text (usually a JSON string).
        
    Raises:
        SafetyFilterError: If the prompt is actively blocked.
        AllModelsFailedError: If all retries on all models fail.
    """
    if not GENAI_AVAILABLE:
        raise ImportError("google-generativeai is not installed.")

    for model_id in models_to_try:
        model = genai.GenerativeModel(model_id)
        
        for attempt in range(1, max_retries + 1):
            _apply_proactive_pacing(model_id, progress_cb, progress_idx)
            
            try:
                response = model.generate_content(contents, generation_config=generation_config)
                # Accessing .text triggers the parsing; if blocked, it throws an exception here
                return response.text

            except Exception as exc:
                exc_str = str(exc)
                
                # 1. Blocked by Copyright / Safety
                if "finish_reason" in exc_str or "valid Part" in exc_str or "safety" in exc_str.lower():
                    msg = f"⚠️ {log_context} blocked by AI Safety filter."
                    logger.warning(msg)
                    if progress_cb: progress_cb(progress_idx, msg)
                    raise SafetyFilterError(msg)
                    
                # 2. Hard Quota Exhausted or Model Not Found
                if is_quota_exhausted(exc_str) or "404" in exc_str:
                    msg = f"⚠️ Model {model_id} exhausted/unavailable. Swapping models..."
                    logger.warning(msg)
                    if progress_cb: progress_cb(progress_idx, msg)
                    break  # Break attempt loop, move to next model in models_to_try
                    
                # 3. Rate Limit (429) or Transient Error
                if "429" in exc_str:
                    wait = min(extract_retry_delay(exc_str), max_wait_sec)
                    msg = f"⏳ [{model_id}] rate limited. Waiting {wait}s..."
                else:
                    wait = min(15 + (attempt * 5), max_wait_sec)
                    msg = f"⚠️ [{model_id}] attempt {attempt} failed: {exc_str[:60]}... Retrying in {wait}s..."
                
                logger.warning(msg)
                if progress_cb:
                    for sec in range(wait, 0, -1):
                        progress_cb(progress_idx, f"{msg} ({sec}s...)")
                        time.sleep(1)
                else:
                    time.sleep(wait)

    # If we exit the loops, it means all models failed
    error_msg = f"❌ All models failed for {log_context}."
    logger.error(error_msg)
    if progress_cb: progress_cb(progress_idx, error_msg)
    raise AllModelsFailedError(error_msg)