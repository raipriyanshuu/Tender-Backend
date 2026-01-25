# Phase 3: Required Workers/Modules

**Complete list of all modules to implement in Phase 3**

---

## 📁 Directory Structure

```
workers/
├── requirements.txt
├── .env.example
├── config.py                 # ⭐ Worker 1
├── database/
│   ├── __init__.py
│   ├── connection.py         # ⭐ Worker 2
│   ├── models.py             # ⭐ Worker 3
│   └── operations.py         # ⭐ Worker 4
├── core/
│   ├── __init__.py
│   ├── retry.py              # ⭐ Worker 5
│   ├── errors.py             # ⭐ Worker 6
│   ├── logging.py            # ⭐ Worker 7
│   └── idempotency.py        # ⭐ Worker 8
├── utils/
│   ├── __init__.py
│   └── filesystem.py         # ⭐ Worker 9
└── tests/
    ├── __init__.py
    ├── test_config.py
    ├── test_database.py
    ├── test_retry.py
    ├── test_errors.py
    └── test_idempotency.py
```

---

## ⭐ Worker 1: Configuration Management

**File**: `workers/config.py`  
**Purpose**: Centralized environment-based configuration  
**Lines**: ~150

### Responsibilities
- Load environment variables from `.env`
- Validate all required config values
- Provide type-safe config access
- Build database connection strings
- Resolve storage paths

### Key Functions
```python
class Config:
    # Database
    DATABASE_URL: str
    DATABASE_MAX_CONNECTIONS: int = 10
    DATABASE_TIMEOUT: int = 30
    
    # Storage
    STORAGE_BASE_PATH: str = '/shared'
    STORAGE_UPLOADS_DIR: str = 'uploads'
    STORAGE_EXTRACTED_DIR: str = 'extracted'
    
    # Processing
    MAX_RETRY_ATTEMPTS: int = 3
    RETRY_BASE_DELAY_SECONDS: float = 2.0
    BATCH_PROCESSING_TIMEOUT: int = 1800
    
    # Logging
    LOG_LEVEL: str = 'INFO'
    LOG_FORMAT: str = 'json'
    LOG_FILE_PATH: str = '/shared/logs/worker.log'
    
    def validate(self) -> None:
        """Validate all configuration"""
        
    def get_storage_path(self, subdir: str) -> str:
        """Get absolute storage path"""
```

---

## ⭐ Worker 2: Database Connection

**File**: `workers/database/connection.py`  
**Purpose**: PostgreSQL connection pooling  
**Lines**: ~100

### Responsibilities
- Create SQLAlchemy engine
- Manage connection pool
- Provide session factory
- Handle connection errors
- Close connections gracefully

### Key Functions
```python
def create_engine(config: Config) -> Engine:
    """Create SQLAlchemy engine with pooling"""

def get_session_factory(engine: Engine) -> sessionmaker:
    """Create session factory"""

def get_session() -> Session:
    """Get database session (context manager)"""

def test_connection(engine: Engine) -> bool:
    """Test database connectivity"""
```

---

## ⭐ Worker 3: Database Models

**File**: `workers/database/models.py`  
**Purpose**: SQLAlchemy ORM models  
**Lines**: ~200

### Responsibilities
- Define ProcessingJob model
- Define FileExtraction model
- Define RunSummary model
- Define relationships
- Define status/error enums

### Models
```python
class ProcessingJob(Base):
    """Batch-level processing tracking"""
    __tablename__ = 'processing_jobs'
    
    id: UUID
    batch_id: str
    zip_path: str
    run_id: str
    total_files: int
    status: str
    error_message: str
    created_at: datetime
    updated_at: datetime
    completed_at: datetime
    
    # Relationships
    file_extractions: List[FileExtraction]

class FileExtraction(Base):
    """Per-file extraction results"""
    __tablename__ = 'file_extractions'
    
    id: UUID
    doc_id: str
    run_id: str
    file_path: str
    file_name: str
    status: str
    raw_extraction: dict
    processing_started_at: datetime
    processing_completed_at: datetime
    processing_duration_ms: int
    retry_count: int
    error_type: str
    error_message: str

class RunSummary(Base):
    """Aggregated batch results"""
    __tablename__ = 'run_summaries'
    
    id: UUID
    run_id: str
    ui_json: dict
    nested_summary: dict
    file_count: int
    success_count: int
    error_count: int
```

---

## ⭐ Worker 4: Database Operations

**File**: `workers/database/operations.py`  
**Purpose**: High-level database operations  
**Lines**: ~300

### Responsibilities
- CRUD operations for all models
- Transaction management
- Error handling
- Query optimization
- Batch operations

### Key Functions
```python
# Batch operations
def get_batch_by_id(batch_id: str) -> ProcessingJob
def update_batch_status(batch_id: str, status: str)
def get_batch_files(batch_id: str) -> List[FileExtraction]
def mark_batch_completed(batch_id: str)
def mark_batch_failed(batch_id: str, error: str)

# File operations
def create_file_extraction(batch_id: str, file_info: dict) -> FileExtraction
def get_file_by_doc_id(doc_id: str) -> FileExtraction
def update_file_status(doc_id: str, status: str)
def mark_file_processing_start(doc_id: str)
def mark_file_success(doc_id: str, data: dict)
def mark_file_failed(doc_id: str, error: str, error_type: str)
def increment_retry_count(doc_id: str) -> int

# Idempotency
def is_batch_already_processed(batch_id: str) -> bool
def is_file_already_processed(doc_id: str) -> bool
def get_or_create_file_extraction(doc_id: str, defaults: dict)

# Aggregation
def get_batch_statistics(batch_id: str) -> dict
def create_or_update_run_summary(run_id: str, ui_json: dict)
```

---

## ⭐ Worker 5: Retry Logic

**File**: `workers/core/retry.py`  
**Purpose**: Exponential backoff retry decorator  
**Lines**: ~150

### Responsibilities
- Exponential backoff calculation
- Jitter to prevent thundering herd
- Retry decision logic
- Max attempts enforcement
- Retry only on retryable errors

### Key Functions
```python
def retry_with_backoff(
    max_attempts: int = 3,
    base_delay: float = 2.0,
    max_delay: float = 60.0,
    retryable_exceptions: List[Type[Exception]] = None
):
    """Decorator for retry logic with exponential backoff"""

def calculate_backoff(attempt: int, base: float, max_delay: float) -> float:
    """Calculate backoff with jitter"""
    # delay = base * (2 ** attempt) + random_jitter

def should_retry(error: Exception, attempt: int, max_attempts: int) -> bool:
    """Decide if error is retryable"""
```

### Backoff Schedule
```
Attempt 0: 2s
Attempt 1: 4s + jitter(0-2s)
Attempt 2: 8s + jitter(0-4s)
Attempt 3: 16s + jitter(0-8s)
```

---

## ⭐ Worker 6: Error Classification

**File**: `workers/core/errors.py`  
**Purpose**: Custom exceptions and error classification  
**Lines**: ~100

### Responsibilities
- Define custom exception hierarchy
- Automatic error type detection
- Error message formatting
- Error type constants

### Custom Exceptions
```python
class WorkerError(Exception):
    """Base exception"""
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

### Key Functions
```python
def classify_error(error: Exception) -> str:
    """
    Automatically classify errors into types.
    Returns: RETRYABLE | PERMANENT | TIMEOUT | RATE_LIMIT | PARSE_ERROR | LLM_ERROR | UNKNOWN
    """
```

---

## ⭐ Worker 7: Logging System

**File**: `workers/core/logging.py`  
**Purpose**: Structured logging with context  
**Lines**: ~200

### Responsibilities
- JSON structured logging for production
- Human-readable text for development
- Automatic context injection
- File rotation
- Correlation IDs

### Key Functions
```python
def setup_logger(name: str, config: Config) -> logging.Logger:
    """Create structured logger with file and console handlers"""

class LogContext:
    """Context manager to inject metadata into logs"""
    
    def __init__(self, logger: logging.Logger, **context):
        self.logger = logger
        self.context = context
    
    def __enter__(self):
        # Inject context
        
    def __exit__(self, *args):
        # Clean up

class JSONFormatter(logging.Formatter):
    """JSON log formatter for production"""

class TextFormatter(logging.Formatter):
    """Human-readable formatter for development"""
```

### Usage Example
```python
with LogContext(logger, batch_id='batch_123', file_id='doc_456'):
    logger.info('Processing file')
    # Output: {"message": "Processing file", "batch_id": "batch_123", "file_id": "doc_456"}
```

---

## ⭐ Worker 8: Idempotency Helpers

**File**: `workers/core/idempotency.py`  
**Purpose**: Prevent duplicate processing  
**Lines**: ~150

### Responsibilities
- Unique doc_id constraint enforcement
- Atomic get-or-create operations
- Processing state validation
- Duplicate detection logging
- Stale process detection

### Key Functions
```python
def ensure_idempotent_file(
    doc_id: str,
    batch_id: str,
    file_info: dict
) -> Tuple[FileExtraction, bool]:
    """
    Get existing file or create new one atomically.
    Returns: (file_extraction, created)
    """

def should_reprocess_file(file_extraction: FileExtraction) -> bool:
    """
    Decide if a file should be reprocessed based on current state.
    Checks:
    - Already successful? No
    - Permanent error? No
    - Retryable error with retries left? Yes
    - Stale processing (>30min)? Yes
    """

def detect_stale_processing(
    file_extraction: FileExtraction,
    timeout_seconds: int = 1800
) -> bool:
    """Detect if processing has stalled"""
```

---

## ⭐ Worker 9: Filesystem Helpers

**File**: `workers/utils/filesystem.py`  
**Purpose**: Safe filesystem operations  
**Lines**: ~100

### Responsibilities
- Path validation and sanitization
- Storage path resolution
- File type detection
- Safe file operations
- Directory creation

### Key Functions
```python
def resolve_storage_path(relative_path: str, base_path: str = '/shared') -> str:
    """Convert relative path to absolute"""

def ensure_directory_exists(path: str) -> None:
    """Create directory if it doesn't exist"""

def get_file_type(file_path: str) -> str:
    """Detect file type from extension"""
    # Returns: pdf | word | excel | zip | text | unknown

def safe_read_file(file_path: str) -> bytes:
    """Read file with error handling"""

def safe_write_file(file_path: str, content: bytes) -> None:
    """Write file with error handling"""

def get_file_size(file_path: str) -> int:
    """Get file size in bytes"""

def list_files_in_directory(dir_path: str, pattern: str = '*') -> List[str]:
    """List files matching pattern"""
```

---

## 📦 Dependencies

**File**: `workers/requirements.txt`

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
tenacity==8.2.3
backoff==2.2.1

# Testing
pytest==7.4.3
pytest-cov==4.1.0
pytest-asyncio==0.21.1
faker==22.0.0

# Type checking
mypy==1.8.0
types-psycopg2==2.9.21.16
```

---

## 🧪 Test Files

### test_config.py
- Test environment variable loading
- Test validation rules
- Test default values
- Test connection string builder

### test_database.py
- Test model creation
- Test relationships
- Test query operations
- Test error handling

### test_retry.py
- Test backoff calculation
- Test retry decision logic
- Test max attempts enforcement
- Test jitter randomization

### test_errors.py
- Test error classification
- Test custom exception hierarchy
- Test error message formatting

### test_idempotency.py
- Test duplicate detection
- Test atomic operations
- Test reprocess logic
- Test stale process detection

---

## 📊 Implementation Checklist

### Core Infrastructure
- [ ] Worker 1: Configuration Management (`config.py`)
- [ ] Worker 2: Database Connection (`database/connection.py`)
- [ ] Worker 3: Database Models (`database/models.py`)
- [ ] Worker 4: Database Operations (`database/operations.py`)

### Error Handling & Retry
- [ ] Worker 5: Retry Logic (`core/retry.py`)
- [ ] Worker 6: Error Classification (`core/errors.py`)

### Logging & Utilities
- [ ] Worker 7: Logging System (`core/logging.py`)
- [ ] Worker 8: Idempotency Helpers (`core/idempotency.py`)
- [ ] Worker 9: Filesystem Helpers (`utils/filesystem.py`)

### Supporting Files
- [ ] `requirements.txt` - Python dependencies
- [ ] `.env.example` - Environment template
- [ ] `__init__.py` files for all packages

### Testing
- [ ] `test_config.py` - Configuration tests
- [ ] `test_database.py` - Database tests
- [ ] `test_retry.py` - Retry logic tests
- [ ] `test_errors.py` - Error handling tests
- [ ] `test_idempotency.py` - Idempotency tests

---

## 🎯 Success Metrics

Phase 3 is complete when:

✅ All 9 workers are implemented  
✅ All unit tests pass (>80% coverage)  
✅ Database models match Phase 1 schema  
✅ Configuration validates all env vars  
✅ Retry logic handles all error types  
✅ Logging produces valid JSON  
✅ Idempotency prevents duplicates  
✅ Documentation complete  

---

## 📈 Estimated Effort

| Category | Workers | Lines of Code | Duration |
|----------|---------|---------------|----------|
| Database Layer | 3 | 600 | 9h |
| Error Handling | 2 | 250 | 5h |
| Logging & Utils | 4 | 550 | 10h |
| Testing | 5 | 500 | 6h |
| **Total** | **14 files** | **~1900 LOC** | **30h (1.5-2 days)** |

---

## 🚀 Ready to Implement

All workers are well-defined, dependencies are clear, and the foundation is solid for Phase 4-5 implementation!
