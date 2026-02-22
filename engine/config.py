from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass
class IngestConfig:
    target_fps: float = 30.0
    window_seconds: float = 8.0
    overlap_ratio: float = 0.5
    min_duration_seconds: float = 3.0


@dataclass
class FaceConfig:
    min_face_fraction: float = 0.6
    # Face detection sensitivity (lower = more sensitive, detects smaller/less clear faces)
    detection_sensitivity: float = 1.0  # 1.0 = default, <1.0 = more lenient, >1.0 = stricter


@dataclass
class ROIConfig:
    min_region_coverage: float = 0.2


@dataclass
class RPPGConfig:
    bandpass_low_hz: float = 0.7
    bandpass_high_hz: float = 4.0


@dataclass
class QualityConfig:
    tau_sqi: float = 0.1
    # If True, still output Human/Synthetic when SQI is below threshold (for testing).
    # Reasons will include "low_sqi" and confidence will be capped low.
    allow_verdict_when_low_sqi: bool = True


@dataclass
class FeaturesConfig:
    hr_plausibility_weight: float = 0.10
    spectral_concentration_weight: float = 0.15
    spectral_sharpness_weight: float = 0.15
    coherence_weight: float = 0.10
    phase_coherence_weight: float = 0.10
    periodicity_weight: float = 0.05
    harmonic_weight: float = 0.10
    hrv_weight: float = 0.05
    temporal_stability_weight: float = 0.10
    respiratory_weight: float = 0.10


@dataclass
class ScoringConfig:
    tau_auth: float = 0.50


@dataclass
class EvidenceConfig:
    enable_plots: bool = True  # rPPG traces & spectra
    enable_roi_masks: bool = True  # face/ROI visualization frames


@dataclass
class EvalConfig:
    pass


@dataclass
class CalibrationConfig:
    pass


@dataclass
class Config:
    """
    Top-level configuration for the engine.
    """

    config_version: str = "0.1.0"
    ingest: IngestConfig = field(default_factory=IngestConfig)
    face: FaceConfig = field(default_factory=FaceConfig)
    roi: ROIConfig = field(default_factory=ROIConfig)
    rppg: RPPGConfig = field(default_factory=RPPGConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    features: FeaturesConfig = field(default_factory=FeaturesConfig)
    scoring: ScoringConfig = field(default_factory=ScoringConfig)
    evidence: EvidenceConfig = field(default_factory=EvidenceConfig)
    eval: EvalConfig = field(default_factory=EvalConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    extra: Dict[str, Any] = field(default_factory=dict)

