# PK-OS Failure Mode Matrix

**Status**: SKELETON — Phase 0. Test implementations added per phase.
**Last updated**: 2026-10-16

Each failure mode must have a corresponding test or documented reproduction procedure before it can be marked TESTED.

---

## Legend

| Status | Meaning |
|---|---|
| PLANNED | Failure mode identified; test not yet written |
| PARTIAL | Some testing exists; full scenario not covered |
| TESTED | Deterministic test exists and passes |
| BLOCKED | Cannot test until a dependency is resolved |
| NOT APPLICABLE | Not relevant to the current architecture |

---

## Category 1 — Power Loss

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-PWR-001 | Power loss during update download | 4 | PLANNED | tests/update/ |
| F-PWR-002 | Power loss during update preparation | 4 | PLANNED | tests/update/ |
| F-PWR-003 | Power loss during update activation | 4 | PLANNED | tests/update/ |
| F-PWR-004 | Power loss during installation | 7 | PLANNED | tests/install/ |

---

## Category 2 — Storage

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-STR-001 | Insufficient disk space during update | 4 | PLANNED | tests/update/ |
| F-STR-002 | Full disk during installation | 7 | PLANNED | tests/install/ |
| F-STR-003 | Filesystem corruption after update | 4 | PLANNED | tests/update/ |
| F-STR-004 | Damaged OS image | 1 | PLANNED | tests/image/ |

---

## Category 3 — Update and Signing

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-UPD-001 | Corrupt update artifact | 4 | PLANNED | tests/update/ |
| F-UPD-002 | Invalid update signature | 4 | PLANNED | tests/update/ |
| F-UPD-003 | Expired update metadata | 4 | PLANNED | tests/update/ |
| F-UPD-004 | Malformed update metadata | 4 | PLANNED | tests/update/ |
| F-UPD-005 | Unauthorized downgrade attempt | 4 | PLANNED | tests/update/ |
| F-UPD-006 | Network interruption during download | 4 | PLANNED | tests/update/ |
| F-UPD-007 | Unavailable update server | 4 | PLANNED | tests/update/ |
| F-UPD-008 | Compromised distribution endpoint | 4 | PLANNED | tests/update/ |
| F-UPD-009 | Failed health check after activation | 4 | PLANNED | tests/update/ |
| F-UPD-010 | Rollback triggered | 4 | PLANNED | tests/update/ |

---

## Category 4 — Boot

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-BOOT-001 | Failed boot after update | 4 | PLANNED | tests/boot/ |
| F-BOOT-002 | Bootloader corruption | 7 | PLANNED | manual procedure |
| F-BOOT-003 | Missing firmware | 1 | PLANNED | tests/image/ |
| F-BOOT-004 | Incorrect system time affecting signature validation | 4 | PLANNED | tests/update/ |

---

## Category 5 — Hardware and Drivers

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-HW-001 | Unsupported GPU (no acceleration) | 2 | PLANNED | tests/shell/ |
| F-HW-002 | Missing sensors (no battery info) | 3 | PLANNED | tests/integration/ |
| F-HW-003 | Audio device unavailable | 3 | PLANNED | tests/integration/ |
| F-HW-004 | Network adapter unsupported | 3 | PLANNED | tests/integration/ |

---

## Category 6 — Service and Process

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-SVC-001 | System service crash loop | 5 | PLANNED | tests/services/ |
| F-SVC-002 | Desktop shell crash | 2 | PLANNED | tests/shell/ |
| F-SVC-003 | IPC message malformed or oversized | 3 | PLANNED | tests/ipc/ |
| F-SVC-004 | Resource exhaustion (memory, CPU, disk) | 6 | PLANNED | tests/reliability/ |

---

## Category 7 — Migration and Compatibility

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-MIG-001 | Failed data migration during update | 4 | PLANNED | tests/update/ |
| F-MIG-002 | Incompatible update (schema mismatch) | 4 | PLANNED | tests/update/ |
| F-MIG-003 | Permission revocation during update | 4 | PLANNED | tests/update/ |

---

## Category 8 — Security

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-SEC-001 | Shell attempts to bypass IPC authorization | 3 | PLANNED | tests/security/ |
| F-SEC-002 | Feature flag used to disable security control | 5 | PLANNED | tests/security/ |
| F-SEC-003 | Secret leaked in logs | 0 | PARTIAL | CI Gitleaks scan |
| F-SEC-004 | Unsigned update accepted | 4 | PLANNED | tests/update/ |

---

## Category 9 — AI Features (Phase 5+)

| ID | Failure Mode | Phase | Status | Test Location |
|---|---|---|---|---|
| F-AI-001 | AI provider unavailable | 5 | PLANNED | tests/ai/ |
| F-AI-002 | AI attempts system-changing action without authorization | 5 | PLANNED | tests/ai/ |
| F-AI-003 | Cloud inference attempted without user consent | 5 | PLANNED | tests/ai/ |

---

## Notes

- A failure mode without a TESTED status must not be claimed as handled in any release.
- Failure modes marked PLANNED must have tests before their target phase can pass its exit gate.
- This document is reviewed at every phase gate.
