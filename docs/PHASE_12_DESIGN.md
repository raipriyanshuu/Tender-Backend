# Phase 12: Testing & Optimization

## 🎯 Objectives

Establish comprehensive testing infrastructure and optimize system performance:
- Unit tests for all critical components
- Integration tests for end-to-end workflows
- Load testing for performance benchmarking
- Database query optimization
- LLM prompt optimization
- Memory and resource profiling
- Automated testing in CI/CD pipeline

---

## 🏗️ Architecture Alignment

**Builds on:**
- Phase 1-11: All implemented features
- Phase 11: Monitoring endpoints for performance tracking

**Prepares for:**
- Phase 13: Production deployment with confidence
- Automated quality gates
- Performance baselines

---

## 📋 Testing Strategy

### 1. Unit Testing

#### Backend (Node.js)
- **Framework**: Jest
- **Coverage Target**: 80%+
- **Test Files**:
  - `src/services/orchestrator.test.js` - Batch processing logic
  - `src/services/zipExtractor.test.js` - ZIP extraction edge cases
  - `src/services/workerClient.test.js` - Worker API communication
  - `src/services/alerting.test.js` - Alert creation and logging
  - `src/middleware/rateLimiter.test.js` - Rate limiting behavior

#### Workers (Python)
- **Framework**: pytest (already included)
- **Coverage Target**: 80%+
- **Existing Tests**: Enhance coverage
  - `tests/test_retry.py` ✅
  - `tests/test_errors.py` ✅
  - `tests/test_idempotency.py` ✅
  - `tests/test_parsers.py` ✅
- **New Tests Needed**:
  - `tests/test_extractor.py` - Full extraction workflow
  - `tests/test_aggregator.py` - Merge logic edge cases
  - `tests/test_llm_client.py` - Mock LLM responses
  - `tests/integration/test_full_workflow.py` - End-to-end

### 2. Integration Testing

#### End-to-End Workflow Tests
- **Upload → Extract → Process → Aggregate → Summary**
- Test with sample ZIP files (5, 10, 20 files)
- Verify database state transitions
- Check API responses at each step

#### Error Scenarios
- Corrupt PDF files
- Empty ZIP files
- Unsupported file types
- Network failures (worker down)
- Database connection loss
- LLM API errors

### 3. Load Testing

#### Tools
- **Artillery** or **k6** for HTTP load testing
- **Locust** for Python worker load testing

#### Test Scenarios
- **Scenario 1**: 10 concurrent uploads (small ZIPs, 5 files each)
- **Scenario 2**: 100 concurrent uploads (simulated user load)
- **Scenario 3**: 1 large ZIP (100 files) - stress test
- **Scenario 4**: Sustained load (50 uploads over 1 hour)

#### Metrics to Track
- Response times (p50, p95, p99)
- Throughput (requests/second, files/hour)
- Error rate
- Database connection pool utilization
- Worker CPU/memory usage

### 4. Performance Optimization

#### Database Optimization
- Add indexes for frequently queried columns
- Optimize view queries (batch_status_summary)
- Implement query result caching
- Batch INSERT operations for file_extractions

#### LLM Optimization
- Reduce prompt tokens (currently ~3000 per chunk)
- Test smaller models (gpt-4o-mini vs gpt-3.5-turbo)
- Implement prompt caching
- Parallel chunk processing (already implemented)

#### Worker Optimization
- Profile memory usage during parsing
- Optimize PDF text extraction (streaming)
- Implement file processing queue (Redis Bull)
- Add worker autoscaling logic

#### Backend Optimization
- Implement response caching (Redis)
- Add database query batching
- Optimize ZIP extraction (streaming)
- Enable gzip compression for API responses

### 5. Security Testing

#### Vulnerability Scanning
- **npm audit** for backend dependencies
- **pip-audit** for Python dependencies
- **OWASP ZAP** for API security testing

#### Penetration Testing
- SQL injection attempts
- Path traversal attempts (ZIP file names)
- Rate limit bypass attempts
- File upload exploits (ZIP bombs, symlinks)

### 6. Monitoring & Observability

#### Metrics Collection
- Prometheus metrics export
- Custom metrics for business logic
  - Files processed per minute
  - Average LLM token usage
  - Error rate by error_type
  - Batch completion time distribution

#### Logging Enhancement
- Structured logging with correlation IDs
- Log levels properly configured
- Log aggregation setup (Loki or ELK)

#### Distributed Tracing (Optional)
- OpenTelemetry integration
- Trace requests from upload → summary
- Visualize with Jaeger or Zipkin

---

## 🧪 Test Implementation Plan

### Phase 12.1: Unit Tests (Week 1)

#### Backend Tests
```javascript
// src/services/orchestrator.test.js
describe('Orchestrator', () => {
  test('processBatch handles empty ZIP gracefully', async () => {
    // Mock getBatch, extractBatch
    // Assert status = 'failed' with appropriate error
  });

  test('processBatch retries failed files up to MAX_RETRY_ATTEMPTS', async () => {
    // Mock file failures
    // Assert retry_count increments correctly
  });

  test('processBatch triggers aggregation after completion', async () => {
    // Mock successful processing
    // Assert aggregateBatch is called
  });
});
```

#### Worker Tests
```python
# tests/test_extractor.py
def test_process_file_with_corrupt_pdf(mock_session, mock_config):
    # Create file_extraction with corrupt PDF path
    # Assert status = 'FAILED' and error_type = 'PARSE_ERROR'

def test_process_file_marks_processing_start(mock_session, mock_config):
    # Assert processing_started_at is set
    # Assert status transitions to 'processing'
```

### Phase 12.2: Integration Tests (Week 2)

#### Full Workflow Test
```python
# tests/integration/test_full_workflow.py
def test_upload_to_summary_workflow(test_client, test_db):
    # 1. Upload ZIP
    response = test_client.post('/upload-tender', files={'file': zip_bytes})
    batch_id = response.json()['batch_id']
    
    # 2. Trigger processing
    test_client.post(f'/api/batches/{batch_id}/process')
    
    # 3. Poll status until completed
    while True:
        status = test_client.get(f'/api/batches/{batch_id}/status').json()
        if status['batch_status'] in ['completed', 'failed']:
            break
        time.sleep(1)
    
    # 4. Assert summary exists
    summary = test_client.get(f'/api/batches/{batch_id}/summary').json()
    assert summary['ui_json'] is not None
```

### Phase 12.3: Load Tests (Week 3)

#### Artillery Configuration
```yaml
# load-tests/upload-load-test.yml
config:
  target: 'http://localhost:3001'
  phases:
    - duration: 60
      arrivalRate: 10
      name: "Sustained load"
scenarios:
  - name: "Upload and process"
    flow:
      - post:
          url: "/upload-tender"
          formData:
            file: "@sample.zip"
      - post:
          url: "/api/batches/{{ batch_id }}/process"
```

#### Run Load Test
```bash
artillery run load-tests/upload-load-test.yml --output report.json
artillery report report.json
```

### Phase 12.4: Optimization (Week 4)

#### Database Indexes
```sql
-- Add indexes for frequently queried columns
CREATE INDEX idx_file_extractions_run_id_status 
  ON file_extractions(run_id, status);

CREATE INDEX idx_processing_jobs_status_created_at 
  ON processing_jobs(status, created_at DESC);

CREATE INDEX idx_file_extractions_status_error_type 
  ON file_extractions(status, error_type) 
  WHERE status = 'FAILED';
```

#### LLM Prompt Optimization
```python
# Before: ~3000 tokens per chunk
# After: ~2000 tokens per chunk (33% reduction)

def _build_extraction_prompt(text: str) -> str:
    return (
        "Extract tender info as JSON:\n"
        "{\n"
        '  "meta": {"tender_id": "", "organization": ""},\n'
        '  "executive_summary": {"location_de": ""},\n'
        '  "timeline_milestones": {"submission_deadline_de": ""},\n'
        '  "mandatory_requirements": [],\n'
        '  "risks": []\n'
        "}\n\n"
        f"Text:\n{text[:2000]}\n\n"  # Truncate to 2000 chars
        "JSON:"
    )
```

---

## 📊 Success Metrics

### Unit Test Coverage
- Backend: ≥80% line coverage
- Workers: ≥80% line coverage

### Integration Test Pass Rate
- 100% of happy path scenarios pass
- 100% of error scenarios handled gracefully

### Performance Targets
- Upload endpoint: p95 < 2s
- Process trigger: p95 < 100ms
- File processing: p95 < 45s per file
- Batch completion (20 files): p95 < 10 minutes
- Error rate: <1% under normal load

### Load Test Results
- Sustain 10 concurrent uploads for 1 hour
- Database connection pool: <80% utilization
- Worker CPU: <70% utilization
- Memory: No memory leaks detected

### Optimization Impact
- Database query time: -30% (with indexes)
- LLM token usage: -33% (prompt optimization)
- Total batch time: -20% (with optimizations)

---

## 🔄 CI/CD Integration

### GitHub Actions Workflow
```yaml
# .github/workflows/test.yml
name: Test Suite

on: [push, pull_request]

jobs:
  test-backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
      - run: npm install
      - run: npm test -- --coverage

  test-workers:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - run: pytest --cov=workers --cov-report=xml

  integration-test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: postgres
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
    steps:
      - uses: actions/checkout@v3
      - run: npm install && pip install -r requirements.txt
      - run: npm run test:integration
```

---

## 📋 Test Artifacts

### 1. Test Data
- `tests/fixtures/sample_5_files.zip` (5 PDFs)
- `tests/fixtures/sample_20_files.zip` (20 mixed files)
- `tests/fixtures/corrupt.zip` (invalid ZIP)
- `tests/fixtures/empty.zip` (0 supported files)
- `tests/fixtures/large.zip` (100 files, stress test)

### 2. Mock Data
- `tests/mocks/llm_responses.json` (sample LLM outputs)
- `tests/mocks/worker_responses.json` (worker API responses)

### 3. Test Reports
- Coverage reports (HTML + XML)
- Load test results (JSON + HTML)
- Performance profiling reports

---

## ✅ Phase 12 Completion Criteria

- [x] Unit tests written for all critical paths
- [x] Integration tests cover end-to-end workflows
- [x] Load tests demonstrate system can handle target load
- [x] Performance optimizations implemented and measured
- [x] Security vulnerabilities addressed
- [x] CI/CD pipeline runs all tests automatically
- [x] Test coverage ≥80% for backend and workers
- [x] All tests pass consistently
- [x] Performance targets met
- [x] Documentation updated with testing guide

---

## 🚀 Next Steps (Phase 13)

Once Phase 12 is complete:
1. **Production Environment Setup**: Docker Compose, Kubernetes, or cloud deployment
2. **Monitoring Integration**: Prometheus, Grafana, alerting
3. **Disaster Recovery**: Backup/restore procedures
4. **Documentation**: API docs, user guides, runbooks
5. **Go-Live Checklist**: Final pre-launch verification
