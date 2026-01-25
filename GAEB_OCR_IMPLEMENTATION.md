# GAEB + OCR PDF Support Implementation

## Overview

This implementation adds two critical features for German tender processing:
1. **GAEB file support** - Extract structured data from German tender exchange format files
2. **OCR PDF support** - Extract text from scanned/image-based PDFs using Tesseract OCR

Both features feed into the **same extraction pipeline** and produce identical structured outputs.

---

## PART A: GAEB Support

### What is GAEB?

GAEB (Gemeinsamer Ausschuss Elektronik im Bauwesen) is the German standard for electronic tender data exchange in construction. Files contain:
- Leistungsverzeichnis (Bill of Quantities / BoQ)
- Position numbers (OZ - Ordnungszahl)
- Descriptions, quantities, units, prices
- Project metadata, notes, remarks

### File Extensions Supported

All standard GAEB extensions are now recognized:
```
.x83, .x84, .x85, .x86, .x89  (Exchange formats)
.d83, .d84, .d85, .d86, .d89  (Data formats)
.p83, .p84, .p85, .p86, .p89  (Price formats)
.gaeb                         (Generic)
```

### Implementation Details

**File: `workers/utils/filesystem.py` (lines 19-48)**
```python
def get_file_type(file_path: str) -> str:
    ext = Path(file_path).suffix.lower()
    mapping = {
        ...
        # GAEB formats
        ".x83": "gaeb",
        ".x84": "gaeb",
        ".x85": "gaeb",
        ".x86": "gaeb",
        ".x89": "gaeb",
        ".d83": "gaeb",
        # ... all GAEB extensions ...
    }
```

**File: `workers/processing/parsers.py` (lines 97-161)**

The GAEB parser extracts:
- ✅ Project title (`BoQTitle`)
- ✅ Leistungsverzeichnis sections (`BoQInfo`)
- ✅ Position numbers (`OZ`)
- ✅ Descriptions (`Description/CompleteText/DetailTxt`)
- ✅ Quantities + Units (`Qty`, `QU`)
- ✅ Prices (`UP` - Unit Price)
- ✅ Notes and remarks

**Output format (normalized text):**
```
=== GAEB LEISTUNGSVERZEICHNIS ===

Projekt: Neubau Bürogebäude - Leistungsverzeichnis

## Leistungsverzeichnis Rohbau

01.01.010 | Oberboden abtragen, Dicke 20 cm, seitlich lagern | Menge: 450 m³ | Preis: 12.50
01.01.020 | Baugrube ausheben, Tiefe bis 3 m | Menge: 850 m³ | Preis: 18.75
02.01.010 | Stahlbeton C25/30 für Fundamente einbauen | Menge: 125 m³ | Preis: 285.00

Hinweis: Alle Preise verstehen sich netto. Ausführungsfrist: 6 Monate.
```

### Error Handling

```python
# If GAEB parsing fails
try:
    parse_gaeb(file_path)
except ParseError as exc:
    # Stored in file_extractions:
    # - status='FAILED'
    # - error=str(exc)
    # - error_type='PARSE_ERROR'
```

### Logging

```
[Parser] GAEB file detected: sample.x83
[Parser] Extracted 2456 characters from GAEB (12 positions)
```

---

## PART B: OCR PDF Support

### Detection Logic

**Trigger OCR when:**
- `ENABLE_OCR=true` in config
- PDF text extraction returns < 100 characters (likely scanned)

**File: `workers/processing/parsers.py` (lines 50-94)**
```python
def parse_pdf(file_path: str, enable_ocr: bool = False, ocr_max_pages: int = 50) -> str:
    with open(file_path, "rb") as handle:
        reader = PyPDF2.PdfReader(handle)
        text_content = "\n".join(page.extract_text() or "" for page in reader.pages)
        
        # Check if PDF is scanned (no/minimal text)
        if enable_ocr and _OCR_AVAILABLE and len(text_content.strip()) < 100:
            print(f"[Parser] PDF appears scanned ({len(text_content)} chars), running OCR...")
            
            # Limit pages to prevent runaway jobs
            num_pages = len(reader.pages)
            pages_to_ocr = min(num_pages, ocr_max_pages)
            
            images = convert_from_path(file_path, dpi=300, first_page=1, last_page=pages_to_ocr)
            ocr_chunks = [_ocr_pdf_page(img) for img in images]
            ocr_text = "\n\n=== PAGE BREAK ===\n\n".join(ocr_chunks)
            
            if len(ocr_text.strip()) > 100:
                print(f"[Parser] OCR successful: {len(ocr_text)} chars from {pages_to_ocr} pages")
                return ocr_text
```

### Dependencies

```txt
pytesseract>=0.3.10    # Python wrapper for Tesseract OCR
Pillow>=10.0.0         # Image processing
pdf2image>=1.16.3      # Convert PDF pages to images
```

**System requirement:** Tesseract OCR must be installed on the system.

### Safety Features

✅ **Page limit**: `OCR_MAX_PAGES` (default 50) prevents processing huge documents  
✅ **DPI cap**: 300 DPI balances quality and performance  
✅ **Fallback**: If OCR fails, returns original text (even if empty)  
✅ **Optional**: Can be disabled with `ENABLE_OCR=false`  
✅ **Language support**: `lang="deu+eng"` for German + English

### Performance

| PDF Type | Pages | Processing Time (est.) |
|----------|-------|------------------------|
| Normal (selectable text) | Any | ~1-3 seconds |
| Scanned (10 pages) | 10 | ~15-30 seconds |
| Scanned (50 pages, max) | 50 | ~60-180 seconds |

### Logging

```
[Parser] PDF appears scanned (34 chars), running OCR...
[Parser] OCR successful: 15234 chars from 12 pages
```

Or if OCR not available:
```
[Parser] PDF appears scanned but OCR not available (install pytesseract)
```

---

## Configuration Flags

### Backend `.env`
```bash
MAX_ZIP_DEPTH=3  # Support nested ZIPs
```

### Workers `.env`
```bash
# OCR Configuration
ENABLE_OCR=true
OCR_MAX_PAGES=50

# GAEB Configuration
GAEB_ENABLED=true
```

---

## Installation

### Step 1: Install Python Dependencies

```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend\workers
pip install --user -r requirements.txt
```

This installs:
- `lxml` - GAEB XML parsing
- `pytesseract` - OCR wrapper
- `Pillow` - Image handling
- `pdf2image` - PDF to image conversion

### Step 2: Install Tesseract OCR (Windows)

**Option A: Via Chocolatey**
```powershell
choco install tesseract
```

**Option B: Manual Download**
1. Download from: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Program Files\Tesseract-OCR`
3. Add to PATH:
   ```powershell
   $env:PATH += ";C:\Program Files\Tesseract-OCR"
   ```
4. Download German language data:
   - Get `deu.traineddata` from https://github.com/tesseract-ocr/tessdata
   - Place in: `C:\Program Files\Tesseract-OCR\tessdata\`

**Option C: Portable (if admin access not available)**
1. Download portable Tesseract
2. Set environment variable in `workers/.env`:
   ```bash
   TESSERACT_CMD=C:\path\to\tesseract.exe
   ```

### Step 3: Verify Tesseract Installation

```powershell
tesseract --version
```

Expected output:
```
tesseract 5.x.x
 leptonica-1.x.x
```

### Step 4: Update Environment Variables

**workers/.env (add these lines):**
```bash
ENABLE_OCR=true
OCR_MAX_PAGES=50
GAEB_ENABLED=true
```

### Step 5: Restart Queue Worker

```powershell
# Stop current worker (Ctrl+C)

# Start fresh
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
python -m workers.queue_worker
```

---

## Updated File Support Matrix

| File Type | Status | Parser | OCR/Special | Notes |
|-----------|--------|--------|-------------|-------|
| **PDF** | ✅ Full | PyPDF2 + OCR | Automatic fallback | OCR if <100 chars |
| **DOCX/DOC** | ✅ Full | python-docx | - | Standard |
| **XLSX/XLS** | ✅ Full | openpyxl | - | Standard |
| **CSV** | ✅ Full | csv (stdlib) | - | Standard |
| **TXT** | ✅ Full | open() | - | Standard |
| **GAEB** | ✅ Full | lxml (XML parsing) | - | All German formats |
| **ZIP (nested)** | ✅ Full | adm-zip | Recursive, depth=3 | Standard |

---

## Verification Checklist

### Test 1: GAEB File Processing

**Create test ZIP:**
```powershell
# Create a ZIP containing the sample GAEB file
Compress-Archive -Path "workers\tests\fixtures\sample_gaeb.x83" -DestinationPath "test_gaeb.zip"
```

**Upload and process:**
```powershell
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "test_gaeb.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

# Check status
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
# Expected: total_files=1, files_success=1
```

**Check worker logs:**
```
[QueueWorker] Processing doc_id=batch_abc..._uuid
Processing file: C:\Users\...\sample_gaeb.x83 (type: gaeb)
Parsed 2456 characters from ...
Successfully processed batch_abc..._uuid
```

**Check extracted data:**
```powershell
$files = Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/files"
$files.files[0].extracted_json
# Should contain tender data extracted by LLM from GAEB text
```

### Test 2: Scanned PDF Processing

**Create test with scanned PDF:**
```powershell
# Upload ZIP with scanned PDF (no selectable text)
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "scanned_tender.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'
```

**Check worker logs:**
```
Processing file: C:\Users\...\scanned_document.pdf (type: pdf)
[Parser] PDF appears scanned (34 chars), running OCR...
[Parser] OCR successful: 15234 chars from 12 pages
Parsed 15234 characters from ...
Split into 6 chunks, calling LLM...
Successfully processed batch_abc..._uuid
```

**Expected behavior:**
- ✅ OCR triggered automatically
- ✅ Text extracted from scanned pages
- ✅ Processed same as normal PDF
- ✅ `extracted_json` contains tender data

### Test 3: Mixed ZIP (GAEB + Scanned PDF + Normal PDF)

**Create ZIP with:**
```
mixed_tender.zip
├── tender_specs.pdf (normal PDF)
├── floor_plans.pdf (scanned PDF)
└── bill_of_quantities.x84 (GAEB)
```

**Upload and process:**
```powershell
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "mixed_tender.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
# Expected: total_files=3, files_success=3
```

**Worker logs should show:**
```
[QueueWorker] Processing doc_id=... (tender_specs.pdf)
Processing file: ...tender_specs.pdf (type: pdf)
Parsed 5678 characters from ... (no OCR needed)

[QueueWorker] Processing doc_id=... (floor_plans.pdf)
Processing file: ...floor_plans.pdf (type: pdf)
[Parser] PDF appears scanned (12 chars), running OCR...
[Parser] OCR successful: 3421 chars from 8 pages

[QueueWorker] Processing doc_id=... (bill_of_quantities.x84)
Processing file: ...bill_of_quantities.x84 (type: gaeb)
Parsed 12456 characters from GAEB (45 positions)
```

### Test 4: Single File Test Harness

**Test GAEB file directly:**
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
python test_single_file.py workers\tests\fixtures\sample_gaeb.x83
```

**Expected output:**
```
============================================================
Testing file: workers\tests\fixtures\sample_gaeb.x83
============================================================

Config loaded:
  - ENABLE_OCR: True
  - OCR_MAX_PAGES: 50
  - GAEB_ENABLED: True

Parsing file...

============================================================
SUCCESS
============================================================
Extracted 2456 characters

First 500 characters:
------------------------------------------------------------
=== GAEB LEISTUNGSVERZEICHNIS ===

Projekt: Neubau Bürogebäude - Leistungsverzeichnis

## Leistungsverzeichnis Rohbau

01.01.010 | Oberboden abtragen, Dicke 20 cm, seitlich lagern | Menge: 450 m³ | Preis: 12.50
01.01.020 | Baugrube ausheben, Tiefe bis 3 m | Menge: 850 m³ | Preis: 18.75
...
------------------------------------------------------------

File can be processed successfully!
```

**Test scanned PDF:**
```powershell
python test_single_file.py path\to\scanned.pdf
```

---

## Troubleshooting

### Issue: GAEB Files Not Detected

**Symptoms:**
- GAEB files skipped during extraction
- Status shows "No supported files found"

**Check:**
```powershell
# Verify GAEB extension is in SUPPORTED_EXTENSIONS
# Check backend logs during extraction
```

**Fix:**
- Ensure `src/services/zipExtractor.js` includes all GAEB extensions
- Check file has correct extension (not .xml or other)

### Issue: GAEB Parsing Fails

**Symptoms:**
- Worker logs show: `ParseError: Failed to parse GAEB file`
- File marked as FAILED

**Check:**
```powershell
python test_single_file.py path\to\file.x84
```

**Common causes:**
1. **lxml not installed:**
   ```powershell
   pip install lxml
   ```

2. **Invalid XML:**
   - File corrupt or not actually GAEB format
   - Check with XML validator

3. **Unknown GAEB version:**
   - Parser uses `local-name()` for version-agnostic extraction
   - Should work with all versions, but some edge cases possible

**Fix:**
- Check error message in worker logs
- Try opening file in GAEB viewer software
- Share error for debugging

### Issue: OCR Not Working

**Symptoms:**
- Scanned PDFs return empty text
- No OCR logs appear

**Check:**
```powershell
# Verify tesseract installed
tesseract --version

# Check if pytesseract can find tesseract
python -c "import pytesseract; print(pytesseract.get_tesseract_version())"
```

**Common causes:**

1. **Tesseract not installed:**
   ```powershell
   choco install tesseract
   ```

2. **Tesseract not in PATH:**
   ```powershell
   # Add to workers/.env
   TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
   ```
   
   Then in parsers.py before using pytesseract:
   ```python
   if config.tesseract_cmd:
       pytesseract.pytesseract.tesseract_cmd = config.tesseract_cmd
   ```

3. **German language data missing:**
   - Download `deu.traineddata`
   - Place in `C:\Program Files\Tesseract-OCR\tessdata\`

4. **pdf2image dependencies missing (Windows):**
   - Requires poppler-utils
   - Download from: https://github.com/oschwartz10612/poppler-windows/releases
   - Add to PATH or set `POPPLER_PATH` in config

**Fix:**
```powershell
# Test OCR manually
python -c "import pytesseract; from PIL import Image; print(pytesseract.image_to_string(Image.open('test.png'), lang='deu+eng'))"
```

### Issue: OCR Too Slow

**Symptoms:**
- Files take 5+ minutes to process
- Worker appears hung

**Fix:**
Reduce `OCR_MAX_PAGES` in `workers/.env`:
```bash
OCR_MAX_PAGES=20  # Process first 20 pages only
```

Or disable OCR for specific batches:
```bash
ENABLE_OCR=false
```

### Issue: OCR Memory Usage

**Symptoms:**
- Worker crashes with MemoryError
- System becomes unresponsive

**Fix:**
1. Lower DPI (in parsers.py, change `dpi=300` → `dpi=200`)
2. Reduce `OCR_MAX_PAGES`
3. Process PDFs in smaller batches

---

## File Type Routing Map

**Current flow:**
```
1. Upload ZIP
   ↓
2. zipExtractor.js checks extension against SUPPORTED_EXTENSIONS
   ├─→ .pdf → extracted
   ├─→ .x83, .x84, .x85, .x86 → extracted (GAEB)
   └─→ other → skipped
   ↓
3. File record created with file_type (pdf, gaeb, word, etc.)
   ↓
4. Queue worker pops job
   ↓
5. extractor.py → parse_file(path, enable_ocr, ocr_max_pages)
   ↓
6. parsers.py routes based on file_type:
   ├─→ "pdf" → parse_pdf() → check if scanned → OCR if needed
   ├─→ "gaeb" → parse_gaeb() → extract XML structure
   ├─→ "word" → parse_word()
   └─→ "excel" → parse_excel()
   ↓
7. Normalized text → chunking → LLM extraction
   ↓
8. Same DB schema: file_extractions.extracted_json
```

---

## Database Schema (No Changes)

GAEB and OCR PDFs use **existing** tables:

**file_extractions:**
- `file_type`: "gaeb" or "pdf"
- `extracted_json`: Same structure as other files
- `status`: "SUCCESS" / "FAILED"
- `error`: Full error if parsing failed

**Metadata in extracted_json (optional):**
```json
{
  "meta": {
    "tender_id": "...",
    "source_type": "gaeb",  // or "pdf_ocr", "pdf_text"
    "gaeb_format": "x84",   // if GAEB
    "ocr_applied": true,    // if OCR used
    "ocr_pages": 12         // if OCR used
  },
  "executive_summary": { ... },
  ...
}
```

---

## Code Changes Summary

| File | Change | Lines |
|------|--------|-------|
| `workers/requirements.txt` | Added lxml, pytesseract, Pillow, pdf2image, gaeb-xml-parser | +6 |
| `workers/utils/filesystem.py` | Added GAEB extensions to mapping | +16 |
| `workers/processing/parsers.py` | Added `parse_gaeb()`, OCR logic in `parse_pdf()` | +114 |
| `workers/config.py` | Added `enable_ocr`, `ocr_max_pages`, `gaeb_enabled`, `redis_*` | +10 |
| `workers/processing/extractor.py` | Pass OCR flags to `parse_file()` | +4 |
| `src/services/zipExtractor.js` | Added GAEB extensions to `SUPPORTED_EXTENSIONS` | +5 |
| `workers/env.example` | Added OCR/GAEB config vars | +6 |
| `ENV_VARS_REQUIRED.md` | Added OCR/GAEB config vars | +6 |
| `workers/tests/test_gaeb_ocr.py` | Test suite for GAEB/OCR | +97 (new) |
| `workers/tests/fixtures/sample_gaeb.x83` | Sample GAEB file | +73 (new) |
| `test_single_file.py` | CLI test harness | +82 (new) |

**Total:** 11 files changed, ~420 lines added

---

## Verification Commands

### 1. Test GAEB File
```powershell
python test_single_file.py workers\tests\fixtures\sample_gaeb.x83
```

### 2. Upload GAEB ZIP
```powershell
Compress-Archive -Path "workers\tests\fixtures\sample_gaeb.x83" -DestinationPath "test_gaeb.zip"

$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "test_gaeb.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

# Monitor
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
```

### 3. Test Scanned PDF (if you have one)
```powershell
python test_single_file.py path\to\scanned.pdf
```

### 4. Check Queue Metrics
```powershell
Invoke-RestMethod http://localhost:3001/api/queue/metrics
```

### 5. End-to-End Test
```powershell
# Upload ZIP with GAEB + normal PDF + scanned PDF
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "comprehensive_test.zip"}
$batchId = $upload.batch_id

Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

# Poll status
while ($true) {
  $status = Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
  Write-Host "Success: $($status.files_success) | Failed: $($status.files_failed) | Pending: $($status.files_pending)"
  if ($status.batch_status -match "completed") { break }
  Start-Sleep -Seconds 10
}

# Check results
Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/files"
```

---

## Expected Logging Output

**GAEB file:**
```
[ZipExtractor]   ✓ tender_lv.x84 (.x84)
[QueueWorker] Processing doc_id=batch_abc..._uuid
Processing file: C:\Users\...\tender_lv.x84 (type: gaeb)
Parsed 8765 characters from GAEB (34 positions)
Split into 3 chunks, calling LLM...
Successfully processed batch_abc..._uuid
```

**Scanned PDF:**
```
[ZipExtractor]   ✓ scanned_plan.pdf (.pdf)
[QueueWorker] Processing doc_id=batch_def..._uuid
Processing file: C:\Users\...\scanned_plan.pdf (type: pdf)
[Parser] PDF appears scanned (18 chars), running OCR...
[Parser] OCR successful: 12456 chars from 15 pages
Parsed 12456 characters from ...
Split into 5 chunks, calling LLM...
Successfully processed batch_def..._uuid
```

**Normal PDF (no OCR):**
```
Processing file: C:\Users\...\document.pdf (type: pdf)
Parsed 9876 characters from ...
Split into 4 chunks, calling LLM...
Successfully processed batch_ghi..._uuid
```

---

## Performance Considerations

**GAEB files:**
- ✅ Fast parsing (XML is lightweight)
- ✅ Typical processing: 1-3 seconds
- ⚠️ Large GAEB files (1000+ positions) may take longer

**OCR PDFs:**
- ⚠️ Slow (20-60 seconds per file)
- ⚠️ Memory intensive (loads images)
- ✅ Page limit prevents runaway jobs
- ✅ Only triggered for scanned PDFs (< 100 chars)

**Recommendations:**
- Set `OCR_MAX_PAGES=20` for faster processing if full document OCR not needed
- Consider splitting large scanned PDFs before upload
- Monitor memory usage during OCR-heavy batches

---

## Next Steps

1. **Install dependencies** (lxml, pytesseract, etc.)
2. **Install Tesseract OCR** (Windows system requirement)
3. **Update .env files** (add ENABLE_OCR, GAEB_ENABLED, etc.)
4. **Restart queue worker**
5. **Test with sample GAEB file**
6. **Test with scanned PDF** (if available)
7. **Monitor logs** for GAEB/OCR detection

---

## Optional: Poppler Installation (for pdf2image on Windows)

pdf2image requires poppler-utils. If you get "Unable to find pdftoppm" error:

**Download Poppler for Windows:**
1. Get from: https://github.com/oschwartz10612/poppler-windows/releases
2. Extract to: `C:\poppler`
3. Add to PATH or set in code:
   ```python
   images = convert_from_path(file_path, dpi=300, poppler_path=r"C:\poppler\bin")
   ```

Or add to `workers/.env`:
```bash
POPPLER_PATH=C:\poppler\bin
```

And update parsers.py to use it.
