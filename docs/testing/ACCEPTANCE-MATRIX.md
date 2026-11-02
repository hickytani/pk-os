# PK-OS Acceptance Matrix

Evidence capture date: **2026-11-01**. Latest full desktop interactions belong
to the guarded `0f81a42` build. Current `main` source (`a84de7a`) and a later
working-tree image reached `Session ACTIVE`; on the latter, QMP/HMP connections
were refused and a retry was blocked by its VNC listener. Browser-driven noVNC
input was not tested. See the [continuation audit](DISPLAY-RELIABILITY-REPORT.md#post-acceptance-continuation-audit--2026-11-01).

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| Current working-tree image build and boot | Built and reached `Session ACTIVE`; interactions blocked by harness sockets | Image `verification-20261101-post-acceptance-a84de7a/build/pk-os-qmp-text-final.raw`, 2,726,297,600 bytes, SHA-256 `84531c96a2882a17d6dac68c27c488be8eefac918412c2b494e3ed21d79dccea`; source commit `a84de7a16f0324291b280e1581bb2002887b801e` plus working-tree changes. QEMU used snapshot, KVM, OVMF, 768 MiB and 2 CPUs. | Fix control-socket lifecycle and rerun the UI sequence with fresh screenshots and guest shutdown evidence. |
| Current exact-image interactions | Not verified | QMP and HMP clients returned `Connection refused`; QEMU still held VNC 5999 and prevented a second runner. The identified test process was stopped by host signal. No screenshots or interaction results are claimed. | Fix runner cleanup/control sockets, then verify launcher, navigation, settings, approvals, policy and shutdown. |
| Cage failure root cause | Unresolved | The prior exact-image log contains 2,602 `Basic output test failed for Virtual-1` lines in bursts while GTK rendered. The source test outcome and backend reason were not exposed. | Enable compatible diagnostic logging or instrument matching wlroots; test output modes and repeat under controlled changes. |
| Exact guest-observed text entry | Not completed on current image | Prior frames show malformed RFB text. QMP exact-query assertions were implemented and tested, but the final guest control socket refused the test client before input. | Resolve QMP/HMP socket lifecycle, then compare every query with the guest log. |
| Browser-driven noVNC input | Not tested | The current run's runner passed VNC TCP and noVNC HTTP checks only. Browser automation host was unavailable; no WebSocket or guest-visible browser input was established. | Use a supported browser-control host and verify typed guest state end to end. |
| Guest-initiated shutdown on current working-tree image | Not tested | Final QEMU instance stopped by host after control-socket failure; no current-image `poweroff.target` result is claimed. | Request poweroff inside guest and verify systemd, QEMU exit and port cleanup. |
| Full Python test suite | Passed | `python3 -m pytest shell/tests intelligence/tests scripts/tests -q`: 202 passed in 14.34 s. | Re-run lint and `git diff --check` after documentation edits. |
| Current deterministic intent/policy benchmark | Passed; no neural inference | `run_intent_benchmark(PKIntelligenceOrchestrator())`: 14/14 intent, 14/14 decisions, 2/2 adversarial rejections (100%); mean 0.05 ms. | Broaden independent evaluation; keep separate from model-quality evidence. |
| Dataset v2 integrity | Passed validation; limited coverage | `python3 -m intelligence.scripts.validate_dataset`: checksums valid, 60 training-source examples, 24 held-out, 0 ID overlap, GPL-2.0-or-later. | Add licensed examples and broader, independently reviewed held-out topics before training claims. |
| Current AI resource preflight | Training blocked; inference not run | WSL: 959 MiB available RAM, 2 GiB swap unused; RTX 3050 with 6 GiB VRAM, 223 MiB in use at preflight. `torch`, `transformers`, `datasets`, and `peft` absent; no verified model weights/license. | Keep the 4 GiB RAM gate closed; prepare a measured, safe plan before dependency or model installation. |

## Previous-image acceptance evidence

The following rows document the prior `0f81a42` or explicitly named older
images. They do not establish acceptance for the current working-tree image.

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| Reproducible image assembly | Guarded build passed; one earlier transfer artifact failed | [Guarded build log](../../build/output/verification-20261101-cage-instrumented/build/guard-build.log) records final image hash and GPT. An earlier unguarded output had an empty ESP and fell through to PXE. The assembler now validates the FAT32 boot sector before and after transfer; two regression tests cover valid and empty ESPs. | Verify the fallback EFI file itself and repeat independent builds. |
| Prior `0f81a42` x86-64 UEFI boot | Passed to visible GTK desktop | [Ready frame](../../build/output/verification-20261101-cage-instrumented/interactive-ui/00-after-session-active.png), 1280x800. Linux and launcher reached `Session ACTIVE`; workspace captures show visible output. Cage output-test warnings remain. | Diagnose repeated Cage output-test errors and retest reliability over longer runs/resolutions. |
| Prior exact-source image | Built and booted; interactive evidence captured | `verification-20261101-cage-instrumented/build/pk-os-cage-guard.raw`, 2,726,297,600 bytes; SHA-256 `1f36eb385cf3fef91058835d215e59cf512be738146be33ec6721641a0d702a6`; source commit `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` plus guest-tree patch SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`. | Root-cause Cage output warnings and expand acceptance coverage. |
| Prior `0f81a42` GTK/Cage desktop | Visible and interactive; reliability partial | Main/Code/Settings frames are in `verification-20261101-cage-instrumented/interactive-ui/`. `Alt+2`, `Alt+3`, and `Alt+1` changed views; Cage logged 2,602 Virtual-1 output-test failures. | Explain and fix or bound the Cage output-test failure; test additional resolutions and longer sessions. |
| Cage output failure diagnosis | Reproduced; cause unresolved | Serial logs contain 2,602 `Basic output test failed for Virtual-1` messages even though the desktop rendered and responded. The earlier `-D` attempt still records the incompatible Cage 0.1.4-4 option. See [display report](DISPLAY-RELIABILITY-REPORT.md). | Enable wlroots DEBUG logging compatibly and identify the failing test condition. |
| noVNC/VNC | Endpoint health passed; browser input untested | Runner verified loopback VNC TCP and noVNC HTTP. RFB keyboard and QMP pointer were used directly; no browser WebSocket/input test was made. | Test browser input after or alongside the display reliability investigation. |
| Prior `0f81a42` guest input | Workspace keys and some clicks delivered; exact text unreliable | Readiness-gated harness switched Main/Code/Settings, activated Hey PK controls, submitted `launch terminal`, and accepted Settings shutdown. Brightness text dropped/repeated characters. | Current-tree interaction remains open; resolve control sockets and rerun exact assertions. |
| Application launcher / allowlisted app | Launch request reached the tool; app missing | Current image response says `pk-terminal` is not installed; no app launch succeeded. Launcher buttons remain disabled. | Package a real allowlisted app and verify its lifecycle. |
| Navigation and keyboard | Passed for workspace switching | Readiness-gated `Alt+2`, `Alt+3`, `Alt+1` captures show Code, Settings, and Main. | Verify focus order across all controls; browser path remains untested. |
| Settings and approval | Accurate unavailable status verified; current approval incomplete | Current Settings frame says display brightness is unavailable and audio write access is unverified. Current brightness approval text was corrupted by RFB typing; approval/backend failure was verified on the earlier `819cbcd` image only. | Fix text input reliability, then verify confirmation and backend failure on latest image. |
| Guest diagnostics | Current image guest-sourced response verified | `06-live-system-status.png` reports uptime 311 seconds, free RAM 459 MB / total 702 MB, disk available 0.86 GB, and `PK-OS prototype`. | Check values under varied load and unavailable-source conditions. |
| Hey PK behavior | Deterministic fallback verified; inference not integrated | `07-deterministic-capabilities.png` labels `RULE-BASED` and no language model. `10-launch-terminal-response.png` reports the missing `pk-terminal`; system status response labels `pk-deterministic-assistant · deterministic / no LLM`. | Integrate a licensed local runtime and evaluate independently. |
| Guest shutdown | Latest guest UI shutdown verified | `18-shutdown-confirmation.png` shows explicit guest shutdown confirmation. After acceptance, serial reached `poweroff.target`, `reboot: Power down`; runner exited 0, ports 5999/6080 closed, and snapshot hash stayed unchanged. | Verify restart and repeated shutdown. |
| Visual palette and contrast | Earlier screenshot metrics only | 99.0% token match, 96.5% background-token coverage, and five 4.5:1 contrast pairs were measured on the earlier `819cbcd` screenshot, not recomputed on the latest image. The old 37.4% heuristic was not a visual regression score; a GTK text surface defect was fixed there. | Recompute measurable visual criteria on latest screenshots and review layout/focus/legibility. |
| Earlier full Python suite | Passed at earlier source state | WSL Python 3.12: **193 passed** before this continuation's QMP input adapter additions. | Current full suite result is 202 passed in the table above. |
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
