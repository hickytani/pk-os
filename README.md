# PK-OS

> **An open-source, Linux-based operating system for x86_64 PCs and laptops.**

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-2E%20%E2%80%94%20Real%20Local%20AI%20%26%20Desktop-blue.svg)](#project-status)
[![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

---

## Project Status: Phase 2E — Real Local AI & End-to-End Desktop Functionality

PK-OS has reached **Phase 2E**, featuring a provider-neutral local inference boundary, ONNX Runtime integration with zero-cost deterministic fallback, end-to-end orchestration, atomic context engine persistence with auto-recovery, safe file discovery, live notification toasts, and verified graphical UEFI boot.

| Subsystem / Capability | Status | Verified Evidence |
|---|---|---|
| **Repository Foundation & CI** | ✅ DONE (Phase 0) | Strict linters, 32/32 structure checks passing |
| **Architecture Decision Records** | ✅ DONE (Phases 0–2E) | ADR-001 (Debian base), ADR-002 (Wayland Shell), ADR-003 (PK Intelligence), ADR-004 (cage compositor) |
| **Reproducible Minimal Rootfs** | ✅ DONE (Phase 1A) | `pk-os-rootfs.latest.tar.zst` (87 MB compressed) |
| **Bootable UEFI GPT Disk Image** | ✅ DONE (Phase 2E) | `pk-os-dev.raw` (2,600 MB, GPT: 256 MB FAT32 ESP + 2,344 MB ext4 Root) |
| **QEMU Automated Boot Test** | ✅ DONE (Phase 2E) | Serial console reaches login & graphical services active with KVM (Exit Code 0) |
| **Wayland Display (QEMU Visual)** | ✅ DONE (Phase 2E) | Framebuffer screendump (1280×800) verified with 97.6% palette match and Obsidian Dark styling |
| **Local Inference Boundary** | ✅ DONE (Phase 2E) | `InferenceProvider` interface with `ONNXInferenceProvider` (onnxruntime-1.31) & `DeterministicAssistantProvider` (<15ms latency, 0MB model cost) |
| **End-to-End Orchestrator** | ✅ DONE (Phase 2E) | `PKIntelligenceOrchestrator` combining prompt injection defense, policy gates, structured responses, and tool dispatch |
| **Evaluation Benchmark Suite** | ✅ DONE (Phase 2E) | `BenchmarkSuite` (v1.0.0 dataset): 100% intent accuracy, 100% injection defense, held-out test cases |
| **Persistent Context Engine** | ✅ DONE (Phase 2E) | Atomic JSON writes with schema versioning (`schema_version: 1`) and automatic corrupt-file backup & recovery |
| **Safe File Discovery Tool** | ✅ DONE (Phase 2E) | `list_directory` sandboxed inspection tool with traversal guards and truthful error reporting |
| **Desktop Shell & Toasts** | ✅ DONE (Phase 2E) | GTK3 Wayland surface with live notification toast cards, window manager dock, volume slider command dispatch |
| **Test Suite** | ✅ 160 passed / 0 failed | 160 unit/integration tests across shell, window manager, notifications, inference, orchestration, benchmarks, and context engine |
| **A/B Signed Atomic Updates** | 📋 PLANNED (Phase 4) | Dual-slot root, dm-verity, automatic rollback |
| **Bare-Metal Physical Installer** | 📋 PLANNED (Phase 7) | Live ISO installer with target drive protection |

---

## System Architecture

```text
+-------------------------------------------------------------------------+
|                               FIRMWARE                                  |
|                 UEFI x86_64 Firmware (OVMF / Secure Boot)               |
+------------------------------------+------------------------------------+
                                     | Loads /EFI/systemd/systemd-bootx64.efi
                                     v
+-------------------------------------------------------------------------+
|                             BOOTLOADER                                  |
|                 systemd-boot (UEFI BLS specification)                   |
|                   Kernel: vmlinuz-6.1.0-50-amd64                        |
|                   Initramfs: initrd.img-6.1.0-50-amd64                  |
+------------------------------------+------------------------------------+
                                     | Mounts root=LABEL=PKOS_ROOT
                                     v
+-------------------------------------------------------------------------+
|                             CORE OS LAYER                               |
|                systemd (PID 1) / systemd-journald / udev                |
|                    Serial Console on ttyS0 & tty0                       |
+------------------+-----------------------------------+------------------+
                   |                                   |
                   v                                   v
+------------------------------------+ +----------------------------------+
|           DESKTOP SHELL            | |         PK INTELLIGENCE          |
|    wlr-layer-shell UI Process      | |    Local-First Voice Assistant   |
|                                    | |                                  |
| - Top Panel (Exclusive 36px)       | | - Offline Silero-VAD & Wake-Word |
| - Application Launcher Modal       | | - whisper.cpp Local Speech-to-Text|
| - Obsidian Mathematical Tokens     | | - GBNF Quantized Intent Planning |
| - Responsive (Desktop & Mobile)    | | - Capability-Gated Tool Registry |
| - Voice HUD Overlay Card           | | - SHA-256 Audit Permission Ledger|
+------------------+-----------------+ +-----------------+----------------+
                   |                                     |
                   +<--- Unix Domain Socket IPC (JSON-RPC) >+
```

---

## What Is PK-OS?

PK-OS is a real, independent Linux operating system distribution engineered from the ground up:

- **Primary Target**: x86_64 personal computers and laptops.
- **Future Vision**: Seamless mobile companion devices via an adaptive UI layer and an AOSP-based port.
- **Zero Cost (₹0 Budget)**: 100% free and open-source tooling (Debian 12 base, Linux LTS, QEMU/KVM, Wayland, Python 3). Zero paid subscriptions or cloud dependencies.
- **True Privacy**: PK Intelligence operates strictly on-device without cloud API calls, telemetry, or hidden audio transmission.
- **Robust Security**: Capability-gated tool execution requiring explicit user approval for consequential actions (file deletion, network alterations, system modifications).

---

## Phase 2 Boot Verification & Disk Artifact Evidence

The verified bootable UEFI GPT raw image is located at:

- **Local Windows Path**: `build/output/pk-os-dev.raw` (`build\output\pk-os-dev.latest.raw`)
- **Local WSL2 Path**: `/mnt/c/Users/prasu/Downloads/pk-os/build/output/pk-os-dev.raw`
- **File Byte Size**: `2,726,297,600` bytes (2,600 MB)
- **Immutable SHA-256**: `1203e1599507c8ccdeb3a30ec773059f46380d49c443e4d17ed1054ebb916714`
- **Latest Commit**: `58f5f3b` on branch `feat/phase2e-local-ai-and-desktop`
- **Partition Table (GPT)**:
  - **Partition 1 (`ESP`)**: 256 MB FAT32 (`LABEL="PKOS_ESP"`), systemd-boot, Linux kernel `6.1.0-50-amd64`, initramfs, and BLS entry `pkos.conf`.
  - **Partition 2 (`PKOS_ROOT`)**: 2,344 MB ext4 (`LABEL="PKOS_ROOT"`), Debian 12 Bookworm, cage Wayland kiosk compositor, GTK3 PK-OS desktop shell (`shell/src/ui/gui.py`), `pk-intelligenced` daemon, notifications, window manager, and context engine.
- **QEMU Automated Boot Checkpoints**:

```text
==========================================================
                 BOOT TEST AUDIT REPORT                   
==========================================================
Audit Checkpoints:
  [PASS] Bootloader: systemd-boot detected
  [PASS] Kernel: [ 0.000000] Linux version 6.1.0-50-amd64 (Debian 6.1.176-1)
  [PASS] Init System: systemd started in system mode
  [PASS] Systemd Targets: 37 targets reached
  [PASS] Userspace Target: Login prompt reached (pk-os login:)
  [PASS] Graphical Compositor: pk-session.service detected
  [PASS] Framebuffer Capture: 1280x800, 97.7% Obsidian Dark palette match
==========================================================
                ALL BOOT GATES PASSED (Exit Code 0)        
==========================================================
```

Serial console output is archived in [build/output/qemu-boot.log](build/output/qemu-boot.log).
Graphical framebuffer capture is archived in [build/output/qemu-graphical-boot-interactive.png](build/output/qemu-graphical-boot-interactive.png).

---

## Interactive Desktop Preview & Safe Exit

To see and interact with the live graphical desktop on Windows:

### 1-Click Launch from Windows PowerShell

```powershell
.\scripts\windows\preview.ps1
```

*Starts QEMU with hardware KVM acceleration, verifies endpoint reachability, and automatically opens `http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale` in your Windows browser.*

### Launch from Linux / WSL2

```bash
./scripts/run-qemu.sh --graphical --preview --memory=1024
```

*Open `http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale` in any browser or connect native VNC to `127.0.0.1:5999`.*

### Safe Exit Procedures

1. **Guest Graceful Shutdown**: Click **Shut Down PK-OS** in the top-right panel or in **Workspace 3 (Settings)**. This cleanly flushes filesystem caches, stops all systemd services, and powers off the virtual machine.
2. **Host Terminal Exit**: Press `Ctrl-C` in the PowerShell/WSL terminal running QEMU to terminate the VM safely without affecting the Windows host.

---

## Phase 2: Desktop Shell Foundation

Located in [`shell/`](shell/):

- **Design System Tokens** ([shell/src/tokens/](shell/src/tokens/)): Mathematical tokens for colors, spacing (4px grid), typography, radii, and motion. Supports `@media (prefers-reduced-motion: reduce)` and WCAG AAA contrast (14:1 primary text).
- **Session Lifecycle Manager** ([shell/src/session/lifecycle.py](shell/src/session/lifecycle.py)): Strict state machine (`INIT` -> `READY` -> `ACTIVE` -> `SUSPENDED` -> `TERMINATED`) and configuration validator.
- **Adaptive Layout Calculator** ([shell/src/ui/layout.py](shell/src/ui/layout.py)): Geometry engine calculating layer-shell coordinates for desktop (`>=1024px`) and mobile/touch (`<1024px`) displays.
- **UI Surface Generator** ([shell/src/ui/surface.py](shell/src/ui/surface.py)): Accessible, contrast-validated DOM structure for panels, workspace switchers, and the Voice HUD overlay.
- **Interactive GTK3 Shell** ([shell/src/ui/gui.py](shell/src/ui/gui.py)): Native Wayland GTK3 client window running under `cage(1)` with 3 virtual workspaces, live notification toasts, dock taskbar, and shutdown lifecycle controls.
- **Test Suite**: 24 unit tests passing 100% (`shell/tests/`).

---

## Parallel Track: PK Intelligence ("Hey PK") Foundation

Located in [`intelligence/`](intelligence/):

- **Local Inference Boundary** ([intelligence/src/inference.py](intelligence/src/inference.py)): Provider-neutral boundary with `DeterministicAssistantProvider` (<15ms latency, 0MB model overhead) and `ONNXInferenceProvider` (`onnxruntime-1.31.0`).
- **End-to-End Orchestrator** ([intelligence/src/orchestration.py](intelligence/src/orchestration.py)): Classifies and executes queries into typed decisions (`CONVERSATIONAL`, `TOOL_EXECUTION`, `CONFIRMATION_REQUIRED`, `ERROR`) with prompt injection defense.
- **Hardened Context Engine** ([intelligence/src/context.py](intelligence/src/context.py)): Atomic JSON writes, schema versioning (`schema_version: 1`), and automatic corrupt-file backup & recovery.
- **Deterministic Tool Registry** ([intelligence/src/tools.py](intelligence/src/tools.py)): Sandboxed tools (`launch_application`, `get_system_status`, `adjust_setting`, `delete_path`, `list_directory`) with path traversal guards.
- **Permission & Safety Ledger** ([intelligence/src/security.py](intelligence/src/security.py)): Capability matrix (`READ_ONLY`, `SYSTEM_CONFIG`, `CONSEQUENTIAL`). Consequential actions raise an interactive approval interrupt. Audit records are cryptographically chained with SHA-256 hashes.
- **Evaluation Benchmark Suite** ([intelligence/src/benchmark.py](intelligence/src/benchmark.py)):
  - Intent Accuracy: 12/12 (100.0%)
  - Prompt Injection Defense: 3/3 (100.0% rejected)
  - Consequential Interceptions: 1/1 (100% intercepted)
  - Orchestration Decision Accuracy: 6/6 (100.0%)

---

## Quickstart & Developer Workflow

### Windows 11 (PowerShell Workflow)

```powershell
# 1. Audit Windows and WSL prerequisites
.\scripts\windows\check-prereqs.ps1

# 2. Automated setup (installs missing packages in WSL2 Ubuntu)
.\scripts\windows\setup.ps1

# 3. Check environment readiness
.\scripts\windows\check-build-environment.ps1

# 4. Launch interactive desktop preview in your browser
.\scripts\windows\preview.ps1

# 5. Run repository validation, linters, and the automated QEMU boot test
.\scripts\windows\test.ps1 -BootTest -GraphicalBoot
```

### Linux / WSL2 (Bash Workflow)

```bash
# 1. Verify prerequisites & run linters
./scripts/check-prereqs.sh
./scripts/lint.sh

# 2. Build bootable raw disk image (requires root)
sudo python3 scripts/assemble_phase2e_disk.py

# 3. Launch interactive desktop preview (browser VNC on port 6080)
./scripts/run-qemu.sh --graphical --preview --memory=1024

# 4. Run automated QEMU UEFI boot smoke test (KVM accelerated)
./scripts/run-qemu.sh --graphical --test --timeout=60

# 5. Run full test suite (166 tests)
python3 -m pytest shell/tests intelligence/tests -v
```

---

## Repository Structure

```text
pk-os/
+-- build/
|   +-- manifests/             # Minimal package manifests (base, kernel)
|   +-- output/                # Local build artifacts (git-ignored)
+-- docs/
|   +-- adr/                   # Architecture Decision Records (ADR-001, ADR-002, ADR-003)
|   +-- architecture/          # Overview, Roadmap, Shell, Intelligence, IPC
|   +-- development/           # Developer setup and workflow guides
|   +-- security/              # Threat model, invariants, audit policies
|   +-- testing/               # Test strategy, failure-mode matrix
|   +-- release/               # Release process, hardware compatibility
+-- intelligence/              # PK Intelligence local agent foundation
|   +-- benchmarks/            # Reproducible eval harness & metrics
|   +-- data/v1/               # Versioned intent evaluation datasets
|   +-- src/                   # Interfaces, tools, security ledger, intent planner
|   +-- tests/                 # Unit test suite
+-- scripts/                   # Linux build, lint, and VM runner scripts
|   +-- windows/               # Windows PowerShell automation wrappers
+-- shell/                     # PK-OS Desktop Shell vertical slice
|   +-- src/tokens/            # Design tokens (JSON, CSS)
|   +-- src/session/           # Session lifecycle state machine & config
|   +-- src/ui/                # Adaptive layout engine & preview surface
|   +-- tests/                 # Shell unit tests
+-- README.md
+-- CONTRIBUTING.md
+-- SECURITY.md
+-- LICENSE
```

---

## License & Community

- **License**: GNU General Public License v2.0. See [LICENSE](LICENSE).
- **Issues**: [GitHub Issues](https://github.com/hickytani/pk-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/hickytani/pk-os/discussions)
