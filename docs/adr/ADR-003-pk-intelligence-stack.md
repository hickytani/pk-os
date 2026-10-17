# ADR-003: PK Intelligence Local-First Voice and Agent Architecture

## Status

Accepted

## Date

2026-10-17

## Context

Phase 5 and the parallel PK Intelligence workstream define the conversational and autonomous assistant system ("Hey PK") for PK-OS.
Key constraints:

1. **Local-First & Offline**: Must operate without mandatory internet connection, zero external API keys, zero paid cloud subscriptions.
2. **Resource Budget**: Host systems include entry-level laptops (e.g. 8–16 GB RAM, x86-64 CPU, no dedicated NVIDIA GPU required; CPU-quantized inference).
3. **Safety & Permission Ledger**: A language model must never have unrestricted shell access or arbitrary code execution capabilities. Every action must flow through a deterministic, typed, capability-checked tool registry with user approval gates for consequential operations.
4. **Privacy Invariants**: Audio capture is strictly local. Microphones are gated behind hardware/system indicators. Audio buffers are processed in memory and never stored or exfiltrated.

## Evaluated Options

### Option 1: Cloud-Based Agent Service (OpenAI / Anthropic / Google Cloud API)

- **Pros**: High reasoning capability, zero local compute overhead.
- **Cons**: Violates privacy invariants, breaks offline operation, incurs ongoing monetary cost, requires network connectivity.
- **Verdict**: Rejected.

### Option 2: Monolithic Desktop Assistant Script (Regex / Hardcoded Intent matching)

- **Pros**: Extremely low CPU/RAM usage.
- **Cons**: Inflexible, fragile natural language understanding, cannot handle complex compound user goals or ambiguous requests.
- **Verdict**: Rejected as a complete solution, though deterministic slot-filling is retained as a fast-path tier.

### Option 3: Tiered Hybrid Local Pipeline (VAD -> openWakeWord -> Whisper.cpp -> Local SLM / Grammar-Constrained Tool Planner)

- **Tier 1 (Audio Gating)**: Silero-VAD / WebRTC-VAD consumes <1% CPU continuously to detect voice activity.
- **Tier 2 (Wake-Word Detection)**: `openWakeWord` (Apache-2.0, ONNX-based, ultra-lightweight) activates only on acoustic detection of "Hey PK" without sending audio upstream.
- **Tier 3 (Local Speech-to-Text)**: `whisper.cpp` (`tiny.en` or `base.en` quantized to 4-bit) performs local transcription in ~150-300ms on CPU with zero cloud transmission.
- **Tier 4 (Intent Planning & Tool Selection)**: Quantized local small language model (SLM) such as Qwen2.5-Coder-1.5B-Instruct or SmolLM2-1.7B running via `llama.cpp` using GBNF grammar constraints to output strictly valid JSON conforming to the PK-OS Tool Registry schema.
- **Tier 5 (Permission & Execution)**: Typed tools executed with capability checks, sandboxing, and explicit user confirmation for consequential actions.
- **Verdict**: Accepted.

## Decision

PK-OS adopts the **Tiered Hybrid Local Pipeline**:

1. **Wake-Word**: `openWakeWord` engine with custom-trained or fine-tuned "Hey PK" acoustic model running via ONNX Runtime CPU.
2. **Speech Recognition**: Local `whisper.cpp` engine using 4-bit quantized models (`ggml-tiny.en-q5_1.bin` / `ggml-base.en-q5_1.bin`).
3. **Reasoning & Tool Invocation**: Local quantized SLM running under `llama.cpp` CPU execution, constrained by GBNF (Grammar-Based Normal Form) to enforce valid typed JSON tool requests.
4. **Safety & Tool Execution**: All OS modifications, application launches, settings adjustments, and file operations execute through a strictly typed `ToolRegistry` requiring explicit permission grants and writing immutable records to an audit ledger.

## Safety Invariants

1. **No Arbitrary Execution**: The model is provided only with allowlisted, typed tool schemas (`LaunchApplication`, `GetSystemStatus`, `AdjustSetting`, `SearchFiles`). Shell interpreters (`/bin/sh`, `/bin/bash`, `powershell`) are strictly prohibited as tool targets.
2. **Approval Gate**: Operations classified as `CONSEQUENTIAL` (file deletion, network modification, software installation, credential access) pause execution and require explicit user confirmation via the PK-OS Shell Voice HUD modal.
3. **Auditability**: Every invocation records a structured JSON audit log entry with timestamp, session ID, transcribed text, proposed tool call, parameters, permission status, and execution outcome.
