# Environment Variables Reference

## Backend (.env)

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/tender_db

# Worker API Configuration
WORKER_API_URL=http://localhost:8000

# Redis Queue Configuration
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_KEY=tender:jobs

# Queue Retry
QUEUE_RETRY_DELAY_MS=2000

# Storage Configuration
STORAGE_BASE_PATH=./shared
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted

# Processing Configuration
WORKER_CONCURRENCY=3
MAX_RETRY_ATTEMPTS=3

# Rate Limiting
UPLOAD_RATE_LIMIT_PER_HOUR=10
PROCESS_RATE_LIMIT_PER_MINUTE=5

# Batch Retention
BATCH_RETENTION_DAYS=30

# Server Configuration
PORT=3001
CORS_ORIGIN=http://localhost:5173
NODE_ENV=development

# File Upload Limits
MAX_FILE_SIZE_MB=100

# ZIP Extraction
MAX_ZIP_DEPTH=3
```

## Workers (.env)

```bash
# Database Configuration
DATABASE_URL=postgresql://user:password@localhost:5432/tender_db
DATABASE_MAX_CONNECTIONS=10
DATABASE_TIMEOUT=30

# Storage Configuration
STORAGE_BASE_PATH=/shared
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted
STORAGE_TEMP_DIR=temp
STORAGE_LOGS_DIR=logs

# LLM Configuration
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4096
OPENAI_RATE_LIMIT_RPM=60

# OCR Configuration (for scanned PDFs)
ENABLE_OCR=true
OCR_MAX_PAGES=50

# GAEB Configuration (German tender format)
GAEB_ENABLED=true

# Processing Configuration
MAX_RETRY_ATTEMPTS=3
RETRY_BASE_DELAY_SECONDS=2.0
RETRY_MAX_DELAY_SECONDS=60.0
BATCH_PROCESSING_TIMEOUT=1800

# Redis Queue Configuration
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_KEY=tender:jobs

# Queue Retry
QUEUE_RETRY_DELAY_MS=2000

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=/shared/logs/worker.log
```

## Quick Setup

### Backend
```bash
cd tenderBackend
cp ENV_VARS_REQUIRED.md .env
# Edit .env with your actual values
npm install
npm start
```

### Workers
```bash
cd workers
# Create .env manually with values from ENV_VARS_REQUIRED.md
pip install -r requirements.txt
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000
```
