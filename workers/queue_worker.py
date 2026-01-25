from __future__ import annotations

import json
import time
import uuid

from redis import Redis
from sqlalchemy import func, text

from workers.config import load_config
from workers.core.logging import setup_logger
from workers.database import operations
from workers.database.connection import get_session
from workers.database.models import ProcessingJob
from workers.processing.aggregator import aggregate_batch
from workers.processing.extractor import process_file


def _parse_job(raw: str) -> dict | None:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _maybe_finalize_batch(session, batch_id: str, logger, config, redis_client) -> None:
    logger.info(f"[QueueWorker] _maybe_finalize_batch CALLED for batch {batch_id}")
    
    if operations.is_batch_already_processed(session, batch_id):
        logger.info(f"[QueueWorker] Batch {batch_id} already processed, skipping finalization")
        return

    job = operations.get_batch_by_id(session, batch_id)
    if job is None:
        logger.warning(f"[QueueWorker] Batch not found: {batch_id}")
        return
    
    logger.info(f"[QueueWorker] Batch {batch_id} current status: {job.status}, total_files: {job.total_files}")

    summary = operations.get_batch_status_summary(session, batch_id)
    if summary:
        logger.info(f"[QueueWorker] Got summary for batch {batch_id}: {summary}")
        try:
            pending = int(summary.get("files_pending") or 0)
            processing = int(summary.get("files_processing") or 0)
            success = int(summary.get("files_success") or 0)
            failed = int(summary.get("files_failed") or 0)
            total = int(summary.get("total_files") or 0)
        except Exception as e:
            logger.error(f"[QueueWorker] Error parsing summary: {e}")
            pending = processing = 0
            success = failed = total = 0

        logger.info(
            f"[QueueWorker] Finalize check: total={total}, pending={pending}, processing={processing}, "
            f"success={success}, failed={failed}, sum={success + failed}"
        )
        
        if total > 0 and pending == 0 and processing == 0 and (success + failed) >= total:
            logger.info(f"[QueueWorker] FINALIZATION CONDITION MET for batch {batch_id}!")
            status = (
                ProcessingJob.STATUS_COMPLETED_WITH_ERRORS
                if failed > 0
                else ProcessingJob.STATUS_COMPLETED
            )
            job.status = status
            job.completed_at = func.now()
            job.updated_at = func.now()
            
            # Flush status update to DB before aggregation (prevents rollback if aggregation fails)
            session.flush()
            
            logger.info(
                f"[QueueWorker] Batch {batch_id} finalized: {status} "
                f"(success={success}, failed={failed})"
            )
            
            # Wrap aggregation in try/except to preserve status update even if aggregation fails
            try:
                aggregate_batch(session, batch_id, config)
                logger.info(f"[QueueWorker] Batch {batch_id} aggregated successfully")
            except Exception as agg_error:
                logger.error(
                    f"[QueueWorker] Aggregation failed for batch {batch_id}: {agg_error}"
                )
                # Status update is preserved due to flush() above
            return
    else:
        logger.info(f"[QueueWorker] Summary not available, using fallback stats for batch {batch_id}")

    stats = operations.get_batch_statistics(session, batch_id)
    counts = operations.get_batch_state_counts(session, batch_id)
    logger.info(f"[QueueWorker] Stats: {stats}")
    logger.info(f"[QueueWorker] Counts: {counts}")
    
    total_files = job.total_files or counts["total_files"]
    processed = (
        counts["success_files"]
        + counts["failed_files"]
        + counts["skipped_files"]
    )
    pending = counts["pending_files"] + counts["processing_files"]

    if total_files == 0 and counts["total_files"] > 0:
        job.total_files = counts["total_files"]
        total_files = counts["total_files"]
        logger.info(
            f"[QueueWorker] Backfilled total_files for batch {batch_id}: {total_files}"
        )

    logger.info(
        f"[QueueWorker] Fallback finalize check: total_files={total_files}, pending={pending}, "
        f"processed={processed}"
    )
    
    if total_files == 0:
        logger.warning(
            f"[QueueWorker] Skipping finalize (total_files=0) for batch {batch_id}"
        )
        return

    if pending > 0:
        if counts["processing_files"] == 0:
            pending_doc_ids = operations.get_pending_doc_ids(session, batch_id)
            if pending_doc_ids:
                for doc_id in pending_doc_ids:
                    job = {
                        "job_id": str(uuid.uuid4()),
                        "type": "process_file",
                        "doc_id": doc_id,
                        "batch_id": batch_id,
                        "attempt": 0,
                        "max_attempts": config.max_retry_attempts,
                        "retry_delay_ms": int(config.retry_base_delay_seconds * 1000),
                        "enqueued_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    }
                    redis_client.lpush(config.redis_queue_key, json.dumps(job))
                logger.warning(
                    f"[QueueWorker] Re-queued {len(pending_doc_ids)} pending files for batch {batch_id}"
                )
        logger.info(
            f"[QueueWorker] Skipping finalize (pending={pending}) for batch {batch_id}"
        )
        return

    if processed < total_files:
        logger.info(
            f"[QueueWorker] Skipping finalize (processed={processed}/{total_files}) "
            f"for batch {batch_id}"
        )
        return

    status = (
        ProcessingJob.STATUS_COMPLETED_WITH_ERRORS
        if stats["failed_files"] > 0
        else ProcessingJob.STATUS_COMPLETED
    )
    job.status = status
    job.completed_at = func.now()
    job.updated_at = func.now()
    
    # Flush status update to DB before aggregation (prevents rollback if aggregation fails)
    session.flush()

    logger.info(
        f"[QueueWorker] Batch {batch_id} finalized: {status} "
        f"(success={stats['success_files']}, failed={stats['failed_files']})"
    )

    # Wrap aggregation in try/except to preserve status update even if aggregation fails
    try:
        aggregate_batch(session, batch_id, config)
        logger.info(f"[QueueWorker] Batch {batch_id} aggregated successfully")
    except Exception as agg_error:
        logger.error(
            f"[QueueWorker] Aggregation failed for batch {batch_id}: {agg_error}"
        )
        # Status update is preserved due to flush() above


def _schedule_retry(redis_client: Redis, delayed_key: str, job: dict, delay_seconds: float, logger) -> None:
    run_at = time.time() + delay_seconds
    job["retry_at"] = run_at
    redis_client.zadd(delayed_key, {json.dumps(job): run_at})
    logger.warning(
        f"[QueueWorker] Scheduled retry for job {job.get('job_id')} in {delay_seconds:.1f}s"
    )


def _drain_delayed(redis_client: Redis, delayed_key: str, queue_key: str, logger, limit: int = 20) -> int:
    now = time.time()
    ready_jobs = redis_client.zrangebyscore(delayed_key, 0, now, start=0, num=limit)
    if not ready_jobs:
        return 0
    for job_raw in ready_jobs:
        redis_client.zrem(delayed_key, job_raw)
        redis_client.lpush(queue_key, job_raw)
    if ready_jobs:
        logger.info(f"[QueueWorker] Moved {len(ready_jobs)} delayed jobs back to queue")
    return len(ready_jobs)


def _check_stuck_batches(session, logger, config, redis_client) -> None:
    """
    STATE-DRIVEN finalization: Find batches that are complete but stuck in 'processing' state
    """
    try:
        result = session.execute(
            text("""
                SELECT 
                    pj.batch_id,
                    pj.status,
                    bss.files_success,
                    bss.files_failed,
                    bss.files_processing,
                    bss.files_pending,
                    bss.total_files,
                    bss.last_file_completed_at
                FROM processing_jobs pj
                INNER JOIN batch_status_summary bss ON pj.batch_id = bss.batch_id
                WHERE pj.status = 'processing'
                    AND bss.total_files > 0
                    AND bss.files_processing = 0
                    AND bss.files_pending = 0
                    AND (bss.files_success + bss.files_failed) >= bss.total_files
                    AND bss.last_file_completed_at < NOW() - INTERVAL '10 seconds'
                ORDER BY bss.last_file_completed_at ASC
                LIMIT 5
            """)
        ).mappings().fetchall()
        
        if result:
            logger.info(f"[QueueWorker] Found {len(result)} stuck batches to finalize")
            for row in result:
                batch_id = row["batch_id"]
                logger.warning(
                    f"[QueueWorker] STUCK BATCH DETECTED: {batch_id} "
                    f"(success={row['files_success']}, failed={row['files_failed']}, "
                    f"total={row['total_files']}) - forcing finalization"
                )
                _maybe_finalize_batch(session, batch_id, logger, config, redis_client)
                session.commit()  # Commit each batch separately
    except Exception as e:
        logger.error(f"[QueueWorker] Error checking stuck batches: {e}")
        session.rollback()


def main() -> None:
    config = load_config()
    logger = setup_logger("worker.queue", config)

    redis_client = Redis.from_url(
        config.redis_url,
        decode_responses=True,
    )
    processing_key = f"{config.redis_queue_key}:processing"
    delayed_key = f"{config.redis_queue_key}:delayed"
    dead_key = f"{config.redis_queue_key}:dead"

    logger.info(f"[QueueWorker] Connected to Redis: {config.redis_url}")
    logger.info(f"[QueueWorker] Listening on queue: {config.redis_queue_key}")

    last_stuck_check = time.time()
    stuck_check_interval = 30  # Check every 30 seconds

    while True:
        try:
            # Periodic stuck batch check (STATE-DRIVEN finalization)
            now = time.time()
            if now - last_stuck_check > stuck_check_interval:
                logger.info("[QueueWorker] Running periodic stuck batch check...")
                with get_session(config) as session:
                    _check_stuck_batches(session, logger, config, redis_client)
                last_stuck_check = now
            
            _drain_delayed(redis_client, delayed_key, config.redis_queue_key, logger)

            job_data = redis_client.brpop(config.redis_queue_key, timeout=5)
            if not job_data:
                continue

            _, raw = job_data
            job = _parse_job(raw)
            if not job:
                logger.error("[QueueWorker] Invalid job payload (not JSON)")
                continue

            job_type = job.get("type")
            job_id = job.get("job_id") or "unknown"
            redis_client.sadd(processing_key, job_id)
            try:
                if job_type == "process_file":
                    doc_id = job.get("doc_id")
                    batch_id = job.get("batch_id")
                    if not doc_id:
                        logger.error("[QueueWorker] Missing doc_id in job payload")
                        continue

                    logger.info(f"[QueueWorker] Processing doc_id={doc_id}")
                    with get_session(config) as session:
                        process_file(session, doc_id, config)
                        file_row = operations.get_file_by_doc_id(session, doc_id)
                        if file_row and file_row.status == file_row.STATUS_FAILED:
                            retry_count = operations.increment_retry_count(session, doc_id)
                            session.flush()
                            if retry_count < config.max_retry_attempts:
                                attempt = job.get("attempt", 0) + 1
                                job["attempt"] = attempt
                                delay_seconds = max(
                                    1.0,
                                    float(job.get("retry_delay_ms", 2000)) / 1000.0,
                                )
                                _schedule_retry(
                                    redis_client,
                                    delayed_key,
                                    job,
                                    delay_seconds,
                                    logger,
                                )
                            else:
                                redis_client.rpush(dead_key, json.dumps(job))
                                logger.error(
                                    f"[QueueWorker] Job {job_id} exceeded max retries, moved to dead queue"
                                )
                        
                        # Determine effective batch_id (handle run_id semantics)
                        effective_batch_id = batch_id or (file_row.run_id if file_row else None)
                        if effective_batch_id:
                            _maybe_finalize_batch(session, effective_batch_id, logger, config, redis_client)

                elif job_type == "aggregate_batch":
                    batch_id = job.get("batch_id")
                    if not batch_id:
                        logger.error("[QueueWorker] Missing batch_id in job payload")
                        continue
                    logger.info(f"[QueueWorker] Aggregating batch_id={batch_id}")
                    with get_session(config) as session:
                        try:
                            aggregate_batch(session, batch_id, config)
                        except Exception as exc:  # noqa: BLE001
                            attempt = job.get("attempt", 0) + 1
                            if attempt < config.max_retry_attempts:
                                job["attempt"] = attempt
                                delay_seconds = max(
                                    1.0,
                                    float(job.get("retry_delay_ms", 2000)) / 1000.0,
                                )
                                _schedule_retry(
                                    redis_client,
                                    delayed_key,
                                    job,
                                    delay_seconds,
                                    logger,
                                )
                            else:
                                redis_client.rpush(dead_key, json.dumps(job))
                                logger.error(
                                    f"[QueueWorker] Aggregate job {job_id} exceeded max retries"
                                )
                            raise exc

                else:
                    logger.warning(f"[QueueWorker] Unknown job type: {job_type}")
            finally:
                redis_client.srem(processing_key, job_id)

        except KeyboardInterrupt:
            logger.info("[QueueWorker] Shutting down...")
            break
        except Exception as exc:  # noqa: BLE001 - keep worker loop alive
            logger.error(f"[QueueWorker] Error: {exc}")
            time.sleep(1)


if __name__ == "__main__":
    main()
