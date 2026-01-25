# Tender Backend API

Backend API server for the tender document processing system. This Node.js/Express server connects to PostgreSQL and provides REST endpoints to fetch tender data processed by the N8N workflow.

## 🏗️ Architecture

```
Frontend (React) → Backend API (Node.js/Express) → PostgreSQL Database
                                                          ↑
                                                    N8N Workflow
                                                    (LLM Processing)
```

The N8N workflow processes tender documents with LLM and stores extracted data in PostgreSQL. This backend API reads that data and serves it to the frontend.

## 📋 Prerequisites

- Node.js 18+ installed
- PostgreSQL database (Supabase)
- Access to the database connection string

## 🚀 Quick Start

### 1. Install Dependencies

```bash
cd tenderBackend
npm install
```

### 2. Configure Environment Variables

Create a `.env` file (copy from `.env.example`):

```bash
cp .env.example .env
```

Edit `.env` and add your database password:

```env
DATABASE_URL=postgresql://postgres.mbandhbypmgtlxmwbyae:[YOUR-PASSWORD]@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
PORT=3001
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173
```

### 3. Run Database Migration

Connect to your PostgreSQL database and run the migration:

```bash
psql $DATABASE_URL -f migrations/create_n8n_tables.sql
```

Or use your database client (pgAdmin, DBeaver, etc.) to execute the SQL file.

### 4. Start the Server

**Development mode (with auto-reload):**
```bash
npm run dev
```

**Production mode:**
```bash
npm start
```

The server will start on `http://localhost:3001`

## 📡 API Endpoints

### Health Check
```
GET /api/tenders/health
```
Check if the API and database connection are working.

**Response:**
```json
{
  "success": true,
  "status": "healthy",
  "timestamp": "2026-01-17T10:30:00.000Z",
  "database": "connected"
}
```

---

### Get All Tenders
```
GET /api/tenders
```
Fetch all processed tenders from the database.

**Query Parameters:**
- `sortBy` (optional): `deadline` or `score` (default: `deadline`)
- `limit` (optional): Number of results (default: `50`)
- `offset` (optional): Pagination offset (default: `0`)

**Response:**
```json
{
  "success": true,
  "count": 3,
  "data": [
    {
      "id": "t-ce-501",
      "title": "Baustelleneinrichtung Infrastrukturprojekt A7",
      "buyer": "DEGES GmbH",
      "region": "DE-HH",
      "deadline": "2025-12-15",
      "url": "/tender/t-ce-501",
      "score": 91,
      "legalRisks": ["VOB/C DIN 18299", "DGUV Vorschrift 52/70/52"],
      "mustHits": 9,
      "mustTotal": 10,
      "canHits": 14,
      "canTotal": 16,
      "serviceTypes": ["Baustelleneinrichtung", "Erdbau"]
    }
  ]
}
```

---

### Get Tender Details
```
GET /api/tenders/:tenderId
```
Fetch detailed information for a specific tender.

**Response:**
```json
{
  "success": true,
  "data": {
    "id": "t-ce-501",
    "title": "t-ce-501",
    "deadline": "2025-12-15",
    "deadlineLabel": "Submission Deadline",
    "daysRemaining": 332,
    "briefDescription": "Construction equipment rental project...",
    "mandatoryRequirements": ["ISO 9001", "DGUV certification"],
    "mainRisks": ["Penalty clauses", "Insurance requirements"],
    "economicAnalysis": {
      "potential_margin": { "min_percent": 15, "max_percent": 25 },
      "order_value_estimated": { "min_eur": 50000, "max_eur": 150000 }
    }
  }
}
```

---

### List All Runs
```
GET /api/tenders/runs/list
```
Get a list of all N8N workflow runs.

**Response:**
```json
{
  "success": true,
  "count": 5,
  "data": [
    {
      "run_id": "12345",
      "status": "COMPLETED",
      "total_files": 3,
      "success_files": 3,
      "failed_files": 0,
      "created_at": "2026-01-17T10:00:00.000Z",
      "updated_at": "2026-01-17T10:05:00.000Z"
    }
  ]
}
```

---

### Get Run Files
```
GET /api/tenders/runs/:runId/files
```
Get all files processed in a specific N8N run.

**Response:**
```json
{
  "success": true,
  "runId": "12345",
  "count": 3,
  "data": [
    {
      "id": "uuid-1",
      "doc_id": "doc-123",
      "filename": "tender_document.pdf",
      "file_type": "application/pdf",
      "status": "SUCCESS",
      "error": null,
      "created_at": "2026-01-17T10:00:00.000Z"
    }
  ]
}
```

---

### Batch Summary (Phase 9)
```
GET /api/batches/:batchId/summary
```
Returns the aggregated `run_summaries` record for a batch once aggregation finishes.

## 🗄️ Database Schema

### `file_extractions` Table
Stores extraction results for each processed file.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| run_id | text | N8N execution ID |
| source | text | Source (e.g., 'gdrive') |
| doc_id | text | Document identifier (unique) |
| filename | text | Original filename |
| file_type | text | MIME type |
| extracted_json | jsonb | LLM extracted data |
| status | text | 'SUCCESS' or 'FAILED' |
| error | text | Error message if failed |
| created_at | timestamptz | Creation timestamp |
| updated_at | timestamptz | Last update timestamp |

### `run_summaries` Table
Stores aggregated UI-ready data for each N8N run.

| Column | Type | Description |
|--------|------|-------------|
| id | uuid | Primary key |
| run_id | text | N8N execution ID (unique) |
| summary_json | jsonb | Summary of all files |
| ui_json | jsonb | Frontend-ready JSON |
| total_files | integer | Total files in run |
| success_files | integer | Successfully processed files |
| failed_files | integer | Failed files |
| status | text | Run status |
| created_at | timestamptz | Creation timestamp |
| updated_at | timestamptz | Last update timestamp |

## 🔗 Frontend Integration

### Configure Frontend

In your frontend project, create a `.env` file:

```env
VITE_API_URL=http://localhost:3001
```

### Example Frontend Code

```typescript
// Fetch all tenders
const response = await fetch(`${import.meta.env.VITE_API_URL}/api/tenders`);
const data = await response.json();
console.log(data.data); // Array of tenders

// Fetch tender details
const detailResponse = await fetch(
  `${import.meta.env.VITE_API_URL}/api/tenders/t-ce-501`
);
const detailData = await detailResponse.json();
console.log(detailData.data); // Tender details
```

## 🔧 Development

### Project Structure

```
tenderBackend/
├── src/
│   ├── index.js          # Express server & app setup
│   ├── db.js             # PostgreSQL connection pool
│   └── routes/
│       └── tenders.js    # API route handlers
├── migrations/
│   └── create_n8n_tables.sql  # Database schema
├── package.json
├── .env                  # Environment variables (not in git)
├── .env.example          # Example env file
├── .gitignore
└── README.md
```

### Adding New Endpoints

1. Open `src/routes/tenders.js`
2. Add your route handler:
```javascript
router.get('/my-endpoint', async (req, res) => {
  try {
    const result = await query('SELECT * FROM my_table');
    res.json({ success: true, data: result.rows });
  } catch (error) {
    res.status(500).json({ success: false, error: error.message });
  }
});
```

### Database Queries

Use the `query` helper function from `db.js`:

```javascript
import { query } from '../db.js';

// Simple query
const result = await query('SELECT * FROM tenders');

// Parameterized query (prevents SQL injection)
const result = await query(
  'SELECT * FROM tenders WHERE id = $1',
  [tenderId]
);
```

## 🐛 Troubleshooting

### Connection Refused
- Make sure the server is running (`npm run dev`)
- Check that PORT 3001 is not already in use
- Verify CORS_ORIGIN matches your frontend URL

### Database Connection Errors
- Verify DATABASE_URL is correct in `.env`
- Check that database tables exist (run migration)
- Ensure your IP is allowed in Supabase settings
- Test connection: `psql $DATABASE_URL -c "SELECT NOW()"`

### No Tenders Returned
- Check if N8N workflow has run and populated the database
- Query the database directly: `SELECT * FROM run_summaries;`
- Check server logs for errors

### CORS Errors
- Ensure CORS_ORIGIN in `.env` matches your frontend URL
- For development, use `http://localhost:5173` (Vite default)

## 📝 Notes

- **No Authentication**: This is a demo setup. Add authentication for production.
- **No File Upload**: Backend only reads from DB. N8N webhook handles file uploads.
- **Fallback to Mock Data**: Frontend falls back to MOCK_TENDERS if API fails.
- **SSL Required**: Supabase requires SSL connections (configured in `db.js`).

## 🚀 Deployment

For production deployment:

1. Set `NODE_ENV=production` in `.env`
2. Use a process manager like PM2:
   ```bash
   npm install -g pm2
   pm2 start src/index.js --name tender-api
   ```
3. Set up reverse proxy (nginx) for HTTPS
4. Add authentication middleware
5. Enable rate limiting
6. Set up monitoring and logging

## 📄 License

MIT
