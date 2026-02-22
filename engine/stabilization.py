from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

import numpy as np

from .config import Config
from .types import IngestResult
from .utils.logging import get_logger, log_params


logger = get_logger(__name__)


def stabilize_rois(
    ingest_result: IngestResult,
    face_metrics: Dict[str, Any],
    roi_metrics: Dict[str, Any],
    config: Config,
) -> Dict[str, Any]:
    """
    Placeholder stabilization that simply computes a dummy residual motion per window.

    A real implementation would warp ROIs into a canonical frame and compute optical
    flow residuals; here we just synthesize a small random motion metric so that
    downstream SQI logic has a numeric signal to work with.
    """
    log_params(
        logger,
        "stabilization",
        {
            "config": asdict(config.rppg),
            "num_windows": len(ingest_result.windows),
        },
    )

    # For now, approximate motion as zero with small noise per window.
    motion_per_window: List[Dict[str, Any]] = []
    rng = np.random.default_rng(0)
    for w in ingest_result.windows:
        motion_value = float(abs(rng.normal(loc=0.02, scale=0.01)))
        motion_per_window.append(
            {
                "index": w.index,
                "start_time": w.start_time,
                "end_time": w.end_time,
                "residual_motion": motion_value,
            }
        )

    metrics: Dict[str, Any] = {
        "windows": motion_per_window,
    }

    return {"metrics": metrics}

