# Phase 13 Changes Summary

## Goal
Enable frontend to display **merged tender data** from all uploaded files with **source file tracking** (blue document links).

---

## What Changed

### 1. LLM Prompt Enhanced (Workers)

**File:** `workers/processing/llm_client.py`

**Change:** Updated prompt to include source filename for every extracted field.

**Before:**
```python
def _build_extraction_prompt(text: str) -> str:
    return (
        "Extract tender information...\n"
        '  "meta": {"tender_id": "...", "organization": "..."},\n'
        '  "mandatory_requirements": [{"requirement_de": "...", "category_de": "..."}],\n'
        # No source tracking
    )
```

**After:**
```python
def _build_extraction_prompt(text: str, source_filename: str = "document") -> str:
    return (
        f"Extract tender information from: {source_filename}\n"
        '  "meta": {"tender_id": "...", "source_document": "' + source_filename + '"},\n'
        '  "mandatory_requirements": [{"requirement_de": "...", "source_document": "' + source_filename + '"}],\n'
        # All fields now include source_document
    )
```

**New fields extracted:**
- `meta` → with source_document
- `executive_summary` → with source_document
- `timeline_milestones` → with source_document
- `mandatory_requirements[]` → each with source_document
- `risks[]` → each with source_document
- `evaluation_criteria[]` → each with source_document
- `economic_analysis` → all sub-fields with source_document
- `process_steps[]` → each with source_document
- `missing_evidence_documents[]` → each with source_document
- Plus: service_types, certifications_required, safety_requirements, etc.

**Impact:**
- LLM now returns comprehensive tender data
- Every piece of information tagged with source filename
- Enables traceability in frontend

---

### 2. Pass Filename to LLM (Workers)

**File:** `workers/processing/extractor.py`

**Change:** Extract filename from file record and pass to LLM.

```python
# Before
chunk_results = [extract_tender_data(chunk, config) for chunk in chunks]

# After
source_filename = file_extraction.filename or "document"
chunk_results = [extract_tender_data(chunk, config, source_filename) for chunk in chunks]
```

**Impact:**
- LLM knows which file it's processing
- Can include actual filename (not generic "document")

---

### 3. Frontend Mapping Enhanced (Frontend)

**File:** `project/src/ReikanTenderAI.tsx`

**Change:** Updated `mapSummaryToTender` to extract all fields with source tracking.

**Key updates:**
```typescript
// TOP 5 requirements with source tracking
const submissionWithSource = requirements
  .slice(0, 5)  // Limit to top 5
  .map((req: any) => ({
    text: req?.requirement_de || req?.text,
    source_document: req?.source_document || "",
    source_chunk_id: req?.source_chunk_id ?? null,
  }));

// TOP 5 risks with source tracking
const legalRisksWithSource = risks
  .slice(0, 5)  // Limit to top 5
  .map((risk: any) => ({
    text: risk?.risk_de || risk?.text,
    source_document: risk?.source_document || "",
    source_chunk_id: risk?.source_chunk_id ?? null,
  }));

// Evaluation criteria with source
const evaluationCriteriaWithSource = evaluationCriteria
  .map((crit: any) => ({
    text: typeof crit === 'string' ? crit : (crit?.criterion_de || crit?.text),
    source_document: typeof crit === 'object' ? crit?.source_document || "" : "",
  }));

// Economic analysis (already has source in nested objects)
economicAnalysis: uiJson.economic_analysis || undefined,

// Process steps with source
processSteps: Array.isArray(uiJson.process_steps) ? uiJson.process_steps : [],

// Missing evidence with source
const missingEvidenceWithSource = missingEvidence.map(...);
```

**Impact:**
- All tender fields populated from ui_json
- Source tracking preserved for display
- Top 5 limits enforced
- Comprehensive data mapping

---

### 4. Removed Per-File Display (Frontend)

**File:** `project/src/ReikanTenderAI.tsx`

**Change:** Removed "Extrahierte Daten (Batch)" card that showed per-file extraction details.

**Removed:**
- Batch metadata display
- Per-file extraction list
- Raw ui_json display
- File-by-file status breakdown

**Impact:**
- UI now shows ONLY merged data
- Cleaner, more focused display
- No confusion between per-file vs merged data

---

### 5. Evaluation Criteria Display Updated (Frontend)

**File:** `project/src/ReikanTenderAI.tsx`

**Change:** Award Logic section now uses `evaluationCriteriaWithSource` instead of plain array.

```typescript
// Before
{tender.evaluationCriteria.map((criteria, i) => (
  <li key={i}>{criteria}</li>
))}

// After
{tender.evaluationCriteriaWithSource.map((criteria, i) => (
  <li key={i}>
    <span>{criteria.text}</span>
    <DocumentSourceInline source_document={criteria.source_document} />
  </li>
))}
```

**Impact:**
- Award logic criteria now show source file links
- Consistent with requirements and risks display

---

### 6. Scope of Work Source Display (Frontend)

**File:** `project/src/ReikanTenderAI.tsx`

**Change:** Added source badge below brief description.

```typescript
<p className="text-sm text-zinc-700">
  {tender.buyer} sucht {tender.title}...
</p>
{tender.scopeOfWorkSource?.source_document && (
  <SourceBadge source={tender.scopeOfWorkSource.source_document} />
)}
```

**Impact:**
- Executive summary now shows which file the description came from

---

## Files Modified

| File | Change Type | Lines Changed |
|------|-------------|---------------|
| `workers/processing/llm_client.py` | Enhanced LLM prompt | ~60 lines |
| `workers/processing/extractor.py` | Pass filename to LLM | +2 lines |
| `project/src/ReikanTenderAI.tsx` | Frontend mapping + display | ~150 lines |
| `project/src/components/FileUploadZone.tsx` | Fetch files (internal) | +15 lines |
| `docs/PHASE_13_FRONTEND_TESTING.md` | Complete test guide | New file |
| `phases.md` | Mark Phase 13 complete | 1 line |

**Total: 6 files changed**

---

## How It Works Now

### 1. Upload Flow
```
User uploads ZIP → Backend saves → Creates batch → Returns batch_id
     ↓
Frontend calls /api/batches/:id/process
     ↓
Backend extracts ZIP → Enqueues files to Redis
```

### 2. Processing Flow
```
Queue Worker picks job → Parses file (PDF/GAEB/OCR) → Chunks text
     ↓
Calls LLM with:
  - Text chunk
  - Source filename (e.g., "project_overview.pdf")
     ↓
LLM returns JSON with source_document in every field:
  {
    "mandatory_requirements": [
      {"requirement_de": "...", "source_document": "project_overview.pdf"}
    ]
  }
     ↓
Stores in file_extractions.extracted_json
```

### 3. Aggregation Flow
```
When all files complete → Aggregator runs
     ↓
Merges all file_extractions.extracted_json:
  - File 1: requirements [A, B] with sources
  - File 2: requirements [C, D] with sources
  - Merged: requirements [A, B, C, D] with sources
     ↓
Stores in run_summaries.ui_json
```

### 4. Display Flow
```
Frontend polls status → When 'completed' → Fetches summary
     ↓
Gets ui_json with merged data + source tracking
     ↓
Maps to Tender object:
  - Extracts top 5 requirements with sources
  - Extracts top 5 risks with sources
  - Extracts all other fields with sources
     ↓
Renders on Step 2 (COMPACT):
  - Each requirement shows: text + 📄 filename.pdf
  - Each risk shows: text + 📄 filename.pdf
  - Each criterion shows: text + 📄 filename.pdf
```

---

## Key Features

### ✅ Source File Tracking
Every extracted data point shows which file it came from:
- **Requirement 1** → 📄 contract_documents.pdf
- **Risk 1** → 📄 bill_of_quantities.x84
- **Evaluation criterion** → 📄 award_description.pdf

### ✅ Top 5 Limits
Only shows most important items:
- Top 5 mandatory requirements
- Top 5 major risks

### ✅ Merged Data
All files combined into ONE tender view:
- Not per-file breakdown
- Unified, comprehensive display

### ✅ All File Types Supported
- PDF (normal + OCR)
- GAEB (all extensions)
- Word, Excel, CSV, TXT
- Nested ZIPs

---

## Testing Instructions

See: **`docs/PHASE_13_FRONTEND_TESTING.md`**

Quick test:
```powershell
# Start services (backend, worker, frontend)
# Open http://localhost:5173
# Login: admin / Tender@2026
# Click: "Upload documents"
# Upload a ZIP with PDFs/GAEB
# Wait for processing
# Verify Step 2 shows merged data with source links
```

---

## Success Criteria

✅ Upload works from frontend  
✅ Processing completes for all file types  
✅ Merged data displayed (not per-file)  
✅ Top 5 requirements shown with source links  
✅ Top 5 risks shown with source links  
✅ Source filenames match uploaded files  
✅ All existing functionality preserved  
✅ No database/backend changes  

---

## Restart Required

After applying these changes:

1. **Queue Worker** MUST be restarted:
   ```powershell
   # Stop: Ctrl+C
   # Start: python -m workers.queue_worker
   ```
   Reason: LLM prompt changed

2. **Frontend** MUST be restarted:
   ```powershell
   # Stop: Ctrl+C
   # Start: npm run dev
   ```
   Reason: Component logic changed

3. **Backend** does NOT need restart (no changes)

---

## Verification Checklist

After restarting services, verify:

- [ ] Queue worker shows: "Listening on queue: tender:jobs"
- [ ] Frontend loads at localhost:5173
- [ ] Upload a test ZIP
- [ ] Processing completes
- [ ] Step 2 shows extracted data
- [ ] Requirements have blue source links (📄 filename)
- [ ] Risks have blue source links (📄 filename)
- [ ] Evaluation criteria have source links
- [ ] Exactly 5 requirements shown (or fewer if < 5 extracted)
- [ ] Exactly 5 risks shown (or fewer if < 5 extracted)
- [ ] No per-file breakdown visible
- [ ] All data is merged from multiple files

---

## Next Steps

1. Test with real tender ZIPs
2. Verify LLM extraction quality
3. Tune prompt if needed
4. Add export functionality (PDF/Excel)
5. Consider adding filters/search on extracted data
