#!/usr/bin/env python3
"""Checks for the project standards configuration reader.

Run with: python3 -m unittest discover -s scripts -p 'test_standards.py'
No browser, network, or third-party dependencies are required.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hook_install

RUNTIME = hook_install.ROOT / "structured-coding/scripts/standards.py"
spec = importlib.util.spec_from_file_location("standards", RUNTIME)
standards = importlib.util.module_from_spec(spec)
with patch.object(importlib.util.sys, "dont_write_bytecode", True):
    spec.loader.exec_module(standards)

VALID = """# Project standards

Prose the machine never reads.

```json
{
  "schema": 1,
  "review": {"trigger": "pr", "conventions": ["Public functions carry docstrings"]},
  "checks": {
    "trigger": "pr",
    "tools": [
      {"name": "ruff", "enabled": true, "scope": "changed"},
      {"name": "pytest", "enabled": false, "scope": "repository"}
    ]
  }
}
```

More prose.
"""


class ReaderTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, text, name="standards.md"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_filled_template_parses_into_its_declared_values(self):
        declared = standards.read(self.write(VALID))
        self.assertEqual(declared["schema"], 1)
        self.assertEqual(declared["review"]["trigger"], "pr")
        self.assertEqual(len(declared["review"]["conventions"]), 1)
        names = [tool["name"] for tool in declared["checks"]["tools"]]
        self.assertEqual(names, ["ruff", "pytest"])
        self.assertFalse(declared["checks"]["tools"][1]["enabled"])

    def test_only_declared_sections_are_returned(self):
        """Absent sections stay absent here; defaults belong to resolution."""
        declared = standards.read(
            self.write('```json\n{"schema": 1, "review": {"trigger": "commit"}}\n```\n')
        )
        self.assertEqual(set(declared), {"schema", "review"})
        self.assertNotIn("conventions", declared["review"])

    def test_a_fence_inside_a_fence_is_content_not_configuration(self):
        nested = (
            "````text\n"
            "Example for the reader:\n"
            "```json\n"
            '{"schema": 99}\n'
            "```\n"
            "````\n\n"
            '```json\n{"schema": 1}\n```\n'
        )
        self.assertEqual(standards.read(self.write(nested)), {"schema": 1})

    def test_every_rejection_names_the_file_and_the_field(self):
        cases = {
            "no block": ("# Nothing here\n", "json block"),
            "two blocks": (
                '```json\n{"schema": 1}\n```\n\n```json\n{"schema": 1}\n```\n',
                "json block",
            ),
            "not json": ("```json\n{nope}\n```\n", "json block"),
            "not an object": ("```json\n[1, 2]\n```\n", "json block"),
            "wrong schema": ('```json\n{"schema": 2}\n```\n', "schema"),
            "missing schema": ('```json\n{"review": {}}\n```\n', "schema"),
            "unknown top key": ('```json\n{"schema": 1, "extra": 1}\n```\n', "json block"),
            "review not object": ('```json\n{"schema": 1, "review": []}\n```\n', "review"),
            "unknown review key": (
                '```json\n{"schema": 1, "review": {"nope": 1}}\n```\n',
                "review",
            ),
            "bad trigger": (
                '```json\n{"schema": 1, "review": {"trigger": "always"}}\n```\n',
                "review.trigger",
            ),
            "conventions not list": (
                '```json\n{"schema": 1, "review": {"conventions": "x"}}\n```\n',
                "review.conventions",
            ),
            "empty convention": (
                '```json\n{"schema": 1, "review": {"conventions": ["  "]}}\n```\n',
                "review.conventions[0]",
            ),
            "tools not list": (
                '```json\n{"schema": 1, "checks": {"tools": {}}}\n```\n',
                "checks.tools",
            ),
            "tool not object": (
                '```json\n{"schema": 1, "checks": {"tools": ["ruff"]}}\n```\n',
                "checks.tools[0]",
            ),
            "tool unknown key": (
                '```json\n{"schema": 1, "checks": {"tools": [{"name": "ruff", "x": 1}]}}\n```\n',
                "checks.tools[0]",
            ),
            "bad tool name": (
                '```json\n{"schema": 1, "checks": {"tools": [{"name": "Ruff!"}]}}\n```\n',
                "checks.tools[0].name",
            ),
            "duplicate tool": (
                '```json\n{"schema": 1, "checks": {"tools": ['
                '{"name": "ruff"}, {"name": "ruff"}]}}\n```\n',
                "checks.tools[1].name",
            ),
            "bad enabled": (
                '```json\n{"schema": 1, "checks": {"tools": ['
                '{"name": "ruff", "enabled": "yes"}]}}\n```\n',
                "checks.tools[0].enabled",
            ),
            "bad scope": (
                '```json\n{"schema": 1, "checks": {"tools": ['
                '{"name": "ruff", "scope": "all"}]}}\n```\n',
                "checks.tools[0].scope",
            ),
        }
        for label, (text, field) in cases.items():
            with self.subTest(case=label):
                path = self.write(text, f"{label.replace(' ', '-')}.md")
                with self.assertRaises(standards.Invalid) as caught:
                    standards.read(path)
                message = str(caught.exception)
                self.assertIn(str(path), message)
                self.assertIn(field, message)

    def test_a_symlinked_or_oversized_configuration_is_refused(self):
        target = self.write(VALID, "real.md")
        link = self.root / "link.md"
        link.symlink_to(target)
        with self.assertRaisesRegex(standards.Invalid, "symlinked"):
            standards.read(link)
        big = self.write("x" * (standards.MAX_INPUT + 1), "big.md")
        with self.assertRaisesRegex(standards.Invalid, "larger than"):
            standards.read(big)
        with self.assertRaisesRegex(standards.Invalid, "not a regular file"):
            standards.read(self.root / "absent.md")

    def test_a_refusal_never_echoes_the_file_contents(self):
        secret = "SUPER-SECRET-TOKEN"
        path = self.write(f'```json\n{{"schema": 1, "{secret}": 1}}\n```\n')
        with self.assertRaises(standards.Invalid) as caught:
            standards.read(path)
        # The offending key is named; nothing else from the file appears.
        self.assertIn(secret, str(caught.exception))
        body = self.write('```json\n{"schema": 1, "review": ' + f'"{secret}"' + "}\n```\n")
        with self.assertRaises(standards.Invalid) as caught:
            standards.read(body)
        self.assertNotIn(secret, str(caught.exception))



class PackagingTests(unittest.TestCase):
    def test_a_stray_bytecode_cache_does_not_break_packaging(self):
        """Importing an installed helper must not make the skill unpublishable."""
        import build_packages

        cache = build_packages.SOURCE / "scripts/__pycache__"
        cache.mkdir(parents=True, exist_ok=True)
        stray = cache / "standards.cpython-000.pyc"
        stray.write_bytes(b"\x00")
        self.addCleanup(lambda: stray.exists() and stray.unlink())
        for host in build_packages.HOSTS:
            files = build_packages.source_files(host)
            self.assertNotIn("scripts/__pycache__", " ".join(files))
            self.assertIn("scripts/standards.py", files)


class ResolutionTests(unittest.TestCase):
    BASE = Path("team.md")
    MINE = Path("mine.md")

    def resolve(self, base=None, overlay=None):
        return standards.resolve(
            None if base is None else (self.BASE, {"schema": 1, **base}),
            None if overlay is None else (self.MINE, {"schema": 1, **overlay}),
        )

    def tool(self, effective, name):
        return next(t for t in effective["checks"]["tools"] if t["name"] == name)

    def test_no_file_at_all_yields_the_shipped_defaults(self):
        effective, origins = self.resolve()
        self.assertEqual(effective, standards.DEFAULTS)
        self.assertEqual(set(origins.values()), {"default"})
        self.assertTrue(self.tool(effective, "ruff")["enabled"])
        self.assertFalse(self.tool(effective, "pytest")["enabled"])

    def test_defaults_cannot_be_mutated_through_a_resolution(self):
        effective, _ = self.resolve({"review": {"conventions": ["x"]}})
        self.assertEqual(effective["review"]["conventions"], ["x"])
        self.assertEqual(standards.DEFAULTS["review"]["conventions"], [])

    def test_the_shared_file_may_relax_the_defaults(self):
        """The defaults are our suggestion; the team standard is authoritative."""
        effective, origins = self.resolve(
            {"checks": {"trigger": "off", "tools": [{"name": "ruff", "enabled": False}]}}
        )
        self.assertEqual(effective["checks"]["trigger"], "off")
        self.assertFalse(self.tool(effective, "ruff")["enabled"])
        self.assertEqual(origins["checks.trigger"], "base")

    def test_a_personal_file_may_tighten_every_field(self):
        effective, origins = self.resolve(
            {"checks": {"trigger": "pr", "tools": [{"name": "ruff", "scope": "changed"}]}},
            {
                "review": {"trigger": "commit", "conventions": ["No bare except"]},
                "checks": {
                    "trigger": "commit",
                    "tools": [
                        {"name": "ruff", "scope": "repository"},
                        {"name": "pytest", "enabled": True},
                        {"name": "mypy"},
                    ],
                },
            },
        )
        self.assertEqual(effective["checks"]["trigger"], "commit")
        self.assertEqual(self.tool(effective, "ruff")["scope"], "repository")
        self.assertTrue(self.tool(effective, "pytest")["enabled"])
        self.assertEqual(self.tool(effective, "mypy")["scope"], "changed")
        self.assertIn("No bare except", effective["review"]["conventions"])
        self.assertEqual(origins["checks.tools.ruff.scope"], "overlay")
        self.assertEqual(origins["checks.tools.mypy"], "overlay")
        self.assertEqual(origins["review.trigger"], "overlay")

    def test_a_personal_file_may_not_relax_the_shared_standard(self):
        cases = {
            "trigger off": ({"checks": {"trigger": "off"}}, "checks.trigger"),
            "trigger down": ({"review": {"trigger": "pr"}}, "review.trigger"),
            "disable a check": (
                {"checks": {"tools": [{"name": "ruff", "enabled": False}]}},
                "checks.tools.ruff.enabled",
            ),
            "narrow a scope": (
                {"checks": {"tools": [{"name": "pytest", "scope": "changed"}]}},
                "checks.tools.pytest.scope",
            ),
        }
        base = {
            "review": {"trigger": "commit"},
            "checks": {"trigger": "pr", "tools": [{"name": "pytest", "scope": "repository"}]},
        }
        for label, (overlay, field) in cases.items():
            with self.subTest(case=label):
                with self.assertRaises(standards.Invalid) as caught:
                    self.resolve(base, overlay)
                message = str(caught.exception)
                self.assertIn(str(self.MINE), message)
                self.assertIn(field, message)
                self.assertIn("personal file may not", message)

    def test_a_personal_file_cannot_remove_a_shared_convention(self):
        """Overlay conventions are additions, so removal has no representation."""
        effective, _ = self.resolve(
            {"review": {"conventions": ["Team rule"]}},
            {"review": {"conventions": ["Mine"]}},
        )
        self.assertEqual(effective["review"]["conventions"], ["Team rule", "Mine"])

    def test_an_overlay_without_a_shared_file_is_measured_against_the_defaults(self):
        with self.assertRaisesRegex(standards.Invalid, "checks.trigger"):
            self.resolve(None, {"checks": {"trigger": "off"}})
        effective, origins = self.resolve(None, {"checks": {"trigger": "commit"}})
        self.assertEqual(effective["checks"]["trigger"], "commit")
        self.assertEqual(origins["checks.trigger"], "overlay")

if __name__ == "__main__":
    unittest.main()
