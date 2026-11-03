# PK-OS — Interactive Desktop Preview & Safe Exit Guide

This guide describes how to run and interact with the **PK-OS Graphical Desktop** inside QEMU from Windows 11 and WSL2. The VM is isolated from physical disks by the documented runner, but host resource use depends on the selected QEMU memory setting and available capacity.

---

## 1. Safety Guarantees for the Host Windows PC

- **Virtualized guest**: The documented runner attaches a virtual disk image. Review command-line options before using custom QEMU arguments or images.
- **Virtual Disk**: The system disk is a raw virtual disk image (`build/output/pk-os-dev.raw`), completely isolated from physical host storage.
- **Memory allocation**: The runner default is configurable; choose a value that fits available host/WSL resources.
- **Exit paths**: Guest shutdown and host-side QEMU termination are distinct; only guest shutdown exercises systemd poweroff.

---

## 2. Launching the Interactive Preview

### Method A: Windows PowerShell (Recommended)

From the root of the repository in Windows PowerShell:

```powershell
.\scripts\windows\preview.ps1
```

The script uses `build\output\pk-os-dev.raw` by default; pass `-DiskImage` to
select another image. It starts QEMU and the loopback VNC/noVNC services in
WSL2, then opens the preview URL unless `-NoBrowser` is set. TCP/HTTP readiness
does not prove that browser WebSocket input works. For reproducible acceptance,
use a dedicated artifact directory and monitor/QMP sockets as shown below.

   ```text
   http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale
   ```

### Method B: Linux / WSL2 Terminal

From inside WSL2 Ubuntu:

```bash
cd /mnt/c/Users/prasu/Downloads/pk-os
./scripts/run-qemu.sh --graphical --preview --memory=1024
```

Then open your Windows browser to:
[http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale](http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale)

Alternatively, connect with any native VNC client (e.g., TigerVNC, UltraVNC, TightVNC) to:

```text
127.0.0.1:5999
```

---

## 3. Safe Exit Paths to Return to Windows

### Path 1: Guest Graceful Shutdown (Recommended)

Inside the PK-OS graphical preview:
1. Click the red **Shut Down PK-OS** button in the top-right corner of the status panel, **or** click Workspace **3: Settings** and click **Shut Down PK-OS** under *System Lifecycle*.
2. The guest requests `sudo /bin/systemctl poweroff` (authorized under `/etc/sudoers.d/pkos`).
3. Verify systemd reaches `poweroff.target` in guest logs; this proves the guest shutdown path for that run.
4. The runner reports QEMU exit status and cleans up its tracked QEMU/noVNC children.

### Path 2: Host Terminal Exit

If the guest is unresponsive or you need to exit immediately:
- In the PowerShell or WSL terminal running QEMU, press `Ctrl-C` (or `Ctrl-A` then `X`).
- The QEMU virtual machine process will terminate immediately, freeing all virtual resources.
- *Note:* Hard termination does not allow the guest to flush unwritten buffers; use Guest Shutdown when testing state persistence.

---

## 4. Desktop Navigation & Acceptance Evidence

### Current-source Sway run — 2026-11-03

Fresh image `build/output/verification-20261102-sway-8e190fd-fixed4/pk-os-sway.raw`
(SHA-256 `0aac671a7cd1cc9d5e871be2d8a8d130fd3c60bba6bb26023c91752ddb66d7f7`)
booted in OVMF/KVM snapshot mode with 768 MiB and two CPUs. The GTK shell
appeared at 1280×800. QMP/HMP readiness and VNC/noVNC endpoint checks passed.
Evidence is in `build/output/verification-20261102-sway-8e190fd-fixed4/interactive/run-01/`;
see the [acceptance matrix](../testing/ACCEPTANCE-MATRIX.md) for the exact
interaction results. `Super+Return` opened `foot`; the shell displayed the
actual `SWAYSOCK` path. A RFB modifier chord repeated, however, and created
many terminal windows, so keyboard lifecycle and window-count acceptance is
open. The app button reported dispatch but its immediate frame showed no
terminal. The last VM was stopped after the input storm; clean guest shutdown
was verified on the preceding `fixed3` image. Browser noVNC input remains
untested.

The shell runs as a standard `User=pkos` Wayland session, while
`pk-intelligenced` is a system service. Keep this credential/session boundary
in mind when adding app dispatch; a successful daemon response is not proof a
client surface appeared.

### Historical 2026-11-02 baseline (superseded for current Sway status)

The latest accepted boot evidence is from commit `017638c`; the published
parent is now `8e190fd`, and the Sway/PK Terminal product changes in the
working tree have not yet been built into a guest image. The image is
`verification-20261102-qemu-control-017638c/build/pk-os-control-final.raw`
(SHA-256 `ea3e98e1c4f4911c0263cbcc150a889c021df3a016e3d5a83f2fd9016d5e8c4e`).
Run-04 screenshots and logs are under
`verification-20261102-qemu-control-017638c/interactive/run-04/`.

| Feature | Current verified behavior |
|---|---|
| Main/Code/Settings | `Alt+1/2/3` switches GTK stack views. These are not compositor workspaces. |
| Launcher / PK Terminal | The accepted image predates the new `pk-terminal` wrapper. Current source packages `foot` and an allowlisted `pk-terminal`, but guest launch is unverified and Cage still disables launcher entries. |
| Hey PK | Deterministic/rule-based status is explicit. Diagnostics use guest data; no neural inference or voice pipeline is active. |
| Settings | Brightness unavailable; audio write access unverified. A brightness request showed approval, cancellation explicitly made no change, and an approved attempt returned a backend error. |
| Guest text entry | Most strings, including punctuation and repeated characters, matched guest serial entries. The first single-character assertion was late and made the next assertion ambiguous. |
| Shutdown | Run-04 guest UI shutdown reached `poweroff.target` and `reboot: Power down`; QEMU exited 0. |
| Browser/noVNC | Not tested. Run-05 browser automation stopped before navigation; its owned QEMU process was terminated by cleanup, not guest poweroff. |
| Rendering | 1280×800 framebuffer; service sets software `WLR_RENDERER=pixman`. The archived log has 477 output-test failures; parser reports QEMU `-virgl`, no debug lines, and no measured FPS/frame timing/GPU use. |

The preview harness can be driven directly with `scripts/acceptance/qemu_ui.py`.
It sends RFB keyboard input, QMP absolute-tablet pointer input, and captures
frames. Use unique HMP/QMP sockets and an evidence directory for each run:

```bash
PKOS_MONITOR_SOCKET=/var/tmp/pkos-acceptance/hmp.sock \
PKOS_QMP_SOCKET=/var/tmp/pkos-acceptance/qmp.sock \
PKOS_ARTIFACT_DIR=/path/to/verification \
./scripts/run-qemu.sh --image=/path/to/pk-os.raw --preview --snapshot --memory=768
```

Wait for guest readiness before sending input. Example steps:

```json
[
  {"wait": 45}, {"screenshot": "main"}, {"key": "alt+2"},
  {"wait": 1}, {"screenshot": "code"}, {"key": "alt+3"},
  {"wait": 1}, {"screenshot": "settings"}
]
```

Then invoke `python3 scripts/acceptance/qemu_ui.py` with the same monitor and
QMP paths, plus `--steps` and `--output`. Do not treat VNC TCP or noVNC HTTP
health as browser-input verification. See the
[acceptance matrix](../testing/ACCEPTANCE-MATRIX.md) and
[display reliability report](../testing/DISPLAY-RELIABILITY-REPORT.md) for
full current-source evidence and known limitations.

To refresh the archived rendering diagnosis without changing the guest, run:

```bash
python3 scripts/acceptance/render_diagnostics.py \
  --log build/output/verification-20261102-qemu-control-017638c/interactive/run-04/qemu-boot.log \
  --service shell/src/compositor/pk-session.service \
  --output build/output/verification-20261102-qemu-control-017638c/render-diagnostics.json
```

Sway remains opt-in and Cage remains the default. The later current-source
boot does not close app-button or controlled multi-window acceptance; use the
current-source summary above rather than this historical table for those rows.

---

## 5. Verification Screenshot Evidence

The original QEMU framebuffer screenshot under `build/output/` is historical
(2026-10-19). The GTK desktop capture below is from the earlier image built
from commit `819cbcd` plus its captured working-tree patch; it is not the latest
`main` image:

- `build/output/verification-20261101-current/ui/00-exact-build-gtk-ready.png`
- 1280 × 800, captured from the 2026-11-01 image in snapshot mode.
- Screenshot analysis: 99.0% sampled token palette match within RGB distance 20;
  96.5% background-token coverage; five measured contrast pairs pass 4.5:1.
- These palette percentages are diagnostic only. They do not measure layout,
  legibility, focus behavior, or interaction success.

The latest guarded rebuild on `main` rendered the GTK/Cage desktop. The
readiness-gated captures under
`build/output/verification-20261101-cage-instrumented/interactive-ui/` show
Main, Code, Settings, live guest metrics, Hey PK, the missing Terminal result,
and the guest shutdown prompt. Cage logged 2,602 `Basic output test failed for
Virtual-1` errors during this run; display reliability remains open. The current
approval text test was inconclusive because RFB entry dropped/repeated
characters. The earlier unguarded image with a zero-filled EFI partition is a
separate failed artifact. See the
[display reliability report](../testing/DISPLAY-RELIABILITY-REPORT.md) and
[acceptance matrix](../testing/ACCEPTANCE-MATRIX.md) for the current status.

## 6. Historical current-source evidence — 2026-11-02

The image, build log, QEMU runner/serial logs, UI input JSON, and screenshots
are in `build/output/verification-20261102-qemu-control-017638c/`. The current
run used QMP/HMP control readiness; QMP reported running, HMP `info status`
reported running, the GTK desktop appeared at 1280×800, and guest shutdown
completed in run-04. The image SHA-256 before/after snapshot use was
`ea3e98e1c4f4911c0263cbcc150a889c021df3a016e3d5a83f2fd9016d5e8c4e`.

Run-04 retained 477 Cage `Basic output test failed for Virtual-1` messages.
Run-05 browser acceptance was not performed because the computer-use layer
could not confidently establish Chrome's current URL; cleanup stopped its
owned QEMU process before guest shutdown. No browser keyboard or pointer test
is claimed.
