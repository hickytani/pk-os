"""Regression checks for ownership and exposure of the interactive QEMU runner."""

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNNER = (ROOT / "scripts" / "run-qemu.sh").read_text(encoding="utf-8")


class TestQemuRunnerLifecycle(unittest.TestCase):
    def test_exit_trap_stops_only_tracked_qemu_and_preview_children(self):
        self.assertIn('QEMU_PID=""', RUNNER)
        self.assertIn('trap cleanup EXIT', RUNNER)
        self.assertIn('kill -TERM "${QEMU_PID}"', RUNNER)
        self.assertIn('wait "${QEMU_PID}"', RUNNER)
        self.assertIn('kill "${NOVNC_PID}"', RUNNER)
        self.assertIn('wait "${NOVNC_PID}"', RUNNER)

    def test_preview_services_bind_loopback_and_report_limited_health_checks(self):
        self.assertIn('"-vnc" "127.0.0.1:99"', RUNNER)
        self.assertIn('websockify --web /usr/share/novnc 127.0.0.1:6080 127.0.0.1:5999', RUNNER)
        self.assertIn("TCP reachable; input not yet verified", RUNNER)
        self.assertIn("HTTP reachable; browser input not yet verified", RUNNER)

    def test_qmp_mode_tracks_qemu_and_verifies_both_control_protocols(self):
        self.assertIn('qemu-system-x86_64 "${QEMU_ARGS[@]}" "${SERIAL_ARGS[@]}" &', RUNNER)
        self.assertIn('QEMU_PID=$!', RUNNER)
        self.assertIn('"${CONTROL_PROBE}" --qmp "${QMP_SOCKET}" --hmp "${MONITOR_SOCK}" --pid "${QEMU_PID}"', RUNNER)
        self.assertIn('wait "${QEMU_PID}"', RUNNER)

    def test_runner_refuses_to_reuse_existing_control_socket_paths(self):
        self.assertIn("refusing stale or shared path", RUNNER)
        self.assertIn('[ -S "${MONITOR_SOCK}" ]', RUNNER)
        self.assertIn('[ -S "${QMP_SOCKET}" ]', RUNNER)


if __name__ == "__main__":
    unittest.main()
