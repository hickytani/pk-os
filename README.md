# PK-OS

> **An open-source, Linux-based operating system for x86_64 PCs and laptops.**

[![License](https://img.shields.io/badge/license-GPL--2.0-blue.svg)](LICENSE)
[![Phase](https://img.shields.io/badge/phase-0%20%E2%80%94%20Foundation-orange.svg)](#project-status)
[![CI](https://github.com/hickytani/pk-os/actions/workflows/ci.yml/badge.svg)](https://github.com/hickytani/pk-os/actions/workflows/ci.yml)

---

## WARNING: Project Status — Phase 0 (Repository Foundation)

PK-OS is in **early development**. No bootable image exists yet. The current phase establishes engineering standards, documentation, and CI infrastructure so that future contributors can build on a sound foundation.

| Capability | Status |
|---|---|
| Bootable x86_64 image | NOT IMPLEMENTED |
| Desktop shell (PK-OS UI) | NOT IMPLEMENTED |
| System service integration | NOT IMPLEMENTED |
| Secure update mechanism | NOT IMPLEMENTED |
| Installer | NOT IMPLEMENTED |
| Repository structure and CI | IMPLEMENTED (Phase 0) |
| Architecture decision records | IMPLEMENTED (Phase 0) |
| Engineering standards docs | IMPLEMENTED (Phase 0) |

Do not attempt to install or run PK-OS on physical hardware at this stage. There is nothing to install.

---

## What Is PK-OS?

PK-OS is a real, from-scratch Linux distribution targeting:

- **Primary**: x86_64 PCs and laptops (first release)
- **Future**: One selected Android device via an AOSP-based port (planned, not started)

It aims to deliver a visually distinctive, premium desktop experience with:
- A custom Wayland-based desktop shell with signature motion design
- Strong security boundaries (namespaces, cgroups v2, SELinux)
- Cryptographically signed, atomic-capable software updates
- Local-first optional AI integration
- A reproducible, contributor-friendly build system

PK-OS is NOT:
- A reskin of an existing desktop environment
- A website pretending to be an OS
- A static mockup
- Vaporware -- it will be built gate by gate with verified evidence

---

## Development Roadmap

| Phase | Name | Status | Exit Criteria |
|---|---|---|---|
| 0 | Repository Foundation | In Progress | Docs, CI, ADRs, standards |
| 1 | Reproducible Linux Image and VM Boot | Planned | Image boots in QEMU, serial log evidence |
| 2 | Custom PK-OS Desktop Shell | Planned | Shell renders in running VM, screenshots |
| 3 | Real System Integration | Planned | Live metrics, service controls verified |
| 4 | Secure Updates and Recovery | Planned | Update state machine, rollback tested |
| 5 | Differentiating Features | Planned | Local-AI, permission ledger, feature flags |
| 6 | Security Hardening and Reliability | Planned | Static analysis, fuzz, fault injection |
| 7 | Installer and Alpha Release | Planned | Signed artifacts, hardware compat matrix |

See docs/architecture/ROADMAP.md for the full plan with exit criteria, risks, and dependencies.

---

## Development Prerequisites

These are the prerequisites for contributors developing PK-OS on their own machine.
A clean build has NOT yet been validated end-to-end because the image build pipeline does not exist yet (Phase 1).

### Supported Development Host Platforms

| Platform | Status |
|---|---|
| Ubuntu 22.04 / 24.04 (x86_64) | Primary development target |
| Debian 12 (Bookworm) | Expected to work |
| Fedora 39+ | Not yet validated |
| macOS (arm64/x86_64) | Limited -- image build tools may differ |
| Windows with WSL2 (Ubuntu) | Image build untested |

### Required Tools (Phase 0 -- Documentation and CI only)

    git >= 2.40
    python3 >= 3.11       # scripts and validation
    node >= 20            # tooling scripts
    shellcheck            # shell script linting
    yamllint              # YAML validation
    markdownlint-cli2     # documentation linting

### Future Required Tools (Phase 1+, not yet needed)

    debootstrap or dnf    # base system population
    mkosi / live-build    # image generation
    QEMU >= 8.0           # VM testing
    podman or docker      # build containers
    cosign                # artifact signing

---

## Repository Setup

    # Clone the repository
    git clone https://github.com/hickytani/pk-os.git
    cd pk-os

    # Verify your environment
    ./scripts/check-prereqs.sh

    # Run linting and validation
    ./scripts/lint.sh

The above scripts are created in Phase 0 and cover only documentation/CI validation.
Image build commands will be added in Phase 1 once the build pipeline exists.

---

## Running Tests

    # Lint and format checks (available in Phase 0)
    ./scripts/lint.sh

    # Future: image build smoke test (Phase 1)
    # ./scripts/build-image.sh --dry-run

    # Future: VM boot test (Phase 1)
    # ./scripts/test-boot.sh

Expected Phase 0 output: all linters pass, no secrets detected.

---

## Repository Structure

    pk-os/
    +-- docs/
    |   +-- architecture/      # System architecture, roadmap, decisions
    |   +-- adr/               # Architecture Decision Records
    |   +-- development/       # Developer setup and workflow guides
    |   +-- security/          # Threat model, security policy
    |   +-- testing/           # Test strategy, plans, failure-mode matrix
    |   +-- release/           # Release process, signing, hardware compat
    +-- scripts/               # Developer utility scripts
    +-- .github/
    |   +-- workflows/         # GitHub Actions CI
    |   +-- ISSUE_TEMPLATE/    # Bug and feature templates
    |   +-- PULL_REQUEST_TEMPLATE.md
    +-- README.md
    +-- CONTRIBUTING.md
    +-- SECURITY.md
    +-- CODE_OF_CONDUCT.md
    +-- LICENSE
    +-- .editorconfig
    +-- .gitignore

Build system, image sources, and shell code will be added in later phases under clearly named subdirectories.

---

## Security

Please do not report security vulnerabilities as public GitHub Issues.

See SECURITY.md for the responsible disclosure process.

---

## Contributing

See CONTRIBUTING.md for:
- Code style and engineering standards
- How to open an issue or pull request
- The phase gate system and acceptance criteria
- How to run validation locally

---

## License

PK-OS is released under the GNU General Public License v2.0. See LICENSE.

Components derived from upstream Linux kernel patches remain under GPL-2.0.
Other components may carry their own compatible licenses -- see individual file headers.

---

## Community

- GitHub Issues: https://github.com/hickytani/pk-os/issues -- bug reports and feature requests
- GitHub Discussions: https://github.com/hickytani/pk-os/discussions -- design questions

---

PK-OS -- custom os, first attempt. Built in public.
