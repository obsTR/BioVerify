from __future__ import annotations

from dataclasses import dataclass, asdict
from enum import Enum
from typing import Any, Dict, List, Optional


class Verdict(str, Enum):
    HUMAN = "Human"
    SYNTHETIC = "Synthetic"
    INCONCLUSIVE = "Inconclusive"


@dataclass
class IngestWindow:
    index: int
    start_time: float
    end_time: float
    fps: float
    resolution: Dict[str, int]
    duration: float
    dropped_frames_estimate: float


@dataclass
class IngestResult:
    windows: List[IngestWindow]
    metrics: Dict[str, Any]
    reasons: List[str]


@dataclass
class AnalysisResult:
    verdict: Verdict
    score: float
    confidence: float
    reasons: List[str]
    metrics: Dict[str, Any]
    evidence_paths: Dict[str, Any]
    error: Optional[Dict[str, Any]]
    config_version: str

    def to_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["verdict"] = self.verdict.value
        return data

