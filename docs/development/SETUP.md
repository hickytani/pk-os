# Developer Setup Guide

**Status**: Phase 0 — covers environment setup for documentation and CI validation only.
**Image build setup will be added in Phase 1.**

---

## Prerequisites

### Required (Phase 0)

Install the following on your development machine:

**Ubuntu/Debian:**
```
sudo apt-get update
sudo apt-get install -y git shellcheck python3 python3-pip
pip3 install yamllint
npm install -g markdownlint-cli2
```

**macOS (Homebrew):**
```
brew install git shellcheck python3 node
pip3 install yamllint
npm install -g markdownlint-cli2
```

**Windows (WSL2 with Ubuntu recommended):**
```
# Inside WSL2 Ubuntu:
sudo apt-get update
sudo apt-get install -y git shellcheck python3 python3-pip
pip3 install yamllint
npm install -g markdownlint-cli2
```

### Future Requirements (Phase 1+, not yet needed)

```
# Image build tools (Ubuntu/Debian):
sudo apt-get install -y \
  debootstrap \
  squashfs-tools \
  qemu-system-x86 \
  qemu-utils \
  ovmf \
  podman

# mkosi (for image generation):
pip3 install mkosi

# cosign (for signing):
# See https://github.com/sigstore/cosign#installation
```

---

## Initial Setup

```bash
# 1. Clone the repository
git clone https://github.com/hickytani/pk-os.git
cd pk-os

# 2. Verify prerequisites
./scripts/check-prereqs.sh

# 3. Run all linters
./scripts/lint.sh
```

---

## Running Checks

```bash
# All checks (markdown, YAML, shell, structure)
./scripts/lint.sh

# Individual checks:
markdownlint-cli2 "**/*.md" "#node_modules"   # Markdown
yamllint .                                       # YAML
shellcheck scripts/*.sh                          # Shell scripts
```

---

## Git Workflow

1. Create a branch: `git checkout -b feature/my-feature`
2. Make changes following the standards in CONTRIBUTING.md.
3. Run `./scripts/lint.sh` locally.
4. Commit using Conventional Commits format.
5. Push and open a Pull Request.
6. All CI checks must pass before review.

---

## Phase 1 Preview

When Phase 1 begins, this document will be expanded with:
- Image build instructions.
- QEMU boot testing instructions.
- Dependency pinning procedures.
- Reproducibility verification steps.
