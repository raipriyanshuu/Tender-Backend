# Phase 13: Frontend End-to-End Testing Guide

## Overview

This guide verifies the complete tender extraction workflow from the frontend:
**Upload ZIP → Queue Processing → LLM Extraction → Display Merged Data**

All extracted information is **merged from all files** and displayed with **source file references** (blue links).

---

## Prerequisites

### Services Running
- ✅ Backend API: `http://localhost:3001`
- ✅ Redis: Docker container
- ✅ Python Queue Worker: `python -m workers.queue_worker`
- ✅ Frontend: Vite dev server

### Environment Variables

**Frontend `.env`** (`C:\Users\DELL\OneDrive\Desktop\project\.env`):
```bash
VITE_API_URL=http://localhost:3001
```

**Backend `.env`** (already configured):
```bash
REDIS_URL=redis://localhost:6379
REDIS_QUEUE_KEY=tender:jobs
MAX_ZIP_DEPTH=3
```

**Workers `.env`** (already configured):
```bash
REDIS_URL=redis://localhost:6379
ENABLE_OCR=true
OCR_MAX_PAGES=50
GAEB_ENABLED=true
OPENAI_API_KEY=sk-...
```

---

## Start All Services

### Terminal 1: Backend
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
npm start
```

**Expected output:**
```
✅ Database connectivity verified on startup
🚀 Tender Backend API Server
Server running on: http://localhost:3001
```

### Terminal 2: Queue Worker
```powershell
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
python -m workers.queue_worker
```

**Expected output:**
```
[QueueWorker] Connected to Redis: redis://localhost:6379
[QueueWorker] Listening on queue: tender:jobs
```

### Terminal 3: Frontend
```powershell
cd C:\Users\DELL\OneDrive\Desktop\project
npm run dev
```

**Expected output:**
```
VITE ready in X ms
➜ Local: http://localhost:5173
```

Open browser: **`http://localhost:5173`**

---

## Frontend Test Flow (Complete)

### Step 1: Login
1. Enter credentials:
   - Username: `admin`
   - Password: `Tender@2026`
2. Click **Enter**

### Step 2: Navigate to Upload Mode
1. You'll see **"SEARCH"** tab selected by default (Step 1)
2. In the left sidebar, find: **"Or upload documents"**
3. Click **"Upload documents"** button
4. Upload mode opens (replaces search interface)

### Step 3: Upload ZIP File
1. **Drag & drop** a ZIP file into the upload zone OR click **"Select files"**
2. Supported ZIP contents:
   - PDF (normal + scanned/OCR)
   - GAEB (.x83, .x84, .x85, .x86, .d83, .d84, .d85, .d86, .p83-p86, .gaeb)
   - Word (.doc, .docx)
   - Excel (.xls, .xlsx)
   - CSV (.csv)
   - TXT (.txt)
   - Nested ZIPs (depth limit 3)

**Expected UI changes:**
- File appears in upload list
- Upload progress bar shows
- File status changes: `uploading` → `completed`
- Processing banner appears at top: **"File is processing... Data extraction in progress..."** (blue, pulsing)
- Batch status card shows: `Batch batch_XXX` with progress

### Step 4: Processing (Automatic)
Backend automatically:
1. Saves ZIP to `shared/uploads/`
2. Creates `processing_jobs` record
3. Extracts ZIP contents (including nested ZIPs)
4. Enqueues all files to Redis queue: `tender:jobs`
5. Queue worker picks up jobs one by one
6. For each file:
   - Detects file type (pdf/gaeb/word/excel/csv/txt)
   - Parses file (with OCR if scanned PDF)
   - Chunks text
   - Calls OpenAI LLM with **filename for source tracking**
   - LLM extracts structured data
   - Stores in `file_extractions.extracted_json`
7. When all files complete:
   - Batch finalized
   - Aggregator merges all `extracted_json` into `run_summaries.ui_json`

**Expected UI changes:**
- Progress bar updates: `1/3`, `2/3`, `3/3`
- Batch status shows: `processing` → `completed` or `completed_with_errors`

### Step 5: View Extracted Data (Automatic Redirect)
When processing completes (batch_status = `completed`), frontend:
1. Fetches `/api/batches/:batchId/summary` (merged ui_json)
2. Maps `ui_json` → `Tender` object
3. **Automatically redirects to Step 2: COMPACT (Overview)**
4. Sets the tender as `selected`

---

## What You'll See on Step 2 (COMPACT Overview)

The overview page displays **ONLY merged data from all files** with **source file references**.

### Section A: Executive Summary

**Card Title:** "Executive Summary"  
**Badge:** GO or NO-GO (green or red)

**Content:**
```
Brief description:
DEGES Deutsche Einheit Fernstraßenplanungs- und -bau GmbH is seeking construction 
site setup for the A7 Hamburg-Harburg infrastructure project (150 days). Location: 
Hamburg, Germany. Provision and operation of construction site equipment including 
earthmoving equipment, lifting gear, power supply, and scaffolding...

📄 project_overview.pdf
```

### Section B: Go / No-Go Decision

4 criteria with checkmarks (✓ or ✗):

1. **Must-have criteria: 90% (9/10)**
   - ✓ Green checkmark
   - 📄 *tender_documents.pdf*

2. **Region/Logistics: 100% feasibility**
   - ✓ Green checkmark
   - 📄 *project_description.pdf*

3. **Submission deadline: December 15, 2025**
   - ✓ or ⚠ (green if >7 days away)
   - 📄 *announcement.pdf*

4. **Certificates: ISO 9001, DGUV Regulation 52**
   - ✓ Green checkmark
   - 📄 *technical_specifications.pdf*

### Section C: Supply Capability (Operational)

```
• Logistics: 100% feasibility, DE-HH
  📄 project_description.pdf

• Scope of services: Provision and operation of construction site facilities including...
  📄 schedule_of_services.pdf

• SLA: Specific requirements
```

### Section D: Award Logic (Zuschlagslogik)

List of evaluation criteria:
```
• Evaluation matrix: Price 60%, Quality 25%
  📄 award_description.pdf

• Overall score: 91 % (weighted)
  📄 award_description.pdf

• Price vs. Quality: See rating matrix
  📄 award_description.pdf
```

### Section E: Top 5 Mandatory Requirements

**Numbered list (exactly 5 items):**
```
1. Extract from the commercial register
   📄 contract_documents.pdf

2. Business liability insurance: minimum €10 million
   📄 insurance_requirements.docx

3. DGUV certificates
   📄 safety_specifications.pdf

4. References: Infrastructure Projects
   📄 qualification_criteria.x84

5. BGL-compliant calculation
   📄 pricing_model.pdf
```

### Section F: Main Risks (Haupt-Risiken)

**Shows TOP 5 risks with warning icons:**
```
⚠ VOB/C DIN 18299: Site setup must be calculated according to EFB price 221-223.
  📄 contract_terms.pdf

⚠ DGUV Regulation 52/70/52: All construction equipment must be UVV-tested (current test stickers)
  📄 technical_specifications.pdf

⚠ Contractual penalties: In case of late delivery, up to 5% of the daily value per day.
  📄 penalties_annex.docx

⚠ Liability: Business liability insurance of at least €10 million is required for construction equipment/personal injury.
  📄 insurance_requirements.pdf

⚠ BGL 2020 compliance: Equipment cost calculation according to the current construction equipment list
  📄 pricing_guidelines.pdf
```

### Section G: Economic Analysis

**Card showing financial metrics:**
```
┌─────────────────────────┬─────────────────────────┐
│ Potential margin        │ Order value (estimated) │
│ 12-18%                  │ €180k-250k              │
│ At optimal capacity     │ Depending on features   │
└─────────────────────────┴─────────────────────────┘

competitive intensity       High
Logistics costs             Low
Contract risk               Increased

Critical success factors:
• Availability of specific construction equipment categories
• Fast spare parts procurement & service
• Compliance with DGUV maintenance intervals
• Competitive daily rents
```

### Section H: Detailed Assessment (KPI Boxes)

4 large metric boxes showing:
```
┌─────────┬─────────┬─────────┬─────────┐
│ Must-hit│Possible │ In total│Logistics│
│   90%   │   88%   │   91%   │  100%   │
│  9/10   │ 14/16   │Weighted │Distance/│
│         │         │         │Frequency│
└─────────┴─────────┴─────────┴─────────┘
```

### Section I: Timeline & Milestones (if extracted)

```
1  Feasibility check (today)
   Check device availability, certificates, and site logistics.

2  Calculation (Days 2-3)
   Calculate daily rental costs, transport, maintenance, and insurance.

3  Documentation (Days 3-4)
   Compile evidence, references, CE documents

4  Release process (days 5-6)
   Internal review, management, final adjustments

5  Submission (Day 7)
   Upload offer documents, receive confirmation
```

---

## Data Flow Architecture

```
Frontend Upload
     ↓
Backend: POST /upload-tender
     ├─ Saves ZIP to shared/uploads/
     ├─ Creates processing_jobs record
     └─ Returns batch_id
     ↓
Frontend: POST /api/batches/:batchId/process
     ↓
Backend Orchestrator:
     ├─ Extracts ZIP (nested recursion)
     ├─ Creates file_extractions records
     └─ Enqueues jobs to Redis (LPUSH tender:jobs)
     ↓
Python Queue Worker (BRPOP tender:jobs):
     └─ For each file:
         ├─ Detect type (pdf/gaeb/word/excel/csv/txt)
         ├─ Parse file:
         │   ├─ PDF → PyPDF2 → text (or OCR if scanned)
         │   ├─ GAEB → lxml → normalized text
         │   ├─ Word → python-docx → text
         │   └─ Excel/CSV/TXT → respective parser
         ├─ Chunk text (3000 chars, 200 overlap)
         ├─ Call LLM for each chunk:
         │   ├─ Prompt includes filename for source tracking
         │   └─ LLM returns structured JSON with source_document
         ├─ Merge chunks per file
         └─ Store in file_extractions.extracted_json
     ↓
When all files SUCCESS/FAILED:
     ├─ Batch finalized
     └─ Aggregator merges all extracted_json → ui_json
         ├─ Merges arrays (keeps all requirements/risks)
         ├─ Preserves source_document for each item
         └─ Stores in run_summaries.ui_json
     ↓
Frontend polls: GET /api/batches/:batchId/status
     ├─ Checks batch_status
     └─ When 'completed', fetches summary
     ↓
Frontend: GET /api/batches/:batchId/summary
     ├─ Returns run_summaries.ui_json
     └─ Frontend maps to Tender object
     ↓
Display on Step 2 (COMPACT):
     ├─ Executive Summary with source
     ├─ Top 5 Requirements with sources
     ├─ Top 5 Risks with sources
     ├─ Evaluation Criteria with sources
     └─ Economic Analysis
```

---

## Data Mapping (Backend → Frontend Display)

### From `run_summaries.ui_json` to UI

| Backend Field | Frontend Display | Example Value | Source Link |
|---------------|------------------|---------------|-------------|
| `meta.tender_id` | Title (fallback) | "TENDER_2025_001" | meta.source_document |
| `meta.tender_title` | Title | "Baustelleneinrichtung A7" | meta.source_document |
| `meta.organization` | Buyer | "DEGES GmbH" | meta.source_document |
| `executive_summary.title_de` | Title (priority) | "A7 Infrastructure Project" | executive.source_document |
| `executive_summary.organization_de` | Buyer | "DEGES GmbH" | executive.source_document |
| `executive_summary.location_de` | Region | "DE-HH" | executive.source_document |
| `executive_summary.brief_description_de` | Scope | "Bereitstellung Baugeräte..." | executive.source_document |
| `timeline_milestones.submission_deadline_de` | Deadline | "2025-12-15" | timeline.source_document |
| `mandatory_requirements[0-4]` | Top 5 Requirements | Array with source_document | Each item's source |
| `risks[0-4]` | Top 5 Risks | Array with source_document | Each item's source |
| `evaluation_criteria` | Award Logic | Array with source_document | Each item's source |
| `economic_analysis.potentialMargin` | Margin | "12-18%" | analysis.source_document |
| `economic_analysis.orderValueEstimated` | Order Value | "€180k-250k" | analysis.source_document |
| `process_steps` | Timeline | Array with steps | Each step's source |

### Source Tracking Structure

Each extracted field includes source information:
```json
{
  "requirement_de": "Extract from the commercial register",
  "category_de": "Legal",
  "source_document": "contract_documents.pdf"
}
```

Frontend renders as:
```
Extract from the commercial register
📄 contract_documents.pdf
```

---

## Complete Test Scenario

### Test Case 1: Mixed ZIP (PDF + GAEB + Scanned PDF)

**Prepare test ZIP:**
```
mixed_tender.zip (sample structure)
├── project_overview.pdf (normal PDF - 15 pages)
├── bill_of_quantities.x84 (GAEB - 45 positions)
└── floor_plans.pdf (scanned PDF - 10 pages)
```

**Frontend Steps:**
1. Open: `http://localhost:5173`
2. Login: admin / Tender@2026
3. Click: **"Upload documents"**
4. Drag `mixed_tender.zip` into upload zone
5. Wait for upload → processing → completion (60-120 seconds)
6. Auto-redirect to **Step 2: COMPACT**

**Expected UI Display:**

**Executive Summary:**
```
Brief description:
DEGES Deutsche Einheit... seeking construction site setup for A7 Hamburg-Harburg 
infrastructure project (150 days). Location: Hamburg, Germany. Provision and 
operation of construction site equipment including earthmoving equipment, lifting 
gear, power supply, and scaffolding for infrastructure work.

📄 project_overview.pdf
```

**Top 5 Mandatory Requirements:**
```
1. Extract from the commercial register
   📄 contract_documents.pdf (or merged from project_overview.pdf)

2. Business liability insurance: minimum €10 million
   📄 insurance_requirements.pdf (extracted from bill_of_quantities.x84)

3. DGUV certificates
   📄 project_overview.pdf

4. References: Infrastructure Projects
   📄 bill_of_quantities.x84

5. BGL-compliant calculation
   📄 project_overview.pdf
```

**Top 5 Main Risks:**
```
⚠ VOB/C DIN 18299: Site setup must be calculated according to EFB price 221-223.
  📄 project_overview.pdf

⚠ DGUV Regulation 52/70/52: All construction equipment must be UVV-tested
  📄 bill_of_quantities.x84

⚠ Contractual penalties: In case of late delivery, up to 5% of the daily value per day.
  📄 project_overview.pdf

⚠ Liability: Business liability insurance of at least €10 million is required
  📄 bill_of_quantities.x84

⚠ BGL 2020 compliance: Equipment cost calculation according to current list
  📄 project_overview.pdf
```

**Award Logic (Zuschlagslogik):**
```
• Evaluation matrix: Price 60%, Quality 25%
  📄 project_overview.pdf

• Overall score: 91 % (weighted)
  📄 bill_of_quantities.x84

• Price vs. Quality: See rating matrix
  📄 project_overview.pdf
```

**Economic Analysis:**
```
Potential margin:        12-18%
Order value (estimated): €180k-250k
Competitive intensity:   High
Logistics costs:         Low
Contract risk:           Increased
```

**Worker Logs During Processing:**
```
[Orchestrator] Found 3 files to process
[Orchestrator] → Enqueue file: batch_..._uuid (project_overview.pdf)
[Orchestrator] → Enqueue file: batch_..._uuid (bill_of_quantities.x84)
[Orchestrator] → Enqueue file: batch_..._uuid (floor_plans.pdf)
[Orchestrator] Enqueue complete: 3 queued, 0 failed

[QueueWorker] Processing doc_id=batch_xxx_1
Processing file: C:\...\project_overview.pdf (type: pdf)
Parsed 15234 characters from ...
Split into 6 chunks, calling LLM...
Successfully processed batch_xxx_1

[QueueWorker] Processing doc_id=batch_xxx_2
Processing file: C:\...\bill_of_quantities.x84 (type: gaeb)
Parsed 28456 characters from GAEB (45 positions)
Split into 10 chunks, calling LLM...
Successfully processed batch_xxx_2

[QueueWorker] Processing doc_id=batch_xxx_3
Processing file: C:\...\floor_plans.pdf (type: pdf)
[Parser] PDF appears scanned (12 chars), running OCR...
[Parser] OCR successful: 8421 chars from 10 pages
Parsed 8421 characters from ...
Split into 3 chunks, calling LLM...
Successfully processed batch_xxx_3

[QueueWorker] Batch batch_xxx finalized: completed (success=3, failed=0)
[QueueWorker] Aggregating batch_id=batch_xxx
```

---

### Test Case 2: GAEB File Only

**Upload:**
```
gaeb_only.zip
└── tender_lv.x83 (Bill of Quantities)
```

**Expected Display:**
- All source references point to: *tender_lv.x83*
- Requirements extracted from GAEB positions (OZ numbers)
- Brief description from GAEB project title
- Quantities/units/prices if included in GAEB

**Example Requirements:**
```
1. Position 01.01.010: Oberboden abtragen, Dicke 20 cm
   📄 tender_lv.x83

2. Position 01.01.020: Baugrube ausheben, Tiefe bis 3 m
   📄 tender_lv.x83

3. Position 02.01.010: Stahlbeton C25/30 für Fundamente
   📄 tender_lv.x83
```

### Test Case 3: Scanned PDF (OCR Test)

**Upload:**
```
scanned_tender.zip
└── scanned_document.pdf (image-based PDF, no selectable text)
```

**Worker Logs:**
```
Processing file: ...scanned_document.pdf (type: pdf)
[Parser] PDF appears scanned (34 chars), running OCR...
[Parser] OCR successful: 15234 chars from 12 pages
Parsed 15234 characters from ...
Successfully processed
```

**Expected Display:**
- Data extracted from OCR text
- All sources point to: *scanned_document.pdf*
- No indication in UI that OCR was used (seamless)

### Test Case 4: Nested ZIP

**Upload:**
```
nested_tender.zip
├── main_specs.pdf
└── additional_docs.zip
    ├── annex_a.docx
    └── annex_b.x84
```

**Expected:**
- All 3 files processed (main_specs.pdf, annex_a.docx, annex_b.x84)
- Sources show all 3 filenames
- Requirements/risks merged from all 3

**Example:**
```
Top 5 Mandatory Requirements:

1. Extract from commercial register
   📄 main_specs.pdf

2. Quality certification ISO 9001
   📄 annex_a.docx

3. GAEB position 01.01.010 compliance
   📄 annex_b.x84

4. Insurance minimum €10M
   📄 main_specs.pdf

5. Reference projects documentation
   📄 annex_a.docx
```

---

## Validation Checklist

### Upload & Processing
- [ ] Frontend loads at `http://localhost:5173`
- [ ] Login successful
- [ ] "Upload documents" button visible and clickable
- [ ] ZIP upload accepts file
- [ ] File appears in upload list
- [ ] Upload completes (green checkmark)
- [ ] Processing banner appears (blue, pulsing)
- [ ] Batch status card shows progress
- [ ] Backend logs show: `Upload successful, batch_id: batch_XXX`
- [ ] Orchestrator logs show: `Enqueue complete: X queued`
- [ ] Worker logs show: `Processing doc_id=...` for each file
- [ ] Worker logs show: `Successfully processed` for each file
- [ ] Worker logs show: `Batch finalized: completed`
- [ ] Worker logs show: `Aggregating batch_id=...`

### Data Display (Step 2: COMPACT)
- [ ] Automatic redirect to Step 2 after processing
- [ ] Executive Summary card visible
- [ ] Title shows extracted tender name
- [ ] Buyer/Organization shows extracted value
- [ ] Region shows location
- [ ] Brief description visible (350 char preview)
- [ ] **Source file reference appears** (📄 filename.pdf)

### Top 5 Requirements
- [ ] Section titled: "E. Top-5 Pflichtanforderungen"
- [ ] Shows **exactly 5 items** (numbered 1-5)
- [ ] Each requirement has text description
- [ ] **Each requirement has blue source file link** (📄 filename)
- [ ] Filenames match uploaded files
- [ ] If < 5 requirements extracted, shows fewer (not padded)

### Top 5 Risks
- [ ] Section titled: "Haupt-Risiken"
- [ ] Shows **up to 5 risks**
- [ ] Each risk has ⚠ warning icon
- [ ] Each risk has description
- [ ] **Each risk has blue source file link** (📄 filename)
- [ ] Filenames are correct

### Award Logic (Zuschlagslogik)
- [ ] Evaluation criteria listed
- [ ] Each criterion has source file link
- [ ] Percentages/weights shown if extracted

### Economic Analysis
- [ ] Card visible (if economic_analysis in ui_json)
- [ ] Potential margin shown
- [ ] Order value shown
- [ ] Competitive intensity shown
- [ ] Logistics costs shown
- [ ] Contract risk shown
- [ ] Critical success factors listed (if available)

### Detailed Assessment
- [ ] 4 KPI boxes visible
- [ ] Must-hit percentage calculated
- [ ] Possible hit percentage calculated
- [ ] In total (weighted) percentage shown
- [ ] Logistics score shown

### Source Tracking Verification
- [ ] Blue document icons (📄) appear next to extracted data
- [ ] Filenames in source links match uploaded files
- [ ] No "undefined" or "null" as source
- [ ] No "document" as generic source (should be actual filename)

---

## API Endpoints Verification

### 1. Upload
```powershell
POST http://localhost:3001/upload-tender
Content-Type: multipart/form-data
Body: file=test.zip

Response:
{
  "success": true,
  "batch_id": "batch_12345678-1234-1234-1234-123456789abc"
}
```

### 2. Trigger Processing
```powershell
POST http://localhost:3001/api/batches/:batchId/process
Content-Type: application/json
Body: {}

Response:
{
  "success": true,
  "message": "Processing started for batch batch_XXX",
  "batch_id": "batch_XXX"
}
```

### 3. Poll Status
```powershell
GET http://localhost:3001/api/batches/:batchId/status

Response:
{
  "batch_id": "batch_XXX",
  "batch_status": "completed",
  "total_files": 3,
  "files_success": 3,
  "files_failed": 0,
  "progress_percent": "100.00"
}
```

### 4. Get Summary (Merged Data)
```powershell
GET http://localhost:3001/api/batches/:batchId/summary

Response:
{
  "run_id": "batch_XXX",
  "ui_json": {
    "meta": {
      "tender_id": "...",
      "organization": "...",
      "source_document": "project_overview.pdf"
    },
    "executive_summary": {
      "title_de": "...",
      "brief_description_de": "...",
      "location_de": "DE-HH",
      "source_document": "project_overview.pdf"
    },
    "mandatory_requirements": [
      {
        "requirement_de": "Extract from commercial register",
        "category_de": "Legal",
        "source_document": "contract_documents.pdf"
      },
      ...
    ],
    "risks": [
      {
        "risk_de": "VOB/C DIN 18299: Site setup must...",
        "severity": "high",
        "source_document": "contract_terms.pdf"
      },
      ...
    ],
    "evaluation_criteria": [...],
    "economic_analysis": {...},
    "process_steps": [...]
  },
  "total_files": 3,
  "success_files": 3,
  "failed_files": 0,
  "status": "completed"
}
```

---

## Troubleshooting

### Issue: No source file links appear

**Symptoms:**
- Data displayed but no blue 📄 links
- Source shows as "—" or empty

**Cause:**
- LLM didn't include `source_document` in response
- Old prompt cached (worker not restarted)

**Fix:**
```powershell
# 1. Stop queue worker (Ctrl+C in Terminal 2)
# 2. Restart queue worker
cd C:\Users\DELL\OneDrive\Desktop\tenderBackend
python -m workers.queue_worker

# 3. Reprocess failed batch
Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/batch_XXX/retry-failed" -ContentType "application/json" -Body '{}'
```

### Issue: Shows wrong filename as source

**Symptoms:**
- Source shows "document" instead of actual filename
- All sources point to same file

**Cause:**
- Filename not passed to LLM correctly

**Debug:**
```powershell
# Check file_extractions.extracted_json
Invoke-RestMethod http://localhost:3001/api/batches/batch_XXX/files

# Each file's extracted_json should have:
# - source_document = actual filename
```

**Fix:**
- Check `extractor.py` passes correct `file_extraction.filename`
- Restart worker and reprocess

### Issue: More than 5 requirements/risks shown

**Symptoms:**
- UI shows 10+ requirements
- Not limited to top 5

**Cause:**
- Frontend mapping didn't slice arrays

**Fix:**
- Already fixed in `mapSummaryToTender` (`.slice(0, 5)`)
- Refresh browser

### Issue: No data extracted (empty ui_json)

**Symptoms:**
- Processing completes
- But ui_json is {} or minimal

**Cause:**
- LLM extraction failed
- OpenAI API key invalid
- Files not parseable

**Debug:**
```powershell
# Check individual file extractions
Invoke-RestMethod http://localhost:3001/api/batches/batch_XXX/files

# Check if extracted_json has data for each file
```

**Fix:**
1. Verify `OPENAI_API_KEY` is valid
2. Check worker logs for LLM errors
3. Test single file: `python test_single_file.py path\to\file.pdf`

### Issue: GAEB not detected

**Symptoms:**
- GAEB file uploaded
- Not in file list or shows as unsupported

**Debug:**
```powershell
# Check backend logs during extraction
# Should see: "[ZipExtractor]   ✓ tender.x84 (.x84)"
```

**Fix:**
- Verify `SUPPORTED_EXTENSIONS` includes GAEB extensions
- Check file actually has .x83/.x84/etc. extension
- Restart backend if needed

### Issue: OCR not working

**Symptoms:**
- Scanned PDF processed
- No text extracted

**Debug:**
```powershell
# Check if Tesseract installed
tesseract --version

# Check worker logs
# Expected: "[Parser] PDF appears scanned (XX chars), running OCR..."
```

**Fix:**
1. Install Tesseract: `choco install tesseract`
2. Install German language: Download `deu.traineddata`
3. Set `ENABLE_OCR=true` in workers/.env
4. Restart queue worker

### Issue: Processing stuck

**Symptoms:**
- Files stay in "pending" status
- No progress after 5+ minutes

**Debug:**
```powershell
# Check queue worker running
# Terminal 2 should show logs

# Check queue metrics
Invoke-RestMethod http://localhost:3001/api/queue/metrics
# Check if jobs stuck in processing_count
```

**Fix:**
1. Check Redis: `docker ps` (should show redis-local)
2. Restart queue worker
3. Check worker logs for errors

---

## Performance Expectations

| Scenario | Files | Processing Time |
|----------|-------|-----------------|
| Simple PDF (10 pages) | 1 | 10-20 seconds |
| GAEB file (100 positions) | 1 | 15-30 seconds |
| Scanned PDF (10 pages) | 1 | 40-90 seconds |
| Mixed ZIP (3 files) | 3 | 45-120 seconds |
| Large ZIP (20 files) | 20 | 3-8 minutes |
| Nested ZIP (10 files deep) | 10 | 2-5 minutes |

---

## Success Criteria

✅ **Upload works** from frontend UI  
✅ **Processing completes** for all file types  
✅ **Merged data displayed** on Step 2 (not per-file)  
✅ **Top 5 requirements** shown with blue source file links  
✅ **Top 5 risks** shown with blue source file links  
✅ **Award logic** shown with source tracking  
✅ **Economic analysis** displayed  
✅ **Source filenames** are correct (match uploaded files)  
✅ **GAEB files** extracted and merged  
✅ **OCR PDFs** processed and merged  
✅ **Nested ZIPs** extracted recursively  

---

## Quick Verification Commands

### Check all services running
```powershell
# Backend
Invoke-RestMethod http://localhost:3001/ping

# Redis
docker ps | findstr redis

# Frontend
# Open http://localhost:5173 in browser
```

### Upload test file via API
```powershell
# Create test ZIP
Compress-Archive -Path "workers\tests\fixtures\sample_gaeb.x83" -DestinationPath "test.zip"

# Upload
$upload = Invoke-RestMethod -Method POST -Uri http://localhost:3001/upload-tender -Form @{file=Get-Item "test.zip"}
$batchId = $upload.batch_id

# Process
Invoke-RestMethod -Method POST -Uri "http://localhost:3001/api/batches/$batchId/process" -ContentType "application/json" -Body '{}'

# Monitor
while ($true) {
  $status = Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/status"
  Write-Host "Status: $($status.batch_status) | Success: $($status.files_success)/$($status.total_files)"
  if ($status.batch_status -match "completed") { break }
  Start-Sleep -Seconds 5
}

# Get summary
$summary = Invoke-RestMethod "http://localhost:3001/api/batches/$batchId/summary"
$summary.ui_json | ConvertTo-Json -Depth 10
```

### Check queue activity
```powershell
Invoke-RestMethod http://localhost:3001/api/queue/metrics
```

**Expected:**
```json
{
  "success": true,
  "metrics": {
    "queue_length": 0,
    "processing_count": 0,
    "delayed_count": 0,
    "dead_count": 0
  }
}
```

---

## What Changed in Phase 13

### Frontend Changes (ONLY)
1. **FileUploadZone.tsx**: Now fetches batch files after completion (for internal use, not displayed)
2. **ReikanTenderAI.tsx**: 
   - Enhanced `mapSummaryToTender` to extract ALL fields from ui_json
   - Added source tracking for requirements, risks, evaluation criteria
   - Limited to TOP 5 requirements and risks
   - Removed per-file extraction display
   - Maps source_document fields to SourceBadge/DocumentSourceInline components

### Worker Changes (MINIMAL)
3. **llm_client.py**: 
   - Updated LLM prompt to include filename
   - Prompt now requests source_document for every field
   - Added comprehensive schema for all tender fields
4. **extractor.py**: 
   - Passes filename to `extract_tender_data()`
   - Ensures source tracking propagates

### No Changes
- ❌ No database schema changes
- ❌ No backend API changes
- ❌ No queue system changes
- ❌ No aggregator logic changes

---

## LLM Extraction Schema (What the AI Returns)

The LLM now extracts this structure **per file**:

```json
{
  "meta": {
    "tender_id": "TENDER_2025_001",
    "tender_title": "Baustelleneinrichtung A7",
    "organization": "DEGES GmbH",
    "source_document": "project_overview.pdf"
  },
  "executive_summary": {
    "title_de": "A7 Hamburg-Harburg Infrastructure",
    "organization_de": "DEGES GmbH",
    "brief_description_de": "Construction site setup for 150 days...",
    "location_de": "DE-HH",
    "source_document": "project_overview.pdf"
  },
  "timeline_milestones": {
    "submission_deadline_de": "2025-12-15",
    "project_duration_de": "150 days",
    "source_document": "project_overview.pdf"
  },
  "mandatory_requirements": [
    {
      "requirement_de": "Extract from commercial register",
      "category_de": "Legal",
      "source_document": "project_overview.pdf"
    },
    {
      "requirement_de": "Business liability insurance: minimum €10 million",
      "category_de": "Insurance",
      "source_document": "project_overview.pdf"
    }
  ],
  "risks": [
    {
      "risk_de": "VOB/C DIN 18299: Site setup must be calculated...",
      "severity": "high",
      "source_document": "project_overview.pdf"
    }
  ],
  "evaluation_criteria": [
    {
      "criterion_de": "Price 60%, Quality 25%",
      "weight_percent": 60,
      "source_document": "project_overview.pdf"
    }
  ],
  "economic_analysis": {
    "potentialMargin": {
      "text": "12-18%",
      "source_document": "project_overview.pdf"
    },
    "orderValueEstimated": {
      "text": "€180k-250k",
      "source_document": "project_overview.pdf"
    },
    "competitiveIntensity": {
      "text": "High",
      "source_document": "project_overview.pdf"
    },
    "logisticsCosts": {
      "text": "Low",
      "source_document": "project_overview.pdf"
    },
    "contractRisk": {
      "text": "Increased",
      "source_document": "project_overview.pdf"
    },
    "criticalSuccessFactors": [
      {
        "text": "Availability of specific equipment",
        "source_document": "project_overview.pdf"
      }
    ]
  },
  "service_types": ["Site setup", "Earthwork", "Scaffolding"],
  "certifications_required": ["ISO 9001", "DGUV Regulation 52"],
  "safety_requirements": ["UVV testing", "CE marking"],
  "contract_penalties": ["Late delivery: 5% per day"],
  "submission_requirements": ["Commercial register", "Insurance"],
  "process_steps": [
    {
      "step": 1,
      "days_de": "today",
      "title_de": "Feasibility check",
      "description_de": "Check device availability...",
      "source_document": "project_overview.pdf"
    }
  ],
  "missing_evidence_documents": [
    {
      "document_de": "Current UVV test certificates",
      "source_document": "project_overview.pdf"
    }
  ]
}
```

**Aggregator merges** all per-file JSONs into one ui_json (preserving source_document).

---

## Final Notes

### What Frontend Shows
- **MERGED data** from all files in the ZIP
- **Top 5** most important requirements
- **Top 5** major risks
- **Source file references** for every piece of data
- **NO per-file breakdown** (only merged view)

### What Frontend Does NOT Show
- ❌ Individual file extraction details
- ❌ All 20+ requirements (only top 5)
- ❌ All 15+ risks (only top 5)
- ❌ Raw ui_json (removed from display)
- ❌ Per-file status cards

### Blue Links (📄 filename.pdf)
- Appear after every extracted data point
- Show which file the information came from
- Enable traceability and verification
- Match the uploaded filenames exactly

---

## Ready to Test

1. Start all 3 services (backend, worker, frontend)
2. Open `http://localhost:5173`
3. Login
4. Upload a ZIP
5. Wait for processing
6. Verify extracted data on Step 2
7. Check source file links appear
8. Confirm top 5 requirements & risks shown

**Phase 13 is complete when:**
- Upload → process → display works end-to-end
- All file types supported (PDF/GAEB/OCR/Office/CSV/TXT)
- Source tracking visible for all extracted data
- UI shows merged data (not per-file)
- Top 5 requirements and risks displayed with sources
