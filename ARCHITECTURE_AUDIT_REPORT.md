# Architecture & Capability Audit Report

**Date**: 2026-01-23  
**System**: Tender Document Processing System  
**Audit Type**: Architecture validation, queue system review, file handling capabilities

---

## EXECUTIVE SUMMARY

### Critical Findings

1. **❌ NO QUEUE SYSTEM EXISTS**: Despite Redis being available, the system uses direct HTTP calls, not queues
2. **❌ NESTED ZIPs NOT SUPPORTED**: Only single-level ZIP extraction implemented
3. **✅ PARTIAL FILE SUPPORT**: PDF/DOCX/XLSX supported, CSV/TXT recognized but not parsed
4. **✅ ARCHITECTURE WORKING**: System is functional but not as originally intended

### Recommendations Priority

| Priority | Item | Impact | Complexity |
|----------|------|--------|------------|
| **HIGH** | Implement queue system | Scalability, reliability | Medium |
| **MEDIUM** | Add nested ZIP support | User experience | Low |
| **LOW** | Add CSV/TXT parsers | Feature completeness | Low |

---

## PART 1: QUEUE ARCHITECTURE ANALYSIS

### Current State: HTTP-Based (NOT Queue-Based)

```
┌─────────────┐
│   Upload    │
│  (create    │
│   batch)    │
└──────┬──────┘
       │
       ↓
┌──────────────┐
│ POST /process│
│   (trigger   │
│  async func) │
└──────┬───────┘
       │
       ↓
┌──────────────────┐      ┌──────────────┐
│  processBatch()  │─────→│ HTTP POST to │
│  (orchestrator)  │      │    Worker    │
└──────────────────┘      └──────┬───────┘
                                 │
                                 ↓
                          ┌─────────────┐
                          │   Worker    │
                          │  (FastAPI)  │
                          └─────────────┘
```

### Evidence: No Queue Implementation

**package.json (lines 20-30):**
```json
"dependencies": {
  "adm-zip": "^0.5.10",
  "axios": "^1.13.2",
  "cors": "^2.8.5",
  "dotenv": "^16.3.1",
  "express": "^4.18.2",
  "express-rate-limit": "^7.5.1",
  "form-data": "^4.0.5",
  "multer": "^2.0.2",
  "pg": "^8.11.3"
}
```
**❌ Missing**: `bullmq`, `ioredis`, `redis`, `bee-queue`, `bull`, etc.

**workers/requirements.txt (lines 1-27):**
```txt
sqlalchemy==2.0.42
psycopg[binary]==3.2.3
python-dotenv==1.0.0
PyPDF2==3.0.1
python-docx==1.1.0
openpyxl==3.1.2
openai>=1.30.0
fastapi==0.110.0
uvicorn==0.27.1
```
**❌ Missing**: `redis`, `celery`, `rq`, etc.

**Codebase scan results:**
```bash
$ grep -r "queue\|Bull\|bullmq\|enqueue\|dequeue" src/ workers/
# No matches found (except database status field "queued")
```

### What "Queued" Actually Means

**In the database (processing_jobs table):**
- `status = 'queued'` is just a **status field**, not a queue
- No actual job queue exists
- Jobs are processed via direct function calls

**Current flow (src/services/orchestrator.js lines 114-125):**
```javascript
await runWithConcurrency(
  files,
  async (file) => {
    console.log(`[Orchestrator] → Processing file: ${file.doc_id}`);
    try {
      const startTime = Date.now();
      await workerClient.processFile(file.doc_id);  // ← DIRECT HTTP CALL
      const duration = Date.now() - startTime;
      succeeded += 1;
      console.log(`[Orchestrator] ✓ File ${file.doc_id} completed in ${duration}ms`);
```

**workerClient.js (lines 27-36):**
```javascript
async processFile(docId) {
  try:
    const response = await axiosInstance.post("/process-file", {  // ← HTTP POST
      doc_id: docId,
    });
    return response.data;
```

### Architecture Roles (As Implemented)

| Component | Current Role | Queue-Based Role (Expected) |
|-----------|--------------|---------------------------|
| **API** | Triggers `processBatch()` directly | Should **enqueue** jobs |
| **Redis** | Docker container exists but **unused** | Should be **queue backend** |
| **Orchestrator** | Makes **direct HTTP calls** | Should **enqueue** only |
| **Worker** | HTTP server (`FastAPI`) | Should **consume from queue** |

### Limitations of Current Architecture

❌ **No job persistence**: If backend crashes, in-flight jobs are lost  
❌ **No built-in retry**: Must implement manually in orchestrator  
❌ **Cannot scale workers**: HTTP endpoint tied to single process  
❌ **No priority**: All files processed in arbitrary order  
❌ **No monitoring**: Cannot see queue depth, pending jobs, etc.  
❌ **Synchronous bottleneck**: Orchestrator waits for each HTTP response  

### Redis Status

**Setup**: Docker container `redis-local` is running on `localhost:6379`  
**Usage**: **NONE** - only exists for testing, not integrated into codebase  
**Evidence**: `docs/REDIS_DOCKER_TESTING.md` shows manual Redis setup, but no code uses it

---

## PART 2: ZIP & NESTED CONTENT HANDLING

### Current Extraction Logic

**src/services/zipExtractor.js (lines 44-47):**
```javascript
const AdmZip = (await import("adm-zip")).default;
const zip = new AdmZip(zipPath);
zip.extractAllTo(extractPath, true);  // ← Extracts once, no recursion
console.log(`[ZipExtractor] ZIP extracted successfully`);
```

**File discovery (lines 55-68):**
```javascript
for (const file of extractedFiles) {
  const fullPath = path.join(extractPath, file);
  const stats = await fs.stat(fullPath);

  if (stats.isFile()) {
    const ext = path.extname(file).toLowerCase();
    const supportedExtensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx"];
    // ← .zip NOT included, nested ZIPs are ignored
    
    if (supportedExtensions.includes(ext)) {
      files.push({
        filename: path.basename(file),
        file_path: path.join(STORAGE_EXTRACTED_DIR, batchId, file),
        file_type: ext.substring(1),
      });
```

### Capabilities

| Feature | Supported | Notes |
|---------|-----------|-------|
| **Single ZIP extraction** | ✅ Yes | Works correctly |
| **Folder traversal** | ✅ Yes | `fs.readdir(..., {recursive: true})` |
| **Nested ZIPs** | ❌ No | Treated as unsupported file type |
| **Recursive extraction** | ❌ No | No logic to detect/extract nested ZIPs |
| **Depth limit** | ❌ No | Would be infinite if implemented |
| **Path preservation** | ⚠️ Partial | `filename` only, not full path |

### Test Case: Nested ZIP

**Input:**
```
test.zip
├── doc1.pdf
├── nested.zip
│   ├── doc2.docx
│   └── doc3.xlsx
└── folder/
    └── doc4.pdf
```

**Current behavior:**
- ✅ `doc1.pdf` → extracted and processed
- ❌ `nested.zip` → **ignored** (not in supportedExtensions)
- ✅ `folder/doc4.pdf` → extracted and processed
- **Result**: 2 files processed (doc1.pdf, doc4.pdf), 2 files missed (doc2.docx, doc3.xlsx)

**Expected behavior:**
- ✅ All 4 documents should be extracted and processed
- ✅ Nested ZIP should be detected and recursively extracted
- ✅ Original hierarchy should be preserved in metadata

---

## PART 3: FILE TYPE SUPPORT MATRIX

### Supported File Types (Current)

| File Type | Supported | Parser Library | Function | Notes |
|-----------|-----------|----------------|----------|-------|
| **PDF** | ✅ Yes | PyPDF2 | `parse_pdf()` | Full text extraction |
| **DOCX** | ✅ Yes | python-docx | `parse_word()` | Paragraphs → text |
| **DOC** | ✅ Yes | python-docx | `parse_word()` | Legacy Word format |
| **XLSX** | ✅ Yes | openpyxl | `parse_excel()` | All sheets, row-by-row |
| **XLS** | ✅ Yes | openpyxl | `parse_excel()` | Legacy Excel format |
| **CSV** | ❌ No | None | ❌ Missing | Type recognized but no parser |
| **TXT** | ❌ No | None | ❌ Missing | Type recognized but no parser |
| **ZIP** | ⚠️ Partial | adm-zip | N/A | Top-level only, no nesting |

### Parser Implementation

**workers/processing/parsers.py (lines 13-43):**
```python
def parse_pdf(file_path: str) -> str:
    try:
        with open(file_path, "rb") as handle:
            reader = PyPDF2.PdfReader(handle)
            return "\n".join(page.extract_text() or "" for page in reader.pages)
    except Exception as exc:
        raise ParseError(f"Failed to parse PDF: {file_path}") from exc

def parse_word(file_path: str) -> str:
    try:
        doc = Document(file_path)
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    except Exception as exc:
        raise ParseError(f"Failed to parse Word document: {file_path}") from exc

def parse_excel(file_path: str) -> str:
    try:
        wb = load_workbook(filename=file_path, data_only=True)
        chunks: list[str] = []
        for sheet in wb.worksheets:
            chunks.append(f"## {sheet.title}")
            for row in sheet.iter_rows(values_only=True):
                row_text = " | ".join("" if value is None else str(value) for value in row)
                if row_text.strip():
                    chunks.append(row_text)
        return "\n".join(chunks)
    except Exception as exc:
        raise ParseError(f"Failed to parse Excel file: {file_path}") from exc
```

**Main parser dispatcher (lines 45-53):**
```python
def parse_file(file_path: str) -> str:
    file_type = get_file_type(file_path)
    if file_type == "pdf":
        return parse_pdf(file_path)
    if file_type == "word":
        return parse_word(file_path)
    if file_type == "excel":
        return parse_excel(file_path)
    # ← CSV and TXT fall through to error
    raise PermanentError(f"Unsupported file type: {file_path}")
```

### Type Detection

**workers/utils/filesystem.py (lines 19-30):**
```python
def get_file_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    mapping = {
        ".pdf": "pdf",
        ".doc": "word",
        ".docx": "word",
        ".xls": "excel",
        ".xlsx": "excel",
        ".zip": "zip",
        ".txt": "text",   # ← Recognized but no parser
        ".csv": "csv",    # ← Recognized but no parser
    }
    return mapping.get(ext, "unknown")
```

### Extraction Filter

**src/services/zipExtractor.js (line 61):**
```javascript
const supportedExtensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx"];
// ← CSV and TXT NOT included in extraction filter
```

**Issue**: CSV/TXT files are **filtered out during extraction**, never reaching the parser.

### Failure Behavior

**Scenario 1: Unsupported file in ZIP**
- File is **skipped** during extraction
- Not added to `file_extractions` table
- No error logged (just `console.log` with "unsupported")

**Scenario 2: File reaches parser but unsupported**
- Worker throws `PermanentError`
- File marked as `FAILED` in database
- Error logged: "Unsupported file type"

---

## PART 4: IMPLEMENTATION RECOMMENDATIONS

### Recommendation 1: Add Queue System (HIGH PRIORITY)

**Why**: 
- Enables job persistence (survives crashes)
- Built-in retry and priority support
- Scalable worker pool
- Proper monitoring

**How**: See `QUEUE_MIGRATION_PLAN.md`

**Effort**: Medium (2-3 days)
- Install BullMQ + ioredis
- Create queue service
- Update orchestrator to enqueue
- Create Python queue consumer
- Dual-mode deployment for backward compatibility

### Recommendation 2: Add Nested ZIP Support (MEDIUM PRIORITY)

**Why**:
- Common use case (documents organized in nested folders)
- User expects all files to be processed
- Prevents manual re-upload

**How**: See `NESTED_ZIP_AND_FILE_SUPPORT.md`

**Effort**: Low (4-6 hours)
- Implement recursive extraction function
- Add depth limit (MAX_ZIP_DEPTH=3)
- Preserve original path hierarchy
- Add safety checks (infinite recursion prevention)

### Recommendation 3: Add CSV/TXT Parsers (LOW PRIORITY)

**Why**:
- CSV common in tender documents (pricing tables, etc.)
- TXT files for requirements, notes
- Simple to implement (stdlib only)

**How**: See `NESTED_ZIP_AND_FILE_SUPPORT.md` (Part 2)

**Effort**: Low (2-3 hours)
- Add `parse_csv()` using Python csv module
- Add `parse_txt()` using open()
- Update `parse_file()` dispatcher
- Add `.csv`, `.txt` to extraction filter

---

## PART 5: VERIFICATION PLAN

### Test 1: Queue System (after implementation)

```powershell
# 1. Check queue is connected
docker exec -it redis-local redis-cli ping
# Expected: PONG

# 2. Upload batch
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "test.zip"}
$batchId = $upload.batch_id

# 3. Trigger processing
Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{"concurrency":2}'

# 4. Check queue depth
docker exec -it redis-local redis-cli LLEN bullmq:file-processing:wait
# Expected: > 0 initially, → 0 as processed

# 5. Monitor status
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
# Expected: files move from pending → processing → SUCCESS
```

### Test 2: Nested ZIP

**Create test file:**
```powershell
# Create nested.zip with structure:
# nested.zip
#   ├── doc1.pdf
#   ├── inner.zip
#   │   ├── doc2.docx
#   │   └── doc3.xlsx
#   └── folder/
#       └── doc4.csv
```

**Upload and process:**
```powershell
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "nested.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
# Expected: total_files = 4 (all files extracted including from inner.zip)
```

**Check logs:**
```
[ZipExtractor] Extracting (depth 0): uploads\batch_abc...zip
[ZipExtractor]   ✓ doc1.pdf (.pdf, depth 0)
[ZipExtractor] Extracting (depth 1): extracted\batch_abc...\inner.zip
[ZipExtractor]   ✓ doc2.docx (.docx, depth 1)
[ZipExtractor]   ✓ doc3.xlsx (.xlsx, depth 1)
[ZipExtractor]   ✓ folder/doc4.csv (.csv, depth 0)
[ZipExtractor] 4 supported files found (including nested)
```

### Test 3: Mixed File Types

**Create mixed.zip:**
```
mixed.zip
├── document.pdf
├── spreadsheet.xlsx
├── data.csv (NEW)
└── notes.txt (NEW)
```

**Upload and process:**
```powershell
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "mixed.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
# Expected: total_files = 4, files_success = 4
```

**Check worker logs:**
```
Processing file: ...document.pdf
Parsed 12345 characters from ...document.pdf
Processing file: ...spreadsheet.xlsx
Parsed 5678 characters from ...spreadsheet.xlsx
Processing file: ...data.csv
Parsed 234 characters from ...data.csv
Processing file: ...notes.txt
Parsed 89 characters from ...notes.txt
```

### Test 4: Depth Limit

**Create deeply_nested.zip:**
```
deeply_nested.zip
└── level1.zip
    └── level2.zip
        └── level3.zip
            └── level4.zip (should be skipped)
                └── doc.pdf
```

**Expected:**
- Extraction stops at depth 3
- `level4.zip` is not extracted
- Warning logged: "Max depth 3 reached"
- `doc.pdf` inside level4.zip is NOT processed

---

## SUMMARY

### Current State

✅ **Working**: System processes PDF/DOCX/XLSX files via HTTP calls  
⚠️ **Incomplete**: No queue system, no nested ZIPs, no CSV/TXT  
❌ **Misconception**: System described as queue-based but isn't  

### Required Changes

| Item | Priority | Effort | Files Changed |
|------|----------|--------|---------------|
| **Queue system** | HIGH | Medium | 5 files (new + modified) |
| **Nested ZIPs** | MEDIUM | Low | 1 file (zipExtractor.js) |
| **CSV/TXT parsers** | LOW | Low | 1 file (parsers.py) |

### Migration Path

**Phase 1**: Add queue system (dual-mode for safety)  
**Phase 2**: Add nested ZIP support + CSV/TXT parsers  
**Phase 3**: Switch to queue-only mode  
**Phase 4**: Remove HTTP processing endpoints  

### Documentation Created

1. `QUEUE_MIGRATION_PLAN.md` - Full queue implementation guide
2. `NESTED_ZIP_AND_FILE_SUPPORT.md` - Recursive extraction + parsers
3. `ARCHITECTURE_AUDIT_REPORT.md` - This document

---

## CONCLUSION

The system is **functional but architecturally incomplete**:
- Redis exists but is unused
- HTTP calls work but aren't scalable
- File support is partial but extensible

**Recommendation**: Implement queue system first (highest impact on reliability and scalability), then add nested ZIP + CSV/TXT support (user-facing features).
