# PK-OS Acceptance Matrix

Evidence capture date: **2026-11-01**. Current-image boot and direct guest
interaction evidence are in the ignored artifact directory
`build/output/verification-20261101-current/`. Browser-driven noVNC interaction
is not included; all features remain at their demonstrated level.

| Requirement | Status | Evidence | Remaining work |
|---|---|---|---|
| Reproducible image assembly | Built from current guest sources | [Build log](../../build/output/verification-20261101-current/build.log); cached rootfs/kernel; image checksum in `SHA256SUMS`. Image source commit and working-tree patch are described in README. | Rebuild from a newly bootstrapped base rootfs and compare artifacts across independent builds. |
| Current-source x86-64 UEFI boot | Passed | Current [GTK ready screenshot](../../build/output/verification-20261101-current/ui/00-exact-build-gtk-ready.png), 1280×800; serial log shows systemd/Cage/GTK. Image SHA-256 before and after snapshot: `d8770ee3a1fb6d2be44918f278a66590d2286d393a445746496fd81d1fc4f8a5`. | Repeat on release hardware and separately verify recovery. |
| GTK/Cage desktop | Boot and interaction partial | Current-image workspace, settings, and diagnostics captures are under `verification-20261101-current/ui/`. | Guest log repeatedly reports `Basic output test failed for Virtual-1`; diagnose output lifecycle and test more sizes/durations before marking reliable. |
| noVNC/VNC | Local endpoint health only | VNC TCP and noVNC HTTP were reachable. Runner binds both services to loopback. | Browser-driven websocket/input was not tested; endpoint health is not input acceptance. |
| Repeatable guest input | Direct RFB/QMP harness exercised | `scripts/acceptance/qemu_ui.py` uses RFB keyboard, QMP absolute-tablet pointer, and monitor screenshots. Current captures show Alt+2/Alt+3 navigation, toggle click, keyboard focus, assistant, approval dialog, backend failure, and shutdown confirmation. RFB pacing and monitor-error parsing have regression tests. | Repeat from browser/noVNC after resolution of output-test errors; test keyboard traversal across all controls. |
| Application launcher / allowlisted app | Blocked in current preview | Current guest request `launch terminal` returned that `pk-terminal` is not installed; no app launch is claimed. | Package at least one real allowlisted application and verify lifecycle management beyond Cage's single-client model. |
| Navigation and keyboard | Current image, partial pass | RFB `Alt+2` and `Alt+3` switched to Code and Settings; Tab placed visible focus on Shutdown. Current screenshots are `01-exact-build-code-workspace.png`, `02-exact-build-settings-workspace.png`, and `23-exact-settings-keyboard-focus.png`. | Verify all controls' focus order and browser/noVNC event path. |
| Settings and approval | Failure reporting verified; controls incomplete | Current image shows unavailable brightness. Exact `set brightness to 50` produced a confirmation prompt; after approval the tool returned `no verified guest-system backend configured`. No change was claimed. | Implement verified brightness/audio backends and confirm state changes against the guest device. |
| Guest diagnostics | Current image verified | `04-exact-build-live-status.png` displays uptime, memory, disk, OS, and deterministic engine status queried from guest sources. | Exercise unavailable-source states and cross-check values under varied guest load. |
| Hey PK behavior | Deterministic fallback verified; neural inference not integrated | `07-exact-build-assistant-capabilities.png` identifies `pk-deterministic-assistant`, deterministic, no LLM. Adversarial prompt rejection is captured in `11-exact-build-adversarial-result.png`. | Integrate a licensed local runtime/model and evaluate model outputs independently. |
| Guest shutdown | Current guest shutdown verified | `24-exact-shutdown-confirmation.png` records prompt; serial log reaches `poweroff.target` and `reboot: Power down`; runner reports exit 0. Image before/after SHA-256 matches. Port query showed no listener on 5999/6080 after exit. Windows process inventory was denied, so process absence was not independently enumerated. | Verify restart and repeated shutdown from other controls. |
| Visual palette and contrast | Corrected metric; visual fix verified | Fresh screenshot: 99.0% within RGB distance 20 of a declared color token, 96.5% background-token coverage. Five declared text/control pairs pass 4.5:1 (minimum measured 5.42:1). The old 37.4% figure came from a hard-coded heuristic, not a visual regression measurement. The old GTK text view did have a real gray-surface defect; CSS now resets the `GtkTextView` surface and a guest capture showed the correction. | Add layout/focus/legibility review across screen sizes; palette coverage remains diagnostic, not an acceptance score. |
| Full Python suite | Passed | WSL Python 3.12: **191 passed** on 2026-11-01, including six runner/input regression assertions. | Run release CI and platform-specific checks. |
| Repository lint | Passed | `scripts/lint.sh`, `bash -n scripts/run-qemu.sh`, and `git diff --check` passed on 2026-11-01. | Run release CI and platform-specific checks. |
| Intent benchmark | Passed; planner/policy only | [Report](../../build/output/verification-20261023-interactive/intelligence-report.json): 14/14 intent, 14/14 policy decisions, 2/2 adversarial rejections (100%), mean 0.14 ms. Not inference or model-quality evidence. | Expand independent intent and adversarial evaluation. |
| Assistant response dataset | Passed integrity checks; limited coverage | v2 now has 60 training-source and 24 held-out records; manifest SHA-256 values pass, IDs are unique, train/test overlap is 0, declared license is GPL-2.0-or-later. | Human-review factual accuracy and broaden independent topic/language coverage; topic overlap remains. |
| Training preflight | Correctly blocked; no training | 60 records pass the count gate. Preflight found no local model directory/weights/license, missing `torch`, `transformers`, `datasets`, `peft`, and about 586 MiB available WSL RAM versus a conservative 4096 MiB minimum. GPU free memory was reported separately; it does not remove the CPU RAM gate. | Choose a specific licensed low-resource inference/training stack and produce a measured resource plan before installing or downloading anything. |
| Neural inference / training | Not run | No local model artifact was present; training dependencies were absent; no inference or training occurred. | Verify a real local model run and saved artifact before making either claim. |
| System controls, privilege separation, updates, recovery, hardening, distribution, phone/AOSP | Roadmap only | No complete end-to-end acceptance evidence. | Implement narrow privileged services, real device controls, signed updates/rollback, recovery, security hardening, reproducible release packaging, and future phone/AOSP support. |

## Current image record

- Branch at build: `feat/premium-gtk-shell`; commit `819cbcd8f8eaacd6dcb3ca4a27b2777ecd35847d` plus captured working-tree patch.
- Image: `build/output/verification-20261101-current/pk-os-current.raw`, 2,726,297,600 bytes; SHA-256 above. Separate from historical artifacts.
- Build: `scripts/assemble_phase2e_disk.py --output .../pk-os-current.raw`; cached Debian rootfs and kernel inputs; GPT/UEFI, 2600 MB image.
- QEMU: KVM, OVMF UEFI, 768 MiB RAM, 2 CPUs, snapshot mode, VNC/noVNC, optional QMP tablet socket. Final guest log and runner cleanup evidence are in the verification directory.
- The October 19 screenshots under `build/output/` remain historical and are not current-source evidence.

Do not promote a feature because a screen, API, or unit-test double exists. Keep
each feature at its demonstrated level until current-image evidence covers its
real guest effect and failure path.
