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

## 4. Desktop Navigation & Feature Audit

The interaction statuses below combine current-source checks from
`verification-20261101-cage-instrumented/interactive-ui/` with older checks
explicitly labeled as such. The current image rendered the desktop and
responded to workspace and pointer input, with repeated Cage output-test errors.

| Feature / Control | Location | Status | Real Behavior |
|---|---|---|---|
| **Workspace 1: Main** | Top bar or `Alt+1` | Current image captured | Includes disabled app launchers, live guest diagnostics, and deterministic Hey PK. |
| **Workspace 2: Code** | Top bar or `Alt+2` | Current image keyboard switch captured | A GTK view, not a separate compositor workspace. |
| **Workspace 3: Settings** | Top bar or `Alt+3` | Current image keyboard switch captured | Brightness explicitly unavailable; audio write access unverified. |
| **Application launcher** | Main workspace | Current request failed honestly | `launch terminal` reports `pk-terminal` is not installed; no app launched. |
| **Hey PK diagnostics** | Main workspace | Current image query captured | Returned guest uptime, RAM, disk, and OS; UI identifies deterministic/no LLM. |
| **System-change approval** | Hey PK text entry | Earlier image verified; current text entry inconclusive | Earlier brightness request showed approval and missing-backend failure. Latest RFB text input dropped/repeated characters, so this flow remains unverified on the latest image. |
| **Audio volume** | Settings | Current write access unverified | UI says audio sink detected via `wpctl`, write access unverified. An earlier `wpctl set-volume` request timed out. |
| **Guest shutdown** | Settings | Current GTK confirmation accepted; systemd reached `poweroff.target`; QEMU runner exited 0 | Restart behavior still needs verification. |
| **Wake-word preference** | Settings | Preference only | No microphone capture or wake-word inference is active. |
| **Floating / tiled windows** | Compositor | Unsupported in Cage | Requires a multi-window compositor and application lifecycle management. |

### Controllable acceptance input without a browser

The preview can be driven without browser automation by using
`scripts/acceptance/qemu_ui.py`. The harness sends RFB keyboard input, QMP
absolute-tablet pointer input, and captures frames through QEMU's monitor. Start
the preview with stable monitor and QMP sockets:

```bash
PKOS_MONITOR_SOCKET=/var/tmp/pkos-acceptance/monitor.sock \
PKOS_QMP_SOCKET=/var/tmp/pkos-acceptance/qmp.sock \
PKOS_ARTIFACT_DIR=/path/to/verification \
./scripts/run-qemu.sh --image=/path/to/pk-os.raw --preview --snapshot --memory=768
```

Wait until a monitor screenshot visibly shows the GTK desktop before sending
input; VNC/noVNC endpoint checks can pass while systemd is still booting. Store a
JSON list of actions such as:

```json
[
  {"wait": 45},
  {"screenshot": "main"},
  {"key": "alt+2"},
  {"wait": 1},
  {"screenshot": "code"},
  {"key": "alt+3"},
  {"screenshot": "settings"}
]
```

Then run:

```bash
python3 scripts/acceptance/qemu_ui.py \
  --monitor-socket /var/tmp/pkos-acceptance/monitor.sock \
  --qmp-socket /var/tmp/pkos-acceptance/qmp.sock \
  --steps /path/to/steps.json --output /path/to/verification/ui
```

Use keyboard activation after focusing a control when a pointer click only
places focus. Keep the frame and guest log for every claimed action. The
acceptance matrix records which checks used this harness. Latest guest evidence
is under `build/output/verification-20261101-cage-instrumented/interactive-ui/`;
the guest log has 2,602 Cage output-test failures despite the rendered frames,
so display reliability remains open. Browser-driven noVNC input was not tested.

A follow-up Cage logging diagnostic is recorded in the
[display reliability report](../testing/DISPLAY-RELIABILITY-REPORT.md). Its
temporary `-D` flag was rejected by the installed Cage 0.1.4-4 package; that
diagnostic image never reached GTK and does not count as desktop acceptance.

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
