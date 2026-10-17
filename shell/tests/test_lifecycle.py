"""
Tests for PK-OS Shell Lifecycle State Machine
Verifies legal transitions, forbidden jumps, and config validation.
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.session.lifecycle import ShellSession, SessionState, ShellConfig, ShellLayer


class TestShellLifecycle(unittest.TestCase):
    def test_config_validation_success(self):
        cfg = ShellConfig(panel_height_px=40, font_family="Inter")
        self.assertTrue(cfg.validate())

    def test_config_validation_failure(self):
        with self.assertRaises(ValueError):
            cfg = ShellConfig(panel_height_px=10)
            cfg.validate()

    def test_standard_lifecycle_flow(self):
        session = ShellSession()
        self.assertEqual(session.state, SessionState.INIT)

        session.transition_to(SessionState.READY)
        self.assertEqual(session.state, SessionState.READY)

        session.transition_to(SessionState.ACTIVE)
        self.assertEqual(session.state, SessionState.ACTIVE)

        session.transition_to(SessionState.SUSPENDED)
        self.assertEqual(session.state, SessionState.SUSPENDED)

        session.transition_to(SessionState.ACTIVE)
        self.assertEqual(session.state, SessionState.ACTIVE)

        session.transition_to(SessionState.TERMINATED)
        self.assertEqual(session.state, SessionState.TERMINATED)

    def test_illegal_transition_rejection(self):
        session = ShellSession()
        with self.assertRaises(RuntimeError):
            session.transition_to(SessionState.ACTIVE)  # Must go INIT -> READY first

    def test_surface_attachment_tracking(self):
        session = ShellSession()
        session.transition_to(SessionState.READY)
        self.assertEqual(session.attach_surface(ShellLayer.TOP), 1)
        self.assertEqual(session.attach_surface(ShellLayer.OVERLAY), 2)
        self.assertEqual(session.detach_surface(), 1)


if __name__ == "__main__":
    unittest.main()
