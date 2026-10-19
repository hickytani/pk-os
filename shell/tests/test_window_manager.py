"""
Tests for PK-OS Application Window Manager (Phase 2D)
"""

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from shell.src.ui.window_manager import (
    AppWindow,
    WindowState,
    WindowManager,
)


class TestAppWindow:
    """Tests for the AppWindow data class."""

    def test_window_creation(self):
        win = AppWindow(app_id="terminal", title="Terminal")
        assert win.app_id == "terminal"
        assert win.state == WindowState.OPEN
        assert win.is_active is True
        assert win.is_visible is True

    def test_closed_window_not_active(self):
        win = AppWindow(app_id="test", state=WindowState.CLOSED)
        assert win.is_active is False
        assert win.is_visible is False

    def test_minimized_window_not_visible(self):
        win = AppWindow(app_id="test", state=WindowState.MINIMIZED)
        assert win.is_active is True
        assert win.is_visible is False

    def test_focused_window_visible(self):
        win = AppWindow(app_id="test", state=WindowState.FOCUSED)
        assert win.is_visible is True


class TestWindowManager:
    """Tests for the WindowManager."""

    def test_open_window(self):
        wm = WindowManager()
        win = wm.open_window("terminal", "Terminal")
        assert wm.window_count == 1
        assert win.state == WindowState.FOCUSED

    def test_focus_window(self):
        wm = WindowManager()
        w1 = wm.open_window("terminal", "Terminal")
        w2 = wm.open_window("browser", "Browser")
        assert wm.focused_window.id == w2.id
        wm.focus(w1.id)
        assert wm.focused_window.id == w1.id

    def test_minimize_window(self):
        wm = WindowManager()
        win = wm.open_window("terminal", "Terminal")
        assert wm.minimize(win.id) is True
        assert wm.get_window(win.id).state == WindowState.MINIMIZED

    def test_close_window(self):
        wm = WindowManager()
        win = wm.open_window("terminal", "Terminal")
        assert wm.close(win.id) is True
        assert wm.window_count == 0

    def test_close_all(self):
        wm = WindowManager()
        wm.open_window("terminal")
        wm.open_window("browser")
        wm.open_window("editor")
        count = wm.close_all()
        assert count == 3
        assert wm.window_count == 0

    def test_max_window_limit(self):
        wm = WindowManager()
        for i in range(WindowManager.MAX_WINDOWS):
            wm.open_window(f"app{i}")
        with pytest.raises(RuntimeError, match="Maximum window limit"):
            wm.open_window("one_too_many")

    def test_taskbar_entries(self):
        wm = WindowManager()
        wm.open_window("terminal", "Terminal")
        wm.open_window("browser", "Browser")
        entries = wm.taskbar_entries
        assert len(entries) == 2
        assert entries[0]["app_id"] == "terminal"
        assert entries[1]["is_focused"] is True

    def test_get_windows_by_app(self):
        wm = WindowManager()
        wm.open_window("terminal", "Term 1")
        wm.open_window("terminal", "Term 2")
        wm.open_window("browser", "Browser")
        terms = wm.get_windows_by_app("terminal")
        assert len(terms) == 2

    def test_get_windows_in_workspace(self):
        wm = WindowManager()
        wm.open_window("terminal", workspace=0)
        wm.open_window("browser", workspace=1)
        ws0 = wm.get_windows_in_workspace(0)
        assert len(ws0) == 1

    def test_focus_next_after_close(self):
        wm = WindowManager()
        w1 = wm.open_window("terminal", "Terminal")
        w2 = wm.open_window("browser", "Browser")
        wm.close(w2.id)
        assert wm.focused_window.id == w1.id

    def test_callback_on_focus_change(self):
        wm = WindowManager()
        focused = []
        wm.set_on_focus_change(lambda w: focused.append(w))
        wm.open_window("terminal")
        assert len(focused) == 1

    def test_callback_on_window_closed(self):
        wm = WindowManager()
        closed = []
        wm.set_on_window_closed(lambda w: closed.append(w))
        win = wm.open_window("terminal")
        wm.close(win.id)
        assert len(closed) == 1

    def test_close_nonexistent_returns_false(self):
        wm = WindowManager()
        assert wm.close("nonexistent") is False

    def test_minimize_nonexistent_returns_false(self):
        wm = WindowManager()
        assert wm.minimize("nonexistent") is False
