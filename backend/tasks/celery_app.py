from celery import Celery
import os
from datetime import datetime

from backend.runner.runner import JobSpec, run_analysis
from backend.storage.factory import create_storage_backend
from backend.storage.base import StorageConfig
from backend.database import db as dbmod
from backend.database.models import Analysis, AnalysisStatus

# Initialize Celery
celery_app = Celery(
    'bioverify',
    broker=os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0'),
    backend=os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0'),
)

celery_app.conf.task_serializer = 'json'
celery_app.conf.accept_content = ['json']
celery_app.conf.result_serializer = 'json'
celery_app.conf.timezone = 'UTC'
celery_app.conf.enable_utc = True
celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_max_memory_per_child = 1500000  # 1.5 GB, restart worker if exceeded

def ensure_db_initialized() -> None:
    """
    Ensure SQLAlchemy engine/session are initialized in *this* process.

    Celery prefork workers can end up with processes where module-level globals
    (SessionLocal) are not initialized as expected; calling this at task start
    makes DB access reliable.
    """
    if dbmod.SessionLocal is not None:
        return
    database_url = os.getenv(
        "DATABASE_URL", "postgresql://bioverify:bioverify@localhost/bioverify"
    )
    dbmod.init_db(database_url)


@celery_app.task(
    name='bioverify.process_analysis',
    bind=True,
    max_retries=1,
    soft_time_limit=300,
    time_limit=360,
)
def process_analysis_task(self, job_dict: dict):
    """Celery task to process an analysis job."""
    ensure_db_initialized()
    job = JobSpec(**job_dict)

    db_gen = dbmod.get_db()
    db = next(db_gen)
    try:
        analysis = db.query(Analysis).filter(Analysis.analysis_id == job.analysis_id).first()
        if not analysis:
            raise ValueError(f"Analysis {job.analysis_id} not found")

        if analysis.status in [AnalysisStatus.DONE, AnalysisStatus.FAILED]:
            result_dict = analysis.to_dict()
            db.close()
            return result_dict

        analysis.status = AnalysisStatus.RUNNING
        analysis.started_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()

    storage_config = StorageConfig(
        backend=os.getenv("STORAGE_BACKEND", "local"),
        base_path=os.getenv("STORAGE_BASE_PATH", "./storage"),
        bucket_name=os.getenv("S3_BUCKET_NAME"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
        aws_region=os.getenv("AWS_REGION", "us-east-1"),
        endpoint_url=os.getenv("S3_ENDPOINT_URL"),
    )
    storage = create_storage_backend(storage_config)

    try:
        result = run_analysis(job, storage)
    except Exception as exc:
        _mark_analysis_failed(job.analysis_id, str(exc))
        raise

    ensure_db_initialized()
    db_gen = dbmod.get_db()
    db = next(db_gen)
    try:
        analysis = db.query(Analysis).filter(Analysis.analysis_id == job.analysis_id).first()
        if analysis:
            analysis.status = result.status
            analysis.finished_at = datetime.utcnow()
            analysis.result_json = result.to_dict()
            if result.status == 'failed':
                analysis.error_code = result.error_code
                analysis.error_message = result.error_message
            db.commit()
    finally:
        db.close()

    return result.to_dict()


def _mark_analysis_failed(analysis_id: str, error_message: str):
    """Mark an analysis as failed in the database."""
    try:
        ensure_db_initialized()
        db_gen = dbmod.get_db()
        db = next(db_gen)
        try:
            analysis = db.query(Analysis).filter(Analysis.analysis_id == analysis_id).first()
            if analysis and analysis.status == AnalysisStatus.RUNNING:
                analysis.status = AnalysisStatus.FAILED
                analysis.finished_at = datetime.utcnow()
                analysis.error_message = error_message[:500]
                db.commit()
        finally:
            db.close()
    except Exception:
        pass


def cleanup_stuck_analyses():
    """Mark analyses stuck in RUNNING state as FAILED (e.g. after OOM kill)."""
    try:
        ensure_db_initialized()
        db_gen = dbmod.get_db()
        db = next(db_gen)
        try:
            stuck = db.query(Analysis).filter(
                Analysis.status == AnalysisStatus.RUNNING
            ).all()
            for analysis in stuck:
                analysis.status = AnalysisStatus.FAILED
                analysis.finished_at = datetime.utcnow()
                analysis.error_message = "Worker process was killed (likely out of memory). Try a shorter or lower-resolution video."
            if stuck:
                db.commit()
                print(f"Cleaned up {len(stuck)} stuck analyses")
        finally:
            db.close()
    except Exception as e:
        print(f"Cleanup failed: {e}")


def enqueue_analysis_job(job: JobSpec):
    """Enqueue an analysis job."""
    job_dict = {
        'analysis_id': job.analysis_id,
        'input_uri': job.input_uri,
        'policy_name': job.policy_name,
        'output_uri_prefix': job.output_uri_prefix,
        'metadata': job.metadata or {},
    }
    process_analysis_task.delay(job_dict)
