# PK-OS Development Roadmap

Status: LIVING DOCUMENT — updated 2026-11-02.

The current acceptance index is the [acceptance matrix](../testing/ACCEPTANCE-MATRIX.md).
Published `main` is `3e7f8e7`. The last exact image is from parent commit
`017638c`; no image has yet been built from the current desktop/application
working-tree changes. That parent image booted to GTK/Cage at 1280×800 and
completed guest shutdown. Its service forces Pixman; the new diagnostic parser
records 477 `Virtual-1` basic-output failures, QEMU's `-virgl` feature report,
and unavailable performance metrics, without inferring the root cause.

This sprint selected Sway as the first real multi-window foundation and added
an opt-in unit/config while keeping Cage as the default. It also added the
packaged `foot`-backed PK Terminal entry point and early-process-exit reporting
for allowlisted launches. These are source-level integration milestones only;
the Sway config and two-client window behavior have not been boot-tested. The
shell launcher stays disabled under Cage. Hey PK remains deterministic; no
neural inference or training occurred. See [ADR-005](../adr/ADR-005-native-desktop-foundation.md),
the [current acceptance matrix](../testing/ACCEPTANCE-MATRIX.md), and the
[exact-image continuation report](../testing/DISPLAY-RELIABILITY-REPORT.md#qemu-control-and-exact-image-acceptance--2026-11-02).

## Parallel product workstreams — current state

| Workstream | Verified state this sprint | Next concrete milestone |
|---|---|---|
| W1 — QEMU/QMP/RFB reliability | Added QMP greeting/capability/status and HMP readiness checks, owned-child lifecycle, stale-socket refusal, and real-QEMU protocol coverage. Run-04 guest shutdown passed. Browser input did not. | Resolve serial input correlation and complete browser noVNC keyboard/pointer acceptance. |
| W2 — Cage/rendering | QEMU output is 1280×800; service uses Pixman; parser found 477 output-test failures and `-virgl`. Root cause and frame performance remain unknown. | Boot the opt-in Sway image with debug logs, compare output commit behavior, and capture renderer/frame metrics where available. |
| W3 — Native desktop/window management | ADR-005 selects Sway; an opt-in systemd session/config is installed by graphical builders. Cage remains default. Sway config has structural tests only. | Build and boot Sway, then verify two independent Wayland clients, focus, move/resize, fullscreen, close, scratchpad and workspaces. |
| W4 — Functional PK applications | Added `pk-terminal` as an `exec` wrapper around packaged Wayland-native `foot`, plus desktop entry and image installation. Launch tool now detects quick startup exits. No guest launch is verified. | Boot Sway image; launch terminal from PK, run a real shell command, verify focus/close/exit/error propagation. Then build Files. |
| W5 — Hey PK/training | Benchmark remains deterministic (14/14); dataset v2 remains 60/24 with verified checksums and no ID overlap. No weights/license/dependencies; current WSL RAM remains below the 4 GiB gate. No training/inference. | Review and expand the licensed dataset, choose a specific model/license, and prove a resource-safe local inference/training plan before dependencies or weights. |
| W6 — Security/OS infrastructure | Privileged settings, secure update/recovery, and hardening are not accepted end-to-end. | Specify narrow privileged service and threat model; implement one auditable system-control path. |
| W7 — Open distribution/CLI | Release and `pk` CLI remain roadmap work. | Define reproducible release provenance and a minimal documented developer CLI milestone. |

A GTK frame, API, test count, or QEMU boot alone does not close a product
milestone. Long-term distribution, security, recovery, hardware support, and
future phone/AOSP work remain in scope.

## Product breadth still required

The target remains a complete, independently branded desktop OS built on
established Linux components. A GTK shell frame does not satisfy these product
milestones:

- **PK Desktop**: multi-window compositor, minimize/maximize/resize/snapping,
  multiple real workspaces, search, dock/taskbar, notifications, quick
  settings, appearance, and accessibility.
- **PK apps**: a real PK Terminal with shell execution, tabs and developer
  workflows; PK Files with safe file operations and removable media; an
  allowlisted application launcher and verified application lifecycle.
- **System services**: real display, audio, network, Bluetooth, power, storage,
  user/account, security, privacy, and accessibility backends. Unavailable
  backends must say so.
- **System monitor and app management**: guest-sourced CPU/RAM/GPU/storage,
  processes, network and logs; package discovery, install, update, removal,
  signature verification, dependency handling and permission visibility.
- **Hey PK**: independent wake-word, offline STT, local LLM, typed/policy-gated
  tools, local TTS, microphone/privacy controls, reproducible training and
  held-out evaluation. These are separate acceptance gates; none is implied by
  the current deterministic assistant.
- **Platform and release**: privilege separation, signed updates and rollback,
  recovery, security hardening, a usable public `pk` developer CLI, installer,
  open-source release artifacts and hardware support. Phone/AOSP remains a
  separate future target with its own build and acceptance.

---

## Phase Dependency Order & Parallel Tracks

```text
Phase 0 (Foundation) [DONE]
  |
Phase 1 (Bootable UEFI Image & QEMU Smoke Test) [DONE]
  +-----------------------------------+
  |                                   |
Phase 2 (Desktop Shell Foundation)  Parallel PK Intelligence Foundation
  | [IN PROGRESS]                     | [IN PROGRESS]
  v                                   v
Phase 3 (System Integration) <--------+
  |
Phase 4 (Secure Updates & A/B Rollback)
  |
Phase 5 (Advanced Intelligence & Voice Expansion)
  |
Phase 6 (Security Hardening & Fuzzing)
  |
Phase 7 (Bare-Metal Installer & Alpha Release)
```

Phases must complete their exit gate before general promotion.
Independent work (PK Intelligence local pipeline, design tokens, test suites) proceeds in coordinated parallel tracks.

---

## Phase 0 — Repository Foundation

**Status**: COMPLETED  
**Exit Criteria Met**:
- [x] Repository inspected and baselined.
- [x] README.md accurately describes current state.
- [x] CONTRIBUTING.md, SECURITY.md, LICENSE, CODE_OF_CONDUCT.md present.
- [x] .gitignore and .editorconfig configured.
- [x] CI workflow runs and all applicable checks pass.
- [x] ADR-001 (base distribution) created and accepted.
- [x] Windows-first developer automation (`setup.ps1`, `check-prereqs.ps1`, `build.ps1`, `test.ps1`).

---

## Phase 1 — Reproducible Linux Rootfs and Bootable Disk Image

**Status**: COMPLETED  
**Exit Criteria Met**:
- [x] Base distribution selected: Debian 12 minimal (`ADR-001`).
- [x] Reproducible base rootfs archive built (`build/output/pk-os-rootfs.latest.tar.zst`, ~87 MB).
- [x] Linux LTS 6.1 kernel (`linux-image-6.1.0-50-amd64`) and initramfs integrated.
- [x] systemd-boot (UEFI BLS) configured with `loader.conf` and `pkos.conf`.
- [x] Bootable GPT raw disk image generated (`build/output/pk-os-dev.raw`, 1,500 MB).
- [x] Memory-safe partition format and rsync staging pipeline verified in WSL2.
- [x] Automated QEMU boot smoke test with KVM acceleration verified reaching userspace login prompt (`pk-os login:`, Exit Code 0).
- [x] Boot serial log captured and archived (`build/output/qemu-boot.log`).

---

## Phase 2 — Custom PK-OS Desktop Shell

**Status**: IN PROGRESS  
**Depends on**: Phase 1 complete  

### Objectives

- Implement modular Wayland shell architecture (`ADR-002`).
- Establish mathematical design tokens (typography, surfaces, colors, spacing, motion).
- Build independent user-space shell process (`pk-shell`) binding to `wlr-layer-shell-unstable-v1`.
- Support responsive adaptive breakpoints (desktop `>=1024px`, phone `<1024px`).
- Deliver vertical slice: Top panel, application launcher modal, and voice HUD overlay.
- Full Wayland compositor session packaging and execution.

### Exit Criteria

- [x] ADR-002 accepted (Wayland compositor & layer-shell architecture).
- [x] Design token system implemented (`shell/src/tokens/tokens.json`, `tokens.css`).
- [x] Session lifecycle state machine implemented and tested (`shell/src/session/lifecycle.py`).
- [x] Adaptive layout calculator implemented and tested (`shell/src/ui/layout.py`).
- [x] Shell test suite passing 100% (`test_tokens.py`, `test_lifecycle.py`, `test_layout.py`).
- [x] Cage, GTK shell, and intelligence service are packaged in the fresh UEFI image.
- [x] Graphical session auto-starts and reaches GTK in QEMU snapshot mode.
- [ ] Partial current-image acceptance completed; browser input, early one-character text correlation, and remaining checks are open.
- [ ] Launch a real allowlisted application in a compositor/session that supports application switching.
- [ ] Replace the single-client Cage preview or add verified application lifecycle management.
- [ ] Implement real brightness and audio controls with privilege boundaries and end-to-end failure reporting.
- [ ] Verify focus navigation, responsive layouts, notifications, and desktop behavior on supported hardware.

---

## Parallel Track — PK Intelligence ("Hey PK") Foundation

**Status**: IN PROGRESS (Deterministic Text Prototype; Local Model and Voice Not Integrated)
**Objective**: Local-first, offline voice and autonomous task assistant.

### Exit Criteria

- [x] ADR-003 accepted (Local-first voice & agent architecture).
- [x] Abstract pipeline interfaces defined (`AudioCapture`, `WakeWord`, `STT`, `IntentPlanner`, `Tool`, `SecurityLedger`).
- [x] Deterministic tool registry implemented (`launch_application`, `get_system_status`, `adjust_setting`, `delete_path`).
- [x] Permission ledger with SHA-256 hash chaining and consequential action intercept implemented.
- [x] Prompt injection defense validated against adversarial attacks.
- [x] Versioned evaluation dataset created (`intelligence/data/v1/commands.jsonl`).
- [x] Reproducible benchmark harness passing 100% (`intelligence/benchmarks/eval_harness.py`).
- [ ] Integration of local quantized ONNX wake-word model and GGUF SLM engine. Current ONNX provider explicitly reports unsupported; no neural inference is verified.
- [ ] End-to-end microphone-to-speaker audio verification on host hardware.
- [x] Versioned response dataset bundle with provenance, checksums, deterministic validation split, and separate held-out set (60 training-source / 24 held-out); broader task coverage and quality review remain open.
- [x] Fail-closed model/license/data/dependency/resource preflight. Current WSL RAM is below the 4 GiB minimum; training remains blocked.
- [ ] Select a licensed low-memory local inference runtime and model from measured RAM/GPU limits; do not download before an explicit resource plan.
- [ ] Establish independent semantic/safety evaluation, model registry, and rollback before integrating inference.

---

## Phase 3 — Real System Integration

**Status**: PLANNED  
**Depends on**: Phase 2 and PK Intelligence groundwork  
- IPC integration between shell and system daemons (`docs/architecture/IPC-INTEGRATION.md`) with service-level authorization and audit records.
- Real settings and device controls through verified guest interfaces, with explicit failure states and no fabricated success.
- Application discovery from `/usr/share/applications/` and application lifecycle management in a multi-window compositor.
- Privilege separation between GTK, policy, and narrowly scoped system services.

---

## Phase 4 — Secure Updates and Recovery

**Status**: PLANNED  
- A/B dual-root slot partitioning with dm-verity read-only verification.
- Cryptographically signed update payloads (`cosign`).
- Automatic rollback on boot failure.
- Recovery environment and fault-injection acceptance before release.

---

## Phase 5 — Differentiating Features

**Status**: PLANNED (Advanced Intelligence Expansion)  
- Multi-step tool planning with verification.
- Contextual file and document search.
- Adaptive continuity between desktop and future mobile port.

---

## Phase 6 — Security Hardening and Reliability

**Status**: PLANNED  
- Static analysis, fuzzing of IPC endpoints, cgroup resource limits.
- Fault injection and power-loss recovery tests.
- Threat modeling, least-privilege review, signed artifact verification, and supply-chain checks.

---

## Phase 7 — Installer and Alpha Release

**Status**: PLANNED  
- Hybrid live ISO with guided bare-metal installer.
- Target drive selection safety checks (never overwrite host without confirmation).
- Reproducible signed alpha release artifacts.
- Open-source distribution policy, attribution review, installation/recovery guidance, and supported-device matrix.
- Future phone/AOSP port remains a separate target with its own maintained build and hardware acceptance.
