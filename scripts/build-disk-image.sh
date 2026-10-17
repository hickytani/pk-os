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
    --help|-h)
      echo "Usage: $0 [--size=3G] [--output=path] [--rootfs-tar=path]"
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

echo "=========================================================="
echo "          PK-OS Bootable Disk Image Build (Phase 1C)      "
echo "=========================================================="
echo "  * Target Disk Image: ${FINAL_IMAGE}"
echo "  * Image Size:        ${IMAGE_SIZE}"
echo "  * Base Rootfs Tar:   ${ROOTFS_TAR}"
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

# Tune kernel writeback parameters to prevent host commit memory exhaustion during heavy disk I/O
sysctl -q -w vm.dirty_ratio=5 vm.dirty_background_ratio=2 vm.vfs_cache_pressure=200 2>/dev/null || true
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true

# Check available disk space on /var/tmp (require at least 4 GB free)
AVAIL_KB=$(df -P "/var/tmp" | awk 'NR==2 {print $4}')
if [ "${AVAIL_KB}" -lt 4194304 ]; then
  echo "ERROR: Less than 4 GB available on /var/tmp (${AVAIL_KB} KB free)." >&2
  exit 1
fi

# Ensure base rootfs exists, or build it
if [ ! -f "${ROOTFS_TAR}" ]; then
  echo "[INFO] Base rootfs archive not found. Triggering Milestone 1A rootfs build..."
  "${SCRIPT_DIR}/build-rootfs.sh" --format=tar
  if [ ! -f "${ROOTFS_TAR}" ]; then
    echo "ERROR: Base rootfs archive failed to build." >&2
    exit 1
  fi
fi

# 2. Prepare Rootfs Workspace with Kernel & Bootloader
ROOTFS_WORK="/var/tmp/pkos-rootfs-installed"
BUILD_KERNEL_ROOTFS=true

if [ -f "/var/tmp/test-kernel-install/boot/vmlinuz-6.1.0-50-amd64" ] && [ -f "/var/tmp/test-kernel-install/boot/initrd.img-6.1.0-50-amd64" ]; then
  ROOTFS_WORK="/var/tmp/test-kernel-install"
  echo "[INFO] Using existing verified kernel rootfs at ${ROOTFS_WORK}"
  BUILD_KERNEL_ROOTFS=false
elif [ -f "${ROOTFS_WORK}/boot/vmlinuz-6.1.0-50-amd64" ] && [ -f "${ROOTFS_WORK}/boot/initrd.img-6.1.0-50-amd64" ]; then
  echo "[INFO] Found existing verified kernel rootfs at ${ROOTFS_WORK}"
  BUILD_KERNEL_ROOTFS=false
fi

if [ "${BUILD_KERNEL_ROOTFS}" = true ]; then
  echo "[1/4] Preparing rootfs and installing Linux LTS kernel + systemd-boot..."
  rm -rf "${ROOTFS_WORK}"
  mkdir -p "${ROOTFS_WORK}"
  tar -I zstd -xpf "${ROOTFS_TAR}" -C "${ROOTFS_WORK}"

  # Configure initramfs to use gzip compression
  mkdir -p "${ROOTFS_WORK}/etc/initramfs-tools/conf.d"
  echo "COMPRESS=gzip" > "${ROOTFS_WORK}/etc/initramfs-tools/conf.d/compress.conf"

  # Bind mount for chroot package installation
  mount --bind /proc "${ROOTFS_WORK}/proc"
  mount --bind /sys "${ROOTFS_WORK}/sys"
  mount --bind /dev "${ROOTFS_WORK}/dev"
  mount --bind /dev/pts "${ROOTFS_WORK}/dev/pts"
  cp -L /etc/resolv.conf "${ROOTFS_WORK}/etc/resolv.conf"

  # Install kernel and bootloader with IPv4 constraint to prevent GeoDNS timeouts
  DEBIAN_FRONTEND=noninteractive chroot "${ROOTFS_WORK}" apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 update -qq
  DEBIAN_FRONTEND=noninteractive chroot "${ROOTFS_WORK}" apt-get -o Acquire::ForceIPv4=true -o Acquire::Retries=3 install -y --no-install-recommends \
    linux-image-amd64 initramfs-tools systemd-boot systemd-boot-efi

  # Clean caches
  chroot "${ROOTFS_WORK}" apt-get clean
  rm -rf "${ROOTFS_WORK}/var/lib/apt/lists/"*

  # Unmount bind mounts
  umount -l "${ROOTFS_WORK}/dev/pts" || true
  umount -l "${ROOTFS_WORK}/dev" || true
  umount -l "${ROOTFS_WORK}/sys" || true
  umount -l "${ROOTFS_WORK}/proc" || true
fi

# Locate kernel and initrd
KERNEL_PATH=$(find "${ROOTFS_WORK}/boot" -maxdepth 1 -name 'vmlinuz*' | sort -V | tail -n 1)
INITRD_PATH=$(find "${ROOTFS_WORK}/boot" -maxdepth 1 -name 'initrd.img*' | sort -V | tail -n 1)
BOOTX64_SRC="${ROOTFS_WORK}/usr/lib/systemd/boot/efi/systemd-bootx64.efi"

if [ -z "${KERNEL_PATH}" ] || [ ! -f "${KERNEL_PATH}" ]; then
  echo "ERROR: Kernel binary (vmlinuz*) not found in ${ROOTFS_WORK}/boot" >&2
  exit 1
fi

if [ -z "${INITRD_PATH}" ] || [ ! -f "${INITRD_PATH}" ]; then
  echo "ERROR: Initramfs (initrd.img*) not found in ${ROOTFS_WORK}/boot" >&2
  exit 1
fi

if [ ! -f "${BOOTX64_SRC}" ]; then
  echo "ERROR: systemd-bootx64.efi not found in ${ROOTFS_WORK}" >&2
  exit 1
fi

echo "  * Kernel:   $(basename "${KERNEL_PATH}")"
echo "  * Initrd:   $(basename "${INITRD_PATH}")"
echo "  * EFI Bin:  $(basename "${BOOTX64_SRC}")"

# Configure rootfs fstab, issue banner, hostname and serial console
cat << 'EOF' > "${ROOTFS_WORK}/etc/fstab"
# /etc/fstab: static file system information for PK-OS
LABEL=PKOS_ROOT  /          ext4  errors=remount-ro,noatime  0  1
LABEL=PKOS_ESP   /boot/efi  vfat  umask=0077                 0  2
EOF

echo "PK-OS 0.1.0 LTS (\l)" > "${ROOTFS_WORK}/etc/issue"
echo "pk-os" > "${ROOTFS_WORK}/etc/hostname"
chroot "${ROOTFS_WORK}" passwd -d root 2>/dev/null || true

mkdir -p "${ROOTFS_WORK}/etc/systemd/system/getty.target.wants"
ln -sf /lib/systemd/system/serial-getty@.service \
  "${ROOTFS_WORK}/etc/systemd/system/getty.target.wants/serial-getty@ttyS0.service"

# 3. Create and Partition Raw Disk Image
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
    rm -rf "${TMP_DIR}"
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

# Format filesystems
echo "[3/4] Populating Root partition via mount + rsync..."
mkfs.ext4 -F -L PKOS_ROOT "${PART_ROOT}"
mount "${PART_ROOT}" "${MNT_ROOT}"
rsync -aHAX --numeric-ids "${ROOTFS_WORK}/" "${MNT_ROOT}/"
sync
echo 3 > /proc/sys/vm/drop_caches 2>/dev/null || true
umount "${MNT_ROOT}"
echo "  * Root partition populated successfully."

echo "  * Formatting ESP (FAT32) -> ${PART_ESP}..."
mkfs.vfat -F 32 -n PKOS_ESP "${PART_ESP}" >/dev/null

# Stage bootloader and kernel on ESP
mount "${PART_ESP}" "${MNT_ESP}"

mkdir -p "${MNT_ESP}/EFI/BOOT"
mkdir -p "${MNT_ESP}/EFI/systemd"
mkdir -p "${MNT_ESP}/EFI/PKOS"
mkdir -p "${MNT_ESP}/loader/entries"

cp "${BOOTX64_SRC}" "${MNT_ESP}/EFI/BOOT/BOOTX64.EFI"
cp "${BOOTX64_SRC}" "${MNT_ESP}/EFI/systemd/systemd-bootx64.efi"

# Stage kernel & initramfs on ESP for systemd-boot
cp "${KERNEL_PATH}" "${MNT_ESP}/EFI/PKOS/vmlinuz"
cp "${INITRD_PATH}" "${MNT_ESP}/EFI/PKOS/initrd.img"
cp "${KERNEL_PATH}" "${MNT_ESP}/vmlinuz"
cp "${INITRD_PATH}" "${MNT_ESP}/initrd.img"

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
echo "  * Streaming artifact to host output with dsync..."
dd if="${RAW_TMP}" of="${FINAL_IMAGE}" bs=2M status=progress oflag=dsync conv=fsync
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
