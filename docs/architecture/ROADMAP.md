# PK-OS Development Roadmap

Status: LIVING DOCUMENT — updated after each phase gate.
Last updated: Phase 0

---

## Phase Dependency Order

```text
Phase 0 (Foundation)
  |
Phase 1 (Bootable Image)
  |
Phase 2 (Desktop Shell)
  |
Phase 3 (System Integration)
  |
Phase 4 (Secure Updates)
  |
Phase 5 (Differentiating Features)
  |
Phase 6 (Security Hardening)
  |
Phase 7 (Installer + Alpha Release)
```text

Phases must complete their exit gate before the next phase begins.
Independent work (documentation, design exploration, test writing) may be parallelized.

---

## Phase 0 — Repository Foundation

**Status**: IN PROGRESS
**Owner**: Engineering Lead
**Estimated Duration**: 1-2 weeks

### Objectives

- Inspect and baseline the repository.
- Establish engineering standards (formatting, linting, commit conventions).
- Create all required governance documents.
- Implement CI with linting, secret scanning, and structure validation.
- Document architecture and record initial ADRs.
- Produce Phase 1 handoff prompt.

### Exit Criteria

- [ ] Repository inspected and baselined.
- [ ] README.md accurately describes current state (no future features documented as working).
- [ ] CONTRIBUTING.md, SECURITY.md, LICENSE, CODE_OF_CONDUCT.md present.
- [ ] .gitignore and .editorconfig configured.
- [ ] PR template and issue templates created.
- [ ] CI workflow runs and all applicable checks pass.
- [ ] At least ADR-001 (base distribution) created.
- [ ] docs/architecture/ROADMAP.md present (this file).
- [ ] docs/security/THREAT-MODEL.md skeleton present.
- [ ] docs/testing/FAILURE-MODE-MATRIX.md skeleton present.
- [ ] Phase 1 implementation prompt ready.

### Known Risks

- GitHub Actions free-tier limits may throttle CI on large image builds (Phase 1+).
- Base distribution decision (ADR-001) requires research before Phase 1 can begin.

---

## Phase 1 — Reproducible Linux Image and VM Boot

**Status**: PLANNED
**Depends on**: Phase 0 complete
**Estimated Duration**: 3-5 weeks

### Objectives

- Finalize base distribution (Debian/Ubuntu/Fedora/custom).
- Implement image build pipeline (mkosi, live-build, or equivalent).
- Pin all dependencies and record provenance.
- Configure kernel, bootloader (systemd-boot or GRUB), and minimal userspace.
- Boot the image in QEMU and capture evidence (serial log, screenshot).
- Document known hardware assumptions and limitations.

### Exit Criteria

- [ ] Image builds reproducibly from documented commands.
- [ ] Image boots in QEMU (serial log evidence required).
- [ ] Display and basic input available in VM.
- [ ] Networking functional in VM.
- [ ] Clean restart works.
- [ ] Build documented in docs/development/BUILD.md.

### Key Decisions Needed

- ADR-001: Base distribution selection (Debian vs Ubuntu vs Fedora vs custom).
- ADR-002: Bootloader selection (systemd-boot vs GRUB).
- ADR-003: Image build tooling (mkosi vs live-build vs custom).

---

## Phase 2 — Custom PK-OS Desktop Shell

**Status**: PLANNED
**Depends on**: Phase 1 complete
**Estimated Duration**: 6-10 weeks

### Objectives

- Design system: color tokens, typography, spacing, motion, iconography.
- Implement Wayland compositor integration (using wlroots, KWin, or Mutter as backend).
- Build core shell components: dock, launcher, workspace switcher, notifications, quick settings.
- Capture screenshots from actual running shell (not browser mockups).
- Validate keyboard navigation, focus management, and reduced-motion mode.

### Exit Criteria

- [ ] Shell renders in running VM (screenshot evidence).
- [ ] All core shell components functional.
- [ ] Keyboard navigation and focus management verified.
- [ ] Reduced motion mode tested.
- [ ] Performance measurements documented (environment, methodology).

---

## Phase 3 — Real System Integration

**Status**: PLANNED
**Depends on**: Phase 2 complete

### Objectives

- Implement narrow D-Bus or IPC system service interfaces.
- Wire up: CPU/memory metrics, network controls, audio, battery, storage health.
- Ensure shell never receives unrestricted root access.
- Integration tests for each supported capability.

### Exit Criteria

- [ ] All displayed metrics are live (not cached or faked).
- [ ] Each system control maps to a real kernel/service capability.
- [ ] Privileged operations require explicit authorization.
- [ ] Integration tests pass.

---

## Phase 4 — Secure Updates and Recovery

**Status**: PLANNED
**Depends on**: Phase 3 complete

### Objectives

- Design update state machine with all transition states.
- Implement cryptographic verification of update metadata and artifacts.
- Implement atomic activation (A/B or equivalent).
- Implement health checks and automatic rollback.
- Test: power loss scenarios, corrupt artifacts, invalid signatures, rollback.

### Exit Criteria

- [ ] State machine fully implemented and documented.
- [ ] All signing and verification tests pass.
- [ ] Power-loss and corruption tests pass.
- [ ] Rollback tested end-to-end.

---

## Phase 5 — Differentiating Features

**Status**: PLANNED
**Depends on**: Phase 4 complete

### Objectives

- Local-first AI provider interface (optional, feature-flagged).
- Permission ledger (records system-service access decisions).
- Supervised service recovery policies.
- Reproducible build verification.

### Exit Criteria

- [ ] Each feature behind a feature flag.
- [ ] Each feature has a threat model, tests, and resource limits.
- [ ] No feature bypasses mandatory security controls.

---

## Phase 6 — Security Hardening and Reliability

**Status**: PLANNED
**Depends on**: Phase 5 complete

### Objectives

- Static analysis (clang-tidy, semgrep, ruff).
- Dependency vulnerability scanning (trivy, grype).
- Fuzz testing of IPC surface and update parser.
- Fault injection (power loss, disk full, corrupt image).
- SBOM generation.

### Exit Criteria

- [ ] All critical static analysis findings resolved.
- [ ] SBOM generated and published.
- [ ] Fuzz corpus and findings documented.
- [ ] Fault injection tests pass.

---

## Phase 7 — Installer and Alpha Release

**Status**: PLANNED
**Depends on**: Phase 6 complete

### Objectives

- Calamares-based or custom installer.
- Signed release artifacts with checksums.
- Hardware compatibility matrix finalized.
- Release manifest and SBOM.
- Public alpha announcement.

### Exit Criteria

- [ ] Installer tested on at least one real x86_64 machine.
- [ ] All release artifacts signed and checksums published.
- [ ] Hardware compatibility matrix accurate.
- [ ] SBOM present.
- [ ] Contributor onboarding documented and tested.

---

## Assumptions Register

| ID | Assumption | Risk if Wrong |
|---|---|---|
| A-001 | Linux kernel mainline supports target hardware | May need out-of-tree drivers |
| A-002 | Wayland compositing stack is stable enough for Phase 2 | May need fallback to X11 |
| A-003 | GitHub Actions runners sufficient for image builds | May need self-hosted runners |
| A-004 | QEMU sufficient for Phase 1 boot testing | Hardware differences may surface in Phase 7 |
| A-005 | GPL-2.0 compatible with all chosen components | License audit needed before Phase 7 |

---

## Decision Log

| ID | Decision | Phase | Status |
|---|---|---|---|
| ADR-001 | Base Linux distribution | Phase 1 | OPEN |
| ADR-002 | Bootloader | Phase 1 | OPEN |
| ADR-003 | Image build tooling | Phase 1 | OPEN |
| ADR-004 | Wayland compositor strategy | Phase 2 | OPEN |
| ADR-005 | Update mechanism | Phase 4 | OPEN |
| ADR-006 | Signing infrastructure | Phase 4 | OPEN |
