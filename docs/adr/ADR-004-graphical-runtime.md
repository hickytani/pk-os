# ADR-004: Graphical Runtime — cage + wlroots over Full Compositor Stack

| Field       | Value |
|-------------|-------|
| **Status**  | Accepted |
| **Date**    | 2026-10-17 |
| **Authors** | PK-OS Core Team |
| **Supersedes** | — |
| **Related** | ADR-002 (Wayland shell architecture) |

---

## Context

Phase 2A requires a real graphical session running inside QEMU with `virtio-gpu`
acceleration and also on bare-metal x86-64 targets.  The decision is which
Wayland compositor to ship as the initial production compositor.

### Options considered

| Option | Summary |
|--------|---------|
| **A: cage** | Minimal single-app wlroots compositor (kiosk model). |
| **B: labwc** | stacking wlroots compositor with xdg-shell; closest to an IceWM/Openbox replacement. |
| **C: Sway** | i3-compatible tiling compositor; rich, but 3 MB binary and i3bar dependency. |
| **D: Weston** | Reference compositor; useful for testing, not production-grade UX. |
| **E: Custom wlroots compositor** | Maximum control; 4–6 sprint engineering cost. |

---

## Decision

**Option A (cage)** is adopted for Phase 2A.

### Rationale

1. **Minimal attack surface.** cage has ≈1 200 lines of C; a full compositor
   (Sway, labwc) adds tens of thousands of lines for features we do not yet
   need.

2. **Ships in Debian 12.** No custom build is required; `apt-get install cage`
   is the only dependency step.  This keeps the rootfs build reproducible.

3. **Single-application model matches Phase 2A scope.** The PK-Shell launcher
   (`shell.launcher`) is the sole Wayland client in Phase 2A.  Multi-window
   management is a Phase 3 concern.

4. **QEMU virtio-gpu compatibility.** cage delegates rendering to wlroots, which
   supports the Mesa llvmpipe (software) fallback automatically when no KMS
   device is present, and switches to hardware acceleration on bare metal without
   configuration changes.

5. **Migration path to labwc/custom.** When Phase 3 introduces multi-window
   management, cage can be replaced by labwc or a custom wlroots compositor
   while the PK-Shell client code and systemd service remain unchanged.  The
   `CompositorManager.start()` API abstracts the binary path.

### Constraints imposed by this decision

- Only **one Wayland client surface** is supported at a time in cage's
  default mode.  Additional application windows must wait for Phase 3 (labwc
  or custom compositor integration).
- XWayland is installed but **not launched by cage** by default; X11
  applications will require explicit `cage -s -- xwayland-satellite` in Phase 3.

---

## Consequences

### Positive

- Graphical session ships in Phase 2A with zero custom C code.
- QEMU boot-to-desktop is testable immediately after `apt-get install cage`.
- `CompositorManager` abstracts the cage binary path, so the migration to a
  full compositor in Phase 3 is a one-line change.

### Negative / mitigations

- Single-surface limitation is a real UX constraint.  Mitigated by the fact
  that Phase 2A scope is a single panel + HUD overlay (both layers within one
  cage surface using wlr-layer-shell).
- cage does not implement xdg-toplevel (normal application windows).  Mitigated
  by deferring multi-app windows to Phase 3.

---

## Verification

The following are the minimum acceptance gates before this ADR is closed:

1. `cage` launches successfully inside QEMU with `virtio-gpu` (`WLR_RENDERER=vulkan`
   or `WLR_RENDERER=gles2`).
2. The PK-Shell launcher attaches its panel surface and exits cleanly.
3. `CompositorManager` unit tests pass on the host without cage installed.
4. The `pk-session.service` systemd unit reaches `active (running)` state in a
   test boot.
