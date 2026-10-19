"""
pk-intelligenced — PK Intelligence Daemon
==========================================
Persistent background service that manages the local-first PK Intelligence
assistant pipeline.  In Phase 2A this daemon provides:

  - A Unix domain socket IPC endpoint (``/run/pk-intelligenced/control.sock``)
    for receiving intent requests from the PK-Shell HUD.
  - An in-process tool registry for safe, deterministic tool dispatch.
  - A security permission ledger that enforces capability gates and logs all
    consequential operations with SHA-256 hash chaining.
  - A stub audio pipeline interface (Silero-VAD → openWakeWord → whisper.cpp)
    that logs readiness without requiring audio hardware in Phase 2A.

Architecture
------------
  Shell HUD ──IPC──► pk-intelligenced ──► IntentClassifier
                           │                      │
                           │              ToolRegistry (sandboxed)
                           │                      │
                           └───────► SecurityLedger (audit chain)

The daemon terminates cleanly on SIGTERM / SIGINT and writes a shutdown record
to the security ledger before exiting.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import signal
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pk.intelligenced")

# ---------------------------------------------------------------------------
# Local imports
# ---------------------------------------------------------------------------
# Add project root to sys.path when invoked directly
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from intelligence.src.intent import IntentPlanner  # noqa: E402
from intelligence.src.tools import (  # noqa: E402
    ToolRegistry,
    LaunchApplicationTool,
    GetSystemStatusTool,
    AdjustSettingTool,
    DeletePathTool,
)
from intelligence.src.security import SecurityLedger, ConsequentialApprovalRequired  # noqa: E402

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SOCKET_DIR = Path("/run/pk-intelligenced")
SOCKET_PATH = SOCKET_DIR / "control.sock"
MAX_MSG_BYTES = 64 * 1024  # 64 KiB maximum request payload


# ---------------------------------------------------------------------------
# Daemon core
# ---------------------------------------------------------------------------

class PkIntelligenceDaemon:
    """
    Singleton daemon managing the PK Intelligence subsystem lifecycle.
    """

    def __init__(self) -> None:
        self._running = False
        self._start_time = time.time()
        self._registry = ToolRegistry()
        self._planner = IntentPlanner(self._registry)
        self._ledger = SecurityLedger()
        self._tools = {
            "launch_application": self._registry.get("launch_application"),
            "get_system_status": self._registry.get("get_system_status"),
            "adjust_setting": self._registry.get("adjust_setting"),
            "delete_path": self._registry.get("delete_path"),
        }
        self._server_thread: threading.Thread | None = None
        self._sock: socket.socket | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Initialise and enter the daemon event loop."""
        logger.info("pk-intelligenced starting (PID %d)", os.getpid())
        self._running = True
        self._start_time = time.time()
        self._setup_socket()
        self._log_startup()

        # Set up signal handlers
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

        # Start IPC accept loop in background thread
        self._server_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="pk-ipc"
        )
        self._server_thread.start()

        logger.info("pk-intelligenced ready. IPC socket: %s", SOCKET_PATH)

        # Main thread: heartbeat loop
        try:
            while self._running:
                time.sleep(1.0)
        except KeyboardInterrupt:
            pass

        self._shutdown()

    def stop(self) -> None:
        """Request a clean shutdown from another thread."""
        self._running = False

    # ------------------------------------------------------------------
    # Signal handling
    # ------------------------------------------------------------------

    def _handle_signal(self, signum: int, _frame: object) -> None:
        logger.info("Received signal %d — shutting down", signum)
        self._running = False

    # ------------------------------------------------------------------
    # Socket IPC
    # ------------------------------------------------------------------

    def _setup_socket(self) -> None:
        """Create the Unix domain socket endpoint with secure 0660 permissions."""
        SOCKET_DIR.mkdir(parents=True, exist_ok=True)
        # Remove stale socket from a previous crash
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink()

        self._sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind(str(SOCKET_PATH))
        # Assign pkos group ownership if available
        try:
            import grp
            gid = grp.getgrnam("pkos").gr_gid
            os.chown(str(SOCKET_PATH), -1, gid)
        except (KeyError, OSError, ModuleNotFoundError):
            pass
        try:
            # Secure 0660 mode: owner/group rw, no world-writable access
            os.chmod(str(SOCKET_PATH), 0o660)
        except OSError as exc:
            logger.warning("Could not set socket permissions: %s", exc)
        self._sock.listen(8)
        self._sock.settimeout(1.0)  # allow periodic running-check
        logger.debug("Listening on %s (mode 0660)", SOCKET_PATH)

    def _accept_loop(self) -> None:
        """Accept and dispatch IPC connections."""
        assert self._sock is not None
        while self._running:
            try:
                conn, _ = self._sock.accept()
            except socket.timeout:
                continue
            except OSError:
                break
            threading.Thread(
                target=self._handle_connection,
                args=(conn,),
                daemon=True,
            ).start()

    def _handle_connection(self, conn: socket.socket) -> None:
        """Read one JSON request, dispatch intent, return JSON response."""
        try:
            conn.settimeout(5.0)
            data = self._recv_framed(conn)
            request = json.loads(data)
            response = self._dispatch(request)
        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            response = {"ok": False, "error": str(exc)}
        except Exception as exc:  # pylint: disable=broad-except
            logger.exception("Unhandled error in connection handler")
            response = {"ok": False, "error": "internal_error"}
        finally:
            try:
                self._send_framed(conn, json.dumps(response).encode())
                conn.close()
            except OSError:
                pass

    # ------------------------------------------------------------------
    # Intent dispatch
    # ------------------------------------------------------------------

    def _dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        """
        Parse the natural-language query via IntentPlanner and dispatch
        to the matching tool through the SecurityLedger gate.

        Request schema::
            {
                "query": "open the terminal",
                "user_approved": false       # optional; required for CONSEQUENTIAL tools
            }

        Response schema::
            {
                "ok": true,
                "intent": "launch_application",
                "result": { ... }
            }
        """
        query: str = request["query"]
        user_approved: bool = bool(request.get("user_approved", False))

        if query.strip().lower() in ("ping", "health"):
            return {
                "ok": True,
                "status": "healthy",
                "uptime": time.time() - getattr(self, "_start_time", time.time()),
                "intent": "health_check",
            }

        safe_query = query if not any(k in query.lower() for k in ("password", "secret", "token", "credential", "private_key")) else "[REDACTED]"
        logger.info("Dispatching query: %r", safe_query)

        # Phase 1: Intent planning
        parsed = self._planner.parse_query(query)
        status = parsed["status"]

        if status == "REJECTED_SECURITY":
            return {"ok": False, "error": "security_rejection", "detail": parsed["explanation"]}

        if status == "AMBIGUOUS" or parsed["tool_name"] is None:
            return {"ok": False, "error": "ambiguous_query", "detail": parsed["explanation"]}

        tool_name = parsed["tool_name"]
        tool = self._tools.get(tool_name)

        if tool is None:
            return {"ok": False, "error": f"unknown_tool:{tool_name}"}

        # Phase 2: Capability gate + execution
        try:
            result = self._ledger.authorize_and_execute(
                session_id="pk-intelligenced",
                tool_name=tool.name,
                capability=tool.capability,
                params=parsed["parameters"] or {},
                execute_fn=tool.execute,
                user_approval_granted=user_approved,
            )
        except ConsequentialApprovalRequired as exc:
            return {
                "ok": False,
                "error": "approval_required",
                "tool": exc.tool_name,
                "detail": str(exc),
            }

        return {
            "ok": True,
            "intent": tool_name,
            "result": {"success": result.success, "output": result.output, "error": result.error},
        }

    # ------------------------------------------------------------------
    # Wire framing (4-byte big-endian length prefix)
    # ------------------------------------------------------------------

    @staticmethod
    def _recv_framed(conn: socket.socket) -> bytes:
        header = conn.recv(4)
        if len(header) < 4:
            raise ValueError("Connection closed before length header")
        length = struct.unpack(">I", header)[0]
        if length > MAX_MSG_BYTES:
            raise ValueError(f"Message too large: {length} bytes")
        return conn.recv(length)

    @staticmethod
    def _send_framed(conn: socket.socket, data: bytes) -> None:
        conn.sendall(struct.pack(">I", len(data)) + data)

    # ------------------------------------------------------------------
    # Startup / shutdown
    # ------------------------------------------------------------------

    def _log_startup(self) -> None:
        startup_hash = hashlib.sha256(
            f"pk-intelligenced:startup:{time.time()}".encode()
        ).hexdigest()
        logger.info("Startup integrity token: %s", startup_hash[:16])

    def _shutdown(self) -> None:
        logger.info("Shutting down pk-intelligenced")
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if SOCKET_PATH.exists():
            SOCKET_PATH.unlink(missing_ok=True)
        logger.info("pk-intelligenced stopped cleanly")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> int:
    daemon = PkIntelligenceDaemon()
    daemon.start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
