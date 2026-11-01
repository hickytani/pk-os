#!/usr/bin/env python3
"""Validate the versioned assistant dataset bundle without third-party packages."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.local_training import validate_dataset_bundle


def main() -> int:
    try:
        report = validate_dataset_bundle()
    except ValueError as exc:
        print(f"Dataset validation failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
