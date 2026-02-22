from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

import cv2
import numpy as np

from .config import Config
from .types import IngestResult
from .utils.logging import get_logger, log_params
from .utils.video import read_video


logger = get_logger(__name__)


def _region_masks_for_frame(frame_shape, face_box):
    h, w = frame_shape[:2]
    if face_box is None:
        return {}
    
    # Validate face_box format
    if not isinstance(face_box, (list, tuple)) or len(face_box) != 4:
        logger.warning(f"Invalid face_box format: {face_box}")
        return {}
    
    x, y, fw, fh = face_box
    x, y, fw, fh = int(x), int(y), int(fw), int(fh)
    
    # Validate face box is within frame bounds
    if fw <= 0 or fh <= 0:
        logger.warning(f"Invalid face box dimensions: w={fw}, h={fh}")
        return {}
    
    # Clamp face box to frame bounds
    x = max(0, min(x, w - 1))
    y = max(0, min(y, h - 1))
    fw = min(fw, w - x)
    fh = min(fh, h - y)
    
    if fw <= 0 or fh <= 0:
        logger.warning(f"Face box clamped to invalid size: w={fw}, h={fh} at ({x},{y})")
        return {}
    
    # Calculate ROI regions with bounds checking
    forehead_y0 = max(0, int(y + 0.0 * fh))
    forehead_y1 = min(h, int(y + 0.3 * fh))
    forehead_x0 = max(0, x)
    forehead_x1 = min(w, x + fw)
    
    cheek_y0 = max(0, int(y + 0.3 * fh))
    cheek_y1 = min(h, int(y + 0.7 * fh))
    left_cheek_x0 = max(0, int(x + 0.0 * fw))
    left_cheek_x1 = min(w, int(x + 0.5 * fw))
    right_cheek_x0 = max(0, int(x + 0.5 * fw))
    right_cheek_x1 = min(w, int(x + 1.0 * fw))
    
    forehead = (slice(forehead_y0, forehead_y1), slice(forehead_x0, forehead_x1))
    left_cheek = (slice(cheek_y0, cheek_y1), slice(left_cheek_x0, left_cheek_x1))
    right_cheek = (slice(cheek_y0, cheek_y1), slice(right_cheek_x0, right_cheek_x1))
    
    masks = {}
    base = np.zeros((h, w), dtype=bool)
    for name, slc in {
        "forehead": forehead,
        "left_cheek": left_cheek,
        "right_cheek": right_cheek,
    }.items():
        # Validate slice bounds
        y_slice, x_slice = slc
        if y_slice.start < y_slice.stop and x_slice.start < x_slice.stop:
            m = base.copy()
            m[slc] = True
            masks[name] = m
        else:
            # Invalid slice - region is empty or out of bounds
            masks[name] = base.copy()
    
    return masks


def extract_rois(path: str, face_metrics: Dict[str, Any], ingest_result: IngestResult, config: Config) -> Dict[str, Any]:
    """
    Produce simple ROI masks (forehead, left/right cheek) per frame and coverage stats.
    """
    log_params(logger, "roi", {"path": path, "roi": asdict(config.roi)})

    frames, timestamps, _fps = read_video(path)
    per_frame_face = {m["time"]: m for m in face_metrics["frames"]}

    per_frame: List[Dict[str, Any]] = []
    min_cov = config.roi.min_region_coverage

    frames_with_valid_box = 0
    frames_with_invalid_box = 0
    
    for idx, t in enumerate(timestamps):
        rec = per_frame_face.get(float(t))
        if rec is None:
            rec = face_metrics["frames"][min(idx, len(face_metrics["frames"]) - 1)]
        box = rec["box"]
        
        if idx < 3:
            frame_h, frame_w = frames[idx].shape[:2]
            if box:
                logger.info(f"ROI frame {idx}: face_box={box}, frame_size=({frame_w}x{frame_h})")
            else:
                logger.warning(f"ROI frame {idx}: No face box available")
        
        masks = _region_masks_for_frame(frames[idx].shape, box)
        
        # Compute coverage relative to face area (not frame area) so the threshold
        # is scale-independent and works for both close-ups and distant subjects.
        if box and isinstance(box, (list, tuple)) and len(box) == 4:
            face_area = max(1, int(box[2]) * int(box[3]))
        else:
            face_area = 1
        
        regions: Dict[str, Any] = {}
        
        if box:
            frames_with_valid_box += 1
        else:
            frames_with_invalid_box += 1
        
        for name, m in masks.items():
            coverage = float(m.sum()) / float(face_area) if face_area > 1 else 0.0
            regions[name] = {
                "coverage": coverage,
                "valid": coverage >= min_cov,
            }
            if idx == 0:
                logger.info(
                    f"ROI frame 0 - {name}: coverage={coverage:.4f} (of face area), "
                    f"valid={coverage >= min_cov}, threshold={min_cov}"
                )
        
        # Store box so rppg can compute per-ROI pixel means without re-detecting
        per_frame.append({"time": float(t), "regions": regions, "box": box})
    
    logger.info(
        f"ROI extraction: {frames_with_valid_box} frames with face box, "
        f"{frames_with_invalid_box} frames without face box"
    )

    # Compact summary for API/diagnostics (avoid sending thousands of frame entries)
    regions_list = ["forehead", "left_cheek", "right_cheek"]
    frames_with_all_valid = sum(
        1 for f in per_frame
        if all((f.get("regions") or {}).get(r, {}).get("valid") for r in regions_list)
    )
    frames_per_region = {
        name: sum(1 for f in per_frame if (f.get("regions") or {}).get(name, {}).get("valid"))
        for name in regions_list
    }
    metrics: Dict[str, Any] = {
        "frames": per_frame,
        "summary": {
            "total_frames": len(per_frame),
            "frames_with_all_regions_valid": frames_with_all_valid,
            "frames_per_region": frames_per_region,
        },
    }

    return {"metrics": metrics}

