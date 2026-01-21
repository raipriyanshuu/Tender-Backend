# Shared Filesystem (Phase 2)

This project uses a local shared filesystem so the backend and workers see the same files.

## Local Path

- Base folder: `shared/` (repo root)
- Docker containers should mount this folder as `/shared`

## Folder Layout

- `shared/uploads/`    ZIP files uploaded by the backend
- `shared/extracted/`  Unzipped files per batch (worker writes here)
- `shared/temp/`       Temporary processing files
- `shared/logs/`       Optional processing logs
- `shared/.metadata/`  Internal metadata and locks

## Initialize

Run the init script once:

- PowerShell: `.\scripts\init_shared_volume.ps1`
- Bash: `./scripts/init_shared_volume.sh`

## Path Conventions

### Backend
- Saves files to: `/shared/uploads/{batch_id}.zip`
- Stores in DB: `uploads/{batch_id}.zip` (relative path)
- Passes to worker: Full batch record with file paths

### Worker
- Receives: `{batch_id}` from backend
- Reads from: `/shared/uploads/{batch_id}.zip` (absolute)
- Extracts to: `/shared/extracted/{batch_id}/` (absolute)
- Writes results to DB with relative paths

## Notes

- Keep file paths **absolute** inside containers (e.g., `/shared/uploads/batch_123.zip`)
- Store **relative** paths in database (e.g., `uploads/batch_123.zip`)
- Backend writes ZIPs to `uploads/`
- Worker extracts to `extracted/`
- Both services use the same base path: `/shared`

