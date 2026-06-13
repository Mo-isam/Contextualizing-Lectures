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
import numpy as np
from skimage.metrics import structural_similarity as ssim

from core.config import app_config

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

# Constants from config
FPS_SAMPLE_RATE = app_config.get("video", "frame_sample_rate", 1)
SSIM_THRESHOLD = app_config.get("video", "ssim_threshold", 0.90) # Increased sensitivity


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
            
            # Convert to grayscale and apply Gaussian Blur to melt away noise/mouse movements
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_blurred = cv2.GaussianBlur(gray, (11, 11), 0)
            
            # If this is the very first frame, it's our first chapter keyframe
            if prev_gray is None:
                keyframe_path = os.path.join(output_dir, f"keyframe_{int(current_sec):04d}s.jpg")
                cv2.imwrite(keyframe_path, frame)
                keyframes.append({
                    "start_time": current_sec,
                    "end_time": None, # Will be updated when the next cut happens
                    "keyframe_path": keyframe_path
                })
                prev_gray = gray_blurred
            else:
                # Compare current blurred frame to previous blurred frame
                score, _ = ssim(prev_gray, gray_blurred, full=True)
                
                # If the score drops below threshold, we have a structural slide transition!
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
                    prev_gray = gray_blurred
                    
        frame_count += 1

    # Close the very last chapter with the end of the video
    if keyframes:
        total_duration = frame_count / video_fps
        keyframes[-1]["end_time"] = total_duration

    cap.release()
    logger.info(f"Found {len(keyframes)} unique visual chapters.")
    return keyframes


# ── Phase 3: Slide Matching ──────────────────────────────────────────

def _get_orb_matches(kp1, des1, kp2, des2):
    """Calculate spatially verified feature matches using Lowe's Ratio and RANSAC."""
    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return 0
        
    # Use k-Nearest Neighbors (k=2) instead of crossCheck
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des1, des2, k=2)
    
    # 1. Lowe's Ratio Test: Keep matches that are distinct and unambiguous
    good_matches = []
    for match_set in matches:
        if len(match_set) == 2:
            m, n = match_set
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
                
    # 2. Spatial Verification (RANSAC)
    if len(good_matches) < 10:
        return 0 # Not enough points to verify geometry
        
    src_pts = np.float32([ kp1[m.queryIdx].pt for m in good_matches ]).reshape(-1, 1, 2)
    dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good_matches ]).reshape(-1, 1, 2)
    
    # Find geometric transformation; mask contains the 'inliers' (points that physically align)
    _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    if mask is None:
        return 0
        
    # Return the count of points that survived spatial verification
    return int(np.sum(mask))


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
    
    # Lowered threshold because RANSAC inliers are highly accurate
    MIN_MATCH_COUNT = 15 
    
    # 1. Pre-compute ORB features (keypoints AND descriptors) for all PDF slides
    slide_features = []
    if strategy in ["cv", "hybrid"]:
        # Increased feature count to give ORB more data to work with
        orb = cv2.ORB_create(nfeatures=5000)
        for img_path in slide_images:
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                kp, des = orb.detectAndCompute(img, None)
                slide_features.append({"kp": kp, "des": des})
            else:
                slide_features.append(None)
                
    last_matched_idx = 0 # Start at Slide 1 (index 0)
    
    for kf in keyframes:
        kf_path = kf["keyframe_path"]
        matched_slide_num = None
        
        # --- STRATEGY: CV or HYBRID ---
        if strategy in ["cv", "hybrid"]:
            kf_img = cv2.imread(kf_path, cv2.IMREAD_GRAYSCALE)
            kf_kp, kf_des = orb.detectAndCompute(kf_img, None)
            
            match_scores = []
            
            # BRUTE FORCE: Score against all slides
            for idx in range(len(slide_features)):
                sf = slide_features[idx]
                if sf is None or sf["des"] is None:
                    match_scores.append((idx, 0))
                    continue
                    
                matches = _get_orb_matches(kf_kp, kf_des, sf["kp"], sf["des"])
                match_scores.append((idx, matches))
                
            # Sort scores highest to lowest to find 1st and 2nd place
            match_scores.sort(key=lambda x: x[1], reverse=True)
            
            best_idx, best_score = match_scores[0]
            runner_up_score = match_scores[1][1] if len(match_scores) > 1 else 0
            
            # RELATIVE CONFIDENCE LOGIC
            is_confident_match = False
            
            # Rule 1: High absolute match (e.g., full text slide)
            if best_score >= 15:
                is_confident_match = True
            # Rule 2: Sparse slide (e.g., 1 bullet point), but massive lead over 2nd place (ratio test)
            elif best_score >= 5 and best_score >= (runner_up_score * 1.5):
                is_confident_match = True
                
            if is_confident_match:
                matched_slide_num = best_idx + 1
                logger.info(f"CV Match: Keyframe {os.path.basename(kf_path)} -> Slide {matched_slide_num} (Score: {best_score}, Runner-up: {runner_up_score})")
            else:
                logger.warning(f"CV Failed for {os.path.basename(kf_path)}. Score: {best_score}, Runner-up: {runner_up_score}.")
        
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


# ── Phase 4 & 5: Deterministic Fusion & AI Insights ──────────────────

def fuse_audio_and_video(
    segments: list, 
    keyframes: list[dict], 
    slides: list, 
    api_key: str = ""
) -> list:
    """
    Phase 4: Mathematically aligns audio segments to visual chapters using midpoints.
    Phase 5: Generates a single AI insight per slide block.
    Returns a list of AlignedNote objects.
    """
    from core.models import AlignedNote
    from core.llm_service import generate_content_with_fallback
    import json

    logger.info("Starting deterministic Audio-Visual Fusion...")
    
    # 1. Assign each segment to a slide based on its temporal midpoint
    blocks = []
    current_block = {"slide_number": -1, "segments": []}
    
    for seg in segments:
        midpoint = (seg.start + seg.end) / 2.0
        
        # Find which keyframe chapter this midpoint falls into
        matched_slide = 0 # Default to General
        for kf in keyframes:
            if kf["start_time"] <= midpoint <= kf["end_time"]:
                matched_slide = kf["matched_slide"]
                break
        
        # If the slide changed, start a new block
        if matched_slide != current_block["slide_number"]:
            if current_block["segments"]:
                blocks.append(current_block)
            current_block = {"slide_number": matched_slide, "segments": [seg]}
        else:
            current_block["segments"].append(seg)
            
    if current_block["segments"]:
        blocks.append(current_block)

    # 2. Build final notes and generate AI Insights
    final_notes = []
    slide_dict = {s.page_number: s for s in slides}
    
    for block in blocks:
        s_num = block["slide_number"]
        block_segs = block["segments"]
        
        t_start = block_segs[0].start
        t_end = block_segs[-1].end
        exact_transcript = " ".join([s.text for s in block_segs]).strip()
        
        slide_title = slide_dict[s_num].title if s_num in slide_dict else "General / Off-topic"
        slide_text = slide_dict[s_num].text if s_num in slide_dict else ""
        
        ai_insight = ""
        # Only call AI if we have transcript text and an API key
        if api_key and exact_transcript and s_num > 0:
            logger.info(f"Generating AI Insight for Slide {s_num}...")
            schema = {
                "type": "OBJECT",
                "properties": {"ai_insight": {"type": "STRING"}},
                "required": ["ai_insight"]
            }
            prompt = (
                "You are a lecture assistant. Compare the SLIDE TEXT to the PROFESSOR TRANSCRIPT.\n"
                "Summarize any important points the professor said that are NOT written on the slide.\n"
                "Keep it to 1-2 concise sentences. If the professor just read the slide exactly, output an empty string.\n\n"
                f"--- SLIDE TEXT ---\n{slide_text}\n\n"
                f"--- PROFESSOR TRANSCRIPT ---\n{exact_transcript}"
            )
            try:
                response = generate_content_with_fallback(
                    contents=[prompt],
                    models_to_try=["gemini-2.5-flash", "gemini-3.5-flash"],
                    api_key=api_key,
                    schema=schema,
                    max_retries=2
                )
                ai_insight = json.loads(response).get("ai_insight", "").strip()
            except Exception as e:
                logger.error(f"Failed to generate insight for slide {s_num}: {e}")
                
        final_notes.append(AlignedNote(
            slide_number=s_num,
            slide_title=slide_title,
            exact_transcript=exact_transcript,
            ai_insight=ai_insight,
            timestamp_start=t_start,
            timestamp_end=t_end
        ))
        
    logger.info(f"Fusion complete. Generated {len(final_notes)} aligned notes.")
    return final_notes


if __name__ == "__main__":
    # --- TESTING PLAYGROUND ---
    # Instructions:
    # 1. Place 'test_video.mp4' and 'test_presentation.pdf' in your root folder.
    # 2. Add your GEMINI API KEY below to test the full hybrid matching + insights.
    
    API_KEY = "AIzaSyAiJJ1D_cypCnlrrQj0PmvM3ZSrNmMzmvU" # <-- PUT YOUR API KEY HERE FOR TESTING
    
    ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
    TEST_VIDEO = os.path.join(ROOT_DIR, "test_video.mp4")
    TEST_PDF = os.path.join(ROOT_DIR, "test_presentation.pdf")
    TEST_OUT_DIR = os.path.join(ROOT_DIR, "data_storage", "tmp", "video_test_frames")
    
    if os.path.exists(TEST_VIDEO) and os.path.exists(TEST_PDF):
        from core.pdf_processor import render_pdf_to_images, extract_slide_text, format_slides_for_prompt
        from core.audio_processor import process_media_file
        
        print("\n--- 1. PROCESSING PDF ---")
        slide_images = render_pdf_to_images(TEST_PDF, os.path.join(TEST_OUT_DIR, "pdf_images"))
        slides = extract_slide_text(TEST_PDF)
        slides_text = format_slides_for_prompt(slides)
        
        print("\n--- 2. EXTRACTING VIDEO FRAMES & DETECTING CUTS ---")
        chapters = extract_and_detect_transitions(TEST_VIDEO, TEST_OUT_DIR)
        
        print("\n--- 3. MATCHING KEYFRAMES TO SLIDES ---")
        chapters = match_keyframes_to_slides(chapters, slide_images, slides_text, api_key=API_KEY)
        for chap in chapters:
            print(f"[{chap['start_time']}s - {chap['end_time']}s] -> Slide {chap['matched_slide']}")
            
        print("\n--- 4. TRANSCRIBING AUDIO ---")
        print("⏭️ Skipped for CV testing phase.")
        # segments = process_media_file(TEST_VIDEO, temp_dir=TEST_OUT_DIR, engine="local")
        
        print("\n--- 5. FUSING PIPELINE ---")
        print("⏭️ Skipped for CV testing phase.")
        # notes = fuse_audio_and_video(segments, chapters, slides, api_key=API_KEY)
        
        print("\n--- FINAL OUTPUT ---")
        print("Done testing Phase 3.")
            
    else:
        logger.warning("Missing 'test_video.mp4' or 'test_presentation.pdf' in the root directory. Add them to run the full test.")