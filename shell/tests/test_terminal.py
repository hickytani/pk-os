"""Tests for the PK Terminal process entry point."""

from __future__ import annotations

import importlib.util
from importlib.machinery import SourceFileLoader
import io
from pathlib import Path
import unittest
from unittest.mock import Mock


TERMINAL_PATH = Path(__file__).resolve().parents[1] / "apps" / "pk-terminal"
LOADER = SourceFileLoader("pk_terminal", str(TERMINAL_PATH))
SPEC = importlib.util.spec_from_loader("pk_terminal", LOADER)
assert SPEC and SPEC.loader
pk_terminal = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pk_terminal)


class TestPkTerminal(unittest.TestCase):
    def test_desktop_entry_uses_pk_terminal_wrapper(self):
        desktop_entry = TERMINAL_PATH.with_suffix(".desktop").read_text(encoding="utf-8")
        self.assertIn("Exec=pk-terminal", desktop_entry)
        self.assertIn("Terminal=false", desktop_entry)

    def test_exec_replaces_wrapper_and_forwards_argv_without_shell(self):
        execv = Mock()
        args = ["--", "/bin/sh", "-c", "printf '%s' '$HOME; $(id)'"]

        result = pk_terminal.run(args, which=lambda name: "/usr/bin/foot", execv=execv)

        self.assertEqual(result, 126)  # mocked execv returns; real execv never does
        execv.assert_called_once_with("/usr/bin/foot", ["/usr/bin/foot", *args])

    def test_missing_foot_fails_visibly(self):
        stderr = io.StringIO()

        result = pk_terminal.run([], which=lambda _name: None, stderr=stderr)

        self.assertEqual(result, 127)
        self.assertIn("'foot' is not installed", stderr.getvalue())

    def test_exec_failure_returns_command_failure(self):
        stderr = io.StringIO()

        def fail_exec(_binary: str, _argv: list[str]) -> None:
            raise OSError("permission denied")

        result = pk_terminal.run([], which=lambda _name: "/usr/bin/foot", execv=fail_exec, stderr=stderr)

        self.assertEqual(result, 126)
        self.assertIn("could not start foot: permission denied", stderr.getvalue())


if __name__ == "__main__":
    unittest.main()
