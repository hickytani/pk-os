"""Structural and, when installed, native syntax checks for opt-in Sway."""

import shutil
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SWAY_CONFIG = ROOT / "shell" / "src" / "compositor" / "sway" / "config"
SWAY_UNIT = ROOT / "shell" / "src" / "compositor" / "pk-sway-session.service"


class TestSwaySessionPackaging(unittest.TestCase):
    def test_sway_is_packaged_but_cage_remains_the_enabled_default(self):
        manifest = (ROOT / "build" / "manifests" / "graphical-pkgs.list").read_text()
        rootfs_builder = (ROOT / "scripts" / "build-rootfs.sh").read_text()
        disk_builder = (ROOT / "scripts" / "assemble_phase2e_disk.py").read_text()

        self.assertIn("\nsway\n", manifest)
        self.assertIn("pk-sway-session.service", rootfs_builder)
        self.assertIn('"sway" / "config"', disk_builder)
        self.assertIn('ln -sf /lib/systemd/system/pk-session.service', rootfs_builder)
        self.assertNotIn('ln -sf /lib/systemd/system/pk-sway-session.service', rootfs_builder)

    def test_sway_unit_is_opt_in_and_conflicts_with_cage(self):
        unit = SWAY_UNIT.read_text()
        self.assertIn("Conflicts=pk-session.service getty@tty1.service", unit)
        self.assertIn("ExecStart=/usr/bin/sway --debug --config /etc/pk-os/sway/config", unit)
        self.assertIn("Environment=WLR_RENDERER=pixman", unit)
        self.assertIn("StandardError=journal+console", unit)

    def test_configuration_launches_shell_and_separate_terminal(self):
        config = SWAY_CONFIG.read_text()
        self.assertIn("exec /usr/bin/python3 -m shell.launcher", config)
        self.assertIn("exec /usr/bin/pk-terminal", config)
        self.assertIn("floating toggle", config)
        self.assertIn("floating_modifier $mod normal", config)
        self.assertIn("fullscreen toggle", config)
        self.assertIn("move scratchpad", config)
        self.assertIn("scratchpad show", config)
        self.assertIn('mode "resize"', config)
        self.assertIn("resize grow width 10 px", config)
        self.assertIn("move container to workspace", config)

    @unittest.skipUnless(shutil.which("sway"), "Sway parser is not installed on this test host")
    def test_sway_native_config_validation(self):
        result = subprocess.run(
            [shutil.which("sway"), "--validate", "--config", str(SWAY_CONFIG)],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
