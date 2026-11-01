#!/usr/bin/env python3
"""Optionally fine-tune a locally stored causal model with PEFT LoRA, fully offline."""

from __future__ import annotations

import argparse
import json
import math
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.src.local_training import (
    DEFAULT_DATASET,
    format_example,
    load_examples,
    split_examples,
    training_preflight,
)


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model-path", type=Path, required=True, help="Existing local causal model directory")
    parser.add_argument("--output-dir", type=Path, required=True, help="New directory for the LoRA adapter and report")
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET, help="Versioned JSONL prompt/response dataset")
    parser.add_argument("--epochs", type=float, default=1.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-length", type=int, default=384)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--validation-fraction", type=float, default=0.2)
    parser.add_argument("--validate-only", action="store_true", help="Validate and report split without ML dependencies")
    parser.add_argument(
        "--preflight-only",
        action="store_true",
        help="Report resources, local model/license, data readiness, and dependencies without training",
    )
    return parser.parse_args()


def validate_args(args: argparse.Namespace) -> None:
    if args.epochs <= 0 or args.max_length < 32 or args.learning_rate <= 0:
        raise ValueError("epochs, max-length, and learning-rate must be positive (max-length >= 32)")
    if not 0 < args.validation_fraction < 1:
        raise ValueError("validation-fraction must be between 0 and 1")
    if not args.model_path.is_dir() and not (args.validate_only or args.preflight_only):
        raise ValueError(f"Local model directory does not exist: {args.model_path}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"Output directory must be new or empty: {args.output_dir}")


def _save_report(path: Path, report: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(args: argparse.Namespace) -> Dict[str, Any]:
    validate_args(args)
    examples = load_examples(args.dataset)
    train_examples, validation_examples = split_examples(
        examples, args.validation_fraction, args.seed
    )
    report: Dict[str, Any] = {
        "schema_version": 1,
        "dataset": str(args.dataset),
        "dataset_examples": len(examples),
        "train_examples": len(train_examples),
        "validation_examples": len(validation_examples),
        "seed": args.seed,
        "model_path": str(args.model_path),
        "training_status": "not_started",
        "inference_status": "not_integrated",
    }
    if args.validate_only:
        report["training_status"] = "validation_only"
        return report

    preflight = training_preflight(args.model_path, args.output_dir, len(examples))
    report["preflight"] = preflight
    if args.preflight_only or not preflight["ready"]:
        report["training_status"] = "preflight_only" if args.preflight_only else "blocked_preflight"
        return report

    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["TRANSFORMERS_OFFLINE"] = "1"
    random.seed(args.seed)

    try:
        import torch
        from peft import LoraConfig, get_peft_model
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            DataCollatorForLanguageModeling,
            Trainer,
            TrainingArguments,
        )
        from datasets import Dataset
    except ImportError as exc:
        raise RuntimeError(
            "Optional local training dependencies are missing. Install intelligence/requirements-training.txt "
            "in a dedicated environment; no model or data will be downloaded by this script."
        ) from exc

    if preflight["selected_device"] == "cuda" and torch.cuda.is_available():
        device = "cuda"
    else:
        device = "cpu"
    random.seed(args.seed)
    torch.manual_seed(args.seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(args.seed)

    tokenizer = AutoTokenizer.from_pretrained(str(args.model_path), local_files_only=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        str(args.model_path),
        local_files_only=True,
        torch_dtype=torch.float32 if device == "cpu" else "auto",
    )
    model.config.use_cache = False
    model = get_peft_model(
        model,
        LoraConfig(
            r=8,
            lora_alpha=16,
            lora_dropout=0.05,
            bias="none",
            task_type="CAUSAL_LM",
            target_modules=["q_proj", "v_proj"],
        ),
    )

    def tokenize(batch: Dict[str, Any]) -> Dict[str, Any]:
        return tokenizer(
            [format_example(example) for example in batch["example"]],
            truncation=True,
            max_length=args.max_length,
        )

    train_data = Dataset.from_dict({"example": train_examples}).map(tokenize, batched=True)
    validation_data = Dataset.from_dict({"example": validation_examples}).map(tokenize, batched=True)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    training = TrainingArguments(
        output_dir=str(args.output_dir / "checkpoints"),
        num_train_epochs=args.epochs,
        learning_rate=args.learning_rate,
        per_device_train_batch_size=1,
        per_device_eval_batch_size=1,
        gradient_accumulation_steps=4,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        logging_strategy="epoch",
        report_to=[],
        seed=args.seed,
        data_seed=args.seed,
        use_cpu=device == "cpu",
        fp16=False,
    )
    trainer = Trainer(
        model=model,
        args=training,
        train_dataset=train_data,
        eval_dataset=validation_data,
        data_collator=DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=False),
    )
    trainer.train()
    model.save_pretrained(args.output_dir / "adapter")
    tokenizer.save_pretrained(args.output_dir / "adapter")
    evaluation = trainer.evaluate()
    eval_loss = float(evaluation["eval_loss"])
    report.update(
        {
            "training_status": "completed",
            "device": device,
            "epochs": args.epochs,
            "learning_rate": args.learning_rate,
            "max_length": args.max_length,
            "evaluation_loss": eval_loss,
            "evaluation_perplexity": math.exp(min(eval_loss, 80)),
            "adapter_path": str(args.output_dir / "adapter"),
            "inference_status": "adapter_saved_not_integrated",
        }
    )
    _save_report(args.output_dir / "training-report.json", report)
    return report


if __name__ == "__main__":
    try:
        result = run(_arguments())
    except (ValueError, RuntimeError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(result, indent=2, sort_keys=True))
    if result.get("training_status") == "blocked_preflight":
        sys.exit(2)
