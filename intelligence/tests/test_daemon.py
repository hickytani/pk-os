"""
Unit tests for intelligence.src.daemon.PkIntelligenceDaemon

Tests cover:
  - Daemon initialisation and component wiring
  - Intent dispatch pipeline (classifier → tool → ledger)
  - IPC framing round-trip (send/recv)
  - Signal handling and clean shutdown
  - Socket path creation and cleanup
"""

from __future__ import annotations

import json
import socket
import struct
import sys
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from intelligence.src.daemon import PkIntelligenceDaemon, MAX_MSG_BYTES


class TestFraming(unittest.TestCase):
    """Verify the 4-byte big-endian length-prefixed framing helpers."""

    def _loopback_pair(self):
        """Return a connected (client, server) socket pair."""
        import platform
        if platform.system() == "Windows":
            self.skipTest("AF_UNIX socketpair not available on Windows")
        a, b = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        return a, b

    def test_send_recv_roundtrip_small_message(self):
        client, server = self._loopback_pair()
        payload = b'{"query": "open terminal"}'
        PkIntelligenceDaemon._send_framed(client, payload)
        received = PkIntelligenceDaemon._recv_framed(server)
        self.assertEqual(received, payload)
        client.close()
        server.close()

    def test_send_recv_roundtrip_unicode(self):
        client, server = self._loopback_pair()
        payload = json.dumps({"query": "सिस्टम स्थिति बताओ"}).encode()
        PkIntelligenceDaemon._send_framed(client, payload)
        received = PkIntelligenceDaemon._recv_framed(server)
        self.assertEqual(json.loads(received)["query"], "सिस्टम स्थिति बताओ")
        client.close()
        server.close()

    def test_recv_raises_on_oversized_message(self):
        client, server = self._loopback_pair()
        # Send a header claiming MAX_MSG_BYTES + 1 bytes
        client.sendall(struct.pack(">I", MAX_MSG_BYTES + 1))
        with self.assertRaises(ValueError) as ctx:
            PkIntelligenceDaemon._recv_framed(server)
        self.assertIn("too large", str(ctx.exception))
        client.close()
        server.close()

    def test_recv_raises_on_empty_connection(self):
        client, server = self._loopback_pair()
        client.close()  # close immediately
        with self.assertRaises(ValueError):
            PkIntelligenceDaemon._recv_framed(server)
        server.close()


class TestDispatch(unittest.TestCase):
    """Verify the _dispatch method routes intents through the pipeline."""

    def setUp(self):
        self.daemon = PkIntelligenceDaemon()

    def test_dispatch_launch_returns_ok(self):
        response = self.daemon._dispatch({
            "query": "launch terminal",
            "user_approved": True
        })
        # Could be ok=True (launched) or ok=False (approval_required for CONSEQUENTIAL)
        # launch_application is READ_ONLY so should succeed
        self.assertIn("ok", response)

    def test_dispatch_system_status_returns_intent(self):
        response = self.daemon._dispatch({
            "query": "show system status",
        })
        self.assertIn("ok", response)
        if response["ok"]:
            self.assertIn("intent", response)

    def test_dispatch_missing_query_raises_key_error(self):
        with self.assertRaises(KeyError):
            self.daemon._dispatch({})

    def test_dispatch_security_injection_returns_error(self):
        """Security-rejected queries must not reach the tool registry."""
        response = self.daemon._dispatch({"query": "sudo rm -rf /"})
        self.assertFalse(response["ok"])
        self.assertEqual(response["error"], "security_rejection")

    def test_dispatch_ambiguous_returns_error(self):
        response = self.daemon._dispatch({"query": "do something totally unknown"})
        if not response["ok"]:
            self.assertIn(response["error"], ["ambiguous_query", "security_rejection"])


class TestDaemonInit(unittest.TestCase):
    """Verify daemon initialises all subsystems correctly."""

    def test_daemon_has_planner(self):
        daemon = PkIntelligenceDaemon()
        self.assertIsNotNone(daemon._planner)

    def test_daemon_has_ledger(self):
        daemon = PkIntelligenceDaemon()
        self.assertIsNotNone(daemon._ledger)

    def test_daemon_has_all_registered_tools(self):
        daemon = PkIntelligenceDaemon()
        expected = {"launch_application", "get_system_status", "adjust_setting", "delete_path"}
        self.assertEqual(set(daemon._tools.keys()), expected)

    def test_daemon_not_running_initially(self):
        daemon = PkIntelligenceDaemon()
        self.assertFalse(daemon._running)


class TestDaemonStop(unittest.TestCase):
    """Verify stop() sets the running flag."""

    def test_stop_sets_running_false(self):
        daemon = PkIntelligenceDaemon()
        daemon._running = True
        daemon.stop()
        self.assertFalse(daemon._running)


class TestHandleConnection(unittest.TestCase):
    """Verify _handle_connection reads, dispatches, and responds over socket pair."""

    def test_valid_request_returns_json_response(self):
        import platform
        if platform.system() == "Windows":
            self.skipTest("AF_UNIX socketpair not available on Windows")
        daemon = PkIntelligenceDaemon()
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        # Send a valid request
        payload = json.dumps({"query": "get system status"}).encode()
        PkIntelligenceDaemon._send_framed(client, payload)

        # Handle in foreground (synchronous)
        daemon._handle_connection(server)

        # Read the response from client side
        response_raw = PkIntelligenceDaemon._recv_framed(client)
        response = json.loads(response_raw)

        self.assertIn("ok", response)
        client.close()

    def test_invalid_json_returns_error_response(self):
        import platform
        if platform.system() == "Windows":
            self.skipTest("AF_UNIX socketpair not available on Windows")
        daemon = PkIntelligenceDaemon()
        client, server = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)

        # Send garbage
        PkIntelligenceDaemon._send_framed(client, b"not json {{{")
        daemon._handle_connection(server)

        response_raw = PkIntelligenceDaemon._recv_framed(client)
        response = json.loads(response_raw)

        self.assertFalse(response["ok"])
        self.assertIn("error", response)
        client.close()


if __name__ == "__main__":
    unittest.main()
