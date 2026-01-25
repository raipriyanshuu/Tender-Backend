# 🧪 Localhost Testing Guide - Complete Walkthrough

**Project**: Tender Document Processing System  
**Phases Covered**: 1-11 (Database → Monitoring)  
**Estimated Time**: 30-45 minutes  
**Difficulty**: Intermediate

---

## 📋 Table of Contents

1. [Prerequisites & Dependencies](#prerequisites--dependencies)
2. [Environment Setup](#environment-setup)
3. [Database Setup & Migrations](#database-setup--migrations)
4. [Backend Server Setup](#backend-server-setup)
5. [Worker Service Setup](#worker-service-setup)
6. [Testing Workflow](#testing-workflow)
7. [Monitoring Endpoints](#monitoring-endpoints)
8. [Troubleshooting](#troubleshooting)

---

## 🔧 Prerequisites & Dependencies

### System Requirements
- **OS**: Windows 10/11, macOS, or Linux
- **RAM**: 8GB minimum (16GB recommended)
- **Disk**: 10GB free space
- **Internet**: Required for LLM API calls

### Software Prerequisites

#### 1. Node.js (v18+)
```bash
# Check if installed
node --version  # Should show v18.x.x or higher

# Install from https://nodejs.org if needed
```

#### 2. Python (3.11+)
```bash
# Check if installed
python --version  # Should show 3.11.x or higher

# Install from https://python.org if needed
```

#### 3. PostgreSQL (v15+)
```bash
# Check if installed
psql --version  # Should show PostgreSQL 15.x or higher

# Install from https://www.postgresql.org/download/
# OR use Docker:
docker run -d --name tender-postgres \
  -e POSTGRES_PASSWORD=postgres \
  -e POSTGRES_DB=tender_db \
  -p 5432:5432 \
  postgres:15
```

#### 4. Git
```bash
# Check if installed
git --version

# Install from https://git-scm.com if needed
```

---

## ⚙️ Environment Setup

### Step 1: Clone Repository (if not already done)
```bash
cd C:\Users\DELL\OneDrive\Desktop
# Repositories should already be at:
# - tenderBackend/
# - project/ (frontend)
```

### Step 2: Create Backend Environment File

**File**: `tenderBackend/.env`

```bash
cd tenderBackend
```

Create `.env` file with these contents:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tender_db

# Worker API Configuration
WORKER_API_URL=http://localhost:8000

# Storage Configuration
STORAGE_BASE_PATH=./shared
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted

# Processing Configuration
WORKER_CONCURRENCY=3
MAX_RETRY_ATTEMPTS=3

# Rate Limiting
UPLOAD_RATE_LIMIT_PER_HOUR=100
PROCESS_RATE_LIMIT_PER_MINUTE=50

# Batch Retention
BATCH_RETENTION_DAYS=30

# Server Configuration
PORT=3001
CORS_ORIGIN=http://localhost:5173
NODE_ENV=development

# File Upload Limits
MAX_FILE_SIZE_MB=100
```

**What this does**: Configures backend to connect to local PostgreSQL, communicate with workers on port 8000, and use local `./shared` directory for file storage.

---

### Step 3: Create Worker Environment File

**File**: `workers/.env`

```bash
cd workers
```

Create `.env` file with these contents:

```env
# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tender_db
DATABASE_MAX_CONNECTIONS=10
DATABASE_TIMEOUT=30

# Storage Configuration
STORAGE_BASE_PATH=C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted
STORAGE_TEMP_DIR=temp
STORAGE_LOGS_DIR=logs

# LLM Configuration
OPENAI_API_KEY=sk-your-actual-api-key-here
OPENAI_MODEL=gpt-4o-mini
OPENAI_MAX_TOKENS=4096
OPENAI_RATE_LIMIT_RPM=60

# Processing Configuration
MAX_RETRY_ATTEMPTS=3
RETRY_BASE_DELAY_SECONDS=2.0
RETRY_MAX_DELAY_SECONDS=60.0
BATCH_PROCESSING_TIMEOUT=1800

# Logging Configuration
LOG_LEVEL=INFO
LOG_FORMAT=json
LOG_FILE_PATH=C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared\logs\worker.log
```

**⚠️ IMPORTANT**: Replace `sk-your-actual-api-key-here` with your real OpenAI API key from https://platform.openai.com/api-keys

**What this does**: Configures workers to use absolute paths for Windows compatibility, connect to same database, and authenticate with OpenAI API.

---

### Step 4: Initialize Shared Storage

**Windows (PowerShell)**:
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
.\scripts\init_shared_volume.ps1
```

**macOS/Linux**:
```bash
cd tenderBackend
chmod +x scripts/init_shared_volume.sh
./scripts/init_shared_volume.sh
```

**Expected Output**:
```
✅ Created directory: shared/uploads
✅ Created directory: shared/extracted
✅ Created directory: shared/temp
✅ Created directory: shared/logs
✅ Created directory: shared/.metadata/locks
Shared volume initialized successfully!
```

**What this does**: Creates required directory structure for file uploads, extraction, temporary files, and logs.

---

## 🗄️ Database Setup & Migrations

### Step 1: Create Database

```bash
# Connect to PostgreSQL
psql -U postgres -h localhost

# Create database
CREATE DATABASE tender_db;

# Exit
\q
```

**Expected Output**:
```
CREATE DATABASE
```

**What this does**: Creates empty PostgreSQL database named `tender_db`.

---

### Step 2: Run Migrations (in order)

```bash
cd tenderBackend

# Migration 1: Processing Jobs Table
node run-migration.js migrations/001_processing_jobs_table.sql
```

**Expected Output**:
```
✅ Migration completed successfully: 001_processing_jobs_table.sql
```

```bash
# Migration 2: Extend File Extractions
node run-migration.js migrations/002_extend_file_extractions.sql
```

**Expected Output**:
```
✅ Migration completed successfully: 002_extend_file_extractions.sql
```

```bash
# Migration 3: Database Views
node run-migration.js migrations/003_database_views.sql
```

**Expected Output**:
```
✅ Migration completed successfully: 003_database_views.sql
```

```bash
# Migration 4: Seed Test Data (OPTIONAL)
node run-migration.js migrations/004_seed_test_data.sql
```

**Expected Output**:
```
✅ Migration completed successfully: 004_seed_test_data.sql
Inserted 5 test batches with various statuses
```

```bash
# Migration 5: Monitoring Tables
node run-migration.js migrations/005_monitoring_tables.sql
```

**Expected Output**:
```
✅ Migration completed successfully: 005_monitoring_tables.sql
```

**What this does**: Creates all database tables, views, and indexes. Seeds with test data for verification.

---

### Step 3: Verify Database Schema

```bash
psql -U postgres -d tender_db

# List tables
\dt

# Expected tables:
# - processing_jobs
# - file_extractions
# - run_summaries
# - system_alerts

# List views
\dv

# Expected views:
# - batch_status_summary
# - failed_files_report
# - processing_performance_metrics
# - active_batches_monitor
# - batch_history_summary
# - error_summary_by_type

# Exit
\q
```

**What this does**: Confirms all tables and views were created successfully.

---

## 🚀 Backend Server Setup

### Step 1: Install Dependencies

```bash
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
npm install
```

**Expected Output**:
```
added 150 packages in 25s
✅ Dependencies installed successfully
```

**What this does**: Installs all Node.js packages including express, pg, multer, axios, express-rate-limit, adm-zip.

---

### Step 2: Start Backend Server

```bash
npm start
```

**Expected Output**:
```
╔═══════════════════════════════════════════════════════╗
║                                                       ║
║   🚀 Tender Backend API Server                       ║
║                                                       ║
║   Server running on: http://localhost:3001           ║
║   Environment: development                           ║
║   CORS Origin: http://localhost:5173                 ║
║                                                       ║
║   API Documentation: http://localhost:3001/          ║
║                                                       ║
╚═══════════════════════════════════════════════════════╝

✅ Connected to PostgreSQL database
```

**What this does**: Starts Express server on port 3001, connects to database, and exposes REST API endpoints.

**⚠️ Keep this terminal open!** The server needs to keep running.

---

### Step 3: Test Backend Health

Open new terminal:

```bash
curl http://localhost:3001/health
```

**Expected Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-22T12:00:00.000Z",
  "checks": {
    "database": {
      "status": "ok",
      "latency_ms": 5
    },
    "worker_api": {
      "status": "error",
      "error": "connect ECONNREFUSED"
    },
    "filesystem": {
      "status": "ok",
      "path": "./shared"
    },
    "recent_batches": {
      "status": "ok",
      "success_rate_percent": 100
    }
  }
}
```

**Note**: `worker_api` will show error until we start the worker service (next section). This is expected.

**What this does**: Verifies backend can connect to database and filesystem. Worker check will pass once workers are running.

---

## 🤖 Worker Service Setup

### Step 1: Install Python Dependencies

Open new terminal:

```bash
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip install -r requirements.txt
```

**Expected Output**:
```
Successfully installed:
- sqlalchemy-2.0.25
- psycopg2-binary-2.9.9
- python-dotenv-1.0.0
- PyPDF2-3.0.1
- python-docx-1.1.0
- openpyxl-3.1.2
- openai-1.10.0
- fastapi-0.110.0
- uvicorn-0.27.1
- pytest-7.4.3
```

**What this does**: Installs all Python packages for file parsing, LLM calls, and FastAPI server.

---

### Step 2: Verify OpenAI API Key

```bash
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('API Key:', os.getenv('OPENAI_API_KEY')[:10] + '...')"
```

**Expected Output**:
```
API Key: sk-proj-Ab...
```

**If you see "API Key: None"**: Your `.env` file is missing or `OPENAI_API_KEY` is not set correctly.

---

### Step 3: Start Worker Service

```bash
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Expected Output**:
```
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [12345]
INFO:     Started server process [12346]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

**What this does**: Starts FastAPI worker server on port 8000 with auto-reload enabled for development.

**⚠️ Keep this terminal open!** The worker service needs to keep running.

---

### Step 4: Test Worker Health

Open new terminal:

```bash
curl http://localhost:8000/health
```

**Expected Response**:
```json
{
  "status": "ok",
  "checks": {
    "database": "ok",
    "storage_path": "C:\\Users\\DELL\\OneDrive\\Desktop\\tenderBackend\\shared",
    "disk_usage_percent": 45.23,
    "parsers_ready": true,
    "llm_configured": true
  }
}
```

**What this does**: Verifies worker can connect to database, access shared filesystem, and has LLM configured.

**✅ If you see this, all systems are ready!**

---

### Step 5: Verify Backend-Worker Communication

```bash
curl http://localhost:3001/health
```

**Expected Response** (now with worker_api healthy):
```json
{
  "status": "healthy",
  "timestamp": "2026-01-22T12:00:00.000Z",
  "checks": {
    "database": { "status": "ok", "latency_ms": 5 },
    "worker_api": { 
      "status": "ok", 
      "latency_ms": 12,
      "details": {
        "status": "ok",
        "checks": {
          "database": "ok",
          "parsers_ready": true,
          "llm_configured": true
        }
      }
    },
    "filesystem": { "status": "ok", "path": "./shared" },
    "recent_batches": { "status": "ok", "success_rate_percent": 100 }
  }
}
```

**What this does**: Confirms backend can successfully communicate with worker service.

---

## 🧪 Testing Workflow

### Test 1: Create Sample ZIP File

Create a test ZIP file with 2-3 sample PDF files:

**Option A: Using existing files**
```bash
# Create test directory
mkdir test-files
cd test-files

# Copy 2-3 PDF files to this directory
# Then create ZIP:
# Windows: Right-click → Send to → Compressed folder
# macOS: Select files → Right-click → Compress
# Linux: zip sample.zip file1.pdf file2.pdf file3.pdf
```

**Option B: Create dummy PDFs** (for testing only)
```bash
# Install reportlab if needed
pip install reportlab

# Create dummy PDFs
python -c "
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

for i in range(3):
    c = canvas.Canvas(f'test{i+1}.pdf', pagesize=letter)
    c.drawString(100, 750, f'Test Tender Document {i+1}')
    c.drawString(100, 700, 'Project: Highway Construction')
    c.drawString(100, 650, 'Deadline: 2026-12-31')
    c.showPage()
    c.save()
"

# Create ZIP
zip sample.zip test1.pdf test2.pdf test3.pdf
```

**Expected Result**: You should have `sample.zip` file (~50KB - 5MB depending on content).

---

### Test 2: Upload ZIP via API

```bash
curl -X POST http://localhost:3001/upload-tender \
  -F "file=@sample.zip" \
  -F "uploaded_by=test_user"
```

**Expected Response**:
```json
{
  "success": true,
  "batch_id": "batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**What happens**:
1. Backend receives ZIP file
2. Validates file type (.zip) and size (<100MB)
3. Saves ZIP to `shared/uploads/batch_xxx.zip`
4. Creates `processing_jobs` record with status `"queued"`
5. Returns `batch_id` for tracking

**Save the `batch_id`** - you'll need it for next steps!

---

### Test 3: Check Batch Status (Before Processing)

```bash
curl http://localhost:3001/api/batches/batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890/status
```

**Replace** `batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890` with your actual batch_id.

**Expected Response**:
```json
{
  "batch_id": "batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "batch_status": "queued",
  "zip_path": "uploads/batch_xxx.zip",
  "total_files": 0,
  "files_tracked": 0,
  "files_success": 0,
  "files_failed": 0,
  "files_processing": 0,
  "files_pending": 0,
  "progress_percent": 0,
  "batch_created_at": "2026-01-22T12:00:00.000Z"
}
```

**What this shows**: Batch is uploaded but not yet extracted or processed.

---

### Test 4: Trigger Batch Processing

```bash
curl -X POST http://localhost:3001/api/batches/batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890/process \
  -H "Content-Type: application/json" \
  -d "{\"concurrency\": 2}"
```

**Expected Response** (immediate):
```json
{
  "success": true,
  "message": "Processing started for batch batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890",
  "batch_id": "batch_a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

**What happens** (async):
1. Backend calls `extractBatch()` → unzips files to `shared/extracted/batch_xxx/`
2. Creates `file_extractions` records for each .pdf/.doc/.xls file
3. Updates `processing_jobs` status to `"processing"`
4. Calls worker API for each file (2 concurrent)
5. Worker parses file → chunks text → calls LLM → saves `extracted_json`
6. After all files done, calls aggregation
7. Updates status to `"completed"` or `"completed_with_errors"`

**⏱️ This takes time!** For 3 files: ~2-5 minutes (depending on file size and LLM response time).

---

### Test 5: Monitor Processing Progress

Poll status every 10 seconds:

```bash
# In a loop (Linux/macOS):
while true; do 
  curl -s http://localhost:3001/api/batches/YOUR_BATCH_ID/status | jq .
  sleep 10
done

# Windows (PowerShell):
while ($true) {
  Invoke-RestMethod http://localhost:3001/api/batches/YOUR_BATCH_ID/status | ConvertTo-Json
  Start-Sleep 10
}

# Or manually run every 10 seconds:
curl http://localhost:3001/api/batches/YOUR_BATCH_ID/status
```

**Expected Status Transitions**:

**1. Extracting** (~5-10 seconds):
```json
{
  "batch_status": "extracting",
  "total_files": 0,
  "progress_percent": 0
}
```

**2. Processing** (~1-3 minutes):
```json
{
  "batch_status": "processing",
  "total_files": 3,
  "files_pending": 1,
  "files_processing": 2,
  "files_success": 0,
  "progress_percent": 0
}
```

**3. Partial Progress** (~2 minutes):
```json
{
  "batch_status": "processing",
  "total_files": 3,
  "files_success": 2,
  "files_processing": 1,
  "progress_percent": 66.67
}
```

**4. Completed** (~3-5 minutes):
```json
{
  "batch_status": "completed",
  "total_files": 3,
  "files_success": 3,
  "files_failed": 0,
  "progress_percent": 100,
  "completed_at": "2026-01-22T12:05:00.000Z"
}
```

**What to watch**:
- `batch_status` changes: `queued` → `extracting` → `processing` → `completed`
- `files_success` increments as each file finishes
- `progress_percent` increases to 100

---

### Test 6: Check Individual File Results

```bash
curl http://localhost:3001/api/batches/YOUR_BATCH_ID/files
```

**Expected Response**:
```json
{
  "batch_id": "batch_xxx",
  "files": [
    {
      "doc_id": "doc_uuid_1",
      "filename": "test1.pdf",
      "file_type": "pdf",
      "file_path": "extracted/batch_xxx/test1.pdf",
      "status": "SUCCESS",
      "extracted_json": {
        "meta": {
          "tender_id": "HWY-2026-001",
          "organization": "Department of Transportation"
        },
        "executive_summary": {
          "location_de": "Hamburg, Germany"
        },
        "timeline_milestones": {
          "submission_deadline_de": "2026-12-31"
        },
        "mandatory_requirements": [
          {
            "requirement_de": "ISO 9001 Certification",
            "category_de": "Quality Management"
          }
        ],
        "risks": [
          {
            "risk_de": "Strict deadline requirements",
            "severity": "high"
          }
        ]
      },
      "processing_started_at": "2026-01-22T12:01:00Z",
      "processing_completed_at": "2026-01-22T12:02:30Z",
      "processing_duration_ms": 90000,
      "retry_count": 0
    },
    {
      "doc_id": "doc_uuid_2",
      "filename": "test2.pdf",
      "status": "SUCCESS",
      "extracted_json": { ... }
    },
    {
      "doc_id": "doc_uuid_3",
      "filename": "test3.pdf",
      "status": "SUCCESS",
      "extracted_json": { ... }
    }
  ]
}
```

**What this shows**: Per-file processing results with LLM-extracted data.

---

### Test 7: Get Aggregated Summary

```bash
curl http://localhost:3001/api/batches/YOUR_BATCH_ID/summary
```

**Expected Response**:
```json
{
  "id": "uuid",
  "run_id": "batch_xxx",
  "ui_json": {
    "meta": {
      "tender_id": "HWY-2026-001",
      "organization": "Department of Transportation"
    },
    "executive_summary": {
      "location_de": "Hamburg, Germany"
    },
    "timeline_milestones": {
      "submission_deadline_de": "2026-12-31"
    },
    "mandatory_requirements": [
      {
        "requirement_de": "ISO 9001 Certification",
        "category_de": "Quality Management"
      },
      {
        "requirement_de": "5 years experience",
        "category_de": "Experience"
      }
    ],
    "risks": [
      {
        "risk_de": "Strict deadline requirements",
        "severity": "high"
      }
    ]
  },
  "total_files": 3,
  "success_files": 3,
  "failed_files": 0,
  "status": "completed",
  "created_at": "2026-01-22T12:05:30Z"
}
```

**What this shows**: Merged/aggregated data from all successfully processed files.

**✅ If you see this, the ENTIRE workflow worked end-to-end!**

---

## 📊 Monitoring Endpoints

### Test 8: Check System Errors

```bash
curl "http://localhost:3001/api/monitoring/errors?time_range=24h"
```

**Expected Response** (if no errors):
```json
{
  "summary": {
    "total_errors": 0,
    "by_type": {},
    "batches_affected": 0
  },
  "recent_errors": []
}
```

**Expected Response** (if some errors occurred):
```json
{
  "summary": {
    "total_errors": 5,
    "by_type": {
      "PARSE_ERROR": 2,
      "LLM_ERROR": 1,
      "TIMEOUT": 2
    },
    "batches_affected": 2
  },
  "recent_errors": [
    {
      "batch_id": "batch_xxx",
      "doc_id": "doc_yyy",
      "filename": "corrupt.pdf",
      "error_type": "PARSE_ERROR",
      "error_message": "Failed to parse PDF: corrupt.pdf",
      "retry_count": 3,
      "timestamp": "2026-01-22T12:00:00Z"
    }
  ]
}
```

**What this shows**: Error trends by type, helping identify systematic issues.

---

### Test 9: Check Performance Metrics

```bash
curl http://localhost:3001/api/monitoring/performance
```

**Expected Response**:
```json
{
  "metrics": [
    {
      "processing_date": "2026-01-22",
      "total_files_processed": 15,
      "successful_files": 14,
      "failed_files": 1,
      "avg_processing_seconds": 45.2,
      "min_processing_seconds": 12.5,
      "max_processing_seconds": 98.3,
      "files_with_retries": 2,
      "avg_retry_count": 0.13,
      "errors_retryable": 1,
      "errors_permanent": 0,
      "errors_timeout": 0,
      "errors_rate_limit": 0,
      "errors_parse": 1,
      "errors_llm": 0
    }
  ]
}
```

**What this shows**: Daily performance statistics and error distribution.

---

### Test 10: Check Database Health

```bash
curl http://localhost:3001/api/monitoring/database
```

**Expected Response**:
```json
{
  "status": "ok",
  "connection_pool": {
    "total": 20,
    "idle": 18,
    "waiting": 0
  },
  "table_sizes": [
    {
      "table": "file_extractions",
      "size": "1248 kB"
    },
    {
      "table": "processing_jobs",
      "size": "64 kB"
    },
    {
      "table": "run_summaries",
      "size": "32 kB"
    }
  ]
}
```

**What this shows**: Database connection pool utilization and table sizes.

---

### Test 11: Check Filesystem Usage

```bash
curl http://localhost:3001/api/monitoring/filesystem
```

**Expected Response**:
```json
{
  "disk_usage_mb": 125,
  "disk_usage_bytes": 131072000,
  "storage_path": "./shared",
  "old_batches_count": 0,
  "suggested_cleanup_batches": [],
  "note": "For full disk stats, use OS-level monitoring tools"
}
```

**What this shows**: Storage directory size and batches eligible for cleanup.

---

## 🔍 Troubleshooting

### Issue 1: "Cannot connect to database"

**Error**:
```
❌ Unexpected error on idle client
Error: connect ECONNREFUSED 127.0.0.1:5432
```

**Solution**:
1. Check PostgreSQL is running:
   ```bash
   # Windows: Services → PostgreSQL
   # macOS: brew services list
   # Linux: systemctl status postgresql
   ```
2. Verify DATABASE_URL in `.env` matches your PostgreSQL credentials
3. Test connection manually:
   ```bash
   psql -U postgres -h localhost -d tender_db
   ```

---

### Issue 2: "Worker API unreachable"

**Error** in backend health check:
```json
{
  "worker_api": {
    "status": "error",
    "error": "connect ECONNREFUSED"
  }
}
```

**Solution**:
1. Check worker service is running:
   ```bash
   curl http://localhost:8000/health
   ```
2. If not running, restart:
   ```bash
   cd tenderBackend
   uvicorn workers.api.main:app --host 0.0.0.0 --port 8000
   ```
3. Verify `WORKER_API_URL=http://localhost:8000` in backend `.env`

---

### Issue 3: "File not found" during processing

**Error** in file_extractions:
```json
{
  "status": "FAILED",
  "error_type": "PERMANENT",
  "error": "File not found: extracted/batch_xxx/file.pdf"
}
```

**Solution**:
1. Check `STORAGE_BASE_PATH` in workers `.env` uses **absolute path**:
   ```env
   STORAGE_BASE_PATH=C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared
   ```
2. Verify files were extracted:
   ```bash
   ls shared/extracted/batch_xxx/
   ```
3. Check file permissions (should be readable)

---

### Issue 4: "LLM API error"

**Error**:
```json
{
  "error_type": "LLM_ERROR",
  "error": "Invalid API key"
}
```

**Solution**:
1. Verify OpenAI API key in workers `.env`:
   ```bash
   python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
   ```
2. Check API key is valid at https://platform.openai.com/api-keys
3. Ensure you have credits/billing enabled on OpenAI account

---

### Issue 5: "Rate limit exceeded"

**Error**:
```json
{
  "error_type": "RATE_LIMIT",
  "error": "Rate limit reached for gpt-4o-mini"
}
```

**Solution**:
1. Wait 60 seconds (rate limit window resets)
2. Reduce `OPENAI_RATE_LIMIT_RPM` in workers `.env`:
   ```env
   OPENAI_RATE_LIMIT_RPM=30  # Reduce from 60 to 30
   ```
3. Upgrade OpenAI plan for higher rate limits

---

### Issue 6: "File size too large"

**Error**:
```json
{
  "error": "File size exceeds maximum limit of 100MB",
  "max_size_mb": 100,
  "file_size_mb": 150
}
```

**Solution**:
1. Reduce ZIP file size (remove large files)
2. OR increase limit in backend `.env`:
   ```env
   MAX_FILE_SIZE_MB=200  # Increase to 200MB
   ```
3. Restart backend server for changes to take effect

---

## ✅ Success Checklist

After completing all tests, you should have:

- [x] Backend server running on http://localhost:3001
- [x] Worker service running on http://localhost:8000
- [x] Database with all migrations applied
- [x] Shared storage directory initialized
- [x] Health checks passing for both services
- [x] Successfully uploaded a ZIP file
- [x] Successfully processed files through worker
- [x] Retrieved aggregated summary
- [x] Monitored system via monitoring endpoints
- [x] No critical errors in logs

**If all checked**: 🎉 **Your system is fully operational!**

---

## 📝 Next Steps

1. **Test with real tender documents** (PDFs with actual tender content)
2. **Test error scenarios** (corrupt files, unsupported formats)
3. **Run load tests** (multiple concurrent uploads)
4. **Proceed to Phase 13**: Production deployment

---

## 📞 Need Help?

Check documentation:
- `PHASE_11_REVIEW_COMPLETE.md` - Production readiness report
- `FIXES_APPLIED.md` - Recent bug fixes
- `ENV_VARS_REQUIRED.md` - Environment variable reference
- `CRITICAL_FIXES_PHASE_11.md` - Security & performance checklists

---

**Testing Guide Version**: 1.0  
**Last Updated**: 2026-01-22  
**Phases Covered**: 1-11
