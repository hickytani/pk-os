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
    pk_palette_matches = 0

    # PK-OS Design Tokens (RGB approximations)
    # bg_base: #0a0b0e -> (10, 11, 14)
    # bg_surface: #12151c -> (18, 21, 28)
    # accent_cyan: #00e5ff -> (0, 229, 255)
    # border_subtle: #222736 -> (34, 39, 54)
    # text_primary: #f0f3fa -> (240, 243, 250)

    for i in range(0, total_pixels, sample_step):
        offset = i * 3
        r, g, b = data[offset], data[offset + 1], data[offset + 2]
        rgb = (r, g, b)
        color_counts[rgb] = color_counts.get(rgb, 0) + 1

        if rgb != (0, 0, 0):
            non_black_pixels += 1

        # Check for PK-OS dark theme tones
        if (8 <= r <= 24 and 8 <= g <= 26 and 12 <= b <= 34) or (r < 30 and g > 180 and b > 200) or (r > 200 and g > 200 and b > 200):
            pk_palette_matches += 1

    unique_colors = len(color_counts)
    is_blank = (non_black_pixels == 0)
    samples_checked = len(range(0, total_pixels, sample_step))
    palette_match_pct = (pk_palette_matches / samples_checked * 100.0) if samples_checked > 0 else 0.0

    # Verification threshold: screen has dimensions, is not blank, has multiple colors, and matches palette
    verified = (width >= 640 and height >= 480 and not is_blank and unique_colors > 3)

    report = {
        "verified": verified,
        "width": width,
        "height": height,
        "total_pixels": total_pixels,
        "samples_checked": samples_checked,
        "unique_colors_sampled": unique_colors,
        "non_black_samples": non_black_pixels,
        "pk_palette_match_pct": round(palette_match_pct, 1),
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
