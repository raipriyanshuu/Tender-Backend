$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$sharedRoot = Join-Path $repoRoot "shared"

$dirs = @(
  "uploads",
  "extracted",
  "temp",
  "logs",
  ".metadata",
  ".metadata\locks"
)

foreach ($dir in $dirs) {
  $path = Join-Path $sharedRoot $dir
  New-Item -ItemType Directory -Path $path -Force | Out-Null
}

Write-Host "Shared filesystem initialized at $sharedRoot"
