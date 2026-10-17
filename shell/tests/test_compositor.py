"""
Unit tests for shell.src.compositor.pk_compositor.CompositorManager

These tests exercise all state transitions and helper methods without
requiring cage(1) to be installed on the test host, using monkeypatching.
"""

from __future__ import annotations

import os
import signal
import subprocess
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

# Adjust sys.path so the module is importable from the repo root
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from shell.src.compositor.pk_compositor import (
    CompositorManager,
    CompositorError,
    CompositorState,
)


class TestCompositorManagerInit(unittest.TestCase):
    """Verify default and custom initialisation."""

    def test_default_state_is_stopped(self):
        mgr = CompositorManager()
        self.assertEqual(mgr.state, CompositorState.STOPPED)

    def test_default_display_name(self):
        mgr = CompositorManager(display_number=1)
        self.assertEqual(mgr.display_name, "wayland-1")

    def test_custom_display_number(self):
        mgr = CompositorManager(display_number=3)
        self.assertEqual(mgr.display_name, "wayland-3")

    def test_is_running_when_stopped(self):
        mgr = CompositorManager()
        self.assertFalse(mgr.is_running)

    def test_repr_includes_state(self):
        mgr = CompositorManager()
        self.assertIn("STOPPED", repr(mgr))


class TestCompositorManagerStartErrors(unittest.TestCase):
    """Verify error paths in start()."""

    def test_raises_when_cage_not_found(self):
        mgr = CompositorManager()
        with patch("shutil.which", return_value=None):
            with self.assertRaises(CompositorError) as ctx:
                mgr.start()
        self.assertIn("cage", str(ctx.exception).lower())
        self.assertIn("not found", str(ctx.exception).lower())
        self.assertEqual(mgr.state, CompositorState.CRASHED)

    def test_raises_when_already_running(self):
        mgr = CompositorManager()
        mgr._state = CompositorState.RUNNING
        with self.assertRaises(CompositorError):
            mgr.start()

    def test_cage_binary_not_in_path_transitions_to_crashed(self):
        mgr = CompositorManager()
        with patch("shutil.which", return_value=None):
            with self.assertRaises(CompositorError):
                mgr.start()
        self.assertEqual(mgr.state, CompositorState.CRASHED)


class TestCompositorManagerStartSuccess(unittest.TestCase):
    """Verify happy-path start() with mocked subprocess and socket."""

    def _make_mock_process(self, pid: int = 12345) -> MagicMock:
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = pid
        mock_proc.poll.return_value = None  # still running
        return mock_proc

    def test_start_returns_display_name(self):
        mgr = CompositorManager(display_number=2)
        mock_proc = self._make_mock_process()

        with patch("shutil.which", return_value="/usr/bin/cage"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_for_socket", return_value=None):
            result = mgr.start()

        self.assertEqual(result, "wayland-2")

    def test_start_sets_running_state(self):
        mgr = CompositorManager()
        mock_proc = self._make_mock_process()

        with patch("shutil.which", return_value="/usr/bin/cage"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_for_socket", return_value=None):
            mgr.start()

        self.assertEqual(mgr.state, CompositorState.RUNNING)
        self.assertTrue(mgr.is_running)

    def test_start_exports_wayland_display_env(self):
        mgr = CompositorManager(display_number=5)
        mock_proc = self._make_mock_process()

        with patch("shutil.which", return_value="/usr/bin/cage"), \
             patch("subprocess.Popen", return_value=mock_proc), \
             patch.object(mgr, "_wait_for_socket", return_value=None):
            mgr.start()

        self.assertEqual(os.environ.get("WAYLAND_DISPLAY"), "wayland-5")

    def test_start_socket_timeout_raises_compositor_error(self):
        import platform
        if platform.system() == "Windows":
            self.skipTest("os.getuid() / XDG_RUNTIME_DIR not available on Windows")
        mgr = CompositorManager(startup_timeout_s=0.2)
        mock_proc = self._make_mock_process()

        with patch("shutil.which", return_value="/usr/bin/cage"), \
             patch("subprocess.Popen", return_value=mock_proc):
            # Don't mock _wait_for_socket — let it time out
            with self.assertRaises(CompositorError) as ctx:
                mgr.start()
        self.assertIn("Timeout", str(ctx.exception))
        self.assertEqual(mgr.state, CompositorState.CRASHED)


class TestCompositorManagerStop(unittest.TestCase):
    """Verify stop() behaviour."""

    def _running_manager(self) -> tuple[CompositorManager, MagicMock]:
        mgr = CompositorManager()
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.pid = 9999
        mock_proc.wait.return_value = 0
        mock_proc.poll.return_value = None
        mgr._process = mock_proc
        mgr._state = CompositorState.RUNNING
        return mgr, mock_proc

    def test_stop_sends_sigterm(self):
        mgr, mock_proc = self._running_manager()
        mgr.stop()
        mock_proc.send_signal.assert_called_once_with(signal.SIGTERM)

    def test_stop_returns_exit_code(self):
        mgr, mock_proc = self._running_manager()
        mock_proc.wait.return_value = 0
        rc = mgr.stop()
        self.assertEqual(rc, 0)

    def test_stop_sets_stopped_state(self):
        mgr, mock_proc = self._running_manager()
        mgr.stop()
        self.assertEqual(mgr.state, CompositorState.STOPPED)

    def test_stop_kills_on_timeout(self):
        mgr, mock_proc = self._running_manager()
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired(cmd="cage", timeout=3.0), 0]
        mgr.stop(grace_period_s=3.0)
        mock_proc.kill.assert_called_once()

    def test_stop_noop_when_already_stopped(self):
        mgr = CompositorManager()
        rc = mgr.stop()
        self.assertEqual(rc, 0)


class TestCompositorManagerPoll(unittest.TestCase):
    """Verify poll() state transitions on unexpected exit."""

    def test_poll_returns_none_when_running(self):
        mgr = CompositorManager()
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = None
        mgr._process = mock_proc
        mgr._state = CompositorState.RUNNING
        self.assertIsNone(mgr.poll())

    def test_poll_transitions_to_crashed_on_unexpected_exit(self):
        mgr = CompositorManager()
        mock_proc = MagicMock(spec=subprocess.Popen)
        mock_proc.poll.return_value = 1
        mgr._process = mock_proc
        mgr._state = CompositorState.RUNNING

        rc = mgr.poll()
        self.assertEqual(rc, 1)
        self.assertEqual(mgr.state, CompositorState.CRASHED)

    def test_poll_returns_none_when_no_process(self):
        mgr = CompositorManager()
        self.assertIsNone(mgr.poll())


class TestBuildCommand(unittest.TestCase):
    """Verify the cage command is constructed correctly."""

    def test_default_command_contains_cage_flag(self):
        mgr = CompositorManager()
        cmd = mgr._build_command("/usr/bin/cage")
        self.assertIn("/usr/bin/cage", cmd)
        self.assertIn("-d", cmd)
        self.assertIn("--", cmd)

    def test_client_cmd_appended(self):
        mgr = CompositorManager(client_cmd=["echo", "hello"])
        cmd = mgr._build_command("/usr/bin/cage")
        self.assertIn("echo", cmd)
        self.assertIn("hello", cmd)


if __name__ == "__main__":
    unittest.main()
