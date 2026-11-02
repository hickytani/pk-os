# Cage Display Diagnostic — 2026-11-01

This follow-up is a diagnostic attempt, not a successful GTK acceptance run.

## Image and build

- Source commit: `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` on `main`.
- Build command: `python3 scripts/assemble_phase2e_disk.py --output build/output/verification-20261101-cage-debug/pk-os-cage-debug-logged.raw`.
- Build transcript: `build/output/verification-20261101-cage-debug/build.log`.
- Build-time patch: added `-D` to the Cage command; patch SHA-256 `86222FF2E390D8907B324F7C68EB02454DF989B4D99CAE951AA66C529897F02D`.
- Cached rootfs SHA-256: `c19c64acaef6b13a5503576380136970a2da4fa304a0a2d29d384084ba5aad8a`.
- Kernel SHA-256: `d8808aa4ca188560da1e6d749dcb930c87a5fd8b11ebff1f3fa6d728af35203d`.
- Initramfs SHA-256: `243ef5813759c6cce44d9d710f9bbb8e64fad5ca257d7f8a0c46d4b6f03f0f9d`.
- Image: `build/output/verification-20261101-cage-debug/pk-os-cage-debug-logged.raw`, 2,726,297,600 bytes; SHA-256 `3cb3a6962c65a60d691ebf1405ee3b27b1f5aac496bfbdab3f78656bf3ad227f`.
- QEMU: KVM, OVMF, 768 MiB, 2 CPUs, `virtio-vga`, loopback VNC/noVNC, snapshot mode.

## Observed result

The guest starts the graphical service, but Cage exits with `/usr/bin/cage:
invalid option -- 'D'`. Its usage lists lowercase `-d` for client-side
decorations and does not list `-D`; systemd restarts the service approximately
every 3–4 seconds. The cached Debian Bookworm rootfs reports Cage `0.1.4-4`.
Debian's [Bookworm Cage source](https://sources.debian.org/src/cage/0.1.4-4/)
identifies that package version; the newer upstream
[Cage option documentation](https://github.com/cage-kiosk/cage/blob/master/cage.1.scd)
includes a debug flag that this installed binary does not accept.

The guest did **not** reach GTK in this run. The monitor capture
`build/output/verification-20261101-cage-debug/ui/debug-gtk-ready.ppm` was
taken after 45 seconds; the filename is not evidence of GTK readiness. A first
non-root harness attempt could not access root-owned QEMU sockets; a root
invocation captured the frame. noVNC browser input was not tested.

The diagnostic VM received QEMU monitor `system_powerdown`; guest systemd
reached `poweroff.target` and serial ends with `reboot: Power down`. The runner
exited 0, snapshot hash remained unchanged, and no QEMU/noVNC listener remained
on ports 5999 or 6080.

## Conclusion

This run explains why the attempted debug flag was invalid. It does **not**
identify the cause of the original wlroots
`Basic output test failed for Virtual-1` messages. The original image journal
has no DEBUG-level reason, so the display issue remains unresolved and is not
accepted as reliable. Next, use a Cage 0.1.4-compatible diagnostic build that
enables wlroots DEBUG logging (or instrument the matching wlroots 0.15.1
source), then reproduce the original failure without suppressing it.

The full local run record, including the raw build transcript and serial log,
is in the ignored directory `build/output/verification-20261101-cage-debug/`.

The final full-suite rerun also exposed stale v2 dataset hashes: the manifest
contained hashes for CRLF variants while Git stores the JSONL sources as LF.
The source examples were unchanged. The manifest now records the SHA-256 values
for the committed LF bytes so clean Windows/WSL checkouts validate consistently.

## Exact-source rebuild attempt — EFI partition failure

A later rebuild was attempted from the then-current repository state to get a
fresh image for display diagnosis. It produced an unusable image and supersedes
any claim that this build itself passed current-source boot acceptance.

- Source commit: `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` (`main`).
- Guest-tree patch: `build/output/verification-20261101-cage-instrumented/source-guest-tree.patch`, SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`.
- Image: `build/output/verification-20261101-cage-instrumented/build/pk-os-cage-instrumented.raw`, 2,726,297,600 bytes, SHA-256 `fc5338a4aa61ca34c17ae632b19ae1c1441a608c3e83c182bcbdeb76680d7360`.
- Build transcript: `build/output/verification-20261101-cage-instrumented/build/build.log`. The assembler completed image population and transfer, but failed its final readback with `OSError: [Errno 5] Input/output error` while hashing the Windows-mounted path. The completed Linux-side temporary disk was copied to the verification path; the host file size and SHA-256 were then checked.
- QEMU: OVMF, KVM, 768 MiB, two CPUs, snapshot mode, `virtio-vga`; loopback VNC/noVNC and monitor/QMP sockets.
- Frame: `build/output/verification-20261101-cage-instrumented/ui/00-current-boot.png`. It shows OVMF falling through to PXE, not the PK-OS desktop. Serial output ends with PXE IPv4/IPv6 failures. GTK was not reached, so no desktop interactions were run against this image.
- Sector inspection: the GPT header and EFI System Partition entry are present; the root ext4 superblock/data are present at the declared root partition offset. The first sectors and sampled sectors of the declared ESP are all zero. OVMF therefore has no `EFI/BOOT/BOOTX64.EFI` to load. This points to an ESP population/assembly defect that must be isolated in `scripts/assemble_phase2e_disk.py` before another desktop test.
- A separate 16 MiB WSL loop/FAT probe successfully formatted and mounted a FAT32 partition, wrote a file, and retained the FAT boot sector after unmount. This rules out a general WSL loop/FAT write failure; the defect is specific to the assembler's ESP creation/population path or its handling of that image.
- After stopping this failed snapshot run, QEMU/noVNC processes were absent and only unrelated DNS listeners remained; ports 5999 and 6080 were closed. The image remains available unchanged for reproducing the failure.

This failed artifact is independent of the Cage output-test warning. The
guarded rebuild and QEMU run below later produced a valid ESP and reached the
current GTK desktop. The failed artifact is retained as evidence of the
intermittent empty-ESP/final-transfer failure; it is not the image used for the
interactive acceptance run.

## Guarded exact-source build and interactive QEMU run

The assembler now validates the GPT EFI partition's FAT32 boot sector after
unmount and again after copying the final artifact. Two regression tests
reject a zero-filled ESP and accept a valid FAT32 boot sector. A guarded build
completed and the resulting image booted into the current GTK/Cage session.

- Image: `build/output/verification-20261101-cage-instrumented/build/pk-os-cage-guard.raw`, 2,726,297,600 bytes.
- SHA-256 before and after snapshot runs: `1f36eb385cf3fef91058835d215e59cf512be738146be33ec6721641a0d702a6`.
- Source: commit `0f81a427c3e5c4980fc3826d35ac8785e351bd9a` on `main`; guest-tree patch SHA-256 `8478d75ac6b37a4c6f2c62a6f8fbbf4a2ad73070fcb6e2e7c2a946eb9e45ef78`. The image includes the then-current `shell/` and `intelligence/` trees and was built with the pre-copy ESP guard. The final artifact independently passed the post-copy ESP guard added afterward.
- Build transcript: `build/output/verification-20261101-cage-instrumented/build/guard-build.log`.
- QEMU: OVMF, KVM, 768 MiB, two CPUs, `virtio-vga`, snapshot mode, loopback VNC/noVNC, monitor and QMP tablet input.
- Ready frame: `build/output/verification-20261101-cage-instrumented/interactive-ui/00-after-session-active.png` (1280×800). It shows Main. `01-after-alt2.png`, `04-settings-after-transition.png`, and `05-main-after-transition.png` show Code, Settings, and Main after `Alt+2`, `Alt+3`, and `Alt+1` were sent after the serial `Session ACTIVE` marker.
- Live diagnostics: `06-live-system-status.png` shows uptime 311 seconds, free RAM 459 MB of 702 MB, 0.86 GB available disk, and `PK-OS prototype`; the UI labels the engine `pk-deterministic-assistant · deterministic / no LLM`.
- Hey PK: `07-deterministic-capabilities.png` labels the assistant `RULE-BASED` and says no language model is active. A real `launch terminal` request in `10-launch-terminal-response.png` reports that `pk-terminal` is not installed. No application launched.
- Settings: `04-settings-after-transition.png` says the display-brightness interface is unavailable and audio write access is unverified. A current-image approval request was not successfully submitted: the RFB text path dropped/repeated characters, so no approval prompt is claimed for this run. An approval prompt and missing-backend error were verified on the earlier `819cbcd` image.
- Guest shutdown: `18-shutdown-confirmation.png` shows the GTK confirmation. The confirmation was accepted through QMP pointer input; systemd reached `poweroff.target`, serial ended with `reboot: Power down`, and the runner exited 0. VNC port 5999 and noVNC port 6080 had no remaining listeners. The snapshot image hash was unchanged.
- noVNC TCP/HTTP health passed, but browser-driven WebSocket/input was not tested. RFB keyboard and QMP pointer input were used directly.
- Cage still logged 2,602 instances of `Basic output test failed for Virtual-1` during the long run, despite rendering the desktop and accepting the interactions above. The log is `build/output/verification-20261101-cage-instrumented/interactive-ui/qemu-boot.log`. The failure's root cause remains unknown.

The current-source image therefore passes Linux boot and demonstrates real,
visible desktop interactions. Cage output reliability, current-image approval
text entry, browser input, a usable Terminal application, and verified
brightness/audio backends remain open acceptance items. The 2026-10-19 image
and the earlier `819cbcd` GTK image are separate historical artifacts.

## Post-acceptance continuation audit — 2026-11-01

This section records a separate build from the current clean `main` checkout;
it does not replace the interactive evidence above.

- Source: `main`, commit `a84de7a16f0324291b280e1581bb2002887b801e`, clean
  before this documentation update.
- Build: `python3 scripts/assemble_phase2e_disk.py --output
  build/output/verification-20261101-post-acceptance-a84de7a/build/pk-os.raw`
  as root in WSL, using `/var/tmp/rootfs.tar` and the assembler's cached kernel
  inputs. The assembler completed all five stages and its FAT32 ESP guard.
- Image: `build/output/verification-20261101-post-acceptance-a84de7a/build/pk-os.raw`,
  2,726,297,600 bytes, SHA-256
  `4e4df74ed24826a8ffe55c07f7f25c48672259c9e69422e465e57f403d0e2be5`.
- QEMU: snapshot mode, KVM, OVMF, `virtio-vga`, 768 MiB, two CPUs, loopback
  VNC/noVNC on 5999/6080, dedicated monitor and QMP sockets.
- Boot: the exact image reached the guest log's `Session ACTIVE` marker and
  reported 1280×800. The host ran out of paging-file capacity before a
  current-image screenshot or input actions were captured. No current-image
  RFB, browser input, approval, or shutdown result is claimed. The runner
  session ended from the host; guest-initiated shutdown was not verified.
- The QEMU runner confirmed VNC TCP and noVNC HTTP reachability only. The
  computer-use browser inventory reported that its browser host was
  unavailable, and Chrome was no longer present as a targetable window after
  the host resource failure. Browser WebSocket and input remain NOT TESTED.

### Cage failure analysis

The 2,602 failures belong to the prior `0f81a42` image run and remain
unexplained. They occur in bursts in its serial log (including at 63.9 s and
101–109 s), while the same run rendered and accepted some input. This proves
the output test failed; it does not identify whether the rejected state was a
mode, buffer, renderer, or DRM test. Current-source development did not expose
the wlroots test result because the build uses Cage's non-debug `WLR_ERROR`
logging. The `-D` attempt was invalid for that packaged binary and is not a
diagnostic fix. No error suppression or compositor substitution was made.

The first current-commit build's assembler output was returned to the terminal
without a persistent transcript. The later final build has a saved transcript
at `build/output/verification-20261101-post-acceptance-a84de7a/build/qmp-text-final-build.log`.
Its boot log is
`build/output/verification-20261101-post-acceptance-a84de7a/interactive/guest-run-07/qemu-boot.log`.
Earlier evidence directories remain unchanged.

### RFB text input investigation

The old image's `12-approval-prompt.png` does not show an approval prompt: the
assistant reports malformed request text (`o 50'`). Its retry frame
`14-brightness-approval-response.png` shows only `set brig` in the entry and
the prior malformed response below it. These frames are evidence of failed
input, not approval. The RFB client emits correctly sized key-event packets
and applies a 50 ms key hold plus a 120 ms inter-character interval, but those
send-side properties do not confirm guest receipt. No exact expected-versus-
observed text assertion or current-image input run was completed in this
continuation. The failure's cause remains undetermined.

### Live AI resource status

At preflight, WSL reported 1.4 GiB total memory, 959 MiB available, and 2 GiB
swap with none used. `nvidia-smi` reported an RTX 3050 with 6 GiB VRAM and 223
MiB in use at that time. Python had `pytest` and Pillow, but not `torch`,
`transformers`, `datasets`, or `peft`. The existing 60-example training source
and 24-example held-out set remain the only recorded dataset evidence. Model
weights and verified model-license evidence are absent; no inference or
training occurred. The conservative 4 GiB host-RAM gate therefore remains
closed even with the GPU present.

### Follow-up: QMP text path and final current-tree run

The first text-test iteration exposed two harness defects before it could
complete: printable `+` was parsed as a chord separator, then the QMP qcode
validator rejected named punctuation. Regression tests now cover literal-plus
handling, punctuation qcodes, and exact/partial/duplicate guest query matching.
The focused acceptance tests passed 13/13; the full suite later passed 202
tests.

The final working-tree image was rebuilt with the guarded documented
assembler. Its persistent transcript is
`build/output/verification-20261101-post-acceptance-a84de7a/build/qmp-text-final-build.log`.
Image `pk-os-qmp-text-final.raw` is 2,726,297,600 bytes with SHA-256
`84531c96a2882a17d6dac68c27c488be8eefac918412c2b494e3ed21d79dccea`. It was
built from commit `a84de7a16f0324291b280e1581bb2002887b801e` plus the
acceptance source patch to `scripts/acceptance/qemu_ui.py` and its tests,
SHA-256 `35dfca32a46019931e508fd4e88a4f3fdfceed1368cf819c3bbf392ee6919b92`.
QEMU used KVM, OVMF, `virtio-vga`, snapshot mode, 768 MiB,
and two CPUs. The guest reached `Session ACTIVE` at 1280×800. Cage output-test
failures continued; 192 were logged before the harness stalled.

The QEMU process command line confirmed it had loaded this exact final image,
but both its HMP monitor and QMP Unix sockets returned `Connection refused`
when probed. It continued holding loopback VNC port 5999, preventing a second
runner. The identified acceptance process was stopped by host `SIGTERM`; port
5999 was then released and no QEMU process remained. No current-tree screenshot,
typed query, approval, launch, settings, or guest-shutdown result is claimed.
This is a concrete acceptance-harness blocker, not evidence that the desktop
interaction passed.

Two earlier QMP runs help isolate the harness issues but are not acceptance
passes: the first rejected the adapter's `dot` key name; the second reached
QEMU, typed through most punctuation, then QEMU rejected `grave`. The mapping
was changed to `grave_accent_and_tilde` and covered by tests. The final image
contains that change, but control-channel refusal prevented runtime
confirmation. Images, scripts, build transcripts, and logs for each attempt
remain in the separate verification directory; historical artifacts were not
overwritten.

The requested noVNC browser interaction remains NOT TESTED. Browser automation
was unavailable, and TCP/HTTP health checks do not prove a WebSocket or guest
input path. Current-source approval, launcher behavior, policy rejection,
settings status, live diagnostics, and guest-initiated shutdown are also
unverified because no input event reached the final guest.

## QEMU control and exact-image acceptance — 2026-11-02

This run addresses the prior QMP/HMP refused-connection symptom at the runner boundary. The prior low-level refusal cause was not uniquely isolated. The revised runner checks the QMP greeting, negotiates capabilities, requires `query-status` to report running, reads an HMP prompt and `info status`, tracks the QEMU child PID, and refuses pre-existing socket paths. A repeated real-QEMU integration test also exercised two start/stop cycles and accepted the QMP `grave_accent` keycode. This verifies the revised control path; it does not prove what caused the old refusal.

### Image identity and boot

- Repository branch and commit: `main`, `017638c0df444828b7b1bca1d4976170ceb63396` (`docs: record current-source acceptance findings`). The packaged guest trees were at this commit; the uncommitted changes at image build were in host-side acceptance scripts/tests.
- Build: `python3 scripts/assemble_phase2e_disk.py --output .../build/pk-os-control-final.raw`, using documented cached Debian rootfs/kernel inputs. Build log: `build/output/verification-20261102-qemu-control-017638c/build/final-build.log`.
- Image: `build/output/verification-20261102-qemu-control-017638c/build/pk-os-control-final.raw`, 2,726,297,600 bytes, SHA-256 `ea3e98e1c4f4911c0263cbcc150a889c021df3a016e3d5a83f2fd9016d5e8c4e`.
- QEMU: OVMF, KVM, 768 MiB RAM, two CPUs, `virtio-vga`, snapshot mode, preview VNC/noVNC. QMP and HMP both reported the VM running. Guest reached `Session ACTIVE` and framebuffer size 1280×800.
- Runner log: `build/output/verification-20261102-qemu-control-017638c/interactive/run-04/runner.log`; serial log: `.../run-04/qemu-boot.log`.

### Guest interaction outcomes

Screenshots and structured input records are under `build/output/verification-20261102-qemu-control-017638c/interactive/run-04/ui/`.

- Alt+2, Alt+3, and Alt+1 switched GTK Code, Settings, and Main views. They are stack pages, not independent OS workspaces.
- Exact mixed-case, spaces, punctuation, sequential, and repeated-character queries appeared in the guest serial log. The one-character `a` assertion timed out, and the next `AaZz0123` assertion also saw the late `a` entry, so those first two checks are ambiguous. The newer complete-line parser made repeated text pass; it did not retroactively repair the one-character timing window.
- `set brightness to 50` produced a visible approval dialog. Cancel produced the explicit “Request cancelled; no system change was made” response. A second request was accepted and reported a backend error; no brightness change is claimed.
- `launch terminal` reached the assistant but did not launch an app: `pk-terminal` is missing from the image. `run shell command whoami` was received as text but did not execute a shell command; the assistant displayed an offline/IPC error. This confirms request rejection/error reporting, not shell tool execution.
- Settings report brightness unavailable and audio write access unverified. The application launcher entries remain disabled in the current single-client Cage shell.
- The UI shutdown confirmation was accepted; guest logs show `poweroff.target`, `Powering off`, and `reboot: Power down`. The QEMU runner exited 0, its owned noVNC/QEMU processes exited, and the preview ports were released. The snapshot image hash remained unchanged.
- The log contains 477 `Basic output test failed for Virtual-1` messages during this run. GTK still rendered, but the Cage/wlroots failure cause is not known.

### Browser preview and rendering limits

A separate run-05 preview reached session startup and passed QMP/HMP readiness. The computer-use browser layer stopped before navigation because it could not establish Chrome's current URL with sufficient confidence. That preview then exited through its cleanup trap, which terminated its owned QEMU process; guest poweroff was not verified for run-05. No browser-driven noVNC keyboard or pointer input is claimed. TCP/HTTP endpoint health alone is not browser acceptance.

The service selects `WLR_RENDERER=pixman`, so this image uses the software renderer. QEMU provides a 1280×800 framebuffer observation. Renderer diagnostics beyond that, DRM modes, present timestamps, frame-time distribution, FPS, dropped frames, and GPU utilization were not collected. The 37.4% palette score remains a flawed heuristic, not a visual regression metric; no new quantified visual score was run.

### AI and product scope

The intent benchmark's 14/14 deterministic results are planner/policy checks, not neural model results. No model inference, training, wake-word detection, STT, or TTS occurred. The last recorded training preflight was blocked by insufficient RAM, absent ML dependencies, model weights, and model licensing. Dataset v2 remains 60 training-source and 24 held-out examples; it was not expanded in this sprint. The current assistant, app launcher, metrics view, settings, and in-memory window model do not constitute a finished desktop: no functional PK Terminal/Files/Store or compositor-backed multi-window/workspace management is included.

The old QMP/HMP refused connections were fixed at the orchestration/readiness layer, but the underlying old socket refusal was not traced to a single cause. A follow-up regression test caught a QMP powerdown helper bug: it did not leave the acknowledgement loop after `qmp_capabilities`, so it never sent the requested shutdown command. The helper now advances correctly; two protocol tests cover success and QMP rejection. The run-04 guest UI shutdown succeeded independently of that helper. Browser acceptance, Cage output diagnostics, app lifecycle, robust first-character input, expanded AI data, and viable trained-model evidence remain open. No commit or push was made.

### Fresh AI/data preflight

The small deterministic check was rerun on 2026-11-02: 14/14 intent cases,
14/14 policy decisions, and 2/2 adversarial rejections (100%); mean latency
0.03 ms on this run. Dataset v2 validation passed: 60 training-source records,
24 held-out records, checksum-valid, zero ID overlap, declared
`GPL-2.0-or-later`. These results are not neural inference or model-quality
metrics.

A fresh WSL resource snapshot reported 1,397 MiB total RAM, about 930 MiB available
at capture, 2 GiB swap with 0 used, Intel Core i5-13450HX (16 logical CPUs),
448 GiB free on the workspace volume, and RTX 3050 Laptop GPU with 6,144 MiB
VRAM / 5,824 MiB free. The fail-closed preflight measured 649,183,232 bytes
available RAM and 6,106,906,624 bytes free GPU memory. It
blocked training: no local model directory or weights, no model license, and
`torch`, `transformers`, `datasets`, and `peft` missing; RAM was below 4,096
MiB. No model/dependency download and no training run occurred. The serialized
preflight is `build/output/verification-20261102-qemu-control-017638c/ai/current-preflight.json`.
The current dataset still has only 60/24 examples and was not expanded; human
quality review and external voice-dataset/model license review are still open.
