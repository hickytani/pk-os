"""
Unit tests for PK-OS graphical shell UI, metrics collector, CSS styling,
and intelligence client IPC boundary.
"""

import unittest
from pathlib import Path
import sys

_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from shell.src.ui.gui import (  # noqa: E402
    SystemMetricsCollector,
    PKIntelligenceClient,
    generate_shell_css,
    HeadlessShellSurface,
)


class TestSystemMetrics(unittest.TestCase):
    def setUp(self):
        self.collector = SystemMetricsCollector()

    def test_memory_metrics_structure(self):
        mem = self.collector.get_memory_metrics()
        self.assertIn("available", mem)
        self.assertIn("total_mb", mem)
        self.assertIn("used_mb", mem)
        self.assertIn("percent", mem)
        self.assertIn("label", mem)
        self.assertIsInstance(mem["percent"], float)
        self.assertIsInstance(mem["label"], str)

    def test_load_metrics_structure(self):
        load = self.collector.get_load_metrics()
        self.assertIn("available", load)
        self.assertIn("label", load)
        self.assertIsInstance(load["label"], str)

    def test_uptime_metrics_structure(self):
        up = self.collector.get_uptime_metrics()
        self.assertIn("available", up)
        self.assertIn("label", up)
        self.assertIsInstance(up["label"], str)

    def test_battery_metrics_structure(self):
        bat = self.collector.get_battery_metrics()
        self.assertIn("available", bat)
        self.assertIn("label", bat)
        self.assertIsInstance(bat["label"], str)


class TestDesignTokensCSS(unittest.TestCase):
    def test_css_contains_design_tokens(self):
        css = generate_shell_css(reduced_motion=False)
        self.assertIn("#0a0b0e", css)  # bg_base
        self.assertIn("#12151c", css)  # bg_surface
        self.assertIn("#00e5ff", css)  # accent_cyan
        self.assertIn("#222736", css)  # border_subtle
        self.assertIn("#f0f3fa", css)  # text_primary
        self.assertIn("transition: all", css)

    def test_css_reduced_motion(self):
        css_reduced = generate_shell_css(reduced_motion=True)
        self.assertIn("transition: none", css_reduced)
        self.assertNotIn("transition: all", css_reduced)


class TestIntelligenceClient(unittest.TestCase):
    def test_client_handles_offline_daemon(self):
        client = PKIntelligenceClient(socket_path="/nonexistent/path/control.sock")
        self.assertFalse(client.is_daemon_online())
        res = client.query("test query")
        self.assertFalse(res["ok"])
        self.assertIn("offline", res["error"].lower())

    def test_client_ping_detection(self):
        """Verify client correctly returns False when connection cannot be established."""
        client = PKIntelligenceClient(socket_path="/tmp/test_nonexistent_pk_sock")
        self.assertFalse(client.is_daemon_online(timeout_sec=0.05))


class TestHeadlessShellSurface(unittest.TestCase):
    def test_headless_surface_lifecycle(self):
        surface = HeadlessShellSurface()
        self.assertEqual(surface.state, "INIT")
        surface.tick()
        self.assertEqual(surface.state, "ACTIVE")
        self.assertIsNotNone(surface.last_mem)
        self.assertIsNotNone(surface.last_load)
        self.assertIsNotNone(surface.last_uptime)

    def test_workspace_switching(self):
        surface = HeadlessShellSurface()
        self.assertEqual(surface.active_workspace, 0)
        surface.switch_workspace(1)
        self.assertEqual(surface.active_workspace, 1)
        surface.switch_workspace(2)
        self.assertEqual(surface.active_workspace, 2)
        with self.assertRaises(ValueError):
            surface.switch_workspace(3)

    def test_app_launch_interaction(self):
        surface = HeadlessShellSurface()
        surface.launch_app("terminal")
        self.assertIn("terminal", surface.launched_apps)
        self.assertEqual(surface.history[-1]["action"], "launch_app")
        self.assertEqual(surface.history[-1]["app_id"], "terminal")

    def test_hud_query_interaction(self):
        surface = HeadlessShellSurface()
        surface.send_hud_query("get system status")
        self.assertEqual(surface.history[-1]["action"], "hud_query")
        self.assertEqual(surface.history[-1]["query"], "get system status")

    def test_brightness_setting_adjustment(self):
        surface = HeadlessShellSurface()
        surface.set_brightness(50)
        self.assertEqual(surface.brightness, 50)
        surface.set_brightness(5)   # clamped to 10
        self.assertEqual(surface.brightness, 10)
        surface.set_brightness(120) # clamped to 100
        self.assertEqual(surface.brightness, 100)

    def test_reduced_motion_toggle(self):
        surface = HeadlessShellSurface()
        self.assertFalse(surface.reduced_motion)
        surface.toggle_reduced_motion(True)
        self.assertTrue(surface.reduced_motion)
        surface.toggle_reduced_motion(False)
        self.assertFalse(surface.reduced_motion)


if __name__ == "__main__":
    unittest.main()
