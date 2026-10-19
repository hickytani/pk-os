"""
PK Intelligence Orchestration Layer (Phase 2E)
==============================================
Provides end-to-end orchestration connecting:
  User Request -> Input Validation -> Context Retrieval -> Inference Decision
  -> Policy & Ledger Enforcement -> Typed Tool Execution -> Truthful Verified Response
  -> Context Persistence.

Guarantees:
  - Structured response schema (Conversational, Tool, Confirmation Required, Unsupported, Error).
  - Explicit rejection of unauthorized or malformed tool requests.
  - No synthetic success when underlying tools fail.
  - Direct integration with SecurityLedger and ContextEngine.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from intelligence.src.context import ContextEngine
from intelligence.src.inference import (
    DeterministicAssistantProvider,
    InferenceError,
    InferenceProvider,
    InferenceRequest,
    PromptValidationError,
)
from intelligence.src.intent import IntentPlanner
from intelligence.src.security import ConsequentialApprovalRequired, SecurityLedger
from intelligence.src.tools import ToolInterface, ToolRegistry

logger = logging.getLogger("pk.intelligence.orchestration")


class DecisionType(Enum):
    """Classification of the assistant's decision."""
    CONVERSATIONAL = "conversational"
    TOOL_EXECUTION = "tool_execution"
    CONFIRMATION_REQUIRED = "confirmation_required"
    UNSUPPORTED = "unsupported"
    ERROR = "error"


@dataclass
class OrchestrationResponse:
    """Standardized response schema returned to clients and desktop UI."""
    ok: bool
    decision_type: DecisionType
    response_text: str
    tool_name: Optional[str] = None
    tool_params: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    model_used: str = ""
    latency_ms: float = 0.0
    requires_approval: bool = False
    context_augmented: bool = False
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "decision_type": self.decision_type.value,
            "response_text": self.response_text,
            "tool_name": self.tool_name,
            "tool_params": self.tool_params,
            "tool_result": self.tool_result,
            "model_used": self.model_used,
            "latency_ms": round(self.latency_ms, 2),
            "requires_approval": self.requires_approval,
            "context_augmented": self.context_augmented,
            "error": self.error,
        }


class PKIntelligenceOrchestrator:
    """
    Central orchestration engine for PK Intelligence.
    Coordinates local inference, context engine, intent planning,
    security policy gates, and typed tool execution.
    """

    def __init__(
        self,
        inference_provider: Optional[InferenceProvider] = None,
        tool_registry: Optional[ToolRegistry] = None,
        security_ledger: Optional[SecurityLedger] = None,
        context_engine: Optional[ContextEngine] = None,
        intent_planner: Optional[IntentPlanner] = None,
    ) -> None:
        self.inference = inference_provider or DeterministicAssistantProvider()
        self.tools = tool_registry or ToolRegistry()
        self.ledger = security_ledger or SecurityLedger()
        self.context = context_engine or ContextEngine()
        self.planner = intent_planner or IntentPlanner(self.tools)

    def process_query(
        self,
        query: str,
        user_approved: bool = False,
        session_id: str = "desktop-user",
    ) -> OrchestrationResponse:
        """
        Execute the full end-to-end request pipeline.
        """
        t0 = time.time()

        # Step 1: Input Validation
        cleaned = query.strip() if query else ""
        if not cleaned:
            return OrchestrationResponse(
                ok=False,
                decision_type=DecisionType.ERROR,
                response_text="Query cannot be empty.",
                error="empty_query",
                latency_ms=(time.time() - t0) * 1000,
            )

        # Step 2: Context Retrieval
        context_summary = self.context.get_context_summary()

        # Step 3: Intent Analysis & Policy Pre-screening
        planned = self.planner.parse_query(cleaned)
        plan_status = planned.get("status")

        # Security check: prompt injection / privilege escalation
        if plan_status == "REJECTED_SECURITY":
            self.context.record_query(cleaned, intent="security_blocked", success=False)
            latency = (time.time() - t0) * 1000
            return OrchestrationResponse(
                ok=False,
                decision_type=DecisionType.ERROR,
                response_text=f"Security alert: {planned.get('explanation')}",
                error="security_violation",
                latency_ms=latency,
            )

        # Step 4: Tool Execution Path (if unambiguous tool intent identified)
        tool_name = planned.get("tool_name")
        if tool_name and plan_status != "AMBIGUOUS":
            tool = self.tools.get(tool_name)
            if not tool:
                latency = (time.time() - t0) * 1000
                return OrchestrationResponse(
                    ok=False,
                    decision_type=DecisionType.ERROR,
                    response_text=f"Tool '{tool_name}' is not registered in the system registry.",
                    error="unregistered_tool",
                    latency_ms=latency,
                )

            params = planned.get("parameters") or {}

            # Execute via SecurityLedger
            try:
                tool_output = self.ledger.authorize_and_execute(
                    session_id=session_id,
                    tool_name=tool.name,
                    capability=tool.capability,
                    params=params,
                    execute_fn=tool.execute,
                    user_approval_granted=user_approved,
                )

                if not tool_output.success:
                    self.context.record_query(cleaned, intent=tool_name, success=False)
                    latency = (time.time() - t0) * 1000
                    return OrchestrationResponse(
                        ok=False,
                        decision_type=DecisionType.ERROR,
                        response_text=f"Tool '{tool_name}' failed: {tool_output.error}",
                        tool_name=tool_name,
                        tool_params=params,
                        tool_result={"success": False, "error": tool_output.error},
                        error=tool_output.error,
                        latency_ms=latency,
                    )

                output_dict = tool_output.output if isinstance(tool_output.output, dict) else {"output": tool_output.output}
                response_text = self._format_tool_response(tool_name, params, output_dict)
                self.context.record_query(cleaned, intent=tool_name, success=True)
                latency = (time.time() - t0) * 1000

                return OrchestrationResponse(
                    ok=True,
                    decision_type=DecisionType.TOOL_EXECUTION,
                    response_text=response_text,
                    tool_name=tool_name,
                    tool_params=params,
                    tool_result=output_dict,
                    model_used=self.inference.get_metadata().name,
                    latency_ms=latency,
                    context_augmented=True,
                )

            except ConsequentialApprovalRequired as exc:
                latency = (time.time() - t0) * 1000
                return OrchestrationResponse(
                    ok=False,
                    decision_type=DecisionType.CONFIRMATION_REQUIRED,
                    response_text=(
                        f"Action '{tool_name}' requires explicit user confirmation: {str(exc)}"
                    ),
                    tool_name=tool_name,
                    tool_params=params,
                    requires_approval=True,
                    error="approval_required",
                    latency_ms=latency,
                )

            except Exception as exc:
                self.context.record_query(cleaned, intent=tool_name, success=False)
                latency = (time.time() - t0) * 1000
                return OrchestrationResponse(
                    ok=False,
                    decision_type=DecisionType.ERROR,
                    response_text=f"Tool '{tool_name}' execution failed: {exc}",
                    tool_name=tool_name,
                    tool_params=params,
                    error=str(exc),
                    latency_ms=latency,
                )

        # Step 5: Conversational / General Intelligence Path
        # When no tool is mapped, dispatch to the local inference provider
        try:
            req = InferenceRequest(
                prompt=cleaned,
                context=context_summary,
                timeout_sec=5.0,
            )
            inf_resp = self.inference.infer(req)

            self.context.record_query(cleaned, intent="conversational", success=inf_resp.is_success)
            latency = (time.time() - t0) * 1000

            return OrchestrationResponse(
                ok=inf_resp.is_success,
                decision_type=DecisionType.CONVERSATIONAL if inf_resp.is_success else DecisionType.ERROR,
                response_text=inf_resp.text,
                model_used=inf_resp.model_name,
                latency_ms=latency,
                error=inf_resp.error,
                context_augmented=True,
            )
        except Exception as exc:
            latency = (time.time() - t0) * 1000
            return OrchestrationResponse(
                ok=False,
                decision_type=DecisionType.ERROR,
                response_text=f"Inference error: {exc}",
                error=str(exc),
                latency_ms=latency,
            )

    def _format_tool_response(
        self,
        tool_name: str,
        params: Dict[str, Any],
        output: Dict[str, Any],
    ) -> str:
        """Construct truthful, verified textual explanation of tool output."""
        if tool_name == "list_directory":
            path = output.get("path", params.get("path", ""))
            entries = output.get("entries", [])
            total = output.get("total_count", len(entries))
            if not entries:
                return f"Directory '{path}' is empty."
            lines = [f"Found {total} item(s) in '{path}':"]
            for e in entries[:20]:
                is_dir = bool(e.get("is_dir") or e.get("type") == "directory")
                icon = "📁" if is_dir else "📄"
                size = f" ({e.get('size_bytes', 0)} bytes)" if not is_dir else ""
                lines.append(f"  {icon} {e.get('name')}{size}")
            if total > 20:
                lines.append(f"  ... and {total - 20} more items.")
            return "\n".join(lines)

        elif tool_name == "get_system_status":
            mem_free = output.get("memory_free_mb", 0)
            mem_tot = output.get("memory_total_mb", 0)
            uptime = output.get("uptime_seconds", 0)
            disk = output.get("disk_available_gb", 0)
            return (
                f"System Diagnostics:\n"
                f"- Uptime: {uptime:.0f}s\n"
                f"- Memory: Free {mem_free}MB / Total {mem_tot}MB\n"
                f"- Disk Available: {disk}GB\n"
                f"- OS: {output.get('os_name', 'PK-OS')} {output.get('version', '')}"
            )

        elif tool_name == "adjust_setting":
            setting = params.get("key", params.get("setting", "setting"))
            val = params.get("value", "")
            return f"Adjusted {setting} to {val}. Status: {output.get('status', 'ok')}"

        elif tool_name == "launch_application":
            app = params.get("app_id", "application")
            return f"Application '{app}' dispatched successfully (PID {output.get('pid', 'mock')})."

        elif tool_name == "delete_path":
            path = output.get("deleted_path", params.get("target_path", ""))
            return f"Path '{path}' successfully removed."

        return f"Tool '{tool_name}' executed: {output}"
