$ErrorActionPreference = "Stop"

$skillsRoot = Join-Path $HOME ".claude\skills"

$waveOneSkills = @(
    @{
        Name = "radar-agent-repo-profile"
        InputSchema = "agent_repo_profile.input.json"
        OutputSchema = "agent_repo_profile.output.json"
    },
    @{
        Name = "radar-friction-to-opportunity"
        InputSchema = "friction_signal.input.json"
        OutputSchema = "friction_signal.output.json"
    },
    @{
        Name = "util-json-repair"
        InputSchema = "json_repair.input.json"
        OutputSchema = "json_repair.output.json"
    },
    @{
        Name = "input-image-analyze"
        InputSchema = "image_analysis.input.json"
        OutputSchema = "image_analysis.output.json"
    },
    @{
        Name = "input-text-analyze"
        InputSchema = "text_analysis.input.json"
        OutputSchema = "text_analysis.output.json"
    },
    @{
        Name = "radar-signal-insight"
        InputSchema = "signal_insight.input.json"
        OutputSchema = "signal_insight.output.json"
    },
    @{
        Name = "reflection-polish"
        InputSchema = "reflection_polish.input.json"
        OutputSchema = "reflection_polish.output.json"
    }
)

if (-not (Test-Path $skillsRoot)) {
    throw "Skills directory not found: $skillsRoot"
}

$overallPass = $true

foreach ($skill in $waveOneSkills) {
    $skillDir = Join-Path $skillsRoot $skill.Name
    $referencesDir = Join-Path $skillDir "references"

    $checks = [ordered]@{
        "SKILL.md" = Test-Path (Join-Path $skillDir "SKILL.md")
        ".skill-hash" = Test-Path (Join-Path $skillDir ".skill-hash")
        $skill.InputSchema = Test-Path (Join-Path $referencesDir $skill.InputSchema)
        $skill.OutputSchema = Test-Path (Join-Path $referencesDir $skill.OutputSchema)
        "quality-notes.md" = Test-Path (Join-Path $referencesDir "quality-notes.md")
        "version-history.md" = Test-Path (Join-Path $referencesDir "version-history.md")
        "golden-examples/README.md" = Test-Path (Join-Path $referencesDir "golden-examples\README.md")
        "failure-cases/README.md" = Test-Path (Join-Path $referencesDir "failure-cases\README.md")
    }

    $missing = @($checks.GetEnumerator() | Where-Object { -not $_.Value } | ForEach-Object { $_.Key })
    $passed = $missing.Count -eq 0

    if (-not $passed) {
        $overallPass = $false
    }

    Write-Host ""
    Write-Host "== $($skill.Name) ==" -ForegroundColor Cyan
    if ($passed) {
        Write-Host "PASS" -ForegroundColor Green
    }
    else {
        Write-Host "FAIL" -ForegroundColor Red
        Write-Host "Missing:" -ForegroundColor Yellow
        foreach ($item in $missing) {
            Write-Host " - $item"
        }
    }
}

Write-Host ""
if ($overallPass) {
    Write-Host "Wave 1 skill scaffolding check passed." -ForegroundColor Green
    exit 0
}

Write-Host "Wave 1 skill scaffolding check failed." -ForegroundColor Red
exit 1
