from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

import matplotlib.pyplot as plt
import numpy as np

from .config import Config


def write_evidence(
    out_dir: str,
    result_dict: Dict[str, Any],
    config: Config,
    input_video_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Write evidence artifacts into out_dir.

    Currently writes:
      - summary.json (already handled by CLI but duplicated here for consistency)
      - basic plots for rPPG traces and spectra if available
      - optional face/ROI visualization frames (ROI masks) if enabled
      - index.json listing artifacts
    """
    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)

    artifacts = {}

    summary_path = root / "summary.json"
    summary_path.write_text(json.dumps(result_dict, indent=2, sort_keys=True), encoding="utf-8")
    artifacts["summary"] = "summary.json"

    metrics = result_dict.get("metrics", {})

    # rPPG traces & spectra
    rppg = metrics.get("rppg")
    if config.evidence.enable_plots and rppg:
        plots_dir = root / "plots"
        plots_dir.mkdir(exist_ok=True)
        times = np.asarray(rppg.get("times", []), dtype=float)
        for region_name, data in rppg.get("regions", {}).items():
            # Time trace
            trace_path = plots_dir / f"rppg_trace_{region_name}.png"
            y = np.asarray(data.get("filtered", []), dtype=float)
            if times.size and y.size:
                plt.figure()
                plt.plot(times[: len(y)], y)
                plt.xlabel("Time (s)")
                plt.ylabel("Amplitude")
                plt.title(f"Filtered rPPG - {region_name}")
                plt.tight_layout()
                plt.savefig(trace_path)
                plt.close()
                artifacts.setdefault("rppg_traces", []).append(f"plots/rppg_trace_{region_name}.png")

            # Spectrum
            spec = data.get("spectrum") or {}
            freqs = np.asarray(spec.get("freqs_hz", []), dtype=float)
            power = np.asarray(spec.get("power", []), dtype=float)
            if freqs.size and power.size:
                spec_path = plots_dir / f"rppg_spectrum_{region_name}.png"
                plt.figure()
                plt.plot(freqs, power)
                plt.xlabel("Frequency (Hz)")
                plt.ylabel("Power")
                plt.title(f"Spectrum - {region_name}")
                plt.tight_layout()
                plt.savefig(spec_path)
                plt.close()
                artifacts.setdefault("rppg_spectra", []).append(f"plots/rppg_spectrum_{region_name}.png")

    # Face / ROI visualization frames (screenshots)
    # These help understand framing, motion, and ROI coverage per stage.
    if config.evidence.enable_roi_masks and input_video_path:
        try:
            import cv2
            from .utils.video import read_video  # local import to avoid cycles at import time
            from .utils.logging import get_logger

            logger = get_logger(__name__)

            frames, timestamps, _fps = read_video(input_video_path)
            roi_metrics = metrics.get("roi") or {}
            per_frame = roi_metrics.get("frames") or []
            
            # Check if frames array is empty (numpy arrays can't use 'if not frames')
            if frames is None or (hasattr(frames, 'size') and frames.size == 0) or len(frames) == 0:
                logger.warning("No frames read from video for ROI visualization")
            elif not per_frame:
                logger.warning("No ROI frame data available for visualization")
            else:
                # Choose up to 3 representative frames where we have ROI info.
                indices = list(range(len(per_frame)))
                if not indices:
                    indices = list(range(min(3, len(frames))))
                # Sample at roughly start / middle / end.
                sample_idxs = sorted(
                    {indices[0], indices[len(indices) // 2], indices[-1]}
                    if len(indices) >= 3
                    else set(indices)
                )

                roi_dir = root / "roi_masks"
                roi_dir.mkdir(exist_ok=True)

                for i, frame_idx in enumerate(sample_idxs, start=1):
                    if frame_idx >= len(frames):
                        continue
                    frame = frames[frame_idx].copy()
                    rec = per_frame[min(frame_idx, len(per_frame) - 1)] or {}
                    box = rec.get("box")
                    regions = rec.get("regions") or {}

                    h, w = frame.shape[:2]
                    
                    # Debug: log what we found
                    logger.debug(f"Frame {frame_idx}: box={box}, regions keys={list(regions.keys())}")
                    
                    # Always add text annotation showing frame info
                    frame_time = rec.get("time", timestamps[frame_idx] if frame_idx < len(timestamps) else 0.0)
                    status_text = []
                    
                    # Draw face bounding box, if available
                    # Handle both None and empty list cases
                    has_valid_box = (
                        box is not None 
                        and isinstance(box, (list, tuple))
                        and len(box) == 4
                    )
                    if has_valid_box:
                        x, y, fw, fh = box
                        x, y, fw, fh = int(x), int(y), int(fw), int(fh)
                        if fw > 0 and fh > 0:
                            cv2.rectangle(frame, (x, y), (x + fw, y + fh), (52, 211, 153), 2)  # emerald
                            status_text.append("Face detected")

                            # Draw ROI rectangles based on the same geometry as ROI extraction
                            regions_def = {
                                "forehead": (
                                    (x, int(y + 0.0 * fh)),
                                    (x + fw, int(y + 0.3 * fh)),
                                ),
                                "left_cheek": (
                                    (int(x + 0.0 * fw), int(y + 0.3 * fh)),
                                    (int(x + 0.5 * fw), int(y + 0.7 * fh)),
                                ),
                                "right_cheek": (
                                    (int(x + 0.5 * fw), int(y + 0.3 * fh)),
                                    (int(x + 1.0 * fw), int(y + 0.7 * fh)),
                                ),
                            }
                            valid_count = 0
                            for name, ((x0, y0), (x1, y1)) in regions_def.items():
                                color = (239, 68, 68)  # red (BGR)
                                if regions.get(name, {}).get("valid"):
                                    color = (52, 211, 153)  # emerald (BGR)
                                    valid_count += 1
                                # Clamp to frame
                                x0 = max(0, min(w - 1, x0))
                                x1 = max(0, min(w - 1, x1))
                                y0 = max(0, min(h - 1, y0))
                                y1 = max(0, min(h - 1, y1))
                                if x1 > x0 and y1 > y0:
                                    cv2.rectangle(frame, (x0, y0), (x1, y1), color, 2)
                            
                            if valid_count == 0:
                                status_text.append("No valid ROIs")
                            elif valid_count < 3:
                                status_text.append(f"{valid_count}/3 ROIs valid")
                            else:
                                status_text.append("All ROIs valid")
                        else:
                            status_text.append("Invalid face box")
                    else:
                        status_text.append("No face detected")
                    
                    # Add text overlay at top-left
                    y_offset = 30
                    cv2.putText(frame, f"Frame {i} | t={frame_time:.2f}s", (10, y_offset), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                    for j, text in enumerate(status_text):
                        cv2.putText(frame, text, (10, y_offset + 25 + j * 25), 
                                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)

                    # Resize frame if too large (max width 1280px) to reduce file size
                    h, w = frame.shape[:2]
                    max_width = 1280
                    if w > max_width:
                        scale = max_width / w
                        new_w = max_width
                        new_h = int(h * scale)
                        frame = cv2.resize(frame, (new_w, new_h), interpolation=cv2.INTER_AREA)
                        logger.debug(f"Resized frame from {w}x{h} to {new_w}x{new_h}")
                    
                    # Write JPEG with compression (much smaller than PNG)
                    out_name = f"roi_frame_{i}.jpg"
                    out_path = roi_dir / out_name
                    # JPEG quality 85 (good balance between size and quality)
                    success = cv2.imwrite(str(out_path), frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    if success:
                        file_size_kb = out_path.stat().st_size / 1024
                        artifacts.setdefault("roi_masks", []).append(f"roi_masks/{out_name}")
                        logger.info(f"Wrote ROI visualization: {out_path} ({file_size_kb:.1f} KB)")
                    else:
                        logger.error(f"Failed to write ROI visualization: {out_path}")

        except Exception as e:
            # ROI visualization is best-effort and should never break analysis.
            from .utils.logging import get_logger
            logger = get_logger(__name__)
            logger.warning(f"ROI visualization failed (non-fatal): {e}", exc_info=True)

    index_path = root / "index.json"
    index = {
        "config_version": config.config_version,
        "artifacts": artifacts,
    }
    index_path.write_text(json.dumps(index, indent=2, sort_keys=True), encoding="utf-8")
    artifacts["index"] = "index.json"

    return artifacts

