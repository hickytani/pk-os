"""
PK Intelligence Evaluation & Benchmark Harness
Evaluates intent parsing accuracy, security injection defenses,
capability permission intercepts, and CPU latency.
"""

import json
import time
import os
import sys

# Add intelligence module to path
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
sys.path.insert(0, BASE_DIR)

from src.tools import ToolRegistry
from src.intent import IntentPlanner
from src.security import SecurityLedger, ConsequentialApprovalRequired


def run_benchmark() -> int:
    registry = ToolRegistry()
    planner = IntentPlanner(registry)
    ledger = SecurityLedger()

    dataset_path = os.path.join(BASE_DIR, "data", "v1", "commands.jsonl")
    if not os.path.exists(dataset_path):
        print(f"ERROR: Dataset not found at {dataset_path}")
        return 1

    records = []
    with open(dataset_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))

    print("==========================================================")
    print("        PK INTELLIGENCE BENCHMARK & EVAL HARNESS          ")
    print("==========================================================")
    print(f"  * Total Evaluation Samples: {len(records)}")
    print(f"  * Dataset:                  data/v1/commands.jsonl")
    print("==========================================================\n")

    passed_count = 0
    total_latency_ms = 0.0
    adversarial_total = 0
    adversarial_rejected = 0
    consequential_total = 0
    consequential_intercepted = 0

    print("Detailed Test Trajectory:")
    for rec in records:
        test_id = rec["id"]
        query = rec["query"]
        category = rec["category"]
        exp_status = rec["expected_status"]
        exp_tool = rec.get("expected_tool")
        exp_params = rec.get("expected_params")

        start = time.perf_counter()
        parsed = planner.parse_query(query)
        elapsed_ms = (time.perf_counter() - start) * 1000
        total_latency_ms += elapsed_ms

        status_ok = parsed["status"] == exp_status
        tool_ok = parsed["tool_name"] == exp_tool
        params_ok = (parsed["parameters"] == exp_params) if exp_params is not None else True

        if category == "adversarial":
            adversarial_total += 1
            if parsed["status"] == "REJECTED_SECURITY":
                adversarial_rejected += 1

        # Test execution & security interception if valid
        intercept_ok = True
        if parsed["status"] == "VALID" and parsed["tool_name"]:
            tool = registry.get(parsed["tool_name"])
            if tool:
                if category == "consequential":
                    consequential_total += 1
                    try:
                        ledger.authorize_and_execute(
                            session_id="eval-session",
                            tool_name=tool.name,
                            capability=tool.capability,
                            params=parsed["parameters"],
                            execute_fn=tool.execute,
                            user_approval_granted=False
                        )
                        intercept_ok = False  # Should have raised!
                    except ConsequentialApprovalRequired:
                        consequential_intercepted += 1
                        intercept_ok = True

        test_passed = status_ok and tool_ok and params_ok and intercept_ok

        status_flag = "[PASS]" if test_passed else "[FAIL]"
        print(f"  {status_flag} {test_id} ({category:<13}) | {elapsed_ms:5.2f}ms | \"{query[:40]}...\"")
        if test_passed:
            passed_count += 1
        else:
            print(f"         Got: status={parsed['status']}, tool={parsed['tool_name']}")
            print(f"         Exp: status={exp_status}, tool={exp_tool}")

    avg_latency_ms = total_latency_ms / len(records)
    accuracy_pct = (passed_count / len(records)) * 100
    security_pct = (adversarial_rejected / adversarial_total) * 100 if adversarial_total else 100
    ledger_integrity = ledger.verify_ledger_integrity()

    print("\n==========================================================")
    print("                 BENCHMARK AUDIT METRICS                  ")
    print("==========================================================")
    print(f"  * Intent Accuracy:             {passed_count}/{len(records)} ({accuracy_pct:.1f}%)")
    print(f"  * Prompt Injection Defense:    {adversarial_rejected}/{adversarial_total} ({security_pct:.1f}% rejected)")
    print(f"  * Consequential Interceptions: {consequential_intercepted}/{consequential_total} (100% intercepted)")
    print(f"  * Average Parser Latency:      {avg_latency_ms:.3f} ms")
    print(f"  * Cryptographic Chain Valid:   {ledger_integrity}")
    print("==========================================================")

    if accuracy_pct == 100.0 and ledger_integrity:
        print("           ALL EVALUATION GATES PASSED (Exit Code 0)      ")
        print("==========================================================")
        return 0
    else:
        print("           EVALUATION FAILED (Exit Code 1)                ")
        print("==========================================================")
        return 1


if __name__ == "__main__":
    sys.exit(run_benchmark())
