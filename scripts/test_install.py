"""Exercise installer behavior using disposable projects, never user settings."""

import importlib.machinery
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import build_packages


SCRIPT = Path(__file__).with_name("install")
loader = importlib.machinery.SourceFileLoader("skill_install", str(SCRIPT))
spec = importlib.util.spec_from_loader(loader.name, loader)
installer = importlib.util.module_from_spec(spec)
loader.exec_module(installer)


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project with spaces"
        self.project.mkdir()
        self.destination = self.project / ".agents/skills/structured-coding"

    def test_each_platform_gets_exact_public_files(self):
        for host in installer.PLATFORMS:
            with self.subTest(host=host):
                destination = installer.install(host, self.project)
                expected = {name: path.read_bytes() for name, path in build_packages.source_files(host).items()}
                actual = {path.relative_to(destination).as_posix(): path.read_bytes()
                          for path in destination.rglob("*") if path.is_file()}
                self.assertEqual(expected, actual)
                self.assertEqual((host == "codex"), (destination / "agents/openai.yaml").exists())
        self.assertEqual(sorted(path.name for path in self.project.iterdir()), [".agents", ".claude"])
        self.assertFalse((self.project / ".codex").exists())
        self.assertFalse((self.project / ".claude/settings.json").exists())
        for config in (".agents", ".claude"):
            self.assertEqual([p.name for p in (self.project / config / "skills").iterdir()], ["structured-coding"])

    def test_existing_installation_is_preserved(self):
        installer.install("codex", self.project)
        customized = self.destination / "SKILL.md"
        customized.write_text("local customization")
        with self.assertRaises(FileExistsError):
            installer.install("codex", self.project)
        self.assertEqual(customized.read_text(), "local customization")

    def test_existing_host_settings_are_untouched(self):
        settings = self.project / ".claude/settings.json"
        settings.parent.mkdir()
        original = '{"permissions": {"deny": ["Bash(gh pr merge*)"]}}\n'
        settings.write_text(original)
        installer.install("claude-code", self.project)
        self.assertEqual(settings.read_text(), original)

    def test_empty_existing_directory_is_not_replaced(self):
        self.destination.mkdir(parents=True)
        with self.assertRaises(FileExistsError):
            installer.install("codex", self.project)
        self.assertEqual(list(self.destination.iterdir()), [])

    def test_existing_file_is_not_replaced(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.write_text("keep")
        with self.assertRaises(FileExistsError):
            installer.install("codex", self.project)
        self.assertEqual(self.destination.read_text(), "keep")

    def test_broken_symlink_is_not_replaced(self):
        self.destination.parent.mkdir(parents=True)
        self.destination.symlink_to(self.root / "missing")
        with self.assertRaises(FileExistsError):
            installer.install("codex", self.project)
        self.assertTrue(self.destination.is_symlink())

    def test_parent_symlink_cannot_redirect_installation(self):
        outside = self.root / "outside"
        outside.mkdir()
        (self.project / ".agents").symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "redirected"):
            installer.install("codex", self.project)
        self.assertEqual(list(outside.iterdir()), [])

    def test_missing_project_is_not_created(self):
        missing = self.root / "missing"
        with self.assertRaises(FileNotFoundError):
            installer.install("codex", missing)
        self.assertFalse(missing.exists())

    def test_file_is_not_a_project(self):
        file = self.root / "file"
        file.touch()
        with self.assertRaisesRegex(ValueError, "not a directory"):
            installer.install("codex", file)

    def test_source_validation_happens_before_project_changes(self):
        with patch.object(installer, "source_files", side_effect=ValueError("private source file")):
            with self.assertRaisesRegex(ValueError, "private source file"):
                installer.install("codex", self.project)
        self.assertEqual(list(self.project.iterdir()), [])

    def test_incomplete_copy_is_not_published(self):
        with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
            with self.assertRaisesRegex(OSError, "disk full"):
                installer.install("codex", self.project)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_publish_failure_cleans_empty_reservation(self):
        with patch.object(installer.os, "replace", side_effect=OSError("publish failed")):
            with self.assertRaisesRegex(OSError, "publish failed"):
                installer.install("codex", self.project)
        self.assertFalse(self.destination.exists())
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_destination_appearing_during_copy_is_preserved(self):
        write_bytes = Path.write_bytes

        def competing_install(path, content):
            self.destination.mkdir(exist_ok=True)
            (self.destination / "keep").write_text("other installation")
            return write_bytes(path, content)

        with patch.object(Path, "write_bytes", competing_install):
            with self.assertRaises(FileExistsError):
                installer.install("codex", self.project)
        self.assertEqual((self.destination / "keep").read_text(), "other installation")
        self.assertEqual([p.name for p in self.destination.parent.iterdir()], ["structured-coding"])

    def test_cli_requires_host_and_project_and_supports_help(self):
        for args in ([], ["codex"], ["unknown", "--project", str(self.project)]):
            with self.subTest(args=args):
                result = subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True)
                self.assertEqual(result.returncode, 2)
        result = subprocess.run([sys.executable, str(SCRIPT), "--help"], capture_output=True)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(list(self.project.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "Direct POSIX executable entrypoint")
    def test_executable_entrypoint_from_target_project(self):
        result = subprocess.run([str(SCRIPT), "codex", "--project", "."],
                                cwd=self.project, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.destination / "SKILL.md").exists())
        self.assertIn("No hooks", result.stdout)


if __name__ == "__main__":
    unittest.main()
