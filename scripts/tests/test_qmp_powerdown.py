"""Protocol checks for the isolated QMP graceful-powerdown helper."""

import json
import socket
import sys
import tempfile
import threading
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from qmp_powerdown import execute  # noqa: E402


class FakeQmpServer:
    def __init__(self, path: Path, fail_command: str | None = None):
        self.path = path
        self.fail_command = fail_command
        self.commands = []
        self.errors = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(path))
        self.server.listen(1)
        self.thread = threading.Thread(target=self._serve, daemon=True)
        self.thread.start()

    def _serve(self):
        try:
            with self.server.accept()[0] as connection:
                connection.settimeout(2)
                connection.sendall(b'{"QMP":{"version":{}}}\r\n')
                stream = connection.makefile("rb")
                for line in stream:
                    request = json.loads(line)
                    command = request["execute"]
                    self.commands.append(command)
                    if command == self.fail_command:
                        response = {"error": {"class": "GenericError", "desc": "rejected"}}
                    else:
                        response = {"return": {}}
                    response["id"] = request["id"]
                    connection.sendall((json.dumps(response) + "\r\n").encode())
                    if command != "qmp_capabilities":
                        break
        except Exception as exc:  # Keep fake-server failures visible to the test.
            self.errors.append(exc)
        self.server.close()


class TestQmpPowerdown(unittest.TestCase):
    def test_negotiates_and_requests_graceful_powerdown(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qmp.sock"
            server = FakeQmpServer(path)
            try:
                result = execute(path, "system_powerdown")
            except (OSError, ValueError):
                server.thread.join(timeout=3)
                self.fail(f"fake QMP server commands={server.commands!r}, errors={server.errors!r}")
            server.thread.join(timeout=1)
        self.assertEqual(result, {})
        self.assertEqual(server.commands, ["qmp_capabilities", "system_powerdown"])
        self.assertEqual(server.errors, [])

    def test_reports_qmp_rejection(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "qmp.sock"
            server = FakeQmpServer(path, fail_command="system_powerdown")
            with self.assertRaisesRegex(RuntimeError, "system_powerdown failed.*rejected"):
                execute(path, "system_powerdown")
            server.thread.join(timeout=1)
        self.assertEqual(server.commands, ["qmp_capabilities", "system_powerdown"])
        self.assertEqual(server.errors, [])


if __name__ == "__main__":
    unittest.main()
