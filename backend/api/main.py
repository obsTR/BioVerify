import uuid
import os
import time
import logging
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any

from backend.database.db import init_db, get_db
from backend.database.models import Analysis, AnalysisStatus
from backend.storage.factory import create_storage_backend
from backend.storage.base import StorageConfig
from backend.storage.local import LocalStorageBackend
from backend.runner.runner import JobSpec
from backend.tasks import enqueue_analysis_job
from engine import Config

app = FastAPI(title="BioVerify API", version="0.1.0")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TimingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request/response times."""
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        path = request.url.path
        method = request.method
        
        response = await call_next(request)
        
        process_time = time.time() - start_time
        status_code = response.status_code
        
        # Log slow requests (>1s) or all requests for debugging
        if process_time > 1.0:
            logger.warning(
                f"SLOW REQUEST: {method} {path} - {process_time:.3f}s - Status: {status_code}"
            )
        else:
            logger.info(
                f"{method} {path} - {process_time:.3f}s - Status: {status_code}"
            )
        
        response.headers["X-Process-Time"] = str(process_time)
        return response


# Add timing middleware (before CORS so it times everything)
app.add_middleware(TimingMiddleware)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize on startup
@app.on_event("startup")
async def startup_event():
    database_url = os.getenv("DATABASE_URL", "postgresql://bioverify:bioverify@localhost/bioverify")
    init_db(database_url)

    # Clean up analyses stuck in RUNNING state from previous OOM kills
    try:
        from backend.tasks.celery_app import cleanup_stuck_analyses
        cleanup_stuck_analyses()
    except Exception as e:
        logger.warning(f"Cleanup failed: {e}")

    # Ensure S3 bucket exists when using S3 storage (e.g. MinIO)
    if os.getenv("STORAGE_BACKEND") == "s3":
        storage_config = StorageConfig(
            backend="s3",
            base_path=os.getenv("STORAGE_BASE_PATH"),
            bucket_name=os.getenv("S3_BUCKET_NAME"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        )
        try:
            storage = create_storage_backend(storage_config)
            if hasattr(storage, "ensure_bucket_exists"):
                storage.ensure_bucket_exists()
        except Exception as e:
            import logging
            logging.getLogger("uvicorn.error").warning("Could not ensure S3 bucket exists: %s", e)


# Simple auth check (replace with proper auth in production)
async def verify_token(authorization: Optional[str] = Header(None)):
    """Simple token verification."""
    if not authorization:
        raise HTTPException(status_code=401, detail="Authorization header required")
    token = authorization.replace("Bearer ", "")
    expected_token = os.getenv("API_AUTH_TOKEN", "dev-token")
    if token != expected_token:
        raise HTTPException(status_code=401, detail="Invalid token")
    return token


# Request/Response models
class AnalysisResponse(BaseModel):
    analysis_id: str
    status: str


class AnalysisStatusResponse(BaseModel):
    analysis_id: str
    status: str
    policy_name: Optional[str] = None
    result_json: Optional[Dict[str, Any]] = None
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    created_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class EvidenceResponse(BaseModel):
    index: Dict[str, Any]
    signed_urls: Dict[str, str]


class HealthResponse(BaseModel):
    status: str
    engine_version: Optional[str] = None
    policy_versions: Optional[list] = None


@app.post("/analyses", response_model=AnalysisResponse)
async def create_analysis(
    video: UploadFile = File(...),
    policy_name: Optional[str] = None,
    token: str = Depends(verify_token),
):
    """Create a new analysis job."""
    # Validate file type
    if not video.content_type or not video.content_type.startswith('video/'):
        raise HTTPException(status_code=400, detail="File must be a video")

    # Validate file size (100MB max)
    max_size = 100 * 1024 * 1024
    content = await video.read()
    if len(content) > max_size:
        raise HTTPException(status_code=400, detail="File size exceeds 100MB limit")

    # Generate analysis ID
    analysis_id = str(uuid.uuid4())

    # Initialize storage
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

    # Save uploaded file temporarily
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as tmp_file:
        tmp_file.write(content)
        tmp_path = tmp_file.name

    try:
        # Upload to storage
        input_uri = f"uploads/{analysis_id}/input.mp4"
        storage.upload_file(tmp_path, input_uri)

        # Create database record
        db_gen = get_db()
        db = next(db_gen)
        try:
            analysis = Analysis(
                analysis_id=analysis_id,
                status=AnalysisStatus.QUEUED,
                policy_name=policy_name,
                input_uri=input_uri,
                evidence_prefix=f"evidence/{analysis_id}",
            )
            db.add(analysis)
            db.commit()
        finally:
            db.close()

        # Enqueue job
        job_spec = JobSpec(
            analysis_id=analysis_id,
            input_uri=input_uri,
            policy_name=policy_name,
            output_uri_prefix=f"evidence/{analysis_id}",
        )
        enqueue_analysis_job(job_spec)

        return AnalysisResponse(analysis_id=analysis_id, status="queued")

    finally:
        # Cleanup temp file
        os.unlink(tmp_path)


@app.get("/analyses", response_model=list[AnalysisStatusResponse])
async def list_analyses(
    limit: int = 50,
    offset: int = 0,
    token: str = Depends(verify_token),
):
    """List all analyses, most recent first."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        analyses = (
            db.query(Analysis)
            .order_by(Analysis.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [AnalysisStatusResponse(**a.to_dict()) for a in analyses]
    finally:
        db.close()


@app.get("/analyses/{analysis_id}", response_model=AnalysisStatusResponse)
async def get_analysis(
    analysis_id: str,
    token: str = Depends(verify_token),
):
    """Get analysis status and results."""
    db_gen = get_db()
    db = next(db_gen)
    try:
        analysis = db.query(Analysis).filter(Analysis.analysis_id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        return AnalysisStatusResponse(**analysis.to_dict())
    finally:
        db.close()


@app.get("/analyses/{analysis_id}/evidence", response_model=EvidenceResponse)
async def get_evidence(
    analysis_id: str,
    token: str = Depends(verify_token),
):
    """Get evidence index and signed URLs."""
    t0 = time.time()
    
    # Database query
    t_db_start = time.time()
    db_gen = get_db()
    db = next(db_gen)
    try:
        analysis = db.query(Analysis).filter(Analysis.analysis_id == analysis_id).first()
        if not analysis:
            raise HTTPException(status_code=404, detail="Analysis not found")
        if analysis.status != AnalysisStatus.DONE:
            raise HTTPException(status_code=400, detail="Analysis not completed")
    finally:
        db.close()
    t_db = time.time() - t_db_start
    logger.info(f"Evidence endpoint - DB query: {t_db:.3f}s")

    # Get cached storage backend (much faster than creating new one)
    t_storage_start = time.time()
    storage = _get_storage_backend()
    t_storage = time.time() - t_storage_start
    logger.info(f"Evidence endpoint - Storage init: {t_storage:.3f}s")

    # Load evidence index (optimize: read directly if local storage)
    t_index_start = time.time()
    import json
    index_key = f"{analysis.evidence_prefix}/index.json"
    
    if isinstance(storage, LocalStorageBackend):
        # For local storage, read directly without temp file
        index_path = storage._get_full_path(index_key)
        if not index_path.exists():
            raise HTTPException(status_code=404, detail="Evidence index not found")
        with open(index_path, 'r') as f:
            index_data = json.load(f)
    else:
        # For S3, use temp file (necessary for boto3)
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
            storage.download_file(index_key, tmp_file.name)
            with open(tmp_file.name, 'r') as f:
                index_data = json.load(f)
            os.unlink(tmp_file.name)
    
    t_index = time.time() - t_index_start
    logger.info(f"Evidence endpoint - Index load: {t_index:.3f}s")

    # Generate signed URLs for all artifacts
    t_urls_start = time.time()
    signed_urls = {}
    artifacts = index_data.get('artifacts', {})
    
    logger.info(f"Evidence artifacts in index: {list(artifacts.keys())}")
    if 'roi_masks' in artifacts:
        logger.info(f"ROI masks paths: {artifacts['roi_masks']}")
    
    # Flatten artifact paths
    artifact_paths = []
    for key, value in artifacts.items():
        if isinstance(value, list):
            artifact_paths.extend(value)
        elif isinstance(value, str):
            artifact_paths.append(value)

    logger.info(f"Total artifact paths to sign: {len(artifact_paths)}")
    
    # Generate URLs (this is fast for local storage, just string formatting)
    for artifact_path in artifact_paths:
        if artifact_path.startswith(analysis.evidence_prefix):
            relative_path = artifact_path
        else:
            relative_path = f"{analysis.evidence_prefix}/{artifact_path}"
        
        try:
            signed_url = storage.get_signed_url(relative_path, expires_in=3600)
            signed_urls[artifact_path] = signed_url
        except Exception as e:
            logger.warning(f"Could not generate signed URL for {relative_path}: {e}")
            pass
    
    t_urls = time.time() - t_urls_start
    logger.info(f"Evidence endpoint - URL generation: {t_urls:.3f}s")
    logger.info(f"Generated {len(signed_urls)} signed URLs out of {len(artifact_paths)} artifacts")
    
    t_total = time.time() - t0
    logger.info(f"Evidence endpoint - TOTAL TIME: {t_total:.3f}s (DB: {t_db:.3f}s, Storage: {t_storage:.3f}s, Index: {t_index:.3f}s, URLs: {t_urls:.3f}s)")

    return EvidenceResponse(index=index_data, signed_urls=signed_urls)


# Cache storage backend instance (created once, reused)
_storage_backend_cache = None

def _get_storage_backend():
    """Get or create cached storage backend."""
    global _storage_backend_cache
    if _storage_backend_cache is None:
        storage_config = StorageConfig(
            backend=os.getenv("STORAGE_BACKEND", "local"),
            base_path=os.getenv("STORAGE_BASE_PATH", "./storage"),
            bucket_name=os.getenv("S3_BUCKET_NAME"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
        )
        _storage_backend_cache = create_storage_backend(storage_config)
    return _storage_backend_cache


def _get_media_type(filename: str) -> str:
    """Determine media type from filename."""
    ext = filename.lower().split('.')[-1] if '.' in filename else ''
    media_types = {
        'jpg': 'image/jpeg',
        'jpeg': 'image/jpeg',
        'png': 'image/png',
        'gif': 'image/gif',
        'json': 'application/json',
        'mp4': 'video/mp4',
        'webm': 'video/webm',
    }
    return media_types.get(ext, 'application/octet-stream')


@app.get("/api/storage/{object_key:path}")
async def serve_storage_file(object_key: str):
    """Serve files from local storage backend with caching."""
    t0 = time.time()
    storage = _get_storage_backend()
    
    # For local storage, serve directly
    if isinstance(storage, LocalStorageBackend):
        from pathlib import Path
        full_path = storage._get_full_path(object_key)
        if not full_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Determine media type
        media_type = _get_media_type(full_path.name)
        
        # Get file stats (for ETag and logging)
        file_stats = full_path.stat()
        file_size_mb = file_stats.st_size / (1024 * 1024)
        
        # Add caching headers (1 hour cache for images, 5 min for others)
        cache_max_age = 3600 if media_type.startswith('image/') else 300
        headers = {
            "Content-Disposition": f'inline; filename="{full_path.name}"',
            "Cache-Control": f"public, max-age={cache_max_age}",
            "ETag": f'"{file_stats.st_mtime}-{file_stats.st_size}"',
        }
        
        t_serve = time.time() - t0
        if t_serve > 0.5:  # Log slow file serves
            logger.warning(f"SLOW FILE SERVE: {object_key} ({file_size_mb:.2f} MB) - {t_serve:.3f}s")
        else:
            logger.debug(f"File serve: {object_key} ({file_size_mb:.2f} MB) - {t_serve:.3f}s")
        
        return FileResponse(
            str(full_path),
            media_type=media_type,
            headers=headers,
        )
    
    # For S3, generate a presigned URL redirect
    try:
        signed_url = storage.get_signed_url(object_key, expires_in=3600)
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url=signed_url)
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"File not found: {e}")


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    config = Config()
    return HealthResponse(
        status="ok",
        engine_version=config.config_version,
        policy_versions=["default"],  # TODO: Load from policy service
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
