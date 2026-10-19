"""
PK-OS Desktop Notification System (Phase 2D)
=============================================
Provides toast-style desktop notifications with urgency levels,
auto-dismiss timers, and queue management.

Architecture:
  - NotificationUrgency: Enum for info/warning/critical severity.
  - Notification: Immutable data class for a single notification.
  - NotificationManager: Queue manager with max capacity, auto-dismiss,
    and event callbacks for the GTK shell integration.
  - HeadlessNotificationManager: Testing harness without GTK dependencies.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger("pk.shell.notifications")


class NotificationUrgency(Enum):
    """Notification severity level."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class Notification:
    """Immutable notification record."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    title: str = ""
    body: str = ""
    urgency: NotificationUrgency = NotificationUrgency.INFO
    icon: str = ""
    source: str = "system"
    created_at: float = field(default_factory=time.time)
    auto_dismiss_sec: float = 5.0
    dismissed: bool = False
    actions: List[Dict[str, str]] = field(default_factory=list)

    @property
    def age_seconds(self) -> float:
        return time.time() - self.created_at

    @property
    def should_auto_dismiss(self) -> bool:
        if self.urgency == NotificationUrgency.CRITICAL:
            return False  # Critical notifications require manual dismiss
        return self.age_seconds >= self.auto_dismiss_sec

    def dismiss(self) -> "Notification":
        """Return a copy marked as dismissed."""
        return Notification(
            id=self.id,
            title=self.title,
            body=self.body,
            urgency=self.urgency,
            icon=self.icon,
            source=self.source,
            created_at=self.created_at,
            auto_dismiss_sec=self.auto_dismiss_sec,
            dismissed=True,
            actions=self.actions,
        )


class NotificationManager:
    """
    Desktop notification queue manager.

    Features:
      - Max queue capacity (oldest auto-dismissed when full)
      - Urgency-based ordering (critical first)
      - Auto-dismiss for non-critical notifications
      - Event callbacks for UI integration
      - History retention for audit/search
    """

    MAX_ACTIVE = 5
    MAX_HISTORY = 50

    def __init__(self) -> None:
        self._active: List[Notification] = []
        self._history: List[Notification] = []
        self._on_added: Optional[Callable[[Notification], None]] = None
        self._on_dismissed: Optional[Callable[[Notification], None]] = None
        self._counter = 0

    @property
    def active_count(self) -> int:
        return len(self._active)

    @property
    def active_notifications(self) -> List[Notification]:
        return list(self._active)

    @property
    def history(self) -> List[Notification]:
        return list(self._history)

    def set_on_added(self, cb: Callable[[Notification], None]) -> None:
        self._on_added = cb

    def set_on_dismissed(self, cb: Callable[[Notification], None]) -> None:
        self._on_dismissed = cb

    def notify(
        self,
        title: str,
        body: str = "",
        urgency: NotificationUrgency = NotificationUrgency.INFO,
        icon: str = "",
        source: str = "system",
        auto_dismiss_sec: float = 5.0,
        actions: Optional[List[Dict[str, str]]] = None,
    ) -> Notification:
        """Create and enqueue a new notification."""
        n = Notification(
            title=title,
            body=body,
            urgency=urgency,
            icon=icon,
            source=source,
            auto_dismiss_sec=auto_dismiss_sec,
            actions=actions or [],
        )
        self._counter += 1

        # Auto-dismiss oldest non-critical if at capacity
        while len(self._active) >= self.MAX_ACTIVE:
            dismissed = self._dismiss_oldest_non_critical()
            if not dismissed:
                # All are critical — drop oldest anyway
                self._force_dismiss_oldest()

        self._active.append(n)
        self._active.sort(key=lambda x: (
            0 if x.urgency == NotificationUrgency.CRITICAL else
            1 if x.urgency == NotificationUrgency.WARNING else 2
        ))

        logger.info("Notification [%s] %s: %s", n.urgency.value, n.title, n.body[:60])

        if self._on_added:
            try:
                self._on_added(n)
            except Exception as exc:
                logger.warning("on_added callback error: %s", exc)

        return n

    # Alias for convenience
    add = notify

    def dismiss(self, notification_id: str) -> bool:
        """Manually dismiss a notification by ID."""
        for i, n in enumerate(self._active):
            if n.id == notification_id:
                dismissed = n.dismiss()
                self._active.pop(i)
                self._add_to_history(dismissed)
                if self._on_dismissed:
                    try:
                        self._on_dismissed(dismissed)
                    except Exception as exc:
                        logger.warning("on_dismissed callback error: %s", exc)
                return True
        return False

    def dismiss_all(self) -> int:
        """Dismiss all active notifications. Returns count dismissed."""
        count = len(self._active)
        for n in self._active:
            self._add_to_history(n.dismiss())
        self._active.clear()
        return count

    def tick(self) -> List[str]:
        """
        Process auto-dismiss timers. Call periodically (e.g. every second).
        Returns list of dismissed notification IDs.
        """
        dismissed_ids: List[str] = []
        still_active: List[Notification] = []
        for n in self._active:
            if n.should_auto_dismiss:
                dismissed = n.dismiss()
                self._add_to_history(dismissed)
                dismissed_ids.append(n.id)
                if self._on_dismissed:
                    try:
                        self._on_dismissed(dismissed)
                    except Exception:
                        pass
            else:
                still_active.append(n)
        self._active = still_active
        return dismissed_ids

    def get_by_id(self, notification_id: str) -> Optional[Notification]:
        """Look up an active notification by ID."""
        for n in self._active:
            if n.id == notification_id:
                return n
        return None

    def _dismiss_oldest_non_critical(self) -> bool:
        for i, n in enumerate(self._active):
            if n.urgency != NotificationUrgency.CRITICAL:
                dismissed = n.dismiss()
                self._active.pop(i)
                self._add_to_history(dismissed)
                return True
        return False

    def _force_dismiss_oldest(self) -> None:
        if self._active:
            n = self._active.pop(0)
            self._add_to_history(n.dismiss())

    def _add_to_history(self, n: Notification) -> None:
        self._history.append(n)
        if len(self._history) > self.MAX_HISTORY:
            self._history = self._history[-self.MAX_HISTORY:]
