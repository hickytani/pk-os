#!/usr/bin/env python3
"""Run the deterministic intent and policy benchmark and validate the data bundle."""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.benchmark import run_intent_benchmark
from intelligence.src.context import ContextEngine
from intelligence.src.local_training import validate_dataset_bundle
from intelligence.src.orchestration import PKIntelligenceOrchestrator


def run_verification(state_dir: Path) -> dict[str, object]:
    """Run checks with state isolated from the user's installed PK-OS data."""
    state_dir = Path(state_dir)
    context = ContextEngine(
        prefs_path=str(state_dir / "preferences.json"),
        history_path=str(state_dir / "query_history.json"),
    )
    benchmark = run_intent_benchmark(
        PKIntelligenceOrchestrator(context_engine=context)
    ).to_dict()
    dataset = validate_dataset_bundle()
    return {"benchmark": benchmark, "dataset": dataset}


def main() -> int:
    # Verification must not inspect or write /var/lib/pk-os, which belongs to
    # the installed service and may contain a real user's private query history.
    with tempfile.TemporaryDirectory(prefix="pkos-intelligence-verify-") as state_dir:
        result = run_verification(Path(state_dir))
    benchmark = result["benchmark"]
    dataset = result["dataset"]
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if (
        benchmark["total_samples"] == 14
        and benchmark["security_block_rate_pct"] == 100.0
        and dataset["checksums_valid"]
        and dataset["id_overlap"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
