# ADR-002: Wayland Compositor Architecture and Shell Foundation

## Status

Accepted

## Date

2026-10-17

## Context

Phase 2 of PK-OS requires a custom, high-performance, visually distinctive desktop shell. The shell must satisfy the following constraints:

1. **Target Platforms**: x86-64 desktop and laptop systems initially, with adaptive layout designed for future touch/mobile displays (AOSP/mobile port).
2. **Display Protocol**: Modern Linux display standard. X11 is deprecated, lacks per-window isolation, and has security deficiencies. Wayland is the mandatory foundation.
3. **Budget and Tooling**: Free and open-source tooling only (₹0 budget).
4. **Architecture Division**: Separation of window management/compositing from shell user-interface surfaces (panels, launchers, status bars, notification popups, voice HUD overlays).
5. **Aesthetics & Performance**: Premium, hardware-accelerated rendering, 60+ FPS animations, sub-16ms latency, strict accessibility and contrast standards.

## Decision Drivers

- **Security & Isolation**: Wayland clients cannot snoop on other clients' keystrokes or framebuffers by default.
- **Upstream Reuse vs Custom Complexity**: Writing a complete Wayland display compositor from bare DRM/KMS/GBM requires tens of thousands of lines of low-level graphics plumbing. Upstream compositor libraries (`wlroots`, `smithay`, `mir`) provide production-tested hardware abstraction while allowing custom shell protocols.
- **Protocol Standardization**: Use of `wlr-layer-shell-unstable-v1` allows independent UI shell components to position themselves precisely (exclusive zones, panels, overlays) across multiple display outputs without hardcoding compositor internals.

## Evaluated Options

### Option 1: Custom Compositor from Scratch (Direct DRM/KMS/OpenGL)

- **Pros**: Absolute control over every byte of frame rendering.
- **Cons**: Massive engineering overhead; non-standard driver bugs; fragile multi-monitor, hotplug, and input handling; delays Phase 2 deliverables indefinitely.
- **Verdict**: Rejected.

### Option 2: Full Monolithic Desktop Environment (GNOME Shell / KDE Plasma fork)

- **Pros**: Feature complete.
- **Cons**: Heavy resource footprint (500MB+ idle RAM); deeply coupled upstream dependencies; difficult to strip down for minimal laptops or adapt to phone layouts.
- **Verdict**: Rejected.

### Option 3: Modular wlroots-based Compositor with wlr-layer-shell UI Foundation

- **Pros**: Leverages industry-standard `wlroots` (powering Sway, River, Wayfire, Hyprland). Clean separation where compositor handles outputs and input dispatch, while the shell UI executes as a distinct client process attaching surfaces to the layer shell (`wlr-layer-shell-unstable-v1`).
- **Verdict**: Accepted.

## Decision

PK-OS adopts a **modular Wayland architecture**:

1. **Compositor Engine**: Lightweight `wlroots`-backed compositor session managing DRM/KMS hardware scanout, libinput event dispatch, and Wayland protocols (`xdg-shell`, `wlr-layer-shell-unstable-v1`, `linux-dmabuf-v1`).
2. **Shell Surface Process (`pk-shell`)**: An independent user-space process responsible for the panel, application grid launcher, system status indicators, notification toasts, and the PK Intelligence voice HUD overlay.
3. **Layer Shell Binding**: All PK-OS shell surfaces bind to `zwlr_layer_shell_v1` with predefined layer planes:
   - `ZWLR_LAYER_SHELL_V1_LAYER_TOP`: Top status bar / panel (exclusive zone).
   - `ZWLR_LAYER_SHELL_V1_LAYER_OVERLAY`: PK Intelligence Voice HUD and critical system alerts.
   - `ZWLR_LAYER_SHELL_V1_LAYER_BOTTOM`: Wallpaper and background widgets.
4. **Design System**: Strict token-based styling (surfaces, typography, spacing, elevation, motion, high-contrast dark theme) implemented without external bloated CSS frameworks.

## Consequences

### Positive

- Robust multi-monitor, fractional scaling, and hardware acceleration out of the box.
- Shell crashes do not crash the display server if isolated properly, and shell components can be developed and tested independently in standard Wayland sessions (e.g. nested in Weston or Sway during development).
- Zero licensing costs; permissive MIT / Apache-2.0 / LGPL-2.1 upstream stack.

### Negative / Trade-offs

- Requires `wlr-layer-shell-unstable-v1` protocol support in the compositor.
- Requires seat management (logind / seatd) for VT switching and DRM master leases.
