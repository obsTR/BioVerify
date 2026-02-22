from __future__ import annotations

from typing import Any, Dict, List

import numpy as np

from .config import Config


def compute_sqi(
    rppg_metrics: Dict[str, Any],
    stabilization_metrics: Dict[str, Any],
    config: Config,
) -> Dict[str, Any]:
    """
    Compute a simple SQI (signal quality index) per region and aggregate.

    - SNR proxy: peak power / median power in band.
    - Motion penalty: derived from residual motion metric per window.
    """
    regions = rppg_metrics["regions"]
    sqi_per_region: Dict[str, float] = {}

    for name, data in regions.items():
        spectrum = data.get("spectrum") or {}
        power = np.asarray(spectrum.get("power", []), dtype=float)
        if power.size == 0:
            sqi_per_region[name] = 0.0
            continue
        peak = float(power.max())
        noise = float(np.median(power)) if power.size > 0 else 1.0
        snr = peak / max(noise, 1e-6)
        sqi_per_region[name] = float(np.tanh(snr / 10.0))  # map to (0, 1)

    # Motion penalty: average residual_motion, mapped into [0,1]
    motions: List[float] = [
        float(w["residual_motion"]) for w in stabilization_metrics["windows"]
    ]
    avg_motion = float(np.mean(motions)) if motions else 0.0
    motion_penalty = float(np.clip(avg_motion / 0.2, 0.0, 1.0))

    sqi_values = np.array(list(sqi_per_region.values())) if sqi_per_region else np.array([0.0])
    base_sqi = float(sqi_values.mean())
    aggregate_sqi = float(base_sqi * (1.0 - 0.5 * motion_penalty))

    return {
        "regions": sqi_per_region,
        "aggregate": aggregate_sqi,
        "motion_penalty": motion_penalty,
        "tau_sqi": config.quality.tau_sqi,
    }

