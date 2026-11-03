# PK-OS

An open-source, Linux-based OS prototype for x86-64 PCs, built on Debian with a GTK desktop and a local-first assistant.

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE) [![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

## Current status — 2026-11-03

Published `main` is `8e190fd`; the working tree contains uncommitted desktop, dataset, and test changes. Fresh graphical Sway images were built from this tree under `build/output/verification-20261102-sway-8e190fd-fixed{2,3,4}/`. The final build is `fixed4/pk-os-sway.raw` (SHA-256 `0aac671a7cd1cc9d5e871be2d8a8d130fd3c60bba6bb26023c91752ddb66d7f7`), booted with OVMF/KVM, 768 MiB, two CPUs, and snapshot mode. It reached the GTK/Sway desktop at 1280×800; live metrics and accurate unavailable settings states were visible. The Sway `Super+Return` binding opened a real `foot` shell. The desktop Terminal button reported a PID but its immediate screenshot did not show a terminal window; daemon-to-user dispatch remains unverified. The RFB acceptance harness repeated a shortcut and opened many terminals, so that run does not establish a single-key lifecycle result. Browser-based noVNC input remains untested.

| Area | Verified status |
|---|---|
| Boot and control | Fresh fixed4 image reached Sway/GTK; QMP and HMP reported running; loopback VNC TCP and noVNC HTTP health passed. Browser WebSocket/input remains untested. |
| Desktop interaction | Guest input reached the shell and a real `foot` client. RFB `Super+Return` repeated and opened multiple clients, ending in a guest soft-lockup warning; controlled keyboard lifecycle is not accepted. Guest shutdown passed on preceding fixed3; fixed4 was host-stopped after the input storm. |
| Applications and desktop | Sway and GTK are booted. `Super+Return` opened a real foot shell and displayed the active Wayland socket. Files/Browser/Editor remain unavailable. Terminal button dispatch is not yet accepted. |
| Settings and diagnostics | Brightness is explicitly unavailable; audio write access remains unverified. Reported diagnostics are guest sourced, but this is not a complete system monitor. |
| Rendering | QEMU reports 1280×800. The service explicitly sets `WLR_RENDERER=pixman` (software rendering). A diagnostic parse counted 477 `Virtual-1` basic-output failures; QEMU reported `-virgl`. Root cause, frame timing, FPS, and GPU utilization remain unverified. |
| Hey PK | The assistant identifies itself as deterministic/rule-based. No neural inference, voice model training, or LLM fine-tuning occurred. |

The image used the documented rootfs and disk assembler, Bookworm graphical packages, OVMF, KVM, `virtio-vga`, and snapshot mode. Exact build and run evidence, including prior runs, is in the [current-source acceptance report](docs/testing/DISPLAY-RELIABILITY-REPORT.md#current-source-sway-acceptance--2026-11-03). October 19 and November 1 screenshots remain historical artifacts.

## Hey PK and data status

- Deterministic intent/policy benchmark: 14/14 intent cases, 14/14 policy decisions, 2/2 adversarial rejections. This is not neural inference or model-quality evaluation.
- Dataset v2: 72 training-source examples and 34 held-out examples; checksums valid, IDs unique, zero train/eval ID overlap, zero normalized prompt duplicates/overlap, declared license GPL-2.0-or-later. This is a small baseline, not yet independently quality-reviewed.
- Training and neural inference were not run. Fresh `--preflight-only` measured 589,815,808 bytes available RAM (~563 MiB), 6,162,481,152 bytes free GPU memory, no local model/weights or model license, and missing `torch`, `transformers`, `datasets`, and `peft`. The conservative 4 GiB system-RAM gate blocks training; GPU memory does not substitute for it. No model was downloaded.

## Product direction

The first multi-window foundation is Sway, packaged as an opt-in session while Cage remains the boot default. The architecture decision and limits are in [ADR-005](docs/adr/ADR-005-native-desktop-foundation.md). A current-source Sway guest boot and separate `foot` shell are verified; stable launcher-driven app lifecycle and resilient compositor input remain open. Files, functional hardware settings, full system monitoring, package management, local neural inference/training, secure updates, recovery, and public installation remain incomplete.

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

- Full Python suite: **242 passed, 1 skipped** — `python3 -m pytest shell/tests intelligence/tests scripts/tests -q`. The skip is native Sway config validation because Sway is not installed on the host. Current `git diff --check` is recorded with the acceptance report.

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
