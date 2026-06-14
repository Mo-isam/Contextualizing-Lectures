"""
video_processor.py
------------------
Handles the visual decomposition of video lectures.
Extracts frames, detects cuts using SSIM, and matches keyframes 
to PDF slides using ORB feature matching and Temporal Smoothing.
"""

import os
import cv2
import json
import logging
import numpy as np
from PIL import Image
from skimage.metrics import structural_similarity as ssim

from core.config import app_config
from core.llm_service import generate_content_with_fallback

logger = logging.getLogger(__name__)

# Constants from config
FPS_SAMPLE_RATE = app_config.get("video", "frame_sample_rate", 1)
SSIM_THRESHOLD = app_config.get("video", "ssim_threshold", 0.90)


def extract_and_detect_transitions(video_path: str, output_dir: str, progress_cb=None) -> list[dict]:
    """
    Reads video at specified FPS, compares frames using blurred SSIM, 
    and saves keyframes where structural layout changes occur.
    """
    os.makedirs(output_dir, exist_ok=True)
    
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Could not open video file: {video_path}")
        
    video_fps = cap.get(cv2.CAP_PROP_FPS)
    total_frames_approx = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_interval = int(video_fps / FPS_SAMPLE_RATE)
    
    logger.info(f"Video FPS: {video_fps}. Sampling every {frame_interval} frames.")

    keyframes = []
    prev_gray = None
    frame_count = 0
    
    while True:
        ret, frame = cap.read()
        if not ret:
            break
            
        if frame_count % frame_interval == 0:
            current_sec = frame_count / video_fps
            
            # Update UI Progress every 10 sampled frames
            if progress_cb and len(keyframes) % 10 == 0:
                pct = min(frame_count / max(total_frames_approx, 1), 1.0)
                progress_cb(pct, f"🎞️ Analyzing video structure (detected {len(keyframes)} cuts)...")
            
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_blurred = cv2.GaussianBlur(gray, (11, 11), 0)
            
            if prev_gray is None:
                keyframe_path = os.path.join(output_dir, f"keyframe_{int(current_sec):04d}s.jpg")
                cv2.imwrite(keyframe_path, frame)
                keyframes.append({
                    "start_time": current_sec,
                    "end_time": None, 
                    "keyframe_path": keyframe_path
                })
                prev_gray = gray_blurred
            else:
                score, _ = ssim(prev_gray, gray_blurred, full=True)
                if score < SSIM_THRESHOLD:
                    logger.info(f"Transition detected at {current_sec:.2f}s (SSIM: {score:.3f})")
                    keyframes[-1]["end_time"] = current_sec
                    
                    keyframe_path = os.path.join(output_dir, f"keyframe_{int(current_sec):04d}s.jpg")
                    cv2.imwrite(keyframe_path, frame)
                    keyframes.append({
                        "start_time": current_sec,
                        "end_time": None,
                        "keyframe_path": keyframe_path
                    })
                    prev_gray = gray_blurred
                    
        frame_count += 1

    if keyframes:
        total_duration = frame_count / video_fps
        keyframes[-1]["end_time"] = total_duration

    cap.release()
    logger.info(f"Found {len(keyframes)} unique visual chapters.")
    if progress_cb:
        progress_cb(1.0, f"✅ Extracted {len(keyframes)} visual chapters.")
        
    return keyframes


def _get_orb_matches(kp1, des1, kp2, des2):
    """Calculate spatially verified feature matches using Lowe's Ratio and RANSAC."""
    if des1 is None or des2 is None or len(des1) < 2 or len(des2) < 2:
        return 0
        
    bf = cv2.BFMatcher(cv2.NORM_HAMMING)
    matches = bf.knnMatch(des1, des2, k=2)
    
    good_matches = []
    for match_set in matches:
        if len(match_set) == 2:
            m, n = match_set
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)
                
    if len(good_matches) < 10:
        return 0 
        
    src_pts = np.float32([ kp1[m.queryIdx].pt for m in good_matches ]).reshape(-1, 1, 2)
    dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good_matches ]).reshape(-1, 1, 2)
    
    _, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
    
    if mask is None:
        return 0
        
    return int(np.sum(mask))


def match_keyframes_to_slides(keyframes: list[dict], slide_images: list[str], slides_text: str, api_key: str = "", progress_cb=None) -> list[dict]:
    """
    Pass 1: CV RANSAC ORB Matching
    Pass 2: Temporal Smoothing (Back-Fill) & AI Anomaly Rescue
    """
    strategy = app_config.get("video", "matching_strategy", "hybrid")
    logger.info(f"Starting slide matching using strategy: '{strategy}'")
    
    slide_features = []
    if strategy in ["cv", "hybrid"]:
        if progress_cb: progress_cb(0.0, "🧠 Pre-computing PDF geometric features...")
        orb = cv2.ORB_create(nfeatures=5000)
        for img_path in slide_images:
            img = cv2.imread(img_path, cv2.IMREAD_GRAYSCALE)
            if img is not None:
                kp, des = orb.detectAndCompute(img, None)
                slide_features.append({"kp": kp, "des": des})
            else:
                slide_features.append(None)

    total_kf = len(keyframes)

    # ── PASS 1: Confident CV Matches ──
    for i, kf in enumerate(keyframes):
        if progress_cb: progress_cb((i / total_kf) * 0.5, f"🔍 Geometric CV matching chapter {i+1}/{total_kf}...")
        
        kf_path = kf["keyframe_path"]
        kf["matched_slide"] = None
        
        if strategy in ["cv", "hybrid"]:
            kf_img = cv2.imread(kf_path, cv2.IMREAD_GRAYSCALE)
            kf_kp, kf_des = orb.detectAndCompute(kf_img, None)
            
            match_scores = []
            for idx in range(len(slide_features)):
                sf = slide_features[idx]
                if sf is None or sf["des"] is None:
                    match_scores.append((idx, 0))
                    continue
                    
                matches = _get_orb_matches(kf_kp, kf_des, sf["kp"], sf["des"])
                match_scores.append((idx, matches))
                
            match_scores.sort(key=lambda x: x[1], reverse=True)
            best_idx, best_score = match_scores[0]
            runner_up_score = match_scores[1][1] if len(match_scores) > 1 else 0
            
            is_confident_match = False
            if best_score >= 20:
                is_confident_match = True
            elif best_score >= 15 and best_score >= (runner_up_score * 1.2):
                is_confident_match = True
            elif best_score >= 8 and best_score >= (runner_up_score * 1.5):
                is_confident_match = True
                
            if is_confident_match:
                kf["matched_slide"] = best_idx + 1

    # ── PASS 2: Temporal Smoothing (Back-fill) & AI Fallback ──
    for i, kf in enumerate(keyframes):
        if progress_cb: progress_cb(0.5 + ((i / total_kf) * 0.5), f"⏳ Smoothing temporal gaps {i+1}/{total_kf}...")
        
        if kf["matched_slide"] is None:
            kf_path = kf["keyframe_path"]
            
            next_match = None
            gap_size = 0
            for j in range(i, len(keyframes)):
                if keyframes[j].get("matched_slide") is not None:
                    next_match = keyframes[j]["matched_slide"]
                    break
                gap_size += 1

            if next_match is not None and gap_size <= 2:
                kf["matched_slide"] = next_match
                logger.info(f"Temporal Smoothing: Back-filled {os.path.basename(kf_path)} -> Slide {next_match}")
            else:
                if strategy in ["hybrid", "ai"] and api_key:
                    schema = {"type": "OBJECT", "properties": {"slide_number": {"type": "INTEGER"}}, "required": ["slide_number"]}
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
                        kf["matched_slide"] = data.get("slide_number", 0)
                        logger.info(f"AI Match: {os.path.basename(kf_path)} -> Slide {kf['matched_slide']}")
                    except Exception as e:
                        logger.error(f"AI Fallback failed for {os.path.basename(kf_path)}: {e}")
                        kf["matched_slide"] = 0
                else:
                    kf["matched_slide"] = 0

    if progress_cb:
        progress_cb(1.0, f"✅ Visual mapping complete.")

    return keyframes