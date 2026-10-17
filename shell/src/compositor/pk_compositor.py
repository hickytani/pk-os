"""
PK-OS Compositor Manager
========================
Manages the lifecycle of the cage(1) Wayland compositor process on behalf of
the PK-Shell session.  cage is chosen as the Phase 2A compositor because:

  - Zero X11 dependency — cage is a wlroots-based single-surface compositor.
  - Ships in Debian 12 Bookworm repositories (no custom build needed).
  - Accepts an arbitrary Wayland client as its single argument; PK-Shell
    attaches via the wlr-layer-shell-unstable-v1 protocol as the primary
    surface after cage initialises the display server.
  - QEMU virtio-gpu + Mesa llvmpipe render without KVM acceleration (pure SW).

Architecture integration
------------------------
CompositorManager is driven by ShellSession (shell.src.session.lifecycle).
It exposes async-safe start/stop primitives and publishes WAYLAND_DISPLAY
into the process environment so child processes (pk-intelligenced, GTK3/Qt
applications) can connect without additional configuration.

State machine coupling
----------------------
  ShellSession.INIT        → CompositorManager not yet started
  ShellSession.READY       → compositor running, WAYLAND_DISPLAY exported
  ShellSession.ACTIVE      → at least one client surface attached
  ShellSession.SUSPENDED   → compositor paused (VT switch / lid-close)
  ShellSession.TERMINATED  → compositor process sent SIGTERM
"""

from __future__ import annotations

import logging
import os
import signal
import subprocess
import time
from enum import Enum, auto
from pathlib import Path
from typing import Optional

logger = logging.getLogger("pk.compositor")


class CompositorState(Enum):
    STOPPED = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    CRASHED = auto()


class CompositorError(RuntimeError):
    """Raised when a compositor operation cannot complete safely."""


class CompositorManager:
    """
    Manages one cage(1) compositor subprocess for the PK-OS graphical session.

    Parameters
    ----------
    client_cmd : list[str]
        Argv for the Wayland client cage will host.  Defaults to the PK-Shell
        launcher stub (``python3 -m shell.src.launcher``).
    display_number : int
        wayland-N display socket number.  Defaults to 1 (wayland-1).
    drm_device : str | None
        Explicit DRM render node path (e.g. ``/dev/dri/renderD128``).
        If None, cage selects the first available device automatically.
    startup_timeout_s : float
        Seconds to wait for WAYLAND_DISPLAY to become available.
    """

    _DEFAULT_CLIENT: list[str] = ["python3", "-m", "shell.launcher"]
    _SOCKET_POLL_INTERVAL_S: float = 0.1

    def __init__(
        self,
        client_cmd: Optional[list[str]] = None,
        display_number: int = 1,
        drm_device: Optional[str] = None,
        startup_timeout_s: float = 10.0,
    ) -> None:
        self._client_cmd: list[str] = client_cmd or list(self._DEFAULT_CLIENT)
        self._display_number: int = display_number
        self._drm_device: Optional[str] = drm_device
        self._startup_timeout_s: float = startup_timeout_s

        self._process: Optional[subprocess.Popen[bytes]] = None  # type: ignore[type-arg]
        self._state: CompositorState = CompositorState.STOPPED
        self._display_name: str = f"wayland-{display_number}"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def state(self) -> CompositorState:
        return self._state

    @property
    def display_name(self) -> str:
        """The Wayland display socket name (e.g. 'wayland-1')."""
        return self._display_name

    @property
    def is_running(self) -> bool:
        return self._state is CompositorState.RUNNING

    def start(self) -> str:
        """
        Launch cage and block until its Wayland socket is ready.

        Returns
        -------
        str
            The WAYLAND_DISPLAY value that clients should use.

        Raises
        ------
        CompositorError
            If cage is not found, fails to start, or times out.
        """
        if self._state not in (CompositorState.STOPPED, CompositorState.CRASHED):
            raise CompositorError(
                f"Cannot start compositor from state {self._state}"
            )

        self._state = CompositorState.STARTING

        try:
            cage_bin = self._resolve_cage()
        except CompositorError:
            self._state = CompositorState.CRASHED
            raise

        cmd = self._build_command(cage_bin)

        env = dict(os.environ)
        env["WAYLAND_DISPLAY"] = self._display_name
        # Prefer Vulkan/software rendering in QEMU; hardware kicks in automatically
        # when a DRM device with KMS support is detected by wlroots.
        env.setdefault("WLR_RENDERER", "vulkan")
        env.setdefault("WLR_NO_HARDWARE_CURSORS", "1")  # virtio-gpu compat
        env.setdefault("LIBGL_ALWAYS_SOFTWARE", "0")     # allow HW if present

        if self._drm_device:
            env["WLR_DRM_DEVICES"] = self._drm_device

        logger.info("Launching compositor: %s", " ".join(cmd))

        try:
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                close_fds=True,
            )
        except FileNotFoundError as exc:
            self._state = CompositorState.CRASHED
            raise CompositorError(f"cage not found: {exc}") from exc

        self._wait_for_socket()
        self._state = CompositorState.RUNNING

        # Export display into current process so child spawns inherit it
        os.environ["WAYLAND_DISPLAY"] = self._display_name
        logger.info("Compositor ready on %s (PID %d)", self._display_name, self._process.pid)
        return self._display_name

    def stop(self, grace_period_s: float = 3.0) -> int:
        """
        Terminate the compositor gracefully.

        Returns
        -------
        int
            Exit code of the cage process.
        """
        if self._state not in (CompositorState.RUNNING, CompositorState.STARTING):
            return 0

        self._state = CompositorState.STOPPING
        assert self._process is not None

        logger.info("Sending SIGTERM to compositor PID %d", self._process.pid)
        try:
            self._process.send_signal(signal.SIGTERM)
            returncode = self._process.wait(timeout=grace_period_s)
        except subprocess.TimeoutExpired:
            logger.warning("Compositor did not exit within %.1fs — sending SIGKILL", grace_period_s)
            self._process.kill()
            returncode = self._process.wait()

        self._state = CompositorState.STOPPED
        logger.info("Compositor stopped (exit code %d)", returncode)
        return returncode

    def poll(self) -> Optional[int]:
        """
        Non-blocking check of the compositor process exit status.

        Returns
        -------
        int | None
            Exit code if the process has terminated, else None.
        """
        if self._process is None:
            return None
        rc = self._process.poll()
        if rc is not None and self._state is CompositorState.RUNNING:
            logger.error("Compositor exited unexpectedly (code %d)", rc)
            self._state = CompositorState.CRASHED
        return rc

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _resolve_cage(self) -> str:
        """Return absolute path to cage binary or raise CompositorError."""
        import shutil
        cage = shutil.which("cage")
        if cage is None:
            raise CompositorError(
                "cage(1) not found in PATH. "
                "Install it with: apt-get install cage"
            )
        return cage

    def _build_command(self, cage_bin: str) -> list[str]:
        cmd = [cage_bin, f"-d", "--"]
        cmd.extend(self._client_cmd)
        return cmd

    def _wait_for_socket(self) -> None:
        """Poll XDG_RUNTIME_DIR for the Wayland socket to appear."""
        runtime_dir = os.environ.get(
            "XDG_RUNTIME_DIR",
            f"/run/user/{os.getuid()}" if hasattr(os, 'getuid') else "/tmp"
        )
        socket_path = Path(runtime_dir) / self._display_name

        deadline = time.monotonic() + self._startup_timeout_s
        while time.monotonic() < deadline:
            # Check process hasn't died
            if self._process is not None and self._process.poll() is not None:
                rc = self._process.returncode
                self._state = CompositorState.CRASHED
                raise CompositorError(
                    f"cage exited with code {rc} before socket appeared"
                )
            if socket_path.exists():
                return
            time.sleep(self._SOCKET_POLL_INTERVAL_S)

        self._state = CompositorState.CRASHED
        raise CompositorError(
            f"Timeout ({self._startup_timeout_s}s) waiting for {socket_path}"
        )

    def __repr__(self) -> str:
        pid = self._process.pid if self._process else "—"
        return (
            f"<CompositorManager display={self._display_name!r} "
            f"state={self._state.name} pid={pid}>"
        )
