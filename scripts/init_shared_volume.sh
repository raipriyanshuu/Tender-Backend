#!/usr/bin/env sh
set -e

repo_root="$(cd "$(dirname "$0")/.." && pwd)"
shared_root="$repo_root/shared"

mkdir -p \
  "$shared_root/uploads" \
  "$shared_root/extracted" \
  "$shared_root/temp" \
  "$shared_root/logs" \
  "$shared_root/.metadata" \
  "$shared_root/.metadata/locks"

echo "Shared filesystem initialized at $shared_root"
