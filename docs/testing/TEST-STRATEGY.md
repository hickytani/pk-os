# PK-OS Comprehensive Testing Strategy

## 1. Testing Philosophy

PK-OS follows a multi-tiered test pyramid ensuring that every layer—from kernel boot parameters to desktop shell render latency—is verified automatically before release.

```
       /\
      /  \     Tier 4: Hardware Compatibility & Stress Testing (Physical Reference HW)
     /----\
    /      \    Tier 3: End-to-End System & VM Boot Tests (QEMU/KVM Automation)
   /--------\
  /          \   Tier 2: Component Integration & Mocked D-Bus Services
 /------------\
/              \  Tier 1: Unit Tests, Static Analysis, Linter Checks (Fast CI)
----------------
```

---

## 2. Test Tiers

### Tier 1: Unit and Static Analysis (Continuous Integration)
- **Scope**: Executed on every pull request and commit.
- **Tools**:
  - `shellcheck` for shell scripts.
  - `yamllint` and `markdownlint` for configuration and documentation.
  - Rust `cargo test` / `cargo clippy` (or C++/Go test suites) for individual daemons.
  - Gitleaks for secret and credential leakage detection.
- **Pass Criteria**: 100% clean exit codes; zero lint warnings in enforced rules.

### Tier 2: Component Integration Tests
- **Scope**: Verifies interaction between coupled system services.
- **Focus Areas**:
  - Wayland protocol conformance tests with headless mock clients.
  - D-Bus API contract validation using mock service fixtures.
  - A/B partition switch logic with simulated block device state machines.
  - Sandboxing policy audits (Bubblewrap filesystem leaks, permission denials).

### Tier 3: Automated Virtual Machine Testing (QEMU / KVM)
- **Scope**: Runs full OS image builds in automated virtual machines.
- **Validation Pipeline**:
  1. **Boot Verification**: Launch QEMU with UEFI (OVMF) + Secure Boot enabled. Assert boot succeeds to login prompt in under 15 seconds.
  2. **Systemd Unit Health**: Inspect `systemd-analyze verify` and assert `failed-units == 0`.
  3. **dm-verity Verification**: Validate that the root filesystem is active in read-only mode and verity hashes match.
  4. **A/B Upgrade Test**: Apply an update package, reboot, verify partition switch, simulate boot failure, verify automatic rollback to previous slot.
  5. **Network Stack Test**: Mock virtual TAP network interface, test DHCP resolution and DNS-over-TLS.

### Tier 4: Hardware Compatibility Testing (Physical Labs)
- **Scope**: Validated on reference tier hardware before minor or major releases.
- **Test Matrix**:
  - Suspend / Resume cycles (S3 and modern standby S0ix) across 50 consecutive loops.
  - Multi-monitor hotplugging and display scaling transitions.
  - Wi-Fi and Bluetooth association, audio playback via PipeWire across internal speakers and 3.5mm/USB jack.
  - GPU acceleration stability under Mesa OpenGL and Vulkan test workloads.

---

## 3. Regression Tracking

- Every discovered defect must be paired with an automated integration test or QEMU regression assertion before closing.
- Failure modes documented in [`docs/testing/FAILURE-MODE-MATRIX.md`](FAILURE-MODE-MATRIX.md) serve as the acceptance criteria for release sign-offs.
