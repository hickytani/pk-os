"""
PK-OS Permission & Safety Audit Ledger
Enforces capability checks, intercepts consequential tool calls,
and maintains an immutable cryptographic SHA-256 hash-chained audit trail.
"""

from typing import Dict, Any, Optional, List
import hashlib
import json
import time

from .interfaces import Capability, ToolResult


class PermissionDeniedError(Exception):
    pass


class ConsequentialApprovalRequired(Exception):
    def __init__(self, tool_name: str, params: Dict[str, Any], message: str):
        super().__init__(message)
        self.tool_name = tool_name
        self.params = params


class AuditEntry:
    def __init__(self,
                 index: int,
                 timestamp: float,
                 session_id: str,
                 tool_name: str,
                 params: Dict[str, Any],
                 capability: Capability,
                 approved: bool,
                 result: Optional[ToolResult],
                 previous_hash: str):
        self.index = index
        self.timestamp = timestamp
        self.session_id = session_id
        self.tool_name = tool_name
        self.params = params
        self.capability = capability.value
        self.approved = approved
        self.result = {
            "success": result.success if result else False,
            "error": result.error if result else None
        } if result else None
        self.previous_hash = previous_hash
        self.hash = self.compute_hash()

    def compute_hash(self) -> str:
        record = {
            "index": self.index,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "tool_name": self.tool_name,
            "params": self.params,
            "capability": self.capability,
            "approved": self.approved,
            "result": self.result,
            "previous_hash": self.previous_hash
        }
        raw = json.dumps(record, sort_keys=True).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()


class SecurityLedger:
    GENESIS_HASH = "0" * 64

    def __init__(self):
        self.chain: List[AuditEntry] = []
        self._pending_approvals: Dict[str, Dict[str, Any]] = {}

    def authorize_and_execute(self,
                               session_id: str,
                               tool_name: str,
                               capability: Capability,
                               params: Dict[str, Any],
                               execute_fn,
                               user_approval_granted: bool = False) -> ToolResult:
        """
        Gates execution behind capability checks.
        If capability is CONSEQUENTIAL, user_approval_granted MUST be True.
        """
        now = time.time()
        prev_hash = self.chain[-1].hash if self.chain else self.GENESIS_HASH

        # Capability enforcement
        if capability == Capability.CONSEQUENTIAL and not user_approval_granted:
            # Reject execution and raise approval interrupt
            entry = AuditEntry(
                index=len(self.chain),
                timestamp=now,
                session_id=session_id,
                tool_name=tool_name,
                params=params,
                capability=capability,
                approved=False,
                result=ToolResult(success=False, output=None, error="Awaiting user confirmation"),
                previous_hash=prev_hash
            )
            self.chain.append(entry)
            raise ConsequentialApprovalRequired(
                tool_name=tool_name,
                params=params,
                message=f"Action '{tool_name}' requires explicit user confirmation via Voice HUD modal."
            )

        # Execute
        result = execute_fn(params)

        entry = AuditEntry(
            index=len(self.chain),
            timestamp=now,
            session_id=session_id,
            tool_name=tool_name,
            params=params,
            capability=capability,
            approved=True,
            result=result,
            previous_hash=prev_hash
        )
        self.chain.append(entry)
        return result

    def verify_ledger_integrity(self) -> bool:
        """
        Validates the complete cryptographic hash chain.
        Detects any tampering or omitted history.
        """
        for i, entry in enumerate(self.chain):
            expected_prev = self.chain[i - 1].hash if i > 0 else self.GENESIS_HASH
            if entry.previous_hash != expected_prev:
                return False
            if entry.hash != entry.compute_hash():
                return False
        return True
