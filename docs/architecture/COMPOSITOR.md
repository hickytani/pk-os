# PK-OS Compositor Architecture

> **Status:** Phase 2A — cage-based single-surface Wayland session  
> **ADR:** [ADR-004](../adr/ADR-004-graphical-runtime.md)

---

## Overview

The PK-OS graphical session is driven by a two-process model:

```
systemd (user session)
  └─ pk-session.service
       └─ cage -d -- python3 -m shell.launcher
            ├─ Top-layer panel surface     (ShellLayer.TOP)
            └─ Overlay-layer HUD surface   (ShellLayer.OVERLAY)

systemd (user session)
  └─ pk-intelligenced.service
       └─ python3 -m intelligence.daemon
            └─ UNIX socket: /run/pk-intelligenced/control.sock
```

---

## Component Responsibilities

### cage(1)

cage is a minimal wlroots-based kiosk compositor.  It manages:

- KMS/DRM device acquisition and mode-setting
- Wayland socket creation (`$XDG_RUNTIME_DIR/wayland-N`)
- Input event routing (libinput → Wayland seat)
- Single-client surface composition and VT switching (`-d` flag)

cage does **not** manage window decorations, multiple toplevels, or an IPC
protocol of its own.

### CompositorManager (`shell/src/compositor/pk_compositor.py`)

Python class responsible for:

1. Resolving the `cage` binary in `PATH`
2. Building the cage command with correct client argv
3. Setting `WLR_RENDERER`, `WLR_NO_HARDWARE_CURSORS`, and `WAYLAND_DISPLAY`
4. Polling `$XDG_RUNTIME_DIR/wayland-N` until the socket appears
5. Exporting `WAYLAND_DISPLAY` into the process environment
6. Graceful `SIGTERM` / `SIGKILL` stop with configurable grace period

### Shell Launcher (`shell/launcher.py`)

The Wayland client that cage hosts.  It:

1. Validates `WAYLAND_DISPLAY` is set
2. Detects display geometry to choose the correct `FormFactor`
3. Instantiates `ShellSession` and transitions through the state machine
4. Attaches TOP-layer (panel) and OVERLAY-layer (voice HUD) surfaces
5. Runs a signal-driven event loop until `SIGTERM` / `SIGINT`

---

## State Machine

```
CompositorState.STOPPED
    │  start()
    ▼
CompositorState.STARTING   ← cage launched, waiting for Wayland socket
    │  socket appears
    ▼
CompositorState.RUNNING    ← WAYLAND_DISPLAY exported
    │  stop() or crash
    ▼
CompositorState.STOPPING / CRASHED
    │
    ▼
CompositorState.STOPPED
```

The `ShellSession` state machine (`session/lifecycle.py`) advances in lock-step:

| CompositorState | ShellSession state |
|-----------------|-------------------|
| STARTING        | INIT              |
| RUNNING         | READY → ACTIVE    |
| STOPPING        | TERMINATED        |

---

## QEMU Rendering

QEMU exposes `virtio-gpu` as the display device.  wlroots renders via:

| Priority | Backend | Condition |
|----------|---------|-----------|
| 1 (preferred) | Vulkan / `VK_DRIVER_ID_MESA_LVPIPE` | Mesa llvmpipe always available |
| 2 | GLES2 / `libGL` | Fallback if Vulkan init fails |
| 3 | Pixman software | Last resort; no GPU dependency |

Environment variables set by `CompositorManager`:

```bash
WLR_RENDERER=vulkan          # prefer Vulkan (llvmpipe in QEMU)
WLR_NO_HARDWARE_CURSORS=1    # virtio-gpu has no cursor plane
LIBGL_ALWAYS_SOFTWARE=0      # use HW acceleration on bare metal
```

---

## Security Hardening

The `pk-session.service` unit applies:

| Control | Setting |
|---------|---------|
| New privileges | `NoNewPrivileges=true` |
| Tmp isolation | `PrivateTmp=true` |
| Home access | `ProtectHome=read-only` |
| Filesystem writes | Only `/run/user/%U`, `/tmp`, `/var/log` |
| Capabilities | `CAP_SYS_TTY_CONFIG` only (VT switching) |
| Memory | `MemoryMax=512M` |

---

## Phase 3 Migration Path

When Phase 3 introduces multi-window management, cage is replaced by `labwc`
or a custom wlroots compositor:

1. Update `ExecStart` in `pk-session.service`
2. Update `_DEFAULT_CLIENT` in `CompositorManager` or pass `client_cmd=[]`
3. The `ShellSession` state machine and all layer-shell surfaces continue
   unchanged

No changes to the PK-Shell or PK Intelligence daemon are required.

---

## Testing

```bash
# Run compositor unit tests (no cage binary needed)
python3 -m pytest shell/tests/test_compositor.py -v

# Full graphical session test (WSL2 with QEMU):
./scripts/run-qemu.sh --graphical
```

Expected output on successful start:

```
[INFO] pk.compositor: Compositor ready on wayland-1 (PID 1234)
[INFO] pk.shell.launcher: Session READY — attaching surfaces
[INFO] pk.shell.launcher: Session ACTIVE — all surfaces attached
[INFO] pk.shell.launcher: Entering main event loop.
```
