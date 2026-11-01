# PK-OS Acceptance Matrix

Evidence capture date: **2026-11-01**. The latest guarded image from `main`
booted to the visible GTK/Cage desktop. Direct RFB keyboard and QMP pointer
interactions were run after the guest reported `Session ACTIVE`. Cage still
logged repeated Virtual-1 output-test failures. Browser-driven noVNC input was
not tested. Older artifact directories refer to their recorded source commits.

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| Reproducible image assembly | Guarded build passed; one earlier transfer artifact failed | [Guarded build log](../../build/output/verification-20261101-cage-instrumented/build/guard-build.log) records final image hash and GPT. An earlier unguarded output had an empty ESP and fell through to PXE. The assembler now validates the FAT32 boot sector before and after transfer; two regression tests cover valid and empty ESPs. | Verify the fallback EFI file itself and repeat independent builds. |
| Current-source x86-64 UEFI boot | Passed to visible GTK desktop | [Ready frame](../../build/output/verification-20261101-cage-instrumented/interactive-ui/00-after-session-active.png), 1280x800. Linux and launcher reached `Session ACTIVE`; workspace captures show visible output. Cage output-test warnings remain. | Diagnose the repeated output-test errors and retest reliability over longer runs/resolutions. |
| New exact-source image | Built and booted; interactive evidence captured | `verification-20261101-cage-instrumented/build/pk-os-cage-guard.raw`, 2,726,297,600 bytes; SHA-256 `1f36eb385cf3fef91058835d215e59cf512be738146be33ec6721641a0d702a6`; source commit `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` plus guest-tree patch SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`. | Root-cause Cage output warnings and expand acceptance coverage. |
| GTK/Cage desktop | Visible and interactive; reliability partial | Current image Main/Code/Settings frames are in `verification-20261101-cage-instrumented/interactive-ui/`. `Alt+2`, `Alt+3`, and `Alt+1` changed views; Cage logged 2,602 Virtual-1 output-test failures over the run. | Explain and fix or bound the Cage output-test failure; test additional resolutions and longer sessions. |
| Cage output failure diagnosis | Reproduced; cause unresolved | Serial logs contain 2,602 `Basic output test failed for Virtual-1` messages even though the desktop rendered and responded. The earlier `-D` attempt still records the incompatible Cage 0.1.4-4 option. See [display report](DISPLAY-RELIABILITY-REPORT.md). | Enable wlroots DEBUG logging compatibly and identify the failing test condition. |
| noVNC/VNC | Endpoint health passed; browser input untested | Runner verified loopback VNC TCP and noVNC HTTP. RFB keyboard and QMP pointer were used directly; no browser WebSocket/input test was made. | Test browser input after or alongside the display reliability investigation. |
| Repeatable guest input | Current image keyboard and pointer actions exercised | Readiness-gated harness switched Main/Code/Settings, activated Hey PK controls, submitted `launch terminal`, and accepted the Settings shutdown confirmation. The text-entry path dropped/repeated characters in the brightness approval attempt. | Improve or replace text injection and retest approval. |
| Application launcher / allowlisted app | Launch request reached the tool; app missing | Current image response says `pk-terminal` is not installed; no app launch succeeded. Launcher buttons remain disabled. | Package a real allowlisted app and verify its lifecycle. |
| Navigation and keyboard | Passed for workspace switching | Readiness-gated `Alt+2`, `Alt+3`, `Alt+1` captures show Code, Settings, and Main. | Verify focus order across all controls; browser path remains untested. |
| Settings and approval | Accurate unavailable status verified; current approval incomplete | Current Settings frame says display brightness is unavailable and audio write access is unverified. Current brightness approval text was corrupted by RFB typing; approval/backend failure was verified on the earlier `819cbcd` image only. | Fix text input reliability, then verify confirmation and backend failure on latest image. |
| Guest diagnostics | Current image guest-sourced response verified | `06-live-system-status.png` reports uptime 311 seconds, free RAM 459 MB / total 702 MB, disk available 0.86 GB, and `PK-OS prototype`. | Check values under varied load and unavailable-source conditions. |
| Hey PK behavior | Deterministic fallback verified; inference not integrated | `07-deterministic-capabilities.png` labels `RULE-BASED` and no language model. `10-launch-terminal-response.png` reports the missing `pk-terminal`; system status response labels `pk-deterministic-assistant · deterministic / no LLM`. | Integrate a licensed local runtime and evaluate independently. |
| Guest shutdown | Latest guest UI shutdown verified | `18-shutdown-confirmation.png` shows explicit guest shutdown confirmation. After acceptance, serial reached `poweroff.target`, `reboot: Power down`; runner exited 0, ports 5999/6080 closed, and snapshot hash stayed unchanged. | Verify restart and repeated shutdown. |
| Visual palette and contrast | Earlier screenshot metrics only | 99.0% token match, 96.5% background-token coverage, and five 4.5:1 contrast pairs were measured on the earlier `819cbcd` screenshot, not recomputed on the latest image. The old 37.4% heuristic was not a visual regression score; a GTK text surface defect was fixed there. | Recompute measurable visual criteria on latest screenshots and review layout/focus/legibility. |
| Full Python suite | Passed | WSL Python 3.12: **193 passed** on 2026-11-01, including two ESP boot-sector regressions. | Run release CI and platform-specific checks. |
| Repository lint | Passed | `scripts/lint.sh`, `bash -n scripts/run-qemu.sh`, and `git diff --check` passed after the guard, test, and documentation changes. | Run release CI and platform-specific checks. |
| Intent benchmark | Passed; planner/policy only | [Report](../../build/output/verification-20261023-interactive/intelligence-report.json): 14/14 intent, 14/14 policy decisions, 2/2 adversarial rejections (100%), mean 0.14 ms. Not inference or model-quality evidence. | Expand independent intent and adversarial evaluation. |
| Assistant response dataset | Passed integrity checks; limited coverage | v2 now has 60 training-source and 24 held-out records; manifest SHA-256 values pass, IDs are unique, train/test overlap is 0, declared license is GPL-2.0-or-later. | Human-review factual accuracy and broaden independent topic/language coverage; topic overlap remains. |
| Training preflight | Correctly blocked; no training | Rerun confirms 60 records pass the count gate; no local model, weights, or license; `torch`, `transformers`, `datasets`, and `peft` are missing; WSL had about 471 MiB available RAM versus the 4096 MiB minimum. GPU memory is not a substitute for the CPU RAM gate. | Choose a specific licensed low-resource inference/training stack and produce a measured resource plan before installing or downloading anything. |
| Neural inference / training | Not run | No local model artifact was present; training dependencies were absent; no inference or training occurred. | Verify a real local model run and saved artifact before making either claim. |
| System controls, privilege separation, updates, recovery, hardening, distribution, phone/AOSP | Roadmap only | No complete end-to-end acceptance evidence. | Implement narrow privileged services, real device controls, signed updates/rollback, recovery, security hardening, reproducible release packaging, and future phone/AOSP support. |

## Earlier GTK image record (not latest HEAD)

- Branch at build: `feat/premium-gtk-shell`; commit `819cbcd8f8eaacd6dcb3ca4a27b2777ecd35847d` plus captured working-tree patch.
- Image: `build/output/verification-20261101-current/pk-os-current.raw`, 2,726,297,600 bytes; SHA-256 above. Separate from historical artifacts.
- Build: `scripts/assemble_phase2e_disk.py --output .../pk-os-current.raw`; cached Debian rootfs and kernel inputs; GPT/UEFI, 2600 MB image.
- QEMU: KVM, OVMF UEFI, 768 MiB RAM, 2 CPUs, snapshot mode, VNC/noVNC, optional QMP tablet socket. Final guest log and runner cleanup evidence are in the verification directory.
- The October 19 screenshots under `build/output/` remain historical. The first unguarded current-source artifact had an empty ESP; the guarded image listed above booted and rendered GTK, with current interactions recorded in `DISPLAY-RELIABILITY-REPORT.md`.

The latest guarded `main` image and readiness-gated interactions are recorded
in the display report. The first unguarded attempt with an empty ESP is a failed
artifact; subsequent current-source GTK interaction evidence belongs to the
guarded image listed above.

Do not promote a feature because a screen, API, or unit-test double exists. Keep
each feature at its demonstrated level until current-image evidence covers its
real guest effect and failure path.
