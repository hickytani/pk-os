# PK-OS

An open-source, Linux-based OS prototype for x86-64 PCs, built on Debian with a GTK desktop and a local-first assistant.

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE) [![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

## Current status — 2026-11-02

Current `main` is `017638c`. A fresh image built from that source booted in QEMU snapshot mode, passed a QMP/HMP readiness probe, reached the GTK/Cage session at 1280×800, and shut down from inside the guest. The image and evidence are local, ignored verification artifacts; no release image is published. Image SHA-256: `ea3e98e1c4f4911c0263cbcc150a889c021df3a016e3d5a83f2fd9016d5e8c4e` at `build/output/verification-20261102-qemu-control-017638c/build/pk-os-control-final.raw`.

| Area | Verified status |
|---|---|
| Boot and control | `Session ACTIVE`; QMP greeting/capability/query-status and HMP `info status` all reported running. The runner tracks its QEMU child and refuses stale socket paths. |
| Desktop interaction | Direct guest input switched Main/Code/Settings; most query strings appeared exactly in guest logs. Two early one-character submissions were ambiguous because their serial entries arrived after the assertion window. Approval/cancel and the guest shutdown confirmation were exercised. Browser noVNC input remains untested. |
| Applications and desktop | `launch terminal` reports `pk-terminal` missing. Launcher entries are disabled in the single-client Cage shell. These GTK views are not OS workspaces and the Python window manager is not connected to compositor surfaces. |
| Settings and diagnostics | Brightness is explicitly unavailable; audio write access remains unverified. Reported diagnostics are guest sourced, but this is not a complete system monitor. |
| Rendering | QEMU reports 1280×800. The service explicitly sets `WLR_RENDERER=pixman` (software rendering). Cage logs repeated `Basic output test failed for Virtual-1`; root cause, frame timing, FPS, and GPU utilization remain unverified. |
| Hey PK | The assistant identifies itself as deterministic/rule-based. No neural inference, voice model training, or LLM fine-tuning occurred. |

The image used the documented assembler and cached Debian rootfs/kernel inputs; QEMU used OVMF, KVM, 768 MiB RAM, two CPUs, `virtio-vga`, and snapshot mode. See the [2026-11-02 exact-image report](docs/testing/DISPLAY-RELIABILITY-REPORT.md#qemu-control-and-exact-image-acceptance--2026-11-02). October 19 and November 1 screenshots remain historical artifacts.

## Hey PK and data status

- Deterministic intent/policy benchmark: 14/14 intent cases, 14/14 policy decisions, 2/2 adversarial rejections. This is not neural inference or model-quality evaluation.
- Dataset v2: 60 training-source examples and 24 held-out examples; checksums valid, IDs unique, zero train/eval ID overlap, declared license GPL-2.0-or-later. This is a small baseline, not yet expanded or independently quality-reviewed.
- Training and neural inference were not run. Fresh preflight measured 604,561,408 bytes available RAM (below 4096 MiB), no local model/weights or model license, and missing `torch`, `transformers`, `datasets`, and `peft`. The RTX 3050's 6 GiB VRAM does not satisfy the RAM gate. No model was downloaded. Refresh hardware status before planning any run.

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

- Full Python suite: **217 passed** — `python3 -m pytest shell/tests intelligence/tests scripts/tests -q`. Markdownlint, yamllint, ShellCheck, structure checks, and `git diff --check` passed.

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
