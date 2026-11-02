"""Tests for conservative parsing of PK-OS renderer/output evidence."""

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from render_diagnostics import analyze  # noqa: E402


class TestRenderDiagnostics(unittest.TestCase):
    def test_reports_forced_pixman_and_output_failures_without_claiming_root_cause(self):
        log = """\
[  1.500000] [drm] pci: virtio-vga detected at 0000:00:03.0
[  1.510000] [drm] features: -virgl +edid -resource_blob -host_visible
[  1.520000] [drm] number of scanouts: 1
[  1.600000] cage[10]: Form factor: desktop (1280x800)
[  2.000000] cage[9]: [ERROR] [types/output/output.c:656] Basic output test failed for Virtual-1
[  3.000000] cage[9]: [ERROR] [types/output/output.c:656] Basic output test failed for Virtual-1
"""
        service = "Environment=WLR_RENDERER=pixman\nExecStart=/usr/bin/cage -d -- /usr/bin/python3 -m shell.launcher\n"

        report = analyze(log, service)

        self.assertEqual(report["renderer"]["status"], "software_renderer_forced_by_session_unit")
        self.assertEqual(report["renderer"]["gpu_acceleration"], "not_established")
        self.assertEqual(report["output"]["basic_output_test_failure_count"], 2)
        self.assertEqual(report["output"]["failed_outputs"], ["Virtual-1"])
        self.assertEqual(report["output"]["first_failure_kernel_seconds"], 2.0)
        self.assertEqual(report["output"]["last_failure_kernel_seconds"], 3.0)
        self.assertEqual(report["output"]["root_cause"], "unresolved; transcript reports failure but not the wlroots test sub-result")
        self.assertTrue(report["qemu_virgl_feature_reported_unavailable"])
        self.assertFalse(report["cage_command_debug_option_present"])
        self.assertEqual(report["output"]["session_form_factor_geometry"]["source"], "PK shell form-factor log")

    def test_missing_instrumentation_is_unknown_not_fabricated(self):
        report = analyze("desktop ready\n", "ExecStart=/usr/bin/cage -- app\n")
        self.assertIsNone(report["renderer"]["wlr_renderer_environment"])
        self.assertEqual(report["renderer"]["status"], "renderer_selection_unknown")
        self.assertEqual(report["output"]["basic_output_test_failure_count"], 0)
        self.assertIsNone(report["output"]["session_form_factor_geometry"])
        self.assertEqual(report["performance_metrics"]["fps"], "unavailable")


if __name__ == "__main__":
    unittest.main()
