# PK-OS

> **An open-source, Linux-based operating system for x86_64 PCs and laptops.**

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-2E%20%E2%80%94%20Real%20Local%20AI%20%26%20Desktop-blue.svg)](#project-status)
[![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

---

## Project Status: Development Prototype (current-source evidence: 2026-11-01)

PK-OS is an in-progress Linux desktop and local-assistant prototype. A fresh
image built from the current guest sources booted to the GTK/Cage session in
QEMU snapshot mode on 2026-11-01. Controllable RFB keyboard and QMP pointer
input verified workspace navigation, a Settings toggle, keyboard focus,
guest-sourced diagnostics, deterministic Hey PK behavior, an explicit
system-change approval prompt and the honest missing-backend failure, and
guest-initiated shutdown. The runner exited with status 0 after systemd reached
`poweroff.target`; the raw image hash was unchanged. Acceptance remains partial:
Cage logs repeated output-test failures, the allowlisted Terminal package is
missing, noVNC browser-driven input is unverified, and brightness has no real
backend. See the [acceptance matrix](docs/testing/ACCEPTANCE-MATRIX.md) for
evidence and limitations.

| Subsystem / Capability | Current status | Verified evidence and limits |
|---|---|---|
| Current-source image | Built and booted | `build/output/verification-20261101-current/pk-os-current.raw`; SHA-256 `d8770ee3a1fb6d2be44918f278a66590d2286d393a445746496fd81d1fc4f8a5`. |
| GTK desktop and direct guest interaction | Partial, current image | Fresh 1280×800 guest captures under `build/output/verification-20261101-current/ui/`; workspace switching, settings, keyboard focus, guest diagnostics, assistant, approval/error, and guest poweroff were directly driven and captured. Cage output-test failures remain in the guest log. |
| Cage and window management | Limited | Cage is single-client; Main, Code, and Settings are shell views, not independent compositor workspaces. |
| System status | Deterministic query verified | Current-image Hey PK query returned guest uptime, memory, disk, and OS values; no LLM inference. |
| Application launching | Blocked in preview | Direct `launch terminal` request reported `pk-terminal` is not installed; launcher/window lifecycle is incomplete. |
| Settings controls | Incomplete | Current image showed unavailable brightness backend; explicit approval reached the tool and returned a missing verified guest backend error. |
| Power actions | Guest shutdown verified | Current-image confirmation prompt was accepted; serial log reached `poweroff.target` and `reboot: Power down`; QEMU exited 0. |
| Hey PK orchestration | Deterministic prototype | Benchmark: 14/14 intent, 14/14 policy, 2/2 adversarial rejections; this is not neural inference. |
| Local language model | Not integrated | ONNX text generation is explicitly unsupported; no weights or successful neural inference exist. |
| Voice pipeline | Planned | Wake word, microphone capture, speech recognition, and speech output are not active. |
| Assistant response dataset | Validated, limited | v2 has 60 training-source and 24 held-out examples; checksums valid, zero ID overlap, GPL-2.0-or-later. |
| Fine-tuning | Not run | Preflight blocks for absent weights/license, missing dependencies, and about 586 MiB available WSL RAM (<4096 MiB gate). |
| Python tests | Passed | WSL Python 3.12: 191 passed on 2026-11-01, including current QEMU harness regressions. |
| Lint and whitespace | Passed | `scripts/lint.sh`, `bash -n scripts/run-qemu.sh`, and `git diff --check` passed on 2026-11-01. |
| Signed updates, rollback, recovery, alpha | Planned | No mechanism is claimed complete. |

---

## System Architecture

```text
+-------------------------------------------------------------------------+
|                               FIRMWARE                                  |
|                     UEFI x86_64 Firmware (OVMF)                         |
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
|       GTK3 client under Cage       | | Deterministic local prototype   |
|                                    | |                                  |
| - Top bar, views, notifications    | | - Text queries over local IPC    |
| - Cage is single-client             | | - Deterministic intent planner   |
| - Shared GTK design tokens         | | - Allowlisted typed tools        |
| - Phone layout is future work      | | - SHA-256 audit permission ledger|
| - Text-entry assistant HUD         | | - Microphone pipeline not active |
+------------------+-----------------+ +-----------------+----------------+
                   |                                     |
                   +<------ Unix-domain JSON IPC ---------->+
```

---

## What Is PK-OS?

PK-OS is a Linux-based operating-system prototype built on Debian:

- **Primary Target**: x86_64 personal computers and laptops.
- **Future Vision**: Seamless mobile companion devices via an adaptive UI layer and an AOSP-based port.
- **Zero Cost (₹0 Budget)**: 100% free and open-source tooling (Debian 12 base, Linux LTS, QEMU/KVM, Wayland, Python 3). Zero paid subscriptions or cloud dependencies.
- **Local-first direction**: Current text requests use a local daemon and do not require a paid cloud API. Voice processing is not implemented.
- **Robust Security**: Capability-gated tool execution requiring explicit user approval for consequential actions (file deletion, network alterations, system modifications).

---

## Current-Source Boot Evidence

The current-source QEMU snapshot image and evidence are local, git-ignored
verification artifacts (not a release image):

- **Image**: `build/output/verification-20261101-current/pk-os-current.raw`
- **File Byte Size**: `2,726,297,600` bytes
- **SHA-256**: `d8770ee3a1fb6d2be44918f278a66590d2286d393a445746496fd81d1fc4f8a5`
- **Source**: commit `819cbcd8f8eaacd6dcb3ca4a27b2777ecd35847d` on `feat/premium-gtk-shell` plus the working-tree diff captured at build time in `build/output/verification-20261101-current/source-working-tree.patch` (patch SHA-256 `D2BFF7F5DBED22DA97AB9DC8DD4114474945FD49335CC5A2CC443553B109E845`; additional untracked-test digest is recorded alongside the build). Guest-source trees were unchanged after this image was built; host acceptance harness refinements followed.
- **Fresh GTK screenshot**: `build/output/verification-20261101-current/ui/00-exact-build-gtk-ready.png` (1280×800); interaction captures are in the same `ui/` directory.
- **Build configuration**: `scripts/assemble_phase2e_disk.py --output .../pk-os-current.raw`; cached rootfs/kernel inputs; QEMU used OVMF UEFI, KVM, 768 MiB, 2 CPUs, snapshot mode. Build log and checksum are alongside the image.
- **Partition Table (GPT)**:
  - **Partition 1 (`ESP`)**: 256 MB FAT32 (`LABEL="PKOS_ESP"`), systemd-boot, Linux kernel `6.1.0-50-amd64`, initramfs, and BLS entry `pkos.conf`.
  - **Partition 2 (`PKOS_ROOT`)**: 2,344 MB ext4 (`LABEL="PKOS_ROOT"`), Debian 12 Bookworm, cage Wayland kiosk compositor, GTK3 PK-OS desktop shell (`shell/src/ui/gui.py`), `pk-intelligenced` daemon, notifications, window manager, and context engine.
- **Historical QEMU report (2026-10-19; not current-source acceptance)**:

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
  [PASS] Framebuffer Capture: 1280x800 (legacy heuristic; not a visual acceptance score)
==========================================================
                ALL BOOT GATES PASSED (Exit Code 0)        
==========================================================
```

The current-source serial log, build log, checksum, and interaction artifacts
are under `build/output/verification-20261101-current/`. The current guest
serial log contains repeated Cage `Basic output test failed for Virtual-1`
messages even while GTK frames render; visual output is usable for observed
interactions but not accepted as fully reliable. noVNC HTTP/VNC TCP reachability
was checked, while browser-driven noVNC input was not.
The older `build/output/qemu-boot.log` and
`build/output/qemu-graphical-boot-interactive.png` are dated 2026-10-19 and are
historical only. Current-image interaction evidence and remaining limits are
listed in the matrix.

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

1. **Guest shutdown control**: The UI requests guest `systemctl poweroff` after explicit confirmation. Current-image confirmation, systemd poweroff, and QEMU exit status 0 were observed.
2. **Host terminal exit**: Press `Ctrl-C` in the PowerShell/WSL terminal running QEMU to stop the VM. This is a host-side stop, not proof of guest graceful shutdown.

---

## Phase 2: Desktop Shell Foundation

Located in [`shell/`](shell/):

- **Design System Tokens** ([shell/src/tokens/](shell/src/tokens/)): Shared color, spacing, typography, radius, and motion tokens. The captured text/control contrast pairs passed 4.5:1; screenshot palette percentages are diagnostic only.
- **Session Lifecycle Manager** ([shell/src/session/lifecycle.py](shell/src/session/lifecycle.py)): Strict state machine (`INIT` -> `READY` -> `ACTIVE` -> `SUSPENDED` -> `TERMINATED`) and configuration validator.
- **Adaptive Layout Calculator** ([shell/src/ui/layout.py](shell/src/ui/layout.py)): Geometry engine calculating layer-shell coordinates for desktop (`>=1024px`) and mobile/touch (`<1024px`) displays.
- **UI Surface Generator** ([shell/src/ui/surface.py](shell/src/ui/surface.py)): Accessible, contrast-validated DOM structure for panels, workspace switchers, and the Voice HUD overlay.
- **Interactive GTK3 Shell** ([shell/src/ui/gui.py](shell/src/ui/gui.py)): GTK client under single-client Cage, with Main, Code, and Settings views, keyboard view shortcuts, and a confirmed power-action prompt. App switching and real device controls are incomplete.
- **Test Suite**: Shell behavior is covered by automated tests; guest interaction acceptance is tracked separately in the matrix.

---

## Parallel Track: PK Intelligence ("Hey PK") Foundation

Located in [`intelligence/`](intelligence/):

- **Inference Boundary** ([intelligence/src/inference.py](intelligence/src/inference.py)): Provider interface currently uses deterministic fallback; ONNX text generation reports unsupported. No neural inference has been verified.
- **End-to-End Orchestrator** ([intelligence/src/orchestration.py](intelligence/src/orchestration.py)): Classifies and executes queries into typed decisions (`CONVERSATIONAL`, `TOOL_EXECUTION`, `CONFIRMATION_REQUIRED`, `ERROR`) with prompt injection defense.
- **Hardened Context Engine** ([intelligence/src/context.py](intelligence/src/context.py)): Atomic JSON writes, schema versioning (`schema_version: 1`), and automatic corrupt-file backup & recovery.
- **Deterministic Tool Registry** ([intelligence/src/tools.py](intelligence/src/tools.py)): Sandboxed tools (`launch_application`, `get_system_status`, `adjust_setting`, `delete_path`, `list_directory`) with path traversal guards.
- **Permission & Safety Ledger** ([intelligence/src/security.py](intelligence/src/security.py)): Capability matrix (`READ_ONLY`, `SYSTEM_CONFIG`, `CONSEQUENTIAL`). Consequential actions raise an interactive approval interrupt. Audit records are cryptographically chained with SHA-256 hashes.
- **Evaluation Benchmark Suite** ([intelligence/src/benchmark.py](intelligence/src/benchmark.py)): latest deterministic planner/policy benchmark passed 14/14 intent cases and 14/14 policy decisions, with 2/2 adversarial rejections. This is not a language-model evaluation.
- **Response data**: Version 2 includes 60 authored training-source examples and 24 held-out examples with validated checksums and no ID overlap. Coverage and human quality review remain limited.
- **Training preflight**: Fails closed without model weights/license, optional training dependencies, and adequate RAM. Training and neural inference were not run.

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

# 5. Run full feasible test suite
python3 -m pytest shell/tests intelligence/tests scripts/tests -v
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
