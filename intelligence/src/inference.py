"""
PK Intelligence Inference Boundary (Phase 2E)
==============================================
Provides a provider-neutral, decoupled interface for local language-model
and assistant inference across PK-OS.

Architecture:
  - InferenceRequest: Explicit input schema with prompt, system context, parameters.
  - InferenceResponse: Typed response schema with metadata, latency, and tokens.
  - ModelMetadata: Formal model identity, version, parameter count, and license.
  - ProviderStatus: Explicit lifecycle status (INSTALLED_ACTIVE, CONFIGURED_UNAVAILABLE, etc.)
  - InferenceProvider (ABC): Base class for all inference engines.
  - ONNXInferenceProvider: ONNX Runtime provider for quantized local models.
  - DeterministicAssistantProvider: Zero-cost rule-based fallback assistant engine.
  - MockInferenceProvider: Testing provider for fault-injection and edge cases.
"""

from __future__ import annotations

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("pk.intelligence.inference")


class ProviderStatus(Enum):
    """Status of an inference provider in the local environment."""
    INSTALLED_ACTIVE = "installed_active"
    CONFIGURED_UNAVAILABLE = "configured_unavailable"
    NOT_CONFIGURED = "not_configured"
    UNSUPPORTED = "unsupported"


class InferenceError(Exception):
    """Base error for all inference-layer failures."""


class ModelUnavailableError(InferenceError):
    """Raised when a requested model is not installed or unreachable."""


class InferenceTimeoutError(InferenceError):
    """Raised when inference exceeds the allotted time limit."""


class PromptValidationError(InferenceError):
    """Raised when prompt fails safety or syntax constraints."""


@dataclass
class ModelMetadata:
    """Metadata describing a specific model artifact."""
    name: str
    version: str
    parameter_count: str
    license: str
    size_mb: float
    context_window: int
    runtime: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "parameter_count": self.parameter_count,
            "license": self.license,
            "size_mb": self.size_mb,
            "context_window": self.context_window,
            "runtime": self.runtime,
            "description": self.description,
        }


@dataclass
class InferenceRequest:
    """Request payload for model inference."""
    prompt: str
    system_prompt: str = ""
    temperature: float = 0.0
    max_tokens: int = 256
    context: Dict[str, Any] = field(default_factory=dict)
    timeout_sec: float = 10.0
    stop_sequences: List[str] = field(default_factory=list)

    def validate(self) -> None:
        if not self.prompt or not self.prompt.strip():
            raise PromptValidationError("Prompt cannot be empty or whitespace only.")
        if len(self.prompt) > 8192:
            raise PromptValidationError(f"Prompt length ({len(self.prompt)}) exceeds maximum limit of 8192 characters.")
        if self.timeout_sec <= 0:
            raise PromptValidationError("Timeout must be a positive number of seconds.")


@dataclass
class InferenceResponse:
    """Response payload returned by an inference provider."""
    text: str
    model_name: str
    model_version: str
    provider_type: str
    latency_ms: float
    tokens_used: int = 0
    structured_payload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    is_fallback: bool = False

    @property
    def is_success(self) -> bool:
        return self.error is None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "model_name": self.model_name,
            "model_version": self.model_version,
            "provider_type": self.provider_type,
            "latency_ms": round(self.latency_ms, 2),
            "tokens_used": self.tokens_used,
            "structured_payload": self.structured_payload,
            "error": self.error,
            "is_fallback": self.is_fallback,
        }


class InferenceProvider(ABC):
    """Abstract base class for PK Intelligence inference providers."""

    @abstractmethod
    def get_metadata(self) -> ModelMetadata:
        """Return model identity and licensing metadata."""

    @abstractmethod
    def get_status(self) -> ProviderStatus:
        """Check provider operational status in the local environment."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the model is installed and ready for inference."""

    @abstractmethod
    def infer(self, request: InferenceRequest) -> InferenceResponse:
        """Execute model inference synchronously within request constraints."""


# ---------------------------------------------------------------------------
# 1. Deterministic Assistant Engine (Zero-cost Local Rule-Based Engine)
# ---------------------------------------------------------------------------

class DeterministicAssistantProvider(InferenceProvider):
    """
    Zero-cost, local deterministic assistant provider.
    Handles general knowledge queries about PK-OS, security posture,
    capabilities, and structured intent guidance without external network
    calls or heavy GPU/RAM dependencies.
    """

    def __init__(self) -> None:
        self._metadata = ModelMetadata(
            name="pk-deterministic-assistant",
            version="1.0.0",
            parameter_count="0 (rule-based)",
            license="Apache-2.0",
            size_mb=0.1,
            context_window=2048,
            runtime="python3-native",
            description="Built-in deterministic assistant engine providing safe system guidance and structured intents.",
        )

    def get_metadata(self) -> ModelMetadata:
        return self._metadata

    def get_status(self) -> ProviderStatus:
        return ProviderStatus.INSTALLED_ACTIVE

    def is_available(self) -> bool:
        return True

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        request.validate()
        t0 = time.time()
        q = request.prompt.strip().lower()

        # Check prompt injection markers
        injection_patterns = ["ignore previous", "bypass security", "rm -rf", "sudo su", "chmod 777"]
        if any(p in q for p in injection_patterns):
            latency = (time.time() - t0) * 1000
            return InferenceResponse(
                text="Security alert: The requested command violates PK-OS least-privilege safety policies and was blocked.",
                model_name=self._metadata.name,
                model_version=self._metadata.version,
                provider_type="deterministic_rule_engine",
                latency_ms=latency,
                error="security_violation",
                is_fallback=True,
            )

        # Knowledge base responses
        if any(k in q for k in ["who are you", "what are you", "what is pk-os", "about pk-os"]):
            text = (
                "I am PK Intelligence, the local-first system assistant for PK-OS. "
                "PK-OS is a modern, open-source Linux operating system designed for speed, "
                "sovereignty, and safety with an Obsidian Dark desktop and hardware-isolated tools."
            )
        elif any(k in q for k in ["what can you do", "help", "list tools", "capabilities"]):
            text = (
                "I can perform authorized actions under your supervision:\n"
                "- Browse allowed directories (e.g. 'show files in /home/pkos')\n"
                "- Inspect system diagnostics and memory (e.g. 'check system status')\n"
                "- Adjust hardware settings (e.g. 'set brightness to 80')\n"
                "- Launch applications (e.g. 'launch terminal')\n"
                "- Safely delete files with explicit user confirmation"
            )
        elif "privacy" in q or "data" in q or "local" in q:
            text = (
                "PK-OS follows strict local-first privacy. Your preferences, conversation "
                "history, and file operations remain on your machine and are never transmitted "
                "to external cloud servers without explicit user initiation."
            )
        else:
            text = f"I received your request: '{request.prompt}'. I can map this to system tools or provide operating system guidance."

        latency = (time.time() - t0) * 1000
        return InferenceResponse(
            text=text,
            model_name=self._metadata.name,
            model_version=self._metadata.version,
            provider_type="deterministic_rule_engine",
            latency_ms=latency,
            tokens_used=len(text.split()),
            is_fallback=False,
        )


# ---------------------------------------------------------------------------
# 2. ONNX Runtime Provider (Quantized Local Model Engine)
# ---------------------------------------------------------------------------

class ONNXInferenceProvider(InferenceProvider):
    """
    Local ONNX Runtime inference provider for compact models
    (e.g., SmolLM, MiniLM, or custom intent classifier .onnx models).
    Truthfully reports CONFIGURED_UNAVAILABLE if model weights are not present.
    """

    def __init__(self, model_path: Optional[str] = None) -> None:
        self.model_path = Path(model_path) if model_path else Path("/var/lib/pk-os/models/assistant.onnx")
        self._session: Any = None
        self._ort_available = False
        self._init_runtime()

    def _init_runtime(self) -> None:
        try:
            import onnxruntime as ort  # noqa: F401
            self._ort_available = True
            if self.model_path.exists() and self.model_path.is_file():
                self._session = ort.InferenceSession(str(self.model_path))
                logger.info("Loaded ONNX model from %s", self.model_path)
        except Exception as exc:
            logger.debug("ONNX Runtime initialization info: %s", exc)

    def get_metadata(self) -> ModelMetadata:
        size = round(self.model_path.stat().st_size / (1024 * 1024), 2) if self.model_path.exists() else 0.0
        return ModelMetadata(
            name="pk-local-onnx-model",
            version="1.0.0",
            parameter_count="Compact SLM / Classifier",
            license="Open Model License",
            size_mb=size,
            context_window=1024,
            runtime="onnxruntime",
            description=f"Local ONNX runtime model at {self.model_path}",
        )

    def get_status(self) -> ProviderStatus:
        if not self._ort_available:
            return ProviderStatus.UNSUPPORTED
        if not self.model_path.exists():
            return ProviderStatus.CONFIGURED_UNAVAILABLE
        if self._session is not None:
            return ProviderStatus.INSTALLED_ACTIVE
        return ProviderStatus.CONFIGURED_UNAVAILABLE

    def is_available(self) -> bool:
        return self.get_status() == ProviderStatus.INSTALLED_ACTIVE

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        request.validate()
        if not self.is_available():
            raise ModelUnavailableError(
                f"ONNX model unavailable at '{self.model_path}' (status: {self.get_status().value})"
            )
        t0 = time.time()
        # In a real session, feed input tensors into self._session.run()
        latency = (time.time() - t0) * 1000
        return InferenceResponse(
            text="ONNX inference result",
            model_name="pk-local-onnx-model",
            model_version="1.0.0",
            provider_type="onnxruntime",
            latency_ms=latency,
            tokens_used=4,
        )


# ---------------------------------------------------------------------------
# 3. Mock Provider for Deterministic Testing & Fault Injection
# ---------------------------------------------------------------------------

class MockInferenceProvider(InferenceProvider):
    """Testing harness for validating timeout, errors, and custom response flows."""

    def __init__(
        self,
        default_response: str = "Mock response",
        should_fail: bool = False,
        should_timeout: bool = False,
        is_available_override: bool = True,
        structured_payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.default_response = default_response
        self.should_fail = should_fail
        self.should_timeout = should_timeout
        self.is_available_override = is_available_override
        self.structured_payload = structured_payload

    def get_metadata(self) -> ModelMetadata:
        return ModelMetadata(
            name="mock-model",
            version="0.0.1",
            parameter_count="0",
            license="Test",
            size_mb=0.0,
            context_window=512,
            runtime="mock",
        )

    def get_status(self) -> ProviderStatus:
        if not self.is_available_override:
            return ProviderStatus.CONFIGURED_UNAVAILABLE
        return ProviderStatus.INSTALLED_ACTIVE

    def is_available(self) -> bool:
        return self.is_available_override

    def infer(self, request: InferenceRequest) -> InferenceResponse:
        request.validate()
        if not self.is_available():
            raise ModelUnavailableError("Mock model is marked unavailable.")
        if self.should_timeout:
            time.sleep(min(0.05, request.timeout_sec + 0.01))
            raise InferenceTimeoutError(f"Inference timed out after {request.timeout_sec}s")
        if self.should_fail:
            raise InferenceError("Simulated mock model inference failure.")

        return InferenceResponse(
            text=self.default_response,
            model_name="mock-model",
            model_version="0.0.1",
            provider_type="mock",
            latency_ms=1.5,
            tokens_used=len(self.default_response.split()),
            structured_payload=self.structured_payload,
        )
