param(
    [string]$MachineName = "local",
    [ValidateSet("live", "local")]
    [string]$DataMode = "live",
    [string]$AwsProfile = "your-readonly-profile",
    [switch]$UseDefaultAwsCredentials,
    [int]$BackendPort = 8000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$LogPath = Join-Path $RepoRoot "backend-dev-local.log"

$Host.UI.RawUI.WindowTitle = "AI Radar Backend - $MachineName"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue
$env:AI_RADAR_BACKEND_PRELOAD_CACHE = "0"
$env:AI_RADAR_USE_LOCAL_OUTPUT = if ($DataMode -eq "local") { "1" } else { "0" }
if ($DataMode -eq "live") {
    if ($UseDefaultAwsCredentials) {
        Remove-Item Env:AWS_PROFILE -ErrorAction SilentlyContinue
    } else {
        $env:AWS_PROFILE = $AwsProfile.Trim()
    }
}
$env:PYTHONUNBUFFERED = "1"

try {
    Start-Transcript -Path $LogPath -Append | Out-Null
} catch {
    Write-Host "Could not start transcript: $($_.Exception.Message)"
}

Write-Host "Machine: $MachineName"
Write-Host "Data mode: $DataMode"
$displayProfile = if ($env:AWS_PROFILE) { $env:AWS_PROFILE } else { "default credential chain" }
Write-Host "AWS profile: $displayProfile"
Write-Host "Starting backend on http://127.0.0.1:$BackendPort"
Write-Host "Log: $LogPath"
Write-Host "Backend dir: $BackendDir"

Set-Location $BackendDir
& $PythonExe -u -m uvicorn app.main:app --host 127.0.0.1 --port $BackendPort

Write-Host "Backend process exited with code $LASTEXITCODE"
try {
    Stop-Transcript | Out-Null
} catch {}
