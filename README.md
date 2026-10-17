# PK-OS

> **An open-source, Linux-based operating system for x86_64 PCs and laptops.**

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-2A%20%E2%80%94%20Graphical%20Session%20Runtime-blue.svg)](#project-status)
[![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

---

## Project Status: Phase 2A — Graphical Session Runtime

PK-OS has completed **Phase 1** (bootable UEFI image, QEMU-verified userspace login) and is actively delivering **Phase 2A** (real Wayland graphical session). The parallel **PK Intelligence** workstream now has a production-grade local daemon with Unix socket IPC.

| Subsystem / Capability | Status | Verified Evidence |
|---|---|---|
| **Repository Foundation & CI** | ✅ DONE (Phase 0) | Strict linters, 32/32 structure checks passing |
| **Architecture Decision Records** | ✅ DONE (Phases 0–2A) | ADR-001 (Debian base), ADR-002 (Wayland Shell), ADR-003 (PK Intelligence), ADR-004 (cage compositor) |
| **Reproducible Minimal Rootfs** | ✅ DONE (Phase 1A) | `pk-os-rootfs.latest.tar.zst` (87 MB compressed) |
| **Bootable UEFI GPT Disk Image** | ✅ DONE (Phase 1C) | `pk-os-dev.raw` (1,500 MB, GPT: 128 MB FAT32 ESP + 1,370 MB ext4 Root) |
| **QEMU Automated Boot Test** | ✅ DONE (Phase 1D) | Serial console reaches `pk-os login:` with KVM (Exit Code 0) |
| **Design Tokens & Layout Engine** | ✅ DONE (Phase 2 Slice) | Obsidian dark theme, 4px grid, WCAG AAA contrast, adaptive FormFactor |
| **cage Compositor Manager** | ✅ DONE (Phase 2A) | `CompositorManager` with state machine, socket-ready poll, virtio-gpu/Mesa env; 22 unit tests |
| **Shell Launcher & Session FSM** | ✅ DONE (Phase 2A) | `shell/launcher.py` integrates ShellSession, LayoutEngine, signal-driven loop |
| **systemd Graphical Services** | ✅ DONE (Phase 2A) | `pk-session.service` + `pk-intelligenced.service` with full security hardening |
| **Graphical Package Manifest** | ✅ DONE (Phase 2A) | `build/manifests/graphical-pkgs.list`: cage, Mesa Vulkan, PipeWire, Python3 |
| **pk-intelligenced Daemon** | ✅ DONE (Phase 2A) | Unix socket IPC, IntentPlanner→SecurityLedger pipeline, SHA-256 audit chain |
| **Test Suite** | ✅ 53 passed / 7 skipped (0 failed) | Shell compositor, layout, lifecycle, tokens; intelligence dispatch, security, tools |
| **Wayland Display (QEMU Visual)** | 🔄 IN PROGRESS (Phase 2B) | virtio-gpu boot-to-panel verification in QEMU |
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

## Phase 1 Boot Verification Evidence

The bootable raw image is assembled and validated via [scripts/run-qemu.sh](scripts/run-qemu.sh):

- **Image Path**: `build/output/pk-os-dev.raw`
- **Byte Size**: `1,572,864,000` bytes (1,500 MB)
- **Immutable SHA-256**: `c441a8491c2c7f50bacf32ab7940e0dbffcbb87c741991ece412152c8a9561b0`
- **Partition Table (GPT)**:
  - Partition 1 (`ESP`): 128 MB FAT32 (`LABEL="PKOS_ESP"`) with `systemd-boot`, kernel `6.1.0-50-amd64`, initramfs, and BLS entry `pkos.conf`.
  - Partition 2 (`PKOS_ROOT`): 1,370 MB ext4 (`LABEL="PKOS_ROOT"`) with Debian 12 minimal rootfs, systemd init, and serial login getty.
- **QEMU Automated Boot Checkpoints**:

```text
==========================================================
                 BOOT TEST AUDIT REPORT                   
==========================================================
Audit Checkpoints:
  [PASS] Bootloader: systemd-boot detected
  [PASS] Kernel: [ 0.000000] Linux version 6.1.0-50-amd64 (Debian 6.1.176-1)
  [PASS] Init System: systemd started in system mode
  [PASS] Systemd Targets: 32 targets reached
  [PASS] Userspace Target: Login prompt reached (pk-os login:)
==========================================================
               ALL BOOT GATES PASSED (Exit Code 0)        
==========================================================
```

Serial console output is archived in [build/output/qemu-boot.log](build/output/qemu-boot.log).

---

## Phase 2: Desktop Shell Foundation

Located in [`shell/`](shell/):

- **Design System Tokens** ([shell/src/tokens/](shell/src/tokens/)): Mathematical tokens for colors, spacing (4px grid), typography, radii, and motion. Supports `@media (prefers-reduced-motion: reduce)` and WCAG AAA contrast (14:1 primary text).
- **Session Lifecycle Manager** ([shell/src/session/lifecycle.py](shell/src/session/lifecycle.py)): Strict state machine (`INIT` -> `READY` -> `ACTIVE` -> `SUSPENDED` -> `TERMINATED`) and configuration validator.
- **Adaptive Layout Calculator** ([shell/src/ui/layout.py](shell/src/ui/layout.py)): Geometry engine calculating layer-shell coordinates for desktop (`>=1024px`) and mobile/touch (`<1024px`) displays.
- **UI Surface Generator** ([shell/src/ui/surface.py](shell/src/ui/surface.py)): Accessible, contrast-validated DOM structure for panels, workspace switchers, and the Voice HUD overlay.
- **Test Suite**: 14 unit tests passing 100% (`shell/tests/`).

---

## Parallel Track: PK Intelligence ("Hey PK") Foundation

Located in [`intelligence/`](intelligence/):

- **Pipeline Interfaces** ([intelligence/src/interfaces.py](intelligence/src/interfaces.py)): Modular abstractions for audio capture, VAD gating, wake-word detection, speech-to-text, intent planning, typed tools, and permission ledgers.
- **Deterministic Tool Registry** ([intelligence/src/tools.py](intelligence/src/tools.py)): Sandboxed tools (`launch_application`, `get_system_status`, `adjust_setting`, `delete_path`) with JSON schema validation. Raw shell execution is prohibited.
- **Permission & Safety Ledger** ([intelligence/src/security.py](intelligence/src/security.py)): Capability matrix (`READ_ONLY`, `SYSTEM_CONFIG`, `CONSEQUENTIAL`). Consequential actions raise an interactive approval interrupt. Audit records are cryptographically chained with SHA-256 hashes.
- **Intent Planner & Injection Defense** ([intelligence/src/intent.py](intelligence/src/intent.py)): Parses natural language into typed tasks and automatically rejects adversarial prompt injections (`rm -rf`, `curl | sh`, `eval()`).
- **Benchmark & Evaluation Harness** ([intelligence/benchmarks/eval_harness.py](intelligence/benchmarks/eval_harness.py)):
  - Intent Accuracy: 12/12 (100.0%)
  - Prompt Injection Defense: 3/3 (100.0% rejected)
  - Consequential Interceptions: 1/1 (100% intercepted)
  - Average Parser Latency: 0.040 ms

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

# 4. Run repository validation, linters, and the automated QEMU boot test
.\scripts\windows\test.ps1 -BootTest

# 5. Dispatch image build target
.\scripts\windows\build.ps1 -Target all
```

### Linux / WSL2 (Bash Workflow)

```bash
# 1. Verify prerequisites & run linters
./scripts/check-prereqs.sh
./scripts/lint.sh

# 2. Build bootable raw disk image (requires root)
sudo ./scripts/build-disk-image.sh

# 3. Run automated QEMU UEFI boot smoke test (KVM accelerated)
./scripts/run-qemu.sh --test --timeout=90

# 4. Run shell test suite
python3 -m unittest discover -s shell/tests -p "test_*.py"

# 5. Run PK Intelligence unit tests and benchmark harness
python3 -m unittest discover -s intelligence/tests -p "test_*.py"
python3 intelligence/benchmarks/eval_harness.py
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
