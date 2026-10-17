# PK-OS Development Roadmap

Status: LIVING DOCUMENT — updated after each phase gate.
Last updated: Phase 1 Completed / Phase 2 & Parallel PK Intelligence In Progress

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
- [ ] Packaging of compositor runtime into bootable image.
- [ ] Graphical session auto-start on boot with visual screenshot evidence.

---

## Parallel Track — PK Intelligence ("Hey PK") Foundation

**Status**: IN PROGRESS (Groundwork Complete)  
**Objective**: Local-first, offline voice and autonomous task assistant.

### Exit Criteria

- [x] ADR-003 accepted (Local-first voice & agent architecture).
- [x] Abstract pipeline interfaces defined (`AudioCapture`, `WakeWord`, `STT`, `IntentPlanner`, `Tool`, `SecurityLedger`).
- [x] Deterministic tool registry implemented (`launch_application`, `get_system_status`, `adjust_setting`, `delete_path`).
- [x] Permission ledger with SHA-256 hash chaining and consequential action intercept implemented.
- [x] Prompt injection defense validated against adversarial attacks.
- [x] Versioned evaluation dataset created (`intelligence/data/v1/commands.jsonl`).
- [x] Reproducible benchmark harness passing 100% (`intelligence/benchmarks/eval_harness.py`).
- [ ] Integration of local quantized ONNX wake-word model and GGUF SLM engine.
- [ ] End-to-end microphone-to-speaker audio verification on host hardware.

---

## Phase 3 — Real System Integration

**Status**: PLANNED  
**Depends on**: Phase 2 and PK Intelligence groundwork  
- IPC integration between shell and system daemons (`docs/architecture/IPC-INTEGRATION.md`).
- Live system metrics, NetworkManager, audio volume control via WirePlumber.
- Application discovery from `/usr/share/applications/`.

---

## Phase 4 — Secure Updates and Recovery

**Status**: PLANNED  
- A/B dual-root slot partitioning with dm-verity read-only verification.
- Cryptographically signed update payloads (`cosign`).
- Automatic rollback on boot failure.

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

---

## Phase 7 — Installer and Alpha Release

**Status**: PLANNED  
- Hybrid live ISO with guided bare-metal installer.
- Target drive selection safety checks (never overwrite host without confirmation).
- Reproducible signed alpha release artifacts.
