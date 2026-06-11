"""
video_aligner_test.py
---------------------
Standalone script to test the Visual-Audio Fusion Pipeline.
"""

import os
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