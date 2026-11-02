#!/usr/bin/env python3
"""Summarize observable renderer/output facts without inferring acceleration.

This parser consumes a guest serial/QEMU boot transcript plus the session unit
that was used. It intentionally reports missing instrumentation as unknown.
It never treats a visible framebuffer or a loaded DRM driver as proof that the
compositor uses hardware rendering.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any


OUTPUT_FAILURE = re.compile(r"Basic output test failed for ([A-Za-z0-9_.:-]+)")
KERNEL_TIME = re.compile(r"\[\s*([0-9]+(?:\.[0-9]+)?)\]")
GEOMETRY = re.compile(r"Form factor: [^\r\n]*\((\d+)x(\d+)\)")
DRM_FACTS = (
    re.compile(r"\[drm\].*(?:virtio-vga detected|features:|number of scanouts|number of cap sets|Initialized virtio_gpu|frame buffer device)", re.I),
)


def analyze(log_text: str, service_text: str) -> dict[str, Any]:
    """Return a factual, machine-readable summary of one recorded boot."""
    lines = log_text.splitlines()
    failures: list[tuple[str, float | None]] = []
    for line in lines:
        match = OUTPUT_FAILURE.search(line)
        if not match:
            continue
        time_match = KERNEL_TIME.search(line)
        failures.append((match.group(1), float(time_match.group(1)) if time_match else None))

    renderer_match = re.search(r"^Environment=WLR_RENDERER=(\S+)\s*$", service_text, re.M)
    renderer = renderer_match.group(1) if renderer_match else None
    cage_exec = next((line.partition("=")[2] for line in service_text.splitlines() if line.startswith("ExecStart=") and "cage" in line), None)
    debug_lines = [line for line in lines if "[DEBUG]" in line or "[debug]" in line]
    drm_lines = [line.strip() for line in lines if any(pattern.search(line) for pattern in DRM_FACTS)]
    geometry_match = GEOMETRY.search(log_text)
    geometry = (
        {"width": int(geometry_match.group(1)), "height": int(geometry_match.group(2)), "source": "PK shell form-factor log"}
        if geometry_match
        else None
    )

    times = [timestamp for _, timestamp in failures if timestamp is not None]
    output_names = sorted({name for name, _ in failures})
    virgl_unavailable = any("-virgl" in line for line in drm_lines)
    if renderer == "pixman":
        renderer_status = "software_renderer_forced_by_session_unit"
    elif renderer:
        renderer_status = "renderer_environment_override_present; runtime renderer not confirmed"
    else:
        renderer_status = "renderer_selection_unknown"

    return {
        "schema_version": 1,
        "renderer": {
            "wlr_renderer_environment": renderer,
            "status": renderer_status,
            "debug_log_lines_found": len(debug_lines),
            "gpu_acceleration": "not_established",
        },
        "output": {
            "basic_output_test_failure_count": len(failures),
            "failed_outputs": output_names,
            "first_failure_kernel_seconds": min(times) if times else None,
            "last_failure_kernel_seconds": max(times) if times else None,
            "root_cause": "unresolved; transcript reports failure but not the wlroots test sub-result",
            "session_form_factor_geometry": geometry,
        },
        "kernel_drm_observations": drm_lines,
        "qemu_virgl_feature_reported_unavailable": virgl_unavailable,
        "cage_exec_start": cage_exec,
        "cage_command_debug_option_present": bool(cage_exec and re.search(r"(?:^|\s)-D(?:\s|$)", cage_exec)),
        "performance_metrics": {
            "frame_times": "unavailable",
            "fps": "unavailable",
            "dropped_frames": "unavailable",
            "gpu_utilization": "unavailable",
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, required=True, help="guest serial/QEMU log")
    parser.add_argument("--service", type=Path, required=True, help="systemd graphical session unit")
    parser.add_argument("--output", type=Path, help="write JSON to this path (stdout otherwise)")
    args = parser.parse_args()
    try:
        report = analyze(args.log.read_text(encoding="utf-8", errors="replace"), args.service.read_text(encoding="utf-8"))
    except OSError as exc:
        print(f"render diagnostics: {exc}", file=sys.stderr)
        return 2
    payload = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    else:
        sys.stdout.write(payload)
    return 0


if __name__ == "__main__":
    sys.exit(main())
