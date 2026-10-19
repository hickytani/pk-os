"""
PK-OS Shell Launcher (Phase 2A)
================================
Entry point for the pk-shell graphical session.  This module is invoked by
cage(1) as its single Wayland client subprocess.  It:

  1. Initialises logging.
  2. Validates the Wayland environment.
  3. Creates a ShellSession and transitions it to READY.
  4. Attaches the TOP-layer surface (panel) and OVERLAY-layer surface (HUD).
  5. Enters the main event loop, polling for compositor crashes and OS signals.
  6. Performs a clean teardown on SIGTERM / SIGINT.

Usage (direct, for development):
    WAYLAND_DISPLAY=wayland-1 python3 -m shell.launcher

In production the systemd user service pk-session.service invokes cage which
invokes this launcher; the env var is set by CompositorManager.start().
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import time

# ---------------------------------------------------------------------------
# Logging initialisation (before any local imports to capture import errors)
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pk.shell.launcher")

# ---------------------------------------------------------------------------
# Local imports (path-safe: invoked as module via python3 -m shell.launcher)
# ---------------------------------------------------------------------------
from shell.src.session.lifecycle import ShellConfig, ShellLayer, ShellSession, SessionState  # noqa: E402
from shell.src.ui.layout import LayoutEngine, FormFactor  # noqa: E402


# ---------------------------------------------------------------------------
# Signal handling
# ---------------------------------------------------------------------------
_SHUTDOWN_REQUESTED = False


def _handle_shutdown(signum: int, _frame: object) -> None:
    global _SHUTDOWN_REQUESTED
    logger.info("Received signal %d — initiating graceful shutdown", signum)
    _SHUTDOWN_REQUESTED = True


signal.signal(signal.SIGTERM, _handle_shutdown)
signal.signal(signal.SIGINT, _handle_shutdown)


# ---------------------------------------------------------------------------
# Environment validation
# ---------------------------------------------------------------------------

def validate_wayland_env() -> str:
    """Return WAYLAND_DISPLAY value or raise EnvironmentError."""
    display = os.environ.get("WAYLAND_DISPLAY")
    if not display:
        raise EnvironmentError(
            "WAYLAND_DISPLAY is not set. "
            "pk-shell must be launched through the CompositorManager or cage."
        )
    uid = os.getuid() if hasattr(os, "getuid") else 0
    runtime_dir = os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{uid}")
    socket_path = f"{runtime_dir}/{display}"
    # Wait up to 3 seconds for compositor socket creation
    for _ in range(30):
        if os.path.exists(socket_path):
            break
        time.sleep(0.1)
    if not os.path.exists(socket_path):
        logger.warning("Wayland socket not yet visible at %s (compositor starting?)", socket_path)
    return display


# ---------------------------------------------------------------------------
# Main session entry point
# ---------------------------------------------------------------------------

def run_shell() -> int:
    """
    Run the PK-OS shell session.

    Returns
    -------
    int
        OS exit code (0 = clean shutdown, non-zero = error).
    """
    logger.info("PK-OS Shell Launcher starting (PID %d)", os.getpid())

    # 1. Validate environment
    try:
        display = validate_wayland_env()
        logger.info("Wayland display: %s", display)
    except EnvironmentError as exc:
        logger.error("%s", exc)
        return 1

    # 2. Determine form factor from display dimensions (env hint or default)
    width_hint = int(os.environ.get("PK_DISPLAY_WIDTH", "1920"))
    height_hint = int(os.environ.get("PK_DISPLAY_HEIGHT", "1080"))
    layout = LayoutEngine(screen_width=width_hint, screen_height=height_hint)
    form_factor = layout.form_factor
    logger.info("Form factor: %s (%dx%d)", form_factor.value, width_hint, height_hint)

    # 3. Create and validate session
    config = ShellConfig(
        panel_height_px=36,
        enable_voice_hud=True,
        exclusive_zone=True,
        font_family="Inter",
        theme="obsidian_dark",
    )
    session = ShellSession(config=config)

    # Register lifecycle callbacks
    def _on_ready() -> None:
        logger.info("Session READY — attaching surfaces")

    def _on_active() -> None:
        logger.info("Session ACTIVE — all surfaces attached")

    def _on_terminated() -> None:
        logger.info("Session TERMINATED")

    session.register_listener(SessionState.READY, _on_ready)
    session.register_listener(SessionState.ACTIVE, _on_active)
    session.register_listener(SessionState.TERMINATED, _on_terminated)

    # 4. Transition → READY and attach surfaces
    session.transition_to(SessionState.READY)
    panel_id = session.attach_surface(ShellLayer.TOP)
    hud_id = session.attach_surface(ShellLayer.OVERLAY)
    logger.info("Surfaces attached: panel=%d hud=%d", panel_id, hud_id)

    # 5. Transition → ACTIVE
    session.transition_to(SessionState.ACTIVE)

    # 6. Main event loop (GTK3 Wayland surface or headless loop)
    from shell.src.ui.gui import GTK_AVAILABLE, PKShellWindow
    if GTK_AVAILABLE:
        try:
            logger.info("Instantiating native PKShellWindow GTK3 Wayland surface")
            win = PKShellWindow(on_shutdown=lambda: session.transition_to(SessionState.TERMINATED))
            win.show_all()

            # Signal hook to stop GTK main loop cleanly
            def _gtk_sig_handler(signum: int, _frame: object) -> None:
                global _SHUTDOWN_REQUESTED
                logger.info("Received signal %d in GTK loop — quitting Gtk.main", signum)
                _SHUTDOWN_REQUESTED = True
                from gi.repository import Gtk
                Gtk.main_quit()

            signal.signal(signal.SIGTERM, _gtk_sig_handler)
            signal.signal(signal.SIGINT, _gtk_sig_handler)

            from gi.repository import Gtk
            Gtk.main()
        except Exception as exc:
            logger.error("Failed running GTK graphical surface (%s). Dropping to fallback loop.", exc)
            _POLL_INTERVAL_S = 0.5
            while not _SHUTDOWN_REQUESTED:
                time.sleep(_POLL_INTERVAL_S)
    else:
        logger.info("GTK3 not available in environment; running in headless loop mode.")
        _POLL_INTERVAL_S = 0.5
        try:
            while not _SHUTDOWN_REQUESTED:
                time.sleep(_POLL_INTERVAL_S)
        except KeyboardInterrupt:
            pass

    # 7. Teardown
    logger.info("Shutting down PK-OS shell session")
    try:
        session.detach_surface()  # HUD
        session.detach_surface()  # Panel
    except Exception:
        pass
    if session.state != SessionState.TERMINATED:
        session.transition_to(SessionState.TERMINATED)

    logger.info("Shell session exited cleanly")
    return 0


if __name__ == "__main__":
    sys.exit(run_shell())
