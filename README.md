# PK-OS

An open-source, Linux-based OS prototype for x86-64 PCs, built on Debian with a GTK desktop and a local-first assistant.

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE) [![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

## Current status — 2026-11-02

Published `main` is `3e7f8e7`. The last booted image was built from its parent, `017638c`; the current desktop/application changes below have not yet been built into an image. That earlier image reached GTK/Cage at 1280×800 and shut down from inside the guest. It remains infrastructure evidence, not product acceptance. Its local image SHA-256 is `ea3e98e1c4f4911c0263cbcc150a889c021df3a016e3d5a83f2fd9016d5e8c4e` at `build/output/verification-20261102-qemu-control-017638c/build/pk-os-control-final.raw`.

| Area | Verified status |
|---|---|
| Boot and control | `Session ACTIVE`; QMP greeting/capability/query-status and HMP `info status` all reported running. The runner tracks its QEMU child and refuses stale socket paths. |
| Desktop interaction | Direct guest input switched Main/Code/Settings; most query strings appeared exactly in guest logs. Two early one-character submissions were ambiguous because their serial entries arrived after the assertion window. Approval/cancel and the guest shutdown confirmation were exercised. Browser noVNC input remains untested. |
| Applications and desktop | Added a packaged `pk-terminal` wrapper backed by Wayland-native `foot` and an opt-in Sway session for real compositor-managed windows. These changes are not in a booted image; the current GTK launcher remains disabled under Cage. |
| Settings and diagnostics | Brightness is explicitly unavailable; audio write access remains unverified. Reported diagnostics are guest sourced, but this is not a complete system monitor. |
| Rendering | QEMU reports 1280×800. The service explicitly sets `WLR_RENDERER=pixman` (software rendering). A diagnostic parse counted 477 `Virtual-1` basic-output failures; QEMU reported `-virgl`. Root cause, frame timing, FPS, and GPU utilization remain unverified. |
| Hey PK | The assistant identifies itself as deterministic/rule-based. No neural inference, voice model training, or LLM fine-tuning occurred. |

The image used the documented assembler and cached Debian rootfs/kernel inputs; QEMU used OVMF, KVM, 768 MiB RAM, two CPUs, `virtio-vga`, and snapshot mode. See the [2026-11-02 exact-image report](docs/testing/DISPLAY-RELIABILITY-REPORT.md#qemu-control-and-exact-image-acceptance--2026-11-02). October 19 and November 1 screenshots remain historical artifacts.

## Hey PK and data status

- Deterministic intent/policy benchmark: 14/14 intent cases, 14/14 policy decisions, 2/2 adversarial rejections. This is not neural inference or model-quality evaluation.
- Dataset v2: 60 training-source examples and 24 held-out examples; checksums valid, IDs unique, zero train/eval ID overlap, zero normalized prompt duplicates/overlap, declared license GPL-2.0-or-later. This is a small baseline, not yet expanded or independently quality-reviewed.
- Training and neural inference were not run. Fresh `--preflight-only` measured 599,281,664 bytes available RAM (571 MiB), 5,749 MiB free RTX 3050 VRAM, no local model/weights or model license, and missing `torch`, `transformers`, `datasets`, and `peft`. The conservative 4 GiB system-RAM gate blocks training; GPU memory does not substitute for it. No model was downloaded.

## Product direction

The first multi-window foundation is Sway, packaged as an opt-in session while Cage remains the boot default. The architecture decision and limits are in [ADR-005](docs/adr/ADR-005-native-desktop-foundation.md). PK Terminal now has a real `foot` process/package path, but no image has yet demonstrated opening it beside the PK shell. Files, functional hardware settings, full system monitoring, package management, local neural inference/training, secure updates, recovery, and public installation remain incomplete.

## Build and preview

Build a local image (requires root in Linux/WSL and the documented build inputs):

```bash
sudo python3 scripts/assemble_phase2e_disk.py --output build/output/pk-os-dev.raw
```

Start the isolated QEMU/noVNC preview:

```bash
./scripts/run-qemu.sh --image=build/output/pk-os-dev.raw --graphical --preview --snapshot --memory=768
```

On Windows, see `scripts/windows/preview.ps1`. Use the Settings shutdown control to test guest poweroff; `Ctrl-C` stops QEMU from the host and does not test guest shutdown.

## Checks

- Full Python suite: **230 passed, 1 skipped** — `python3 -m pytest shell/tests intelligence/tests scripts/tests -q`. The skip is native Sway config validation because Sway is not installed on the host. Markdownlint, yamllint, ShellCheck, structure checks, and `git diff --check` passed.

## Project direction

Boot reliability, a usable multi-window desktop, real allowlisted apps, verified hardware controls, privilege separation, secure updates/recovery, security hardening, reproducible release builds, and open-source distribution remain in scope. Phone/AOSP support is a future target. Screens and APIs alone do not count as completed system features.

## Documentation

- [Acceptance matrix](docs/testing/ACCEPTANCE-MATRIX.md)
- [Display reliability report and exact-build evidence](docs/testing/DISPLAY-RELIABILITY-REPORT.md)
- [Interactive preview guide](docs/development/INTERACTIVE-PREVIEW.md)
- [Development roadmap](docs/architecture/ROADMAP.md)
- [PK Intelligence architecture and preflight](docs/architecture/PK-INTELLIGENCE.md)
- [Security policy](SECURITY.md)

Licensed under GPL-2.0-or-later. See [LICENSE](LICENSE).
