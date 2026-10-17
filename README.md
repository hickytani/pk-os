# PK-OS

> **An open-source, Linux-based operating system for x86_64 PCs and laptops.**

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-1%20%E2%80%94%20Verified%20Bootable-green.svg)](#project-status)
[![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

---

## Project Status: Phase 1 Verified → Phase 2 Shell & AI Foundation

PK-OS has completed **Phase 1 (Reproducible Linux Rootfs & Bootable UEFI Disk Image)** with full QEMU hardware-accelerated boot verification reaching userspace login. Phase 2 (Wayland Desktop Shell Foundation) and the parallel PK Intelligence workstream are actively underway.

| Capability | Status | Evidence / Milestone |
|---|---|---|
| Repository structure & CI | IMPLEMENTED (Phase 0) | Linters (markdownlint, yamllint, shellcheck) passing 100% |
| Architecture decision records | IMPLEMENTED (Phase 0/1/2) | ADR-001 (Debian base), ADR-002 (Wayland Shell), ADR-003 (PK Intelligence) |
| Reproducible minimal rootfs | IMPLEMENTED (Phase 1A) | `pk-os-rootfs.latest.tar.zst` (~87 MB compressed, ~950 MB raw) |
| Bootable UEFI GPT disk image | IMPLEMENTED (Phase 1C) | `pk-os-dev.raw` (1,500 MB, GPT: 128MB FAT32 ESP + ext4 Root) |
| QEMU UEFI boot smoke test | IMPLEMENTED (Phase 1D) | Serial console reached `pk-os login:` via systemd-boot & Linux LTS 6.1 |
| Desktop shell foundation | IMPLEMENTED (Phase 2 Slice) | `shell/` (Design tokens, session lifecycle, adaptive layout engine) |
| PK Intelligence local stack | IMPLEMENTED (Phase 5 Slice) | `intelligence/` (Typed tool registry, security permission ledger, eval harness) |
| Full desktop session integration | IN PROGRESS (Phase 2) | Compositor runtime packaging & graphical session execution |
| A/B signed atomic updates | PLANNED (Phase 4) | Dual-root slot partitioning & dm-verity state machine |
| Bare-metal physical installer | PLANNED (Phase 7) | Live installer ISO with target drive partitioning safety |

---

## What Is PK-OS?

PK-OS is a real, independent Linux operating system distribution targeting:

- **Primary**: x86_64 PCs and laptops (Phase 1–7)
- **Future**: Selected mobile devices via an adaptive UI and AOSP-based port (planned)

Key architectural pillars:

- **UEFI & systemd-boot**: Native Boot Loader Specification (BLS) compliant bootchain.
- **Wayland Desktop Shell**: Custom, lightweight, hardware-accelerated desktop shell built on `wlr-layer-shell-unstable-v1` with mathematical design tokens.
- **PK Intelligence ("Hey PK")**: Local-first, privacy-preserving voice assistant operating completely offline with deterministic, capability-gated tool execution.
- **Security & Integrity**: Process isolation, capability-based permission ledgers, and tamper-evident audit logging.

---

## Verified Phase 1 Bootable Artifacts

Build outputs are saved to `build/output/`:

- **Raw Disk Image**: `build/output/pk-os-dev.raw`
  - **Size**: 1,500 MB (1,572,864,000 bytes)
  - **Partition Table**: GPT
    - Partition 1: `ESP` (128 MB FAT32, `boot, esp`) -> `/EFI/systemd/systemd-bootx64.efi`, `/EFI/PKOS/vmlinuz`, `/EFI/PKOS/initrd.img`, `/loader/entries/pkos.conf`
    - Partition 2: `PKOS_ROOT` (1,370 MB ext4, `LABEL=PKOS_ROOT`) -> Debian 12 minimal base rootfs with systemd init
- **Checksum Ledger**: Recorded in `build/output/SHA256SUMS`

---

## Development & Test Workflows

### 1. Automated Test Suite (Windows PowerShell)

```powershell
# Run structure verification, linters, and the automated QEMU boot test
.\scripts\windows\test.ps1 -BootTest
```

### 2. Linux / WSL2 Workflow (Bash)

```bash
# 1. Verify prerequisites
./scripts/check-prereqs.sh

# 2. Run linters
./scripts/lint.sh

# 3. Build bootable disk image (requires root / sudo)
sudo ./scripts/build-disk-image.sh

# 4. Run automated QEMU UEFI boot smoke test (KVM accelerated)
./scripts/run-qemu.sh --test --timeout=90

# 5. Run shell foundation unit tests
python3 -m unittest discover -s shell/tests -p "test_*.py"

# 6. Run PK Intelligence tests & benchmark harness
python3 -m unittest discover -s intelligence/tests -p "test_*.py"
python3 intelligence/benchmarks/eval_harness.py
```

---

## Repository Structure

```text
pk-os/
+-- build/
|   +-- manifests/             # Minimal package manifests (base, kernel)
|   +-- output/                # Local build artifacts (git-ignored)
+-- docs/
|   +-- adr/                   # Architecture Decision Records (ADR-001, ADR-002, ADR-003)
|   +-- architecture/          # Overview, Roadmap, Shell, Intelligence, IPC
|   +-- development/           # Developer setup and workflow guides
|   +-- security/              # Threat model, invariants, audit policies
|   +-- testing/               # Test strategy, failure-mode matrix
|   +-- release/               # Release process, hardware compatibility
+-- intelligence/              # PK Intelligence local agent foundation
|   +-- benchmarks/            # Reproducible eval harness & metrics
|   +-- data/v1/               # Versioned intent evaluation datasets
|   +-- src/                   # Interfaces, tools, security ledger, intent planner
|   +-- tests/                 # Unit test suite
+-- scripts/                   # Linux build, lint, and VM runner scripts
|   +-- windows/               # Windows PowerShell automation wrappers
+-- shell/                     # PK-OS Desktop Shell vertical slice
|   +-- src/tokens/            # Design tokens (JSON, CSS)
|   +-- src/session/           # Session lifecycle state machine & config
|   +-- src/ui/                # Adaptive layout engine & preview surface
|   +-- tests/                 # Shell unit tests
+-- README.md
+-- CONTRIBUTING.md
+-- SECURITY.md
+-- LICENSE
```

---

## License & Community

- **License**: GNU General Public License v2.0. See [LICENSE](LICENSE).
- **Issues**: [GitHub Issues](https://github.com/hickytani/pk-os/issues)
- **Discussions**: [GitHub Discussions](https://github.com/hickytani/pk-os/discussions)
