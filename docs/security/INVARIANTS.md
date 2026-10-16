# PK-OS Core Security Invariants

These invariants are the non-negotiable security promises of PK-OS. Any code change, pull request, or architectural proposal that violates these invariants must be rejected.

---

## Invariant 1: Block-Level Immutability of System Binaries
- **Rule**: The operating system root filesystem must be mounted strictly read-only and cryptographically verified at runtime using `dm-verity`.
- **Enforcement**:
  - The kernel refuses to mount root filesystems whose merkle tree hash does not match the signed UKI boot parameters.
  - Tampered blocks trigger an instantaneous I/O error and security alert.
  - Package installations or binary alterations cannot occur on a live running root partition.

---

## Invariant 2: Hardware Root of Trust and Measured Boot
- **Rule**: Every stage of the boot cycle must be cryptographically measured and verified from hardware firmware through user space login.
- **Enforcement**:
  - UEFI Secure Boot verifies the Unified Kernel Image (UKI).
  - TPM 2.0 measures firmware, secure boot state, and kernel parameters into PCRs (0, 2, 4, 7).
  - Storage decryption keys for `/home` and `/var` are unsealed only if the PCR measurements match expected values.

---

## Invariant 3: Privilege Separation and Least Privilege
- **Rule**: No user session application runs with root privileges. Root account is disabled or locked; administrative operations require explicit, tokenized Polkit authentication.
- **Enforcement**:
  - Polkit rules require explicit authorization for privileged actions.
  - System daemons run in isolated `systemd` dynamic users with minimal Linux capabilities (`cap_net_bind_service`, etc.) and restricted namespaces (`ProtectSystem=strict`, `ProtectHome=yes`, `NoNewPrivileges=yes`).

---

## Invariant 4: Mandatory Application Isolation
- **Rule**: All user-installed desktop applications must execute within sandboxed namespaces with restricted filesystem, network, and device visibility.
- **Enforcement**:
  - Applications run via Bubblewrap or Flatpak container boundaries.
  - Direct access to raw block devices, host IPC, `/dev`, or host `/etc` is prohibited.
  - Inter-application communication is mediated strictly through `xdg-desktop-portal` with user confirmation prompts.

---

## Invariant 5: Secure Network Posture by Default
- **Rule**: Zero listening ports exposed on external network interfaces on fresh installation.
- **Enforcement**:
  - Local packet filtering (`nftables`) is active from early boot.
  - DNS-over-TLS (DoT) is enabled by default via `systemd-resolved`.
  - Inbound traffic is blocked unless an explicit user-configured service is permitted.

---

## Invariant 6: Zero Covert Telemetry
- **Rule**: PK-OS does not collect, log, or transmit personal data, user activity, telemetry, or system identifiers without explicit, transparent, opt-in consent.
- **Enforcement**:
  - Crash reporting and analytics daemons are disabled by default.
  - Update checks send only architecture and version strings without unique machine identifiers.
  - Codebase is continuously audited to guarantee user privacy.
