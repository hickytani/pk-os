"""
PK-OS Shell Session Lifecycle Manager
Defines the state transitions, configuration schema, and signal dispatch
for the independent pk-shell Wayland client process.
"""

from enum import Enum, auto
from typing import Dict, Any, Optional, Callable, List
import dataclasses
import time


class SessionState(Enum):
    INIT = auto()
    READY = auto()
    ACTIVE = auto()
    SUSPENDED = auto()
    TERMINATED = auto()


class ShellLayer(Enum):
    BACKGROUND = "background"
    BOTTOM = "bottom"
    TOP = "top"
    OVERLAY = "overlay"


@dataclasses.dataclass(frozen=True)
class ShellConfig:
    panel_height_px: int = 36
    enable_voice_hud: bool = True
    exclusive_zone: bool = True
    font_family: str = "Inter"
    theme: str = "obsidian_dark"
    keybind_launcher: str = "Super"
    keybind_voice: str = "Super+Space"

    def validate(self) -> bool:
        if self.panel_height_px < 24 or self.panel_height_px > 64:
            raise ValueError(f"Invalid panel height: {self.panel_height_px}px (must be 24-64)")
        if not self.font_family:
            raise ValueError("Font family cannot be empty")
        return True


class ShellSession:
    def __init__(self, config: Optional[ShellConfig] = None):
        self.config = config or ShellConfig()
        self.config.validate()
        self.state = SessionState.INIT
        self.active_surface_count = 0
        self._listeners: Dict[SessionState, List[Callable[[], None]]] = {
            s: [] for s in SessionState
        }
        self.history: List[SessionState] = [SessionState.INIT]

    def register_listener(self, state: SessionState, callback: Callable[[], None]) -> None:
        self._listeners[state].append(callback)

    def transition_to(self, new_state: SessionState) -> None:
        valid_transitions = {
            SessionState.INIT: [SessionState.READY, SessionState.TERMINATED],
            SessionState.READY: [SessionState.ACTIVE, SessionState.TERMINATED],
            SessionState.ACTIVE: [SessionState.SUSPENDED, SessionState.TERMINATED],
            SessionState.SUSPENDED: [SessionState.ACTIVE, SessionState.TERMINATED],
            SessionState.TERMINATED: []
        }

        if new_state not in valid_transitions[self.state]:
            raise RuntimeError(f"Illegal state transition from {self.state} to {new_state}")

        self.state = new_state
        self.history.append(new_state)

        for callback in self._listeners[new_state]:
            callback()

    def attach_surface(self, layer: ShellLayer) -> int:
        if self.state not in (SessionState.READY, SessionState.ACTIVE):
            raise RuntimeError(f"Cannot attach surface in state {self.state}")
        self.active_surface_count += 1
        return self.active_surface_count

    def detach_surface(self) -> int:
        if self.active_surface_count > 0:
            self.active_surface_count -= 1
        return self.active_surface_count
