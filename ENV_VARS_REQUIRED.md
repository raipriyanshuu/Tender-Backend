# Environment Variables Reference

## Required Variables

### Database
```bash
DATABASE_URL=postgresql://user:password@host:5432/dbname
```

### Storage Backend Selection
```bash
# Options: "local" | "r2"
STORAGE_BACKEND=local
```

## Storage Configuration

### Local Storage (STORAGE_BACKEND=local)
```bash
STORAGE_BASE_PATH=/shared
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted
STORAGE_TEMP_DIR=temp
STORAGE_LOGS_DIR=logs
```

### Cloudflare R2 Storage (STORAGE_BACKEND=r2)
```bash
# Required
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key_id
R2_SECRET_ACCESS_KEY=your_r2_secret_access_key
R2_BUCKET_NAME=tender-storage

# Optional
R2_ENDPOINT_URL=https://{account_id}.r2.cloudflarestorage.com  # Auto-generated if not provided
R2_REGION=auto  # Cloudflare uses "auto"
STORAGE_ENVIRONMENT=prod  # Options: "dev" | "staging" | "prod"
```

## Redis Queue
```bash
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_KEY=tender:jobs
```

## LLM Configuration
```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o
OPENAI_MAX_TOKENS=16384
OPENAI_RATE_LIMIT_RPM=60
```

## OCR Configuration
```bash
ENABLE_OCR=true
OCR_MAX_PAGES=50
```

## GAEB Configuration
```bash
GAEB_ENABLED=true
```

## Processing Configuration
```bash
MAX_RETRY_ATTEMPTS=3
RETRY_BASE_DELAY_SECONDS=2.0
RETRY_MAX_DELAY_SECONDS=60.0
BATCH_PROCESSING_TIMEOUT=1800
WORKER_CONCURRENCY=3
```

## Rate Limiting
```bash
UPLOAD_RATE_LIMIT_PER_HOUR=100
PROCESS_RATE_LIMIT_PER_MINUTE=50
MAX_FILE_SIZE_MB=100
```

## Server Configuration
```bash
PORT=3001
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173
```

## Logging
```bash
LOG_LEVEL=INFO  # Options: DEBUG | INFO | WARNING | ERROR | CRITICAL
LOG_FORMAT=json  # Options: json | text
LOG_FILE_PATH=/shared/logs/worker.log
```

## Example .env Files

### Local Development (.env)
```bash
# Database
DATABASE_URL=postgresql://postgres:password@localhost:5432/tender_db

# Storage (Local)
STORAGE_BACKEND=local
STORAGE_BASE_PATH=./shared

# Redis
REDIS_URL=redis://localhost:6379

# LLM
OPENAI_API_KEY=sk-your-key-here

# Server
PORT=3001
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173
```

### Production (.env)
```bash
# Database
DATABASE_URL=postgresql://user:pass@prod-db.example.com:5432/tender_db

# Storage (R2)
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=abc123
R2_ACCESS_KEY_ID=your_access_key
R2_SECRET_ACCESS_KEY=your_secret_key
R2_BUCKET_NAME=tender-storage
STORAGE_ENVIRONMENT=prod

# Redis (Managed Service)
REDIS_URL=redis://prod-redis.example.com:6379

# LLM
OPENAI_API_KEY=sk-prod-key-here

# Server
PORT=3001
NODE_ENV=production
CORS_ORIGIN=https://your-frontend.com
```

## Notes

- **Never commit .env files to git** - use .env.example instead
- **R2 credentials are required** only when `STORAGE_BACKEND=r2`
- **Local storage requires writable filesystem** - not suitable for ephemeral containers
- **Environment prefixes** (dev/staging/prod) allow sharing one R2 bucket
