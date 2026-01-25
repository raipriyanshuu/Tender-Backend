# Storage Migration Guide

## Overview

The tender processing system now supports both local filesystem and Cloudflare R2 object storage. This guide explains how to migrate from local storage to R2 for production deployments.

## Storage Backends

### Local Storage (Default)
- **Use case**: Local development, testing
- **Pros**: Fast, no cloud costs, simple setup
- **Cons**: Ephemeral in production (data lost on container restart)

### Cloudflare R2 Storage
- **Use case**: Production deployments (Render, AWS, etc.)
- **Pros**: Persistent, survives restarts, scalable
- **Cons**: Network latency, cloud costs

## Environment Variables

### Required for All Modes

```bash
# Storage backend selection
STORAGE_BACKEND=local  # Options: "local" | "r2"
```

### Required for R2 Mode

```bash
# R2 Configuration
R2_ACCOUNT_ID=your_cloudflare_account_id
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=tender-storage
R2_REGION=auto  # Cloudflare uses "auto"

# Optional: Environment prefix for multi-tenancy
STORAGE_ENVIRONMENT=prod  # Options: "dev" | "staging" | "prod"
```

### Optional (Both Modes)

```bash
STORAGE_BASE_PATH=/shared  # Only used for local mode
STORAGE_UPLOADS_DIR=uploads
STORAGE_EXTRACTED_DIR=extracted
```

## Setup Instructions

### 1. Create Cloudflare R2 Bucket

1. Log in to Cloudflare Dashboard
2. Navigate to R2 Object Storage
3. Click "Create bucket"
4. Name: `tender-storage`
5. Location: Auto (recommended)

### 2. Generate R2 API Credentials

1. In R2 dashboard, click "Manage R2 API Tokens"
2. Click "Create API Token"
3. Permissions: "Object Read & Write"
4. Bucket: Select `tender-storage` or "All buckets"
5. Copy Access Key ID and Secret Access Key

### 3. Update Environment Variables

**Backend (.env):**
```bash
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_key_here
R2_BUCKET_NAME=tender-storage
STORAGE_ENVIRONMENT=prod
```

**Workers (.env):**
```bash
STORAGE_BACKEND=r2
R2_ACCOUNT_ID=your_account_id_here
R2_ACCESS_KEY_ID=your_access_key_here
R2_SECRET_ACCESS_KEY=your_secret_key_here
R2_BUCKET_NAME=tender-storage
STORAGE_ENVIRONMENT=prod
```

### 4. Install Dependencies

**Python Workers:**
```bash
cd workers
pip install boto3>=1.34.0
```

**Node.js Backend:**
```bash
cd tenderBackend
npm install @aws-sdk/client-s3
```

### 5. Test R2 Connection

**Test upload:**
```bash
# Upload a test file via API
curl -X POST http://localhost:3001/upload-tender \
  -F "file=@test.zip"
```

**Verify in R2:**
- Check Cloudflare R2 dashboard
- Look for files under `prod/uploads/`

## Migration Strategy

### Phase 1: Local Development (Current)

```bash
STORAGE_BACKEND=local
```

- All files stored in `./shared/`
- Fast iteration
- No cloud costs

### Phase 2: R2 Testing (Staging)

```bash
STORAGE_BACKEND=r2
STORAGE_ENVIRONMENT=staging
```

- Test R2 integration
- Validate all file types work
- Monitor costs and performance

### Phase 3: Production Deployment

```bash
STORAGE_BACKEND=r2
STORAGE_ENVIRONMENT=prod
```

- Switch production to R2
- Monitor error rates
- Keep local backup for 1 week

## Object Key Structure

Files are stored in R2 with the following structure:

```
{environment}/{category}/{batch_id}/{filename}
```

**Examples:**
```
prod/uploads/batch_abc123/batch_abc123.zip
prod/extracted/batch_abc123/document.pdf
prod/extracted/batch_abc123/nested/spec.docx
staging/uploads/batch_xyz789/batch_xyz789.zip
```

## Troubleshooting

### Error: "R2 configuration incomplete"

**Cause:** Missing R2 environment variables

**Solution:** Ensure all required R2 variables are set:
- R2_ACCOUNT_ID
- R2_ACCESS_KEY_ID
- R2_SECRET_ACCESS_KEY
- R2_BUCKET_NAME

### Error: "Failed to read from R2: File not found"

**Cause:** File doesn't exist in R2 bucket

**Solution:**
1. Check R2 dashboard for file
2. Verify `STORAGE_ENVIRONMENT` matches (prod vs staging)
3. Check file was uploaded successfully

### Error: "Permission denied for R2"

**Cause:** Invalid or expired R2 credentials

**Solution:**
1. Regenerate R2 API token
2. Update R2_ACCESS_KEY_ID and R2_SECRET_ACCESS_KEY
3. Verify token has "Object Read & Write" permissions

### Slow Upload/Download Performance

**Cause:** Network latency to R2

**Solution:**
1. Choose R2 region closest to your deployment
2. Monitor file sizes (large files take longer)
3. Consider compression for large ZIPs

## Cost Estimation

Cloudflare R2 Pricing (as of 2024):
- Storage: $0.015/GB/month
- Class A Operations (write): $4.50 per million
- Class B Operations (read): $0.36 per million
- Egress: FREE (no bandwidth charges)

**Example:**
- 100 batches/month
- Average 50MB per batch
- 5GB total storage
- ~10,000 operations/month

**Monthly Cost:** ~$0.08 + $0.04 = **$0.12/month**

## Rollback Plan

If R2 has issues, rollback to local storage:

1. Set `STORAGE_BACKEND=local`
2. Restart backend and workers
3. Files will be stored locally again
4. Note: Previously uploaded R2 files won't be accessible

## Best Practices

1. **Use environment prefixes** (`prod`, `staging`, `dev`) to isolate data
2. **Monitor R2 costs** via Cloudflare dashboard
3. **Set up lifecycle policies** to delete old files after 90 days
4. **Test locally first** before deploying to production
5. **Keep R2 credentials secure** - never commit to git

## Support

For issues:
1. Check Cloudflare R2 status page
2. Review backend/worker logs
3. Verify environment variables are set correctly
4. Test with a small file first
