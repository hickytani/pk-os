"""Ensure intelligence verification never opens installed user state."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VERIFY_PATH = REPO_ROOT / "scripts" / "acceptance" / "verify_intelligence.py"
SPEC = importlib.util.spec_from_file_location("verify_intelligence", VERIFY_PATH)
assert SPEC and SPEC.loader
verify_intelligence = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = verify_intelligence
SPEC.loader.exec_module(verify_intelligence)


def test_verification_uses_only_caller_supplied_temporary_state(tmp_path, caplog):
    with patch.object(
        verify_intelligence,
        "ContextEngine",
        wraps=verify_intelligence.ContextEngine,
    ) as context_factory:
        report = verify_intelligence.run_verification(tmp_path)

    assert report["benchmark"]["total_samples"] == 14
    assert report["benchmark"]["adversarial_blocked"] == "2/2"
    assert report["dataset"]["checksums_valid"] is True
    assert context_factory.call_count == 1
    kwargs = context_factory.call_args.kwargs
    assert Path(kwargs["prefs_path"]).parent == tmp_path
    assert Path(kwargs["history_path"]).parent == tmp_path
    assert not any(record.levelname == "WARNING" for record in caplog.records)
    assert list(tmp_path.iterdir()) == []


def test_cli_prints_benchmark_and_dataset_report_without_state_warning(capsys, caplog):
    assert verify_intelligence.main() == 0
    output = capsys.readouterr()
    assert '"total_samples": 14' in output.out
    assert '"checksums_valid": true' in output.out
    assert output.err == ""
    assert not any(record.levelname == "WARNING" for record in caplog.records)
