"""Offline dataset validation and deterministic splitting for optional local SFT."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_DATASET = Path(__file__).resolve().parents[1] / "data" / "v2" / "assistant-sft.jsonl"
DEFAULT_MANIFEST = DEFAULT_DATASET.with_name("manifest.json")
GIB = 1024 ** 3
MIN_TRAINING_EXAMPLES = 50


def load_examples(dataset_path: Path = DEFAULT_DATASET) -> List[Dict[str, str]]:
    """Load and validate prompt/response examples without third-party packages."""
    examples: List[Dict[str, str]] = []
    seen_ids = set()
    with dataset_path.open("r", encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{dataset_path}:{line_number}: invalid JSON: {exc}") from exc
            if not isinstance(record, dict):
                raise ValueError(f"{dataset_path}:{line_number}: expected a JSON object")
            for field in ("id", "topic", "prompt", "response"):
                value = record.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{dataset_path}:{line_number}: '{field}' must be non-empty text")
            if record["id"] in seen_ids:
                raise ValueError(f"{dataset_path}:{line_number}: duplicate id '{record['id']}'")
            seen_ids.add(record["id"])
            examples.append({field: record[field].strip() for field in ("id", "topic", "prompt", "response")})

    if len(examples) < 5:
        raise ValueError(f"Dataset must contain at least 5 examples; found {len(examples)}")
    return examples


def validate_dataset_bundle(manifest_path: Path = DEFAULT_MANIFEST) -> Dict[str, object]:
    """Validate provenance and integrity for the separate train and test files."""
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Cannot read dataset manifest '{manifest_path}': {exc}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != "2.0.0":
        raise ValueError("Dataset manifest schema_version must be '2.0.0'")

    provenance = manifest.get("provenance")
    if not isinstance(provenance, dict):
        raise ValueError("Dataset manifest is missing provenance metadata")
    for field in ("source", "license", "transformation_history", "external_sources"):
        if field not in provenance:
            raise ValueError(f"Dataset provenance '{field}' must be present")
        value = provenance[field]
        if field in ("source", "license") and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"Dataset provenance '{field}' must be non-empty text")
        if field in ("transformation_history", "external_sources") and not isinstance(value, list):
            raise ValueError(f"Dataset provenance '{field}' must be a list")
        if field == "transformation_history" and not value:
            raise ValueError("Dataset provenance 'transformation_history' must not be empty")

    root = manifest_path.parent
    file_records = manifest.get("files")
    if not isinstance(file_records, dict) or set(file_records) != {
        "assistant-sft.jsonl", "assistant-eval.jsonl"
    }:
        raise ValueError("Dataset manifest must declare the SFT and held-out evaluation files")

    loaded: Dict[str, List[Dict[str, str]]] = {}
    for filename, expected_role in (
        ("assistant-sft.jsonl", "training_source"),
        ("assistant-eval.jsonl", "held_out_test"),
    ):
        record = file_records[filename]
        if not isinstance(record, dict) or record.get("role") != expected_role:
            raise ValueError(f"Dataset file '{filename}' has an invalid split role")
        if Path(filename).name != filename:
            raise ValueError(f"Unsafe dataset filename in manifest: '{filename}'")
        path = root / filename
        examples = load_examples(path)
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        if actual_hash != str(record.get("sha256", "")).upper():
            raise ValueError(f"Dataset checksum mismatch for '{filename}'")
        if len(examples) != record.get("examples"):
            raise ValueError(f"Dataset example count mismatch for '{filename}'")
        loaded[filename] = examples

    split_policy = manifest.get("split_policy")
    if not isinstance(split_policy, dict) or split_policy.get("id_overlap_allowed") is not False:
        raise ValueError("Dataset manifest must prohibit train/test ID overlap")
    train_ids = {example["id"] for example in loaded["assistant-sft.jsonl"]}
    test_ids = {example["id"] for example in loaded["assistant-eval.jsonl"]}
    if train_ids & test_ids:
        raise ValueError("Dataset IDs overlap between training and held-out evaluation files")

    return {
        "schema_version": manifest["schema_version"],
        "training_examples": len(train_ids),
        "held_out_examples": len(test_ids),
        "provenance_license": provenance["license"],
        "id_overlap": 0,
        "checksums_valid": True,
    }


def assess_training_readiness(
    *,
    dataset_examples: int,
    model_size_bytes: int,
    available_ram_bytes: int | None,
    free_disk_bytes: int | None,
    license_present: bool,
    missing_dependencies: List[str],
    gpu_free_bytes: int | None = None,
) -> Dict[str, object]:
    """Apply conservative local fine-tuning gates without loading a model."""
    reasons: List[str] = []
    if dataset_examples < MIN_TRAINING_EXAMPLES:
        reasons.append(
            f"training source has {dataset_examples} examples; at least {MIN_TRAINING_EXAMPLES} are required"
        )
    if model_size_bytes <= 0:
        reasons.append("no local model weight files were found")
    if available_ram_bytes is None:
        reasons.append("available system RAM could not be measured")
    else:
        required_ram = max(4 * GIB, model_size_bytes * 2)
        if available_ram_bytes < required_ram:
            reasons.append(
                f"available RAM is below the conservative {required_ram // (1024 ** 2)} MiB minimum"
            )
    if free_disk_bytes is None:
        reasons.append("free disk space could not be measured")
    else:
        required_disk = 2 * GIB + model_size_bytes * 2
        if free_disk_bytes < required_disk:
            reasons.append(
                f"free disk space is below the {required_disk // (1024 ** 2)} MiB artifact minimum"
            )
    if not license_present:
        reasons.append("local model license evidence is missing")
    if missing_dependencies:
        reasons.append("missing training dependencies: " + ", ".join(missing_dependencies))

    use_gpu = gpu_free_bytes is not None and gpu_free_bytes >= max(2 * GIB, model_size_bytes * 2)
    return {
        "ready": not reasons,
        "selected_device": ("cuda" if use_gpu else "cpu") if not reasons else "blocked",
        "dataset_examples": dataset_examples,
        "model_size_bytes": model_size_bytes,
        "available_ram_bytes": available_ram_bytes,
        "gpu_free_bytes": gpu_free_bytes,
        "free_disk_bytes": free_disk_bytes,
        "license_present": license_present,
        "missing_dependencies": missing_dependencies,
        "reasons": reasons,
    }


def _available_ram_bytes() -> int | None:
    if hasattr(os, "sysconf"):
        try:
            return int(os.sysconf("SC_AVPHYS_PAGES") * os.sysconf("SC_PAGE_SIZE"))
        except (OSError, ValueError, TypeError):
            pass
    if os.name == "nt":
        try:
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return int(status.ullAvailPhys)
        except (AttributeError, OSError):
            pass
    return None


def _gpu_free_bytes() -> int | None:
    executable = shutil.which("nvidia-smi")
    if executable is None:
        return None
    try:
        result = subprocess.run(
            [executable, "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=5,
            check=True,
        )
        mib_values = [int(line.strip()) for line in result.stdout.splitlines() if line.strip()]
        return max(mib_values, default=0) * (1024 ** 2)
    except (OSError, subprocess.SubprocessError, ValueError):
        return None


def training_preflight(model_path: Path, output_dir: Path, dataset_examples: int) -> Dict[str, object]:
    """Probe local resources and license before optional ML imports or training."""
    model_path = Path(model_path)
    output_dir = Path(output_dir)
    weights = []
    if model_path.is_dir():
        for pattern in ("*.safetensors", "pytorch_model*.bin", "*.pt"):
            weights.extend(path for path in model_path.rglob(pattern) if path.is_file())
    model_size = sum(path.stat().st_size for path in weights)
    license_present = model_path.is_dir() and any(
        (model_path / name).is_file()
        for name in ("LICENSE", "LICENSE.txt", "LICENSE.md", "LICENSE-MODEL", "license")
    )
    probe_dir = output_dir if output_dir.exists() else output_dir.parent
    while not probe_dir.exists() and probe_dir != probe_dir.parent:
        probe_dir = probe_dir.parent
    try:
        free_disk = shutil.disk_usage(probe_dir).free
    except OSError:
        free_disk = None
    dependencies = ("torch", "transformers", "datasets", "peft")
    missing = [name for name in dependencies if importlib.util.find_spec(name) is None]
    report = assess_training_readiness(
        dataset_examples=dataset_examples,
        model_size_bytes=model_size,
        available_ram_bytes=_available_ram_bytes(),
        gpu_free_bytes=_gpu_free_bytes(),
        free_disk_bytes=free_disk,
        license_present=license_present,
        missing_dependencies=missing,
    )
    if not model_path.is_dir():
        report["ready"] = False
        report["selected_device"] = "blocked"
        report["reasons"].insert(0, "local model directory does not exist")
    report["model_path"] = str(model_path)
    report["output_path"] = str(output_dir)
    return report


def split_examples(
    examples: List[Dict[str, str]], validation_fraction: float = 0.2, seed: int = 42
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]]]:
    """Create a stable hash-based holdout split; identical IDs never leak across sets."""
    if not 0 < validation_fraction < 1:
        raise ValueError("validation_fraction must be between 0 and 1")
    if len(examples) < 2:
        raise ValueError("At least two examples are required for a train/validation split")

    threshold = int(validation_fraction * 10000)
    train: List[Dict[str, str]] = []
    validation: List[Dict[str, str]] = []
    for example in examples:
        digest = hashlib.sha256(f"{seed}:{example['id']}".encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:4], "big") % 10000
        (validation if bucket < threshold else train).append(example)
    if not train or not validation:
        ordered = sorted(
            examples,
            key=lambda item: hashlib.sha256(f"{seed}:{item['id']}".encode("utf-8")).digest(),
        )
        validation_count = max(1, round(len(ordered) * validation_fraction))
        validation_ids = {item["id"] for item in ordered[:validation_count]}
        validation = [item for item in examples if item["id"] in validation_ids]
        train = [item for item in examples if item["id"] not in validation_ids]
    return train, validation


def format_example(example: Dict[str, str]) -> str:
    """Format one local assistant example for causal language-model fine-tuning."""
    return f"### User:\n{example['prompt']}\n\n### PK Assistant:\n{example['response']}"
