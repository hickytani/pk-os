# PK-OS Release Engineering and Process

## 1. Release Principles

1. **Deterministic Reproducibility**: Builds must produce identical binary hashes when given identical inputs and lockfiles.
2. **Cryptographic Provenance**: Every artifact (ISO, raw image, delta update) must be signed with PK-OS release signing keys.
3. **Safe Rollouts**: Upgrades are distributed across canary rings before reaching broad availability.

---

## 2. Release Channels

| Channel | Cadence | Audience | Stability Target |
|---|---|---|---|
| **Nightly** | Daily automated builds | Core developers, automated CI | Experimental; may break |
| **Beta** | Bi-weekly | Early adopters, hardware testers | Feature-complete, pending regression testing |
| **Stable** | Quarterly (with point releases) | General users, production workstations | High reliability, verified against Tier 1 hardware |

---

## 3. Step-by-Step Release Workflow

### Step 1: Feature Freeze & Stabilization
- Create `release/vX.Y.Z` branch from `main`.
- Update version metadata across all manifests and build configurations.
- Execute full Tier 3 QEMU test suite and Tier 4 hardware qualification tests.

### Step 2: Image Generation
- Execute containerized build runner:
  ```bash
  ./scripts/build-image.sh --channel stable --version vX.Y.Z --target x86_64
  ```
- Generate build artifacts:
  - `pk-os-vX.Y.Z-x86_64-installer.iso` (Live installer image)
  - `pk-os-vX.Y.Z-x86_64-rootfs.raw.zst` (A/B sysupdate payload)
  - `pk-os-vX.Y.Z-sbom.spdx.json` (Software Bill of Materials)
  - `SHA256SUMS` (Digest manifest)

### Step 3: Cryptographic Signing
- Compute checksums:
  ```bash
  sha256sum pk-os-vX.Y.Z-* > SHA256SUMS
  ```
- Sign checksum file with PK-OS Release Key:
  ```bash
  minisign -S -s /keys/pk-os-release.key -m SHA256SUMS
  ```
- Sign UEFI binaries and kernel images with Secure Boot credentials.

### Step 4: Staging and Verification
- Upload candidate artifacts to internal staging bucket.
- Perform sanity installation on reference hardware:
  - Clean install onto bare-metal target.
  - Verify TPM 2.0 enrollment and Secure Boot activation.
  - Verify A/B update from v(X-1).Y.Z to vX.Y.Z.

### Step 5: Publication
- Create signed Git tag: `git tag -s vX.Y.Z -m "Release vX.Y.Z"`.
- Push tag to GitHub repository: `git push origin vX.Y.Z`.
- Publish GitHub Release with changelog, signatures, and SBOM.
- Update remote sysupdate server manifest for OTA delivery.
