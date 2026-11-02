# PK-OS

An open-source, Linux-based OS prototype for x86-64 PCs, built on Debian with a GTK desktop and a local-first assistant.

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE) [![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

## Current status — 2026-11-01

A fresh image from current `main` (`a84de7a`) booted in QEMU and reached the GTK/Cage session. A later QMP acceptance attempt also reached `Session ACTIVE`, but its monitor/QMP sockets refused control connections; a second runner was blocked by that QEMU process's VNC listener. No exact desktop actions are claimed for the final image. The prior `0f81a42` image switched Main, Code, and Settings and shut down cleanly, but Cage logged 2,602 output-test failures and text entry was malformed or partial.

| Area | Verified status |
|---|---|
| Current HEAD image | `build/output/verification-20261101-post-acceptance-a84de7a/build/pk-os-qmp-text-final.raw` — SHA-256 `84531c96a2882a17d6dac68c27c488be8eefac918412c2b494e3ed21d79dccea`; built from `a84de7a` plus the working-tree changes and reached `Session ACTIVE`. Input acceptance did not run because QMP/HMP connections were refused. |
| Last fully exercised desktop | Main/Code/Settings rendered and responded on the prior `0f81a42` build. Its screenshot is historical evidence for that image only: `build/output/verification-20261101-cage-instrumented/interactive-ui/00-after-session-active.png`. |
| Apps | `launch terminal` reports `pk-terminal` is not installed; no app launch is claimed. |
| Settings and approvals | Prior image reported brightness backend unavailable and audio write access unverified. Its text entry was malformed or partial; no current-HEAD approval/tool execution is verified. |
| Diagnostics and Hey PK | Guest uptime, memory, disk, and OS returned from guest sources. Assistant identifies as deterministic/rule-based with no language model active. |
| Shutdown | Prior image reached `poweroff.target`; the final current-image QEMU process was stopped by the host after its control sockets refused connections. Current-image guest shutdown is not verified. |
| Browser preview | Current runner confirmed loopback VNC TCP and noVNC HTTP only. Browser WebSocket/input remains untested; the computer-use browser host was unavailable. |
| Visual review | The old 37.4% palette result was a flawed heuristic, not a regression score. Prior GTK surface correction was visually checked; the latest image has not had the full palette/contrast analysis repeated. |

The current-HEAD image used the documented assembler and cached Debian rootfs/kernel inputs. Its QEMU run used OVMF, KVM, 768 MiB RAM, two CPUs, `virtio-vga`, and snapshot mode. The prior fully interacted image was built from `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` plus guest-tree patch SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`. Images and evidence are local, ignored artifacts, not release downloads. See the [continuation evidence](docs/testing/DISPLAY-RELIABILITY-REPORT.md#post-acceptance-continuation-audit--2026-11-01).

## Hey PK and data status

- Deterministic intent/policy benchmark: 14/14 intent cases, 14/14 policy decisions, and 2/2 adversarial rejections. This is not neural inference or model-quality evaluation.
- Dataset v2: 60 training-source examples and 24 held-out examples; checksums valid, IDs unique, zero train/eval ID overlap, declared license GPL-2.0-or-later.
- Training and neural inference were not run. Preflight remains blocked by missing model weights/model license, missing `torch`, `transformers`, `datasets`, and `peft`, and 959 MiB available WSL RAM versus a 4096 MiB gate. The RTX 3050 has 6 GiB VRAM, but that does not satisfy the RAM gate. No model was downloaded.

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

- Python suite: **202 passed** — `python3 -m pytest shell/tests intelligence/tests scripts/tests -q` after the QMP harness fixes.
- `scripts/lint.sh`: markdownlint, yamllint, and structure checks passed; ShellCheck identified a CR character in the generated final-run wrapper, which is being normalized and linted again.
- `git diff --check` will be rerun after the documentation update.

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
