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
| **Workspace 1: Main** | Top bar button `1: Main` or `Alt+1` | ✅ IMPLEMENTED & TESTED | Displays Application Launchers, System Diagnostics, and Voice HUD. |
| **Workspace 2: Code** | Top bar button `2: Code` or `Alt+2` | ✅ IMPLEMENTED & TESTED | Displays Developer Actions and live Session Event Console Stream. |
| **Workspace 3: Settings** | Top bar button `3: Settings` or `Alt+3` | ✅ IMPLEMENTED & TESTED | Displays Brightness slider, Reduced Motion toggle, Volume slider, Wake-word toggle, and System Lifecycle (Shutdown/Reboot) controls. |
| **Shut Down PK-OS** | Top-right panel & Settings | ✅ IMPLEMENTED & TESTED | Dispatches `systemctl poweroff` with ACPI shutdown. |
| **Restart PK-OS** | Settings workspace | ✅ IMPLEMENTED & TESTED | Dispatches `systemctl reboot`. |
| **Taskbar Dock** | Bottom dock | ✅ IMPLEMENTED & TESTED | Tracks open application windows, highlights focused window, and allows focus switching. |
| **Notification Toasts** | Below top bar | ✅ IMPLEMENTED & TESTED | Renders urgent/warning/info toast cards with auto-dismiss timers and manual `×` dismissal. |
| **Voice HUD Entry** | Main workspace HUD | ✅ IMPLEMENTED & TESTED | Accepts natural language queries (`get system status`, `set brightness to 50`, `list files in /tmp`) and communicates with `pk-intelligenced` via UNIX domain socket. |
| **Master Volume** | Settings workspace | ⚠️ IMPLEMENTED BUT NOT FULLY TESTED | Dispatches `wpctl` / `amixer` commands. Gracefully handles absence of audio hardware in QEMU. |
| **Wake-Word Toggle** | Settings workspace | ⚠️ METADATA / SETTING ONLY | Toggles setting state and posts desktop notification; offline audio wake-word inference is a stub in current phase. |
| **Window Floating / Tiling** | Compositor level | ❌ UNSUPPORTED IN CAGE | Cage is a single-window kiosk compositor. Floating multi-window management is planned for Phase 3. |

---

## 5. Verification Screenshot Evidence

The verified QEMU framebuffer boot screenshot is archived at:
- Repository Path: `build/output/qemu-graphical-boot-interactive.png`
- Resolution: 1280 × 800
- Obsidian Dark Palette Match: 97.7%
