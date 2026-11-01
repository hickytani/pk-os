"""Regression checks for token-aware screenshot diagnostics."""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = REPO_ROOT / "scripts" / "verify-screenshot.py"
SPEC = importlib.util.spec_from_file_location("verify_screenshot", VERIFY_PATH)
assert SPEC and SPEC.loader
verify_screenshot = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_screenshot
SPEC.loader.exec_module(verify_screenshot)


class TestScreenshotVerification(unittest.TestCase):
    def test_theme_tokens_meet_contrast_contract(self):
        report = verify_screenshot.token_theme_report()
        self.assertTrue(report["contrast_pass"])
        self.assertTrue(all(item["ratio"] >= 4.5 for item in report["contrast_checks"]))

    def test_screenshot_palette_metric_uses_current_tokens(self):
        colors = json.loads(
            (REPO_ROOT / "shell" / "src" / "tokens" / "tokens.json").read_text(encoding="utf-8")
        )["color"]
        rgb = [verify_screenshot.hex_rgb(colors[name]) for name in (
            "bg_base", "bg_surface", "text_primary", "accent_cyan"
        )]
        width, height = 640, 480
        image = bytearray()
        for y in range(height):
            for x in range(width):
                color = rgb[(y // (height // 2)) * 2 + (x // (width // 2))]
                image.extend(color)
        with tempfile.TemporaryDirectory() as directory:
            ppm = Path(directory) / "tokens.ppm"
            ppm.write_bytes(f"P6\n{width} {height}\n255\n".encode("ascii") + image)
            report = verify_screenshot.analyze_screenshot(str(ppm))
        self.assertEqual(report["token_palette_match_pct"], 100.0)
        self.assertEqual(report["token_background_match_pct"], 50.0)


if __name__ == "__main__":
    unittest.main()
