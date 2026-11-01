"""Regression tests for the direct QEMU guest input harness."""

import struct
import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from qemu_ui import QmpInput, RfbInput  # noqa: E402


class FakeSocket:
    def __init__(self):
        self.events = []

    def sendall(self, data):
        self.events.append(data)


class TestRfbInput(unittest.TestCase):
    def test_type_text_preserves_spaces(self):
        client = RfbInput.__new__(RfbInput)
        client.sock = FakeSocket()
        client.type_text("a b")
        self.assertEqual(len(client.sock.events), 6)
        self.assertEqual(client.sock.events[2], struct.pack(">BBHI", 4, 1, 0, 0x20))
        self.assertEqual(client.sock.events[3], struct.pack(">BBHI", 4, 0, 0, 0x20))


class TestQmpCoordinates(unittest.TestCase):
    def test_pointer_coordinates_scale_to_tablet_range(self):
        client = QmpInput.__new__(QmpInput)
        captured = []
        client.send = lambda *events: captured.append(events)
        client.click(639, 399, 1280, 800)
        self.assertEqual(captured[0][0]["data"], {"axis": "x", "value": 16371})
        self.assertEqual(captured[0][1]["data"], {"axis": "y", "value": 16363})
        self.assertTrue(captured[1][0]["data"]["down"])
        self.assertFalse(captured[2][0]["data"]["down"])


if __name__ == "__main__":
    unittest.main()
