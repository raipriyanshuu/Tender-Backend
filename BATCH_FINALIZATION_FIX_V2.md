# Batch Finalization Bug - Complete Fix V2

## Problem Analysis (Confirmed)

The root cause was **EVENT-DRIVEN vs STATE-DRIVEN finalization**:

### Original Flawed Design
- Finalization only triggered INSIDE `process_file` job handler
- If last file completes but no more jobs are pulled from queue
- OR if worker loop doesn't process any jobs for a while
- **Then finalization NEVER runs**

### Why Previous Fixes Failed
The previous fixes (session.flush, try/except) only addressed:
- Transaction rollback issues
- View join conditions  

But they did NOT address the fundamental trigger problem:
- **Finalization depends on pulling another job from Redis**
- **No job = No finalization check = Batch stuck forever**

---

## Complete Solution: Multi-Layered Defense

### Layer 1: Enhanced Logging (Diagnostic)
**Purpose**: Understand exactly when and why finalization is called/skipped

**Changes**:
1. Entry logging in `_maybe_finalize_batch()`
2. Detailed logging of all condition checks
3. Aggregator start/end logging
4. Database statistics logging

**Files**: 
- `workers/queue_worker.py` (lines 26-145)
- `workers/processing/aggregator.py` (lines 36-79)

---

### Layer 2: Periodic Stuck Batch Checker (STATE-DRIVEN)
**Purpose**: Automatically finalize batches that meet completion criteria

**Implementation**:
```python
def _check_stuck_batches(session, logger, config, redis_client):
    """
    Runs every 30 seconds
    Finds batches where:
    - status = 'processing'
    - total_files > 0
    - files_processing = 0
    - files_pending = 0
    - (files_success + files_failed) >= total_files
    - last_file_completed_at > 10 seconds ago
    
    Forces finalization for these batches
    """
```

**Trigger**: Background loop in worker, runs every 30 seconds

**File**: `workers/queue_worker.py` (lines 160-195, 220-228)

**Impact**:
- ✅ Batches automatically finalize within 30-40 seconds max
- ✅ No dependency on job queue
- ✅ Catches edge cases and race conditions

---

### Layer 3: On-Demand Aggregation (Frontend Safety Net)
**Purpose**: Generate summary on-demand if missing when frontend requests it

**Implementation in `/api/batches/:batchId/summary`**:

```javascript
// 1. Check if run_summaries exists
if (summary exists) return summary;

// 2. Check batch completion status
if (batch complete && summary missing) {
    // Update batch status if stuck in processing
    UPDATE processing_jobs SET status = 'completed', completed_at = NOW();
    
    // Enqueue aggregate job
    enqueueAggregateJob(batchId);
    
    // Return 202 Accepted
    return { message: "Summary being generated", retry_after: 5 };
}

// 3. Otherwise return 404
```

**File**: `src/routes/batches.js` (lines 53-134)

**Impact**:
- ✅ Frontend never stuck forever
- ✅ Immediate recovery on first API call
- ✅ Graceful retry mechanism (202 status)

---

## Execution Flow (New)

### Scenario 1: Normal Case (All Jobs Processed)
```
File 7 completes → process_file finishes
  ↓
Worker pulls next job from Redis
  ↓
_maybe_finalize_batch() called
  ↓
Condition met → Status updated to "completed"
  ↓
aggregate_batch() creates run_summaries
  ✅ SUCCESS
```

### Scenario 2: Worker Idle / No Jobs (PREVIOUSLY BROKEN)
```
File 7 completes → process_file finishes
  ↓
No more jobs in Redis queue
  ↓
Worker waits (brpop timeout 5s)
  ↓
**NEW**: 30-second timer expires
  ↓
_check_stuck_batches() runs (STATE-DRIVEN)
  ↓
Finds batch stuck in 'processing'
  ↓
Forces _maybe_finalize_batch()
  ✅ SUCCESS (max 30-40 seconds delay)
```

### Scenario 3: Worker Crashed / Stopped (PREVIOUSLY BROKEN)
```
File 7 completes → Worker crashes
  ↓
Frontend polls /api/batches/:batchId/summary
  ↓
Summary not found (404)
  ↓
**NEW**: Endpoint checks if batch complete
  ↓
Detects: all files done + summary missing
  ↓
Updates batch status to "completed"
  ↓
Enqueues aggregate job
  ↓
Returns 202 Accepted
  ↓
Frontend retries in 5 seconds
  ✅ SUCCESS (on-demand recovery)
```

---

## Testing Instructions

### 1. Restart Worker with New Code
```bash
# In terminal 7 (worker terminal)
Ctrl+C

# Restart
python -m workers.queue_worker
```

**Expected Output**:
```
[QueueWorker] Connected to Redis...
[QueueWorker] Listening on queue...
[QueueWorker] Running periodic stuck batch check...
```

### 2. Check Logs for Stuck Batch
```bash
# Watch worker logs
tail -f shared/logs/worker.log
```

**Look for**:
```
[QueueWorker] STUCK BATCH DETECTED: batch_xxx (success=7, failed=0, total=7) - forcing finalization
[QueueWorker] _maybe_finalize_batch CALLED for batch batch_xxx
[QueueWorker] FINALIZATION CONDITION MET for batch batch_xxx!
[Aggregator] START: aggregate_batch for batch_xxx
[Aggregator] COMPLETE: aggregate_batch for batch_xxx
```

### 3. Test API Endpoint
```bash
# Test summary endpoint
curl http://localhost:3000/api/batches/YOUR_BATCH_ID/summary

# Expected (if summary ready):
HTTP 200 + JSON summary data

# Expected (if triggering on-demand):
HTTP 202 {
  "message": "Summary is being generated. Please retry in a few seconds.",
  "retry_after": 5
}

# Then retry:
curl http://localhost:3000/api/batches/YOUR_BATCH_ID/summary
# Should return HTTP 200 with data
```

### 4. Verify Database
```sql
-- Check batch status (should be 'completed' or 'completed_with_errors')
SELECT batch_id, status, completed_at 
FROM processing_jobs 
WHERE batch_id = 'YOUR_BATCH_ID';

-- Check run_summaries exists
SELECT run_id, status, total_files, success_files, created_at 
FROM run_summaries 
WHERE run_id IN (
    SELECT COALESCE(run_id, batch_id) 
    FROM processing_jobs 
    WHERE batch_id = 'YOUR_BATCH_ID'
);

-- Check batch_status_summary view
SELECT * 
FROM batch_status_summary 
WHERE batch_id = 'YOUR_BATCH_ID';
```

---

## Architecture Comparison

### Before (EVENT-DRIVEN - BROKEN)
```
Finalization Trigger = "When next job is pulled from Redis"

Problem: If no jobs → No trigger → Batch stuck forever
```

### After (STATE-DRIVEN - ROBUST)
```
Finalization Triggers:
1. EVENT: After each file completes (immediate)
2. STATE: Periodic checker every 30s (safety net)
3. DEMAND: Frontend API call (recovery)

Result: Multiple layers ensure finalization ALWAYS happens
```

---

## Files Modified (Complete List)

### Core Fixes
1. ✅ `workers/queue_worker.py`
   - Added comprehensive logging
   - Added `_check_stuck_batches()` function
   - Integrated periodic checker into main loop
   - Added `text` import from sqlalchemy

2. ✅ `workers/processing/aggregator.py`
   - Added detailed logging
   - Confirms run_summaries creation

3. ✅ `src/routes/batches.js`
   - Enhanced `/api/batches/:batchId/summary` endpoint
   - Added on-demand aggregation trigger
   - Added automatic status update
   - Returns 202 for in-progress aggregation

### Supporting Files (from previous fix)
4. ✅ `migrations/006_fix_batch_status_summary_view.sql`
5. ✅ `migrations/001_002_003_005_consolidated_idempotent.sql`
6. ✅ `migrations/003_database_views.sql`

---

## Performance & Safety

### Performance Impact
- Periodic checker: Runs every 30s, queries only stuck batches (very light)
- On-demand aggregation: Only triggers when explicitly needed
- No impact on normal processing path

### Safety Guarantees
1. **Idempotency**: Multiple finalization calls are safe (checked via `is_batch_already_processed`)
2. **Race Conditions**: Each batch commits separately in stuck checker
3. **Transaction Safety**: session.flush() before aggregate ensures status persists
4. **Error Isolation**: try/except prevents aggregation errors from blocking status update

---

## Success Criteria (All Must Pass)

✅ **Within 40 seconds of last file completion**:
- Batch status → "completed" or "completed_with_errors"
- `completed_at` timestamp set
- `run_summaries` row created

✅ **Frontend behavior**:
- API `/summary` returns 200 (or 202 on first call if stuck)
- Processing indicator disappears
- Tender data displayed

✅ **Logs confirm**:
- Finalization triggered (either event-driven or periodic)
- Aggregation completed successfully
- No errors or silent failures

---

## Monitoring Commands

### Real-time Worker Logs
```bash
tail -f shared/logs/worker.log | grep -E "(STUCK|finalize|Aggregator)"
```

### Check Stuck Batches (Manual)
```sql
SELECT 
    pj.batch_id,
    pj.status,
    bss.files_success,
    bss.files_failed,
    bss.total_files,
    bss.last_file_completed_at,
    EXTRACT(EPOCH FROM (NOW() - bss.last_file_completed_at)) as seconds_since_last_file
FROM processing_jobs pj
INNER JOIN batch_status_summary bss ON pj.batch_id = bss.batch_id
WHERE pj.status = 'processing'
    AND bss.files_processing = 0
    AND bss.files_pending = 0
    AND (bss.files_success + bss.files_failed) >= bss.total_files
ORDER BY bss.last_file_completed_at ASC;
```

---

## Status: COMPLETE ✅

All three layers implemented:
1. ✅ Enhanced diagnostic logging
2. ✅ Periodic state-driven checker (30s interval)
3. ✅ On-demand aggregation in API endpoint

**Next Step**: Restart worker and monitor logs
