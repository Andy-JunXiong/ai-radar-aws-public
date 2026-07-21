param(
    [string]$MachineName,
    [ValidateSet("live", "local")]
    [string]$DataMode,
    [string]$AwsProfile,
    [switch]$UseDefaultAwsCredentials,
    [int]$FrontendPort,
    [int]$BackendPort,
    [switch]$NoOpenWindows,
    [switch]$SkipVerify
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$FrontendDir = Join-Path $RepoRoot "frontend"
$BackendDir = Join-Path $RepoRoot "backend"
$PythonExe = Join-Path $RepoRoot ".venv\Scripts\python.exe"
$PythonwExe = Join-Path $RepoRoot ".venv\Scripts\pythonw.exe"
$NodeExe = (Get-Command "node.exe" -ErrorAction Stop).Source
$FrontendRunner = Join-Path $PSScriptRoot "dev-frontend.ps1"
$BackendRunner = Join-Path $PSScriptRoot "dev-backend.ps1"
$BackendPyRunner = Join-Path $PSScriptRoot "dev_backend.py"
$LocalDevConfigPath = Join-Path $PSScriptRoot "local-dev-config.json"

function Get-DefaultMachineName {
    param([object]$Config)

    $computerName = $env:COMPUTERNAME
    if ($Config -and $Config.machines) {
        foreach ($property in $Config.machines.PSObject.Properties) {
            $candidate = $property.Value
            if ($candidate.windowsComputerName -and $candidate.windowsComputerName -ieq $computerName) {
                return [string]$property.Name
            }
        }
        if ($Config.defaultMachine) {
            return [string]$Config.defaultMachine
        }
    }
    return $computerName
}

function Get-MachineConfig {
    param(
        [object]$Config,
        [string]$Name
    )

    if (-not $Config -or -not $Config.machines -or -not $Name) {
        return $null
    }
    return $Config.machines.PSObject.Properties |
        Where-Object { $_.Name -ieq $Name } |
        Select-Object -First 1 -ExpandProperty Value
}

function Test-CommandPath {
    param(
        [string]$Path,
        [string]$Label
    )

    if (-not (Test-Path $Path)) {
        throw "$Label not found: $Path"
    }
}

function Get-PortListeners {
    param([int]$Port)

    Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue |
        Select-Object LocalAddress, LocalPort, State, OwningProcess
}

function Test-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSec = 3
    )

    try {
        $response = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec $TimeoutSec
        return [int]$response.StatusCode -ge 200 -and [int]$response.StatusCode -lt 500
    } catch {
        return $false
    }
}

function Wait-HttpOk {
    param(
        [string]$Url,
        [int]$TimeoutSec = 30
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    while ((Get-Date) -lt $deadline) {
        if (Test-HttpOk -Url $Url) {
            return $true
        }
        Start-Sleep -Seconds 1
    }
    return $false
}

$localDevConfig = $null
if (Test-Path $LocalDevConfigPath) {
    $localDevConfig = Get-Content -Path $LocalDevConfigPath -Raw | ConvertFrom-Json
}

if (-not $PSBoundParameters.ContainsKey("MachineName") -or [string]::IsNullOrWhiteSpace($MachineName)) {
    $MachineName = Get-DefaultMachineName -Config $localDevConfig
}

$machineConfig = Get-MachineConfig -Config $localDevConfig -Name $MachineName
if ($machineConfig) {
    if (-not $PSBoundParameters.ContainsKey("DataMode") -and $machineConfig.dataMode) {
        $DataMode = [string]$machineConfig.dataMode
    }
    if (-not $PSBoundParameters.ContainsKey("AwsProfile") -and $machineConfig.awsProfile) {
        $AwsProfile = [string]$machineConfig.awsProfile
    }
    if (-not $PSBoundParameters.ContainsKey("FrontendPort") -and $machineConfig.frontendPort) {
        $FrontendPort = [int]$machineConfig.frontendPort
    }
    if (-not $PSBoundParameters.ContainsKey("BackendPort") -and $machineConfig.backendPort) {
        $BackendPort = [int]$machineConfig.backendPort
    }
    if (-not $PSBoundParameters.ContainsKey("UseDefaultAwsCredentials") -and $machineConfig.useDefaultAwsCredentials) {
        $UseDefaultAwsCredentials = [bool]$machineConfig.useDefaultAwsCredentials
    }
}

if ([string]::IsNullOrWhiteSpace($MachineName)) {
    $MachineName = "local"
}
if ([string]::IsNullOrWhiteSpace($DataMode)) {
    $DataMode = "live"
}
if ([string]::IsNullOrWhiteSpace($AwsProfile)) {
    $AwsProfile = "your-readonly-profile"
}
if (-not $FrontendPort) {
    $FrontendPort = 3000
}
if (-not $BackendPort) {
    $BackendPort = 8000
}

Test-CommandPath -Path $PythonExe -Label "Python virtualenv"
Test-CommandPath -Path $PythonwExe -Label "Pythonw virtualenv"
Test-CommandPath -Path (Join-Path $FrontendDir "node_modules\next\dist\bin\next") -Label "Next.js"
Test-CommandPath -Path $FrontendRunner -Label "Frontend runner"
Test-CommandPath -Path $BackendRunner -Label "Backend runner"
Test-CommandPath -Path $BackendPyRunner -Label "Backend Python runner"

Write-Host "Machine: $MachineName"
Write-Host "Data mode: $DataMode"
if ($DataMode -eq "live") {
    $displayProfile = if ($UseDefaultAwsCredentials) { "default credential chain" } else { $AwsProfile }
    Write-Host "AWS profile: $displayProfile"
}

$frontendUrl = "http://127.0.0.1:$FrontendPort"
$backendHealthUrl = "http://127.0.0.1:$BackendPort/health"
$backendVerifyUrl = "http://127.0.0.1:$BackendPort/auth/verify"

$frontendListeners = @(Get-PortListeners -Port $FrontendPort)
$backendListeners = @(Get-PortListeners -Port $BackendPort)
$frontendAlreadyReady = Test-HttpOk -Url $frontendUrl
$backendAlreadyReady = Test-HttpOk -Url $backendHealthUrl

if ($frontendAlreadyReady) {
    Write-Host "Frontend is already responding on $frontendUrl"
} elseif ($frontendListeners.Count -gt 0) {
    Write-Host "Frontend port $FrontendPort is already listening:"
    $frontendListeners | Format-Table | Out-String | Write-Host
} elseif (-not $NoOpenWindows) {
    Write-Host "Starting frontend on $frontendUrl ..."
    $frontendArgs = @(
        "-NoExit",
        "-ExecutionPolicy", "Bypass",
        "-File", "`"$FrontendRunner`"",
        "-MachineName", "`"$MachineName`"",
        "-FrontendPort", "$FrontendPort"
    )
    Start-Process -FilePath "powershell.exe" `
        -ArgumentList $frontendArgs `
        -WindowStyle Minimized
}

if ($backendAlreadyReady) {
    Write-Host "Backend is already responding on $backendHealthUrl"
} elseif ($backendListeners.Count -gt 0) {
    Write-Host "Backend port $BackendPort is already listening:"
    $backendListeners | Format-Table | Out-String | Write-Host
} elseif (-not $NoOpenWindows) {
    Write-Host "Starting backend on http://127.0.0.1:$BackendPort ..."
    $backendArgs = @(
        "`"$BackendPyRunner`"",
        "--machine", "`"$MachineName`"",
        "--data-mode", "$DataMode",
        "--port", "$BackendPort"
    )
    if ($UseDefaultAwsCredentials) {
        $backendArgs += "--use-default-aws-credentials"
    } else {
        $backendArgs += @("--aws-profile", "`"$AwsProfile`"")
    }
    Start-Process -FilePath $PythonwExe `
        -ArgumentList $backendArgs `
        -WorkingDirectory $RepoRoot `
        -WindowStyle Hidden
}

if ($SkipVerify) {
    Write-Host "Started local dev commands. Verification skipped."
    exit 0
}

Write-Host "Verifying frontend: $frontendUrl"
$frontendOk = Wait-HttpOk -Url $frontendUrl -TimeoutSec 35

Write-Host "Verifying backend: $backendHealthUrl"
$backendOk = Wait-HttpOk -Url $backendHealthUrl -TimeoutSec 35

Start-Sleep -Seconds 3
$backendStillOk = Test-HttpOk -Url $backendVerifyUrl -TimeoutSec 5

if ($frontendOk -and $backendOk -and $backendStillOk) {
    Write-Host "Local dev is ready:"
    Write-Host "  Machine: $MachineName"
    Write-Host "  Data mode: $DataMode"
    if ($DataMode -eq "live") {
        $displayProfile = if ($UseDefaultAwsCredentials) { "default credential chain" } else { $AwsProfile }
        Write-Host "  AWS profile: $displayProfile"
    }
    Write-Host "  Frontend: $frontendUrl"
    Write-Host "  Backend:  http://127.0.0.1:$BackendPort"
    exit 0
}

Write-Host "Local dev startup did not fully verify."
Write-Host "  Machine: $MachineName"
Write-Host "  Data mode: $DataMode"
if ($DataMode -eq "live") {
    $displayProfile = if ($UseDefaultAwsCredentials) { "default credential chain" } else { $AwsProfile }
    Write-Host "  AWS profile: $displayProfile"
}
Write-Host "  Frontend ready: $frontendOk"
Write-Host "  Backend health ready: $backendOk"
Write-Host "  Backend still reachable after delay: $backendStillOk"
Write-Host "Check the opened PowerShell windows for server logs."
exit 1
