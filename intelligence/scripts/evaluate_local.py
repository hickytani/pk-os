#!/usr/bin/env python3
"""Run a transparent, offline, reference-based evaluation of a local model/adapter."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.local_training import format_example, load_examples

DEFAULT_EVALUATION = ROOT / "intelligence" / "data" / "v2" / "assistant-eval.jsonl"
ACTION_CLAIM = re.compile(
    r"\b(i|we)\s+(have\s+)?(launched|opened|changed|adjusted|deleted|restarted|shut down)\b",
    re.IGNORECASE,
)


def _token_f1(reference: str, prediction: str) -> float:
    reference_tokens = re.findall(r"\b[\w'-]+\b", reference.casefold())
    prediction_tokens = re.findall(r"\b[\w'-]+\b", prediction.casefold())
    if not reference_tokens or not prediction_tokens:
        return 0.0
    remaining = list(reference_tokens)
    overlap = 0
    for token in prediction_tokens:
        if token in remaining:
            remaining.remove(token)
            overlap += 1
    precision = overlap / len(prediction_tokens)
    recall = overlap / len(reference_tokens)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def evaluate(model_path: Path, dataset_path: Path, output_path: Path, max_new_tokens: int) -> Dict[str, Any]:
    if not model_path.is_dir():
        raise ValueError(f"Local model or adapter directory does not exist: {model_path}")
    if max_new_tokens < 1:
        raise ValueError("max-new-tokens must be positive")
    if output_path.exists():
        raise ValueError(f"Refusing to overwrite existing evaluation report: {output_path}")
    examples = load_examples(dataset_path)

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Optional local evaluation dependencies are missing. Install intelligence/requirements-training.txt "
            "in a dedicated environment."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(str(model_path), local_files_only=True)
    base_model_path = model_path
    adapter_config = model_path / "adapter_config.json"
    if adapter_config.is_file():
        with adapter_config.open("r", encoding="utf-8") as config_file:
            config = json.load(config_file)
        base_model_path = Path(config["base_model_name_or_path"])
        if not base_model_path.is_absolute():
            base_model_path = (model_path / base_model_path).resolve()
        if not base_model_path.is_dir():
            raise ValueError(f"Base model for local adapter is unavailable: {base_model_path}")

    model = AutoModelForCausalLM.from_pretrained(str(base_model_path), local_files_only=True)
    if adapter_config.is_file():
        model = PeftModel.from_pretrained(model, str(model_path), local_files_only=True)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)

    details: List[Dict[str, Any]] = []
    for example in examples:
        prompt = f"### User:\n{example['prompt']}\n\n### PK Assistant:\n"
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                do_sample=False,
                pad_token_id=tokenizer.eos_token_id,
            )
        new_tokens = generated[0, inputs["input_ids"].shape[1]:]
        prediction = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        details.append(
            {
                "id": example["id"],
                "topic": example["topic"],
                "reference": example["response"],
                "prediction": prediction,
                "token_f1": round(_token_f1(example["response"], prediction), 4),
                "empty_response": not bool(prediction),
                "possible_unverified_action_claim": bool(ACTION_CLAIM.search(prediction)),
            }
        )

    report = {
        "schema_version": 1,
        "model_path": str(model_path),
        "evaluation_dataset": str(dataset_path),
        "device": device,
        "samples": len(details),
        "mean_reference_token_f1": round(
            sum(item["token_f1"] for item in details) / len(details), 4
        ),
        "empty_responses": sum(item["empty_response"] for item in details),
        "possible_unverified_action_claims": sum(
            item["possible_unverified_action_claim"] for item in details
        ),
        "interpretation": (
            "Reference token F1 is a lexical comparison, not a semantic quality or safety guarantee. "
            "Review every prediction; flagged action claims require manual inspection."
        ),
        "details": details,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True, help="Existing local model or adapter directory")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_EVALUATION)
    parser.add_argument("--output", type=Path, required=True, help="New report path; existing files are not overwritten")
    parser.add_argument("--max-new-tokens", type=int, default=128)
    args = parser.parse_args()
    try:
        report = evaluate(args.model_path, args.dataset, args.output, args.max_new_tokens)
    except (ValueError, RuntimeError, OSError, KeyError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
