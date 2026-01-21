# Shared Filesystem

This folder is the local shared storage used by the backend and workers.

## Structure

- `uploads/`    ZIP files uploaded by the backend
- `extracted/`  Unzipped files per batch (worker writes here)
- `temp/`       Temporary processing files
- `logs/`       Optional processing logs
- `.metadata/`  Internal lock files and small tracking data

## Local Development

Run the init script to create the folders:

- PowerShell: `.\scripts\init_shared_volume.ps1`
- Bash: `./scripts/init_shared_volume.sh`

