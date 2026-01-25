# Phase 4 Design: File Processing & LLM Client

**Date**: January 22, 2026  
**Status**: 🎨 Design Phase  
**Prerequisites**: Phase 1 ✅, Phase 2 ✅, Phase 3 ✅

---

## 🎯 Goals

Build on Phase 3 foundation to add:
1. **File parsers** (PDF, Word, Excel) with Phase 3 error handling
2. **LLM client** (OpenAI) with Phase 3 retry logic
3. **Text extraction** from tender documents
4. **Simple chunking** (character-based, no embeddings)

---

## 📦 Components (4 modules)

```
workers/
├── processing/
│   ├── __init__.py
│   ├── parsers.py          # Module 1: PDF/Word/Excel parsers
│   ├── chunking.py         # Module 2: Text chunking
│   ├── llm_client.py       # Module 3: OpenAI client with retry
│   └── extractor.py        # Module 4: Main extraction orchestrator
└── tests/
    └── test_parsers.py     # Basic parser tests
```

---

## 📄 Module 1: File Parsers (`processing/parsers.py`)

**Purpose**: Extract raw text from PDF, Word, Excel files

### Dependencies
```python
PyPDF2==3.0.1           # PDF parsing
python-docx==1.1.0      # Word parsing
openpyxl==3.1.2         # Excel parsing
```

### Functions
```python
def parse_pdf(file_path: str) -> str:
    """Extract text from PDF using PyPDF2. Raises ParseError on failure."""

def parse_word(file_path: str) -> str:
    """Extract text from Word doc. Raises ParseError on failure."""

def parse_excel(file_path: str) -> str:
    """Extract text from Excel (all sheets concatenated). Raises ParseError."""

def parse_file(file_path: str) -> str:
    """Auto-detect type and parse. Uses Phase 3 filesystem.get_file_type()."""
```

### Error Handling
- Uses Phase 3 `ParseError` for corrupt files
- Uses Phase 3 `PermanentError` for unsupported types
- Uses Phase 3 `RetryableError` for temp I/O issues

---

## 📝 Module 2: Text Chunking (`processing/chunking.py`)

**Purpose**: Split large text into chunks for LLM context limits

### Strategy
- **Character-based chunking** (simple, no embeddings)
- Max chunk size: 3000 characters (fits in 4096 token limit with prompt)
- Overlap: 200 characters (preserve context)
- Split on paragraph boundaries when possible

### Functions
```python
def chunk_text(text: str, max_chunk_size: int = 3000, overlap: int = 200) -> list[str]:
    """Split text into overlapping chunks. Returns list of text chunks."""

def estimate_token_count(text: str) -> int:
    """Rough estimate: len(text) / 4. For validation only."""
```

### Why Simple?
- No embeddings (deferred to future)
- No semantic chunking (Phase 4 scope is basic extraction)
- Character-based is fast and reliable

---

## 🤖 Module 3: LLM Client (`processing/llm_client.py`)

**Purpose**: Call OpenAI API with Phase 3 retry logic

### Dependencies
```python
openai==1.10.0          # OpenAI SDK
```

### Configuration (from Phase 3)
```python
OPENAI_API_KEY          # Required
OPENAI_MODEL            # Default: gpt-4o-mini
OPENAI_MAX_TOKENS       # Default: 4096
OPENAI_RATE_LIMIT_RPM   # Default: 60 (for backoff)
```

### Functions
```python
def extract_tender_data(text: str, config: Config) -> dict:
    """
    Call OpenAI with tender extraction prompt.
    Returns: JSON matching ui_json schema (from LLM_EXTRACTION_FIELDS.md)
    Uses Phase 3 retry logic for RateLimitError.
    """

def _build_extraction_prompt(text: str) -> str:
    """Build prompt for tender data extraction."""

def _parse_llm_response(response: str) -> dict:
    """Parse LLM JSON response. Raises LLMError on invalid JSON."""
```

### Prompt Template
```text
Extract tender information from the following document.
Return ONLY valid JSON with this structure:
{
  "meta": {"tender_id": "...", "organization": "..."},
  "executive_summary": {"location_de": "..."},
  "mandatory_requirements": [{"requirement_de": "...", "category_de": "..."}],
  "risks": [{"risk_de": "...", "severity": "..."}],
  ...
}

Document:
{text}

JSON:
```

### Retry Strategy
```python
# Uses Phase 3 with_retry_backoff with:
- RateLimitError → Retry with exponential backoff
- LLMError (invalid response) → Retry up to max_attempts
- TimeoutError → Retry
- Other errors → Fail immediately
```

---

## 🔧 Module 4: Extraction Orchestrator (`processing/extractor.py`)

**Purpose**: Coordinate parsing → chunking → LLM → DB

### Main Function
```python
def process_file(doc_id: str, file_path: str, config: Config):
    """
    Full file processing pipeline:
    1. Load file from shared volume
    2. Parse file (PDF/Word/Excel)
    3. Chunk text if too long
    4. Extract data via LLM (per chunk or whole doc)
    5. Merge results from chunks
    6. Write to file_extractions table
    
    Uses Phase 3:
    - logging.log_context(doc_id=doc_id)
    - operations.mark_file_processing_start()
    - operations.mark_file_success() / mark_file_failed()
    - errors.classify_error()
    """
```

### Processing Flow
```
1. Get file from DB (operations.get_file_by_doc_id)
2. Mark processing start (operations.mark_file_processing_start)
3. Parse file (parsers.parse_file) → text
4. If text > 3000 chars: chunk_text(text) → chunks[]
5. For each chunk: extract_tender_data(chunk) → partial_data
6. Merge all partial_data → final_extraction
7. Mark success (operations.mark_file_success(final_extraction))
8. On error: classify_error() + mark_file_failed()
```

### Merge Strategy (Multi-Chunk)
```python
def merge_extractions(chunks_data: list[dict]) -> dict:
    """
    Merge multiple chunk extractions into single result.
    - meta: Use first chunk
    - mandatory_requirements: Union of all chunks
    - risks: Union of all chunks
    - timeline_milestones: Merge (use non-null values)
    """
```

---

## 📊 Data Flow

```
File Upload (Phase 6)
    ↓
ZIP Extraction (Phase 6)
    ↓
process_file() [Phase 4]
    ↓
1. Load file_path from DB
2. Parse PDF/Word/Excel → text
3. Chunk if needed → chunks[]
4. LLM extract per chunk → data[]
5. Merge chunks → final_data
6. Write to file_extractions.extracted_json
    ↓
Aggregation (Phase 9)
    ↓
run_summaries.ui_json
    ↓
Frontend (Phase 10)
```

---

## 🔗 Phase 3 Integration

| Phase 3 Component | Phase 4 Usage |
|-------------------|---------------|
| `core/errors.py` | ParseError, LLMError, RateLimitError |
| `core/retry.py` | LLM API calls with backoff |
| `core/logging.py` | Log extraction progress |
| `database/operations.py` | mark_file_start, mark_file_success/failed |
| `utils/filesystem.py` | safe_read_file, get_file_type |
| `config.py` | OPENAI_API_KEY, model, tokens |

---

## 📋 Implementation Checklist

- [ ] `processing/__init__.py`
- [ ] `processing/parsers.py` (PDF, Word, Excel)
- [ ] `processing/chunking.py` (character-based)
- [ ] `processing/llm_client.py` (OpenAI with retry)
- [ ] `processing/extractor.py` (orchestrator)
- [ ] `tests/test_parsers.py`
- [ ] Update `requirements.txt` (PyPDF2, python-docx, openpyxl, openai)

---

## ✅ Alignment Verification

### Scope Compliance
| Should Include | Status |
|---------------|--------|
| File parsing (PDF, Word, Excel) | ✅ IN SCOPE |
| LLM client (OpenAI) | ✅ IN SCOPE |
| Text chunking | ✅ IN SCOPE (simple) |
| Extraction orchestration | ✅ IN SCOPE |

| Should NOT Include | Status |
|-------------------|--------|
| HTTP API | ✅ DEFERRED to Phase 5 |
| Embeddings | ✅ DEFERRED (future) |
| Semantic chunking | ✅ DEFERRED (future) |

### Requirements Compliance
- ✅ Uses Phase 3 error handling (no new error system)
- ✅ Uses Phase 3 retry logic (no new retry system)
- ✅ Uses Phase 3 database models (writes to `extracted_json`)
- ✅ Simple, not over-engineered (standard parsing libraries)
- ✅ Workers handle heavy logic (LLM calls, parsing)

### Frontend Contract
- ✅ LLM outputs `ui_json` schema from `LLM_EXTRACTION_FIELDS.md`
- ✅ Writes to `file_extractions.extracted_json` (Phase 1 schema)
- ✅ No changes to frontend required

---

## 📈 Estimated Effort

| Module | LOC | Duration |
|--------|-----|----------|
| parsers.py | 150 | 3h |
| chunking.py | 80 | 2h |
| llm_client.py | 120 | 3h |
| extractor.py | 200 | 4h |
| tests | 100 | 2h |
| **Total** | **650** | **14h (~1 day)** |

---

## 🚀 Ready to Implement

Phase 4 builds directly on Phase 3 with:
- ✅ Clear scope (parsing + LLM)
- ✅ Simple approach (no over-engineering)
- ✅ Full Phase 3 integration (errors, retry, logging, DB)
- ✅ Aligned with frontend contract
- ✅ Ready for Phase 5 (HTTP API wrapper)
