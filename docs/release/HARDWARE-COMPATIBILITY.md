# PK-OS Hardware Compatibility Matrix

**Status**: SKELETON — Phase 0. Populated from Phase 1 VM testing and Phase 7 physical testing.
**Last updated**: 2026-10-16

> No hardware has been tested yet. This document will be updated with verified results
> beginning in Phase 1 (VM) and Phase 7 (physical hardware).

---

## Testing Status Legend

| Symbol | Meaning |
|---|---|
| VERIFIED | Tested and confirmed working with evidence |
| PARTIAL | Works with limitations (documented below) |
| UNTESTED | Not yet tested |
| BROKEN | Known not to work; issue filed |
| N/A | Not applicable to this hardware type |

---

## Virtual Machines (Phase 1 target)

| Platform | CPU | RAM | GPU | Network | Status | Notes |
|---|---|---|---|---|---|---|
| QEMU/KVM (x86_64) | virtio | 2GB+ | virtio-gpu / std VGA | virtio-net | UNTESTED | Primary Phase 1 test target |
| VirtualBox (x86_64) | x86_64 | 2GB+ | VBoxSVGA | Intel PRO/1000 | UNTESTED | Secondary VM target |
| VMware Workstation | x86_64 | 2GB+ | SVGA II | vmxnet3 | UNTESTED | |

---

## Physical Hardware (Phase 7 target)

### CPUs

| Family | Vendor | Status | Notes |
|---|---|---|---|
| Intel Core (8th gen+) | Intel | UNTESTED | Target: modern x86_64 |
| AMD Ryzen (3000+) | AMD | UNTESTED | Target: modern x86_64 |
| Intel Core (6th-7th gen) | Intel | UNTESTED | Older hardware, lower priority |

### GPUs

| GPU | Driver | Wayland | Status | Notes |
|---|---|---|---|---|
| Intel integrated (Gen 8+) | i915 (kernel) | Yes | UNTESTED | |
| AMD Radeon (GCN 4+) | amdgpu (kernel) | Yes | UNTESTED | |
| NVIDIA (open kernel module) | nvidia-open | Partial | UNTESTED | Wayland support varies |
| NVIDIA (proprietary) | nvidia | Partial | UNTESTED | Not bundled; user-installed |
| Generic VGA fallback | vesa/fbdev | No GPU accel | UNTESTED | Reduced effects mode |

### Network Adapters

| Controller | Driver | Status | Notes |
|---|---|---|---|
| Intel I219/I225 (Ethernet) | e1000e / igc | UNTESTED | Common in laptops |
| Realtek RTL8111 (Ethernet) | r8169 | UNTESTED | Very common |
| Intel AX200/AX210 (WiFi) | iwlwifi | UNTESTED | Requires non-free firmware |
| Realtek WiFi (various) | rtw88/rtw89 | UNTESTED | May require non-free firmware |

### Audio

| Controller | Driver | Status | Notes |
|---|---|---|---|
| Intel HDA (generic) | snd_hda_intel | UNTESTED | Pipewire target |
| AMD HD Audio | snd_hda_intel | UNTESTED | |

### Storage

| Type | Interface | Status | Notes |
|---|---|---|---|
| NVMe SSD | PCIe | UNTESTED | Primary target |
| SATA SSD | SATA | UNTESTED | |
| eMMC | eMMC | UNTESTED | Lower priority |

---

## Minimum Supported Specifications

> These are targets, not verified requirements. They will be confirmed in Phase 1 and 7.

| Resource | Minimum | Recommended |
|---|---|---|
| CPU | x86_64, 2 cores, SSE4.2 | 4+ cores |
| RAM | 2 GB | 8 GB |
| Storage | 20 GB | 64 GB SSD |
| GPU | Any with framebuffer | Intel/AMD with Wayland support |
| Firmware | UEFI (BIOS fallback TBD) | UEFI |

---

## Unsupported Hardware

The following are explicitly out of scope for the initial x86_64 release:

- 32-bit (i686) CPUs
- ARM/RISC-V systems (future consideration)
- Android phones (AOSP port — future, not started)
- Systems without UEFI (may be added later)

---

## Reporting Hardware Issues

If you test PK-OS on hardware not listed here, please file a GitHub Issue using the Bug Report template and include your hardware specifications and test results.
