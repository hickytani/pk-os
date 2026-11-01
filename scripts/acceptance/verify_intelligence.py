#!/usr/bin/env python3
"""Run the deterministic intent and policy benchmark and validate the data bundle."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.benchmark import run_intent_benchmark
from intelligence.src.local_training import validate_dataset_bundle
from intelligence.src.orchestration import PKIntelligenceOrchestrator


def main() -> int:
    benchmark = run_intent_benchmark(PKIntelligenceOrchestrator()).to_dict()
    dataset = validate_dataset_bundle()
    result = {"benchmark": benchmark, "dataset": dataset}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if (
        benchmark["total_samples"] == 14
        and benchmark["security_block_rate_pct"] == 100.0
        and dataset["checksums_valid"]
        and dataset["id_overlap"] == 0
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())
