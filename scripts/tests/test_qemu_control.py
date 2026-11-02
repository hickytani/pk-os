"""Protocol-level tests for bounded QEMU QMP/HMP readiness checks."""

import json
import os
import socket
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from qemu_control import (  # noqa: E402
    ControlError,
    probe_hmp,
    probe_qmp,
    wait_for_control,
)
from qemu_ui import QmpInput  # noqa: E402


class FakeQmpServer:
    def __init__(self, path: Path, greeting=None):
        self.path = path
        self.greeting = greeting or {"QMP": {"version": {"qemu": {"major": 8}}}}
        self.commands = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.server.accept()
        with conn:
            conn.sendall((json.dumps(self.greeting) + "\r\n").encode())
            stream = conn.makefile("rb")
            for line in stream:
                request = json.loads(line)
                self.commands.append(request["execute"])
                result = {"status": "running"} if request["execute"] == "query-status" else {}
                reply = {"return": result, "id": request["id"]}
                conn.sendall((json.dumps(reply) + "\r\n").encode())
                if request["execute"] == "query-status":
                    break
        self.server.close()


class FakeHmpServer:
    def __init__(self, path: Path):
        self.path = path
        self.commands = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        conn, _ = self.server.accept()
        with conn:
            conn.sendall(b"QEMU monitor - type 'help' for more information\n(qemu) ")
            command = conn.recv(128)
            self.commands.append(command.decode().strip())
            conn.sendall(b"VM status: running\n(qemu) ")
        self.server.close()


class TestQemuControlPlane(unittest.TestCase):
    def test_qmp_greeting_capabilities_and_query_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qmp.sock"
            fake = FakeQmpServer(path)
            result = probe_qmp(path)
            fake.thread.join(timeout=1)
        self.assertEqual(result["state"], "QMP_READY")
        self.assertEqual(result["status"], {"status": "running"})
        self.assertEqual(fake.commands, ["qmp_capabilities", "query-status"])

    def test_hmp_executes_harmless_info_status(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "hmp.sock"
            fake = FakeHmpServer(path)
            result = probe_hmp(path)
            fake.thread.join(timeout=1)
        self.assertEqual(result["state"], "HMP_READY")
        self.assertEqual(fake.commands, ["info status"])
        self.assertIn("VM status: running", result["response"])

    def test_absent_socket_has_distinct_diagnostic(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaisesRegex(ControlError, "socket path absent"):
                probe_qmp(Path(temp) / "absent.sock")

    def test_existing_stale_file_is_connection_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "stale.sock"
            path.touch()
            with self.assertRaisesRegex(ControlError, "refused connection"):
                probe_qmp(path)

    def test_invalid_qmp_greeting_is_classified(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad-qmp.sock"
            fake = FakeQmpServer(path, greeting={"not-QMP": True})
            with self.assertRaisesRegex(ControlError, "invalid QMP greeting"):
                probe_qmp(path)
            fake.thread.join(timeout=1)

    def test_delayed_control_creation_is_retried_until_protocol_ready(self):
        with tempfile.TemporaryDirectory() as temp:
            qmp_path = Path(temp) / "qmp.sock"
            hmp_path = Path(temp) / "hmp.sock"

            def create_servers():
                time.sleep(0.15)
                FakeQmpServer(qmp_path)
                FakeHmpServer(hmp_path)

            creator = threading.Thread(target=create_servers, daemon=True)
            creator.start()
            with patch("qemu_control._process_state", return_value="running"):
                result = wait_for_control(qmp_path, hmp_path, 1234, timeout=2)
            creator.join(timeout=1)
        self.assertEqual(result["state"], "HMP_READY")

    def test_qemu_exit_before_control_readiness_is_reported(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "qemu_control._process_state", return_value="exited"
        ):
            with self.assertRaisesRegex(ControlError, "QEMU exited.*before control readiness"):
                wait_for_control(Path(temp) / "qmp.sock", Path(temp) / "hmp.sock", 42, timeout=1)

    def test_readiness_timeout_reports_last_control_error(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "qemu_control._process_state", return_value="running"
        ):
            with self.assertRaisesRegex(ControlError, "readiness timeout.*socket path absent"):
                wait_for_control(Path(temp) / "qmp.sock", Path(temp) / "hmp.sock", 42, timeout=0.05)

    def test_permission_error_is_not_collapsed_into_retry(self):
        with tempfile.TemporaryDirectory() as temp, patch(
            "qemu_control.socket.socket"
        ) as socket_factory:
            fake_socket = socket_factory.return_value
            fake_socket.connect.side_effect = PermissionError
            with self.assertRaisesRegex(ControlError, "QMP permission denied"):
                probe_qmp(Path(temp) / "protected.sock")


@unittest.skipUnless(shutil.which("qemu-system-x86_64"), "QEMU integration binary is unavailable")
class TestRealQemuControlPlane(unittest.TestCase):
    def test_real_qemu_handshake_cleanup_and_repeated_start_stop(self):
        with tempfile.TemporaryDirectory(prefix="pkos-qemu-control-") as temp:
            base = Path(temp)
            for attempt in range(2):
                qmp_path = base / f"qmp-{attempt}.sock"
                hmp_path = base / f"hmp-{attempt}.sock"
                command = [
                    shutil.which("qemu-system-x86_64"), "-machine", "q35",
                    "-nodefaults", "-display", "none", "-device", "virtio-keyboard-pci",
                    "-monitor", f"unix:{hmp_path},server,nowait",
                    "-qmp", f"unix:{qmp_path},server=on,wait=off",
                ]
                process = subprocess.Popen(
                    command,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    start_new_session=(os.name != "nt"),
                )
                try:
                    result = wait_for_control(qmp_path, hmp_path, process.pid, timeout=5)
                    self.assertEqual(result["state"], "HMP_READY")
                    self.assertEqual(result["qmp"]["status"]["status"], "running")
                    self.assertIn("VM status", result["hmp"]["response"])
                    input_client = QmpInput(qmp_path)
                    try:
                        input_client.key("grave_accent")
                    finally:
                        input_client.close()
                finally:
                    if process.poll() is None:
                        process.terminate()
                    process.wait(timeout=5)
                self.assertIsNotNone(process.poll(), "owned QEMU child remained after cleanup")
                self.assertFalse(qmp_path.exists(), "QEMU left a stale QMP socket")
                self.assertFalse(hmp_path.exists(), "QEMU left a stale HMP socket")


if __name__ == "__main__":
    unittest.main()
