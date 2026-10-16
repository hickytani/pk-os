# PK-OS Threat Model

**Status**: SKELETON — Phase 0. Expanded in Phase 3 and 6.
**Last updated**: 2026-10-16

---

## Scope

This document covers the threat model for PK-OS at the system level.
Individual subsystem threat models (update mechanism, shell IPC, AI features) are addressed in their respective documentation.

## Assets

| Asset | Sensitivity | Notes |
|---|---|---|
| User data and files | High | Must survive updates; must not be wiped by rollback |
| Signing keys | Critical | Compromise enables malicious update delivery |
| System integrity | High | OS must not be modifiable without user consent |
| User credentials | High | Must not be exposed to shell or third-party apps |
| Update metadata | High | Tampering enables downgrade or rogue update |
| Kernel and bootloader | Critical | Compromise of boot chain defeats all other controls |
| Shell IPC messages | Medium | Malformed messages must not gain privilege |
| Feature flag state | Low-Medium | Flags must not bypass mandatory security controls |

## Trust Boundaries

```text
[External Network]
      |
      | (HTTPS + signature verification)
      v
[Update Server / Release CDN]
      |
      | (signed metadata + artifact)
      v
[Update Service — runs with limited privilege]
      |
      | (D-Bus or narrow IPC)
      v
[System Service Layer — runs with minimum required privilege]
      |
      | (IPC, validated messages)
      v
[Desktop Shell — runs as user, NO unrestricted root]
      |
      | (Wayland protocol)
      v
[Applications — sandboxed, isolated]
```text

## Threat Categories

### T1 — Malicious or Compromised Update

- **Threat**: Attacker delivers a modified OS image via the update channel.
- **Mitigation**: Cryptographic signature verification of all update artifacts before activation. Trust anchor pinned in the bootloader or OS image. Rollback on failed health check.
- **Status**: NOT IMPLEMENTED (Phase 4)

### T2 — Privilege Escalation via Shell

- **Threat**: The desktop shell exploits a misconfigured system service to gain root access.
- **Mitigation**: Shell runs as unprivileged user. System services expose only narrow, validated IPC interfaces. No unrestricted sudo from the UI layer.
- **Status**: DESIGN REQUIREMENT — must be verified in Phase 3

### T3 — Malicious Application Escaping Sandbox

- **Threat**: A third-party application escapes its container/flatpak sandbox.
- **Mitigation**: Application isolation via Linux namespaces, cgroups v2, and Wayland protocol isolation. Flatpak or equivalent for third-party apps.
- **Status**: NOT IMPLEMENTED (Phase 3+)

### T4 — Secret Leakage via Logs or Repository

- **Threat**: Credentials, signing keys, or tokens exposed in build logs or committed to the repository.
- **Mitigation**: .gitignore covers key file types. CI includes secret scanning (Gitleaks). No credentials in CI environment variables beyond GITHUB_TOKEN.
- **Status**: PARTIAL — Gitleaks configured in CI (Phase 0)

### T5 — Supply Chain Compromise

- **Threat**: A compromised upstream package or CI action introduces malicious code.
- **Mitigation**: Pin GitHub Actions to commit SHAs. Pin package versions in build manifests. Use SBOM for dependency tracking. Verify checksums of downloaded artifacts.
- **Status**: PARTIAL — Actions pinned in CI (Phase 0); SBOM planned (Phase 6)

### T6 — Unauthorized Downgrade

- **Threat**: Attacker delivers an older, vulnerable OS version as an update.
- **Mitigation**: Signed metadata includes minimum version field. Update service enforces anti-rollback policy.
- **Status**: NOT IMPLEMENTED (Phase 4)

### T7 — Denial of Service via Resource Exhaustion

- **Threat**: Malformed IPC message or runaway process starves the UI or audio subsystem.
- **Mitigation**: Rate limits on IPC endpoints. cgroups v2 resource limits on services and applications. UI-critical paths use bounded queues.
- **Status**: NOT IMPLEMENTED (Phase 3+)

### T8 — Boot Chain Integrity Violation

- **Threat**: Bootloader or kernel replaced by attacker with physical access.
- **Mitigation**: UEFI Secure Boot support (planned). Measured boot logging.
- **Status**: NOT IMPLEMENTED — evaluated in Phase 6

## Out-of-Scope Threats (current phase)

- Evil maid attacks (not yet in scope for Phase 0-3).
- Hardware firmware attacks (TPM integration planned but not scoped).
- Radio-frequency attacks on future phone hardware (AOSP port not started).
- Social engineering of contributors.

## Invariants

The following invariants must never be violated:

1. No unsigned or unverified update artifact can be activated.
2. A failed verification can never report success.
3. The desktop shell cannot bypass system-service authorization.
4. User data must not be erased by a routine update or rollback.
5. Feature flags cannot disable mandatory security controls.
6. Secrets must not appear in logs, repository files, or CI outputs.

## Revision Schedule

This document is reviewed and expanded at each phase gate.
