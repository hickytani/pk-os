# PK Intelligence / "Hey PK" System Specification

## 1. Overview & Vision

PK Intelligence is the privacy-preserving, local-first agent system for PK-OS. A user can interact via voice or text ("Hey PK, launch terminal and check disk usage"), triggering offline acoustic detection, speech recognition, intent planning, capability authorization, deterministic tool execution, and auditory response.

## 2. Pipeline Architecture

```text
                      +-----------------------------+
                      | Hardware Audio Input (Mic)  |
                      +--------------+--------------+
                                     | Raw PCM Audio Stream (16kHz mono)
                                     v
                      +-----------------------------+
                      | Silero-VAD Voice Activity   |
                      | Gating (<1% CPU idle)       |
                      +--------------+--------------+
                                     | Voice chunks detected
                                     v
                      +-----------------------------+
                      | openWakeWord Engine         |
                      | "Hey PK" Model (ONNX CPU)   |
                      +--------------+--------------+
                                     | Wake trigger confirmed
                                     v
                      +-----------------------------+
                      | whisper.cpp Speech-to-Text  |
                      | (4-bit Quantized CPU)       |
                      +--------------+--------------+
                                     | Transcribed text query
                                     v
                      +-----------------------------+
                      | Intent Planner & Grammar    |
                      | llama.cpp (GBNF JSON schema)|
                      +--------------+--------------+
                                     | Structured Task Request
                                     v
                      +-----------------------------+
                      | Permission Ledger & Gate    |
                      | - Check Capability Matrix   |
                      | - User Approval for Actions |
                      +--------------+--------------+
                                     | Approved Tool Call
                                     v
                      +-----------------------------+
                      | Deterministic Tool Registry |
                      | (LaunchApp, SystemStatus,   |
                      |  AdjustSetting, Search)     |
                      +--------------+--------------+
                                     | Execution Outcome
                                     v
                      +-----------------------------+
                      | Piper TTS / Voice HUD Reply |
                      +-----------------------------+
```

## 3. Tool Safety Contract

Every tool in the PK Intelligence registry adheres to a strict formal contract:

1. **Typed Parameter Schema**: Parameters are validated against explicit JSON schemas before execution. Any type mismatch or extra field triggers an immediate rejection.
2. **Capability Scopes**: Tools declare required capability flags (`READ_ONLY`, `CONSEQUENTIAL`, `SYSTEM_CONFIG`, `FILE_WRITE`).
3. **Approval Intercept**: If any tool declares `CONSEQUENTIAL` or `SYSTEM_CONFIG`, execution pauses and sends an interactive approval request to the Shell Voice HUD.
4. **Timeout & Resource Bounds**: Every tool has a hard maximum execution time (default: 5.0 seconds). If exceeded, the process is killed and the transaction logged as aborted.
5. **No Shell Injections**: Raw shell command execution (`sh -c`, `bash -c`, `powershell`) is strictly prohibited. All actions use deterministic system calls or typed IPC.
6. **Immutable Audit Ledger**: Every invocation records a cryptographically hashed log entry containing the timestamp, session ID, tool name, input parameters, approval state, and result status.

## 4. Benchmark & Evaluation Plan

To ensure zero-cost reproducibility and prevent performance degradation:

- **Latency Budgets**:
  - Wake-Word Activation: `< 80 ms` on modern x86 CPU.
  - Speech-to-Text (10-word command): `< 400 ms` on 4 CPU threads.
  - Intent Parsing & Schema Generation: `< 500 ms`.
  - Total Round-Trip: `< 1,200 ms` from end-of-speech to tool dispatch.
- **Accuracy Metrics**:
  - Wake-word false accept rate: `< 1 per 24 hours` of background speech.
  - Intent slot-filling exact match: `> 95%` on evaluation dataset.
