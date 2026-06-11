"""
video_aligner_test.py
---------------------
Standalone script to test the Visual-Audio Fusion Pipeline.
"""

import sys
import os
# Inject the root project directory into Python's path so 'core' imports work
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2
import logging
from skimage.metrics import structural_similarity as ssim

from core.config import app_config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants from config
FPS_SAMPLE_RATE = app_config.get("video", "frame_sample_rate", 1)
SSIM_THRESHOLD = app_config.get("video", "ssim_threshold", 0.85)


def extract_and_detect_transitions(video_path: str, output_dir: str) -> list[dict]:
    """
    Phase 1 & Phase 2 combined: 
    Reads video at specified FPS, compares frames using SSIM, 
    and saves only the keyframes where the slide actually changes.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    frame_interval = int(video_fps / FPS_SAMPLE_RATE)
    
    logger.info(f"Video FPS: {video_fps}. Sampling every {frame_interval} frames.")

    keyframes = []
    prev_gray = None
    frame_count = 0
    chapter_start_sec = 0.0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        # Only process 1 frame per second
        if frame_count % frame_interval == 0:
            current_sec = frame_count / video_fps
            
            # Convert to grayscale for SSIM comparison
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
            # If this is the very first frame, it's our first chapter keyframe
            if prev_gray is None:
                keyframe_path = os.path.join(output_dir, f"keyframe_{int(current_sec):04d}s.jpg")
                cv2.imwrite(keyframe_path, frame)
                keyframes.append({
                    "start_time": current_sec,
                    "end_time": None, # Will be updated when the next cut happens
                    "keyframe_path": keyframe_path
                })
                prev_gray = gray
            else:
                # Compare current frame to previous frame
                score, _ = ssim(prev_gray, gray, full=True)
                
                # If the score drops below threshold, we have a slide transition!
                if score < SSIM_THRESHOLD:
                    logger.info(f"Transition detected at {current_sec:.2f}s (SSIM: {score:.3f})")
                    
                    # Close the previous chapter
                    keyframes[-1]["end_time"] = current_sec
                    
                    # Start new chapter
                    keyframe_path = os.path.join(output_dir, f"keyframe_{int(current_sec):04d}s.jpg")
                    cv2.imwrite(keyframe_path, frame)
                    keyframes.append({
                        "start_time": current_sec,
                        "end_time": None,
                        "keyframe_path": keyframe_path
                    })
                    
                    # Update our reference frame to the new slide
                    prev_gray = gray
                    
        frame_count += 1

    # Close the very last chapter with the end of the video
    if keyframes:
        total_duration = frame_count / video_fps
        keyframes[-1]["end_time"] = total_duration

    cap.release()
    logger.info(f"Found {len(keyframes)} unique visual chapters.")
    return keyframes


# ── Phase 3: Slide Matching ──────────────────────────────────────────

def _get_orb_matches(des1, des2):
    """Calculate the number of good feature matches between two images using ORB."""
    if des1 is None or des2 is None or len(des1) == 0 or len(des2) == 0:
        return 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = bf.match(des1, des2)
    # Filter by distance to keep only high-quality matches
    good_matches = [m for m in matches if m.distance < 50]
    return len(good_matches)


def match_keyframes_to_slides(keyframes: list[dict], slide_images: list[str], slides_text: str, api_key: str = "") -> list[dict]:
    """
    Compares keyframe images to PDF slide images.
    Implements Expanding Radius Search (CV) and optional AI Fallback.
    """
    import json
    from PIL import Image
    from core.llm_service import generate_content_with_fallback
    
    strategy = app_config.get("video", "matching_strategy", "hybrid")
    logger.info(f"Starting slide matching using strategy: '{strategy}'")
    
    MIN_MATCH_COUNT = 25 # Threshold for a confident ORB match
    
    # 1. Pre-compute ORB features for all PDF slides if using CV
    slide_descriptors = []
    if strategy in ["cv", "hybrid"]:
        orb = cv2.ORB_create(nfeatures=2000)
        for img_path in slide_images:
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                _, des = orb.detectAndCompute(img, None)
                slide_descriptors.append(des)
            else:
                slide_descriptors.append(None)
                
    last_matched_idx = 0 # Start at Slide 1 (index 0)
    
    for kf in keyframes:
        kf_path = kf["keyframe_path"]
        matched_slide_num = None
        
        # --- STRATEGY: CV or HYBRID ---
        if strategy in ["cv", "hybrid"]:
            kf_img = cv2.imread(kf_path, cv2.IMREAD_GRAYSCALE)
            _, kf_des = orb.detectAndCompute(kf_img, None)
            
            # Tier 1: Expanding Radius (Current, Next, Previous)
            tier_1_indices = [
                last_matched_idx, 
                min(last_matched_idx + 1, len(slide_descriptors) - 1),
                max(last_matched_idx - 1, 0)
            ]
            tier_1_indices = list(set(tier_1_indices)) # Remove duplicates
            
            best_match_count = -1
            best_idx = -1
            
            for idx in tier_1_indices:
                matches = _get_orb_matches(kf_des, slide_descriptors[idx])
                if matches > best_match_count:
                    best_match_count = matches
                    best_idx = idx
            
            if best_match_count >= MIN_MATCH_COUNT:
                matched_slide_num = best_idx + 1
                logger.info(f"CV Tier 1 Match: Keyframe {kf_path} -> Slide {matched_slide_num} ({best_match_count} matches)")
            else:
                # Tier 2: Full Search (Check all other slides)
                logger.info(f"CV Tier 1 failed for {kf_path}. Executing Tier 2 Full Search...")
                for idx in range(len(slide_descriptors)):
                    if idx in tier_1_indices: continue # Skip already checked
                    matches = _get_orb_matches(kf_des, slide_descriptors[idx])
                    if matches > best_match_count:
                        best_match_count = matches
                        best_idx = idx
                
                if best_match_count >= MIN_MATCH_COUNT:
                    matched_slide_num = best_idx + 1
                    logger.info(f"CV Tier 2 Match: Keyframe {kf_path} -> Slide {matched_slide_num} ({best_match_count} matches)")
        
        # --- STRATEGY: AI FALLBACK or PURE AI ---
        if matched_slide_num is None:
            if strategy == "cv":
                # Strict CV mode: if it fails, map to 0 (General)
                matched_slide_num = 0
                logger.warning(f"CV failed for {kf_path}. Strict CV mode mapping to Slide 0.")
            elif strategy in ["hybrid", "ai"]:
                if not api_key:
                    logger.error("API Key missing! Cannot run AI matching. Defaulting to Slide 0.")
                    matched_slide_num = 0
                else:
                    logger.info(f"Triggering AI Matching for {kf_path}...")
                    schema = {
                        "type": "OBJECT",
                        "properties": {"slide_number": {"type": "INTEGER"}},
                        "required": ["slide_number"]
                    }
                    prompt = (
                        "You are an OCR and matching assistant. Look at this video frame. "
                        f"Here is the text array of our presentation: \n\n{slides_text}\n\n"
                        "Does the text/visual in the video frame match any of these slides? "
                        "If yes, return the slide_number. If the video frame shows a web browser, "
                        "a person, or something entirely unrelated to the presentation, return 0."
                    )
                    
                    try:
                        img_obj = Image.open(kf_path)
                        response_text = generate_content_with_fallback(
                            contents=[prompt, img_obj],
                            models_to_try=["gemini-2.5-flash", "gemini-3.5-flash"],
                            api_key=api_key,
                            schema=schema,
                            max_retries=2
                        )
                        data = json.loads(response_text)
                        matched_slide_num = data.get("slide_number", 0)
                        logger.info(f"AI Match: Keyframe {kf_path} -> Slide {matched_slide_num}")
                    except Exception as e:
                        logger.error(f"AI Fallback failed for {kf_path}: {e}")
                        matched_slide_num = 0
        
        # Save result
        kf["matched_slide"] = matched_slide_num
        if matched_slide_num > 0:
            last_matched_idx = matched_slide_num - 1 # Update radius center
            
    return keyframes


if __name__ == "__main__":
    # --- TESTING PLAYGROUND ---
    # To test this, place a short lecture video in your root folder
    # named 'test_video.mp4' and run this script directly.
    
    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    TEST_VIDEO = os.path.join(ROOT_DIR, "test_video.mp4")
    TEST_OUT_DIR = os.path.join(ROOT_DIR, "data_storage", "tmp", "video_test_frames")
    
    if os.path.exists(TEST_VIDEO):
        chapters = extract_and_detect_transitions(TEST_VIDEO, TEST_OUT_DIR)
        for idx, chap in enumerate(chapters):
            print(f"Chapter {idx+1}: {chap['start_time']:.1f}s -> {chap['end_time']:.1f}s | File: {chap['keyframe_path']}")
    else:
        logger.warning(f"No test video found at {TEST_VIDEO}. Please add one to test Phase 1 & 2.")