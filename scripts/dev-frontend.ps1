param(
    [string]$MachineName = "local",
    [int]$FrontendPort = 3000
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $RepoRoot "frontend"
$NodeExe = (Get-Command "node.exe" -ErrorAction Stop).Source
$LogPath = Join-Path $RepoRoot "frontend-dev-local.log"

$Host.UI.RawUI.WindowTitle = "AI Radar Frontend - $MachineName"
Remove-Item Env:ELECTRON_RUN_AS_NODE -ErrorAction SilentlyContinue

try {
    Start-Transcript -Path $LogPath -Append | Out-Null
} catch {
    Write-Host "Could not start transcript: $($_.Exception.Message)"
}

Write-Host "Machine: $MachineName"
Write-Host "Starting frontend on http://127.0.0.1:$FrontendPort"
Write-Host "Log: $LogPath"
Write-Host "Frontend dir: $FrontendDir"

Set-Location $FrontendDir
& $NodeExe node_modules/next/dist/bin/next dev --hostname 127.0.0.1 --port $FrontendPort

Write-Host "Frontend process exited with code $LASTEXITCODE"
try {
    Stop-Transcript | Out-Null
} catch {}
