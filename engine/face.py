from __future__ import annotations

import os
from dataclasses import asdict
from typing import Any, Dict, List, Tuple
from pathlib import Path

import cv2
import numpy as np

from .config import Config
from .types import IngestResult
from .utils.logging import get_logger, log_params
from .utils.video import read_video


logger = get_logger(__name__)

# Directory where DNN model files are stored
_MODEL_DIR = Path(__file__).parent / "models"

_dnn_net = None


def _get_dnn_detector():
    """
    Load OpenCV's built-in DNN face detector (Caffe model).
    Downloads the model files on first use if they don't exist.
    Falls back to Haar cascade if DNN model is unavailable.
    """
    global _dnn_net
    if _dnn_net is not None:
        return _dnn_net

    _MODEL_DIR.mkdir(exist_ok=True)

    prototxt = _MODEL_DIR / "deploy.prototxt"
    caffemodel = _MODEL_DIR / "res10_300x300_ssd_iter_140000_fp16.caffemodel"

    if not prototxt.exists() or not caffemodel.exists():
        logger.info("Downloading DNN face detection model (one-time)...")
        try:
            import urllib.request

            proto_url = (
                "https://raw.githubusercontent.com/opencv/opencv/master/samples/dnn/face_detector/deploy.prototxt"
            )
            model_url = (
                "https://github.com/opencv/opencv_3rdparty/raw/dnn_samples_face_detector_20180205_fp16/"
                "res10_300x300_ssd_iter_140000_fp16.caffemodel"
            )

            if not prototxt.exists():
                urllib.request.urlretrieve(proto_url, str(prototxt))
                logger.info(f"Downloaded {prototxt.name}")

            if not caffemodel.exists():
                urllib.request.urlretrieve(model_url, str(caffemodel))
                logger.info(f"Downloaded {caffemodel.name}")

        except Exception as e:
            logger.warning(f"Could not download DNN model: {e}. Will fall back to Haar cascade.")
            return None

    try:
        net = cv2.dnn.readNetFromCaffe(str(prototxt), str(caffemodel))
        _dnn_net = net
        logger.info("DNN face detector loaded successfully")
        return net
    except Exception as e:
        logger.warning(f"Could not load DNN model: {e}. Will fall back to Haar cascade.")
        return None


def _detect_face_dnn(frame: np.ndarray, net, confidence_threshold: float = 0.5) -> List[Tuple[int, int, int, int, float]]:
    """
    Detect faces using OpenCV DNN (SSD ResNet-10).
    Returns list of (x, y, w, h, confidence).
    """
    h, w = frame.shape[:2]
    blob = cv2.dnn.blobFromImage(
        cv2.resize(frame, (300, 300)),
        1.0,
        (300, 300),
        (104.0, 177.0, 123.0),
    )
    net.setInput(blob)
    detections = net.forward()

    faces = []
    for i in range(detections.shape[2]):
        conf = float(detections[0, 0, i, 2])
        if conf < confidence_threshold:
            continue
        x0 = int(detections[0, 0, i, 3] * w)
        y0 = int(detections[0, 0, i, 4] * h)
        x1 = int(detections[0, 0, i, 5] * w)
        y1 = int(detections[0, 0, i, 6] * h)

        # Clamp to frame bounds
        x0 = max(0, min(x0, w - 1))
        y0 = max(0, min(y0, h - 1))
        x1 = max(0, min(x1, w - 1))
        y1 = max(0, min(y1, h - 1))

        fw = x1 - x0
        fh = y1 - y0
        if fw > 10 and fh > 10:
            faces.append((x0, y0, fw, fh, conf))

    return faces


def _detect_face_haar(frame: np.ndarray) -> List[Tuple[int, int, int, int, float]]:
    """Fallback: Haar cascade face detection. Returns list of (x, y, w, h, confidence)."""
    cascade = cv2.CascadeClassifier(
        cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
    )
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30))
    if len(faces) == 0:
        return []
    return [(int(x), int(y), int(w), int(h), 0.8) for (x, y, w, h) in faces]


def _select_best_face(
    faces: List[Tuple[int, int, int, int, float]],
    frame_w: int,
    frame_h: int,
) -> Tuple[int, int, int, int, float] | None:
    """
    Pick the best face from candidates.
    Prefers faces that are: high confidence, large, near frame center.
    Penalizes detections near frame edges (likely false positives).
    """
    if not faces:
        return None

    cx_frame = frame_w / 2
    cy_frame = frame_h / 2
    best = None
    best_score = -1e9

    for (x, y, w, h, conf) in faces:
        cx = x + w / 2
        cy = y + h / 2

        area_frac = (w * h) / (frame_w * frame_h)
        dx = (cx - cx_frame) / frame_w
        dy = (cy - cy_frame) / frame_h
        center_penalty = dx * dx + dy * dy

        score = conf * 0.5 + area_frac * 0.3 - center_penalty * 0.8

        # Penalize detections in outer 15% of frame
        edge = 0.15
        if (cx < frame_w * edge or cx > frame_w * (1 - edge) or
                cy < frame_h * edge or cy > frame_h * (1 - edge)):
            score -= 0.5

        if score > best_score:
            best_score = score
            best = (x, y, w, h, conf)

    return best


def _make_result(x, y, w, h, conf):
    """Build a face result dict from detection coordinates."""
    landmarks = [
        [int(x + 0.3 * w), int(y + 0.35 * h)],
        [int(x + 0.7 * w), int(y + 0.35 * h)],
        [int(x + 0.5 * w), int(y + 0.5 * h)],
        [int(x + 0.35 * w), int(y + 0.75 * h)],
        [int(x + 0.65 * w), int(y + 0.75 * h)],
        [int(x + 0.5 * w), int(y + 0.9 * h)],
    ]
    return {
        "box": [int(x), int(y), int(w), int(h)],
        "landmarks": landmarks,
        "tracking_confidence": float(conf),
    }


_NO_FACE = {"box": None, "landmarks": [], "tracking_confidence": 0.0}

# Run DNN detector every Nth frame; reuse the last detection for skipped frames.
_DETECT_EVERY_N = 3


def _detect_faces(frames: np.ndarray) -> List[Dict[str, Any]]:
    """Detect faces with frame skipping for speed."""
    dnn_net = _get_dnn_detector()
    use_dnn = dnn_net is not None
    logger.info(f"Face detector: {'DNN (SSD ResNet-10)' if use_dnn else 'Haar cascade (fallback)'}")

    results: List[Dict[str, Any]] = []
    detected_count = 0
    last_detection = None
    logged = 0

    for frame_idx, frame in enumerate(frames):
        frame_h, frame_w = frame.shape[:2]

        # Only run the detector every Nth frame
        run_detector = (frame_idx % _DETECT_EVERY_N == 0)

        if run_detector:
            if use_dnn:
                faces = _detect_face_dnn(frame, dnn_net, confidence_threshold=0.5)
            else:
                faces = _detect_face_haar(frame)
            best = _select_best_face(faces, frame_w, frame_h)

            if best is not None:
                x, y, w, h, conf = best
                last_detection = _make_result(x, y, w, h, conf)
                detected_count += 1
                if logged < 3:
                    cx = x + w / 2
                    cy = y + h / 2
                    size_pct = (w * h) / (frame_w * frame_h) * 100
                    logger.info(
                        f"Face selected frame {frame_idx}: box=({x},{y},{w},{h}), "
                        f"center=({cx:.0f},{cy:.0f}), size={size_pct:.1f}% of frame, "
                        f"conf={conf:.2f}"
                    )
                    logged += 1
            else:
                last_detection = None
        else:
            # Reuse last detection for skipped frames
            if last_detection is not None:
                detected_count += 1

        results.append(dict(last_detection) if last_detection else dict(_NO_FACE))

    rate = detected_count / len(frames) * 100 if len(frames) else 0
    logger.info(f"Face detection summary: {detected_count}/{len(frames)} frames ({rate:.1f}%) had faces")
    if detected_count == 0:
        logger.warning("No faces detected in any frame! The DNN model may not have downloaded correctly.")

    return results


def analyze_faces(path: str, ingest_result: IngestResult, config: Config) -> Dict[str, Any]:
    """Run per-frame face detection and basic tracking quality metrics."""
    log_params(
        logger,
        "face",
        {"path": path, "face": asdict(config.face), "num_windows": len(ingest_result.windows)},
    )

    frames, timestamps, _fps = read_video(path)
    per_frame = _detect_faces(frames)

    window_summaries: List[Dict[str, Any]] = []
    reasons: List[str] = []
    min_fraction = config.face.min_face_fraction

    for w in ingest_result.windows:
        mask = (timestamps >= w.start_time) & (timestamps <= w.end_time)
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            fraction = 0.0
        else:
            num_valid = sum(
                1 for i in idxs if per_frame[i]["tracking_confidence"] > 0.0
            )
            fraction = num_valid / len(idxs)

        usable = fraction >= min_fraction
        if not usable:
            reasons.append("window_face_insufficient")

        window_summaries.append(
            {
                "index": w.index,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "face_fraction": fraction,
                "usable": usable,
            }
        )

    metrics: Dict[str, Any] = {
        "frames": [
            {
                "time": float(timestamps[i]),
                "box": rec["box"],
                "landmarks": rec["landmarks"],
                "tracking_confidence": float(rec["tracking_confidence"]),
            }
            for i, rec in enumerate(per_frame)
        ],
        "windows": window_summaries,
    }

    return {"metrics": metrics, "reasons": reasons}
