from __future__ import annotations

from typing import Any, Dict

import numpy as np

from .config import Config
from .types import Verdict
from .utils.logging import get_logger

logger = get_logger(__name__)


def score_and_decide(
    sqi_metrics: Dict[str, Any],
    feature_metrics: Dict[str, Any],
    config: Config,
) -> Dict[str, Any]:
    """
    Combine SQI gate and physiological liveness features into a verdict.

    Uses weighted features + critical feature gates.
    Gates penalize the score multiplicatively when key discriminating
    features fail, preventing noise from compensating.
    """
    aggregate_sqi = float(sqi_metrics["aggregate"])
    tau_sqi = float(sqi_metrics["tau_sqi"])
    sqi_gate_failed = aggregate_sqi < tau_sqi

    liveness = feature_metrics.get("liveness") or {}
    fw = config.features

    hr_plausibility = float(liveness.get("hr_plausibility", 0.0))
    spectral_concentration = float(liveness.get("spectral_concentration", 0.0))
    spectral_sharpness = float(liveness.get("spectral_sharpness", 0.0))
    coherence = float(liveness.get("inter_region_coherence", 0.0))
    phase_coherence = float(liveness.get("phase_coherence", 0.0))
    periodicity = float(liveness.get("periodicity", 0.0))
    harmonic = float(liveness.get("harmonic_structure", 0.0))
    hrv_score = float(liveness.get("hrv_score", 0.0))
    temporal_stability = float(liveness.get("temporal_hr_stability", 0.0))
    respiratory = float(liveness.get("respiratory_score", 0.0))

    total_weight = (
        fw.hr_plausibility_weight
        + fw.spectral_concentration_weight
        + fw.spectral_sharpness_weight
        + fw.coherence_weight
        + fw.phase_coherence_weight
        + fw.periodicity_weight
        + fw.harmonic_weight
        + fw.hrv_weight
        + fw.temporal_stability_weight
        + fw.respiratory_weight
    )
    if total_weight < 1e-6:
        total_weight = 1.0

    base_score = (
        fw.hr_plausibility_weight * hr_plausibility
        + fw.spectral_concentration_weight * spectral_concentration
        + fw.spectral_sharpness_weight * spectral_sharpness
        + fw.coherence_weight * coherence
        + fw.phase_coherence_weight * phase_coherence
        + fw.periodicity_weight * periodicity
        + fw.harmonic_weight * harmonic
        + fw.hrv_weight * hrv_score
        + fw.temporal_stability_weight * temporal_stability
        + fw.respiratory_weight * respiratory
    ) / total_weight

    # ── Critical feature gates ───────────────────────────────────────
    # A real human MUST demonstrate ALL of these at minimum levels.
    # Failing any gate drags the score down multiplicatively.

    SCR_GATE = 0.20
    TEMPORAL_GATE = 0.25
    HR_GATE = 0.20
    Q_GATE = 0.15
    RESP_GATE = 0.20

    scr_gate = min(1.0, spectral_concentration / SCR_GATE)
    temporal_gate = min(1.0, temporal_stability / TEMPORAL_GATE)
    hr_gate = min(1.0, hr_plausibility / HR_GATE)
    q_gate = min(1.0, spectral_sharpness / Q_GATE)
    resp_gate = min(1.0, respiratory / RESP_GATE)

    raw_gate = scr_gate * temporal_gate * hr_gate * q_gate * resp_gate
    gate_factor = float(np.sqrt(raw_gate))
    gate_factor = max(gate_factor, 0.10)
    liveness_score = base_score * gate_factor

    reasons = []

    feature_breakdown = {
        "hr_plausibility": {"value": hr_plausibility, "weight": fw.hr_plausibility_weight},
        "spectral_concentration": {"value": spectral_concentration, "weight": fw.spectral_concentration_weight},
        "spectral_sharpness": {"value": spectral_sharpness, "weight": fw.spectral_sharpness_weight},
        "inter_region_coherence": {"value": coherence, "weight": fw.coherence_weight},
        "phase_coherence": {"value": phase_coherence, "weight": fw.phase_coherence_weight},
        "periodicity": {"value": periodicity, "weight": fw.periodicity_weight},
        "harmonic_structure": {"value": harmonic, "weight": fw.harmonic_weight},
        "hrv": {"value": hrv_score, "weight": fw.hrv_weight},
        "temporal_stability": {"value": temporal_stability, "weight": fw.temporal_stability_weight},
        "respiratory": {"value": respiratory, "weight": fw.respiratory_weight},
    }

    if hr_plausibility < 0.3:
        reasons.append("no_clear_heartbeat")
    if spectral_concentration < 0.25:
        reasons.append("diffuse_spectrum")
    if spectral_sharpness < 0.3:
        reasons.append("broad_spectral_peak")
    if coherence < 0.3:
        reasons.append("low_inter_region_coherence")
    if phase_coherence < 0.3:
        reasons.append("no_pulse_transit")
    if temporal_stability < 0.3:
        reasons.append("unstable_hr")
    if hrv_score < 0.2:
        reasons.append("abnormal_hrv")
    if harmonic < 0.1:
        reasons.append("no_harmonic_structure")
    if respiratory < 0.2:
        reasons.append("no_respiratory_modulation")

    logger.info(
        f"Scoring: base={base_score:.3f}, "
        f"gates=[SCR={scr_gate:.2f} temporal={temporal_gate:.2f} "
        f"HR={hr_gate:.2f} Q={q_gate:.2f} resp={resp_gate:.2f}], "
        f"gate_factor={gate_factor:.3f}, final={liveness_score:.3f}, "
        f"tau={config.scoring.tau_auth}"
    )

    # Decision
    if sqi_gate_failed and not getattr(config.quality, "allow_verdict_when_low_sqi", False):
        verdict = Verdict.INCONCLUSIVE
        reasons.append("low_sqi")
    else:
        if sqi_gate_failed:
            reasons.append("low_sqi")

        if liveness_score >= config.scoring.tau_auth:
            verdict = Verdict.HUMAN
            reasons.append("authentic")
        else:
            verdict = Verdict.SYNTHETIC
            reasons.append("low_liveness_score")

    dist = abs(liveness_score - config.scoring.tau_auth)
    confidence = float(min(1.0, dist * 2.5))
    if sqi_gate_failed:
        confidence = min(confidence, 0.25)

    breakdown: Dict[str, Any] = {
        "liveness_score": liveness_score,
        "base_score": base_score,
        "gate_factor": gate_factor,
        "aggregate_sqi": aggregate_sqi,
        "tau_auth": config.scoring.tau_auth,
        "gates": {
            "spectral_concentration": {"value": spectral_concentration, "threshold": SCR_GATE, "gate": scr_gate},
            "temporal_stability": {"value": temporal_stability, "threshold": TEMPORAL_GATE, "gate": temporal_gate},
            "hr_plausibility": {"value": hr_plausibility, "threshold": HR_GATE, "gate": hr_gate},
            "spectral_sharpness": {"value": spectral_sharpness, "threshold": Q_GATE, "gate": q_gate},
            "respiratory": {"value": respiratory, "threshold": RESP_GATE, "gate": resp_gate},
        },
        "features": feature_breakdown,
    }

    logger.info(
        f"Verdict: {verdict.value} (confidence={confidence:.2f}), "
        f"score={liveness_score:.3f} (base={base_score:.3f} x gate={gate_factor:.3f})"
    )

    return {
        "verdict": verdict,
        "score": liveness_score,
        "confidence": confidence,
        "reasons": reasons,
        "breakdown": breakdown,
    }
