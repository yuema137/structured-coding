"""Installer CLI selection; fake version executables are not native hook evidence."""

import json
import os
import subprocess
import sys

from test_continuity import WorktreeTest
from test_install import SCRIPT


class PresetCLITests(WorktreeTest):
    def setUp(self):
        super().setUp()
        binaries = self.root / "bin"
        binaries.mkdir()
        for name, version in (("codex", "0.153.4"), ("claude", "2.1.261")):
            path = binaries / name
            path.write_text(f"#!/bin/sh\necho {version}\n")
            path.chmod(0o755)
        self.env = {
            **os.environ,
            "PATH": str(binaries) + os.pathsep + os.environ["PATH"],
        }

    def cli(self, host, *options):
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                host,
                "--project",
                str(self.project),
                *options,
            ],
            env=self.env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_standalone_additive_preview_check_and_selective_remove_both_hosts(self):
        for host, relative in (
            ("codex", ".codex/hooks.json"),
            ("claude-code", ".claude/settings.json"),
        ):
            before = set(self.project.rglob("*"))
            self.assertEqual(
                self.cli(host, "--hooks", "checkpoints", "--dry-run").returncode, 0
            )
            self.assertEqual(before, set(self.project.rglob("*")))
            result = self.cli(host, "--hooks", "checkpoints")
            self.assertEqual(result.returncode, 0, result.stderr)
            config = self.project / relative
            self.assertEqual(
                set(json.loads(config.read_bytes())["hooks"]),
                {"SessionStart", "PreToolUse", "Stop"},
            )
            result = self.cli(host, "--hooks", "continuity", "checkpoints")
            self.assertEqual(result.returncode, 0, result.stderr)
            current = config.read_bytes()
            self.assertEqual(
                self.cli(host, "--hooks", "checkpoints", "continuity").returncode, 0
            )
            self.assertEqual(current, config.read_bytes())
            self.assertIn(
                "continuity, checkpoints", self.cli(host, "--check-hooks").stdout
            )
            self.assertEqual(
                self.cli(host, "--remove-hooks", "continuity", "--dry-run").returncode,
                0,
            )
            self.assertEqual(current, config.read_bytes())
            self.assertEqual(
                self.cli(host, "--remove-hooks", "continuity").returncode, 0
            )
            self.assertEqual(
                set(json.loads(config.read_bytes())["hooks"]),
                {"SessionStart", "PreToolUse", "Stop"},
            )
            self.assertEqual(self.cli(host, "--remove-hooks").returncode, 0)
            self.assertFalse(config.exists())

    def test_invalid_selection_and_customized_runtime_do_not_write(self):
        for options in (
            ("--hooks", "unknown"),
            ("--hooks", "continuity", "continuity"),
            ("--remove-hooks", "checkpoints", "checkpoints"),
            ("--remove-hooks", "unknown"),
            ("--hooks", "continuity", "--hooks", "continuity"),
        ):
            before = set(self.project.rglob("*"))
            self.assertEqual(self.cli("codex", *options).returncode, 2)
            self.assertEqual(before, set(self.project.rglob("*")))
        self.assertEqual(self.cli("codex", "--hooks", "continuity").returncode, 0)
        config = self.project / ".codex/hooks.json"
        before = config.read_bytes()
        script = (
            self.project / ".agents/skills/structured-coding/scripts/checkpoints.py"
        )
        script.write_text("user customization")
        result = self.cli("codex", "--hooks", "checkpoints")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("update the skill", result.stderr)
        self.assertEqual(before, config.read_bytes())
        self.assertEqual(script.read_text(), "user customization")
