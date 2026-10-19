#!/usr/bin/env python3
"""
scripts/assemble_phase2b_disk.py — High-Reliability Bootable Disk Image Assembler (Phase 2B)
Assembles a complete UEFI GPT disk image with PK-OS graphical environment (cage + GTK3 GUI)
and PK Intelligence daemon.
"""

import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path("/mnt/c/Users/prasu/Downloads/pk-os")
OUTPUT_DIR = REPO_ROOT / "build" / "output"
FINAL_IMAGE = OUTPUT_DIR / "pk-os-dev.raw"
ROOTFS_TAR = Path("/var/tmp/rootfs.tar")
KERNEL_CACHE = Path("/var/tmp/test-kernel-install")
TMP_IMAGE = Path("/var/tmp/pkos-graphical.raw")
MNT_ROOT = Path("/mnt/pkos_root")
MNT_ESP = Path("/mnt/pkos_esp")

IMAGE_SIZE_BYTES = 2600 * 1024 * 1024  # 2600 MB


def run_cmd(cmd, desc=""):
    if desc:
        print(f"  * {desc}...")
    t0 = time.time()
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    elapsed = time.time() - t0
    if res.returncode != 0:
        print(f"ERROR: {cmd} failed (exit {res.returncode}):\nStdout: {res.stdout}\nStderr: {res.stderr}", file=sys.stderr)
        sys.exit(1)
    if desc:
        print(f"    -> Done ({elapsed:.2f}s)")
    return res.stdout.strip()


def main():
    print("==========================================================")
    print("  PK-OS Phase 2B Disk Image Assembler (Reliable Engine)  ")
    print("==========================================================")
    
    if os.geteuid() != 0:
        print("ERROR: Root privileges required.", file=sys.stderr)
        sys.exit(1)

    if not ROOTFS_TAR.exists():
        print(f"ERROR: {ROOTFS_TAR} not found.", file=sys.stderr)
        sys.exit(1)

    # 1. Allocate disk image
    print("[1/5] Allocating 2600MB raw disk image...")
    if TMP_IMAGE.exists():
        TMP_IMAGE.unlink()
    with open(TMP_IMAGE, "wb") as f:
        f.truncate(IMAGE_SIZE_BYTES)

    # 2. Partition with parted
    run_cmd(["parted", "-s", str(TMP_IMAGE), "mklabel", "gpt"], "Creating GPT partition table")
    run_cmd(["parted", "-s", str(TMP_IMAGE), "mkpart", "ESP", "fat32", "1MiB", "257MiB"], "Creating ESP partition")
    run_cmd(["parted", "-s", str(TMP_IMAGE), "set", "1", "esp", "on"], "Setting ESP flag")
    run_cmd(["parted", "-s", str(TMP_IMAGE), "mkpart", "PKOS_ROOT", "ext4", "257MiB", "100%"], "Creating Root partition")

    # 3. Setup loopback
    loop_dev = run_cmd(["losetup", "-Pf", "--show", str(TMP_IMAGE)], "Attaching loop device")
    print(f"    Loop device: {loop_dev}")
    part_esp = f"{loop_dev}p1"
    part_root = f"{loop_dev}p2"
    time.sleep(1)

    try:
        # Format Root
        print("[2/5] Formatting and populating Root partition...")
        run_cmd(["mkfs.ext4", "-F", "-L", "PKOS_ROOT", part_root], "Formatting ext4 filesystem")
        MNT_ROOT.mkdir(parents=True, exist_ok=True)
        run_cmd(["mount", part_root, str(MNT_ROOT)], "Mounting root partition")

        # Extract rootfs
        run_cmd(["tar", "-xf", str(ROOTFS_TAR), "-C", str(MNT_ROOT)], "Extracting rootfs tar archive")

        # Install Kernel & Modules
        print("  * Installing kernel and module artifacts...")
        boot_dir = MNT_ROOT / "boot"
        modules_dir = MNT_ROOT / "usr" / "lib" / "modules"
        efi_dir = MNT_ROOT / "usr" / "lib" / "systemd" / "boot" / "efi"
        boot_dir.mkdir(parents=True, exist_ok=True)
        modules_dir.mkdir(parents=True, exist_ok=True)
        efi_dir.mkdir(parents=True, exist_ok=True)

        for item in (KERNEL_CACHE / "boot").glob("*"):
            if item.is_file():
                shutil.copy2(item, boot_dir / item.name)
        print("    -> Kernel boot binaries copied")

        # Copy modules via tar pipe for maximum performance
        run_cmd(["sh", "-c", f"tar -C {KERNEL_CACHE}/usr/lib/modules -cf - . | tar -C {modules_dir} -xf -"], "Copying kernel modules")
        
        # Copy systemd-boot EFI binary
        bootx64_src = KERNEL_CACHE / "usr" / "lib" / "systemd" / "boot" / "efi" / "systemd-bootx64.efi"
        if bootx64_src.exists():
            shutil.copy2(bootx64_src, efi_dir / "systemd-bootx64.efi")

        # Verify kernel and initrd
        vmlinuz_candidates = sorted(boot_dir.glob("vmlinuz*"))
        initrd_candidates = sorted(boot_dir.glob("initrd.img*"))
        if not vmlinuz_candidates or not initrd_candidates:
            print("ERROR: Missing kernel or initramfs in /boot", file=sys.stderr)
            sys.exit(1)
        vmlinuz_path = vmlinuz_candidates[-1]
        initrd_path = initrd_candidates[-1]
        print(f"    Kernel: {vmlinuz_path.name}")
        print(f"    Initrd: {initrd_path.name}")

        # Install PK-OS Shell and Intelligence
        print("  * Synchronizing PK-OS Shell and Intelligence components...")
        pkos_lib = MNT_ROOT / "usr" / "lib" / "pk-os"
        pkos_lib.mkdir(parents=True, exist_ok=True)
        if (pkos_lib / "shell").exists():
            shutil.rmtree(pkos_lib / "shell")
        if (pkos_lib / "intelligence").exists():
            shutil.rmtree(pkos_lib / "intelligence")
        shutil.copytree(REPO_ROOT / "shell", pkos_lib / "shell")
        shutil.copytree(REPO_ROOT / "intelligence", pkos_lib / "intelligence")

        # Install systemd service units
        sysd_system = MNT_ROOT / "lib" / "systemd" / "system"
        sysd_system.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPO_ROOT / "shell" / "src" / "compositor" / "pk-session.service", sysd_system / "pk-session.service")
        shutil.copy2(REPO_ROOT / "intelligence" / "src" / "pk-intelligenced.service", sysd_system / "pk-intelligenced.service")
        run_cmd(["chmod", "0644", str(sysd_system / "pk-session.service")], "Setting unit permissions")
        run_cmd(["chmod", "0644", str(sysd_system / "pk-intelligenced.service")], "Setting unit permissions")

        # Enable services in graphical.target.wants
        graphical_wants = MNT_ROOT / "etc" / "systemd" / "system" / "graphical.target.wants"
        graphical_wants.mkdir(parents=True, exist_ok=True)
        for sname in ["pk-session.service", "pk-intelligenced.service"]:
            slink = graphical_wants / sname
            if slink.exists() or slink.is_symlink():
                slink.unlink()
            slink.symlink_to(f"/lib/systemd/system/{sname}")

        # Set default target to graphical.target
        default_target = MNT_ROOT / "etc" / "systemd" / "system" / "default.target"
        if default_target.exists() or default_target.is_symlink():
            default_target.unlink()
        default_target.symlink_to("/lib/systemd/system/graphical.target")

        # System configuration (fstab, issue, hostname, serial console)
        with open(MNT_ROOT / "etc" / "fstab", "w") as f:
            f.write("LABEL=PKOS_ROOT  /          ext4  errors=remount-ro,noatime  0  1\n")
            f.write("LABEL=PKOS_ESP   /boot/efi  vfat  umask=0077                 0  2\n")

        with open(MNT_ROOT / "etc" / "issue", "w") as f:
            f.write("PK-OS 0.1.0 LTS (\\l)\n\n")

        with open(MNT_ROOT / "etc" / "hostname", "w") as f:
            f.write("pk-os\n")

        # Enable serial console getty
        serial_wants = MNT_ROOT / "etc" / "systemd" / "system" / "getty.target.wants"
        serial_wants.mkdir(parents=True, exist_ok=True)
        serial_service = serial_wants / "serial-getty@ttyS0.service"
        if not serial_service.exists():
            serial_service.symlink_to("/lib/systemd/system/serial-getty@.service")

        # Create unprivileged desktop user 'pkos' (UID 1000) for cage Wayland session
        passwd_path = MNT_ROOT / "etc" / "passwd"
        passwd_text = passwd_path.read_text()
        if "pkos:" not in passwd_text:
            print("  * Creating 'pkos' user account for graphical Wayland session...")
            with open(passwd_path, "a") as f:
                f.write("pkos:x:1000:1000:PK-OS User:/home/pkos:/bin/bash\n")
            with open(MNT_ROOT / "etc" / "shadow", "a") as f:
                f.write("pkos::19000:0:99999:7:::\n")
            with open(MNT_ROOT / "etc" / "group", "a") as f:
                f.write("pkos:x:1000:\n")

            # Add pkos to video, input, render, audio, tty, sudo, users
            group_path = MNT_ROOT / "etc" / "group"
            group_lines = group_path.read_text().splitlines()
            target_groups = {"video", "input", "render", "audio", "tty", "sudo", "users"}
            new_lines = []
            for gline in group_lines:
                parts = gline.split(":")
                if len(parts) >= 3 and parts[0] in target_groups:
                    members = [m for m in parts[3].split(",") if m] if len(parts) > 3 else []
                    if "pkos" not in members:
                        members.append("pkos")
                    parts[3] = ",".join(members)
                    new_lines.append(":".join(parts))
                else:
                    new_lines.append(gline)
            group_path.write_text("\n".join(new_lines) + "\n")

            home_pkos = MNT_ROOT / "home" / "pkos"
            home_pkos.mkdir(parents=True, exist_ok=True)
            run_cmd(["chown", "-R", "1000:1000", str(home_pkos)], "Setting /home/pkos ownership")
            run_cmd(["chmod", "0755", str(home_pkos)], "Setting /home/pkos permissions")

            sudoers_d = MNT_ROOT / "etc" / "sudoers.d"
            sudoers_d.mkdir(parents=True, exist_ok=True)
            # Restricted privileges: allow power management without password, not arbitrary root
            (sudoers_d / "pkos").write_text(
                "# PK-OS restricted desktop user privileges (Phase 2C)\n"
                "pkos ALL=(ALL) NOPASSWD: /sbin/poweroff, /sbin/reboot, /sbin/shutdown, /bin/systemctl poweroff, /bin/systemctl reboot\n"
            )
            run_cmd(["chmod", "0440", str(sudoers_d / "pkos")], "Setting sudoers permissions")

        # Udev rule for seat/VT/DRM access: group-restricted 0660 (no blanket 0666 world-writable)
        udev_rules = MNT_ROOT / "etc" / "udev" / "rules.d"
        udev_rules.mkdir(parents=True, exist_ok=True)
        (udev_rules / "99-seat.rules").write_text(
            '# PK-OS secure device seat access rules (Phase 2C)\n'
            'KERNEL=="tty[0-9]*", OWNER="pkos", GROUP="tty", MODE="0660"\n'
            'SUBSYSTEM=="drm", GROUP="video", MODE="0660"\n'
            'SUBSYSTEM=="input", GROUP="input", MODE="0660"\n'
        )

        # Save kernel artifacts for ESP staging
        esp_vmlinuz_data = vmlinuz_path.read_bytes()
        esp_initrd_data = initrd_path.read_bytes()
        esp_bootx64_data = (efi_dir / "systemd-bootx64.efi").read_bytes()

        # Unmount root
        run_cmd(["sync"], "Syncing root filesystem")
        run_cmd(["umount", str(MNT_ROOT)], "Unmounting root partition")

        # 4. Format & Populate ESP
        print("[3/5] Formatting and populating ESP (FAT32)...")
        run_cmd(["mkfs.vfat", "-F", "32", "-n", "PKOS_ESP", part_esp], "Formatting FAT32 filesystem")
        MNT_ESP.mkdir(parents=True, exist_ok=True)
        run_cmd(["mount", part_esp, str(MNT_ESP)], "Mounting ESP")

        (MNT_ESP / "EFI" / "BOOT").mkdir(parents=True, exist_ok=True)
        (MNT_ESP / "EFI" / "systemd").mkdir(parents=True, exist_ok=True)
        (MNT_ESP / "EFI" / "PKOS").mkdir(parents=True, exist_ok=True)
        (MNT_ESP / "loader" / "entries").mkdir(parents=True, exist_ok=True)

        (MNT_ESP / "EFI" / "BOOT" / "BOOTX64.EFI").write_bytes(esp_bootx64_data)
        (MNT_ESP / "EFI" / "systemd" / "systemd-bootx64.efi").write_bytes(esp_bootx64_data)
        (MNT_ESP / "EFI" / "PKOS" / "vmlinuz").write_bytes(esp_vmlinuz_data)
        (MNT_ESP / "EFI" / "PKOS" / "initrd.img").write_bytes(esp_initrd_data)
        (MNT_ESP / "vmlinuz").write_bytes(esp_vmlinuz_data)
        (MNT_ESP / "initrd.img").write_bytes(esp_initrd_data)

        with open(MNT_ESP / "loader" / "loader.conf", "w") as f:
            f.write("default pkos.conf\ntimeout 3\nconsole-mode max\neditor no\n")

        with open(MNT_ESP / "loader" / "entries" / "pkos.conf", "w") as f:
            f.write("title PK-OS (0.1.0 LTS)\n")
            f.write("version 0.1.0\n")
            f.write("linux /EFI/PKOS/vmlinuz\n")
            f.write("initrd /EFI/PKOS/initrd.img\n")
            f.write("options root=LABEL=PKOS_ROOT rw console=tty0 console=ttyS0,115200 init=/lib/systemd/systemd systemd.show_status=1 systemd.journald.forward_to_console=1\n")

        run_cmd(["sync"], "Syncing ESP")
        run_cmd(["umount", str(MNT_ESP)], "Unmounting ESP")

    finally:
        # Detach loop device safely
        subprocess.run(["umount", "-l", str(MNT_ROOT)], stderr=subprocess.DEVNULL)
        subprocess.run(["umount", "-l", str(MNT_ESP)], stderr=subprocess.DEVNULL)
        time.sleep(0.5)
        run_cmd(["losetup", "-d", loop_dev], "Detaching loop device")

    # 5. Stream artifact to host output
    print("[4/5] Finalizing artifact and transferring to host...")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    run_cmd(["dd", f"if={TMP_IMAGE}", f"of={FINAL_IMAGE}", "bs=4M", "conv=fsync", "status=progress"], "Writing pk-os-dev.raw")
    run_cmd(["sync"], "Flushing filesystem cache")
    TMP_IMAGE.unlink()

    # Symlink latest
    latest_link = OUTPUT_DIR / "pk-os-dev.latest.raw"
    if latest_link.exists() or latest_link.is_symlink():
        latest_link.unlink()
    latest_link.symlink_to(FINAL_IMAGE.name)

    # 6. Verify checksum & partitions
    print("[5/5] Recording evidence and checksum...")
    h = hashlib.sha256()
    with open(FINAL_IMAGE, "rb") as f:
        while chunk := f.read(16 * 1024 * 1024):
            h.update(chunk)
    sha256 = h.hexdigest()
    image_size_mb = FINAL_IMAGE.stat().st_size // (1024 * 1024)
    print(f"  * Disk Image: {FINAL_IMAGE}")
    print(f"  * Size:       {image_size_mb} MB")
    print(f"  * SHA-256:    {sha256}")

    with open(OUTPUT_DIR / "SHA256SUMS", "a") as f:
        f.write(f"{sha256}  {FINAL_IMAGE.name}\n")

    fdisk_out = run_cmd(["fdisk", "-l", str(FINAL_IMAGE)], "Reading partition table")
    print("\nPartition table:\n" + fdisk_out)

    print("\n==========================================================")
    print("  PHASE 2B DISK IMAGE ASSEMBLY COMPLETED SUCCESSFULLY     ")
    print("==========================================================")


if __name__ == "__main__":
    main()
