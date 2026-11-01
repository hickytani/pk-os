"""Tests for offline assistant dataset preparation and evaluation helpers."""

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.local_training import (
    DEFAULT_DATASET,
    format_example,
    load_examples,
    split_examples,
    validate_dataset_bundle,
    assess_training_readiness,
)
from intelligence.scripts.evaluate_local import _token_f1


class TestLocalTrainingData(unittest.TestCase):
    def test_versioned_dataset_is_valid_and_splittable(self):
        examples = load_examples(DEFAULT_DATASET)
        self.assertGreaterEqual(len(examples), 50)
        train, validation = split_examples(examples, seed=17)
        self.assertTrue(train)
        self.assertTrue(validation)
        self.assertFalse({item["id"] for item in train} & {item["id"] for item in validation})
        self.assertEqual(
            [item["id"] for item in validation],
            [item["id"] for item in split_examples(examples, seed=17)[1]],
        )

    def test_fixed_evaluation_set_does_not_overlap_training_ids(self):
        eval_path = ROOT / "intelligence" / "data" / "v2" / "assistant-eval.jsonl"
        train_ids = {item["id"] for item in load_examples(DEFAULT_DATASET)}
        eval_examples = load_examples(eval_path)
        self.assertEqual(len(eval_examples), 24)
        self.assertFalse(train_ids & {item["id"] for item in eval_examples})

    def test_manifest_provenance_counts_checksums_and_splits(self):
        report = validate_dataset_bundle()
        self.assertEqual(report["training_examples"], 60)
        self.assertEqual(report["held_out_examples"], 24)
        self.assertEqual(report["id_overlap"], 0)
        self.assertTrue(report["checksums_valid"])

    def test_training_preflight_blocks_low_resources_and_small_data(self):
        report = assess_training_readiness(
            dataset_examples=20,
            model_size_bytes=1024,
            available_ram_bytes=1024 ** 3,
            free_disk_bytes=10 * 1024 ** 3,
            license_present=False,
            missing_dependencies=["torch"],
            gpu_free_bytes=6 * 1024 ** 3,
        )
        self.assertFalse(report["ready"])
        self.assertEqual(report["selected_device"], "blocked")
        self.assertEqual(len(report["reasons"]), 4)

    def test_training_preflight_accepts_measured_sufficient_cpu_resources(self):
        report = assess_training_readiness(
            dataset_examples=50,
            model_size_bytes=1024 ** 2,
            available_ram_bytes=8 * 1024 ** 3,
            free_disk_bytes=10 * 1024 ** 3,
            license_present=True,
            missing_dependencies=[],
        )
        self.assertTrue(report["ready"])
        self.assertEqual(report["selected_device"], "cpu")

    def test_duplicate_ids_are_rejected(self):
        duplicate = {"id": "same", "topic": "test", "prompt": "one", "response": "answer"}
        with tempfile.TemporaryDirectory() as temp_dir:
            dataset = Path(temp_dir) / "duplicate.jsonl"
            dataset.write_text(
                "\n".join(json.dumps(duplicate) for _ in range(5)),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate id"):
                load_examples(dataset)

    def test_prompt_format_and_reference_f1(self):
        example = {"id": "one", "topic": "test", "prompt": "Question?", "response": "Good answer."}
        self.assertEqual(
            format_example(example),
            "### User:\nQuestion?\n\n### PK Assistant:\nGood answer.",
        )
        self.assertEqual(_token_f1("one two", "one two"), 1.0)
        self.assertEqual(_token_f1("one two", "three"), 0.0)

    def test_invalid_split_fraction_is_rejected(self):
        with self.assertRaises(ValueError):
            split_examples(load_examples(DEFAULT_DATASET), validation_fraction=1.0)


if __name__ == "__main__":
    unittest.main()
