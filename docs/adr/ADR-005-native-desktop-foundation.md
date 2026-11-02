# ADR-005: Native Desktop Foundation — Sway on Wayland

| Field | Value |
|---|---|
| **Status** | Accepted for the first multi-window integration milestone; not a claim of product completion |
| **Date** | 2026-11-02 |
| **Supersedes** | ADR-004's forward migration recommendation; Cage remains the default boot session for now |
| **Related** | ADR-002 (Wayland shell architecture), ADR-004 (graphical runtime) |

## Context

PK-OS currently boots Cage and a single GTK shell client. Cage is a kiosk
compositor: it can run multiple clients but shows only one at a time. The Python
`WindowManager` is an in-memory model and has no compositor surface lifecycle
or IPC connection. Keeping Cage as the only desktop session would prevent the
required multi-application product milestone.

The image builder currently targets Debian 12 Bookworm. The official Debian
package index lists Sway 1.7-6 in Bookworm, while `labwc` is packaged for
Trixie, not Bookworm. The Trixie package requires a newer libc than the current
Bookworm base. Adding labwc now would therefore require either a distribution
suite migration or a separately maintained build. A suite migration is outside
this desktop milestone.

## Decision

Use **Sway as the first real multi-window Wayland compositor/window manager**.
Retain Cage as the default and recovery/kiosk session until Sway has passed
exact-image acceptance. Install an opt-in `pk-sway-session.service` and a PK
Sway configuration alongside Cage. Sway will launch the existing PK shell as a
normal application window; its compositor-managed window tree will handle
focus, stacking, floating, tiling, fullscreen, workspace switching, and
application lifecycle. The first user-facing terminal is a separate client,
not a simulated panel inside the shell.

This is a foundation choice, not a commitment to expose stock i3 styling as
PK's final desktop. PK owns the shell, panel, launcher, application suite,
visual language, startup policy, and service boundaries. The Sway configuration
provides a tested Wayland window manager while PK develops and integrates
those components. Keep shell-to-window-manager integration behind Sway's IPC
and standard Wayland protocols; do not couple product APIs to a private C
compositor implementation.

## Options considered

| Option | Assessment |
|---|---|
| Cage | Keep for the reliable single-client/recovery path; insufficient as the only desktop because it is a kiosk compositor. |
| labwc | Better default stacking model and Openbox-like interaction; strong future candidate after a Debian suite decision or a reproducible source-package plan. Not directly installable from the current Bookworm archive. |
| **Sway** | Selected now. Mature wlroots compositor with real tiling and floating window management, keyboard-driven focus and workspaces, IPC, Xwayland support, and an official Bookworm package. GTK Wayland applications run as separate xdg-shell clients. MIT license. |
| Weston | Useful for protocol testing, but would still require PK to build substantial window-management and desktop policy around it. |
| Custom wlroots compositor | Too much low-level surface, DRM, input, and protocol work before PK has an application ecosystem; revisit only for a demonstrated product requirement that Sway cannot meet. |

## Reused infrastructure and PK-owned work

- Reuse the Debian Bookworm kernel, systemd, logind/seat access, libinput,
  wlroots, Mesa, Wayland protocols, GTK shell, and existing snapshot/QEMU build
  and test pipeline.
- Sway owns compositor surfaces, focus, stacking, tiling/floating, fullscreen,
  keyboard bindings, and workspace changes.
- PK must implement its own shell/panel, app discovery and launch policy,
  consistent application decoration/theme, notifications, settings, display
  management, session UX, typed system services, application permissions,
  and security boundaries.
- PK's Python window model is not authoritative once Sway is running. Replace
  it with real compositor state through Sway IPC or Wayland protocols before
  presenting it as window-management functionality.

## Migration path

1. Add Sway to the graphical image, but do not enable its service by default.
2. Keep the current Cage service enabled; make the opt-in Sway unit conflict
   with Cage and tty1 getty so only one seat owner runs at a time.
3. Launch the PK shell and independent native applications as separate Sway
   clients. Exercise focus, floating/tiling, fullscreen, close, and shortcuts.
4. Add a PK-owned panel and launcher, then wire application launch and Sway IPC
   to live compositor state.
5. Compare the Sway output diagnostics with the Cage output failures. Do not
   infer that changing compositors fixed the underlying GPU/DRM issue.
6. Reassess labwc only after the Bookworm-to-Trixie direction, package
   compatibility, and update policy are explicit. Cage remains useful for
   recovery, kiosk, and early-boot diagnostics.

## Risks and compatibility

- Sway is a tiling manager; PK must design floating defaults and accessible
  keyboard/pointer workflows for everyday use. Full desktop polish is PK work.
- The current Debian 12 wlroots/Mesa stack and the QEMU virtio-vga setup have
  known output-test warnings. Sway may reproduce the same failure.
- The current graphical service explicitly selects `WLR_RENDERER=pixman`, so
  it is software-rendered. Do not claim GPU acceleration until the running
  compositor and DRM path report it and measured output confirms it.
- Sway 1.7 is the version available in Bookworm. Keep config syntax within that
  supported version and test against the packaged binary before promotion.
- Existing GTK workspace buttons are application views, not compositor
  workspaces; the PK shell needs an explicit integration design for that split.
- This opt-in service has not yet been boot-tested in an image. Cage remains
  the only currently accepted boot session.

## Evidence and references

- [Debian Bookworm Sway package (1.7-6)](https://packages.debian.org/bookworm/sway)
- [Sway upstream documentation and MIT license](https://github.com/swaywm/sway)
- [Debian package search for labwc](https://packages.debian.org/search?keywords=labwc)
- [labwc project scope and compositor description](https://labwc.github.io/)
- [Debian Bookworm Cage man page (0.1.4-4)](https://manpages.debian.org/bookworm/cage/cage.1.en.html)

The package index and upstream descriptions establish availability, scope, and
license; they do not prove PK's session works. The first image built with this
unit/config must verify two independent clients and real focus/window actions.
