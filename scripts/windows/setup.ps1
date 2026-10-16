<#
.SYNOPSIS
    PK-OS Windows & WSL Setup Automator
.DESCRIPTION
    Safely installs and configures missing zero-cost prerequisites.
    For Windows: guides or runs winget for missing user tools.
    For WSL2: verifies Ubuntu and installs required Linux packages inside WSL2.
    Adheres strictly to the ₹0 budget constraint.
#>

[CmdletBinding()]
param(
    [switch]$SkipWSL,
    [switch]$DryRun
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         PK-OS Zero-Cost Setup Automator                  " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# Find winget
$wingetCmd = Get-Command "winget" -ErrorAction SilentlyContinue
if (-not $wingetCmd) {
    $wingetApp = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\winget.exe"
    if (Test-Path $wingetApp) {
        $wingetCmd = [PSCustomObject]@{ Source = $wingetApp }
    }
}

# 1. Windows Tools Verification
Write-Host "[1/2] Verifying Windows-Side Tools..." -ForegroundColor Yellow

$toolsToVerify = @(
    @{ Name = "Git"; Command = "git"; WingetId = "Git.Git" },
    @{ Name = "Python 3"; Command = "py"; WingetId = "Python.Python.3.13" },
    @{ Name = "VS Code"; Command = "code"; WingetId = "Microsoft.VisualStudioCode" },
    @{ Name = "Windows Terminal"; Command = "wt"; WingetId = "Microsoft.WindowsTerminal" }
)

foreach ($t in $toolsToVerify) {
    $found = Get-Command $t.Command -ErrorAction SilentlyContinue
    if (-not $found) {
        $winApp = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$($t.Command).exe"
        if (Test-Path $winApp) { $found = $true }
    }
    if ($found) {
        Write-Host "  * $($t.Name): Already installed." -ForegroundColor Green
    } else {
        Write-Host "  * $($t.Name): Missing." -ForegroundColor Yellow
        if ($wingetCmd) {
            Write-Host "    Installing $($t.Name) via winget (ID: $($t.WingetId))..." -ForegroundColor Cyan
            if (-not $DryRun) {
                & $wingetCmd.Source install --id $t.WingetId -e --silent --accept-source-agreements --accept-package-agreements
            } else {
                Write-Host "    [DRY-RUN] Would run: winget install --id $($t.WingetId)" -ForegroundColor Gray
            }
        } else {
            Write-Host "    [MANUAL STEP] Winget not available. Please install $($t.Name) manually from official website." -ForegroundColor Red
        }
    }
}

# 2. Linux Tools inside WSL2
if ($SkipWSL) {
    Write-Host "`n[2/2] Skipping WSL2 setup as requested (-SkipWSL)." -ForegroundColor Gray
    exit 0
}

Write-Host "`n[2/2] Verifying and Setting Up WSL2 Ubuntu Environment..." -ForegroundColor Yellow
$hasWsl = Get-Command "wsl" -ErrorAction SilentlyContinue
if (-not $hasWsl) {
    Write-Host "  [FAIL] WSL is not installed. Please enable WSL2: wsl --install" -ForegroundColor Red
    exit 1
}

$distros = wsl --list --quiet 2>&1 | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
if ($distros -notcontains "Ubuntu") {
    Write-Host "  Ubuntu is not yet installed in WSL." -ForegroundColor Yellow
    Write-Host "  Installing Ubuntu in WSL2 (free, official Microsoft store distribution)..." -ForegroundColor Cyan
    if (-not $DryRun) {
        wsl --install -d Ubuntu --no-launch
    } else {
        Write-Host "  [DRY-RUN] Would run: wsl --install -d Ubuntu" -ForegroundColor Gray
    }
} else {
    Write-Host "  * Ubuntu distribution detected in WSL2." -ForegroundColor Green
}

$linuxPackages = @(
    "debootstrap",
    "mmdebstrap",
    "systemd-container",
    "cryptsetup-bin",
    "qemu-system-x86",
    "ovmf",
    "xorriso",
    "shellcheck",
    "yamllint",
    "build-essential",
    "python3-pip",
    "nodejs",
    "npm"
)

Write-Host "  Installing required Linux build packages inside WSL2 Ubuntu..." -ForegroundColor Cyan
Write-Host "  Packages: $($linuxPackages -join ', ')" -ForegroundColor Gray

if (-not $DryRun) {
    $pkgList = $linuxPackages -join " "
    $installCmd = "DEBIAN_FRONTEND=noninteractive apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends $pkgList && npm install -g markdownlint-cli2"
    wsl -d Ubuntu -u root bash -c $installCmd
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  [OK] Linux build packages successfully verified and installed in WSL2 Ubuntu." -ForegroundColor Green
    } else {
        Write-Host "  [FAIL] Failed to install packages in WSL2 Ubuntu (Exit Code: $LASTEXITCODE)." -ForegroundColor Red
        exit $LASTEXITCODE
    }
} else {
    Write-Host "  [DRY-RUN] Would run apt-get install inside WSL2 Ubuntu for required packages." -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "   Setup Completed Successfully (₹0 budget maintained)" -ForegroundColor Green
Write-Host "   Next: Run .\scripts\windows\check-build-environment.ps1" -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Cyan
