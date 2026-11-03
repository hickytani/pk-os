"""Structural and, when installed, native syntax checks for opt-in Sway."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from scripts.assemble_phase2e_disk import configure_session_links, session_unit_name

ROOT = Path(__file__).resolve().parents[2]
SWAY_CONFIG = ROOT / "shell" / "src" / "compositor" / "sway" / "config"
SWAY_UNIT = ROOT / "shell" / "src" / "compositor" / "pk-sway-session.service"


class TestSwaySessionPackaging(unittest.TestCase):
    def test_session_selection_replaces_existing_links_idempotently(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wants = root / "etc/systemd/system/graphical.target.wants"
            wants.mkdir(parents=True)
            (wants / "pk-session.service").symlink_to("/lib/systemd/system/pk-session.service")
            (wants / "pk-intelligenced.service").symlink_to("/lib/systemd/system/pk-intelligenced.service")

            configure_session_links(root, "sway")

            self.assertFalse((wants / "pk-session.service").exists())
            self.assertEqual((wants / "pk-sway-session.service").readlink(), Path("/lib/systemd/system/pk-sway-session.service"))
            self.assertEqual((wants / "pk-intelligenced.service").readlink(), Path("/lib/systemd/system/pk-intelligenced.service"))

    def test_cage_remains_session_default(self):
        self.assertEqual(session_unit_name("cage"), "pk-session.service")
        self.assertEqual(session_unit_name("sway"), "pk-sway-session.service")

    def test_sway_is_packaged_but_cage_remains_the_enabled_default(self):
        manifest = (ROOT / "build" / "manifests" / "graphical-pkgs.list").read_text()
        rootfs_builder = (ROOT / "scripts" / "build-rootfs.sh").read_text()
        disk_builder = (ROOT / "scripts" / "assemble_phase2e_disk.py").read_text()

        self.assertIn("\nsway\n", manifest)
        self.assertIn("\nwofi\n", manifest)
        self.assertIn("\nxterm\n", manifest)
        self.assertIn("\nxfonts-base\n", manifest)
        self.assertIn('OUTPUT_DIR="${PKOS_BUILD_OUTPUT_DIR:-${OUTPUT_DIR}}"', rootfs_builder)
        self.assertIn("pk-sway-session.service", rootfs_builder)
        self.assertIn('"sway" / "config"', disk_builder)
        self.assertIn('ln -sf /lib/systemd/system/pk-session.service', rootfs_builder)
        self.assertNotIn('ln -sf /lib/systemd/system/pk-sway-session.service', rootfs_builder)
        self.assertIn('parser.add_argument("--session", choices=("cage", "sway"), default="cage"', disk_builder)
        self.assertIn('"usr/bin/wofi", "usr/bin/xterm", "usr/bin/foot", "usr/bin/pk-terminal"', disk_builder)

    def test_sway_config_has_real_launcher_and_second_app_shortcut(self):
        config = SWAY_CONFIG.read_text()
        css = (ROOT / "shell" / "src" / "compositor" / "sway" / "wofi.css").read_text()
        self.assertIn("wofi --show drun", config)
        self.assertIn("exec xterm -bg '#0d1115' -fg '#ecf1ef'", config)
        self.assertIn("#70d7cf", css)
        self.assertIn("PK_DESKTOP_SESSION=sway", SWAY_UNIT.read_text())
        cage_unit = (ROOT / "shell" / "src" / "compositor" / "pk-session.service").read_text()
        self.assertIn("PK_DESKTOP_SESSION=cage", cage_unit)

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
