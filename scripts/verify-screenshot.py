#!/usr/bin/env python3
"""
scripts/verify-screenshot.py — Defensible Visual Verification for PK-OS Graphical Boot
Analyzes a QEMU framebuffer screendump (PPM format) to prove actual graphical rendering.
"""

import hashlib
import json
import os
import struct
import sys
from pathlib import Path


def parse_ppm(ppm_path: Path):
    """Parse binary P6 PPM file and return header metadata and RGB buffer."""
    with open(ppm_path, "rb") as f:
        magic = f.readline().strip()
        if magic != b"P6":
            raise ValueError(f"Invalid PPM magic: {magic} (expected b'P6')")

        # Read dimensions, skipping comments
        dims = []
        while len(dims) < 3:
            line = f.readline().strip()
            if not line or line.startswith(b"#"):
                continue
            for token in line.split():
                dims.append(int(token))

        width, height, max_val = dims[0], dims[1], dims[2]
        data = f.read()

    expected_len = width * height * 3
    if len(data) < expected_len:
        raise ValueError(f"PPM data truncated: got {len(data)} bytes, expected {expected_len}")

    return width, height, max_val, data


def hex_rgb(value: str) -> tuple[int, int, int]:
    """Convert a six-digit design-token color to integer RGB channels."""
    value = value.removeprefix("#")
    if len(value) != 6:
        raise ValueError(f"Expected #RRGGBB token color, got {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (0, 2, 4))


def relative_luminance(rgb: tuple[int, int, int]) -> float:
    channels = []
    for channel in rgb:
        normalized = channel / 255
        channels.append(
            normalized / 12.92 if normalized <= 0.04045
            else ((normalized + 0.055) / 1.055) ** 2.4
        )
    return sum(weight * channel for weight, channel in zip((0.2126, 0.7152, 0.0722), channels))


def contrast_ratio(first: tuple[int, int, int], second: tuple[int, int, int]) -> float:
    lighter, darker = sorted(
        (relative_luminance(first), relative_luminance(second)), reverse=True
    )
    return (lighter + 0.05) / (darker + 0.05)


def token_theme_report(token_path: Path | None = None) -> dict:
    """Check text/control contrast against the shared color tokens."""
    if token_path is None:
        token_path = Path(__file__).resolve().parents[1] / "shell" / "src" / "tokens" / "tokens.json"
    colors_json = json.loads(token_path.read_text(encoding="utf-8"))["color"]
    colors = {key: hex_rgb(value) for key, value in colors_json.items()}
    pairs = (
        ("primary text / base", "text_primary", "bg_base"),
        ("secondary text / base", "text_secondary", "bg_base"),
        ("tertiary text / base", "text_tertiary", "bg_base"),
        ("primary text / raised surface", "text_primary", "bg_surface_raised"),
        ("base text / cyan accent", "bg_base", "accent_cyan"),
    )
    checks = [
        {"pair": label, "ratio": round(contrast_ratio(colors[fg], colors[bg]), 2), "minimum": 4.5}
        for label, fg, bg in pairs
    ]
    return {
        "contrast_checks": checks,
        "contrast_pass": all(row["ratio"] >= row["minimum"] for row in checks),
    }


def analyze_screenshot(ppm_path_str: str) -> dict:
    ppm_path = Path(ppm_path_str)
    if not ppm_path.exists():
        return {"verified": False, "error": f"Screenshot file not found: {ppm_path}"}

    file_size = ppm_path.stat().st_size
    with open(ppm_path, "rb") as f:
        file_sha256 = hashlib.sha256(f.read()).hexdigest()

    try:
        width, height, max_val, data = parse_ppm(ppm_path)
    except Exception as exc:
        return {
            "verified": False,
            "error": f"PPM parse failed: {exc}",
            "sha256": file_sha256,
            "size_bytes": file_size,
        }

    total_pixels = width * height

    # Sample color distribution
    color_counts = {}
    sample_step = max(1, total_pixels // 10000)  # sample up to 10k pixels

    non_black_pixels = 0
    palette_matches = 0
    background_matches = 0
    token_file = Path(__file__).resolve().parents[1] / "shell" / "src" / "tokens" / "tokens.json"
    token_colors = json.loads(token_file.read_text(encoding="utf-8"))["color"]
    palette = {name: hex_rgb(color) for name, color in token_colors.items()}
    tolerance_rgb = 20

    for i in range(0, total_pixels, sample_step):
        offset = i * 3
        r, g, b = data[offset], data[offset + 1], data[offset + 2]
        rgb = (r, g, b)
        color_counts[rgb] = color_counts.get(rgb, 0) + 1

        if rgb != (0, 0, 0):
            non_black_pixels += 1

        nearest_name, nearest_color = min(
            palette.items(),
            key=lambda item: sum((channel - token) ** 2 for channel, token in zip(rgb, item[1])),
        )
        distance = sum((channel - token) ** 2 for channel, token in zip(rgb, nearest_color)) ** 0.5
        if distance <= tolerance_rgb:
            palette_matches += 1
            if nearest_name in ("bg_base", "bg_surface", "bg_surface_raised", "bg_surface_hover"):
                background_matches += 1

    unique_colors = len(color_counts)
    is_blank = (non_black_pixels == 0)
    samples_checked = len(range(0, total_pixels, sample_step))
    palette_match_pct = (palette_matches / samples_checked * 100.0) if samples_checked > 0 else 0.0
    background_match_pct = (background_matches / samples_checked * 100.0) if samples_checked > 0 else 0.0

    # These are capture/rendering gates only. Palette coverage is diagnostic and
    # does not establish layout, legibility, or interaction acceptance.
    verified = (width >= 640 and height >= 480 and not is_blank and unique_colors > 3)

    report = {
        "verified": verified,
        "width": width,
        "height": height,
        "total_pixels": total_pixels,
        "samples_checked": samples_checked,
        "unique_colors_sampled": unique_colors,
        "non_black_samples": non_black_pixels,
        "token_palette_match_pct": round(palette_match_pct, 1),
        "token_palette_tolerance_rgb": tolerance_rgb,
        "token_background_match_pct": round(background_match_pct, 1),
        "palette_metric_scope": "diagnostic only; not a visual acceptance score",
        **token_theme_report(),
        "file_size_bytes": file_size,
        "sha256": file_sha256,
        "format": "PPM (binary P6)",
    }

    # Attempt to convert to PNG for documentation artifact
    try:
        from PIL import Image
        img = Image.frombytes("RGB", (width, height), data)
        png_path = ppm_path.with_suffix(".png")
        img.save(png_path)
        report["png_artifact"] = str(png_path)
    except Exception:
        report["png_artifact"] = "Pillow not installed; raw PPM preserved"

    return report


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: verify-screenshot.py <path-to-screenshot.ppm>")
        sys.exit(1)

    res = analyze_screenshot(sys.argv[1])
    print(json.dumps(res, indent=2))
    sys.exit(0 if res.get("verified") else 1)
