import tempfile
import json
import os
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

from engine import analyze_video, Config
from engine.types import Verdict
from backend.storage.base import StorageBackend


@dataclass
class JobSpec:
    analysis_id: str
    input_uri: str
    policy_name: Optional[str] = None
    output_uri_prefix: str = ""
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class JobResult:
    analysis_id: str
    status: str  # 'done' or 'failed'
    verdict: Optional[str] = None
    score: Optional[float] = None
    confidence: Optional[float] = None
    reasons: Optional[list] = None
    metrics_summary: Optional[Dict[str, Any]] = None
    metrics: Optional[Dict[str, Any]] = None  # diagnostics: ingest, face, roi, rppg (compact)
    evidence_index: Optional[str] = None
    engine_version: Optional[str] = None
    policy_version: Optional[str] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def run_analysis(job: JobSpec, storage: StorageBackend) -> JobResult:
    """
    Execute an analysis job.

    Downloads video, runs engine, uploads evidence, returns result.
    """
    temp_dir = None
    try:
        # Create temp directory for this analysis
        temp_dir = Path(tempfile.mkdtemp(prefix=f"bioverify_{job.analysis_id}_"))
        input_video_path = temp_dir / "input.mp4"
        evidence_dir = temp_dir / "evidence"

        # Download input video
        try:
            storage.download_file(job.input_uri, str(input_video_path))
        except Exception as e:
            return JobResult(
                analysis_id=job.analysis_id,
                status='failed',
                error_code='DOWNLOAD_FAILED',
                error_message=f"Failed to download input video: {str(e)}",
            )

        # Load policy config if specified
        config = Config()
        if job.policy_name:
            # TODO: Load policy from storage or config service
            # For now, use default config
            pass

        # Run engine analysis
        try:
            result = analyze_video(str(input_video_path), config)
        except Exception as e:
            return JobResult(
                analysis_id=job.analysis_id,
                status='failed',
                error_code='ENGINE_ERROR',
                error_message=f"Engine analysis failed: {str(e)}",
            )

        # Write evidence artifacts
        evidence_dir.mkdir(exist_ok=True)
        result_dict = result.to_dict()
        
        # Write summary JSON
        summary_path = evidence_dir / "summary.json"
        with open(summary_path, 'w') as f:
            json.dump(result_dict, f, indent=2)

        # Write evidence plots and visualizations if available
        from engine.evidence import write_evidence
        import logging
        logger = logging.getLogger(__name__)
        try:
            logger.info(f"Writing evidence artifacts to {evidence_dir}, video: {input_video_path}")
            evidence_paths = write_evidence(
                str(evidence_dir),
                result_dict,
                config,
                input_video_path=str(input_video_path),
            )
            logger.info(f"Evidence artifacts written: {list(evidence_paths.keys())}")
            if evidence_paths.get("roi_masks"):
                logger.info(f"ROI masks generated: {evidence_paths['roi_masks']}")
        except Exception as e:
            # Evidence writing failure is non-fatal
            logger.error(f"Evidence writing failed (non-fatal): {e}", exc_info=True)
            evidence_paths = {}

        # Create evidence index
        index_data = {
            "config_version": config.config_version,
            "artifacts": evidence_paths,
        }
        index_path = evidence_dir / "index.json"
        with open(index_path, 'w') as f:
            json.dump(index_data, f, indent=2)

        # Upload evidence folder
        try:
            uploaded_keys = storage.upload_folder(
                str(evidence_dir),
                job.output_uri_prefix or f"evidence/{job.analysis_id}"
            )
        except Exception as e:
            return JobResult(
                analysis_id=job.analysis_id,
                status='failed',
                error_code='UPLOAD_FAILED',
                error_message=f"Failed to upload evidence: {str(e)}",
            )

        # Extract metrics summary (sqi, features, scoring)
        metrics_summary = {}
        if result.metrics:
            metrics_summary = {
                'sqi': result.metrics.get('sqi', {}),
                'features': result.metrics.get('features', {}),
                'scoring': result.metrics.get('scoring', {}),
            }

        # Compact diagnostics for API (ingest, face windows, roi/rppg summaries)
        metrics_diagnostics = None
        if result.metrics:
            face_data = result.metrics.get('face') or {}
            roi_data = result.metrics.get('roi') or {}
            rppg_data = result.metrics.get('rppg') or {}
            metrics_diagnostics = {
                'ingest': result.metrics.get('ingest'),
                'face': {'windows': face_data.get('windows', [])},
                'roi': roi_data.get('summary'),
                'rppg': rppg_data.get('summary'),
            }

        # Build JobResult
        return JobResult(
            analysis_id=job.analysis_id,
            status='done',
            verdict=result.verdict.value,
            score=result.score,
            confidence=result.confidence,
            reasons=result.reasons,
            metrics_summary=metrics_summary,
            metrics=metrics_diagnostics,
            evidence_index=f"{job.output_uri_prefix}/index.json",
            engine_version=config.config_version,
            policy_version=job.policy_name or 'default',
        )

    except Exception as e:
        return JobResult(
            analysis_id=job.analysis_id,
            status='failed',
            error_code='INTERNAL_ERROR',
            error_message=f"Unexpected error: {str(e)}",
        )
    finally:
        # Cleanup temp directory
        if temp_dir and temp_dir.exists():
            import shutil
            shutil.rmtree(temp_dir, ignore_errors=True)
