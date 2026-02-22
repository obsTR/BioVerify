from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np

from engine.config import Config
from engine.ingest import ingest_video


def _make_synthetic_video(path: Path, num_frames: int = 60, fps: int = 30) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    out = cv2.VideoWriter(str(path), fourcc, fps, (64, 64))
    for i in range(num_frames):
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        cv2.putText(
            img,
            str(i),
            (10, 32),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (255, 255, 255),
            1,
            cv2.LINE_AA,
        )
        out.write(img)
    out.release()


def test_ingest_windowing(tmp_path: Path) -> None:
    video_path = tmp_path / "synthetic.mp4"
    _make_synthetic_video(video_path, num_frames=90, fps=30)

    cfg = Config()
    cfg.ingest.window_seconds = 3.0
    cfg.ingest.overlap_ratio = 0.5
    cfg.ingest.min_duration_seconds = 1.0

    result = ingest_video(str(video_path), cfg)

    assert result.reasons == []
    assert result.metrics["num_windows"] >= 1
    # Check monotonic windows
    starts = [w.start_time for w in result.windows]
    assert starts == sorted(starts)

