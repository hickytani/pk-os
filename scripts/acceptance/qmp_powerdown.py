#!/usr/bin/env python3
"""Request graceful ACPI guest powerdown through a QMP Unix socket."""

from __future__ import annotations

import argparse
import json
import socket
import sys
from pathlib import Path


def execute(path: Path, command: str, timeout: float = 5.0) -> dict:
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
        client.settimeout(timeout)
        client.connect(str(path))
        stream = client.makefile("rwb", buffering=0)
        try:
            greeting = json.loads(stream.readline())
            if not isinstance(greeting, dict) or "QMP" not in greeting:
                raise RuntimeError(f"invalid QMP greeting: {greeting!r}")
            for serial, request in ((1, "qmp_capabilities"), (2, command)):
                stream.write((json.dumps({"execute": request, "id": serial}) + "\r\n").encode())
                while True:
                    response = json.loads(stream.readline())
                    if response.get("id") != serial:
                        continue
                    if "error" in response:
                        raise RuntimeError(f"QMP {request} failed: {response['error']}")
                    print(f"QMP {request}: accepted")
                    if request == command:
                        return response.get("return", {})
                    break
        finally:
            stream.close()
    raise RuntimeError("QMP command returned no response")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("socket", type=Path, help="owned QEMU QMP socket")
    args = parser.parse_args()
    try:
        execute(args.socket, "system_powerdown")
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as exc:
        print(f"QMP powerdown failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
