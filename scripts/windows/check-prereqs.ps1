<#
.SYNOPSIS
    PK-OS Windows Prerequisites Inspector
.DESCRIPTION
    Audits Windows-side tools, virtualization support, and WSL2 availability
    without requiring administrator privileges or modifying the machine.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = 'Continue'

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         PK-OS Windows Prerequisites Audit               " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$AllPassed = $true

# 1. System Info
Write-Host "[1/5] Checking Operating System & Architecture..." -ForegroundColor Yellow
$os = Get-CimInstance Win32_OperatingSystem
$proc = Get-CimInstance Win32_Processor | Select-Object -First 1

$totalRamGB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
$freeRamGB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
$driveC = Get-PSDrive -Name C -PSProvider FileSystem
$freeDiskGB = [math]::Round($driveC.Free / 1GB, 2)

Write-Host "  * OS: $($os.Caption) ($($os.Version), Build $($os.BuildNumber), $($os.OSArchitecture))"
Write-Host "  * CPU: $($proc.Name)"
Write-Host "  * Memory: $totalRamGB GB Total ($freeRamGB GB Free)"
Write-Host "  * Disk C: $freeDiskGB GB Free"

if ($totalRamGB -lt 8) {
    Write-Host "  [WARN] Total RAM is under 8 GB. Minimum 8 GB recommended for image builds." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] RAM meets requirements (>= 8 GB)" -ForegroundColor Green
}

if ($freeDiskGB -lt 30) {
    Write-Host "  [WARN] Free disk space is under 30 GB. OS image builds require >= 30 GB." -ForegroundColor Yellow
} else {
    Write-Host "  [OK] Disk space meets requirements (>= 30 GB)" -ForegroundColor Green
}

# 2. Administrative Status
Write-Host "`n[2/5] Checking User Privileges..." -ForegroundColor Yellow
$isAdmin = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if ($isAdmin) {
    Write-Host "  * Session: Administrator (Elevated)" -ForegroundColor Cyan
} else {
    Write-Host "  * Session: Standard User (Non-Elevated, Safe Default)" -ForegroundColor Gray
}

# 3. Windows Core Tools
Write-Host "`n[3/5] Checking Windows Development Tools..." -ForegroundColor Yellow

function Test-Tool ($name, $command, [string]$versionFlag = '--version') {
    $cmd = Get-Command $command -ErrorAction SilentlyContinue
    if (-not $cmd) {
        $winApp = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps\$command.exe"
        if (Test-Path $winApp) {
            $cmd = [PSCustomObject]@{ Source = $winApp }
        }
    }
    if ($cmd) {
        if ($name -eq "Windows Terminal") {
            $appx = Get-AppxPackage *WindowsTerminal* -ErrorAction SilentlyContinue | Select-Object -First 1
            $v = if ($appx) { $appx.Version } else { "Installed" }
            Write-Host ("  [OK] {0,-18} : {1} (Version {2})" -f $name, $cmd.Source, $v) -ForegroundColor Green
            return $true
        }
        try {
            $ver = & $cmd.Source $versionFlag 2>&1 | Select-Object -First 1
            Write-Host ("  [OK] {0,-18} : {1} ({2})" -f $name, $cmd.Source, $ver.ToString().Trim()) -ForegroundColor Green
            return $true
        } catch {
            Write-Host ("  [WARN] {0,-18} : Found at {1} but failed to report version" -f $name, $cmd.Source) -ForegroundColor Yellow
            return $true
        }
    } else {
        Write-Host ("  [FAIL] {0,-18} : Not found in PATH or WindowsApps" -f $name) -ForegroundColor Red
        return $false
    }
}

$hasGit = Test-Tool "Git" "git" "--version"
$hasPy = Test-Tool "Python Launcher" "py" "--version"
$hasCode = Test-Tool "VS Code" "code" "--version"
$hasWT = Test-Tool "Windows Terminal" "wt" ""
$hasWinget = Test-Tool "Winget" "winget" "--version"

if (-not $hasGit) { $AllPassed = $false }
if (-not $hasPy) { $AllPassed = $false }

# 4. WSL & Virtualization
Write-Host "`n[4/5] Checking WSL2 Environment..." -ForegroundColor Yellow
$hasWsl = Get-Command "wsl" -ErrorAction SilentlyContinue
if ($hasWsl) {
    Write-Host "  [OK] WSL executable: $($hasWsl.Source)" -ForegroundColor Green
    try {
        $distros = wsl --list --quiet 2>&1 | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" }
        $hasUbuntu = $distros -contains "Ubuntu"
        if ($hasUbuntu) {
            $uVer = (wsl -d Ubuntu cat /etc/issue 2>&1 | Select-Object -First 1).ToString().Replace('\n \l', '').Trim()
            Write-Host "  [OK] Ubuntu distribution detected: $uVer" -ForegroundColor Green
        } else {
            Write-Host "  [WARN] Ubuntu distribution not found in WSL2. Found: $($distros -join ', ')" -ForegroundColor Yellow
            $AllPassed = $false
        }
    } catch {
        Write-Host "  [WARN] Failed to inspect WSL status: $_" -ForegroundColor Yellow
    }
} else {
    Write-Host "  [FAIL] WSL is not installed. WSL2 is required for Linux build operations." -ForegroundColor Red
    $AllPassed = $false
}

# 5. Optional Free Tooling
Write-Host "`n[5/5] Checking Container & Virtualization Tooling..." -ForegroundColor Yellow
$hasDocker = Get-Command "docker" -ErrorAction SilentlyContinue
if ($hasDocker) {
    Write-Host "  * Docker CLI: Available at $($hasDocker.Source)" -ForegroundColor Gray
} else {
    Write-Host "  * Docker CLI: Not installed (optional, zero-cost podman/wsl used instead)" -ForegroundColor Gray
}

$hasPodman = Get-Command "podman" -ErrorAction SilentlyContinue
if ($hasPodman) {
    Write-Host "  * Podman: Available at $($hasPodman.Source)" -ForegroundColor Green
} else {
    Write-Host "  * Podman: Not installed on Windows (Linux podman inside WSL is supported)" -ForegroundColor Gray
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
if ($AllPassed) {
    Write-Host "   Prerequisites Status: READY (Exit Code 0)" -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "   Prerequisites Status: MISSING REQUIRED TOOLS (Exit Code 1)" -ForegroundColor Red
    Write-Host "   Run .\scripts\windows\setup.ps1 to install missing prerequisites." -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 1
}
