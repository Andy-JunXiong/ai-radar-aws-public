$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "skills.ps1"
& $scriptPath --check @args
exit $LASTEXITCODE
