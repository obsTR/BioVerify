# BioVerify Backend

Backend services for the BioVerify video deepfake detection system.

## Architecture

- **API Service**: FastAPI REST API for job creation and status queries
- **Worker Service**: Celery worker for background video processing
- **Storage**: Abstraction layer supporting local filesystem (dev) and S3 (prod)
- **Database**: PostgreSQL for job status and results

## Services

### API Service

REST API endpoints:
- `POST /analyses` - Upload video and create analysis job
- `GET /analyses/{id}` - Get analysis status and results
- `GET /analyses/{id}/evidence` - Get evidence artifacts with signed URLs
- `GET /health` - Health check

### Worker Service

Celery worker processes analysis jobs:
- Downloads video from storage
- Runs detection engine
- Uploads evidence artifacts
- Updates database with results

## Setup

### Local Development

1. Install dependencies:
```bash
pip install -r backend/requirements.txt
pip install -r requirements.txt  # Engine dependencies
```

2. Set up environment variables (see `.env.example`)

3. Start services with Docker Compose:
```bash
docker-compose up -d
```

4. Initialize MinIO bucket (if using S3):
```bash
docker-compose exec minio mc alias set local http://localhost:9000 minioadmin minioadmin
docker-compose exec minio mc mb local/bioverify
```

5. Run database migrations (if needed):
```bash
# Alembic migrations can be added here
```

6. Start API:
```bash
uvicorn backend.api.main:app --reload
```

7. Start worker:
```bash
celery -A backend.tasks.celery_app worker --loglevel=info
```

### Docker Compose

All services can be started with:
```bash
docker-compose up
```

Services:
- `api` - FastAPI service (port 8000)
- `worker` - Celery worker
- `postgres` - PostgreSQL database (port 5432)
- `redis` - Redis broker (port 6379)
- `minio` - S3-compatible storage (ports 9000, 9001)

## Testing

Run smoke test:
```bash
python scripts/smoke_test.py
```

## Configuration

Environment variables:
- `DATABASE_URL` - PostgreSQL connection string
- `CELERY_BROKER_URL` - Redis broker URL
- `STORAGE_BACKEND` - 'local' or 's3'
- `API_AUTH_TOKEN` - API authentication token
- S3 configuration (if using S3 backend)
