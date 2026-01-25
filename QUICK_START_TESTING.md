# 🚀 Quick Start - Localhost Testing (5 Minutes)

**For full details, see**: `docs/LOCALHOST_TESTING_GUIDE.md`

---

## ⚡ Prerequisites (1 minute)

Ensure installed:
- Node.js 18+: `node --version`
- Python 3.11+: `python --version`
- PostgreSQL 15+: `psql --version`

---

## 🔧 Setup (2 minutes)

### 1. Database
```bash
psql -U postgres -c "CREATE DATABASE tender_db;"
cd tenderBackend
node run-migration.js migrations/001_processing_jobs_table.sql
node run-migration.js migrations/002_extend_file_extractions.sql
node run-migration.js migrations/003_database_views.sql
node run-migration.js migrations/005_monitoring_tables.sql
```

### 2. Environment Files

**Backend** (`tenderBackend/.env`):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tender_db
WORKER_API_URL=http://localhost:8000
STORAGE_BASE_PATH=./shared
PORT=3001
NODE_ENV=development
```

**Workers** (`workers/.env`):
```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/tender_db
STORAGE_BASE_PATH=C:\Users\DELL\OneDrive\Desktop\tenderBackend\shared
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4o-mini
LOG_LEVEL=INFO
```

### 3. Install Dependencies
```bash
# Backend
cd tenderBackend
npm install

# Workers
pip install -r workers/requirements.txt
```

### 4. Initialize Storage
```bash
# Windows
.\scripts\init_shared_volume.ps1

# macOS/Linux
./scripts/init_shared_volume.sh
```

---

## 🎬 Start Services (30 seconds)

**Terminal 1 - Backend**:
```bash
cd tenderBackend
npm start
```

**Terminal 2 - Workers**:
```bash
cd tenderBackend
uvicorn workers.api.main:app --host 0.0.0.0 --port 8000
```

**Expected**:
- Backend: `🚀 Server running on http://localhost:3001`
- Workers: `Uvicorn running on http://0.0.0.0:8000`

---

## ✅ Verify Health (10 seconds)

```bash
curl http://localhost:3001/health
curl http://localhost:8000/health
```

**Expected**: Both return `{"status": "ok"}` or `{"status": "healthy"}`

---

## 🧪 Test Upload → Process → Summary (2 minutes)

### 1. Upload ZIP
```bash
curl -X POST http://localhost:3001/upload-tender \
  -F "file=@sample.zip"
```

**Response**: `{"success": true, "batch_id": "batch_xxx"}`

### 2. Trigger Processing
```bash
curl -X POST http://localhost:3001/api/batches/batch_xxx/process
```

**Response**: `{"success": true, "message": "Processing started"}`

### 3. Check Status (poll every 10s)
```bash
curl http://localhost:3001/api/batches/batch_xxx/status
```

**Watch for**: `"batch_status": "queued"` → `"extracting"` → `"processing"` → `"completed"`

### 4. Get Summary
```bash
curl http://localhost:3001/api/batches/batch_xxx/summary
```

**Expected**: Aggregated `ui_json` with tender data

---

## 🎉 Success!

If you reached this point:
- ✅ All services running
- ✅ Database connected
- ✅ File processing works
- ✅ LLM extraction works
- ✅ Aggregation works

**Next**: See full testing guide for monitoring endpoints, error scenarios, and load testing.

---

## 🐛 Quick Troubleshooting

| Issue | Quick Fix |
|-------|-----------|
| Database error | Check PostgreSQL is running |
| Worker unreachable | Verify worker on port 8000 |
| LLM error | Check `OPENAI_API_KEY` in `.env` |
| File not found | Use absolute path in `STORAGE_BASE_PATH` |

**Full troubleshooting**: `docs/LOCALHOST_TESTING_GUIDE.md` → Troubleshooting section

---

**Quick Start Version**: 1.0  
**For detailed walkthrough**: Read `docs/LOCALHOST_TESTING_GUIDE.md`
