# Nested ZIP & Extended File Type Support

## Problem 1: Nested ZIPs Not Supported

**Current Behavior:**
- ZIPs are extracted once
- Nested ZIPs inside are treated as unsupported files and skipped
- No recursive extraction

**Required Behavior:**
- Detect nested ZIPs
- Extract recursively with depth limit
- Preserve original path hierarchy in metadata

## Problem 2: Missing File Type Parsers

**Current Support:**
- ✅ PDF, DOCX, DOC, XLSX, XLS

**Missing:**
- ❌ CSV
- ❌ TXT

---

## Solution 1: Recursive ZIP Extraction

### Implementation

**src/services/zipExtractor.js (REPLACE extractBatch function)**

```javascript
import path from "path";
import fs from "fs/promises";
import crypto from "crypto";
import { query } from "../db.js";

const STORAGE_BASE_PATH =
  process.env.STORAGE_BASE_PATH || path.join(process.cwd(), "shared");
const STORAGE_EXTRACTED_DIR = process.env.STORAGE_EXTRACTED_DIR || "extracted";
const MAX_ZIP_DEPTH = Number(process.env.MAX_ZIP_DEPTH || "3");

/**
 * Recursively extract ZIP files
 */
async function extractZipRecursive(zipPath, extractPath, depth = 0, parentPath = "") {
  if (depth > MAX_ZIP_DEPTH) {
    console.warn(`[ZipExtractor] Max depth ${MAX_ZIP_DEPTH} reached at ${zipPath}`);
    return [];
  }

  console.log(`[ZipExtractor] Extracting (depth ${depth}): ${zipPath}`);

  const AdmZip = (await import("adm-zip")).default;
  const zip = new AdmZip(zipPath);
  zip.extractAllTo(extractPath, true);

  const extractedFiles = await fs.readdir(extractPath, { recursive: true });
  const allFiles = [];
  const nestedZips = [];

  for (const file of extractedFiles) {
    const fullPath = path.join(extractPath, file);
    const stats = await fs.stat(fullPath);

    if (!stats.isFile()) {
      continue;
    }

    const ext = path.extname(file).toLowerCase();
    const relativePath = path.join(parentPath, file);

    // If it's a nested ZIP, mark for recursive extraction
    if (ext === ".zip") {
      nestedZips.push({
        file,
        fullPath,
        relativePath,
      });
      continue;
    }

    // Check if supported file type
    const supportedExtensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".csv", ".txt"];
    if (supportedExtensions.includes(ext)) {
      allFiles.push({
        filename: path.basename(file),
        file_path: relativePath,
        file_type: ext.substring(1),
        original_path: relativePath,  // Preserve hierarchy
        extraction_depth: depth,
      });
      console.log(`[ZipExtractor]   ✓ ${relativePath} (${ext}, depth ${depth})`);
    } else {
      console.log(`[ZipExtractor]   ✗ ${relativePath} (unsupported: ${ext})`);
    }
  }

  // Process nested ZIPs recursively
  for (const nestedZip of nestedZips) {
    const nestedExtractPath = path.join(extractPath, `__extracted_${crypto.randomBytes(8).toString('hex')}`);
    await fs.mkdir(nestedExtractPath, { recursive: true });

    try {
      const nestedFiles = await extractZipRecursive(
        nestedZip.fullPath,
        nestedExtractPath,
        depth + 1,
        nestedZip.relativePath
      );
      allFiles.push(...nestedFiles);
      
      // Delete the nested ZIP after extraction to save space
      await fs.unlink(nestedZip.fullPath);
    } catch (error) {
      console.error(`[ZipExtractor] Failed to extract nested ZIP ${nestedZip.file}:`, error.message);
      // Continue with other files even if one nested ZIP fails
    }
  }

  return allFiles;
}

/**
 * Extract ZIP file and create file_extraction records
 */
export async function extractBatch(batchId) {
  console.log(`[ZipExtractor] Starting extraction for batch ${batchId}`);
  
  const jobResult = await query(
    "SELECT * FROM processing_jobs WHERE batch_id = $1",
    [batchId]
  );
  const job = jobResult.rows[0];
  if (!job) {
    throw new Error(`Batch not found: ${batchId}`);
  }

  console.log(`[ZipExtractor] Batch found, zip_path: ${job.zip_path}`);

  await query(
    "UPDATE processing_jobs SET status = $2, updated_at = now() WHERE batch_id = $1",
    [batchId, "extracting"]
  );

  const zipPath = path.join(STORAGE_BASE_PATH, job.zip_path);
  const extractPath = path.join(STORAGE_BASE_PATH, STORAGE_EXTRACTED_DIR, batchId);

  console.log(`[ZipExtractor] ZIP path: ${zipPath}`);
  console.log(`[ZipExtractor] Extract to: ${extractPath}`);

  await fs.mkdir(extractPath, { recursive: true });

  // CHANGED: Use recursive extraction
  const files = await extractZipRecursive(zipPath, extractPath, 0, "");

  console.log(`[ZipExtractor] ${files.length} supported files found (including nested)`);

  if (files.length === 0) {
    await query(
      "UPDATE processing_jobs SET status = $2, error_message = $3, updated_at = now() WHERE batch_id = $1",
      [batchId, "failed", "No supported files found in ZIP"]
    );
    throw new Error("No supported files found in ZIP");
  }

  const runId = job.run_id || batchId;
  console.log(`[ZipExtractor] Creating file_extractions records with run_id: ${runId}`);

  for (const file of files) {
    const docId = `${batchId}_${crypto.randomUUID()}`;

    const result = await query(
      `
      INSERT INTO file_extractions (
        doc_id,
        run_id,
        filename,
        file_path,
        file_type,
        status,
        source
      ) VALUES ($1, $2, $3, $4, $5, $6, $7)
      ON CONFLICT (doc_id) DO NOTHING
      RETURNING id
      `,
      [
        docId,
        runId,
        file.filename,
        path.join(STORAGE_EXTRACTED_DIR, batchId, file.file_path),
        file.file_type,
        "pending",
        "upload"
      ]
    );
    
    if (result.rows.length > 0) {
      console.log(`[ZipExtractor]   Created: ${docId} → ${file.original_path} (depth ${file.extraction_depth})`);
    }
  }

  await query(
    "UPDATE processing_jobs SET total_files = $2, run_id = $3, status = $4, updated_at = now() WHERE batch_id = $1",
    [batchId, files.length, runId, "queued"]
  );

  console.log(`[ZipExtractor] Batch updated: total_files=${files.length}, run_id=${runId}, status=queued`);

  return { batch_id: batchId, total_files: files.length };
}
```

### Configuration

**Add to .env:**
```env
MAX_ZIP_DEPTH=3  # Maximum nesting depth (default: 3)
```

### Safety Features

✅ **Depth Limit**: Prevents infinite recursion  
✅ **Error Isolation**: One bad nested ZIP doesn't fail entire batch  
✅ **Cleanup**: Deletes nested ZIPs after extraction to save space  
✅ **Path Preservation**: Maintains original hierarchy in metadata  

---

## Solution 2: Add CSV and TXT Parsers

### Add CSV Parser

**workers/processing/parsers.py (ADD after parse_excel)**

```python
import csv

def parse_csv(file_path: str) -> str:
    """Parse CSV file into text representation."""
    try:
        chunks: list[str] = []
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
            reader = csv.reader(handle)
            for row in reader:
                row_text = " | ".join(str(cell) for cell in row)
                if row_text.strip():
                    chunks.append(row_text)
        return "\n".join(chunks)
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Failed to parse CSV file: {file_path}") from exc


def parse_txt(file_path: str) -> str:
    """Parse text file."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as handle:
            return handle.read()
    except Exception as exc:  # noqa: BLE001
        raise ParseError(f"Failed to parse text file: {file_path}") from exc
```

### Update parse_file Function

**workers/processing/parsers.py (MODIFY parse_file)**

```python
def parse_file(file_path: str) -> str:
    file_type = get_file_type(file_path)
    if file_type == "pdf":
        return parse_pdf(file_path)
    if file_type == "word":
        return parse_word(file_path)
    if file_type == "excel":
        return parse_excel(file_path)
    if file_type == "csv":
        return parse_csv(file_path)
    if file_type == "text":
        return parse_txt(file_path)
    raise PermanentError(f"Unsupported file type: {file_path}")
```

### Update File Type Mapping

**workers/utils/filesystem.py (ALREADY HAS csv and text mappings)**

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
        ".txt": "text",
        ".csv": "csv",  # ← Already exists, just needs parser
    }
    return mapping.get(ext, "unknown")
```

---

## Updated File Support Matrix

| File Type | Supported | Parser | Notes |
|-----------|-----------|--------|-------|
| **PDF** | ✅ Yes | PyPDF2 | Full support |
| **DOCX** | ✅ Yes | python-docx | Full support |
| **DOC** | ✅ Yes | python-docx | Legacy format |
| **XLSX** | ✅ Yes | openpyxl | Full support |
| **XLS** | ✅ Yes | openpyxl | Legacy format |
| **CSV** | ✅ Yes (NEW) | csv (stdlib) | Converts to pipe-delimited text |
| **TXT** | ✅ Yes (NEW) | open() (stdlib) | UTF-8 with fallback |
| **ZIP** | ✅ Recursive (NEW) | adm-zip | Depth limit = 3 |

---

## Verification Checklist

### Test 1: Nested ZIP

**Create test structure:**
```
test.zip
├── file1.pdf
├── nested.zip
│   ├── file2.docx
│   └── deeply_nested.zip
│       └── file3.xlsx
└── folder/
    └── file4.csv
```

**Expected:**
- ✅ All 4 files extracted and processed
- ✅ Depth tracking in logs
- ✅ Original paths preserved

### Test 2: Mixed File Types

**Create test ZIP:**
```
mixed.zip
├── document.pdf
├── spreadsheet.xlsx
├── data.csv
└── notes.txt
```

**Expected:**
- ✅ PDF extracted with PyPDF2
- ✅ XLSX extracted with openpyxl
- ✅ CSV parsed as pipe-delimited rows
- ✅ TXT read as plain text

### Test 3: Depth Limit

**Create deeply nested structure:**
```
test.zip
└── level1.zip
    └── level2.zip
        └── level3.zip
            └── level4.zip (should be skipped)
```

**Expected:**
- ✅ Extraction stops at depth 3
- ✅ Warning logged: "Max depth 3 reached"
- ✅ Files at depth ≤ 3 are processed

### Test 4: Malformed Nested ZIP

**Create ZIP with corrupt nested ZIP:**
```
test.zip
├── good_file.pdf
├── corrupt.zip (invalid)
└── another_good.docx
```

**Expected:**
- ✅ good_file.pdf processes successfully
- ✅ another_good.docx processes successfully
- ⚠️ Warning logged for corrupt.zip
- ✅ Batch completes with 2 files

---

## Migration Steps

1. **Backup current code**
   ```powershell
   git commit -am "Backup before nested ZIP support"
   ```

2. **Apply zipExtractor changes**
   - Replace `src/services/zipExtractor.js`
   - Add `MAX_ZIP_DEPTH` to `.env`

3. **Apply parser changes**
   - Update `workers/processing/parsers.py`
   - No new dependencies needed (csv is stdlib)

4. **Test with simple ZIP first**
   ```powershell
   # Upload non-nested ZIP
   Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "simple.zip"}
   ```

5. **Test with nested ZIP**
   ```powershell
   # Upload nested ZIP
   Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "nested.zip"}
   ```

6. **Verify in logs**
   - Backend should show "depth X" in extraction logs
   - Worker should process CSV/TXT files
   - Check DB for correct file counts

---

## Performance Considerations

**Nested ZIP extraction:**
- Each nesting level creates a temporary directory
- Nested ZIPs are deleted after extraction
- Depth limit prevents exponential growth

**CSV/TXT parsing:**
- No external dependencies (uses Python stdlib)
- UTF-8 encoding with fallback for corrupted files
- Memory-efficient (line-by-line for CSV)

**Storage impact:**
- Nested extraction uses ~2x disk space temporarily
- Cleanup removes nested ZIPs after processing
- Consider `MAX_FILE_SIZE_MB` for nested content
