"""
Tests for PK-OS Shell Adaptive Layout Calculator
Verifies geometry for desktop (1920x1080) vs phone/mobile (390x844).
"""

import unittest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from src.ui.layout import LayoutCalculator, DisplayFormFactor


class TestAdaptiveLayout(unittest.TestCase):
    def test_desktop_form_factor(self):
        self.assertEqual(LayoutCalculator.get_form_factor(1920), DisplayFormFactor.DESKTOP)
        self.assertEqual(LayoutCalculator.get_form_factor(1024), DisplayFormFactor.DESKTOP)

    def test_mobile_form_factor(self):
        self.assertEqual(LayoutCalculator.get_form_factor(390), DisplayFormFactor.MOBILE)
        self.assertEqual(LayoutCalculator.get_form_factor(800), DisplayFormFactor.MOBILE)

    def test_desktop_top_panel_geometry(self):
        geom = LayoutCalculator.calculate_top_panel(1920, 1080)
        self.assertEqual(geom.width, 1920)
        self.assertEqual(geom.height, 36)
        self.assertTrue(geom.anchor_top)
        self.assertEqual(geom.exclusive_zone, 36)

    def test_mobile_top_panel_geometry(self):
        geom = LayoutCalculator.calculate_top_panel(390, 844)
        self.assertEqual(geom.width, 390)
        self.assertEqual(geom.height, 44)  # Touch target is taller
        self.assertEqual(geom.exclusive_zone, 44)

    def test_launcher_adaptive_geometry(self):
        desktop = LayoutCalculator.calculate_launcher_modal(1920, 1080)
        self.assertEqual(desktop.width, 680)
        self.assertFalse(desktop.anchor_top)  # Centered modal

        mobile = LayoutCalculator.calculate_launcher_modal(390, 844)
        self.assertEqual(mobile.width, 390)
        self.assertEqual(mobile.height, 844)
        self.assertTrue(mobile.anchor_top)
        self.assertTrue(mobile.anchor_bottom)  # Full screen drawer


if __name__ == "__main__":
    unittest.main()
