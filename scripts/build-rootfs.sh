#!/usr/bin/env bash
# scripts/build-rootfs.sh — Build reproducible minimal PK-OS rootfs via mmdebstrap
# Usage: ./scripts/build-rootfs.sh [--with-kernel] [--with-graphical] [--format=tar|dir]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${REPO_ROOT}/build/output"
MANIFEST_BASE="${REPO_ROOT}/build/manifests/base-pkgs.list"
MANIFEST_KERNEL="${REPO_ROOT}/build/manifests/kernel-pkgs.list"
MANIFEST_GRAPHICAL="${REPO_ROOT}/build/manifests/graphical-pkgs.list"

DEBIAN_SUITE="bookworm"
DEBIAN_MIRROR="http://deb.debian.org/debian"
DEBIAN_KEYRING="/usr/share/keyrings/debian-archive-keyring.gpg"
TARGET_ARCH="amd64"

WITH_KERNEL=false
WITH_GRAPHICAL=false
FORMAT="tar"

for arg in "$@"; do
  case "$arg" in
    --with-kernel)
      WITH_KERNEL=true
      ;;
    --with-graphical)
      WITH_GRAPHICAL=true
      ;;
    --format=tar)
      FORMAT="tar"
      ;;
    --format=dir)
      FORMAT="dir"
      ;;
    --help|-h)
      echo "Usage: $0 [--with-kernel] [--with-graphical] [--format=tar|dir]"
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

echo "=========================================================="
echo "          PK-OS Root Filesystem Build (Phase 2A)          "
echo "=========================================================="
echo "  * Suite:          ${DEBIAN_SUITE}"
echo "  * Mirror:         ${DEBIAN_MIRROR}"
echo "  * Architecture:   ${TARGET_ARCH}"
echo "  * Format:         ${FORMAT}"
echo "  * With Kernel:    ${WITH_KERNEL}"
echo "  * With Graphical: ${WITH_GRAPHICAL}"
echo "  * Output Dir:     ${OUTPUT_DIR}"
echo ""

# 1. Validation & Pre-flight checks
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: Root privileges required for filesystem bootstrapping." >&2
  echo "Please run inside WSL with: wsl -d Ubuntu -u root ..." >&2
  exit 1
fi

if ! command -v mmdebstrap &>/dev/null; then
  echo "ERROR: mmdebstrap is not installed. Run scripts/windows/setup.ps1" >&2
  exit 1
fi

if [ ! -f "${DEBIAN_KEYRING}" ]; then
  echo "ERROR: Debian archive keyring not found at ${DEBIAN_KEYRING}" >&2
  exit 1
fi

if [ ! -f "${MANIFEST_BASE}" ]; then
  echo "ERROR: Base manifest not found at ${MANIFEST_BASE}" >&2
  exit 1
fi

# Ensure output directory exists
mkdir -p "${OUTPUT_DIR}"

# Check available disk space (require at least 5 GB free)
AVAIL_KB=$(df -P "${OUTPUT_DIR}" | awk 'NR==2 {print $4}')
if [ "${AVAIL_KB}" -lt 5242880 ]; then
  echo "ERROR: Less than 5 GB available on output filesystem (${AVAIL_KB} KB free)." >&2
  exit 1
fi

# 2. Parse Package Manifests
parse_manifest() {
  local file="$1"
  grep -v '^[[:space:]]*#' "${file}" | grep -v '^[[:space:]]*$' | tr '\n' ',' | sed 's/,$//'
}

PKGS_BASE=$(parse_manifest "${MANIFEST_BASE}")
ALL_PKGS="${PKGS_BASE}"

if [ "${WITH_KERNEL}" = true ]; then
  if [ -f "${MANIFEST_KERNEL}" ]; then
    PKGS_KERNEL=$(parse_manifest "${MANIFEST_KERNEL}")
    ALL_PKGS="${ALL_PKGS},${PKGS_KERNEL}"
  fi
fi

if [ "${WITH_GRAPHICAL}" = true ]; then
  if [ ! -f "${MANIFEST_GRAPHICAL}" ]; then
    echo "ERROR: Graphical manifest not found at ${MANIFEST_GRAPHICAL}" >&2
    exit 1
  fi
  PKGS_GRAPHICAL=$(parse_manifest "${MANIFEST_GRAPHICAL}")
  ALL_PKGS="${ALL_PKGS},${PKGS_GRAPHICAL}"
fi

# 3. Setup temporary working directory with cleanup trap
# Use native ext4 filesystem (/var/tmp) to avoid DrvFS/NTFS socket and permission limitations in WSL2
TMP_BUILD="$(mktemp -d /var/tmp/pkos-rootfs.XXXXXX)"
# shellcheck disable=SC2317
cleanup() {
  if [ -d "${TMP_BUILD}" ]; then
    echo "  [CLEANUP] Removing temporary build directory..."
    rm -rf "${TMP_BUILD}"
  fi
}
trap cleanup EXIT INT TERM

ROOTFS_CHROOT="${TMP_BUILD}/rootfs"
mkdir -p "${ROOTFS_CHROOT}"

# 4. Bootstrap Root Filesystem via mmdebstrap
echo "[1/3] Bootstrapping Debian 12 minimal userspace..."
echo "  * Packages: ${ALL_PKGS}"

mmdebstrap \
  --arch="${TARGET_ARCH}" \
  --variant=minbase \
  --include="${ALL_PKGS}" \
  --keyring="${DEBIAN_KEYRING}" \
  "${DEBIAN_SUITE}" \
  "${ROOTFS_CHROOT}" \
  "${DEBIAN_MIRROR}"

echo "  [OK] Bootstrap completed successfully."

# 5. Basic OS Configuration & Post-processing
echo "[2/3] Configuring base OS identity & services..."

# Hostname
echo "pk-os" > "${ROOTFS_CHROOT}/etc/hostname"

# Hosts
cat << 'EOF' > "${ROOTFS_CHROOT}/etc/hosts"
127.0.0.1   localhost
127.0.1.1   pk-os
::1         localhost ip6-localhost ip6-loopback
ff02::1     ip6-allnodes
ff02::2     ip6-allrouters
EOF

# Machine ID (systemd initializes unique on first boot)
: > "${ROOTFS_CHROOT}/etc/machine-id"

# OS Release branding
cat << 'EOF' > "${ROOTFS_CHROOT}/etc/os-release"
NAME="PK-OS"
PRETTY_NAME="PK-OS 0.1.0 LTS (Based on Debian 12 Bookworm)"
ID=pkos
ID_LIKE=debian
VERSION_ID="0.1"
VERSION="0.1.0 (Phase 1 Baseline)"
HOME_URL="https://github.com/hickytani/pk-os"
SUPPORT_URL="https://github.com/hickytani/pk-os/issues"
BUG_REPORT_URL="https://github.com/hickytani/pk-os/issues"
EOF

# Ensure systemd serial gettys are enabled on ttyS0 for headless testing
mkdir -p "${ROOTFS_CHROOT}/etc/systemd/system/getty.target.wants"
ln -sf /lib/systemd/system/serial-getty@.service \
  "${ROOTFS_CHROOT}/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"

# Phase 2A: Install graphical session units when graphical build is requested
if [ "${WITH_GRAPHICAL}" = true ]; then
  echo "  [2A] Installing PK-OS graphical session units..."
  SYSTEMD_USER_DIR="${ROOTFS_CHROOT}/usr/lib/systemd/user"
  mkdir -p "${SYSTEMD_USER_DIR}"

  # Install pk-session.service (compositor)
  cp "${REPO_ROOT}/shell/src/compositor/pk-session.service" \
     "${SYSTEMD_USER_DIR}/pk-session.service"

  # Install pk-intelligenced.service
  cp "${REPO_ROOT}/intelligence/src/pk-intelligenced.service" \
     "${SYSTEMD_USER_DIR}/pk-intelligenced.service"

  # Enable both units in graphical-session.target
  mkdir -p "${SYSTEMD_USER_DIR}/graphical-session.target.wants"
  ln -sf ../pk-session.service \
    "${SYSTEMD_USER_DIR}/graphical-session.target.wants/pk-session.service"
  ln -sf ../pk-intelligenced.service \
    "${SYSTEMD_USER_DIR}/graphical-session.target.wants/pk-intelligenced.service"

  # Install PK-OS Python libraries to /usr/lib/pk-os
  PKOS_LIB="${ROOTFS_CHROOT}/usr/lib/pk-os"
  mkdir -p "${PKOS_LIB}"
  cp -r "${REPO_ROOT}/shell" "${PKOS_LIB}/"
  cp -r "${REPO_ROOT}/intelligence" "${PKOS_LIB}/"

  echo "  [OK] Graphical session units installed."
fi

# Configure root user with passwordless login for test development
chroot "${ROOTFS_CHROOT}" passwd -d root || true

# Clean apt caches to save image space
chroot "${ROOTFS_CHROOT}" apt-get clean || true
rm -rf "${ROOTFS_CHROOT}/var/lib/apt/lists/"*

echo "  [OK] System configuration applied."

# 6. Artifact Generation
echo "[3/3] Packaging rootfs artifact (${FORMAT})..."

TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
MANIFEST_DUMP="${OUTPUT_DIR}/rootfs-manifest-${TIMESTAMP}.txt"
# shellcheck disable=SC2016
chroot "${ROOTFS_CHROOT}" dpkg-query -W -f='${Package}\t${Version}\t${Architecture}\n' > "${MANIFEST_DUMP}"
cp "${MANIFEST_DUMP}" "${OUTPUT_DIR}/rootfs-manifest.latest.txt"

if [ "${FORMAT}" = "tar" ]; then
  OUTPUT_TAR="${OUTPUT_DIR}/pk-os-rootfs-${TIMESTAMP}.tar.zst"
  LATEST_TAR="${OUTPUT_DIR}/pk-os-rootfs.latest.tar.zst"
  
  echo "  * Creating compressed archive: ${OUTPUT_TAR}"
  tar -C "${ROOTFS_CHROOT}" --xattrs --xattrs-include='*' -c . | zstd -T0 -3 > "${OUTPUT_TAR}"
  ln -sf "$(basename "${OUTPUT_TAR}")" "${LATEST_TAR}"
  
  # Checksum
  (cd "${OUTPUT_DIR}" && sha256sum "$(basename "${OUTPUT_TAR}")" >> "${OUTPUT_DIR}/SHA256SUMS")
  
  SIZE_MB=$(du -m "${OUTPUT_TAR}" | cut -f1)
  SHA256=$(sha256sum "${OUTPUT_TAR}" | cut -d' ' -f1)
  
  echo ""
  echo "=========================================================="
  echo "          ROOTFS BUILD SUCCESSFUL (Milestone 1A)          "
  echo "=========================================================="
  echo "  * Artifact:   ${OUTPUT_TAR}"
  echo "  * Symlink:    ${LATEST_TAR}"
  echo "  * Size:       ${SIZE_MB} MB"
  echo "  * SHA256:     ${SHA256}"
  echo "  * Manifest:   ${MANIFEST_DUMP}"
  echo "=========================================================="
elif [ "${FORMAT}" = "dir" ]; then
  FINAL_DIR="${OUTPUT_DIR}/rootfs"
  rm -rf "${FINAL_DIR}"
  cp -a --reflink=auto "${ROOTFS_CHROOT}" "${FINAL_DIR}"
  echo "  [OK] Rootfs directory created at: ${FINAL_DIR}"
fi

exit 0
