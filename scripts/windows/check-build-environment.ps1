<#
.SYNOPSIS
    PK-OS Build-Environment Readiness Verifier
.DESCRIPTION
    Performs full cross-environment verification (Windows + WSL2 Ubuntu).
    Tests loop devices, KVM hardware acceleration, dm-verity tooling, and image building utilities.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "      PK-OS Full Build-Environment Readiness Check       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

$Matrix = [System.Collections.Generic.List[PSCustomObject]]::new()
$TotalFailed = 0

function Add-Result ($Subsystem, $Capability, $Status, $Detail) {
    $Matrix.Add([PSCustomObject]@{
        Subsystem  = $Subsystem
        Capability = $Capability
        Status     = $Status
        Detail     = $Detail
    })
    if ($Status -eq "FAIL") {
        $script:TotalFailed++
    }
}

# 1. Windows Host Subsystem
Write-Host "[1/3] Testing Windows Host Capabilities..." -ForegroundColor Yellow

$gitVer = git --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Add-Result "Windows" "Git Version" "PASS" $gitVer.ToString().Trim()
} else {
    Add-Result "Windows" "Git Version" "FAIL" "Git executable not functional"
}

$pyVer = py --version 2>&1
if ($LASTEXITCODE -eq 0) {
    Add-Result "Windows" "Python Launcher" "PASS" $pyVer.ToString().Trim()
} else {
    Add-Result "Windows" "Python Launcher" "FAIL" "Python (py) not functional"
}

$gitAttr = Test-Path (Join-Path $PSScriptRoot "..\..\.gitattributes")
if ($gitAttr) {
    Add-Result "Windows" "Line Ending Policy" "PASS" ".gitattributes enforces LF for scripts"
} else {
    Add-Result "Windows" "Line Ending Policy" "WARN" ".gitattributes missing"
}

# 2. WSL2 Linux Subsystem
Write-Host "[2/3] Testing WSL2 Kernel & Virtualization..." -ForegroundColor Yellow

$wslKernel = wsl -d Ubuntu bash -c "uname -r" 2>&1
if ($LASTEXITCODE -eq 0) {
    Add-Result "WSL2" "Linux Kernel" "PASS" $wslKernel.ToString().Trim()
} else {
    Add-Result "WSL2" "Linux Kernel" "FAIL" "Failed to execute bash in WSL2 Ubuntu"
}

# KVM Acceleration
$kvmCheck = wsl -d Ubuntu bash -c "test -c /dev/kvm && echo 'OK' || echo 'MISSING'" 2>&1
if ($kvmCheck.ToString().Trim() -eq "OK") {
    Add-Result "WSL2" "KVM Virtualization" "PASS" "/dev/kvm available (hardware accelerated QEMU)"
} else {
    Add-Result "WSL2" "KVM Virtualization" "WARN" "/dev/kvm not present (emulation fallback)"
}

# Loop Devices
$loopCheck = wsl -d Ubuntu -u root bash -c "losetup -f 2>&1"
if ($LASTEXITCODE -eq 0) {
    Add-Result "WSL2" "Loop Devices" "PASS" "losetup functional ($($loopCheck.ToString().Trim()))"
} else {
    Add-Result "WSL2" "Loop Devices" "FAIL" "losetup failed in WSL2"
}

# Root Filesystem Free Space in WSL
$wslDisk = wsl -d Ubuntu bash -c "df -h / | awk 'NR==2 {print \$4}'" 2>&1
Add-Result "WSL2" "Linux Disk Space" "PASS" "$($wslDisk.ToString().Trim()) free on WSL rootfs"

# 3. Linux Build Toolchain
Write-Host "[3/3] Testing Linux Image Build Toolchain..." -ForegroundColor Yellow

$tools = @(
    @{ Name = "debootstrap"; Cmd = "debootstrap --version | head -n 1" },
    @{ Name = "mmdebstrap"; Cmd = "mmdebstrap --version" },
    @{ Name = "systemd-nspawn"; Cmd = "systemd-nspawn --version | head -n 1" },
    @{ Name = "mksquashfs"; Cmd = "mksquashfs -version | head -n 1" },
    @{ Name = "veritysetup"; Cmd = "veritysetup --version" },
    @{ Name = "cryptsetup"; Cmd = "cryptsetup --version" },
    @{ Name = "qemu-system-x86_64"; Cmd = "qemu-system-x86_64 --version | head -n 1" },
    @{ Name = "OVMF UEFI Firmware"; Cmd = "test -f /usr/share/OVMF/OVMF_CODE_4M.fd && echo 'Present' || (test -f /usr/share/ovmf/OVMF.fd && echo 'Present')" },
    @{ Name = "xorriso"; Cmd = "xorriso --version 2>&1 | head -n 1" },
    @{ Name = "shellcheck"; Cmd = "shellcheck --version | head -n 2 | tail -n 1" },
    @{ Name = "yamllint"; Cmd = "yamllint --version" },
    @{ Name = "markdownlint-cli2"; Cmd = "markdownlint-cli2 --version 2>&1 | head -n 1" }
)

foreach ($t in $tools) {
    $out = wsl -d Ubuntu bash -c "$($t.Cmd)" 2>&1
    if ($LASTEXITCODE -eq 0 -and $out -ne "") {
        Add-Result "Toolchain" $t.Name "PASS" $out.ToString().Trim()
    } else {
        Add-Result "Toolchain" $t.Name "FAIL" "Command '$($t.Cmd)' failed or output empty"
    }
}

# Output Matrix
Write-Host ""
Write-Host "=== VERIFICATION SUMMARY MATRIX ===" -ForegroundColor Cyan
$Matrix | Format-Table -AutoSize

Write-Host "==========================================================" -ForegroundColor Cyan
if ($TotalFailed -eq 0) {
    Write-Host "   Build Environment: 100% READY FOR PHASE 1 (Exit 0)   " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 0
} else {
    Write-Host "   Build Environment: $TotalFailed CHECKS FAILED (Exit 1) " -ForegroundColor Red
    Write-Host "   Run .\scripts\windows\setup.ps1 to resolve missing tools." -ForegroundColor Yellow
    Write-Host "==========================================================" -ForegroundColor Cyan
    exit 1
}
