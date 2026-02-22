from .config import Config
from .types import AnalysisResult, Verdict
from .ingest import ingest_video
from .face import analyze_faces
from .roi import extract_rois
from .stabilization import stabilize_rois
from .rppg import extract_rppg
from .quality import compute_sqi
from .features import compute_features
from .scoring import score_and_decide


def analyze_video(input_path: str, config: Config) -> AnalysisResult:
    """
    Public entrypoint for the bioverify engine.

    Run the full analysis pipeline (ingest, face, ROI, stabilization, rPPG,
    SQI, features, scoring) and return an AnalysisResult.
    """
    try:
        ingest_result = ingest_video(input_path, config)
        face_result = analyze_faces(input_path, ingest_result, config)
        roi_result = extract_rois(
            input_path, face_result["metrics"], ingest_result, config
        )
        stabilization_result = stabilize_rois(
            ingest_result, face_result["metrics"], roi_result["metrics"], config
        )
        rppg_result = extract_rppg(
            input_path,
            ingest_result,
            roi_result["metrics"],
            config,
        )
        sqi = compute_sqi(rppg_result["metrics"], stabilization_result["metrics"], config)
        feats = compute_features(rppg_result["metrics"])
        scoring = score_and_decide(sqi, feats, config)

        metrics = {
            "config_version": config.config_version,
            "ingest": ingest_result.metrics,
            "face": face_result["metrics"],
            "roi": roi_result["metrics"],
            "stabilization": stabilization_result["metrics"],
            "rppg": rppg_result["metrics"],
            "sqi": sqi,
            "features": feats,
            "scoring": scoring["breakdown"],
        }
        return AnalysisResult(
            verdict=scoring["verdict"],
            score=scoring["score"],
            confidence=scoring["confidence"],
            reasons=ingest_result.reasons + face_result["reasons"] + scoring["reasons"],
            metrics=metrics,
            evidence_paths={},
            error=None,
            config_version=config.config_version,
        )
    except Exception as exc:  # noqa: BLE001
        return AnalysisResult(
            verdict=Verdict.INCONCLUSIVE,
            score=0.0,
            confidence=0.0,
            reasons=["internal_error"],
            metrics={},
            evidence_paths={},
            error={"message": str(exc), "type": exc.__class__.__name__},
            config_version=config.config_version,
        )


__all__ = ["analyze_video", "Config", "AnalysisResult", "Verdict"]

