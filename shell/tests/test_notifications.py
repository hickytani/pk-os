"""
Tests for PK-OS Notification System (Phase 2D)
"""

import time
import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent))

from shell.src.ui.notifications import (
    Notification,
    NotificationUrgency,
    NotificationManager,
)


class TestNotification:
    """Tests for the Notification data class."""

    def test_notification_creation(self):
        n = Notification(title="Test", body="Body text")
        assert n.title == "Test"
        assert n.body == "Body text"
        assert n.urgency == NotificationUrgency.INFO
        assert not n.dismissed
        assert len(n.id) == 12

    def test_notification_auto_dismiss_info(self):
        n = Notification(title="Info", auto_dismiss_sec=0.0)
        assert n.should_auto_dismiss is True

    def test_notification_no_auto_dismiss_critical(self):
        n = Notification(
            title="Critical",
            urgency=NotificationUrgency.CRITICAL,
            auto_dismiss_sec=0.0,
        )
        assert n.should_auto_dismiss is False

    def test_notification_dismiss_creates_copy(self):
        n = Notification(title="Test")
        dismissed = n.dismiss()
        assert dismissed.dismissed is True
        assert n.dismissed is False  # Original unmodified
        assert dismissed.id == n.id

    def test_notification_age(self):
        n = Notification(title="Test", created_at=time.time() - 10)
        assert n.age_seconds >= 10


class TestNotificationManager:
    """Tests for the NotificationManager queue."""

    def test_notify_creates_notification(self):
        mgr = NotificationManager()
        n = mgr.notify("Hello", body="World")
        assert mgr.active_count == 1
        assert n.title == "Hello"

    def test_notify_respects_max_capacity(self):
        mgr = NotificationManager()
        for i in range(10):
            mgr.notify(f"Notification {i}")
        assert mgr.active_count <= NotificationManager.MAX_ACTIVE

    def test_dismiss_by_id(self):
        mgr = NotificationManager()
        n = mgr.notify("Test")
        assert mgr.dismiss(n.id) is True
        assert mgr.active_count == 0
        assert len(mgr.history) == 1

    def test_dismiss_nonexistent_returns_false(self):
        mgr = NotificationManager()
        assert mgr.dismiss("nonexistent") is False

    def test_dismiss_all(self):
        mgr = NotificationManager()
        mgr.notify("A")
        mgr.notify("B")
        count = mgr.dismiss_all()
        assert count == 2
        assert mgr.active_count == 0

    def test_tick_auto_dismisses(self):
        mgr = NotificationManager()
        mgr.notify("Test", auto_dismiss_sec=0.0)
        dismissed = mgr.tick()
        assert len(dismissed) == 1
        assert mgr.active_count == 0

    def test_tick_keeps_critical(self):
        mgr = NotificationManager()
        mgr.notify("Critical", urgency=NotificationUrgency.CRITICAL, auto_dismiss_sec=0.0)
        dismissed = mgr.tick()
        assert len(dismissed) == 0
        assert mgr.active_count == 1

    def test_urgency_ordering(self):
        mgr = NotificationManager()
        mgr.notify("Low", urgency=NotificationUrgency.INFO)
        mgr.notify("High", urgency=NotificationUrgency.CRITICAL)
        mgr.notify("Mid", urgency=NotificationUrgency.WARNING)
        active = mgr.active_notifications
        assert active[0].urgency == NotificationUrgency.CRITICAL
        assert active[1].urgency == NotificationUrgency.WARNING

    def test_callback_on_added(self):
        mgr = NotificationManager()
        added = []
        mgr.set_on_added(lambda n: added.append(n))
        mgr.notify("Test")
        assert len(added) == 1

    def test_callback_on_dismissed(self):
        mgr = NotificationManager()
        dismissed = []
        mgr.set_on_dismissed(lambda n: dismissed.append(n))
        n = mgr.notify("Test")
        mgr.dismiss(n.id)
        assert len(dismissed) == 1

    def test_get_by_id(self):
        mgr = NotificationManager()
        n = mgr.notify("Findme")
        found = mgr.get_by_id(n.id)
        assert found is not None
        assert found.title == "Findme"

    def test_history_limit(self):
        mgr = NotificationManager()
        for i in range(60):
            n = mgr.notify(f"N{i}")
            mgr.dismiss(n.id)
        assert len(mgr.history) <= NotificationManager.MAX_HISTORY
