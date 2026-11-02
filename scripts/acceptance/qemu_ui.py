#!/usr/bin/env python3
"""Send deterministic keyboard and pointer input to a running QEMU guest.

Input uses the standard VNC RFB protocol; screenshots use QEMU's human monitor.
This keeps acceptance tests independent of a host browser or GUI automation
package. Example actions JSON: [{"key":"alt+3"},{"screenshot":"settings"}].
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import struct
import sys
import time
from pathlib import Path
from typing import Any


KEYSYMS = {
    "tab": 0xFF09,
    "return": 0xFF0D,
    "enter": 0xFF0D,
    "escape": 0xFF1B,
    "space": 0x20,
    "backspace": 0xFF08,
    "alt": 0xFFE9,
    "ctrl": 0xFFE3,
    "shift": 0xFFE1,
    "super": 0xFFEB,
    "up": 0xFF52,
    "down": 0xFF54,
    "left": 0xFF51,
    "right": 0xFF53,
}

# Pace RFB typing so a small, loaded guest does not lose adjacent key events.
RFB_KEY_HOLD_SECONDS = 0.05
RFB_TEXT_INTERVAL_SECONDS = 0.12


def recv_exact(sock: socket.socket, count: int) -> bytes:
    chunks = bytearray()
    while len(chunks) < count:
        data = sock.recv(count - len(chunks))
        if not data:
            raise ConnectionError("VNC server closed the connection")
        chunks.extend(data)
    return bytes(chunks)


def monitor_reported_error(response: str) -> bool:
    """Match QEMU monitor error lines without flagging an error word in a path."""
    return re.search(
        r"(?im)^\s*(?:error\b|failed\b|screendump\s*:\s*(?:failed|error)\b)",
        response,
    ) is not None


class RfbInput:
    """Minimal RFB 3.8 client supporting QEMU's unauthenticated test VNC."""

    def __init__(self, host: str, port: int, timeout: float = 5.0):
        self.sock = socket.create_connection((host, port), timeout=timeout)
        self.sock.settimeout(timeout)
        version = recv_exact(self.sock, 12)
        if not version.startswith(b"RFB 003."):
            raise RuntimeError(f"Unsupported RFB version: {version!r}")
        self.sock.sendall(b"RFB 003.008\n")
        count = recv_exact(self.sock, 1)[0]
        security_types = recv_exact(self.sock, count)
        if 1 not in security_types:
            raise RuntimeError(f"VNC requires unsupported security types: {security_types!r}")
        self.sock.sendall(b"\x01")  # Security type: None (isolated local test VM)
        result = struct.unpack(">I", recv_exact(self.sock, 4))[0]
        if result:
            raise RuntimeError("VNC security negotiation failed")
        self.sock.sendall(b"\x01")  # Shared desktop
        header = recv_exact(self.sock, 24)
        self.width, self.height = struct.unpack(">HH", header[:4])
        name_len = struct.unpack(">I", header[20:24])[0]
        self.name = recv_exact(self.sock, name_len).decode("utf-8", errors="replace")

    def key(self, chord: str) -> None:
        if chord == " ":
            self._key_event(True, 0x20)
            self._key_event(False, 0x20)
            return
        # Printable plus is itself a valid keysym. Parse a one-character
        # printable input before treating '+' as a modifier separator.
        if len(chord) == 1 and chord.isascii():
            keysyms = [self._keysym(chord)]
        else:
            keys = [part.strip().lower() for part in chord.split("+") if part.strip()]
            if not keys:
                raise ValueError("empty key chord")
            keysyms = [self._keysym(item) for item in keys]
        # Hold modifiers, tap the final key, then release everything.
        for keysym in keysyms[:-1]:
            self._key_event(True, keysym)
            time.sleep(RFB_KEY_HOLD_SECONDS)
        self._key_event(True, keysyms[-1])
        time.sleep(RFB_KEY_HOLD_SECONDS)
        self._key_event(False, keysyms[-1])
        for keysym in reversed(keysyms[:-1]):
            self._key_event(False, keysym)

    def type_text(self, text: str) -> None:
        for char in text:
            if char.isascii() and char.isupper():
                self.key("shift+" + char.lower())
            else:
                self.key(char)
            time.sleep(RFB_TEXT_INTERVAL_SECONDS)

    def click(self, x: int, y: int) -> None:
        if not 0 <= x < self.width or not 0 <= y < self.height:
            raise ValueError(f"pointer ({x}, {y}) outside {self.width}x{self.height} framebuffer")
        self.sock.sendall(struct.pack(">BBHH", 5, 1, x, y))
        time.sleep(0.08)
        self.sock.sendall(struct.pack(">BBHH", 5, 0, x, y))

    def _keysym(self, key: str) -> int:
        if key in KEYSYMS:
            return KEYSYMS[key]
        if len(key) == 1 and key.isascii():
            return ord(key)
        raise ValueError(f"unsupported key: {key}")

    def _key_event(self, down: bool, keysym: int) -> None:
        self.sock.sendall(struct.pack(">BBHI", 4, int(down), 0, keysym))

    def close(self) -> None:
        self.sock.close()


class QmpInput:
    """QMP keyboard and absolute-tablet input for reliable GUI acceptance."""

    def __init__(self, path: Path, timeout: float = 5.0):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(str(path))
        self.file = self.sock.makefile("rwb", buffering=0)
        greeting = json.loads(self.file.readline())
        if "QMP" not in greeting:
            raise RuntimeError(f"Invalid QMP greeting: {greeting!r}")
        self.serial = 0
        self.execute("qmp_capabilities")

    def execute(self, command: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        self.serial += 1
        request: dict[str, Any] = {"execute": command, "id": self.serial}
        if arguments is not None:
            request["arguments"] = arguments
        self.file.write((json.dumps(request) + "\r\n").encode("utf-8"))
        while True:
            reply = json.loads(self.file.readline())
            if reply.get("id") == self.serial:
                if "error" in reply:
                    raise RuntimeError(f"QMP {command} failed: {reply['error']}")
                return reply.get("return", {})

    def send(self, *events: dict[str, Any]) -> None:
        self.execute("input-send-event", {"events": list(events)})

    def key(self, chord: str) -> None:
        keys = [part.strip().lower() for part in chord.split("+") if part.strip()]
        qcodes = [self._qcode(key) for key in keys]
        self.send(*({"type": "key", "data": {"down": True, "key": {"type": "qcode", "data": code}}} for code in qcodes))
        time.sleep(0.03)
        self.send(*({"type": "key", "data": {"down": False, "key": {"type": "qcode", "data": code}}} for code in reversed(qcodes)))

    def type_text(self, text: str) -> None:
        """Type ASCII text using QMP qcodes and await each command reply."""
        shifted = {
            "!": "shift+1", "@": "shift+2", "#": "shift+3", "$": "shift+4",
            "%": "shift+5", "^": "shift+6", "&": "shift+7", "*": "shift+8",
            "(": "shift+9", ")": "shift+0", "_": "shift+minus", "+": "shift+equal",
            "{": "shift+bracket_left", "}": "shift+bracket_right", ":": "shift+semicolon",
            '"': "shift+apostrophe", "<": "shift+comma", ">": "shift+dot",
            "?": "shift+slash", "|": "shift+backslash", "~": "shift+grave_accent_and_tilde",
        }
        plain = {
            " ": "space", "-": "minus", "=": "equal", "[": "bracket_left",
            "]": "bracket_right", ";": "semicolon", "'": "apostrophe",
            ",": "comma", ".": "dot", "/": "slash", "\\": "backslash", "`": "grave_accent_and_tilde",
        }
        for char in text:
            if char in shifted:
                chord = shifted[char]
            elif char in plain:
                chord = plain[char]
            elif char.isascii() and char.isalpha():
                chord = ("shift+" if char.isupper() else "") + char.lower()
            elif char.isascii() and char.isdigit():
                chord = char
            else:
                raise ValueError(f"unsupported QMP text character: {char!r}")
            self.key(chord)

    def click(self, x: int, y: int, width: int, height: int) -> None:
        self.send(
            {"type": "abs", "data": {"axis": "x", "value": round(x * 32767 / max(1, width - 1))}},
            {"type": "abs", "data": {"axis": "y", "value": round(y * 32767 / max(1, height - 1))}},
        )
        self.send({"type": "btn", "data": {"down": True, "button": "left"}})
        time.sleep(0.08)
        self.send({"type": "btn", "data": {"down": False, "button": "left"}})

    @staticmethod
    def _qcode(key: str) -> str:
        aliases = {"return": "ret", "enter": "ret", "escape": "esc", "backspace": "backspace", "tab": "tab", "space": "spc", "alt": "alt", "ctrl": "ctrl", "shift": "shift", "super": "meta_l", "up": "up", "down": "down", "left": "left", "right": "right"}
        aliases.update({key: key for key in ("minus", "equal", "bracket_left", "bracket_right", "semicolon", "apostrophe", "comma", "dot", "slash", "backslash", "grave_accent_and_tilde")})
        if key in aliases:
            return aliases[key]
        if len(key) == 1 and key.isascii() and key.isalnum():
            return key.lower()
        raise ValueError(f"unsupported QMP key: {key}")

    def close(self) -> None:
        self.file.close()
        self.sock.close()


class HmpMonitor:
    def __init__(self, path: Path, timeout: float = 8.0):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(timeout)
        self.sock.connect(str(path))
        self._read_prompt()

    def command(self, command: str) -> str:
        self.sock.sendall(command.encode("utf-8") + b"\n")
        return self._read_prompt()

    def _read_prompt(self) -> str:
        data = bytearray()
        while b"(qemu) " not in data:
            part = self.sock.recv(4096)
            if not part:
                raise ConnectionError("QEMU monitor closed the connection")
            data.extend(part)
        return data.decode("utf-8", errors="replace")

    def close(self) -> None:
        self.sock.close()


def guest_query_log_entries(path: Path) -> list[str]:
    """Read only shell-submitted query strings from the guest serial journal."""
    if not path.is_file():
        return []
    entries = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        marker = "Executing HUD query: "
        if marker in line:
            entries.append(line.split(marker, 1)[1].rstrip("\r"))
    return entries


def wait_for_guest_query(
    path: Path, expected: str, cursor: int, timeout: float = 8.0
) -> tuple[str, list[str]]:
    """Classify text from the guest itself, with a bounded submission wait."""
    deadline = time.monotonic() + timeout
    observed: list[str] = []
    while time.monotonic() < deadline:
        entries = guest_query_log_entries(path)
        observed = entries[cursor:]
        if observed:
            if len(observed) > 1:
                status = "DUPLICATED" if all(item == expected for item in observed) else "MULTIPLE_OR_MISMATCHED"
            elif observed[0] == expected:
                status = "TEXT_DELIVERED"
            else:
                status = "TEXT_MISMATCH"
            return status, observed
        time.sleep(0.1)
    return "SUBMISSION_NOT_TRIGGERED", observed


def run_steps(args: argparse.Namespace) -> dict[str, Any]:
    steps = json.loads(args.steps.read_text(encoding="utf-8-sig"))
    if not isinstance(steps, list):
        raise ValueError("steps JSON must be a list")
    args.output.mkdir(parents=True, exist_ok=True)
    rfb = RfbInput(args.vnc_host, args.vnc_port)
    monitor = HmpMonitor(args.monitor_socket)
    qmp = QmpInput(args.qmp_socket) if args.qmp_socket else None
    query_cursor = len(guest_query_log_entries(args.guest_log)) if args.guest_log else 0
    evidence = {
        "framebuffer": {"width": rfb.width, "height": rfb.height, "name": rfb.name},
        "input_transport": {
            "keyboard": "RFB and QMP qcodes" if qmp else "RFB",
            "pointer": "QMP absolute tablet" if qmp else "RFB pointer events",
        },
        "steps": [],
    }
    try:
        for index, step in enumerate(steps, start=1):
            if not isinstance(step, dict) or len(step) != 1:
                raise ValueError(f"step {index} must have exactly one action")
            action, value = next(iter(step.items()))
            if action == "key":
                rfb.key(str(value))
            elif action == "text":
                rfb.type_text(str(value))
            elif action == "key_qmp":
                if not qmp:
                    raise ValueError(f"step {index}: key_qmp requires --qmp-socket")
                qmp.key(str(value))
            elif action == "text_qmp":
                if not qmp:
                    raise ValueError(f"step {index}: text_qmp requires --qmp-socket")
                qmp.type_text(str(value))
            elif action == "expect_query":
                if not args.guest_log:
                    raise ValueError(f"step {index}: expect_query requires --guest-log")
                status, observed = wait_for_guest_query(args.guest_log, str(value), query_cursor)
                query_cursor += len(observed)
                evidence["steps"].append({
                    "index": index, "action": action, "expected": str(value),
                    "observed": observed, "status": status,
                })
                continue
            elif action == "click":
                if not isinstance(value, list) or len(value) != 2:
                    raise ValueError(f"step {index}: click must be [x, y]")
                if qmp:
                    qmp.click(int(value[0]), int(value[1]), rfb.width, rfb.height)
                else:
                    rfb.click(int(value[0]), int(value[1]))
            elif action == "wait":
                time.sleep(max(0, min(float(value), 10)))
            elif action == "screenshot":
                name = Path(str(value)).name
                if not name or name in (".", ".."):
                    raise ValueError(f"step {index}: invalid screenshot name")
                target = args.output / f"{name}.ppm"
                response = monitor.command(f"screendump {target}")
                if monitor_reported_error(response):
                    raise RuntimeError(response)
                if not target.is_file() or target.stat().st_size == 0:
                    raise RuntimeError(f"QEMU did not create a screenshot: {response}")
                evidence["steps"].append({"index": index, "action": action, "path": str(target)})
                continue
            else:
                raise ValueError(f"step {index}: unsupported action {action!r}")
            evidence["steps"].append({"index": index, "action": action, "value": value})
        evidence_path = args.output / "ui-input-evidence.json"
        evidence_path.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return evidence
    finally:
        monitor.close()
        if qmp:
            qmp.close()
        rfb.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--monitor-socket", type=Path, required=True)
    parser.add_argument("--qmp-socket", type=Path)
    parser.add_argument("--steps", type=Path, required=True, help="JSON action sequence")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--vnc-host", default="127.0.0.1")
    parser.add_argument("--vnc-port", type=int, default=5999)
    parser.add_argument("--guest-log", type=Path, help="serial log used by expect_query actions")
    args = parser.parse_args()
    try:
        report = run_steps(args)
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"UI acceptance input failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    failed_queries = [
        item for item in report["steps"]
        if item.get("action") == "expect_query" and item.get("status") != "TEXT_DELIVERED"
    ]
    if failed_queries:
        print(f"{len(failed_queries)} guest text assertion(s) failed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
