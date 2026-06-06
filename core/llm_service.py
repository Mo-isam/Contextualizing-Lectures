"""
llm_service.py
--------------
Centralized service for handling all Gemini API interactions.
Manages proactive RPM pacing, fallback rate limiting (429 parsing), 
safety filter exceptions, model hot-swapping, and retry loops.
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


# ── Configuration & Discovery ──────────────────────────────────────────────────
GEMINI_MODEL_PRIORITY = [
    "gemini-3.5-flash",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemma-4-31b-it",
    "gemma-4-26b-a4b-it",
]

DEFAULT_MODEL_OPTIONS = {
    "Auto (try all, best quota)"                : "",
    "Gemini 3.5 Flash ✦ Latest"                 : "gemini-3.5-flash",
    "Gemini 3.1 Flash Lite ✦ Fast"              : "gemini-3.1-flash-lite",
    "Gemini 3.0 Flash Preview"                  : "gemini-3-flash-preview",
    "Gemini 2.5 Flash ✦ Stable"                 : "gemini-2.5-flash",
    "Gemini 2.5 Flash Lite"                     : "gemini-2.5-flash-lite",
    "Gemma 4 (31B) ✦ Open Weights"              : "gemma-4-31b-it",
    "Gemma 4 (26B A4B) ✦ Optimized"             : "gemma-4-26b-a4b-it",
}

def discover_available_models(api_key: str) -> list[str]:
    """Dynamically discover all models available for the provided API key."""
    if not GENAI_AVAILABLE:
        return []
    if not api_key or not api_key.strip():
        return []
    try:
        genai.configure(api_key=api_key.strip())
        available = []
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                name = m.name
                if name.startswith("models/"):
                    name = name[7:]
                available.append(name)
        return available
    except Exception as e:
        logger.error(f"Error discovering Gemini models: {e}")
        return []


# ── Custom Exceptions ──────────────────────────────────────────────────────────

class SafetyFilterError(Exception):
    """Raised when the AI blocks the prompt due to copyright or safety filters."""
    pass

class AllModelsFailedError(Exception):
    """Raised when all models in the fallback list exhaust their retries."""
    pass


# ── Global State for Proactive Rate Limiting ─────────────────────────────────
# Dictionary to track pacing per individual API key
_last_call_times = {}

# Free tier limits (2026 guidelines)
MODEL_RPM_LIMITS = {
    "gemini-3.5-flash": 15,
    "gemini-3.1-flash-lite": 30,
    "gemini-3-flash-preview": 15,
    "gemini-2.5-flash": 15,
    "gemini-2.5-flash-lite": 30,
    "default": 15
}

def _apply_proactive_pacing(api_key: str, model_id: str, is_paid: bool, progress_cb, progress_idx: float):
    """Pace requests perfectly to avoid hitting 429 errors entirely."""
    if is_paid:
        return
        
    global _last_call_times
    key_hash = hash(api_key)
    
    rpm = MODEL_RPM_LIMITS.get(model_id, MODEL_RPM_LIMITS["default"])
    if rpm <= 0:
        return
        
    required_interval = 60.0 / rpm
    last_call = _last_call_times.get(key_hash, 0.0)
    elapsed = time.time() - last_call
    sleep_time = required_interval - elapsed
    
    if sleep_time > 0:
        if progress_cb and sleep_time > 1.0:
            # Yield to Streamlit UI with 1-second ticks
            for sec in range(int(sleep_time), 0, -1):
                progress_cb(progress_idx, f"⏳ Pacing API to maintain {rpm} RPM ({sec}s)...")
                time.sleep(1)
            time.sleep(sleep_time - int(sleep_time)) # Sleep remainder
        else:
            time.sleep(sleep_time)
        
    _last_call_times[key_hash] = time.time()


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


# ── Cloud File Management ──────────────────────────────────────────────────────

def upload_and_wait_for_file(file_path: str, api_key: str, timeout: int = 300):
    """Uploads a file to the GenAI cloud and waits for it to become ACTIVE."""
    if not GENAI_AVAILABLE:
        raise ImportError("google-generativeai is not installed.")
    genai.configure(api_key=api_key.strip())
    
    gemini_file = genai.upload_file(file_path)
    wait_start = time.time()
    while gemini_file.state.name == "PROCESSING":
        if time.time() - wait_start > timeout:
            raise TimeoutError(f"Cloud API timed out processing file after {timeout} seconds.")
        time.sleep(2)
        gemini_file = genai.get_file(gemini_file.name)
    return gemini_file

def delete_cloud_file(file_name: str, api_key: str):
    """Deletes a file from the GenAI cloud."""
    if not GENAI_AVAILABLE:
        return
    genai.configure(api_key=api_key.strip())
    try:
        genai.delete_file(file_name)
    except Exception as e:
        logger.warning(f"Failed to delete cloud file {file_name}: {e}")

# ── Core Generation Function ───────────────────────────────────────────────────

def generate_content_with_fallback(
    contents: list,
    models_to_try: list[str],
    api_key: str,
    schema: dict = None,
    temperature: float = 0.0,
    is_paid: bool = False,
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

    genai.configure(api_key=api_key.strip())
    
    gen_config = None
    if schema is not None:
        gen_config = genai.GenerationConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema
        )

    for model_id in models_to_try:
        model = genai.GenerativeModel(model_id)
        
        for attempt in range(1, max_retries + 1):
            _apply_proactive_pacing(api_key, model_id, is_paid, progress_cb, progress_idx)
            
            try:
                response = model.generate_content(contents, generation_config=gen_config)
                # Accessing .text triggers the parsing; if blocked, it throws an exception here
                raw_text = response.text.strip()
                # Defensively strip Markdown code blocks that Gemini sometimes wraps JSON in
                clean_text = re.sub(r"^```(?:json)?\n?", "", raw_text, flags=re.IGNORECASE)
                clean_text = re.sub(r"\n?```$", "", clean_text)
                return clean_text.strip()

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