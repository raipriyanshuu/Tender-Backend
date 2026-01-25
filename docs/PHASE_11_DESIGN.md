# Phase 11: Error Handling & Monitoring

## 🎯 Objectives

Establish a comprehensive error handling and monitoring system that:
- Provides visibility into system health across all services
- Enables rapid debugging and issue resolution
- Alerts operators to critical failures
- Tracks performance and error trends
- Ensures graceful degradation under failure conditions
- Prepares the system for production deployment (Phase 13)

## 🏗️ Architecture Alignment

**Builds on:**
- Phase 3: Existing error classification, retry logic, structured logging
- Phase 4: LLM error handling, parsing errors
- Phase 7: Orchestrator error handling
- Phase 9: Aggregation error handling
- Phase 10: Frontend error display

**Prepares for:**
- Phase 12: Testing & Optimization (health checks for test environments)
- Phase 13: Documentation & Deployment (production monitoring setup)

**Constraints:**
- No Redis (Phase 8 skipped) → database + logs as primary sources
- No over-engineering → practical, actionable monitoring
- Maintain existing error handling patterns
- All monitoring queryable via database views and API endpoints

---

## 📋 Components

### 1. Enhanced Health Check System

**Purpose:** Verify all services are operational and can communicate

**Implementation:**

#### 1.1 Backend Health Endpoint
- **Endpoint:** `GET /health`
- **Checks:**
  - Database connectivity (connection pool status)
  - Worker API reachability (`/health` on worker)
  - Shared filesystem accessibility (read/write test)
  - Recent batch processing success rate
- **Response Format:**
```json
{
  "status": "healthy" | "degraded" | "unhealthy",
  "timestamp": "2026-01-22T12:00:00Z",
  "checks": {
    "database": { "status": "ok", "latency_ms": 5 },
    "worker_api": { "status": "ok", "latency_ms": 12 },
    "filesystem": { "status": "ok", "disk_usage_percent": 45 },
    "recent_batches": { "status": "ok", "success_rate_percent": 95 }
  }
}
```

#### 1.2 Worker Health Endpoint (Enhanced)
- **Endpoint:** `GET /health` (already exists, enhance)
- **Additional Checks:**
  - OpenAI API connectivity (test request)
  - File parser libraries loaded
  - Disk space for temp files
  - Average processing time (last 10 files)

---

### 2. Comprehensive Error Reporting

**Purpose:** Provide detailed, actionable error information for debugging

#### 2.1 Error Dashboard Endpoint
- **Endpoint:** `GET /api/monitoring/errors`
- **Query Parameters:**
  - `time_range`: `1h`, `24h`, `7d` (default: 24h)
  - `error_type`: filter by error type
  - `batch_id`: filter by batch
- **Response:**
```json
{
  "summary": {
    "total_errors": 45,
    "by_type": {
      "RATE_LIMIT": 12,
      "TIMEOUT": 8,
      "PARSE_ERROR": 15,
      "LLM_ERROR": 5,
      "UNKNOWN": 5
    },
    "batches_affected": 8
  },
  "recent_errors": [
    {
      "batch_id": "batch_abc",
      "doc_id": "doc_xyz",
      "filename": "tender.pdf",
      "error_type": "PARSE_ERROR",
      "error_message": "Failed to parse PDF: corrupt file",
      "retry_count": 3,
      "timestamp": "2026-01-22T12:00:00Z"
    }
  ]
}
```

#### 2.2 Batch Error Details
- **Endpoint:** `GET /api/batches/:batchId/errors`
- **Purpose:** Detailed error breakdown for a specific batch
- **Response:** List of all failed files with full error context

#### 2.3 Failed Files Retry Endpoint
- **Endpoint:** `POST /api/batches/:batchId/retry-failed`
- **Purpose:** Manual retry trigger for failed files in a batch
- **Action:** Resets failed files to `pending` status, triggers reprocessing

---

### 3. Performance Monitoring

**Purpose:** Track system performance and identify bottlenecks

#### 3.1 Performance Metrics Endpoint
- **Endpoint:** `GET /api/monitoring/performance`
- **Metrics:**
  - Average processing time per file
  - Average batch processing time
  - Files processed per hour
  - Success rate (overall, by file type)
  - Worker utilization (active workers, queue depth)
  - LLM API latency and rate limit hits

#### 3.2 Database View Enhancement
- Extend `processing_performance_metrics` view with:
  - File type breakdown (PDF vs Word vs Excel)
  - LLM token usage estimates
  - Peak processing hours
  - Worker error rates

---

### 4. Alerting System (Lightweight)

**Purpose:** Notify operators of critical issues without external dependencies

#### 4.1 Critical Error Detection
- **Trigger Conditions:**
  - Batch failure rate > 50% in last hour
  - Worker API unreachable for > 5 minutes
  - Database connection failures
  - Disk space > 90% full
  - LLM API errors > 20 in 10 minutes

#### 4.2 Alert Mechanism (Extensible)
- **Phase 11 Implementation:** Log critical alerts with `CRITICAL` level
- **Future Extension Points:**
  - Email notifications (SMTP)
  - Webhook to Slack/Discord
  - PagerDuty integration
- **Alert Log Table:**
```sql
CREATE TABLE system_alerts (
  id SERIAL PRIMARY KEY,
  alert_type VARCHAR(50) NOT NULL,
  severity VARCHAR(20) NOT NULL, -- CRITICAL, WARNING, INFO
  message TEXT NOT NULL,
  context JSONB,
  created_at TIMESTAMP DEFAULT now(),
  resolved_at TIMESTAMP,
  resolved_by VARCHAR(100)
);
```

---

### 5. Graceful Error Handling

**Purpose:** Ensure system degrades gracefully under failure conditions

#### 5.1 Backend Orchestrator Enhancements
- **Partial batch completion:** If some files fail but max retries reached, mark batch as `completed_with_errors` and proceed to aggregation with successful files
- **Worker timeout handling:** If worker doesn't respond within 5 minutes, mark file as `TIMEOUT` error and continue
- **Concurrency throttling:** Reduce concurrency if error rate spikes (e.g., rate limit errors)

#### 5.2 Frontend Error Messages
- **User-facing error states:**
  - `queued` → "Your files are being prepared..."
  - `extracting` → "Extracting files from ZIP..."
  - `processing` → "Processing X of Y files..." (with progress bar)
  - `completed_with_errors` → "Completed with X files failed. View details."
  - `failed` → "Processing failed. Please contact support or retry."
- **Error action buttons:**
  - "Retry Failed Files" → calls retry endpoint
  - "View Error Details" → shows per-file error messages
  - "Download Error Report" → CSV export of failed files

#### 5.3 Worker Error Boundaries
- **File-level isolation:** One file failure never crashes the entire batch
- **LLM fallback:** If LLM extraction fails after retries, save partial/empty extraction and mark as failed (don't crash worker)
- **Memory limits:** Set max file size (e.g., 50MB) to prevent OOM errors

---

### 6. Filesystem Monitoring & Cleanup

**Purpose:** Prevent disk space issues and manage file lifecycle

#### 6.1 Disk Space Monitor
- **Check:** Shared volume disk usage every 5 minutes
- **Alert:** If usage > 80%, log warning with oldest batches
- **Action:** Archive or delete batches older than 30 days

#### 6.2 Cleanup Script
- **File:** `scripts/cleanup_old_batches.py`
- **Logic:**
  - Find batches completed > 30 days ago
  - Move ZIP and extracted files to archive (or delete)
  - Update `processing_jobs.archived_at` timestamp
  - Log cleanup actions
- **Scheduling:** Cron job or manual trigger

#### 6.3 Filesystem Health Endpoint
- **Endpoint:** `GET /api/monitoring/filesystem`
- **Response:**
```json
{
  "disk_usage_percent": 67,
  "disk_usage_gb": 45.2,
  "disk_total_gb": 67.5,
  "old_batches_count": 12,
  "suggested_cleanup_batches": ["batch_old_1", "batch_old_2"]
}
```

---

### 7. Structured Logging Enhancements

**Purpose:** Improve log searchability and debugging efficiency

#### 7.1 Log Levels
- **CRITICAL:** System-wide failures (DB down, worker unreachable)
- **ERROR:** File processing failures, LLM errors
- **WARNING:** Retries, rate limits, degraded performance
- **INFO:** Batch start/complete, file processing success
- **DEBUG:** Detailed parsing, chunking, LLM prompts (disabled in prod)

#### 7.2 Contextual Logging
- All logs include: `batch_id`, `doc_id` (if applicable), `timestamp`, `service` (backend vs worker)
- Correlation IDs for end-to-end tracing (batch_id serves this purpose)

#### 7.3 Log Aggregation (Optional for Phase 13)
- **Phase 11:** Logs to local files with rotation
- **Phase 13:** Optionally integrate with log aggregation tools (e.g., Loki, ELK, CloudWatch)

---

### 8. Rate Limiting & Throttling

**Purpose:** Prevent external API abuse and enforce fair usage

#### 8.1 LLM API Rate Limiting (Worker-side)
- **Implementation:** Token bucket or sliding window
- **Config:** `MAX_LLM_REQUESTS_PER_MINUTE` (default: 60)
- **Behavior:** If limit reached, sleep until window resets (already handled by retry logic)

#### 8.2 Backend API Rate Limiting
- **Endpoint Protection:** `/upload-tender`, `/api/batches/:id/process`
- **Implementation:** Express middleware (e.g., `express-rate-limit`)
- **Limits:**
  - Upload: 10 uploads per IP per hour
  - Process: 5 batch triggers per IP per minute
- **Response:** `429 Too Many Requests` with `Retry-After` header

---

### 9. Database Monitoring

**Purpose:** Ensure database health and optimize query performance

#### 9.1 Connection Pool Monitoring
- **Metrics:** Active connections, idle connections, wait time
- **Alerts:** If connection pool exhausted, log critical alert

#### 9.2 Slow Query Logging
- Enable PostgreSQL `log_min_duration_statement` (e.g., 1000ms)
- Identify slow queries in batch status views or file processing queries
- Optimize with indexes or query rewrites

#### 9.3 Database Health Endpoint
- **Endpoint:** `GET /api/monitoring/database`
- **Response:**
```json
{
  "status": "ok",
  "connection_pool": {
    "total": 20,
    "active": 5,
    "idle": 15,
    "waiting": 0
  },
  "table_sizes": {
    "processing_jobs": "1.2 MB",
    "file_extractions": "45.3 MB",
    "run_summaries": "8.7 MB"
  },
  "recent_slow_queries": []
}
```

---

### 10. Monitoring Dashboard (Minimal UI)

**Purpose:** Centralized view of system health for operators

#### 10.1 Simple Admin Dashboard (Optional)
- **Route:** `/admin` (password protected, separate from main UI)
- **Sections:**
  - System Health (green/yellow/red status)
  - Active Batches (count, progress)
  - Recent Errors (last 20 errors)
  - Performance Metrics (charts: files/hour, avg time)
  - Alerts (unresolved critical alerts)
- **Implementation:** Simple HTML page served by backend, fetching monitoring endpoints

#### 10.2 CLI Monitoring Tool (Alternative)
- **Script:** `scripts/monitor.sh` or `scripts/monitor.py`
- **Commands:**
  - `./monitor.sh status` → system health
  - `./monitor.sh errors` → recent errors
  - `./monitor.sh batch <batch_id>` → batch details
  - `./monitor.sh cleanup` → trigger cleanup script

---

## 📊 Database Schema Changes

### New Table: `system_alerts`

```sql
CREATE TABLE system_alerts (
  id SERIAL PRIMARY KEY,
  alert_type VARCHAR(50) NOT NULL, -- e.g., 'WORKER_UNREACHABLE', 'DISK_FULL'
  severity VARCHAR(20) NOT NULL, -- 'CRITICAL', 'WARNING', 'INFO'
  message TEXT NOT NULL,
  context JSONB, -- Additional details (e.g., batch_id, error_count)
  created_at TIMESTAMP DEFAULT now(),
  resolved_at TIMESTAMP,
  resolved_by VARCHAR(100)
);

CREATE INDEX idx_system_alerts_severity ON system_alerts(severity, created_at DESC);
CREATE INDEX idx_system_alerts_unresolved ON system_alerts(resolved_at) WHERE resolved_at IS NULL;
```

### New View: `error_summary_by_type`

```sql
CREATE OR REPLACE VIEW error_summary_by_type AS
SELECT 
  fe.error_type,
  COUNT(*) as total_errors,
  COUNT(DISTINCT fe.run_id) as batches_affected,
  ROUND(AVG(fe.retry_count), 2) as avg_retry_count,
  MIN(fe.processing_completed_at) as first_occurrence,
  MAX(fe.processing_completed_at) as last_occurrence
FROM file_extractions fe
WHERE fe.status = 'FAILED' AND fe.error_type IS NOT NULL
GROUP BY fe.error_type
ORDER BY total_errors DESC;
```

---

## 🔄 Implementation Sequence

1. **Backend Health Endpoint** (`src/routes/health.js`)
2. **Enhanced Worker Health** (`workers/api/main.py`)
3. **Error Reporting Endpoints** (`src/routes/monitoring.js`)
4. **Database Schema Changes** (`migrations/005_monitoring_tables.sql`)
5. **Graceful Error Handling** (update `orchestrator.js`, `extractor.py`)
6. **Filesystem Monitoring** (`scripts/cleanup_old_batches.py`, new endpoint)
7. **Rate Limiting Middleware** (`src/middleware/rateLimiter.js`)
8. **Alerting System** (`src/services/alerting.js`)
9. **Frontend Error UI** (update `FileUploadZone.tsx`, batch status display)
10. **CLI Monitoring Tool** (`scripts/monitor.py`)

---

## ✅ Success Criteria

- All services have health check endpoints returning accurate status
- Operators can view system health, errors, and performance in real-time
- Critical alerts are logged and queryable
- Failed batches can be manually retried
- System degrades gracefully under failure (no cascading crashes)
- Disk space is monitored and cleanup is automated
- Rate limiting prevents API abuse
- Frontend displays user-friendly error messages with actionable buttons
- All monitoring data is queryable via API or database views

---

## 🚀 Future Enhancements (Post-Phase 13)

- **External Alerting:** Email, Slack, PagerDuty integrations
- **Advanced Metrics:** Prometheus + Grafana for time-series metrics
- **Distributed Tracing:** OpenTelemetry for request tracing across services
- **Anomaly Detection:** ML-based detection of unusual error patterns
- **Self-Healing:** Automatic worker restarts, batch retries on transient failures
- **Cost Tracking:** LLM API usage and cost per batch

---

## 📌 Alignment Summary

**Phase 11 aligns with:**
- **Existing error handling:** Builds on Phase 3/4 error classification and retry logic
- **Database-centric architecture:** Uses views and tables for monitoring (no external tools required)
- **Simplicity principle:** Practical, actionable monitoring without over-engineering
- **Production readiness:** Prepares for Phase 13 deployment with health checks and alerting
- **User experience:** Frontend error handling ensures users always know what's happening

**No breaking changes:** All existing functionality remains intact; Phase 11 adds observability and resilience layers on top.
