#!/usr/bin/env python3
"""Bounded QMP/HMP readiness probes for an owned QEMU process."""

from __future__ import annotations

import argparse
import json
import os
import re
import socket
import sys
import time
from pathlib import Path
from typing import Any


class ControlError(RuntimeError):
    """A classified failure while bringing up QEMU's control plane."""


def _recv_prompt(sock: socket.socket, prompt: bytes, timeout: float, phase: str) -> bytes:
    sock.settimeout(timeout)
    data = bytearray()
    while prompt not in data:
        try:
            part = sock.recv(4096)
        except socket.timeout as exc:
            raise ControlError(f"HMP {phase} timeout") from exc
        if not part:
            raise ControlError("HMP connection closed before prompt")
        data.extend(part)
    return bytes(data)


def probe_qmp(path: Path, timeout: float = 1.0) -> dict[str, Any]:
    """Require a valid greeting, capabilities negotiation and query-status."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(path))
        file = sock.makefile("rwb", buffering=0)
        try:
            try:
                greeting_line = file.readline()
            except socket.timeout as exc:
                raise ControlError("QMP greeting timeout") from exc
            if not greeting_line:
                raise ControlError("QMP greeting missing")
            try:
                greeting = json.loads(greeting_line)
            except json.JSONDecodeError as exc:
                raise ControlError("invalid QMP greeting JSON") from exc
            if not isinstance(greeting, dict) or not isinstance(greeting.get("QMP"), dict):
                raise ControlError(f"invalid QMP greeting: {greeting!r}")

            serial = 0

            def execute(command: str) -> dict[str, Any]:
                nonlocal serial
                serial += 1
                request = {"execute": command, "id": serial}
                file.write((json.dumps(request) + "\r\n").encode("utf-8"))
                while True:
                    try:
                        line = file.readline()
                    except socket.timeout as exc:
                        raise ControlError(f"QMP response timeout during {command}") from exc
                    if not line:
                        raise ControlError(f"QMP closed during {command}")
                    try:
                        reply = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise ControlError(f"invalid QMP response during {command}") from exc
                    if not isinstance(reply, dict):
                        raise ControlError(f"invalid QMP response during {command}: {reply!r}")
                    if reply.get("id") != serial:
                        continue  # Ignore asynchronous QMP events.
                    if "error" in reply:
                        raise ControlError(f"QMP {command} rejected: {reply['error']}")
                    result = reply.get("return")
                    if not isinstance(result, dict):
                        raise ControlError(f"invalid QMP {command} response: {reply!r}")
                    return result

            execute("qmp_capabilities")
            status = execute("query-status")
            return {"state": "QMP_READY", "version": greeting["QMP"].get("version"), "status": status}
        finally:
            file.close()
    except PermissionError as exc:
        raise ControlError(f"QMP permission denied: {path}") from exc
    except FileNotFoundError as exc:
        raise ControlError(f"QMP socket path absent: {path}") from exc
    except ConnectionRefusedError as exc:
        raise ControlError(f"QMP socket exists but listener refused connection: {path}") from exc
    except socket.timeout as exc:
        raise ControlError("QMP greeting timeout") from exc
    finally:
        sock.close()


def probe_hmp(path: Path, timeout: float = 1.0) -> dict[str, str]:
    """Connect to HMP, consume the prompt and run harmless `info status`."""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect(str(path))
        _recv_prompt(sock, b"(qemu) ", timeout, "greeting")
        sock.sendall(b"info status\n")
        response = _recv_prompt(sock, b"(qemu) ", timeout, "command").decode("utf-8", errors="replace")
        response = re.sub(r"\x1b\[[0-9;?]*[ -/]*[@-~]", "", response)
        if "(qemu) " not in response or not response.strip():
            raise ControlError("invalid HMP info status response")
        return {"state": "HMP_READY", "response": response.strip()}
    except PermissionError as exc:
        raise ControlError(f"HMP permission denied: {path}") from exc
    except FileNotFoundError as exc:
        raise ControlError(f"HMP socket path absent: {path}") from exc
    except ConnectionRefusedError as exc:
        raise ControlError(f"HMP socket exists but listener refused connection: {path}") from exc
    except socket.timeout as exc:
        raise ControlError("HMP greeting timeout") from exc
    finally:
        sock.close()


def _process_state(pid: int) -> str:
    """Return running/exited/unknown without mistaking a zombie for running."""
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        fields = stat_path.read_text(encoding="ascii").split()
    except FileNotFoundError:
        return "exited"
    except OSError:
        try:
            os.kill(pid, 0)
            return "running"
        except ProcessLookupError:
            return "exited"
        except PermissionError:
            return "unknown"
    return "exited" if len(fields) > 2 and fields[2] == "Z" else "running"


def wait_for_control(qmp_path: Path, hmp_path: Path, pid: int, timeout: float) -> dict[str, Any]:
    """Wait for live protocol endpoints and fail promptly if owned QEMU exits."""
    deadline = time.monotonic() + timeout
    last_error = "socket path absent"
    while time.monotonic() < deadline:
        process_state = _process_state(pid)
        if process_state == "exited":
            raise ControlError(f"QEMU exited (PID {pid}) before control readiness; {last_error}")
        try:
            qmp = probe_qmp(qmp_path, timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            hmp = probe_hmp(hmp_path, timeout=min(1.0, max(0.1, deadline - time.monotonic())))
            return {"pid": pid, "state": "HMP_READY", "qmp": qmp, "hmp": hmp}
        except ControlError as exc:
            last_error = str(exc)
            # Permission, malformed protocol and protocol rejection won't heal
            # by waiting; retain their specific classification and stop.
            if any(token in last_error for token in ("permission denied", "invalid QMP", "rejected", "invalid HMP")):
                raise
            time.sleep(min(0.1, max(0.0, deadline - time.monotonic())))
    raise ControlError(f"control readiness timeout after {timeout:.1f}s; PID={pid}; last error: {last_error}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qmp", type=Path, required=True)
    parser.add_argument("--hmp", type=Path, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--timeout", type=float, default=15.0)
    args = parser.parse_args()
    try:
        report = wait_for_control(args.qmp, args.hmp, args.pid, args.timeout)
    except ControlError as exc:
        print(json.dumps({"state": "CONTROL_FAILED", "pid": args.pid, "error": str(exc)}, indent=2), file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
