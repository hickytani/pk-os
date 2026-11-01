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


def build_preview_url(host: str = "127.0.0.1", port: int = 6080, autoconnect: bool = True, resize: str = "scale") -> str:
    """Constructs the canonical browser preview URL for noVNC desktop session."""
    query = []
    if autoconnect:
        query.append("autoconnect=true")
    if resize:
        query.append(f"resize={resize}")
    qs = f"?{'&'.join(query)}" if query else ""
    return f"http://{host}:{port}/vnc.html{qs}"


def check_endpoint_reachability(host: str, port: int, timeout_sec: float = 0.5) -> bool:
    """Verifies that a TCP endpoint is active and accepting connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout_sec):
            return True
    except (OSError, socket.timeout):
        return False


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


def query_with_user_approval(client: PKIntelligenceClient, query: str, prompt: Any) -> Dict[str, Any]:
    """Retry a gated request only after an explicit, request-specific approval."""
    response = client.query(query)
    if response.get("error") != "approval_required":
        return response
    if not prompt(query, str(response.get("detail", ""))):
        return {"ok": False, "error": "approval_cancelled", "detail": "No change was made."}
    return client.query(query, user_approved=True)


def detect_audio_backend(which: Any = shutil.which, run: Any = subprocess.run) -> tuple[Optional[str], str]:
    """Report audio control only when a live default playback device responds."""
    wpctl = which("wpctl")
    if wpctl:
        try:
            result = run(
                [wpctl, "inspect", "@DEFAULT_AUDIO_SINK@"], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, check=False, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return wpctl, f"Audio sink detected via {Path(wpctl).name}; write access unverified."
        except (OSError, subprocess.TimeoutExpired):
            pass
    amixer = which("amixer")
    if amixer:
        try:
            result = run(
                [amixer, "get", "Master"], stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, check=False, timeout=2,
            )
            if result.returncode == 0 and result.stdout.strip():
                return amixer, f"Audio device detected via {Path(amixer).name}; write access unverified."
        except (OSError, subprocess.TimeoutExpired):
            pass
    return None, "Unavailable: no verified default audio playback control is connected."


# ---------------------------------------------------------------------------
# 3. Design Tokens & CSS Styler
# ---------------------------------------------------------------------------

def generate_shell_css(reduced_motion: bool = False) -> str:
    """
    Generate a GTK3 stylesheet from the shared PK-OS design tokens.
    """
    token_path = Path(__file__).resolve().parents[1] / "tokens" / "tokens.json"
    with token_path.open("r", encoding="utf-8") as token_file:
        tokens = json.load(token_file)

    colors = tokens["color"]
    spacing = tokens["spacing"]
    typography = tokens["typography"]
    radii = tokens["radii"]
    controls = tokens["control"]
    motion_duration = 0 if reduced_motion else tokens["motion"]["duration_fast_ms"]
    motion_css = f"transition: all {motion_duration}ms ease-out;"
    font_sans = typography["font_sans"]
    font_mono = typography["font_mono"]

    return f"""
    window.pk-window {{
        background-color: {colors["bg_base"]};
        color: {colors["text_primary"]};
        font-family: {font_sans};
        font-size: {typography["size_base"]}px;
    }}

    .pk-top-panel {{
        background-color: {colors["bg_surface"]};
        border-bottom: 1px solid {colors["border_subtle"]};
        padding: {spacing["space_2"]}px {spacing["space_6"]}px;
        min-height: {controls["height_standard"]}px;
    }}

    .pk-brand {{
        color: {colors["accent_cyan"]};
        font-size: {typography["size_base"]}px;
        font-weight: 700;
        letter-spacing: 0.08em;
    }}

    .pk-workspace-badge {{
        background-color: transparent;
        color: {colors["text_secondary"]};
        font-size: {typography["size_sm"]}px;
        font-weight: 600;
        border-radius: {radii["sm"]}px;
        padding: 0 {spacing["space_3"]}px;
        min-height: {controls["height_compact"]}px;
        border: 1px solid transparent;
        box-shadow: none;
        {motion_css}
    }}

    button.pk-workspace-badge, button.pk-app-btn, button.pk-btn-primary, button.pk-exit-btn {{
        background-image: none;
        text-shadow: none;
    }}

    button.pk-workspace-badge:hover, button.pk-workspace-badge:focus,
    button.pk-app-btn:hover, button.pk-app-btn:focus,
    button.pk-btn-primary:hover, button.pk-btn-primary:focus,
    button.pk-exit-btn:hover, button.pk-exit-btn:focus {{
        background-image: none;
    }}

    button.pk-workspace-badge label, button.pk-app-btn label,
    button.pk-btn-primary label, button.pk-exit-btn label {{
        color: inherit;
    }}

    .pk-workspace-badge:hover {{
        background-color: {colors["bg_surface_hover"]};
        color: {colors["text_primary"]};
    }}

    .pk-workspace-badge:focus {{
        background-color: {colors["bg_surface_hover"]};
        color: {colors["text_primary"]};
        border-color: {colors["border_focused"]};
    }}

    .pk-workspace-badge.active {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["accent_cyan"]};
        border-color: {colors["border_subtle"]};
    }}

    .pk-metric-badge {{
        color: {colors["text_secondary"]};
        font-size: {typography["size_sm"]}px;
        font-family: {font_mono};
    }}

    .pk-desktop-area {{
        background-color: {colors["bg_base"]};
        padding: {spacing["space_6"]}px;
    }}

    .pk-card {{
        background-color: {colors["bg_surface"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["md"]}px;
        padding: {spacing["space_6"]}px;
    }}

    .pk-card-title {{
        color: {colors["text_primary"]};
        font-size: {typography["size_lg"]}px;
        font-weight: 700;
    }}

    .pk-eyebrow {{
        color: {colors["accent_cyan"]};
        font-size: {typography["size_xs"]}px;
        font-weight: 700;
        letter-spacing: 0.1em;
    }}

    .pk-display-title {{
        color: {colors["text_primary"]};
        font-size: {typography["size_display"]}px;
        font-weight: 600;
    }}

    .pk-supporting {{
        color: {colors["text_secondary"]};
        font-size: {typography["size_base"]}px;
    }}

    .pk-detail {{
        color: {colors["text_tertiary"]};
        font-size: {typography["size_sm"]}px;
    }}

    .pk-app-btn {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["text_primary"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px {spacing["space_4"]}px;
        min-height: {controls["height_standard"]}px;
        font-size: {typography["size_sm"]}px;
        font-weight: 600;
        box-shadow: none;
        {motion_css}
    }}

    .pk-app-btn:hover, .pk-app-btn:focus {{
        background-color: {colors["bg_surface_hover"]};
        border-color: {colors["border_focused"]};
        color: {colors["accent_cyan"]};
        outline-color: {colors["border_focused"]};
    }}

    .pk-app-btn:disabled {{
        color: {colors["text_tertiary"]};
        background-color: {colors["bg_surface"]};
        border-color: {colors["border_subtle"]};
    }}

    .pk-hud {{
        background-color: {colors["bg_surface"]};
        border: 1px solid {colors["border_subtle"]};
        border-top: 2px solid {colors["accent_cyan"]};
        border-radius: {radii["md"]}px;
        padding: {spacing["space_6"]}px;
    }}

    .pk-badge-online {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["accent_cyan"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_1"]}px {spacing["space_2"]}px;
        font-size: {typography["size_xs"]}px;
        font-weight: 700;
    }}

    .pk-badge-offline {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["accent_amber"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_1"]}px {spacing["space_2"]}px;
        font-size: {typography["size_xs"]}px;
        font-weight: 700;
    }}

    .pk-exit-btn {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["accent_crimson"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px {spacing["space_3"]}px;
        min-height: {controls["height_compact"]}px;
        font-size: {typography["size_xs"]}px;
        font-weight: 700;
        box-shadow: none;
    }}

    entry.pk-hud-entry {{
        background-color: {colors["bg_base"]};
        color: {colors["text_primary"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px {spacing["space_3"]}px;
        min-height: {controls["height_compact"]}px;
        font-size: {typography["size_sm"]}px;
    }}

    entry.pk-hud-entry:focus {{
        border-color: {colors["border_focused"]};
        box-shadow: 0 0 0 1px {colors["border_focused"]};
    }}

    .pk-btn-primary {{
        background-color: {colors["accent_cyan"]};
        color: {colors["bg_base"]};
        border: 1px solid {colors["accent_cyan"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px {spacing["space_4"]}px;
        min-height: {controls["height_compact"]}px;
        font-size: {typography["size_sm"]}px;
        font-weight: 700;
        box-shadow: none;
        {motion_css}
    }}

    .pk-btn-primary:hover {{
        background-color: {colors["border_focused"]};
    }}

    .pk-console-view {{
        background-color: {colors["bg_base"]};
        color: {colors["accent_cyan"]};
        font-family: {font_mono};
        font-size: {typography["size_xs"]}px;
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px;
    }}

    textview.pk-console-view,
    textview.pk-console-view text,
    textview.pk-console-view.view {{
        background-color: {colors["bg_base"]};
        background-image: none;
        color: {colors["accent_cyan"]};
    }}

    .pk-bottom-dock {{
        background-color: {colors["bg_surface"]};
        border-top: 1px solid {colors["border_subtle"]};
        padding: {spacing["space_2"]}px {spacing["space_6"]}px;
        min-height: {controls["height_standard"]}px;
    }}

    .pk-dock-item {{
        background-color: {colors["bg_surface_raised"]};
        color: {colors["text_primary"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_1"]}px {spacing["space_3"]}px;
        min-height: {controls["height_compact"]}px;
        font-size: {typography["size_sm"]}px;
        font-weight: 600;
        box-shadow: none;
        {motion_css}
    }}

    .pk-dock-item.focused {{
        border-color: {colors["accent_cyan"]};
        color: {colors["accent_cyan"]};
    }}

    .pk-toast-area {{
        padding: {spacing["space_2"]}px {spacing["space_6"]}px;
    }}

    .pk-toast {{
        background-color: {colors["bg_surface_raised"]};
        border: 1px solid {colors["border_subtle"]};
        border-radius: {radii["sm"]}px;
        padding: {spacing["space_2"]}px {spacing["space_3"]}px;
        {motion_css}
    }}

    .pk-toast-info {{
        border-left: 3px solid {colors["accent_cyan"]};
    }}

    .pk-toast-warning {{
        border-left: 3px solid {colors["accent_amber"]};
    }}

    .pk-toast-critical {{
        border-left: 3px solid {colors["accent_crimson"]};
    }}

    .pk-setting-row {{
        padding: {spacing["space_3"]}px 0;
        border-bottom: 1px solid {colors["border_subtle"]};
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
            gtk_settings = Gtk.Settings.get_default()
            if gtk_settings:
                gtk_settings.set_property("gtk-application-prefer-dark-theme", True)
            self.on_shutdown = on_shutdown
            self.metrics = SystemMetricsCollector()
            self.intelligence = PKIntelligenceClient()
            self.notification_manager = NotificationManager() if NotificationManager else None
            self.window_manager = WindowManager() if WindowManager else None

            # Window configuration for cage fullscreening
            self.set_default_size(1280, 720)
            self.get_style_context().add_class("pk-window")

            # Check reduced motion preference
            self.reduced_motion = os.environ.get("PK_REDUCED_MOTION") == "1"
            self._apply_css(self.reduced_motion)

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
            for idx, ws_name in enumerate(["Main", "Code", "Settings"]):
                btn = Gtk.Button(label=ws_name)
                btn.get_style_context().add_class("pk-workspace-badge")
                btn.set_tooltip_text(f"Switch to {ws_name} workspace (Alt+{idx + 1})")
                if idx == 0:
                    btn.get_style_context().add_class("active")
                btn.connect("clicked", lambda b, i=idx: self._switch_workspace(i))
                top_panel.pack_start(btn, False, False, 0)
                self.ws_buttons.append(btn)

            # Spacer
            spacer = Gtk.Box()
            top_panel.pack_start(spacer, True, True, 0)

            # Status indicators
            self.lbl_cpu = Gtk.Label(label="Load: …")
            self.lbl_cpu.get_style_context().add_class("pk-metric-badge")
            self.lbl_mem = Gtk.Label(label="Mem: …")
            self.lbl_mem.get_style_context().add_class("pk-metric-badge")
            self.lbl_uptime = Gtk.Label(label="Up: …")
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
            self.workspace_stack.set_transition_type(
                Gtk.StackTransitionType.NONE if self.reduced_motion else Gtk.StackTransitionType.CROSSFADE
            )
            self.workspace_stack.set_transition_duration(150 if not self.reduced_motion else 0)

            # ===================================================================
            # View 0: Workspace Main (Apps, Diagnostics, Hey PK HUD)
            # ===================================================================
            ws0_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
            ws0_box.get_style_context().add_class("pk-desktop-area")

            main_intro = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            eyebrow = Gtk.Label(label="PK / DESKTOP", xalign=0)
            eyebrow.get_style_context().add_class("pk-eyebrow")
            main_intro.pack_start(eyebrow, False, False, 0)
            main_title = Gtk.Label(label="A focused place to begin.", xalign=0)
            main_title.get_style_context().add_class("pk-display-title")
            main_intro.pack_start(main_title, False, False, 0)
            main_subtitle = Gtk.Label(label="A live view of this PK-OS session.", xalign=0)
            main_subtitle.get_style_context().add_class("pk-supporting")
            main_intro.pack_start(main_subtitle, False, False, 0)
            ws0_box.pack_start(main_intro, False, False, 0)

            workspace_content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=20)
            workspace_content.set_margin_top(24)

            left_col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)

            # Application Launcher Card
            app_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            app_card.get_style_context().add_class("pk-card")
            app_title = Gtk.Label(label="Applications", xalign=0)
            app_title.get_style_context().add_class("pk-card-title")
            app_card.pack_start(app_title, False, False, 0)

            btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            for app_name, key in [
                ("Terminal", "terminal"),
                ("Files", "files"),
                ("Browser", "browser"),
                ("Editor", "editor"),
            ]:
                btn = Gtk.Button(label=app_name)
                btn.get_style_context().add_class("pk-app-btn")
                btn.set_sensitive(False)
                btn.set_tooltip_text(
                    f"{app_name} is not available in the current single-window Cage preview."
                )
                btn.connect("clicked", lambda b, k=key: self._on_app_click(k))
                btn_box.pack_start(btn, True, True, 0)
            app_card.pack_start(btn_box, False, False, 0)
            app_note = Gtk.Label(
                label="Application windows are not connected in this preview.",
                xalign=0,
            )
            app_note.get_style_context().add_class("pk-detail")
            app_card.pack_start(app_note, False, False, 0)
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
                f"Kernel: {platform.release()} · {platform.machine()}\n"
                f"Session: {os.environ.get('XDG_SESSION_TYPE', 'Wayland')}\n"
                f"Display: {os.environ.get('WAYLAND_DISPLAY', 'Unavailable')}\n"
                "Metrics: kernel load average, memory and uptime"
            )
            self.lbl_diag = Gtk.Label(label=diag_text, xalign=0)
            self.lbl_diag.get_style_context().add_class("pk-metric-badge")
            diag_card.pack_start(self.lbl_diag, False, False, 0)
            left_col.pack_start(diag_card, True, True, 0)

            workspace_content.pack_start(left_col, True, True, 0)

            # Hey PK Intelligence HUD
            hud_card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
            hud_card.set_size_request(380, -1)
            hud_card.get_style_context().add_class("pk-hud")

            hud_header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            hud_title = Gtk.Label(label="Hey PK", xalign=0)
            hud_title.get_style_context().add_class("pk-card-title")
            hud_header.pack_start(hud_title, True, True, 0)

            self.hud_badge = Gtk.Label(label="CHECKING")
            self.hud_badge.get_style_context().add_class("pk-badge-offline")
            hud_header.pack_start(self.hud_badge, False, False, 0)
            hud_card.pack_start(hud_header, False, False, 0)

            assistant_detail = Gtk.Label(
                label="Local deterministic assistant · no language model active",
                xalign=0,
            )
            assistant_detail.get_style_context().add_class("pk-detail")
            assistant_detail.set_line_wrap(True)
            hud_card.pack_start(assistant_detail, False, False, 0)

            # Quick Action Buttons
            hud_btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            for q_label, q_text in [
                ("Check System Status", "get system status"),
                ("What can you do?", "what can you do"),
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

            workspace_content.pack_start(hud_card, False, False, 0)
            ws0_box.pack_start(workspace_content, True, True, 0)
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
                ("Check system status", "get system status"),
                ("Show assistant capabilities", "what can you do"),
                ("List files in /home/pkos", "list files in /home/pkos"),
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

            brightness_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            b_label = Gtk.Label(label="Display brightness", xalign=0)
            b_label.get_style_context().add_class("pk-supporting")
            brightness_row.pack_start(b_label, False, False, 0)
            brightness_note = Gtk.Label(
                label="Unavailable: no verified display-brightness interface is connected.",
                xalign=0,
            )
            brightness_note.get_style_context().add_class("pk-detail")
            brightness_note.set_line_wrap(True)
            brightness_row.pack_start(brightness_note, False, False, 0)
            settings_card.pack_start(brightness_row, False, False, 0)

            # Reduced Motion toggle
            motion_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            m_label = Gtk.Label(label="Reduced motion", xalign=0)
            m_label.get_style_context().add_class("pk-supporting")
            motion_box.pack_start(m_label, True, True, 0)
            self.switch_motion = Gtk.Switch()
            self.switch_motion.set_active(os.environ.get("PK_REDUCED_MOTION") == "1")
            self.switch_motion.connect("notify::active", self._on_motion_toggle)
            motion_box.pack_start(self.switch_motion, False, False, 0)
            motion_box.get_style_context().add_class("pk-setting-row")
            settings_card.pack_start(motion_box, False, False, 0)

            theme_lbl = Gtk.Label(label="Appearance · PK-OS Slate", xalign=0)
            theme_lbl.get_style_context().add_class("pk-supporting")
            settings_card.pack_start(theme_lbl, False, False, 0)

            # Master volume changes are sent only to a detected real audio backend.
            audio_row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            v_label = Gtk.Label(label="Master volume", xalign=0)
            v_label.get_style_context().add_class("pk-supporting")
            audio_row.pack_start(v_label, False, False, 0)
            self.audio_backend, audio_message = detect_audio_backend()
            self.volume_status = Gtk.Label(
                label=audio_message,
                xalign=0,
            )
            self.volume_status.get_style_context().add_class("pk-detail")
            audio_row.pack_start(self.volume_status, False, False, 0)
            self.scale_volume = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
            self.scale_volume.set_value(75)
            self.scale_volume.set_sensitive(bool(self.audio_backend))
            self.scale_volume.connect("value-changed", self._on_volume_change)
            audio_row.pack_start(self.scale_volume, False, False, 0)
            settings_card.pack_start(audio_row, False, False, 0)

            # This switch stores a UI preference only; wake-word inference is not implemented.
            wake_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            wake_labels = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
            wake_label = Gtk.Label(label="Wake-word preference", xalign=0)
            wake_label.get_style_context().add_class("pk-supporting")
            wake_labels.pack_start(wake_label, False, False, 0)
            wake_note = Gtk.Label(label="Preference only · wake-word detection is not available.", xalign=0)
            wake_note.get_style_context().add_class("pk-detail")
            wake_labels.pack_start(wake_note, False, False, 0)
            wake_box.pack_start(wake_labels, True, True, 0)
            self.switch_wake = Gtk.Switch()
            self.switch_wake.set_active(False)
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

            # 3. Session footer; application windows are not managed by Cage.
            self.dock_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
            self.dock_box.get_style_context().add_class("pk-bottom-dock")
            dock_label = Gtk.Label(label="PK-OS PREVIEW")
            dock_label.get_style_context().add_class("pk-eyebrow")
            self.dock_box.pack_start(dock_label, False, False, 4)
            dock_note = Gtk.Label(label="Application windows unavailable in Cage")
            dock_note.get_style_context().add_class("pk-detail")
            self.dock_box.pack_start(dock_note, False, False, 4)
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
            if not self.audio_backend:
                self.volume_status.set_text("Unavailable: no supported audio control detected.")
                return
            try:
                if Path(self.audio_backend).name == "wpctl":
                    vol_float = val / 100.0
                    command = [
                        self.audio_backend, "set-volume", "@DEFAULT_AUDIO_SINK@", f"{vol_float:.2f}"
                    ]
                else:
                    command = [self.audio_backend, "sset", "Master", f"{val}%"]
                result = subprocess.run(
                    command,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False,
                    timeout=2,
                )
                if result.returncode:
                    detail = result.stderr.strip() or f"exit status {result.returncode}"
                    self.audio_backend = None
                    self.scale_volume.set_sensitive(False)
                    self.volume_status.set_text(f"Unavailable: audio control failed: {detail}")
                    self._log_to_console(f"Audio control failed: {detail}")
                    return
                self.volume_status.set_text(f"Volume command sent via {Path(self.audio_backend).name}.")
                self._log_to_console(f"Master volume set to {val}% via {Path(self.audio_backend).name}.")
            except (OSError, subprocess.TimeoutExpired) as exc:
                self.audio_backend = None
                self.scale_volume.set_sensitive(False)
                self.volume_status.set_text(f"Unavailable: audio control failed: {exc}")
                logger.warning("Audio volume control failed: %s", exc)

        def _on_shutdown_clicked(self) -> None:
            """Execute graceful guest system shutdown via systemctl poweroff."""
            self._confirm_lifecycle_action("poweroff")

        def _confirm_lifecycle_action(self, action: str) -> None:
            label = "Shut down PK-OS" if action == "poweroff" else "Restart PK-OS"
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.CANCEL,
                text=f"{label}?",
            )
            dialog.format_secondary_text(
                "This affects only the PK-OS guest virtual machine."
            )
            dialog.add_button(label, Gtk.ResponseType.ACCEPT)
            response = dialog.run()
            dialog.destroy()
            if response != Gtk.ResponseType.ACCEPT:
                self._log_to_console(f"{label} cancelled.")
                return

            self._run_lifecycle_action(action)

        def _run_lifecycle_action(self, action: str) -> None:
            label = "Shutting down" if action == "poweroff" else "Restarting"
            self._log_to_console(f"Requesting guest {action}...")
            if self.notification_manager:
                self.notification_manager.add("Power", f"{label} PK-OS guest...")
            try:
                systemctl = shutil.which("systemctl")
                sudo = shutil.which("sudo")
                if not systemctl or not sudo:
                    raise RuntimeError("Guest systemctl or sudo is unavailable.")
                subprocess.Popen([sudo, systemctl, action])
                self._log_to_console(f"Guest {action} request dispatched.")
            except Exception as exc:
                logger.error("Guest %s request failed: %s", action, exc)
                self.hud_response.set_text(f"Guest lifecycle request failed: {exc}")
                if self.notification_manager:
                    urgency = NotificationUrgency.CRITICAL if NotificationUrgency else "critical"
                    self.notification_manager.add("Power request failed", str(exc), urgency=urgency)

        def _on_reboot_clicked(self) -> None:
            """Execute graceful guest system reboot via systemctl reboot."""
            self._confirm_lifecycle_action("reboot")

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
            state = "preference enabled" if active else "preference disabled"
            self._log_to_console(f"Wake-word {state}; detection is not implemented.")
            if self.notification_manager:
                self.notification_manager.add(
                    "Wake-word preference",
                    f"{state.capitalize()}. Detection is not implemented.",
                    urgency=NotificationUrgency.INFO if NotificationUrgency else "info",
                )

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

            self.lbl_cpu.set_text(load["label"] if load["available"] else "Load: unavailable")
            self.lbl_mem.set_text(mem["label"])
            self.lbl_uptime.set_text(up["label"])
            self.lbl_clock.set_text(time.strftime("%H:%M:%S"))

            # Update intelligence daemon status badge
            if self.intelligence.is_daemon_online():
                self.hud_badge.set_text("RULE-BASED")
                self.hud_badge.get_style_context().remove_class("pk-badge-offline")
                self.hud_badge.get_style_context().add_class("pk-badge-online")
            else:
                self.hud_badge.set_text("OFFLINE")
                self.hud_badge.get_style_context().remove_class("pk-badge-online")
                self.hud_badge.get_style_context().add_class("pk-badge-offline")

        def _on_app_click(self, app_id: str) -> None:
            logger.info("Application launch requested: %s", app_id)
            response = self.intelligence.query(f"launch {app_id}")
            if response.get("ok"):
                detail = str(response.get("text") or response.get("result") or "Application started.")
                message = f"Launch request accepted: {detail}"
                title = "Application started"
            else:
                detail = str(response.get("detail") or response.get("error") or "Unknown launch failure")
                message = f"Could not launch {app_id}: {detail}"
                title = "Application unavailable"
            self.hud_response.set_text(message)
            self._log_to_console(message)
            if self.notification_manager:
                urgency = (
                    NotificationUrgency.INFO if response.get("ok") else NotificationUrgency.WARNING
                ) if NotificationUrgency else ("info" if response.get("ok") else "warning")
                self.notification_manager.add(title, message, urgency=urgency)

        def _on_intelligence_query(self, query: str) -> None:
            logger.info("Executing HUD query: %s", query)
            self.hud_response.set_text(f"Working… {query}")
            self._log_to_console(f"HUD query dispatched: '{query}'")
            res = query_with_user_approval(
                self.intelligence, query, self._prompt_system_change_approval
            )
            if res.get("error") == "approval_cancelled":
                self.hud_response.set_text("Request cancelled; no system change was made.")
                self._log_to_console("System change cancelled by user.")
                return
            if res.get("ok"):
                response = str(res.get("text") or json.dumps(res.get("result", {}), indent=2))
                model_used = res.get("model_used", "")
                if model_used:
                    engine = f"Engine: {model_used} · deterministic / no LLM"
                else:
                    engine = "Engine: deterministic local rules · no LLM inference"
                self.hud_response.set_text(f"{response}\n\n{engine}")
                self._log_to_console(f"Query succeeded via {model_used or 'deterministic local rules'}: {response}")
            else:
                error = res.get("detail") or res.get("error") or "Daemon unavailable"
                self.hud_response.set_text(f"Request unavailable: {error}")
                self._log_to_console(f"Query error: {error}")

        def _prompt_system_change_approval(self, query: str, detail: str) -> bool:
            dialog = Gtk.MessageDialog(
                transient_for=self,
                modal=True,
                message_type=Gtk.MessageType.WARNING,
                buttons=Gtk.ButtonsType.CANCEL,
                text="Approve this system change?",
            )
            dialog.format_secondary_text(
                f"Request: {query}\n{detail}\n\n"
                "The action applies only to this guest and will run only after you approve it."
            )
            dialog.add_button("Approve once", Gtk.ResponseType.ACCEPT)
            dialog.set_default_response(Gtk.ResponseType.CANCEL)
            approved = dialog.run() == Gtk.ResponseType.ACCEPT
            dialog.destroy()
            return approved

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
