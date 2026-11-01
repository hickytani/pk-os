# PK-OS — Interactive Desktop Preview & Safe Exit Guide

This guide describes how to run and interact with the **PK-OS Graphical Desktop** inside QEMU directly from Windows 11 and WSL2, with zero risk to the host machine and verified safe exit procedures.

---

## 1. Safety Guarantees for the Host Windows PC

- **No Host Modification**: PK-OS runs strictly inside an isolated QEMU virtual machine. It **never** touches Windows bootloader, UEFI NVRAM, or physical disks.
- **Virtual Disk**: The system disk is a raw virtual disk image (`build/output/pk-os-dev.raw`), completely isolated from physical host storage.
- **Host Resource Protection**: Memory allocation is capped at **1,024 MB RAM** (out of the host's 16 GB), preventing memory exhaustion or host slowdowns.
- **Graceful Clean Exits**: Safe exit paths are provided both from within the guest OS and from the host terminal.

---

## 2. Launching the Interactive Preview

### Method A: Windows PowerShell (Recommended)

From the root of the repository in Windows PowerShell:

```powershell
.\scripts\windows\preview.ps1
```

**What this does:**
1. Validates the existence and integrity of `build\output\pk-os-dev.raw`.
2. Starts QEMU with hardware KVM acceleration and Wayland graphical display inside WSL2.
3. Automatically launches the noVNC WebSocket proxy on port `6080`.
4. Opens your default Windows browser (Edge, Chrome, or Firefox) directly to:

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
2. The guest executes `sudo /bin/systemctl poweroff` (authorized under `/etc/sudoers.d/pkos`).
3. Systemd stops all active services (`pk-intelligenced`, `pk-session`, `dbus`, `systemd-logind`), unmounts filesystems cleanly, and signals ACPI poweroff.
4. The QEMU process terminates and your terminal returns to the Windows prompt.

### Path 2: Host Terminal Exit

If the guest is unresponsive or you need to exit immediately:
- In the PowerShell or WSL terminal running QEMU, press `Ctrl-C` (or `Ctrl-A` then `X`).
- The QEMU virtual machine process will terminate immediately, freeing all virtual resources.
- *Note:* Hard termination does not allow the guest to flush unwritten buffers; use Guest Shutdown when testing state persistence.

---

## 4. Desktop Navigation & Feature Audit

| Feature / Control | Location | Status | Real Behavior |
|---|---|---|---|
| **Workspace 1: Main** | Top bar or `Alt+1` | Keyboard switch verified on the immediately preceding image; final image boot screenshot captured | Contains disabled launchers, live diagnostics, and Hey PK. |
| **Workspace 2: Code** | Top bar or `Alt+2` | Keyboard switch and dark console rendering verified on the immediately preceding image | This is a GTK view, not a separate compositor workspace. |
| **Workspace 3: Settings** | Top bar or `Alt+3` | Keyboard switch verified on the immediately preceding image | Brightness reports unavailable; audio write access is not claimed until a write succeeds. |
| **Application launcher** | Main workspace | Blocked in current preview | Buttons are disabled because no desktop apps are packaged and Cage is single-client. No real launch is claimed. |
| **Hey PK diagnostics** | Main workspace | Deterministic query verified on the immediately preceding image | Returned guest uptime, memory, disk availability, and OS. UI says rule-based/no LLM. |
| **System-change approval** | Hey PK text entry | Approval and cancellation verified on the immediately preceding image | Cancel performs no retry; approval reaches the tool, which reports the missing brightness backend. |
| **Audio volume** | Settings | Backend failure observed; final source reports write access unverified | A `wpctl set-volume` call timed out. The UI now marks the control unavailable and disables further attempts after failure. |
| **Guest shutdown** | Top bar or Settings | Final serial log records systemd poweroff and clean QEMU exit; visible dialog observed on immediately preceding image | Restart behavior still needs verification. |
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
acceptance matrix records which checks used this harness and which still need a
confirmed final-image run.

---

## 5. Verification Screenshot Evidence

The original QEMU framebuffer screenshot under `build/output/` is historical
(2026-10-19), not current-source acceptance evidence. The current final-image
desktop capture is:

- `build/output/verification-20261023-final/ui/23-latest-gtk-ready-check.png`
- 1280 × 800, captured from the final image in snapshot mode.
- Screenshot analysis: 99.0% sampled token palette match within RGB distance 20;
  96.5% background-token coverage; five measured contrast pairs pass 4.5:1.
- These palette percentages are diagnostic only. They do not measure layout,
  legibility, focus behavior, or interaction success.
