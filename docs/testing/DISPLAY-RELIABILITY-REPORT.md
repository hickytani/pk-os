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
