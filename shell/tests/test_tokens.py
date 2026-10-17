"""
Tests for PK-OS Shell Design Tokens
Verifies JSON validity, 4px grid conformance, and WCAG contrast math.
"""

import json
import os
import math
import unittest


def luminance(hex_color: str) -> float:
    hex_color = hex_color.lstrip("#")
    r = int(hex_color[0:2], 16) / 255.0
    g = int(hex_color[2:4], 16) / 255.0
    b = int(hex_color[4:6], 16) / 255.0

    def adjust(c: float) -> float:
        return c / 12.92 if c <= 0.03928 else math.pow((c + 0.055) / 1.055, 2.4)

    return 0.2126 * adjust(r) + 0.7152 * adjust(g) + 0.0722 * adjust(b)


def contrast_ratio(hex1: str, hex2: str) -> float:
    l1 = luminance(hex1)
    l2 = luminance(hex2)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


class TestDesignTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        tokens_path = os.path.join(base_dir, "src", "tokens", "tokens.json")
        with open(tokens_path, "r", encoding="utf-8") as f:
            cls.tokens = json.load(f)

    def test_required_sections_present(self):
        self.assertIn("color", self.tokens)
        self.assertIn("spacing", self.tokens)
        self.assertIn("typography", self.tokens)
        self.assertIn("motion", self.tokens)

    def test_4px_grid_adherence(self):
        for name, value in self.tokens["spacing"].items():
            self.assertEqual(value % 4, 0, f"Spacing {name} ({value}px) violates 4px grid")

    def test_contrast_ratio_primary_text_wcag_aaa(self):
        bg = self.tokens["color"]["bg_base"]
        text_primary = self.tokens["color"]["text_primary"]
        ratio = contrast_ratio(bg, text_primary)
        # WCAG AAA requires at least 7.0:1 for normal text
        self.assertGreater(ratio, 7.0, f"Contrast {ratio:.2f}:1 is below WCAG AAA (7.0:1)")

    def test_contrast_ratio_secondary_text_wcag_aa(self):
        bg = self.tokens["color"]["bg_base"]
        text_secondary = self.tokens["color"]["text_secondary"]
        ratio = contrast_ratio(bg, text_secondary)
        # WCAG AA requires at least 4.5:1 for normal text
        self.assertGreater(ratio, 4.5, f"Contrast {ratio:.2f}:1 is below WCAG AA (4.5:1)")


if __name__ == "__main__":
    unittest.main()
