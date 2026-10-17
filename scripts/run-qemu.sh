#!/usr/bin/env bash
# scripts/run-qemu.sh — Run and verify PK-OS disk image in QEMU (Milestone 1D)
# Usage: ./scripts/run-qemu.sh [--image=path] [--test] [--timeout=90] [--memory=1024]

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

OUTPUT_DIR="${REPO_ROOT}/build/output"
DISK_IMAGE="${OUTPUT_DIR}/pk-os-dev.raw"
TEST_MODE=false
TIMEOUT_SECS=90
MEM_MB=1024
SMP_CORES=2

for arg in "$@"; do
  case "$arg" in
    --image=*)
      DISK_IMAGE="${arg#*=}"
      ;;
    --test)
      TEST_MODE=true
      ;;
    --timeout=*)
      TIMEOUT_SECS="${arg#*=}"
      ;;
    --memory=*)
      MEM_MB="${arg#*=}"
      ;;
    --smp=*)
      SMP_CORES="${arg#*=}"
      ;;
    --help|-h)
      echo "Usage: $0 [--image=path] [--test] [--timeout=90] [--memory=1024]"
      exit 0
      ;;
    *)
      echo "ERROR: Unknown argument: $arg" >&2
      exit 1
      ;;
  esac
done

echo "=========================================================="
echo "          PK-OS QEMU Virtual Machine Runner (Phase 1D)    "
echo "=========================================================="
echo "  * Disk Image:   ${DISK_IMAGE}"
echo "  * Test Mode:    ${TEST_MODE}"
echo "  * Memory:       ${MEM_MB} MB"
echo "  * CPU Cores:    ${SMP_CORES}"
echo "=========================================================="

# 1. Pre-flight checks
if [ ! -f "${DISK_IMAGE}" ]; then
  echo "ERROR: Disk image not found at '${DISK_IMAGE}'" >&2
  echo "Run ./scripts/build-disk-image.sh first." >&2
  exit 1
fi

if ! command -v qemu-system-x86_64 &>/dev/null; then
  echo "ERROR: qemu-system-x86_64 is not installed." >&2
  exit 1
fi

# Locate OVMF firmware
OVMF_CODE=""
OVMF_VARS=""

if [ -f "/usr/share/OVMF/OVMF_CODE_4M.fd" ] && [ -f "/usr/share/OVMF/OVMF_VARS_4M.fd" ]; then
  OVMF_CODE="/usr/share/OVMF/OVMF_CODE_4M.fd"
  OVMF_VARS="/usr/share/OVMF/OVMF_VARS_4M.fd"
elif [ -f "/usr/share/OVMF/OVMF_CODE.fd" ] && [ -f "/usr/share/OVMF/OVMF_VARS.fd" ]; then
  OVMF_CODE="/usr/share/OVMF/OVMF_CODE.fd"
  OVMF_VARS="/usr/share/OVMF/OVMF_VARS.fd"
elif [ -f "/usr/share/qemu/OVMF.fd" ]; then
  OVMF_CODE="/usr/share/qemu/OVMF.fd"
fi

if [ -z "${OVMF_CODE}" ]; then
  echo "ERROR: UEFI OVMF firmware not found." >&2
  exit 1
fi

# Disposable UEFI VARS in temp directory
TMP_QEMU="$(mktemp -d /var/tmp/pkos-qemu.XXXXXX)"
# shellcheck disable=SC2317
cleanup() {
  if [ -d "${TMP_QEMU}" ]; then
    rm -rf "${TMP_QEMU}"
  fi
}
trap cleanup EXIT INT TERM

QEMU_ARGS=()

# Acceleration check
if [ -r "/dev/kvm" ] && [ -w "/dev/kvm" ]; then
  echo "  * Hardware Acceleration: KVM (Enabled)"
  QEMU_ARGS+=("-enable-kvm" "-cpu" "host")
else
  echo "  * Hardware Acceleration: Software TCG (Emulation)"
  QEMU_ARGS+=("-accel" "tcg" "-cpu" "max")
fi

# Firmware setup
if [ -n "${OVMF_VARS}" ]; then
  VARS_COPY="${TMP_QEMU}/OVMF_VARS.fd"
  cp "${OVMF_VARS}" "${VARS_COPY}"
  QEMU_ARGS+=(
    "-drive" "if=pflash,format=raw,unit=0,file=${OVMF_CODE},readonly=on"
    "-drive" "if=pflash,format=raw,unit=1,file=${VARS_COPY}"
  )
else
  QEMU_ARGS+=("-bios" "${OVMF_CODE}")
fi

# VM configuration
QEMU_ARGS+=(
  "-m" "${MEM_MB}"
  "-smp" "${SMP_CORES}"
  "-drive" "file=${DISK_IMAGE},format=raw,if=virtio"
  "-no-reboot"
)

if [ "${TEST_MODE}" = true ]; then
  QEMU_ARGS+=("-snapshot")
fi

# 2. Execution
BOOT_LOG="${OUTPUT_DIR}/qemu-boot.log"

if [ "${TEST_MODE}" = false ]; then
  echo "[ACTION] Launching interactive QEMU session (Press Ctrl-A X to exit)..."
  qemu-system-x86_64 "${QEMU_ARGS[@]}" -nographic -serial mon:stdio
  exit 0
else
  echo "[ACTION] Running automated boot smoke test (Timeout: ${TIMEOUT_SECS}s)..."
  rm -f "${BOOT_LOG}"
  : > "${BOOT_LOG}"
  
  # Start QEMU in background writing serial port to BOOT_LOG
  qemu-system-x86_64 "${QEMU_ARGS[@]}" -nographic -serial "file:${BOOT_LOG}" &
  QEMU_PID=$!

  echo "  * QEMU PID: ${QEMU_PID}"
  echo "  * Logging serial console to: ${BOOT_LOG}"

  START_TIME=$(date +%s)
  BOOT_SUCCESS=false

  while true; do
    CURRENT_TIME=$(date +%s)
    ELAPSED=$(( CURRENT_TIME - START_TIME ))

    if [ "${ELAPSED}" -ge "${TIMEOUT_SECS}" ]; then
      echo "  [TIMEOUT] Boot acceptance target not reached within ${TIMEOUT_SECS}s." >&2
      break
    fi

    # Check if QEMU died unexpectedly
    if ! kill -0 "${QEMU_PID}" 2>/dev/null; then
      echo "  [FAIL] QEMU process terminated unexpectedly." >&2
      break
    fi

    # Check for login prompt milestone in serial log
    if grep -q "pk-os login:" "${BOOT_LOG}" 2>/dev/null; then
      BOOT_SUCCESS=true
      echo "  [MILESTONE REACHED] System successfully reached userspace login prompt!"
      break
    fi

    sleep 1
  done

  # Graceful kill of QEMU
  kill "${QEMU_PID}" 2>/dev/null || true
  wait "${QEMU_PID}" 2>/dev/null || true

  echo ""
  echo "=========================================================="
  echo "                 BOOT TEST AUDIT REPORT                   "
  echo "=========================================================="
  
  # Audit milestones reached in serial log
  echo "Audit Checkpoints:"
  KERNEL_OK=false
  SYSTEMD_OK=false
  LOGIN_OK=false

  if grep -qi "systemd-boot" "${BOOT_LOG}" 2>/dev/null; then
    echo "  [PASS] Bootloader: systemd-boot detected"
  else
    echo "  [INFO] Bootloader banner: skipped or direct"
  fi

  if grep -qi "Linux version" "${BOOT_LOG}" 2>/dev/null; then
    KERNEL_VER=$(grep -i "Linux version" "${BOOT_LOG}" | head -n 1)
    echo "  [PASS] Kernel: ${KERNEL_VER}"
    KERNEL_OK=true
  else
    echo "  [FAIL] Kernel load marker not detected"
  fi

  if grep -qi "systemd.*running in system mode" "${BOOT_LOG}" 2>/dev/null || grep -qi "Welcome to PK-OS" "${BOOT_LOG}" 2>/dev/null; then
    echo "  [PASS] Init System: systemd started in system mode"
    SYSTEMD_OK=true
  else
    echo "  [FAIL] systemd initialization marker not detected"
  fi

  if grep -qi "Reached target" "${BOOT_LOG}" 2>/dev/null; then
    TARGET_COUNT=$(grep -ci "Reached target" "${BOOT_LOG}")
    echo "  [PASS] Systemd Targets: ${TARGET_COUNT} targets reached"
  fi

  if [ "${BOOT_SUCCESS}" = true ] && grep -q "pk-os login:" "${BOOT_LOG}" 2>/dev/null; then
    echo "  [PASS] Userspace Target: Login prompt reached (pk-os login:)"
    LOGIN_OK=true
  else
    echo "  [FAIL] Userspace Target: Login prompt NOT reached."
  fi

  echo "=========================================================="
  if [ "${KERNEL_OK}" = true ] && [ "${SYSTEMD_OK}" = true ] && [ "${LOGIN_OK}" = true ]; then
    echo "               ALL BOOT GATES PASSED (Exit Code 0)        "
    echo "=========================================================="
    exit 0
  else
    echo "                 BOOT TEST FAILED (Exit Code 1)           "
    echo "=========================================================="
    echo ""
    echo "Last 30 lines of serial console log:"
    tail -n 30 "${BOOT_LOG}" 2>/dev/null || true
    exit 1
  fi
fi
