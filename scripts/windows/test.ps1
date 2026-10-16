<#
.SYNOPSIS
    PK-OS Test & Verification Runner
.DESCRIPTION
    Runs all existing repository verifications, linters, and structure checks
    from Windows PowerShell, delegating Linux-specific checks to WSL2.
#>

[CmdletBinding()]
param(
    [switch]$SkipLint,
    [switch]$SkipStructure
)

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "             PK-OS Test & Lint Runner                     " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$driveLetter = $repoRoot.Substring(0, 1).ToLower()
$wslPath = "/mnt/" + $driveLetter + $repoRoot.Substring(2).Replace("\", "/")

$FailedSteps = 0

# 1. Structure Verification
if (-not $SkipStructure) {
    Write-Host "[1/2] Verifying Critical Repository Artifacts..." -ForegroundColor Yellow
    $criticalFiles = @(
        "README.md",
        "LICENSE",
        "SECURITY.md",
        "CONTRIBUTING.md",
        "CODE_OF_CONDUCT.md",
        ".gitattributes",
        ".gitignore",
        ".markdownlint.yaml",
        ".yamllint.yaml",
        ".github\workflows\ci.yml",
        "docs\adr\ADR-001-base-distribution.md",
        "docs\architecture\OVERVIEW.md",
        "docs\architecture\ROADMAP.md",
        "docs\development\SETUP.md",
        "docs\release\HARDWARE-COMPATIBILITY.md",
        "docs\release\RELEASE-PROCESS.md",
        "docs\security\INVARIANTS.md",
        "docs\security\THREAT-MODEL.md",
        "docs\testing\FAILURE-MODE-MATRIX.md",
        "docs\testing\TEST-STRATEGY.md",
        "scripts\check-prereqs.sh",
        "scripts\lint.sh",
        "scripts\windows\check-prereqs.ps1",
        "scripts\windows\setup.ps1",
        "scripts\windows\check-build-environment.ps1",
        "scripts\windows\build.ps1",
        "scripts\windows\test.ps1"
    )

    $allFilesExist = $true
    foreach ($f in $criticalFiles) {
        $p = Join-Path $repoRoot $f
        if (Test-Path $p) {
            Write-Host "  [OK] $f" -ForegroundColor Green
        } else {
            Write-Host "  [FAIL] Missing required artifact: $f" -ForegroundColor Red
            $allFilesExist = $false
        }
    }
    if (-not $allFilesExist) { $FailedSteps++ }
}

# 2. Linux Prerequisite & Linting Suite in WSL
if (-not $SkipLint) {
    Write-Host "`n[2/2] Running Prerequisite & Linting Suite inside WSL2..." -ForegroundColor Yellow
    wsl -d Ubuntu bash -c "cd '$wslPath' && ./scripts/check-prereqs.sh && ./scripts/lint.sh"
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  [FAIL] WSL test suite returned exit code $LASTEXITCODE" -ForegroundColor Red
        $FailedSteps++
    } else {
        Write-Host "  [OK] WSL test and lint suite passed successfully." -ForegroundColor Green
    }
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
if ($FailedSteps -eq 0) {
    Write-Host "   All Tests & Linters PASSED (Exit Code 0)              " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "   $FailedSteps Test Suite(s) FAILED (Exit Code 1)       " -ForegroundColor Red
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 1
}
