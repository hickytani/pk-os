# ADR-001: Base Linux Distribution Selection

**Status**: PROPOSED
**Date**: 2026-10-16
**Deciders**: Architecture Team
**Target Phase**: Phase 1

---

## Context and Problem Statement

PK-OS must be built on a Linux base. The choice of base distribution determines:
- The package manager and software availability.
- The release and security update cadence.
- The image build tooling available.
- Licensing and redistribution obligations.
- Long-term maintenance burden.
- Compatibility with future AOSP-based phone port.

This decision must be made before Phase 1 can begin.

## Decision Drivers

- Must produce a reproducible, bootable x86_64 image.
- Must support Wayland compositing (Phase 2).
- Must allow custom branding without violating upstream trademarks.
- Must have LTS or rolling security update support.
- Must have a well-tested image build toolchain.
- Must be GPL-2.0 compatible.
- Image size should be minimizable for distribution.
- Build infrastructure should work in a CI/CD environment.

## Considered Options

1. Debian Stable (bookworm) as the base — custom image via live-build or mkosi
2. Ubuntu LTS (24.04) as the base — custom image via live-build or ubuntu-image
3. Fedora as the base — custom image via Lorax / mkosi
4. Arch Linux as the base — custom image via archiso
5. Void Linux — custom image via void-mklive
6. Fully custom (Linux From Scratch approach) — no upstream base

## Decision Outcome

**Status**: OPEN — awaiting Phase 1 research

**Preliminary preference**: Debian Stable or Ubuntu LTS, due to:
- Well-understood live-build and mkosi tooling.
- Long support window.
- Large package set for driver coverage.
- No trademark issues when building a derivative.
- Strong community and upstream security response.

**Conditions for revisiting**:
- If Debian/Ubuntu cannot support the target Wayland compositor in Phase 2.
- If package update cadence proves too slow for security needs.
- If a better atomic-update story emerges from Fedora (rpm-ostree) that outweighs Debian advantages.

---

## Pros and Cons of the Options

### Option 1 — Debian Stable

**Evidence / sources**: https://www.debian.org/releases/ ; https://wiki.debian.org/DebianLive

Pros:
- Rock-solid stability and long LTS window.
- Excellent live-build tooling with CI support.
- No trademark concerns when building derivatives.
- Excellent hardware driver availability via non-free firmware.
- mkosi supports Debian as a first-class target.

Cons:
- Older package versions (kernel, graphics stack).
- Backports needed for cutting-edge Wayland support.
- Slower security response than Ubuntu on some packages.

Security / maintenance implications:
- Debian Security Team provides timely CVE patches.
- Must track debian-security mailing list.

### Option 2 — Ubuntu LTS (24.04)

**Evidence / sources**: https://ubuntu.com/about/release-cycle

Pros:
- More current packages than Debian Stable.
- Canonical provides 5-year LTS support.
- ubuntu-image and live-build both supported.
- Excellent Wayland/GNOME stack support.

Cons:
- Snaps are default; must be opted out carefully.
- Ubuntu trademark requires care in naming.
- Canonical occasionally makes controversial default changes.

Security / maintenance implications:
- Ubuntu Security Notices (USN) well-managed.
- Must remove snap daemon if not desired.

### Option 3 — Fedora

**Evidence / sources**: https://docs.fedoraproject.org/en-US/fedora-coreos/ ; https://coreos.github.io/rpm-ostree/

Pros:
- Cutting-edge kernel and Wayland stack.
- rpm-ostree enables atomic image-based updates natively.
- Good CI tooling with Lorax and mkosi.

Cons:
- Shorter support window (13 months per release).
- Less prior art for custom-branded Fedora derivatives.
- RPM ecosystem is less familiar than apt for many contributors.

Security / maintenance implications:
- Fedora Security Team is responsive.
- SELinux policies well-maintained on Fedora.

### Option 4 — Arch Linux

**Evidence / sources**: https://wiki.archlinux.org/title/Archiso

Pros:
- Always-current packages (rolling release).
- Minimal base; full control over installed packages.
- archiso is well-maintained.

Cons:
- No LTS; every update is potentially breaking.
- No formal security support window.
- Not suitable for a stable, maintainable distribution.

Security / maintenance implications:
- Arch Security Team exists but no formal CVE SLA.
- Rolling release makes reproducible builds harder.

### Option 5 — Void Linux

**Evidence / sources**: https://voidlinux.org/

Pros:
- Musl or glibc variants; very lightweight.
- runit init system is simple.
- Independent project (not a Red Hat or Canonical derivative).

Cons:
- Small community; fewer contributors available.
- Less tooling for custom image generation.
- Less driver coverage than Debian/Ubuntu.

Security / maintenance implications:
- Smaller security team; patch latency may be higher.

### Option 6 — Linux From Scratch / Fully Custom

Pros:
- Complete control over every component.
- No upstream trademark issues.

Cons:
- Enormously high maintenance burden.
- Rebuilding package management, security updates, and drivers from scratch is out of scope for an initial release.
- Contradicts the project contract to use maintained upstream infrastructure.

Security / maintenance implications:
- The project would own all security patching — not feasible for a small team.

---

## Licensing and Redistribution Notes

- Debian and Ubuntu: Debian Free Software Guidelines (DFSG) compatible; non-free firmware available separately; no trademark issues for custom OS names.
- Fedora: Fedora trademark must not be used in derivative names.
- All options carry GPL-2.0, LGPL, and MIT components; license audit required before Phase 7.

## References

- https://wiki.debian.org/DebianLive
- https://ubuntu.com/about/release-cycle
- https://docs.fedoraproject.org/en-US/fedora-coreos/
- https://systemd.io/BUILDING_IMAGES/
- https://github.com/systemd/mkosi
- https://coreos.github.io/rpm-ostree/
