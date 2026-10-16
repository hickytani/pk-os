# PK-OS Architecture Overview

## 1. System Vision

PK-OS is a modern, lightweight, highly secure, and reproducible operating system built for x86_64 personal computing hardware (with an architectural path toward AOSP-based companion integration). PK-OS merges the reliability of immutable infrastructure with an intuitive, performant, and responsive desktop experience.

---

## 2. High-Level System Architecture

```mermaid
graph TD
    subgraph Firmware and Boot
        UEFI[UEFI Firmware / Secure Boot] --> SB[systemd-boot / UKI]
        SB --> Kernel[Linux LTS Hardened Kernel]
    end

    subgraph Core OS Layer - Immutable
        Kernel --> Initrd[systemd Initramfs]
        Initrd --> DMVerity[dm-verity Rootfs Verification]
        DMVerity --> Sysd[systemd PID 1 Core Services]
        Sysd --> UDev[systemd-udevd / Hardware]
        Sysd --> Net[NetworkManager / iwd]
        Sysd --> Log[systemd-journald]
        Sysd --> Upd[pk-updated / A-B System Update]
    end

    subgraph Security and Storage
        TPM[TPM 2.0 Module] --> LUKS[LUKS2 Volume Unsealing]
        LUKS --> UserData[/var /home Partition]
        Polkit[Polkit / AppArmor / Landlock] --> Sysd
    end

    subgraph Display and Session Layer
        Sysd --> Greet[PK Greeter / Login]
        Greet --> Session[pk-session-manager]
        Session --> Comp[PK Wayland Compositor]
        Comp --> Shell[PK Desktop Shell UI]
    end

    subgraph Application Sandboxing
        Comp --> Portal[xdg-desktop-portal-pk]
        Portal --> Flatpak[Flatpak Runtime Environment]
        Portal --> Bwrap[Bubblewrap Sandboxes]
        Flatpak --> App1[Sandboxed Desktop Apps]
        Bwrap --> App2[Isolated System Daemons]
    end
```

---

## 3. Structural Layers

### 3.1 Firmware and Boot Layer
- **Unified Kernel Images (UKI)**: Combines the Linux kernel, initramfs, microcode, and kernel command line into a single cryptographically signed PE binary.
- **Secure Boot**: Hardware-verified execution from UEFI root keys to PK-OS UKI signing keys.
- **Bootloader**: Fast, minimal `systemd-boot` managing dual-slot selection.

### 3.2 Root Filesystem & Immutability Layer
- **A/B Dual Partitioning**: Two identical read-only root partitions (`root-a`, `root-b`).
- **Cryptographic Verification**: `dm-verity` ensures block-level integrity. Any tampering triggers immediate boot rejection or kernel panic.
- **Stateless Root**: Root `/` is strictly read-only. Mutable state is restricted to `/var` and `/etc` (managed via `systemd-sysusers`, `systemd-tmpfiles`, and overlayfs where necessary).
- **Atomic Updates**: Updates are downloaded and written in the background to the inactive slot. Activation occurs via a reboot with automatic health check and rollback.

### 3.3 Storage & Data Layer
- **Encrypted User Data**: `/home` resides on a LUKS2-encrypted partition cryptographically bound to TPM 2.0 PCR states (PCR 0, 2, 4, 7).
- **Key Recovery**: High-entropy offline recovery key generated during installation.

### 3.4 Session & Desktop Layer
- **Wayland-Native**: Pure Wayland architecture; X11 dependencies are isolated strictly to rootless `Xwayland` sandboxes when compatibility is required.
- **Compositor**: Custom, optimized Wayland compositor prioritizing frame pacing, low latency input handling, and strict display power efficiency.
- **Inter-Process Communication**: D-Bus and Varlink protocols with explicit access control enforced by Polkit and AppArmor.

### 3.5 Application Sandboxing Layer
- **Isolation by Default**: Third-party applications run within Bubblewrap or Flatpak namespaces.
- **Permission Portals**: Hardware access (camera, microphone, file picker, network, notifications) is mediated through `xdg-desktop-portal` user-prompted dialogs.

---

## 4. Subsystem Interfaces and Communication

| Component | Protocol / Interface | Access Control |
|---|---|---|
| Desktop Shell <-> Compositor | Wayland Protocols / IPC | Local Unix Socket |
| Compositor <-> Display Hardware | KMS/DRM, libinput, Mesa GB | `video`, `input` groups |
| Client App <-> System Resources | XDG Desktop Portal / D-Bus | Sandbox Filters / Tokenized |
| PK Update Daemon <-> Shell | D-Bus (`org.pkos.Update1`) | Polkit Authentication |
| Network Daemon <-> Shell | NetworkManager D-Bus | Polkit Authentication |
| Session <-> systemd | `logind` / `systemd` IPC | Polkit / User Session Bus |

---

## 5. Architectural Non-Negotiables

1. **Zero System Mutation in Production**: No package manager mutating the active root filesystem live.
2. **Deterministic Builds**: The entire OS image must build from audited, lock-pinned manifests.
3. **Fail-Safe Rollback**: A failed OS update must revert to the previous working slot within a single reboot cycle without manual user intervention.
