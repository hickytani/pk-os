<#
.SYNOPSIS
    PK-OS Windows Interactive Desktop Preview Runner
.DESCRIPTION
    Launches PK-OS in QEMU via WSL2 with zero-install browser-based VNC interaction.
    Allows inspecting and navigating the real PK-OS graphical desktop directly from
    Windows browsers (Edge, Chrome, Firefox) with verified safe exit paths.
#>

[CmdletBinding()]
param(
    [string]$DiskImage = "",
    [int]$MemoryMB = 1024,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "     PK-OS Interactive Desktop Preview (Windows)          " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$driveLetter = $repoRoot.Substring(0, 1).ToLower()
$wslPath = "/mnt/" + $driveLetter + $repoRoot.Substring(2).Replace("\", "/")

if (-not $DiskImage) {
    $DiskImage = Join-Path $repoRoot "build\output\pk-os-dev.raw"
}

if (-not (Test-Path $DiskImage)) {
    Write-Host "ERROR: Disk image not found at '$DiskImage'" -ForegroundColor Red
    Write-Host "Run 'wsl -d Ubuntu -u root bash -c `"python3 /mnt/c/.../scripts/assemble_phase2e_disk.py`"' first." -ForegroundColor Yellow
    exit 1
}

$imgSizeMB = [math]::Round((Get-Item $DiskImage).Length / 1MB, 2)
Write-Host "  * Disk Image:  $DiskImage ($imgSizeMB MB)" -ForegroundColor Green
Write-Host "  * VM Memory:   $MemoryMB MB (Allocated safely from 16 GB host)" -ForegroundColor Green
Write-Host "  * Web Display: http://localhost:6080/vnc.html?autoconnect=true&resize=scale" -ForegroundColor Green
Write-Host ""

Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "           SAFE EXIT INSTRUCTIONS TO RETURN TO WINDOWS    " -ForegroundColor Yellow
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host "  1. GUEST SHUTDOWN (Recommended):" -ForegroundColor White
Write-Host "     Inside the PK-OS preview window, click 'Shut Down PK-OS' in the" -ForegroundColor White
Write-Host "     top status bar or in Workspace 3 (Settings)." -ForegroundColor White
Write-Host "     This flushes filesystem caches, cleanly stops services, and powers off the VM." -ForegroundColor White
Write-Host ""
Write-Host "  2. HOST TERMINAL EXIT:" -ForegroundColor White
Write-Host "     In this PowerShell terminal, press Ctrl-C to terminate QEMU safely." -ForegroundColor White
Write-Host "     Windows host OS and other applications will not be affected." -ForegroundColor White
Write-Host "==========================================================" -ForegroundColor Yellow
Write-Host ""

# Open browser if requested
if (-not $NoBrowser) {
    Start-Job -ScriptBlock {
        Start-Sleep -Seconds 4
        Start-Process "http://localhost:6080/vnc.html?autoconnect=true&resize=scale"
    } | Out-Null
}

# Launch QEMU inside WSL2
$cmd = "cd '$wslPath' && ./scripts/run-qemu.sh --graphical --preview --memory=$MemoryMB"
wsl -d Ubuntu bash -c "$cmd"
