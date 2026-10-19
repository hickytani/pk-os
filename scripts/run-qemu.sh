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
GRAPHICAL_MODE=false
PREVIEW_MODE=false

SNAPSHOT_MODE=false

for arg in "$@"; do
  case "$arg" in
    --image=*)
      DISK_IMAGE="${arg#*=}"
      ;;
    --test)
      TEST_MODE=true
      ;;
    --graphical)
      GRAPHICAL_MODE=true
      ;;
    --preview)
      GRAPHICAL_MODE=true
      PREVIEW_MODE=true
      ;;
    --snapshot)
      SNAPSHOT_MODE=true
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
      echo "Usage: $0 [--image=path] [--test] [--graphical] [--preview] [--snapshot] [--timeout=90] [--memory=1024]"
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
echo "  * Graphical:    ${GRAPHICAL_MODE}"
echo "  * Preview:      ${PREVIEW_MODE}"
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

if [ "${PREVIEW_MODE}" = true ]; then
  if ! command -v websockify &>/dev/null; then
    echo "ERROR: websockify is not installed. Required for --preview." >&2
    echo "Install with: sudo apt-get install -y websockify" >&2
    exit 1
  fi
  if [ ! -d "/usr/share/novnc" ]; then
    echo "ERROR: /usr/share/novnc directory not found. Required for --preview." >&2
    echo "Install with: sudo apt-get install -y novnc" >&2
    exit 1
  fi
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
NOVNC_PID=""
# shellcheck disable=SC2317
cleanup() {
  if [ -n "${NOVNC_PID}" ]; then
    kill "${NOVNC_PID}" 2>/dev/null || true
  fi
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

if [ "${TEST_MODE}" = true ] || [ "${SNAPSHOT_MODE}" = true ]; then
  QEMU_ARGS+=("-snapshot")
fi

# 2. Execution
BOOT_LOG="${OUTPUT_DIR}/qemu-boot.log"
MONITOR_SOCK="${TMP_QEMU}/monitor.sock"
SCREENSHOT_PPM="${OUTPUT_DIR}/qemu-graphical-boot.ppm"
VERIFY_JSON="${OUTPUT_DIR}/screenshot-verification.json"
WEBSOCKIFY_LOG="${OUTPUT_DIR}/websockify.log"

if [ "${GRAPHICAL_MODE}" = true ]; then
  echo "  * Display Mode: Graphical (virtio-vga, VNC :99, QEMU Monitor)"
  QEMU_ARGS+=(
    "-device" "virtio-vga"
    "-display" "none"
    "-vnc" "0.0.0.0:99"
    "-monitor" "unix:${MONITOR_SOCK},server,nowait"
  )
else
  echo "  * Display Mode: Headless Serial Console (-nographic)"
  QEMU_ARGS+=("-nographic" "-monitor" "none")
fi

if [ "${TEST_MODE}" = false ]; then
  if [ "${GRAPHICAL_MODE}" = true ]; then
    if [ "${PREVIEW_MODE}" = true ]; then
      echo "  * Starting noVNC proxy on port 6080..."
      websockify --web /usr/share/novnc 0.0.0.0:6080 127.0.0.1:5999 > "${WEBSOCKIFY_LOG}" 2>&1 &
      NOVNC_PID=$!
    fi

    SERIAL_ARGS=("-serial" "mon:stdio")
    if [ ! -t 0 ] || [ "${PREVIEW_MODE}" = true ]; then
      SERIAL_ARGS=("-serial" "file:${BOOT_LOG}")
    fi

    if [ "${PREVIEW_MODE}" = true ]; then
      echo "  * Launching PK-OS virtual machine in background..."
      qemu-system-x86_64 "${QEMU_ARGS[@]}" "${SERIAL_ARGS[@]}" &
      QEMU_PID=$!

      echo "  * Verifying VNC backend (:5999) and noVNC proxy (:6080) endpoint reachability..."
      VERIFIED=false
      for _ in $(seq 1 30); do
        if ! kill -0 "${QEMU_PID}" 2>/dev/null; then
          echo "ERROR: QEMU terminated unexpectedly during launch. Check ${BOOT_LOG}" >&2
          exit 1
        fi
        if ! kill -0 "${NOVNC_PID}" 2>/dev/null; then
          echo "ERROR: websockify terminated unexpectedly. Check ${WEBSOCKIFY_LOG}" >&2
          exit 1
        fi
        if python3 -c "
import socket, urllib.request
s = socket.socket()
s.settimeout(0.5)
s.connect(('127.0.0.1', 5999))
s.close()
res = urllib.request.urlopen('http://127.0.0.1:6080/vnc.html', timeout=0.5)
assert res.status == 200
" 2>/dev/null; then
          VERIFIED=true
          break
        fi
        sleep 0.5
      done

      if [ "${VERIFIED}" = false ]; then
        echo "ERROR: Endpoints failed reachability verification within 15 seconds." >&2
        kill "${QEMU_PID}" 2>/dev/null || true
        exit 1
      fi

      echo ""
      echo "========================================================================"
      echo "         PK-OS INTERACTIVE DESKTOP PREVIEW READY                        "
      echo "========================================================================"
      echo "  * VNC Backend:   127.0.0.1:5999 (Verified Active)"
      echo "  * noVNC Service: 127.0.0.1:6080 (Verified Active)"
      echo ""
      echo "  Open your web browser on Windows to see and interact with PK-OS:"
      echo "    http://127.0.0.1:6080/vnc.html?autoconnect=true&resize=scale"
      echo "    http://localhost:6080/vnc.html?autoconnect=true&resize=scale"
      echo ""
      echo "  Or connect using any standard VNC viewer:"
      echo "    127.0.0.1:5999"
      echo ""
      echo "  HOW TO SAFELY EXIT AND RETURN TO WINDOWS:"
      echo "    1. GUEST SHUTDOWN (Recommended):"
      echo "       Click 'Shut Down PK-OS' in the top status bar or in Settings."
      echo "       This cleanly stops services, flushes disks, and powers off the VM."
      echo "    2. HOST TERMINAL EXIT:"
      echo "       Press 'Ctrl-C' in this terminal to exit QEMU safely."
      echo "========================================================================"
      echo ""

      wait "${QEMU_PID}" 2>/dev/null || true
      if [ -n "${NOVNC_PID}" ]; then
        kill "${NOVNC_PID}" 2>/dev/null || true
      fi
    else
      echo "[ACTION] Launching interactive graphical QEMU session..."
      qemu-system-x86_64 "${QEMU_ARGS[@]}" "${SERIAL_ARGS[@]}"
    fi
  else
    echo "[ACTION] Launching interactive QEMU session (Press Ctrl-A X to exit)..."
    SERIAL_ARGS=("-serial" "mon:stdio")
    if [ ! -t 0 ]; then
      SERIAL_ARGS=("-serial" "file:${BOOT_LOG}")
    fi
    qemu-system-x86_64 "${QEMU_ARGS[@]}" "${SERIAL_ARGS[@]}"
  fi
  exit 0
else
  echo "[ACTION] Running automated boot verification test (Timeout: ${TIMEOUT_SECS}s)..."
  rm -f "${BOOT_LOG}" "${SCREENSHOT_PPM}" "${VERIFY_JSON}"
  : > "${BOOT_LOG}"

  # Start QEMU in background writing serial console to BOOT_LOG
  qemu-system-x86_64 "${QEMU_ARGS[@]}" -serial "file:${BOOT_LOG}" &
  QEMU_PID=$!

  echo "  * QEMU PID: ${QEMU_PID}"
  echo "  * Logging serial console to: ${BOOT_LOG}"

  START_TIME=$(date +%s)
  BOOT_SUCCESS=false
  GRAPHICAL_SESSION_STARTED=false

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

    # Check for graphical session milestones in serial/journal
    if grep -qi "Started PK-OS Graphical Shell Session" "${BOOT_LOG}" 2>/dev/null || \
       grep -qi "pk-session" "${BOOT_LOG}" 2>/dev/null; then
      GRAPHICAL_SESSION_STARTED=true
    fi

    # Check for login prompt milestone
    if grep -q "pk-os login:" "${BOOT_LOG}" 2>/dev/null; then
      BOOT_SUCCESS=true
      if [ "${GRAPHICAL_MODE}" = false ]; then
        echo "  [MILESTONE REACHED] System successfully reached userspace login prompt!"
        break
      elif [ "${GRAPHICAL_SESSION_STARTED}" = true ] || [ "${ELAPSED}" -ge 20 ]; then
        echo "  [MILESTONE REACHED] System reached userspace with graphical services active!"
        break
      fi
    fi

    sleep 1
  done

  # In graphical mode, capture QEMU framebuffer screendump via monitor socket
  SCREENSHOT_CAPTURED=false
  SCREENSHOT_VERIFIED=false
  if [ "${GRAPHICAL_MODE}" = true ] && [ -S "${MONITOR_SOCK}" ]; then
    echo "[ACTION] Capturing QEMU framebuffer screendump via monitor..."
    sleep 18  # allow cage + GTK3 compositor to draw first frame
    python3 -c "
import socket, time
try:
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.connect('${MONITOR_SOCK}')
    time.sleep(0.5)
    s.sendall(b'screendump ${SCREENSHOT_PPM}\n')
    time.sleep(1.0)
    s.close()
except Exception as e:
    print(f'Screendump error: {e}')
" 2>/dev/null || true

    if [ -f "${SCREENSHOT_PPM}" ] && [ -s "${SCREENSHOT_PPM}" ]; then
      SCREENSHOT_CAPTURED=true
      echo "  * Screendump captured: ${SCREENSHOT_PPM}"
      # Run visual verification analysis
      if python3 "${SCRIPT_DIR}/verify-screenshot.py" "${SCREENSHOT_PPM}" > "${VERIFY_JSON}" 2>&1; then
        SCREENSHOT_VERIFIED=true
        echo "  [PASS] Framebuffer visual verification PASSED!"
      else
        echo "  [WARN] Framebuffer visual verification reported anomaly (see ${VERIFY_JSON})"
      fi
    fi
  fi

  # Graceful kill of QEMU
  kill "${QEMU_PID}" 2>/dev/null || true
  wait "${QEMU_PID}" 2>/dev/null || true

  echo ""
  echo "=========================================================="
  echo "                 BOOT TEST AUDIT REPORT                   "
  echo "=========================================================="
  
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

  if [ "${GRAPHICAL_MODE}" = true ]; then
    echo "Graphical Session Audit:"
    if [ "${GRAPHICAL_SESSION_STARTED}" = true ] || grep -qi "pk-session" "${BOOT_LOG}" 2>/dev/null; then
      echo "  [PASS] Compositor Service: pk-session.service detected"
    else
      echo "  [INFO] Compositor Service: started or queued"
    fi

    if [ "${SCREENSHOT_CAPTURED}" = true ]; then
      echo "  [PASS] Framebuffer Capture: ${SCREENSHOT_PPM} ($(stat -c%s "${SCREENSHOT_PPM}" 2>/dev/null || du -b "${SCREENSHOT_PPM}" | cut -f1) bytes)"
      if [ -f "${VERIFY_JSON}" ]; then
        echo "  [REPORT] Verification Results:"
        sed 's/^/    /' "${VERIFY_JSON}"
      fi
    else
      echo "  [FAIL] Framebuffer Capture: No screendump produced."
    fi
  fi

  echo "=========================================================="
  OVERALL_PASS=false
  if [ "${GRAPHICAL_MODE}" = true ]; then
    if [ "${KERNEL_OK}" = true ] && [ "${SYSTEMD_OK}" = true ] && [ "${SCREENSHOT_CAPTURED}" = true ] && [ "${SCREENSHOT_VERIFIED}" = true ]; then
      OVERALL_PASS=true
    fi
  else
    if [ "${KERNEL_OK}" = true ] && [ "${SYSTEMD_OK}" = true ] && [ "${LOGIN_OK}" = true ]; then
      OVERALL_PASS=true
    fi
  fi

  if [ "${OVERALL_PASS}" = true ]; then
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
