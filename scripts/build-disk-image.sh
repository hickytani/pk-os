#!/usr/bin/env bash
# scripts/build-disk-image.sh — Build bootable UEFI GPT disk image for PK-OS (Milestone 1C)
# Usage: ./scripts/build-disk-image.sh [--size=3G] [--output=path] [--rootfs-tar=path]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${REPO_ROOT}/build/output"
IMAGE_SIZE="3G"
CUSTOM_OUTPUT=""
CUSTOM_ROOTFS_TAR=""

WITH_GRAPHICAL=false

for arg in "$@"; do
  case "$arg" in
    --size=*)
      IMAGE_SIZE="${arg#*=}"
      ;;
    --output=*)
      CUSTOM_OUTPUT="${arg#*=}"
      ;;
    --rootfs-tar=*)
      CUSTOM_ROOTFS_TAR="${arg#*=}"
      ;;
    --with-graphical)
      WITH_GRAPHICAL=true
      ;;
    --help|-h)
      echo "Usage: $0 [--size=3G] [--output=path] [--rootfs-tar=path] [--with-graphical]"
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

FINAL_IMAGE="${CUSTOM_OUTPUT:-${OUTPUT_DIR}/pk-os-dev.raw}"
LATEST_IMAGE="${OUTPUT_DIR}/pk-os-dev.latest.raw"
ROOTFS_TAR="${CUSTOM_ROOTFS_TAR:-${OUTPUT_DIR}/pk-os-rootfs.latest.tar.zst}"
if [ -z "${CUSTOM_ROOTFS_TAR}" ] && [ -f "/var/tmp/rootfs.tar.zst" ]; then
  ROOTFS_TAR="/var/tmp/rootfs.tar.zst"
fi

echo "=========================================================="
echo "          PK-OS Bootable Disk Image Build (Phase 2B)      "
echo "=========================================================="
echo "  * Target Disk Image: ${FINAL_IMAGE}"
echo "  * Image Size:        ${IMAGE_SIZE}"
echo "  * Base Rootfs Tar:   ${ROOTFS_TAR}"
echo "  * Graphical Mode:    ${WITH_GRAPHICAL}"
echo "  * Partition Layout:  GPT (ESP: 256MB FAT32, Root: ext4)"
echo "  * Bootloader:        systemd-boot (UEFI BLS)"
echo "=========================================================="
echo ""

# 1. Validation & Pre-flight checks
if [ "$(id -u)" -ne 0 ]; then
  echo "ERROR: Root privileges required for loopback disk formatting and partitioning." >&2
  echo "Please run inside WSL with: wsl -d Ubuntu -u root ..." >&2
  exit 1
fi

REQUIRED_TOOLS=("parted" "mkfs.vfat" "mke2fs" "losetup" "sha256sum" "tar" "zstd")
for tool in "${REQUIRED_TOOLS[@]}"; do
  if ! command -v "${tool}" &>/dev/null; then
    echo "ERROR: Required tool '${tool}' is not installed." >&2
    exit 1
  fi
done

# Ensure output directory exists
mkdir -p "${OUTPUT_DIR}"

# Check available disk space on /var/tmp (require at least 4 GB free)
AVAIL_KB=$(df -P "/var/tmp" | awk 'NR==2 {print $4}')
if [ "${AVAIL_KB}" -lt 4194304 ]; then
  echo "ERROR: Less than 4 GB available on /var/tmp (${AVAIL_KB} KB free)." >&2
  exit 1
fi

# Ensure base rootfs exists, or build it
if [ ! -f "${ROOTFS_TAR}" ]; then
  echo "[INFO] Base rootfs archive not found. Triggering rootfs build..."
  if [ "${WITH_GRAPHICAL}" = true ]; then
    "${SCRIPT_DIR}/build-rootfs.sh" --format=tar --with-graphical
  else
    "${SCRIPT_DIR}/build-rootfs.sh" --format=tar
  fi
  if [ ! -f "${ROOTFS_TAR}" ]; then
    echo "ERROR: Base rootfs archive failed to build." >&2
    exit 1
  fi
fi

# 2. Create and Partition Raw Disk Image
echo "[1/4] Preparing raw disk image (${IMAGE_SIZE})..."
TMP_DIR="$(mktemp -d /var/tmp/pkos-img.XXXXXX)"
RAW_TMP="${TMP_DIR}/disk.raw"
MNT_ESP="${TMP_DIR}/mnt_esp"
MNT_ROOT="${TMP_DIR}/mnt_root"
mkdir -p "${MNT_ESP}" "${MNT_ROOT}"

LOOP_DEV=""
# shellcheck disable=SC2317
cleanup() {
  echo "  [CLEANUP] Performing safe teardown..."
  if [ -d "${MNT_ESP}" ] && mountpoint -q "${MNT_ESP}" 2>/dev/null; then
    umount -l "${MNT_ESP}" || true
  fi
  if [ -d "${MNT_ROOT}" ] && mountpoint -q "${MNT_ROOT}" 2>/dev/null; then
    umount -l "${MNT_ROOT}" || true
  fi
  if [ -n "${LOOP_DEV}" ] && losetup -a | grep -q "${LOOP_DEV}"; then
    losetup -d "${LOOP_DEV}" || true
  fi
  if [ -d "${TMP_DIR}" ]; then
    rm -rf "${TMP_DIR}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

# Allocate sparse image
truncate -s "${IMAGE_SIZE}" "${RAW_TMP}"

# Partition with parted (GPT)
parted -s "${RAW_TMP}" mklabel gpt
parted -s "${RAW_TMP}" mkpart ESP fat32 1MiB 257MiB
parted -s "${RAW_TMP}" set 1 esp on
parted -s "${RAW_TMP}" mkpart PKOS_ROOT ext4 257MiB 100%

# Attach loopback device with partition scanner
LOOP_DEV=$(losetup -Pf --show "${RAW_TMP}")
echo "  * Attached to: ${LOOP_DEV}"

sleep 1
PART_ESP="${LOOP_DEV}p1"
PART_ROOT="${LOOP_DEV}p2"

if [ ! -b "${PART_ESP}" ] || [ ! -b "${PART_ROOT}" ]; then
  echo "ERROR: Partition nodes (${PART_ESP}, ${PART_ROOT}) failed to generate." >&2
  exit 1
fi

# 3. Populate Root Partition directly from Rootfs Archive
echo "[2/4] Formatting & populating Root partition directly..."
mkfs.ext4 -F -L PKOS_ROOT "${PART_ROOT}"
mount "${PART_ROOT}" "${MNT_ROOT}"

echo "  * Extracting ${ROOTFS_TAR} directly into root partition..."
tar -I zstd -xpf "${ROOTFS_TAR}" -C "${MNT_ROOT}"

# Install Kernel & Modules
KERNEL_CACHE="/var/tmp/test-kernel-install"
if [ -d "${KERNEL_CACHE}/boot" ] && [ -n "$(find "${KERNEL_CACHE}/boot" -maxdepth 1 -name 'vmlinuz*' 2>/dev/null)" ]; then
  echo "[INFO] Copying pre-installed kernel & modules from ${KERNEL_CACHE}..."
  mkdir -p "${MNT_ROOT}/boot" "${MNT_ROOT}/usr/lib/modules" "${MNT_ROOT}/usr/lib/systemd/boot/efi"
  cp -a "${KERNEL_CACHE}/boot/"* "${MNT_ROOT}/boot/" 2>/dev/null || true
  if [ -d "${KERNEL_CACHE}/usr/lib/modules" ]; then
    cp -a "${KERNEL_CACHE}/usr/lib/modules/"* "${MNT_ROOT}/usr/lib/modules/" 2>/dev/null || true
  fi
  if [ -d "${KERNEL_CACHE}/usr/lib/systemd/boot/efi" ]; then
    cp -a "${KERNEL_CACHE}/usr/lib/systemd/boot/efi/"* "${MNT_ROOT}/usr/lib/systemd/boot/efi/" 2>/dev/null || true
  fi
else
  echo "[INFO] Installing Linux LTS kernel + systemd-boot in chroot..."
  mkdir -p "${MNT_ROOT}/etc/initramfs-tools/conf.d"
  echo "COMPRESS=gzip" > "${MNT_ROOT}/etc/initramfs-tools/conf.d/compress.conf"

  mount --bind /proc "${MNT_ROOT}/proc"
  mount --bind /sys "${MNT_ROOT}/sys"
  mount --bind /dev "${MNT_ROOT}/dev"
  mount --bind /dev/pts "${MNT_ROOT}/dev/pts"
  cp -L /etc/resolv.conf "${MNT_ROOT}/etc/resolv.conf"

  DEBIAN_FRONTEND=noninteractive chroot "${MNT_ROOT}" apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update -qq
  DEBIAN_FRONTEND=noninteractive chroot "${MNT_ROOT}" apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 install -y --no-install-recommends \
    linux-image-amd64 initramfs-tools systemd-boot systemd-boot-efi

  chroot "${MNT_ROOT}" apt-get clean
  rm -rf "${MNT_ROOT}/var/lib/apt/lists/"*

  umount -l "${MNT_ROOT}/dev/pts" || true
  umount -l "${MNT_ROOT}/dev" || true
  umount -l "${MNT_ROOT}/sys" || true
  umount -l "${MNT_ROOT}/proc" || true
fi

# Locate kernel and initrd
KERNEL_PATH=$(find "${MNT_ROOT}/boot" -maxdepth 1 -name 'vmlinuz*' | sort -V | tail -n 1)
INITRD_PATH=$(find "${MNT_ROOT}/boot" -maxdepth 1 -name 'initrd.img*' | sort -V | tail -n 1)
BOOTX64_SRC="${MNT_ROOT}/usr/lib/systemd/boot/efi/systemd-bootx64.efi"

if [ -z "${KERNEL_PATH}" ] || [ ! -f "${KERNEL_PATH}" ]; then
  echo "ERROR: Kernel binary (vmlinuz*) not found in ${MNT_ROOT}/boot" >&2
  exit 1
fi

if [ -z "${INITRD_PATH}" ] || [ ! -f "${INITRD_PATH}" ]; then
  echo "ERROR: Initramfs (initrd.img*) not found in ${MNT_ROOT}/boot" >&2
  exit 1
fi

if [ ! -f "${BOOTX64_SRC}" ]; then
  echo "ERROR: systemd-bootx64.efi not found in ${MNT_ROOT}" >&2
  exit 1
fi

echo "  * Kernel:   $(basename "${KERNEL_PATH}")"
echo "  * Initrd:   $(basename "${INITRD_PATH}")"
echo "  * EFI Bin:  $(basename "${BOOTX64_SRC}")"

# Configure rootfs fstab, issue banner, hostname and serial console
cat << 'EOF' > "${MNT_ROOT}/etc/fstab"
# /etc/fstab: static file system information for PK-OS
LABEL=PKOS_ROOT  /          ext4  errors=remount-ro,noatime  0  1
LABEL=PKOS_ESP   /boot/efi  vfat  umask=0077                 0  2
EOF

echo "PK-OS 0.1.0 LTS (\l)" > "${MNT_ROOT}/etc/issue"
echo "pk-os" > "${MNT_ROOT}/etc/hostname"
chroot "${MNT_ROOT}" passwd -d root 2>/dev/null || true

mkdir -p "${MNT_ROOT}/etc/systemd/system/getty.target.wants"
ln -sf /lib/systemd/system/serial-getty@.service \
  "${MNT_ROOT}/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"

# Sync latest shell, intelligence, and systemd units from workspace
echo "[INFO] Syncing latest PK-OS shell and intelligence libraries into rootfs..."
mkdir -p "${MNT_ROOT}/usr/lib/pk-os"
cp -r "${REPO_ROOT}/shell" "${MNT_ROOT}/usr/lib/pk-os/"
cp -r "${REPO_ROOT}/intelligence" "${MNT_ROOT}/usr/lib/pk-os/"

SYSTEMD_SYS_DIR="${MNT_ROOT}/lib/systemd/system"
mkdir -p "${SYSTEMD_SYS_DIR}"
cp "${REPO_ROOT}/shell/src/compositor/pk-session.service" "${SYSTEMD_SYS_DIR}/pk-session.service"
cp "${REPO_ROOT}/intelligence/src/pk-intelligenced.service" "${SYSTEMD_SYS_DIR}/pk-intelligenced.service"

mkdir -p "${MNT_ROOT}/etc/systemd/system/graphical.target.wants"
ln -sf /lib/systemd/system/pk-session.service \
  "${MNT_ROOT}/etc/systemd/system/graphical.target.wants/pk-session.service"
ln -sf /lib/systemd/system/pk-intelligenced.service \
  "${MNT_ROOT}/etc/systemd/system/graphical.target.wants/pk-intelligenced.service"

ln -sf /lib/systemd/system/graphical.target "${MNT_ROOT}/etc/systemd/system/default.target"

# Copy kernel artifacts needed for ESP staging before unmounting
TMP_ESP_STAGING="${TMP_DIR}/esp_staging"
mkdir -p "${TMP_ESP_STAGING}"
cp "${KERNEL_PATH}" "${TMP_ESP_STAGING}/vmlinuz"
cp "${INITRD_PATH}" "${TMP_ESP_STAGING}/initrd.img"
cp "${BOOTX64_SRC}" "${TMP_ESP_STAGING}/BOOTX64.EFI"

sync
umount "${MNT_ROOT}"
echo "  * Root partition populated and unmounted successfully."

# 4. Format & Populate ESP (FAT32)
echo "[3/4] Formatting & populating ESP (FAT32)..."
mkfs.vfat -F 32 -n PKOS_ESP "${PART_ESP}" >/dev/null
mount "${PART_ESP}" "${MNT_ESP}"

mkdir -p "${MNT_ESP}/EFI/BOOT"
mkdir -p "${MNT_ESP}/EFI/systemd"
mkdir -p "${MNT_ESP}/EFI/PKOS"
mkdir -p "${MNT_ESP}/loader/entries"

cp "${TMP_ESP_STAGING}/BOOTX64.EFI" "${MNT_ESP}/EFI/BOOT/BOOTX64.EFI"
cp "${TMP_ESP_STAGING}/BOOTX64.EFI" "${MNT_ESP}/EFI/systemd/systemd-bootx64.efi"

# Stage kernel & initramfs on ESP for systemd-boot
cp "${TMP_ESP_STAGING}/vmlinuz" "${MNT_ESP}/EFI/PKOS/vmlinuz"
cp "${TMP_ESP_STAGING}/initrd.img" "${MNT_ESP}/EFI/PKOS/initrd.img"
cp "${TMP_ESP_STAGING}/vmlinuz" "${MNT_ESP}/vmlinuz"
cp "${TMP_ESP_STAGING}/initrd.img" "${MNT_ESP}/initrd.img"

cat << 'EOF' > "${MNT_ESP}/loader/loader.conf"
default pkos.conf
timeout 3
console-mode max
editor no
EOF

cat << 'EOF' > "${MNT_ESP}/loader/entries/pkos.conf"
title PK-OS (0.1.0 LTS)
version 0.1.0
linux /EFI/PKOS/vmlinuz
initrd /EFI/PKOS/initrd.img
options root=LABEL=PKOS_ROOT rw console=tty0 console=ttyS0,115200 init=/lib/systemd/systemd systemd.show_status=1 systemd.journald.forward_to_console=1
EOF

sync
umount "${MNT_ESP}"
losetup -d "${LOOP_DEV}"
LOOP_DEV=""

# 4. Finalize Artifact
echo "[4/4] Finalizing disk image artifact..."
echo "  * Streaming artifact to host output..."
dd if="${RAW_TMP}" of="${FINAL_IMAGE}" bs=4M status=progress conv=fsync
sync
rm -f "${RAW_TMP}"
ln -sf "$(basename "${FINAL_IMAGE}")" "${LATEST_IMAGE}"

IMAGE_SIZE_MB=$(du -m "${FINAL_IMAGE}" | cut -f1)
IMAGE_SHA256=$(sha256sum "${FINAL_IMAGE}" | cut -d' ' -f1)
(cd "${OUTPUT_DIR}" && sha256sum "$(basename "${FINAL_IMAGE}")" >> "${OUTPUT_DIR}/SHA256SUMS")

echo ""
echo "=========================================================="
echo "          DISK IMAGE BUILD SUCCESSFUL (Milestone 1C)      "
echo "=========================================================="
echo "  * Artifact: ${FINAL_IMAGE}"
echo "  * Symlink:  ${LATEST_IMAGE}"
echo "  * Size:     ${IMAGE_SIZE_MB} MB"
echo "  * SHA256:   ${IMAGE_SHA256}"
echo "=========================================================="

exit 0
