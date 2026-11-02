"""Regression tests for the direct QEMU guest input harness."""

import struct
import tempfile
import unittest
from pathlib import Path
import sys
from unittest.mock import call, patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "acceptance"))

from qemu_ui import (  # noqa: E402
    QmpInput,
    RfbInput,
    RFB_TEXT_INTERVAL_SECONDS,
    wait_for_guest_query,
    monitor_reported_error,
)


class FakeSocket:
    def __init__(self):
        self.events = []

    def sendall(self, data):
        self.events.append(data)


class TestRfbInput(unittest.TestCase):
    def test_type_text_preserves_spaces(self):
        client = RfbInput.__new__(RfbInput)
        client.sock = FakeSocket()
        with patch("qemu_ui.time.sleep") as sleep:
            client.type_text("a b")
        self.assertEqual(len(client.sock.events), 6)
        self.assertEqual(client.sock.events[2], struct.pack(">BBHI", 4, 1, 0, 0x20))
        self.assertEqual(client.sock.events[3], struct.pack(">BBHI", 4, 0, 0, 0x20))
        self.assertEqual(sleep.call_args_list.count(call(RFB_TEXT_INTERVAL_SECONDS)), 3)

    def test_key_treats_literal_plus_as_a_keysym_not_an_empty_chord(self):
        client = RfbInput.__new__(RfbInput)
        client.sock = FakeSocket()
        client.key("+")
        self.assertEqual(
            client.sock.events,
            [struct.pack(">BBHI", 4, 1, 0, ord("+")), struct.pack(">BBHI", 4, 0, 0, ord("+"))],
        )

    def test_type_text_supports_mixed_case_digits_spaces_and_punctuation(self):
        client = RfbInput.__new__(RfbInput)
        client.sock = FakeSocket()
        with patch("qemu_ui.time.sleep"):
            client.type_text("Aa09 !+.,")

        keysyms = [struct.unpack(">BBHI", event)[3] for event in client.sock.events]
        self.assertEqual(
            keysyms,
            [
                0xFFE1, ord("a"), ord("a"), 0xFFE1,
                ord("a"), ord("a"), ord("0"), ord("0"),
                ord("9"), ord("9"), 0x20, 0x20,
                ord("!"), ord("!"), ord("+"), ord("+"),
                ord("."), ord("."), ord(","), ord(","),
            ],
        )
        self.assertEqual(len(client.sock.events), 20)


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

    def test_qmp_text_maps_ascii_to_acknowledged_qcode_chords(self):
        client = QmpInput.__new__(QmpInput)
        chords = []
        client.key = chords.append
        client.type_text("Aa09 !+.,")
        self.assertEqual(
            chords,
            ["shift+a", "a", "0", "9", "space", "shift+1", "shift+equal", "dot", "comma"],
        )

    def test_qmp_text_rejects_unsupported_unicode(self):
        client = QmpInput.__new__(QmpInput)
        client.key = lambda chord: None
        with self.assertRaisesRegex(ValueError, "unsupported QMP text character"):
            client.type_text("é")


    def test_qmp_qcode_accepts_named_punctuation_keys(self):
        for key in ("minus", "equal", "bracket_left", "bracket_right", "semicolon", "apostrophe", "comma", "dot", "slash", "backslash", "grave_accent"):
            with self.subTest(key=key):
                self.assertEqual(QmpInput._qcode(key), key)


class TestGuestTextAcknowledgement(unittest.TestCase):
    def test_exact_guest_log_text_is_classified_as_delivered(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            log.write_text("[INFO] Executing HUD query: exact input 123\n", encoding="utf-8")
            status, observed = wait_for_guest_query(log, "exact input 123", 0)
        self.assertEqual(status, "TEXT_DELIVERED")
        self.assertEqual(observed, ["exact input 123"])

    def test_partial_guest_log_text_is_not_reported_as_delivered(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            log.write_text("[INFO] Executing HUD query: et brightness to 50\n", encoding="utf-8")
            status, observed = wait_for_guest_query(log, "set brightness to 50", 0)
        self.assertEqual(status, "TEXT_MISMATCH")
        self.assertEqual(observed, ["et brightness to 50"])

    def test_incomplete_serial_tail_is_not_mistaken_for_submitted_text(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            log.write_text("Executing HUD query: ttt", encoding="utf-8")
            status, observed = wait_for_guest_query(log, "ttt aaa 111", 0, timeout=0)
            self.assertEqual(status, "SUBMISSION_NOT_TRIGGERED")
            self.assertEqual(observed, [])
            with log.open("a", encoding="utf-8") as stream:
                stream.write(" aaa 111\n")
            status, observed = wait_for_guest_query(log, "ttt aaa 111", 0)
        self.assertEqual(status, "TEXT_DELIVERED")
        self.assertEqual(observed, ["ttt aaa 111"])

    def test_duplicate_guest_query_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            log.write_text(
                "Executing HUD query: hello\nExecuting HUD query: hello\n",
                encoding="utf-8",
            )
            status, observed = wait_for_guest_query(log, "hello", 0)
        self.assertEqual(status, "DUPLICATED")
        self.assertEqual(observed, ["hello", "hello"])

    def test_preexisting_guest_queries_do_not_satisfy_a_new_expectation(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "serial.log"
            log.write_text("Executing HUD query: old query\n", encoding="utf-8")
            status, observed = wait_for_guest_query(log, "new query", 1, timeout=0)
        self.assertEqual(status, "SUBMISSION_NOT_TRIGGERED")
        self.assertEqual(observed, [])


class TestMonitorResponse(unittest.TestCase):
    def test_error_word_in_screenshot_path_is_not_a_monitor_failure(self):
        response = "screendump /tmp/approved-backend-error.ppm\n(qemu) "
        self.assertFalse(monitor_reported_error(response))

    def test_monitor_error_line_is_detected(self):
        response = "screendump /tmp/frame.ppm\nError: Could not save image\n(qemu) "
        self.assertTrue(monitor_reported_error(response))


if __name__ == "__main__":
    unittest.main()
