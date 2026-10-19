"""
Tests for PK Intelligence Benchmark Evaluator (Phase 2E)
"""

import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from intelligence.src.benchmark import run_intent_benchmark, EVALUATION_DATASET, BENCHMARK_SCHEMA_VERSION
from intelligence.src.orchestration import PKIntelligenceOrchestrator


class TestBenchmarkSuite:
    def setup_method(self):
        self.orchestrator = PKIntelligenceOrchestrator()

    def test_benchmark_schema_version(self):
        assert BENCHMARK_SCHEMA_VERSION == "1.0.0"
        assert len(EVALUATION_DATASET) >= 10

    def test_run_benchmark_metrics(self):
        report = run_intent_benchmark(self.orchestrator)
        assert report.total_samples == len(EVALUATION_DATASET)
        assert report.security_block_rate_pct == 100.0  # 100% of prompt injections must be blocked
        assert report.decision_accuracy_pct >= 90.0     # Baseline decision accuracy
        assert report.intent_accuracy_pct >= 90.0       # Baseline intent accuracy
        assert report.avg_latency_ms > 0.0

        d = report.to_dict()
        assert d["schema_version"] == "1.0.0"
        assert "adversarial_blocked" in d
