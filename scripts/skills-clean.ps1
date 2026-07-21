$ErrorActionPreference = "Stop"

$scriptPath = Join-Path $PSScriptRoot "skills.ps1"
& $scriptPath --clean @args
exit $LASTEXITCODE
