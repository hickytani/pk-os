# PK-OS

An open-source, Linux-based OS prototype for x86-64 PCs, built on Debian with a GTK desktop and a local-first assistant.

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE) [![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

## Current status — 2026-11-01

A fresh image from `main` booted in QEMU and rendered the GTK/Cage desktop. Readiness-gated keyboard and pointer input switched Main, Code, and Settings; Hey PK returned live guest metrics; and the Settings shutdown confirmation powered off the guest cleanly. Cage logged 2,602 `Basic output test failed for Virtual-1` errors during the run, so display reliability remains under investigation.

| Area | Verified status |
|---|---|
| Current image | `build/output/verification-20261101-cage-instrumented/build/pk-os-cage-guard.raw` — SHA-256 `1f36eb385cf3fef91058835d215e59cf512be738146be33ec6721641a0d702a6` |
| Desktop | Main/Code/Settings rendered and responded to keyboard navigation. Current screenshot: `build/output/verification-20261101-cage-instrumented/interactive-ui/00-after-session-active.png`. |
| Apps | `launch terminal` reports `pk-terminal` is not installed; no app launch is claimed. |
| Settings | Brightness backend unavailable; audio write access unverified. Current-image approval text entry was unreliable, so no approval prompt is claimed for that run. |
| Diagnostics and Hey PK | Guest uptime, memory, disk, and OS returned from guest sources. Assistant identifies as deterministic/rule-based with no language model active. |
| Shutdown | Visible guest confirmation accepted; systemd reached `poweroff.target`; QEMU exited 0 and the snapshot image hash stayed unchanged. |
| Browser preview | Loopback VNC TCP and noVNC HTTP passed health checks. Browser WebSocket/input was not tested; acceptance used direct RFB/QMP input. |
| Visual review | The old 37.4% palette result was a flawed heuristic, not a regression score. Prior GTK surface correction was visually checked; the latest image has not had the full palette/contrast analysis repeated. |

The image was built from commit `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` plus guest-tree patch SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`. It used the documented assembler, cached Debian rootfs/kernel inputs, OVMF, KVM, 768 MiB RAM, two CPUs, and QEMU snapshot mode. Images and evidence are local, ignored artifacts, not release downloads.

## Hey PK and data status

- Deterministic intent/policy benchmark: 14/14 intent cases, 14/14 policy decisions, and 2/2 adversarial rejections. This is not neural inference or model-quality evaluation.
- Dataset v2: 60 training-source examples and 24 held-out examples; checksums valid, IDs unique, zero train/eval ID overlap, declared license GPL-2.0-or-later.
- Training and neural inference were not run. Preflight remains blocked by missing model weights/model license, missing `torch`, `transformers`, `datasets`, and `peft`, and about 471 MiB available WSL RAM versus a 4096 MiB gate. No model was downloaded.

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

- Python suite: **193 passed** — `python3 -m pytest shell/tests intelligence/tests scripts/tests -q`
- `scripts/lint.sh`: markdownlint, yamllint, shellcheck, and structure checks passed.
- `bash -n scripts/run-qemu.sh` and `git diff --check` passed.

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
