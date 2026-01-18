# Setup Instructions

## Step-by-Step Setup Guide

### 1. Database Setup

First, run the database migration to create the required tables:

```bash
# Option A: Using psql command line
psql "postgresql://postgres.mbandhbypmgtlxmwbyae:[YOUR-PASSWORD]@aws-1-ap-south-1.pooler.supabase.com:5432/postgres" -f migrations/create_n8n_tables.sql

# Option B: Using Supabase Dashboard
# 1. Go to your Supabase project
# 2. Navigate to SQL Editor
# 3. Copy and paste the contents of migrations/create_n8n_tables.sql
# 4. Click "Run"
```

This will create:
- `file_extractions` table
- `run_summaries` table
- Indexes for performance
- RLS policies

### 2. Backend Setup

```bash
# Navigate to backend directory
cd tenderBackend

# Install dependencies
npm install

# Copy environment file
cp .env.example .env

# Edit .env and add your database password
# Replace [YOUR-PASSWORD] with your actual password
nano .env  # or use any text editor
```

Your `.env` should look like:
```env
DATABASE_URL=postgresql://postgres.mbandhbypmgtlxmwbyae:YOUR_ACTUAL_PASSWORD@aws-1-ap-south-1.pooler.supabase.com:5432/postgres
PORT=3001
NODE_ENV=development
CORS_ORIGIN=http://localhost:5173
```

### 3. Start Backend Server

```bash
# Development mode (auto-reload on changes)
npm run dev

# You should see:
# ╔═══════════════════════════════════════════════════════╗
# ║   🚀 Tender Backend API Server                       ║
# ║   Server running on: http://localhost:3001           ║
# ╚═══════════════════════════════════════════════════════╝
```

### 4. Test Backend API

Open a new terminal and test the health endpoint:

```bash
curl http://localhost:3001/api/tenders/health

# Expected response:
# {
#   "success": true,
#   "status": "healthy",
#   "timestamp": "2026-01-17T...",
#   "database": "connected"
# }
```

### 5. Frontend Setup

```bash
# Navigate to frontend directory
cd "../project-bolt-sb1-xva34j8s (1)/project"

# Install dependencies (if not already done)
npm install

# Create .env file
echo "VITE_API_URL=http://localhost:3001" > .env

# Start frontend
npm run dev

# Frontend will run on http://localhost:5173
```

### 6. Update N8N Webhook (Important!)

Your N8N workflow currently uses Google Drive as input. You need to:

1. **Add Webhook Trigger Node** in N8N:
   - Add a new "Webhook" node at the start of your workflow
   - Set HTTP Method to POST
   - Set Path to something like `/tender-upload`
   - Copy the webhook URL (e.g., `https://your-n8n.com/webhook/tender-upload`)

2. **Update Frontend to Call Webhook**:
   The frontend already has file upload UI. You'll need to add the webhook call in the upload handler.

3. **Remove Google Drive Node**:
   - Remove or disable the "Search files and folders1" node
   - Connect the Webhook node output to "Download file" node

### 7. Verify Everything Works

1. **Backend is running**: `http://localhost:3001/api/tenders/health` returns healthy
2. **Frontend is running**: `http://localhost:5173` loads
3. **Database is accessible**: Backend logs show "✅ Connected to PostgreSQL database"
4. **API returns data**: Frontend shows tenders (either from DB or mock data as fallback)

## Common Issues

### Issue: "ECONNREFUSED" when frontend calls backend
**Solution**: Make sure backend is running on port 3001

### Issue: "Database connection failed"
**Solution**: 
- Check DATABASE_URL in `.env`
- Verify password is correct
- Check Supabase connection pooler is enabled

### Issue: Frontend shows "Failed to fetch tenders"
**Solution**: 
- Check browser console for CORS errors
- Verify CORS_ORIGIN in backend `.env` matches frontend URL
- Check backend logs for errors

### Issue: No tenders showing up
**Solution**: 
- N8N workflow hasn't run yet (frontend will show mock data)
- Check database: `SELECT * FROM run_summaries;`
- Run N8N workflow to populate data

## Next Steps

1. **Populate Database**: Run your N8N workflow to process some tender documents
2. **Test API**: Use the runs endpoint to see processed data
3. **Update N8N**: Replace Google Drive input with webhook
4. **Add File Upload**: Connect frontend upload to N8N webhook

## Architecture Diagram

```
┌─────────────┐
│   Frontend  │
│  (React)    │
│ Port: 5173  │
└──────┬──────┘
       │
       │ HTTP GET /api/tenders
       │
       ▼
┌─────────────┐
│   Backend   │
│  (Node.js)  │
│ Port: 3001  │
└──────┬──────┘
       │
       │ SQL Queries
       │
       ▼
┌─────────────┐
│  PostgreSQL │
│  (Supabase) │
└──────▲──────┘
       │
       │ INSERT data
       │
┌──────┴──────┐
│     N8N     │
│  Workflow   │
│ (LLM + AI)  │
└─────────────┘
```

## Support

If you encounter issues:
1. Check backend logs in the terminal
2. Check browser console for frontend errors
3. Verify database connection with `psql`
4. Test API endpoints with `curl` or Postman
