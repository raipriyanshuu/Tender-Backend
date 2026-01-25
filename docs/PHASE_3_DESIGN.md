# Phase 3 Design: Python Workers - Core Services

**Status**: 🎨 Design Phase  
**Date**: January 22, 2026  
**Prerequisites**: Phase 1 ✅, Phase 2 ✅

---

## 📋 Implementation Analysis (Phase 1 & 2)

### ✅ Phase 1: Database Foundation
**What We Have:**
- ✅ `processing_jobs` table for batch tracking
- ✅ `file_extractions` table with processing metadata
- ✅ 5 database views for monitoring and analytics
- ✅ Error classification system (7 error types)
- ✅ Retry tracking columns
- ✅ Performance metrics (timing, duration)
- ✅ Test data seeding

**Database Schema Available:**
```sql
-- processing_jobs
- id (uuid), batch_id (text), zip_path (text)
- status (pending|queued|extracting|processing|completed|completed_with_errors|failed)
- total_files, uploaded_by, error_message
- created_at, updated_at, completed_at

-- file_extractions (extended)
- file_path, processing_started_at, processing_completed_at
- processing_duration_ms, retry_count, error_type
- status (pending|processing|SUCCESS|FAILED|SKIPPED)
```

### ✅ Phase 2: Shared Filesystem
**What We Have:**
- ✅ `shared/uploads/` - ZIP files from backend
- ✅ `shared/extracted/` - Unzipped files
- ✅ `shared/temp/` - Temporary processing
- ✅ `shared/logs/` - Processing logs
- ✅ Path conventions documented

**Storage Contract:**
- Backend writes to: `/shared/uploads/{batch_id}.zip`
- Worker extracts to: `/shared/extracted/{batch_id}/`
- Database stores relative paths

---

## 🎯 Phase 3 Goals

### Primary Objectives
1. **Create Python Worker Foundation** - Core infrastructure for all file processing
2. **Database Access Layer** - SQLAlchemy models matching Phase 1 schema
3. **Configuration Management** - Environment-based config with validation
4. **Retry Logic** - Exponential backoff with jitter
5. **Error Classification** - Automatic error type detection
6. **Logging System** - Structured logging with context
7. **Idempotency Helpers** - Prevent duplicate processing

### Non-Goals (Deferred to Phase 4-5)
- ❌ File parsing (PDF, Word, Excel) - Phase 4
- ❌ LLM client integration - Phase 4
- ❌ HTTP API endpoints - Phase 5
- ❌ Chunking/embeddings - Phase 4

---

## 📦 Phase 3 Architecture

### Project Structure
```
workers/
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── config.py                # Configuration management
├── database/
│   ├── __init__.py
│   ├── connection.py        # Database connection pool
│   ├── models.py            # SQLAlchemy ORM models
│   └── operations.py        # Database operations
├── core/
│   ├── __init__.py
│   ├── retry.py             # Retry logic with backoff
│   ├── errors.py            # Error classification
│   ├── logging.py           # Structured logging
│   └── idempotency.py       # Deduplication helpers
├── utils/
│   ├── __init__.py
│   └── filesystem.py        # Filesystem helpers
└── tests/
    ├── __init__.py
    ├── test_database.py
    ├── test_retry.py
    └── test_errors.py
```

---

## 🔧 Worker Components (Phase 3)

### 1. Configuration Management (`config.py`)

**Purpose**: Centralized configuration with validation

**Features:**
- Environment variable loading with `.env` support
- Type validation and default values
- Database connection string builder
- Storage path resolver
- LLM API key management (for Phase 4)

**Config Groups:**
```python
# Database
DATABASE_URL
DATABASE_MAX_CONNECTIONS
DATABASE_TIMEOUT

# Storage
STORAGE_BASE_PATH           # /shared
STORAGE_UPLOADS_DIR         # uploads
STORAGE_EXTRACTED_DIR       # extracted
STORAGE_TEMP_DIR            # temp

# Processing
MAX_RETRY_ATTEMPTS          # 3
RETRY_BASE_DELAY_SECONDS    # 2
RETRY_MAX_DELAY_SECONDS     # 60
BATCH_PROCESSING_TIMEOUT    # 1800 (30 min)

# LLM (Phase 4)
OPENAI_API_KEY
OPENAI_MODEL
OPENAI_MAX_TOKENS
OPENAI_RATE_LIMIT_RPM

# Logging
LOG_LEVEL                   # INFO
LOG_FORMAT                  # json | text
LOG_FILE_PATH               # /shared/logs/worker.log
```

**Validation Rules:**
- DATABASE_URL must start with `postgresql://`
- STORAGE_BASE_PATH must exist and be writable
- MAX_RETRY_ATTEMPTS must be 0-10
- LOG_LEVEL must be DEBUG|INFO|WARNING|ERROR

---

### 2. Database Models (`database/models.py`)

**Purpose**: SQLAlchemy ORM models matching Phase 1 schema

**Models:**

#### 2.1 ProcessingJob
```python
class ProcessingJob(Base):
    __tablename__ = 'processing_jobs'
    
    id = Column(UUID, primary_key=True)
    batch_id = Column(String, unique=True, nullable=False)
    zip_path = Column(String, nullable=False)
    run_id = Column(String)
    total_files = Column(Integer, default=0)
    uploaded_by = Column(String)
    status = Column(String, nullable=False, default='pending')
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))
    
    # Relationship
    file_extractions = relationship("FileExtraction", back_populates="job")
    
    # Status enum
    STATUS_PENDING = 'pending'
    STATUS_QUEUED = 'queued'
    STATUS_EXTRACTING = 'extracting'
    STATUS_PROCESSING = 'processing'
    STATUS_COMPLETED = 'completed'
    STATUS_COMPLETED_WITH_ERRORS = 'completed_with_errors'
    STATUS_FAILED = 'failed'
```

#### 2.2 FileExtraction
```python
class FileExtraction(Base):
    __tablename__ = 'file_extractions'
    
    id = Column(UUID, primary_key=True)
    doc_id = Column(String, unique=True, nullable=False)
    run_id = Column(String, nullable=False)
    file_path = Column(String)
    file_name = Column(String)
    file_type = Column(String)
    status = Column(String, default='pending')
    raw_extraction = Column(JSONB)
    processing_started_at = Column(DateTime(timezone=True))
    processing_completed_at = Column(DateTime(timezone=True))
    processing_duration_ms = Column(Integer)
    retry_count = Column(Integer, default=0)
    error_type = Column(String)
    error_message = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationship
    job = relationship("ProcessingJob", back_populates="file_extractions")
    
    # Status enum
    STATUS_PENDING = 'pending'
    STATUS_PROCESSING = 'processing'
    STATUS_SUCCESS = 'SUCCESS'
    STATUS_FAILED = 'FAILED'
    STATUS_SKIPPED = 'SKIPPED'
    
    # Error types
    ERROR_RETRYABLE = 'RETRYABLE'
    ERROR_PERMANENT = 'PERMANENT'
    ERROR_TIMEOUT = 'TIMEOUT'
    ERROR_RATE_LIMIT = 'RATE_LIMIT'
    ERROR_PARSE_ERROR = 'PARSE_ERROR'
    ERROR_LLM_ERROR = 'LLM_ERROR'
    ERROR_UNKNOWN = 'UNKNOWN'
```

#### 2.3 RunSummary
```python
class RunSummary(Base):
    __tablename__ = 'run_summaries'
    
    id = Column(UUID, primary_key=True)
    run_id = Column(String, unique=True, nullable=False)
    ui_json = Column(JSONB)
    nested_summary = Column(JSONB)
    file_count = Column(Integer)
    success_count = Column(Integer)
    error_count = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
```

---

### 3. Database Operations (`database/operations.py`)

**Purpose**: High-level database operations with error handling

**Core Operations:**

#### 3.1 Batch Operations
```python
def get_batch_by_id(batch_id: str) -> ProcessingJob
def update_batch_status(batch_id: str, status: str, error: str = None)
def get_batch_files(batch_id: str) -> List[FileExtraction]
def mark_batch_completed(batch_id: str)
def mark_batch_failed(batch_id: str, error: str)
```

#### 3.2 File Operations
```python
def create_file_extraction(batch_id: str, file_info: dict) -> FileExtraction
def get_file_by_doc_id(doc_id: str) -> FileExtraction
def update_file_status(doc_id: str, status: str)
def mark_file_processing_start(doc_id: str)
def mark_file_success(doc_id: str, extraction_data: dict)
def mark_file_failed(doc_id: str, error: str, error_type: str)
def increment_retry_count(doc_id: str) -> int
```

#### 3.3 Idempotency Operations
```python
def is_batch_already_processed(batch_id: str) -> bool
def is_file_already_processed(doc_id: str) -> bool
def get_or_create_file_extraction(doc_id: str, defaults: dict) -> Tuple[FileExtraction, bool]
```

#### 3.4 Aggregation Operations (for Phase 9)
```python
def get_batch_statistics(batch_id: str) -> dict
def create_or_update_run_summary(run_id: str, ui_json: dict)
```

---

### 4. Retry Logic (`core/retry.py`)

**Purpose**: Exponential backoff retry decorator with jitter

**Features:**
- Configurable max attempts
- Exponential backoff: `delay = base * (2 ** attempt)`
- Jitter to prevent thundering herd
- Retry only on retryable errors
- Automatic error classification

**Implementation:**
```python
@retry_with_backoff(
    max_attempts=3,
    base_delay=2.0,
    max_delay=60.0,
    retryable_exceptions=[RetryableError, RateLimitError, TimeoutError]
)
def process_file(file_path: str):
    # Processing logic
    pass
```

**Backoff Formula:**
```
attempt_0: 2s
attempt_1: 4s + jitter(0-2s)
attempt_2: 8s + jitter(0-4s)
attempt_3: 16s + jitter(0-8s)
```

**Retry Decision Logic:**
```python
def should_retry(error: Exception, attempt: int, max_attempts: int) -> bool:
    # Check attempt count
    if attempt >= max_attempts:
        return False
    
    # Check error type
    error_type = classify_error(error)
    if error_type in ['PERMANENT', 'PARSE_ERROR']:
        return False
    
    if error_type in ['RETRYABLE', 'TIMEOUT', 'RATE_LIMIT', 'LLM_ERROR']:
        return True
    
    return False  # UNKNOWN errors don't retry by default
```

---

### 5. Error Classification (`core/errors.py`)

**Purpose**: Automatic error type detection and custom exceptions

**Custom Exceptions:**
```python
class WorkerError(Exception):
    """Base exception for all worker errors"""
    error_type = 'UNKNOWN'

class RetryableError(WorkerError):
    """Temporary error, retry recommended"""
    error_type = 'RETRYABLE'

class PermanentError(WorkerError):
    """Permanent error, no retry"""
    error_type = 'PERMANENT'

class TimeoutError(WorkerError):
    """Operation timeout"""
    error_type = 'TIMEOUT'

class RateLimitError(WorkerError):
    """API rate limit exceeded"""
    error_type = 'RATE_LIMIT'

class ParseError(WorkerError):
    """File parsing failed"""
    error_type = 'PARSE_ERROR'

class LLMError(WorkerError):
    """LLM API error"""
    error_type = 'LLM_ERROR'
```

**Error Classifier:**
```python
def classify_error(error: Exception) -> str:
    """
    Automatically classify errors into types.
    Returns: RETRYABLE | PERMANENT | TIMEOUT | RATE_LIMIT | PARSE_ERROR | LLM_ERROR | UNKNOWN
    """
    # Check custom exceptions first
    if hasattr(error, 'error_type'):
        return error.error_type
    
    # Classify by exception type
    error_name = type(error).__name__
    error_message = str(error).lower()
    
    # Network/connection errors
    if 'connection' in error_message or 'timeout' in error_message:
        return 'RETRYABLE'
    
    # Rate limit errors
    if 'rate limit' in error_message or '429' in error_message:
        return 'RATE_LIMIT'
    
    # File parsing errors
    if 'parse' in error_message or 'decode' in error_message:
        return 'PARSE_ERROR'
    
    # LLM errors
    if 'openai' in error_message or 'llm' in error_message:
        return 'LLM_ERROR'
    
    # Permission/file not found
    if 'permission' in error_message or 'not found' in error_message:
        return 'PERMANENT'
    
    return 'UNKNOWN'
```

---

### 6. Logging System (`core/logging.py`)

**Purpose**: Structured logging with context and correlation IDs

**Features:**
- JSON structured logging for production
- Human-readable text for development
- Automatic context injection (batch_id, file_id)
- Log levels: DEBUG, INFO, WARNING, ERROR, CRITICAL
- File rotation and size limits
- Correlation IDs for request tracing

**Logger Setup:**
```python
def setup_logger(name: str, config: Config) -> logging.Logger:
    """
    Creates structured logger with file and console handlers
    """
    logger = logging.getLogger(name)
    logger.setLevel(config.LOG_LEVEL)
    
    # Console handler (text format for dev)
    console_handler = logging.StreamHandler()
    console_formatter = TextFormatter()
    console_handler.setFormatter(console_formatter)
    
    # File handler (JSON format for production)
    file_handler = RotatingFileHandler(
        config.LOG_FILE_PATH,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    json_formatter = JSONFormatter()
    file_handler.setFormatter(json_formatter)
    
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    
    return logger
```

**Context Manager:**
```python
class LogContext:
    """Inject context into all log messages"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
    
    def __enter__(self):
        # Store original factory
        self.old_factory = logging.getLogRecordFactory()
        
        # Inject context
        def record_factory(*args, **kwargs):
            record = self.old_factory(*args, **kwargs)
            for key, value in self.context.items():
                setattr(record, key, value)
            return record
        
        logging.setLogRecordFactory(record_factory)
        return self.logger
    
    def __exit__(self, *args):
        logging.setLogRecordFactory(self.old_factory)

# Usage
with LogContext(logger, batch_id='batch_123', file_id='doc_456'):
    logger.info('Processing file')
    # Log output: {"message": "Processing file", "batch_id": "batch_123", "file_id": "doc_456"}
```

---

### 7. Idempotency Helpers (`core/idempotency.py`)

**Purpose**: Prevent duplicate processing using database-level checks

**Features:**
- Unique doc_id constraint enforcement
- Atomic get-or-create operations
- Processing state validation
- Duplicate detection logging

**Core Functions:**
```python
def ensure_idempotent_file(
    doc_id: str,
    batch_id: str,
    file_info: dict
) -> Tuple[FileExtraction, bool]:
    """
    Get existing file extraction or create new one atomically.
    Returns: (file_extraction, created)
    """
    try:
        # Try to get existing
        existing = get_file_by_doc_id(doc_id)
        if existing:
            logger.info(f"File {doc_id} already exists, status: {existing.status}")
            return existing, False
        
        # Create new
        file_extraction = create_file_extraction(batch_id, {
            'doc_id': doc_id,
            **file_info
        })
        return file_extraction, True
    
    except IntegrityError:
        # Race condition: another worker created it
        existing = get_file_by_doc_id(doc_id)
        return existing, False

def should_reprocess_file(file_extraction: FileExtraction) -> bool:
    """
    Decide if a file should be reprocessed based on current state.
    """
    # Already successful
    if file_extraction.status == FileExtraction.STATUS_SUCCESS:
        return False
    
    # Failed with permanent error
    if (file_extraction.status == FileExtraction.STATUS_FAILED and
        file_extraction.error_type == FileExtraction.ERROR_PERMANENT):
        return False
    
    # Failed but retryable
    if (file_extraction.status == FileExtraction.STATUS_FAILED and
        file_extraction.retry_count < MAX_RETRY_ATTEMPTS):
        return True
    
    # Pending or processing (might be stale)
    if file_extraction.status in [FileExtraction.STATUS_PENDING, FileExtraction.STATUS_PROCESSING]:
        # Check if stale (processing > 30 min)
        if file_extraction.processing_started_at:
            elapsed = datetime.now(timezone.utc) - file_extraction.processing_started_at
            if elapsed.total_seconds() > 1800:  # 30 min
                logger.warning(f"Stale processing detected for {file_extraction.doc_id}")
                return True
        return False
    
    return False
```

---

### 8. Filesystem Helpers (`utils/filesystem.py`)

**Purpose**: Safe filesystem operations with validation

**Features:**
- Path validation and sanitization
- Storage path resolution
- File type detection
- Safe file operations with error handling

**Core Functions:**
```python
def resolve_storage_path(relative_path: str, base_path: str = '/shared') -> str:
    """Convert relative path to absolute storage path"""
    return os.path.join(base_path, relative_path)

def ensure_directory_exists(path: str) -> None:
    """Create directory if it doesn't exist"""
    os.makedirs(path, exist_ok=True)

def get_file_type(file_path: str) -> str:
    """Detect file type from extension"""
    ext = os.path.splitext(file_path)[1].lower()
    type_map = {
        '.pdf': 'pdf',
        '.doc': 'word',
        '.docx': 'word',
        '.xls': 'excel',
        '.xlsx': 'excel',
        '.zip': 'zip',
        '.txt': 'text'
    }
    return type_map.get(ext, 'unknown')

def safe_read_file(file_path: str) -> bytes:
    """Read file with error handling"""
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except FileNotFoundError:
        raise PermanentError(f"File not found: {file_path}")
    except PermissionError:
        raise PermanentError(f"Permission denied: {file_path}")
    except Exception as e:
        raise RetryableError(f"Failed to read file: {e}")
```

---

## 📋 Dependencies (`requirements.txt`)

```txt
# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9
alembic==1.13.1

# Environment & Config
python-dotenv==1.0.0
pydantic==2.5.3
pydantic-settings==2.1.0

# Logging
python-json-logger==2.0.7

# Utilities
tenacity==8.2.3          # Alternative retry library
backoff==2.2.1           # Backoff utilities

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
faker==22.0.0

# Type checking (optional)
mypy==1.8.0
types-psycopg2==2.9.21.16
```

---

## 🧪 Testing Strategy

### Unit Tests
1. **test_database.py**
   - Model creation and relationships
   - Query operations
   - Error handling

2. **test_retry.py**
   - Backoff calculation
   - Retry decision logic
   - Max attempts enforcement

3. **test_errors.py**
   - Error classification
   - Custom exception hierarchy
   - Error message formatting

4. **test_config.py**
   - Environment variable loading
   - Validation rules
   - Default values

5. **test_idempotency.py**
   - Duplicate detection
   - Atomic operations
   - Reprocess logic

### Integration Tests
1. **test_database_integration.py**
   - Real database connection
   - Transaction rollback
   - Concurrent access

---

## ✅ Success Criteria

Phase 3 is complete when:

1. ✅ All 8 worker modules are implemented
2. ✅ Database models match Phase 1 schema exactly
3. ✅ Configuration validates all required env vars
4. ✅ Retry logic handles all error types correctly
5. ✅ Error classifier achieves >90% accuracy on common errors
6. ✅ Logging produces valid JSON in production mode
7. ✅ Idempotency prevents duplicate processing
8. ✅ All unit tests pass (>80% coverage)
9. ✅ Documentation complete for all modules

---

## 🚀 Next Steps (Phase 4 Preview)

Phase 4 will build on this foundation:
- File parsers (PDF, Word, Excel) using Phase 3 error handling
- LLM client using Phase 3 retry logic
- Chunking strategy using Phase 3 database models
- Text extraction pipeline using Phase 3 logging

**Phase 3 → Phase 4 Integration Points:**
- `core/retry.py` → LLM API calls
- `core/errors.py` → Parser exceptions
- `database/operations.py` → Store extraction results
- `core/logging.py` → Track processing progress

---

## 📊 Implementation Estimate

| Component | Lines of Code | Complexity | Duration |
|-----------|--------------|------------|----------|
| config.py | 150 | Low | 2h |
| database/models.py | 200 | Medium | 3h |
| database/operations.py | 300 | Medium | 4h |
| core/retry.py | 150 | Medium | 3h |
| core/errors.py | 100 | Low | 2h |
| core/logging.py | 200 | Medium | 3h |
| core/idempotency.py | 150 | Medium | 3h |
| utils/filesystem.py | 100 | Low | 2h |
| tests/ | 500 | Medium | 6h |

**Total Estimated Duration**: 1.5 days (12 hours coding + 6 hours testing)

---

## 🎯 Summary

Phase 3 creates a **production-ready foundation** for the Python workers:

✅ **Database layer** - Type-safe ORM models  
✅ **Configuration** - Validated environment-based config  
✅ **Retry logic** - Smart exponential backoff  
✅ **Error handling** - Automatic classification  
✅ **Logging** - Structured JSON logs  
✅ **Idempotency** - Prevent duplicates  
✅ **Testing** - Comprehensive test coverage  

**This foundation enables Phases 4-5** to focus purely on business logic (file parsing, LLM integration) without worrying about infrastructure concerns.

**Ready to implement!** 🚀
