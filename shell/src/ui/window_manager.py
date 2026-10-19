"""
PK-OS Application Window Manager (Phase 2D)
=============================================
Tracks application window lifecycle (open, focus, minimize, close) and
provides a taskbar-ready list of active windows for the desktop shell.

Architecture:
  - WindowState: Enum for window lifecycle states.
  - AppWindow: Data class representing an application window.
  - WindowManager: Central manager for window state, focus tracking, and taskbar.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("pk.shell.window_manager")


class WindowState(Enum):
    """Window lifecycle state."""
    OPEN = "open"
    FOCUSED = "focused"
    MINIMIZED = "minimized"
    CLOSED = "closed"


@dataclass
class AppWindow:
    """Represents a single managed application window."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    app_id: str = ""
    title: str = ""
    state: WindowState = WindowState.OPEN
    workspace: int = 0
    created_at: float = field(default_factory=time.time)
    focused_at: float = 0.0
    geometry: Dict[str, int] = field(default_factory=lambda: {
        "x": 100, "y": 100, "width": 800, "height": 600
    })

    @property
    def is_visible(self) -> bool:
        return self.state in (WindowState.OPEN, WindowState.FOCUSED)

    @property
    def is_active(self) -> bool:
        return self.state != WindowState.CLOSED


class WindowManager:
    """
    Central desktop window manager.

    Tracks all application windows, manages focus, and provides
    taskbar data for the shell UI.
    """

    MAX_WINDOWS = 20

    def __init__(self) -> None:
        self._windows: Dict[str, AppWindow] = {}
        self._focus_stack: List[str] = []  # Most recently focused first
        self._on_focus_change: Optional[Callable[[AppWindow], None]] = None
        self._on_window_added: Optional[Callable[[AppWindow], None]] = None
        self._on_window_closed: Optional[Callable[[AppWindow], None]] = None

    @property
    def window_count(self) -> int:
        return sum(1 for w in self._windows.values() if w.is_active)

    @property
    def active_windows(self) -> List[AppWindow]:
        return [w for w in self._windows.values() if w.is_active]

    @property
    def focused_window(self) -> Optional[AppWindow]:
        for wid in self._focus_stack:
            w = self._windows.get(wid)
            if w and w.state == WindowState.FOCUSED:
                return w
        return None

    @property
    def taskbar_entries(self) -> List[Dict[str, Any]]:
        """Return taskbar-ready entries sorted by creation time."""
        entries = []
        for w in sorted(self.active_windows, key=lambda x: x.created_at):
            entries.append({
                "id": w.id,
                "app_id": w.app_id,
                "title": w.title,
                "state": w.state.value,
                "workspace": w.workspace,
                "is_focused": w.state == WindowState.FOCUSED,
            })
        return entries

    def get_taskbar_windows(self) -> List[Dict[str, Any]]:
        """Method alias for taskbar_entries."""
        return self.taskbar_entries

    def set_on_focus_change(self, cb: Callable[[AppWindow], None]) -> None:
        self._on_focus_change = cb

    def set_on_window_added(self, cb: Callable[[AppWindow], None]) -> None:
        self._on_window_added = cb

    def set_on_window_closed(self, cb: Callable[[AppWindow], None]) -> None:
        self._on_window_closed = cb

    def open_window(
        self,
        app_id: str,
        title: str = "",
        workspace: int = 0,
        geometry: Optional[Dict[str, int]] = None,
    ) -> AppWindow:
        """Open a new application window and focus it."""
        if self.window_count >= self.MAX_WINDOWS:
            raise RuntimeError(f"Maximum window limit ({self.MAX_WINDOWS}) reached")

        win = AppWindow(
            app_id=app_id,
            title=title or app_id.title(),
            workspace=workspace,
            geometry=geometry or {"x": 100, "y": 100, "width": 800, "height": 600},
        )
        self._windows[win.id] = win

        logger.info("Window opened: [%s] %s (%s)", win.id, win.title, win.app_id)

        if self._on_window_added:
            try:
                self._on_window_added(win)
            except Exception as exc:
                logger.warning("on_window_added callback error: %s", exc)

        self.focus(win.id)
        return win

    # Alias for convenience
    open = open_window

    def focus(self, window_id: str) -> bool:
        """Set focus to a specific window, unfocusing all others."""
        win = self._windows.get(window_id)
        if not win or not win.is_active:
            return False

        # Unfocus current
        for w in self._windows.values():
            if w.state == WindowState.FOCUSED:
                w.state = WindowState.OPEN

        win.state = WindowState.FOCUSED
        win.focused_at = time.time()

        # Update focus stack
        if window_id in self._focus_stack:
            self._focus_stack.remove(window_id)
        self._focus_stack.insert(0, window_id)

        if self._on_focus_change:
            try:
                self._on_focus_change(win)
            except Exception as exc:
                logger.warning("on_focus_change callback error: %s", exc)

        return True

    def minimize(self, window_id: str) -> bool:
        """Minimize a window."""
        win = self._windows.get(window_id)
        if not win or not win.is_active:
            return False
        win.state = WindowState.MINIMIZED
        logger.info("Window minimized: [%s] %s", win.id, win.title)

        # Focus next in stack
        self._focus_next_available()
        return True

    def close(self, window_id: str) -> bool:
        """Close a window."""
        win = self._windows.get(window_id)
        if not win or win.state == WindowState.CLOSED:
            return False
        win.state = WindowState.CLOSED
        logger.info("Window closed: [%s] %s", win.id, win.title)

        if window_id in self._focus_stack:
            self._focus_stack.remove(window_id)

        if self._on_window_closed:
            try:
                self._on_window_closed(win)
            except Exception as exc:
                logger.warning("on_window_closed callback error: %s", exc)

        self._focus_next_available()
        return True

    def close_all(self) -> int:
        """Close all active windows. Returns count closed."""
        count = 0
        for w in list(self._windows.values()):
            if w.is_active:
                self.close(w.id)
                count += 1
        return count

    def get_window(self, window_id: str) -> Optional[AppWindow]:
        return self._windows.get(window_id)

    def get_windows_by_app(self, app_id: str) -> List[AppWindow]:
        return [w for w in self._windows.values() if w.app_id == app_id and w.is_active]

    def get_windows_in_workspace(self, workspace: int) -> List[AppWindow]:
        return [w for w in self._windows.values() if w.workspace == workspace and w.is_active]

    def _focus_next_available(self) -> None:
        """Focus the next available window in the focus stack."""
        for wid in self._focus_stack:
            w = self._windows.get(wid)
            if w and w.state in (WindowState.OPEN, WindowState.FOCUSED):
                self.focus(wid)
                return
