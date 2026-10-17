# PK-OS Shell Architecture & Design System (Phase 2)

## 1. Overview & Purpose

The PK-OS Desktop Shell (`pk-shell`) provides the user interface layer for PK-OS. It runs as an independent, sandboxed Wayland client that attaches directly to the display compositor via the `wlr-layer-shell-unstable-v1` protocol.

The design philosophy emphasizes technical precision, editorial typography, dark cinematic surfaces, fast responsive transitions, and accessibility.

## 2. Process Boundaries & Session Lifecycle

```text
+-------------------------------------------------------------+
|                     Display Server (KMS/DRM)                |
|               wlroots-based Wayland Compositor              |
+------------------------------+------------------------------+
                               | Wayland Socket
                               v
+-------------------------------------------------------------+
|                      PK-OS Shell Process                    |
|                        (pk-shell)                           |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Layer Surface: TOP (Exclusive Zone: 36px)            |  |
|  | - System Status Bar & Clock                           |  |
|  | - Battery / Power & Network Indicators                |  |
|  | - Active Workspace Switcher                          |  |
|  +-------------------------------------------------------+  |
|                                                             |
|  +-------------------------------------------------------+  |
|  | Layer Surface: OVERLAY (Non-Exclusive Modal)          |  |
|  | - Application Launcher Grid                           |  |
|  | - "Hey PK" Voice HUD & Task Approval Gate             |  |
|  | - Notification Banners & Quick Settings Flyout        |  |
|  +-------------------------------------------------------+  |
+------------------------------+------------------------------+
                               | Typed IPC (Unix Domain Socket / D-Bus)
                               v
+-------------------------------------------------------------+
|                      PK-OS Core Daemons                     |
|  - Systemd / Logind Session                                 |
|  - NetworkManager / WirePlumber Audio                       |
|  - PK Intelligence Agent Service (pk-intelligenced)         |
+-------------------------------------------------------------+
```

### Lifecycle States

1. **INIT**: Connects to `$WAYLAND_DISPLAY`, requests `wl_compositor`, `wl_shm`, and `zwlr_layer_shell_v1` globals.
2. **READY**: Creates layer surfaces, applies exclusive zones, registers keyboard shortcuts (`Super`, `Super+Space`, `Super+K`).
3. **ACTIVE**: Listens for user input and IPC notifications from `pk-intelligenced` (e.g. voice trigger, approval prompt).
4. **SUSPEND / RESUME**: Responds to compositor output reconfiguration and display sleep events without memory leaks.
5. **TERMINATE**: Gracefully destroys layer surfaces, flushes configuration state, disconnects Wayland registry.

## 3. Design Tokens

PK-OS avoids generic CSS frameworks in favor of a curated, mathematical token system.

### Color Tokens (OLED Dark Mode, 60:30:10 Ratio)

- `--pk-bg-base`: `#0a0b0e` (Deep Obsidian base)
- `--pk-bg-surface`: `#12151c` (Elevated card surface)
- `--pk-bg-surface-hover`: `#1a1e28` (Interactive highlight)
- `--pk-border-subtle`: `#222736` (Hairline boundary, 1px)
- `--pk-border-focused`: `#4d78cc` (Active focus ring)
- `--pk-text-primary`: `#f0f3fa` (High contrast text, WCAG AAA 14:1)
- `--pk-text-secondary`: `#8b94a8` (Muted caption text, WCAG AA 4.8:1)
- `--pk-accent-cyan`: `#00e5ff` (Primary electric cyan indicator)
- `--pk-accent-amber`: `#ffb300` (Approval required / warning)
- `--pk-accent-crimson`: `#ff3b5c` (Security alert / critical rejection)

### Typography Tokens

- `--pk-font-sans`: `Inter, -apple-system, system-ui, sans-serif`
- `--pk-font-mono`: `"JetBrains Mono", Menlo, Consolas, monospace`
- `--pk-text-xs`: `0.75rem` (12px, line-height 1.4)
- `--pk-text-sm`: `0.875rem` (14px, line-height 1.5)
- `--pk-text-base`: `1.00rem` (16px, line-height 1.5)
- `--pk-text-lg`: `1.25rem` (20px, line-height 1.4)
- `--pk-text-xl`: `1.50rem` (24px, line-height 1.3)

### Spacing Tokens (4px Grid)

- `--pk-space-1`: `4px`
- `--pk-space-2`: `8px`
- `--pk-space-3`: `12px`
- `--pk-space-4`: `16px`
- `--pk-space-6`: `24px`
- `--pk-space-8`: `32px`

### Radii & Motion Tokens

- `--pk-radius-sm`: `4px`
- `--pk-radius-md`: `8px`
- `--pk-radius-lg`: `14px`
- `--pk-motion-fast`: `120ms cubic-bezier(0.16, 1, 0.3, 1)`
- `--pk-motion-smooth`: `240ms cubic-bezier(0.16, 1, 0.3, 1)`

## 4. Responsive & Adaptive Breakpoints

The shell adapts between desktop laptops and future mobile touch environments:

- **Desktop Mode (`width >= 1024px`)**: Top status bar with continuous horizontal layout, compact floating launcher modal (`max-width: 680px`), HUD overlay anchored to top-right.
- **Compact / Mobile Mode (`width < 1024px`)**: Top bar compresses into mobile status header, launcher transforms into full-screen touch drawer, HUD occupies bottom card drawer.

## 5. Accessibility & Invariants

- **Keyboard Navigable**: All interactive controls are navigable via `Tab`, `Shift+Tab`, arrow keys, and activate via `Enter` or `Space`.
- **Reduced Motion**: Respects `prefers-reduced-motion` by disabling translational animations and preserving instant opacity transitions.
- **Strict Contrast**: All foreground/background combinations strictly satisfy WCAG AA (minimum 4.5:1) and text primary satisfies WCAG AAA (14:1).
