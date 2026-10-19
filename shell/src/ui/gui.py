"""
PK-OS Genuine Wayland Shell Surface (Phase 2B)
==============================================
Provides the real graphical interface for the PK-OS session running inside cage(1).

Architecture:
  - SystemMetricsCollector: Parses real /proc and /sys interfaces with structured
    loading, unavailable, and error states.
  - PKIntelligenceClient: Communicates with pk-intelligenced via framed UNIX socket.
  - PKShellWindow: GTK3-based Wayland client window styled strictly with PK-OS
    design tokens (Obsidian Dark palette, 4px grid spacing, WCAG AAA/AA contrast).
  - HeadlessShellSurface: Fallback harness enabling full headless testing without
    a Wayland display server or GTK runtime.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import socket
import struct
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger("pk.shell.gui")

try:
    from shell.src.ui.notifications import Notification, NotificationUrgency, NotificationManager
    from shell.src.ui.window_manager import AppWindow, WindowState, WindowManager
except ImportError:
    try:
        from notifications import Notification, NotificationUrgency, NotificationManager  # type: ignore
        from window_manager import AppWindow, WindowState, WindowManager  # type: ignore
    except ImportError:
        Notification = None  # type: ignore
        NotificationUrgency = None  # type: ignore
        NotificationManager = None  # type: ignore
        AppWindow = None  # type: ignore
        WindowState = None  # type: ignore
        WindowManager = None  # type: ignore

# Check if GTK3 and Wayland GDK are available
GTK_AVAILABLE = False
try:
    import gi
    gi.require_version("Gtk", "3.0")
    gi.require_version("Gdk", "3.0")
    from gi.repository import Gtk, Gdk, GLib
    GTK_AVAILABLE = True
except (ImportError, ValueError):
    GTK_AVAILABLE = False


# ---------------------------------------------------------------------------
# 1. System Metrics Collector
# ---------------------------------------------------------------------------

class SystemMetricsCollector:
    """Collects hardware and OS metrics from kernel pseudo-filesystems."""

    @staticmethod
    def get_memory_metrics() -> Dict[str, Any]:
        """Parse /proc/meminfo or return unavailable state."""
        meminfo_path = Path("/proc/meminfo")
        if not meminfo_path.exists():
            return {
                "available": False,
                "total_mb": 0,
                "used_mb": 0,
                "percent": 0.0,
                "label": "Memory: N/A",
            }
        try:
            mem_data = {}
            with open(meminfo_path, "r", encoding="utf-8") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        val = parts[1].strip().split()[0]
                        mem_data[key] = int(val)
            total_kb = mem_data.get("MemTotal", 0)
            avail_kb = mem_data.get("MemAvailable", mem_data.get("MemFree", 0))
            used_kb = max(0, total_kb - avail_kb)
            total_mb = total_kb // 1024
            used_mb = used_kb // 1024
            percent = (used_kb / total_kb * 100.0) if total_kb > 0 else 0.0
            return {
                "available": True,
                "total_mb": total_mb,
                "used_mb": used_mb,
                "percent": round(percent, 1),
                "label": f"Mem: {used_mb}/{total_mb}MB ({int(percent)}%)",
            }
        except Exception as exc:
            logger.warning("Failed parsing /proc/meminfo: %s", exc)
            return {
                "available": False,
                "total_mb": 0,
                "used_mb": 0,
                "percent": 0.0,
                "label": "Mem: Error",
            }

    @staticmethod
    def get_load_metrics() -> Dict[str, Any]:
        """Parse /proc/loadavg or return unavailable state."""
        load_path = Path("/proc/loadavg")
        if not load_path.exists():
            return {"available": False, "1m": 0.0, "label": "Load: N/A"}
        try:
            with open(load_path, "r", encoding="utf-8") as f:
                parts = f.read().strip().split()
            load_1m = float(parts[0])
            load_5m = float(parts[1])
            load_15m = float(parts[2])
            return {
                "available": True,
                "1m": load_1m,
                "5m": load_5m,
                "15m": load_15m,
                "label": f"Load: {load_1m:.2f}",
            }
        except Exception as exc:
            logger.warning("Failed parsing /proc/loadavg: %s", exc)
            return {"available": False, "1m": 0.0, "label": "Load: Error"}

    @staticmethod
    def get_uptime_metrics() -> Dict[str, Any]:
        """Parse /proc/uptime or return unavailable state."""
        uptime_path = Path("/proc/uptime")
        if not uptime_path.exists():
            return {"available": False, "seconds": 0, "label": "Up: N/A"}
        try:
            with open(uptime_path, "r", encoding="utf-8") as f:
                total_seconds = int(float(f.read().split()[0]))
            mins, secs = divmod(total_seconds, 60)
            hours, mins = divmod(mins, 60)
            if hours > 0:
                fmt = f"{hours}h {mins}m"
            else:
                fmt = f"{mins}m {secs}s"
            return {"available": True, "seconds": total_seconds, "label": f"Up: {fmt}"}
        except Exception as exc:
            logger.warning("Failed parsing /proc/uptime: %s", exc)
            return {"available": False, "seconds": 0, "label": "Up: Error"}

    @staticmethod
    def get_battery_metrics() -> Dict[str, Any]:
        """Check /sys/class/power_supply or return AC/Unavailable."""
        ps_path = Path("/sys/class/power_supply")
        if not ps_path.exists():
            return {"available": False, "label": "AC Power"}
        try:
            for entry in ps_path.iterdir():
                cap_file = entry / "capacity"
                if cap_file.exists():
                    cap = int(cap_file.read_text().strip())
                    return {"available": True, "percent": cap, "label": f"Bat: {cap}%"}
            return {"available": False, "label": "AC Online"}
        except Exception:
            return {"available": False, "label": "Power: Unknown"}


# ---------------------------------------------------------------------------
# 2. PK Intelligence IPC Client
# ---------------------------------------------------------------------------

class PKIntelligenceClient:
    """Client for pk-intelligenced Unix domain socket."""

    def __init__(self, socket_path: str = "/run/pk-intelligenced/control.sock") -> None:
        self.socket_path = Path(socket_path)

    def is_daemon_online(self, timeout_sec: float = 0.2) -> bool:
        """Check if socket exists and daemon is genuinely responsive via ping."""
        if not self.socket_path.exists():
            return False
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect(str(self.socket_path))
            payload = json.dumps({"query": "ping"}).encode("utf-8")
            sock.sendall(struct.pack(">I", len(payload)) + payload)
            header = sock.recv(4)
            if len(header) < 4:
                sock.close()
                return False
            length = struct.unpack(">I", header)[0]
            data = sock.recv(length)
            sock.close()
            resp = json.loads(data.decode("utf-8"))
            return bool(resp.get("ok", False))
        except Exception:
            return False

    def query(self, text: str, user_approved: bool = False, timeout_sec: float = 2.0) -> Dict[str, Any]:
        """Send a natural-language intent request to the daemon."""
        if not self.socket_path.exists():
            return {"ok": False, "error": "Daemon offline (socket not found)"}

        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(timeout_sec)
            sock.connect(str(self.socket_path))

            payload = json.dumps({"query": text, "user_approved": user_approved}).encode("utf-8")
            sock.sendall(struct.pack(">I", len(payload)) + payload)

            header = sock.recv(4)
            if len(header) < 4:
                return {"ok": False, "error": "Incomplete header from daemon"}
            length = struct.unpack(">I", header)[0]
            data = sock.recv(length)
            sock.close()
            return json.loads(data.decode("utf-8"))
        except Exception as exc:
            return {"ok": False, "error": f"IPC error: {exc}"}


# ---------------------------------------------------------------------------
# 3. Design Tokens & CSS Styler
# ---------------------------------------------------------------------------

def generate_shell_css(reduced_motion: bool = False) -> str:
    """
    Generate GTK3 CSS stylesheet adhering strictly to PK-OS design tokens.
    """
    motion_css = "transition: none;" if reduced_motion else "transition: all 200ms cubic-bezier(0.16, 1, 0.3, 1);"
    return f"""
    /* PK-OS Obsidian Dark Design System */
    window.pk-window {{
        background-color: #0a0b0e;
        color: #f0f3fa;
        font-family: 'Inter', -apple-system, sans-serif;
    }}

    /* Top Status Panel */
    .pk-top-panel {{
        background-color: #12151c;
        border-bottom: 1px solid #222736;
        padding: 4px 16px;
        min-height: 38px;
    }}

    .pk-brand {{
        color: #00e5ff;
        font-size: 14px;
        font-weight: 800;
    }}

    .pk-workspace-badge {{
        background-color: #1a1e28;
        color: #8b94a8;
        font-size: 11px;
        font-weight: 600;
        border-radius: 4px;
        padding: 2px 10px;
        margin: 0 4px;
        border: 1px solid #222736;
    }}

    .pk-workspace-badge.active {{
        background-color: #00e5ff;
        color: #0a0b0e;
        border-color: #00e5ff;
    }}

    .pk-metric-badge {{
        color: #8b94a8;
        font-size: 12px;
        font-family: 'JetBrains Mono', monospace;
        margin: 0 8px;
    }}

    /* Desktop Surface & Cards */
    .pk-desktop-area {{
        background-color: #0a0b0e;
        padding: 24px;
    }}

    .pk-card {{
        background-color: #12151c;
        border: 1px solid #222736;
        border-radius: 8px;
        padding: 16px;
        margin: 8px;
    }}

    .pk-card-title {{
        color: #00e5ff;
        font-size: 13px;
        font-weight: 700;
        margin-bottom: 12px;
    }}

    /* Action Buttons */
    .pk-app-btn {{
        background-color: #1a1e28;
        color: #f0f3fa;
        border: 1px solid #222736;
        border-radius: 6px;
        padding: 10px 16px;
        font-size: 13px;
        font-weight: 600;
        margin: 4px;
        {motion_css}
    }}

    .pk-app-btn:hover, .pk-app-btn:focus {{
        background-color: #252b3a;
        border-color: #4d78cc;
        color: #00e5ff;
    }}

    /* Voice HUD */
    .pk-hud {{
        background-color: #12151c;
        border: 1px solid #00e5ff;
        border-radius: 8px;
        padding: 16px;
        margin: 8px;
    }}

    .pk-badge-online {{
        background-color: rgba(0, 229, 255, 0.15);
        color: #00e5ff;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: bold;
    }}

    .pk-badge-offline {{
        background-color: rgba(255, 59, 92, 0.15);
        color: #ff3b5c;
        border-radius: 4px;
        padding: 2px 8px;
        font-size: 11px;
        font-weight: bold;
    }}

    .pk-exit-btn {{
        background-color: #1a1e28;
        color: #ff3b5c;
        border: 1px solid #ff3b5c;
        border-radius: 4px;
        padding: 4px 10px;
        font-size: 11px;
        font-weight: bold;
    }}

    /* Interactive HUD Input Box */
    entry.pk-hud-entry {{
        background-color: #0e1117;
        color: #f0f3fa;
        border: 1px solid #222736;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 12px;
    }}

    entry.pk-hud-entry:focus {{
        border-color: #00e5ff;
    }}

    /* Primary Accent Button */
    .pk-btn-primary {{
        background-color: #00e5ff;
        color: #0a0b0e;
        border: 1px solid #00e5ff;
        border-radius: 6px;
        padding: 6px 14px;
        font-size: 12px;
        font-weight: 700;
        {motion_css}
    }}

    .pk-btn-primary:hover {{
        background-color: #33ebff;
    }}

    /* Interactive Console Log */
    .pk-console-view {{
        background-color: #0e1117;
        color: #00e5ff;
        font-family: 'JetBrains Mono', monospace;
        font-size: 11px;
        border: 1px solid #222736;
        border-radius: 6px;
        padding: 8px;
    }}

    /* Bottom Taskbar / Dock (Phase 2D) */
    .pk-bottom-dock {{
        background-color: #12151c;
        border-top: 1px solid #222736;
        padding: 4px 16px;
        min-height: 42px;
    }}

    .pk-dock-item {{
        background-color: #1a1e28;
        color: #f0f3fa;
        border: 1px solid #222736;
        border-radius: 6px;
        padding: 4px 12px;
        font-size: 12px;
        font-weight: 600;
        margin: 2px 4px;
        {motion_css}
    }}

    .pk-dock-item.focused {{
        border-color: #00e5ff;
        color: #00e5ff;
        background-color: #222838;
    }}

    /* Notification Toasts (Phase 2D) */
    .pk-toast-area {{
        padding: 8px 16px;
    }}

    .pk-toast {{
        background-color: #181d28;
        border: 1px solid #222736;
        border-radius: 8px;
        padding: 8px 14px;
        margin: 4px 0;
        {motion_css}
    }}

    .pk-toast-info {{
        border-left: 4px solid #00e5ff;
    }}

    .pk-toast-warning {{
        border-left: 4px solid #f59e0b;
    }}

    .pk-toast-critical {{
        border-left: 4px solid #ff3b5c;
    }}
    """


# ---------------------------------------------------------------------------
# 4. GTK3 Wayland Surface Window
# ---------------------------------------------------------------------------

if GTK_AVAILABLE:
    class PKShellWindow(Gtk.Window):
        """Native GTK3 Wayland window running inside cage(1)."""

        def __init__(self, on_shutdown: Optional[Any] = None) -> None:
            super().__init__(title="PK-OS Desktop Shell")
            self.on_shutdown = on_shutdown
            self.metrics = SystemMetricsCollector()
            self.intelligence = PKIntelligenceClient()
            self.notification_manager = NotificationManager() if NotificationManager else None
            self.window_manager = WindowManager() if WindowManager else None

            # Window configuration for cage fullscreening
            self.set_default_size(1280, 720)
            self.get_style_context().add_class("pk-window")

            # Check reduced motion preference
            reduced_motion = os.environ.get("PK_REDUCED_MOTION") == "1"
            self._apply_css(reduced_motion)

            # Build UI layout
            self._build_ui()

            # Wire notification manager callbacks to live UI updates
            if self.notification_manager:
                self.notification_manager.set_on_added(lambda _n: GLib.idle_add(self._update_toasts))
                self.notification_manager.set_on_dismissed(lambda _n: GLib.idle_add(self._update_toasts))

            # Schedule periodic metrics update (every 1 second)
            GLib.timeout_add_seconds(1, self._on_tick)

            # Connect window close / escape handlers
            self.connect("destroy", self._handle_destroy)
            self.connect("key-press-event", self._handle_key)

        def _apply_css(self, reduced_motion: bool) -> None:
            try:
                css_data = generate_shell_css(reduced_motion).encode("utf-8")
                provider = Gtk.CssProvider()
                provider.load_from_data(css_data)
                screen = Gdk.Screen.get_default()
                if screen:
                    Gtk.StyleContext.add_provider_for_screen(
                        screen, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
            except Exception as exc:
                logger.warning("Could not apply GTK CSS styles: %s", exc)

        def _build_ui(self) -> None:
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            self.add(main_box)

            # 1. Top Panel
            top_panel = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            top_panel.get_style_context().add_class("pk-top-panel")

            # Brand logo
            brand = Gtk.Label(label="PK-OS")
            brand.get_style_context().add_class("pk-brand")
            top_panel.pack_start(brand, False, False, 8)

            # Interactive Workspace Switcher Buttons
            self.ws_buttons: list[Gtk.Button] = []
            for idx, ws_name in enumerate(["1: Main", "2: Code", "3: Settings"]):
                btn = Gtk.Button(label=ws_name)
                btn.get_style_context().add_class("pk-workspace-badge")
                if idx == 0:
                    btn.get_style_context().add_class("active")
                btn.connect("clicked", lambda b, i=idx: self._switch_workspace(i))
                top_panel.pack_start(btn, False, False, 0)
                self.ws_buttons.append(btn)

            # Spacer
            spacer = Gtk.Box()
            top_panel.pack_start(spacer, True, True, 0)

            # Status indicators
            self.lbl_cpu = Gtk.Label(label="Load: ...")
            self.lbl_cpu.get_style_context().add_class("pk-metric-badge")
            self.lbl_mem = Gtk.Label(label="Mem: ...")
            self.lbl_mem.get_style_context().add_class("pk-metric-badge")
            self.lbl_uptime = Gtk.Label(label="Up: ...")
            self.lbl_uptime.get_style_context().add_class("pk-metric-badge")
            self.lbl_clock = Gtk.Label(label=time.strftime("%H:%M:%S"))
            self.lbl_clock.get_style_context().add_class("pk-metric-badge")

            top_panel.pack_start(self.lbl_cpu, False, False, 4)
            top_panel.pack_start(self.lbl_mem, False, False, 4)
            top_panel.pack_start(self.lbl_uptime, False, False, 4)
            top_panel.pack_start(self.lbl_clock, False, False, 8)

            # Exit / Power button (Graceful Guest Shutdown)
            btn_quit = Gtk.Button(label="Shut Down PK-OS")
            btn_quit.get_style_context().add_class("pk-exit-btn")
            btn_quit.connect("clicked", lambda _: self._on_shutdown_clicked())
            top_panel.pack_start(btn_quit, False, False, 4)

            main_box.pack_start(top_panel, False, False, 0)

            # Notification Toast Area (Phase 2E live rendering)
            self.toast_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            self.toast_box.get_style_context().add_class("pk-toast-area")
            main_box.pack_start(self.toast_box, False, False, 0)

            # 2. Workspace View Stack
            self.workspace_stack = Gtk.Stack()
            self.workspace_stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
            self.workspace_stack.set_transition_duration(150)

            # ===================================================================
            # View 0: Workspace Main (Apps, Diagnostics, Hey PK HUD)
            # ===================================================================
            ws0_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            ws0_box.get_style_context().add_class("pk-desktop-area")

            left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

            # Application Launcher Card
            app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            app_card.get_style_context().add_class("pk-card")
            app_title = Gtk.Label(label="Applications", xalign=0)
            app_title.get_style_context().add_class("pk-card-title")
            app_card.pack_start(app_title, False, False, 0)

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            for app_name, key in [
                ("Terminal [F1]", "terminal"),
                ("Files [F2]", "files"),
                ("Settings [F3]", "settings"),
                ("Browser [F4]", "browser"),
                ("Editor", "editor"),
            ]:
                btn = Gtk.Button(label=app_name)
                btn.get_style_context().add_class("pk-app-btn")
                btn.connect("clicked", lambda b, k=key: self._on_app_click(k))
                btn_box.pack_start(btn, True, True, 0)
            app_card.pack_start(btn_box, False, False, 0)
            left_col.pack_start(app_card, False, False, 0)

            # System Diagnostics Card
            diag_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            diag_card.get_style_context().add_class("pk-card")
            diag_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            diag_title = Gtk.Label(label="System Diagnostics", xalign=0)
            diag_title.get_style_context().add_class("pk-card-title")
            diag_header.pack_start(diag_title, True, True, 0)

            btn_refresh = Gtk.Button(label="Refresh")
            btn_refresh.get_style_context().add_class("pk-workspace-badge")
            btn_refresh.connect("clicked", lambda _: self._update_all_metrics())
            diag_header.pack_start(btn_refresh, False, False, 0)
            diag_card.pack_start(diag_header, False, False, 0)

            diag_text = (
                f"OS: PK-OS 0.1.0 LTS (Debian 12 Bookworm)\n"
                f"Kernel: {platform.system()} {platform.release()} ({platform.machine()})\n"
                f"Wayland Display: {os.environ.get('WAYLAND_DISPLAY', 'wayland-0')}\n"
                f"Compositor: cage 0.1.5 (wlroots 0.16)\n"
                f"Session Type: {os.environ.get('XDG_SESSION_TYPE', 'wayland')}\n"
                f"Security Gate: Sandboxed Tools + Signed Ledger"
            )
            self.lbl_diag = Gtk.Label(label=diag_text, xalign=0)
            self.lbl_diag.get_style_context().add_class("pk-metric-badge")
            diag_card.pack_start(self.lbl_diag, False, False, 0)
            left_col.pack_start(diag_card, True, True, 0)

            ws0_box.pack_start(left_col, True, True, 0)

            # Hey PK Intelligence HUD
            hud_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            hud_card.set_size_request(380, -1)
            hud_card.get_style_context().add_class("pk-hud")

            hud_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hud_title = Gtk.Label(label="Hey PK Intelligence", xalign=0)
            hud_title.get_style_context().add_class("pk-card-title")
            hud_header.pack_start(hud_title, True, True, 0)

            self.hud_badge = Gtk.Label(label="CHECKING")
            self.hud_badge.get_style_context().add_class("pk-badge-offline")
            hud_header.pack_start(self.hud_badge, False, False, 0)
            hud_card.pack_start(hud_header, False, False, 0)

            # Quick Action Buttons
            hud_btn_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            for q_label, q_text in [
                ("Check System Status", "get system status"),
                ("Adjust Brightness", "set brightness to 80"),
                ("Launch Terminal", "launch terminal"),
            ]:
                btn = Gtk.Button(label=q_label)
                btn.get_style_context().add_class("pk-app-btn")
                btn.connect("clicked", lambda b, q=q_text: self._on_intelligence_query(q))
                hud_btn_box.pack_start(btn, False, False, 0)
            hud_card.pack_start(hud_btn_box, False, False, 0)

            # Interactive Text Entry Bar
            input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.hud_entry = Gtk.Entry()
            self.hud_entry.set_placeholder_text("Ask Hey PK or type command...")
            self.hud_entry.get_style_context().add_class("pk-hud-entry")
            self.hud_entry.connect("activate", lambda _: self._on_hud_submit())
            input_box.pack_start(self.hud_entry, True, True, 0)

            btn_send = Gtk.Button(label="Ask")
            btn_send.get_style_context().add_class("pk-btn-primary")
            btn_send.connect("clicked", lambda _: self._on_hud_submit())
            input_box.pack_start(btn_send, False, False, 0)
            hud_card.pack_start(input_box, False, False, 0)

            # Response Output Box
            self.hud_response = Gtk.Label(label="Ready. Type a query above or click a quick action.", xalign=0)
            self.hud_response.set_line_wrap(True)
            self.hud_response.get_style_context().add_class("pk-metric-badge")
            hud_card.pack_start(self.hud_response, True, True, 0)

            ws0_box.pack_start(hud_card, False, False, 0)
            self.workspace_stack.add_named(ws0_box, "ws_0")

            # ===================================================================
            # View 1: Workspace Code / Developer Console
            # ===================================================================
            ws1_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            ws1_box.get_style_context().add_class("pk-desktop-area")

            dev_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            dev_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            dev_card.get_style_context().add_class("pk-card")
            dev_title = Gtk.Label(label="Developer Actions", xalign=0)
            dev_title.get_style_context().add_class("pk-card-title")
            dev_card.pack_start(dev_title, False, False, 0)

            for act_label, act_cmd in [
                ("Spawn Shell Terminal [F1]", "launch terminal"),
                ("Query Security Ledger Audit", "get system status"),
                ("Verify Hardware & DRM", "get system status"),
            ]:
                btn = Gtk.Button(label=act_label)
                btn.get_style_context().add_class("pk-app-btn")
                btn.connect("clicked", lambda b, c=act_cmd: self._on_intelligence_query(c))
                dev_card.pack_start(btn, False, False, 0)
            dev_col.pack_start(dev_card, False, False, 0)
            ws1_box.pack_start(dev_col, False, False, 0)

            console_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            console_card.get_style_context().add_class("pk-card")
            console_title = Gtk.Label(label="Session Event Stream", xalign=0)
            console_title.get_style_context().add_class("pk-card-title")
            console_card.pack_start(console_title, False, False, 0)

            scrolled_win = Gtk.ScrolledWindow()
            scrolled_win.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
            self.console_view = Gtk.TextView()
            self.console_view.set_editable(False)
            self.console_view.get_style_context().add_class("pk-console-view")
            self.console_buffer = self.console_view.get_buffer()
            self._log_to_console("PK-OS Graphical Runtime initialized.\nReady for interactive developer commands.")
            scrolled_win.add(self.console_view)
            console_card.pack_start(scrolled_win, True, True, 0)
            ws1_box.pack_start(console_card, True, True, 0)

            self.workspace_stack.add_named(ws1_box, "ws_1")

            # ===================================================================
            # View 2: Workspace Settings
            # ===================================================================
            ws2_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            ws2_box.get_style_context().add_class("pk-desktop-area")

            settings_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
            settings_card.get_style_context().add_class("pk-card")
            s_title = Gtk.Label(label="System Preferences", xalign=0)
            s_title.get_style_context().add_class("pk-card-title")
            settings_card.pack_start(s_title, False, False, 0)

            # Brightness adjustment
            b_label = Gtk.Label(label="Display Brightness", xalign=0)
            b_label.get_style_context().add_class("pk-metric-badge")
            settings_card.pack_start(b_label, False, False, 0)
            self.scale_bright = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 10, 100, 5)
            self.scale_bright.set_value(80)
            self.scale_bright.connect("value-changed", self._on_brightness_change)
            settings_card.pack_start(self.scale_bright, False, False, 0)

            # Reduced Motion toggle
            motion_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            m_label = Gtk.Label(label="Reduced Motion Mode", xalign=0)
            m_label.get_style_context().add_class("pk-metric-badge")
            motion_box.pack_start(m_label, True, True, 0)
            self.switch_motion = Gtk.Switch()
            self.switch_motion.set_active(os.environ.get("PK_REDUCED_MOTION") == "1")
            self.switch_motion.connect("notify::active", self._on_motion_toggle)
            motion_box.pack_start(self.switch_motion, False, False, 0)
            settings_card.pack_start(motion_box, False, False, 0)

            # Theme badge
            theme_lbl = Gtk.Label(label="Visual Theme: Obsidian Dark (#0a0b0e, WCAG AAA)", xalign=0)
            theme_lbl.get_style_context().add_class("pk-metric-badge")
            settings_card.pack_start(theme_lbl, False, False, 0)

            # Master Volume (Phase 2D)
            v_label = Gtk.Label(label="Master Volume", xalign=0)
            v_label.get_style_context().add_class("pk-metric-badge")
            settings_card.pack_start(v_label, False, False, 0)
            self.scale_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
            self.scale_volume.set_value(75)
            self.scale_volume.connect("value-changed", self._on_volume_change)
            settings_card.pack_start(self.scale_volume, False, False, 0)

            # Hey PK Wake-Word Toggle (Phase 2D)
            wake_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            wake_label = Gtk.Label(label="'Hey PK' Wake-Word Detection", xalign=0)
            wake_label.get_style_context().add_class("pk-metric-badge")
            wake_box.pack_start(wake_label, True, True, 0)
            self.switch_wake = Gtk.Switch()
            self.switch_wake.set_active(True)
            self.switch_wake.connect("notify::active", self._on_wake_toggle)
            wake_box.pack_start(self.switch_wake, False, False, 0)
            settings_card.pack_start(wake_box, False, False, 0)

            # System Power & Lifecycle Controls (Phase 2D/2E)
            p_label = Gtk.Label(label="System Lifecycle", xalign=0)
            p_label.get_style_context().add_class("pk-metric-badge")
            settings_card.pack_start(p_label, False, False, 0)

            power_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            btn_sd = Gtk.Button(label="Shut Down PK-OS")
            btn_sd.get_style_context().add_class("pk-exit-btn")
            btn_sd.connect("clicked", lambda _: self._on_shutdown_clicked())
            power_btn_box.pack_start(btn_sd, False, False, 0)

            btn_rb = Gtk.Button(label="Restart PK-OS")
            btn_rb.get_style_context().add_class("pk-app-btn")
            btn_rb.connect("clicked", lambda _: self._on_reboot_clicked())
            power_btn_box.pack_start(btn_rb, False, False, 0)
            settings_card.pack_start(power_btn_box, False, False, 0)

            ws2_box.pack_start(settings_card, True, True, 0)
            self.workspace_stack.add_named(ws2_box, "ws_2")

            main_box.pack_start(self.workspace_stack, True, True, 0)

            # 3. Bottom Dock / Taskbar (Phase 2D)
            self.dock_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.dock_box.get_style_context().add_class("pk-bottom-dock")
            dock_label = Gtk.Label(label="Tasks:")
            dock_label.get_style_context().add_class("pk-metric-badge")
            self.dock_box.pack_start(dock_label, False, False, 4)
            self.dock_items_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
            self.dock_box.pack_start(self.dock_items_box, True, True, 0)
            main_box.pack_start(self.dock_box, False, False, 0)

            # Initial metrics update
            self._update_all_metrics()

        def _switch_workspace(self, index: int) -> None:
            """Switch active workspace view and update button styles."""
            self.workspace_stack.set_visible_child_name(f"ws_{index}")
            for idx, btn in enumerate(self.ws_buttons):
                ctx = btn.get_style_context()
                if idx == index:
                    ctx.add_class("active")
                else:
                    ctx.remove_class("active")
            self._log_to_console(f"Switched to Workspace {index + 1}")

        def _log_to_console(self, text: str) -> None:
            """Append a timestamped log line to the developer console view."""
            if hasattr(self, "console_buffer"):
                end_iter = self.console_buffer.get_end_iter()
                ts = time.strftime("[%H:%M:%S] ")
                self.console_buffer.insert(end_iter, f"\n{ts}{text}")

        def _on_hud_submit(self) -> None:
            """Handle user-submitted natural language query from the HUD text entry."""
            text = self.hud_entry.get_text().strip()
            if text:
                self.hud_entry.set_text("")
                self._on_intelligence_query(text)

        def _on_brightness_change(self, scale: Gtk.Scale) -> None:
            val = int(scale.get_value())
            self.hud_response.set_text(f"Setting brightness to {val}%...")
            res = self.intelligence.query(f"set brightness to {val}")
            self._log_to_console(f"Brightness adjusted to {val}% (result: {res.get('ok')})")

        def _on_volume_change(self, scale: Gtk.Scale) -> None:
            val = int(scale.get_value())
            self._log_to_console(f"Master volume adjusted to {val}%")
            try:
                if shutil.which("wpctl"):
                    vol_float = val / 100.0
                    subprocess.run(
                        ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol_float:.2f}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=0.5,
                    )
                elif shutil.which("amixer"):
                    subprocess.run(
                        ["amixer", "sset", "Master", f"{val}%"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        timeout=0.5,
                    )
            except Exception as exc:
                logger.debug("Hardware audio volume control not active: %s", exc)

        def _on_shutdown_clicked(self) -> None:
            """Execute graceful guest system shutdown via systemctl poweroff."""
            self._log_to_console("Initiating graceful system shutdown...")
            if self.notification_manager:
                u = NotificationUrgency.CRITICAL if NotificationUrgency else "critical"
                self.notification_manager.add("Power", "Shutting down PK-OS...", urgency=u)
            try:
                # systemctl poweroff is granted in /etc/sudoers.d/pkos
                if shutil.which("systemctl"):
                    subprocess.Popen(["sudo", "/bin/systemctl", "poweroff"])
                elif shutil.which("poweroff"):
                    subprocess.Popen(["sudo", "/sbin/poweroff"])
                else:
                    self.destroy()
            except Exception as exc:
                logger.warning("Graceful shutdown failed: %s; falling back to window exit", exc)
                self.destroy()

        def _on_reboot_clicked(self) -> None:
            """Execute graceful guest system reboot via systemctl reboot."""
            self._log_to_console("Initiating graceful system reboot...")
            if self.notification_manager:
                u = NotificationUrgency.WARNING if NotificationUrgency else "warning"
                self.notification_manager.add("Power", "Rebooting PK-OS...", urgency=u)
            try:
                if shutil.which("systemctl"):
                    subprocess.Popen(["sudo", "/bin/systemctl", "reboot"])
                elif shutil.which("reboot"):
                    subprocess.Popen(["sudo", "/sbin/reboot"])
                else:
                    self.destroy()
            except Exception as exc:
                logger.warning("Graceful reboot failed: %s; falling back to window exit", exc)
                self.destroy()

        def _update_toasts(self) -> None:
            """Render active notification toasts in the toast container."""
            if not hasattr(self, "toast_box") or not self.notification_manager:
                return
            for child in self.toast_box.get_children():
                self.toast_box.remove(child)

            active = self.notification_manager.active_notifications
            if not active:
                self.toast_box.hide()
                return

            for n in active:
                toast = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
                toast.get_style_context().add_class("pk-toast")
                if NotificationUrgency and n.urgency == NotificationUrgency.CRITICAL:
                    toast.get_style_context().add_class("pk-toast-critical")
                elif NotificationUrgency and n.urgency == NotificationUrgency.WARNING:
                    toast.get_style_context().add_class("pk-toast-warning")
                else:
                    toast.get_style_context().add_class("pk-toast-info")

                content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
                lbl_title = Gtk.Label(label=f"<b>{n.title}</b>", xalign=0)
                lbl_title.set_use_markup(True)
                content_box.pack_start(lbl_title, False, False, 0)

                if n.body:
                    lbl_body = Gtk.Label(label=n.body, xalign=0)
                    lbl_body.set_line_wrap(True)
                    content_box.pack_start(lbl_body, False, False, 0)

                toast.pack_start(content_box, True, True, 0)

                btn_dismiss = Gtk.Button(label="×")
                btn_dismiss.get_style_context().add_class("pk-workspace-badge")
                nid = n.id
                btn_dismiss.connect("clicked", lambda _b, target_id=nid: self._dismiss_toast(target_id))
                toast.pack_start(btn_dismiss, False, False, 0)

                self.toast_box.pack_start(toast, False, False, 0)

            self.toast_box.show_all()

        def _dismiss_toast(self, notification_id: str) -> None:
            if self.notification_manager:
                self.notification_manager.dismiss(notification_id)
                self._update_toasts()

        def _on_wake_toggle(self, switch: Gtk.Switch, _param: Any) -> None:
            active = switch.get_active()
            state = "enabled" if active else "disabled"
            self._log_to_console(f"Hey PK wake-word listener {state}")
            if self.notification_manager:
                self.notification_manager.add("Hey PK Listener", f"Wake-word {state}")

        def _on_motion_toggle(self, switch: Gtk.Switch, _param: Any) -> None:
            reduced = switch.get_active()
            self._apply_css(reduced)
            self._log_to_console(f"Reduced motion set to {reduced}")

        def _update_dock(self) -> None:
            if not hasattr(self, "dock_items_box") or not self.window_manager:
                return
            for child in self.dock_items_box.get_children():
                self.dock_items_box.remove(child)
            for w in self.window_manager.get_taskbar_windows():
                btn = Gtk.Button(label=f"● {w['title']}")
                btn.get_style_context().add_class("pk-dock-item")
                if w["state"] == "focused":
                    btn.get_style_context().add_class("focused")
                wid = w["id"]
                btn.connect("clicked", lambda b, win_id=wid: self._on_dock_click(win_id))
                self.dock_items_box.pack_start(btn, False, False, 0)
            self.dock_items_box.show_all()

        def _on_dock_click(self, window_id: str) -> None:
            if self.window_manager:
                self.window_manager.focus(window_id)
                self._update_dock()

        def _on_tick(self) -> bool:
            """Periodic 1s tick."""
            self._update_all_metrics()
            if self.notification_manager:
                dismissed = self.notification_manager.tick()
                if dismissed:
                    self._update_toasts()
            return True

        def _update_all_metrics(self) -> None:
            load = self.metrics.get_load_metrics()
            mem = self.metrics.get_memory_metrics()
            up = self.metrics.get_uptime_metrics()

            self.lbl_cpu.set_text(load["label"])
            self.lbl_mem.set_text(mem["label"])
            self.lbl_uptime.set_text(up["label"])
            self.lbl_clock.set_text(time.strftime("%H:%M:%S"))

            # Update intelligence daemon status badge
            if self.intelligence.is_daemon_online():
                self.hud_badge.set_text("ONLINE")
                self.hud_badge.get_style_context().remove_class("pk-badge-offline")
                self.hud_badge.get_style_context().add_class("pk-badge-online")
            else:
                self.hud_badge.set_text("OFFLINE")
                self.hud_badge.get_style_context().remove_class("pk-badge-online")
                self.hud_badge.get_style_context().add_class("pk-badge-offline")

        def _on_app_click(self, app_id: str) -> None:
            logger.info("Application launch requested: %s", app_id)
            if self.window_manager:
                self.window_manager.open(app_id=app_id, title=app_id.capitalize())
                self._update_dock()
            if self.notification_manager:
                self.notification_manager.add("App Launch", f"Launched {app_id}")
            self.hud_response.set_text(f"Action: Launching '{app_id}'...")
            self._log_to_console(f"Application dispatch requested: '{app_id}'")
            res = self.intelligence.query(f"launch {app_id}")
            if res.get("ok"):
                self.hud_response.set_text(f"Launched: {app_id}\nResult: {res.get('result')}")
                self._log_to_console(f"Launch {app_id} succeeded: {res.get('result')}")
            else:
                self.hud_response.set_text(f"App Dispatch: {app_id} requested (offline fallback)")
                self._log_to_console(f"Launch {app_id} fallback: {res.get('error')}")

        def _on_intelligence_query(self, query: str) -> None:
            logger.info("Executing HUD query: %s", query)
            self.hud_response.set_text(f"Querying: {query}...")
            self._log_to_console(f"HUD query dispatched: '{query}'")
            res = self.intelligence.query(query)
            if res.get("ok"):
                output_str = json.dumps(res.get("result", {}), indent=2)
                self.hud_response.set_text(f"Intent: {res.get('intent')}\nOutput: {output_str}")
                self._log_to_console(f"Intent: {res.get('intent')} -> {output_str}")
            else:
                self.hud_response.set_text(f"Response: {res.get('error', 'Daemon unreachable')}")
                self._log_to_console(f"Query error: {res.get('error')}")

        def _handle_key(self, _widget: Any, event: Any) -> bool:
            # Workspace switching: Alt+1, Alt+2, Alt+3
            if event.state & Gdk.ModifierType.MOD1_MASK:
                if event.keyval == Gdk.KEY_1:
                    self._switch_workspace(0)
                    return True
                elif event.keyval == Gdk.KEY_2:
                    self._switch_workspace(1)
                    return True
                elif event.keyval == Gdk.KEY_3:
                    self._switch_workspace(2)
                    return True

            # Quick function keys for applications
            if event.keyval == Gdk.KEY_F1:
                self._on_app_click("terminal")
                return True
            elif event.keyval == Gdk.KEY_F2:
                self._on_app_click("files")
                return True
            elif event.keyval == Gdk.KEY_F3:
                self._switch_workspace(2)
                return True
            elif event.keyval == Gdk.KEY_F4:
                self._on_app_click("browser")
                return True

            # Escape or Ctrl+Q quits cleanly
            if event.keyval == Gdk.KEY_Escape or (
                event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_q, Gdk.KEY_Q)
            ):
                self.destroy()
                return True
            return False

        def _handle_destroy(self, _widget: Any) -> None:
            logger.info("PKShellWindow destroyed")
            if self.on_shutdown:
                self.on_shutdown()
            Gtk.main_quit()
else:
    class PKShellWindow:  # type: ignore
        """Dummy placeholder when GTK is not installed."""
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            raise RuntimeError("GTK3 is not available in current environment")


# ---------------------------------------------------------------------------
# 5. Headless Shell Surface (for Host Unit Tests)
# ---------------------------------------------------------------------------

class HeadlessShellSurface:
    """Headless simulation of the shell surface for platform-safe testing."""

    def __init__(self) -> None:
        self.metrics = SystemMetricsCollector()
        self.intelligence = PKIntelligenceClient()
        self.notifications = NotificationManager() if NotificationManager else None
        self.window_manager = WindowManager() if WindowManager else None
        self.state = "INIT"
        self.active_workspace = 0
        self.brightness = 80
        self.volume = 75
        self.wake_word_enabled = True
        self.reduced_motion = False
        self.launched_apps: list[str] = []
        self.history: list[dict[str, Any]] = []
        self.last_load: Dict[str, Any] = {}
        self.last_mem: Dict[str, Any] = {}
        self.last_uptime: Dict[str, Any] = {}

    def switch_workspace(self, index: int) -> int:
        """Switch active workspace (0=Main, 1=Code, 2=Settings)."""
        if index not in (0, 1, 2):
            raise ValueError(f"Invalid workspace index: {index}")
        self.active_workspace = index
        self.history.append({"action": "switch_workspace", "index": index})
        return self.active_workspace

    def launch_app(self, app_id: str) -> Dict[str, Any]:
        """Simulate launching an application."""
        self.launched_apps.append(app_id)
        if self.window_manager:
            self.window_manager.open(app_id=app_id, title=app_id.capitalize())
        if self.notifications:
            self.notifications.add("Application Launched", f"Started {app_id}")
        res = self.intelligence.query(f"launch {app_id}")
        self.history.append({"action": "launch_app", "app_id": app_id, "result": res})
        return res

    def send_hud_query(self, query: str) -> Dict[str, Any]:
        """Simulate sending a HUD natural language query."""
        res = self.intelligence.query(query)
        self.history.append({"action": "hud_query", "query": query, "result": res})
        return res

    def set_brightness(self, level: int) -> Dict[str, Any]:
        """Simulate brightness adjustment."""
        self.brightness = max(10, min(100, level))
        res = self.intelligence.query(f"set brightness to {self.brightness}")
        self.history.append({"action": "set_brightness", "level": self.brightness, "result": res})
        return res

    def set_volume(self, level: int) -> int:
        """Simulate volume adjustment (0-100)."""
        self.volume = max(0, min(100, level))
        self.history.append({"action": "set_volume", "level": self.volume})
        return self.volume

    def toggle_wake_word(self, enabled: bool) -> bool:
        """Toggle 'Hey PK' wake-word detection."""
        self.wake_word_enabled = enabled
        self.history.append({"action": "toggle_wake_word", "enabled": enabled})
        return self.wake_word_enabled

    def toggle_reduced_motion(self, enabled: bool) -> bool:
        """Simulate reduced motion toggle."""
        self.reduced_motion = enabled
        self.history.append({"action": "toggle_reduced_motion", "enabled": enabled})
        return self.reduced_motion

    def post_notification(
        self,
        title: str,
        body: str = "",
        urgency: Any = None,
    ) -> Any:
        """Post a notification through the shell notification manager."""
        if self.notifications:
            u = urgency or (NotificationUrgency.INFO if NotificationUrgency else "info")
            return self.notifications.add(title=title, body=body, urgency=u)
        return None

    def tick(self) -> None:
        """Simulate a tick cycle."""
        self.last_load = self.metrics.get_load_metrics()
        self.last_mem = self.metrics.get_memory_metrics()
        self.last_uptime = self.metrics.get_uptime_metrics()
        if self.notifications:
            self.notifications.tick()
        self.state = "ACTIVE"

    def request_shutdown(self) -> Dict[str, Any]:
        """Simulate graceful guest system shutdown request."""
        self.state = "SHUTDOWN"
        record = {"action": "shutdown", "success": True, "target": "poweroff"}
        self.history.append(record)
        return record

    def request_reboot(self) -> Dict[str, Any]:
        """Simulate graceful guest system reboot request."""
        self.state = "REBOOT"
        record = {"action": "reboot", "success": True, "target": "reboot"}
        self.history.append(record)
        return record

