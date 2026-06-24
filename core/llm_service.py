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
    from google import genai
    from google.genai import types
    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False


from core.config import app_config

# ── Configuration & Discovery ──────────────────────────────────────────────────
GEMINI_MODEL_PRIORITY = app_config.get("llm", "model_priority", [
    "gemini-3.5-flash" # Fallback if yaml is missing
])

DEFAULT_MODEL_OPTIONS = app_config.get("llm", "model_options", {
    "Auto (try all, best quota)": "" # Fallback if yaml is missing
})

def discover_available_models(api_key: str) -> list[str]:
    """Dynamically discover all models available for the provided API key."""
    if not GENAI_AVAILABLE or not api_key.strip():
        return []
    try:
        client = genai.Client(api_key=api_key.strip())
        available = []
        for m in client.models.list():
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
# Set to permanently blacklist models that hit daily quota limits during a run
_dead_models = set()
# Dictionary to track cumulative API call success and failure counts per model ID
_model_call_stats = {}

# Free tier limits (2026 guidelines) populated from config
MODEL_RPM_LIMITS = app_config.get("llm", "rpm_limits", {"default": 15})

def _apply_proactive_pacing(api_key: str, model_id: str, is_paid: bool, progress_cb, progress_idx: float):
    """Pace requests perfectly to avoid hitting 429 errors entirely."""
    if is_paid:
        return
        
    global _last_call_times, _dead_models, _model_call_stats
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
            # Yield to progress callback (WebSockets) with 1-second ticks
            for sec in range(int(sleep_time), 0, -1):
                progress_cb(
                    progress_idx, 
                    f"⏳ Pacing API to maintain {rpm} RPM ({sec}s)...",
                    active_model=model_id,
                    model_status="active",
                    model_message=f"Pacing API to maintain {rpm} RPM ({sec}s remaining)",
                    dead_models=list(_dead_models),
                    model_call_stats=dict(_model_call_stats)
                )
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
    # Google's backend format changes (e.g., limit: 0 vs limit: 20).
    # The mere presence of GenerateRequestsPerDay indicates the daily bucket is empty.
    return "GenerateRequestsPerDay" in exc_str


# ── Cloud File Management ──────────────────────────────────────────────────────

def upload_and_wait_for_file(file_path: str, api_key: str, timeout: int = 300):
    """Uploads a file to the GenAI cloud and waits for it to become ACTIVE."""
    if not GENAI_AVAILABLE:
        raise ImportError("google-genai is not installed.")
    
    client = genai.Client(api_key=api_key.strip())
    gemini_file = client.files.upload(file=file_path)
    
    wait_start = time.time()
    # The new SDK state can be an enum or a string. We handle both dynamically.
    def _is_processing(f):
        state = getattr(f, "state", "")
        name = getattr(state, "name", state)
        return str(name).upper() == "PROCESSING"

    while _is_processing(gemini_file):
        if time.time() - wait_start > timeout:
            raise TimeoutError(f"Cloud API timed out processing file after {timeout} seconds.")
        time.sleep(2)
        gemini_file = client.files.get(name=gemini_file.name)
    return gemini_file

def delete_cloud_file(file_name: str, api_key: str):
    """Deletes a file from the GenAI cloud."""
    if not GENAI_AVAILABLE:
        return
    client = genai.Client(api_key=api_key.strip())
    try:
        client.files.delete(name=file_name)
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
        raise ImportError("google-genai is not installed.")

    client = genai.Client(api_key=api_key.strip())
    
    gen_config = None
    if schema is not None:
        gen_config = types.GenerateContentConfig(
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=schema
        )

    global _dead_models, _model_call_stats
    
    # Initialize stats for any unseen model in the priority list
    for m in models_to_try:
        _model_call_stats.setdefault(m, {"success": 0, "failure": 0})
    
    for model_id in models_to_try:
        if model_id in _dead_models:
            continue  # Skip this model for the rest of the session; it's dead.
            
        for attempt in range(1, max_retries + 1):
            if progress_cb:
                progress_cb(
                    progress_idx,
                    f"🤖 Querying {model_id} (Attempt {attempt})...",
                    active_model=model_id,
                    model_status="active",
                    model_message=f"Querying {model_id} (Attempt {attempt} of {max_retries})",
                    dead_models=list(_dead_models),
                    model_call_stats=dict(_model_call_stats)
                )
            
            _apply_proactive_pacing(api_key, model_id, is_paid, progress_cb, progress_idx)
            
            try:
                response = client.models.generate_content(
                    model=model_id, 
                    contents=contents, 
                    config=gen_config
                )
                
                # New SDK returns None for .text if the output is blocked by safety filters
                if response.text is None:
                    raise ValueError("Safety filter tripped: response.text is None.")

                raw_text = response.text.strip()
                # Defensively strip Markdown code blocks that Gemini sometimes wraps JSON in
                clean_text = re.sub(r"^```(?:json)?\n?", "", raw_text, flags=re.IGNORECASE)
                clean_text = re.sub(r"\n?```$", "", clean_text)
                
                # Increment success count
                _model_call_stats[model_id]["success"] += 1
                
                # Report successful completion and reset status to idle
                if progress_cb:
                    progress_cb(
                        progress_idx,
                        f"✓ Response received from {model_id}",
                        active_model=model_id,
                        model_status=None,
                        model_message=None,
                        dead_models=list(_dead_models),
                        model_call_stats=dict(_model_call_stats)
                    )
                return clean_text.strip()

            except Exception as exc:
                # Increment failure count
                _model_call_stats[model_id]["failure"] += 1
                exc_str = str(exc)
                
                # 1. Blocked by Copyright / Safety
                if "finish_reason" in exc_str or "valid Part" in exc_str or "safety" in exc_str.lower():
                    msg = f"⚠️ {log_context} blocked by AI Safety filter."
                    logger.warning(msg)
                    if progress_cb:
                        progress_cb(
                            progress_idx,
                            msg,
                            active_model=model_id,
                            model_status="warning",
                            model_message="Blocked by AI Safety filter",
                            dead_models=list(_dead_models),
                            model_call_stats=dict(_model_call_stats)
                        )
                    raise SafetyFilterError(msg)
                    
                # 2. Hard Quota Exhausted or Model Not Found
                if is_quota_exhausted(exc_str) or "404" in exc_str:
                    msg = f"⚠️ Model {model_id} exhausted/unavailable on {log_context}. Swapping models..."
                    logger.warning(msg)
                    _dead_models.add(model_id)  # Blacklist it permanently for this run
                    if progress_cb:
                        progress_cb(
                            progress_idx,
                            msg,
                            active_model=model_id,
                            model_status="error",
                            model_message="Hard quota limit hit. Swapping...",
                            dead_models=list(_dead_models),
                            model_call_stats=dict(_model_call_stats)
                        )
                        time.sleep(2)  # Give the UI time to show the error state before swapping
                    break  # Break attempt loop, move to next model in models_to_try
                    
                # 3. Rate Limit (429), Overload (503), or Transient Error
                if "429" in exc_str:
                    wait = min(extract_retry_delay(exc_str), max_wait_sec)
                    msg = f"⏳ [{model_id}] rate limited on {log_context}. Waiting {wait}s..."
                    model_status = "warning"
                    model_message_base = f"Rate limited (429). Retrying in {wait}s"
                elif "503" in exc_str:
                    wait = min(15 + (attempt * 5), max_wait_sec)
                    msg = f"⚠️ [{model_id}] overloaded (503) on {log_context}. Retrying attempt {attempt} in {wait}s..."
                    model_status = "warning"
                    model_message_base = f"Server overloaded (503). Retrying in {wait}s"
                else:
                    wait = min(15 + (attempt * 5), max_wait_sec)
                    msg = f"⚠️ [{model_id}] attempt {attempt} failed on {log_context}: {exc_str[:40]}... Retrying in {wait}s..."
                    model_status = "warning"
                    model_message_base = f"Request failed. Retrying in {wait}s"
                
                logger.warning(msg)
                if progress_cb:
                    for sec in range(wait, 0, -1):
                        progress_cb(
                            progress_idx,
                            f"{msg} ({sec}s...)",
                            active_model=model_id,
                            model_status=model_status,
                            model_message=f"{model_message_base} ({sec}s remaining)",
                            dead_models=list(_dead_models),
                            model_call_stats=dict(_model_call_stats)
                        )
                        time.sleep(1)
                else:
                    time.sleep(wait)
        else:
            # Executed if the attempt loop completed fully without hitting 'break'
            msg = f"⚠️ Model {model_id} failed after {max_retries} attempts on {log_context}. Swapping to next available model..."
            logger.warning(msg)
            _dead_models.add(model_id)
            if progress_cb:
                progress_cb(
                    progress_idx,
                    msg,
                    active_model=model_id,
                    model_status="error",
                    model_message="Model failed all retries. Swapping...",
                    dead_models=list(_dead_models),
                    model_call_stats=dict(_model_call_stats)
                )
 
    # If we exit the loops, it means all models failed
    error_msg = f"❌ All models failed for {log_context}."
    logger.error(error_msg)
    if progress_cb:
        progress_cb(
            progress_idx,
            error_msg,
            active_model=None,
            model_status="error",
            model_message="All models exhausted.",
            dead_models=list(_dead_models),
            model_call_stats=dict(_model_call_stats)
        )
    raise AllModelsFailedError(error_msg)