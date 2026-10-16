# PK-OS Developer Setup & Toolchain Guide

**Status**: Verified Windows-First Setup with Zero-Cost (₹0) Linux Build Engine via WSL2.

---

## 1. Architecture & Design Principles

PK-OS is developed on Windows 11 as the primary developer workstation, delegating hermetic Linux OS image building, loopback mounting, and KVM virtualization directly into a lightweight, free WSL2 Ubuntu environment.

### Core Principles

- **Zero Cost (₹0 Budget)**: Zero paid software, zero paid VM hypervisors, zero Docker Desktop licensing requirements, and zero commercial cloud runners.
- **Native Windows Workflow**: Edit code in VS Code, run Git in PowerShell/Windows Terminal, and execute build/test operations directly via PowerShell scripts.
- **Isolated Linux Engine**: Uses native WSL2 with hardware virtualization (`/dev/kvm`) and block device loop mounts (`/dev/loop-control`).

---

## 2. Quickstart: Windows-First Workflow

All setup and verification operations can be executed from a standard PowerShell prompt at the repository root.

### Step 1: Audit Prerequisites

Inspect system hardware, virtualization state, and installed developer tools:

```powershell
.\scripts\windows\check-prereqs.ps1
```

### Step 2: Automated Setup (Zero Cost)

Automatically configure missing Windows tools (via `winget`) and install required build packages inside WSL2 Ubuntu:

```powershell
# Run setup (safe, non-destructive, ₹0 budget)
.\scripts\windows\setup.ps1

# Dry-run mode to inspect actions without installing:
.\scripts\windows\setup.ps1 -DryRun
```

### Step 3: Verify Build Environment Readiness

Run the end-to-end build environment capability matrix across both Windows and WSL2:

```powershell
.\scripts\windows\check-build-environment.ps1
```

### Step 4: Run Tests & Linters

Execute the complete verification suite (Markdown, YAML, ShellCheck, and structure validation):

```powershell
.\scripts\windows\test.ps1
```

### Step 5: Dispatch Build (Phase 1+)

Invoke the Linux image build pipeline via the Windows dispatcher:

```powershell
.\scripts\windows\build.ps1 -Target all
```

---

## 3. Toolchain & Package Specifications

### Windows Host Subsystem

| Tool | Purpose | Source / Path | License / Cost |
|---|---|---|---|
| **Git** | Version control & line endings | `C:\Program Files\Git\cmd\git.exe` | GPL-2.0 (Free) |
| **Python 3** | Scripting & utility automation | `C:\Users\...\py.exe` | PSF (Free) |
| **VS Code** | Code editor & IDE | `code.cmd` | Free |
| **Windows Terminal** | PowerShell / WSL terminal | `wt.exe` | MIT (Free) |
| **Winget** | Official Windows package manager | `winget.exe` | MIT (Free) |
| **WSL2** | Native Linux kernel subsystem | `C:\Windows\system32\wsl.exe` | Included in Windows |

### WSL2 Linux Build Engine (Ubuntu 24.04 LTS)

| Package | Purpose | Verification Command |
|---|---|---|
| `debootstrap` / `mmdebstrap` | Debian minimal rootfs bootstrapping | `mmdebstrap --version` |
| `systemd-container` | `systemd-nspawn` container chroot | `systemd-nspawn --version` |
| `mksquashfs` | Read-only compressed filesystem creation | `mksquashfs -version` |
| `cryptsetup-bin` | `veritysetup` (dm-verity) & LUKS2 | `veritysetup --version` |
| `qemu-system-x86` | Headless x86_64 virtualization | `qemu-system-x86_64 --version` |
| `ovmf` | UEFI Secure Boot virtual firmware | `test -f /usr/share/OVMF/OVMF_CODE_4M.fd` |
| `xorriso` | Bootable ISO image creation | `xorriso --version` |
| `shellcheck` | Static analysis for shell scripts | `shellcheck --version` |
| `yamllint` | YAML formatting & schema validation | `yamllint --version` |
| `markdownlint-cli2` | Documentation standards validation | `markdownlint-cli2 --version` |

---

## 4. Hardware Virtualization & WSL2 Verification

PK-OS requires hardware virtualization for fast headless testing and block devices for image partitioning.

### Verifying KVM in WSL2

Execute inside WSL2 to confirm KVM acceleration is active:

```bash
ls -l /dev/kvm
# Expected output: crw-rw---- 1 root kvm 10, 232 ... /dev/kvm
```

### Verifying Loop Devices in WSL2

Confirm loop device control is present:

```bash
sudo losetup -f
# Expected output: /dev/loop0 (or next free loop device)
```

---

## 5. Linux-Native Workflow (Alternative)

If you are working directly inside a Linux host or inside a WSL2 bash shell:

```bash
# 1. Install prerequisites (Debian/Ubuntu)
sudo apt-get update && sudo apt-get install -y \
  git python3 python3-pip debootstrap mmdebstrap systemd-container \
  cryptsetup-bin qemu-system-x86 ovmf xorriso shellcheck yamllint \
  nodejs npm

sudo npm install -g markdownlint-cli2@0.13.0

# 2. Check prerequisites
./scripts/check-prereqs.sh

# 3. Run validation suite
./scripts/lint.sh
```
