#!/usr/bin/env python3
"""Checks for the project standards configuration reader.

Run with: python3 -m unittest discover -s scripts -p 'test_standards.py'
No browser, network, or third-party dependencies are required.
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import hook_install
from test_continuity import WorktreeTest

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
            "unsupported schema": ('```json\n{"schema": 9}\n```\n', "schema"),
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



class SchemaTwoTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)

    def write(self, text, name="standards.md"):
        path = self.root / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_a_schema_one_file_written_for_the_previous_release_still_parses(self):
        declared = standards.read(self.write(VALID))
        self.assertEqual(declared["schema"], 1)
        self.assertEqual(
            [t["name"] for t in declared["checks"]["tools"]], ["ruff", "pytest"]
        )

    def test_schema_two_accepts_a_project_supplied_command(self):
        declared = standards.read(self.write(
            '```json\n{"schema": 2, "checks": {"tools": ['
            '{"name": "deno-lint", "command": ["deno", "lint"]}]}}\n```\n'
        ))
        self.assertEqual(declared["checks"]["tools"][0]["command"], ["deno", "lint"])

    def test_the_shipped_argv_is_used_for_allowlisted_tools_and_paths_are_appended(self):
        self.assertEqual(
            standards.argv({"name": "ruff", "scope": "changed"}, ["a.py", "b c.py"]),
            ["ruff", "check", "a.py", "b c.py"],
        )
        self.assertEqual(
            standards.argv({"name": "ruff", "scope": "repository"}, []),
            ["ruff", "check", "."],
        )
        self.assertEqual(standards.argv({"name": "pyright", "scope": "repository"}, []),
                         ["pyright"])
        # A tool we ship no argv for and the project did not describe.
        self.assertIsNone(standards.argv({"name": "mypy"}, ["a.py"]))

    def test_command_is_refused_where_it_makes_no_sense(self):
        cases = {
            "command under schema 1": (
                '```json\n{"schema": 1, "checks": {"tools": ['
                '{"name": "deno", "command": ["deno"]}]}}\n```\n',
                "checks.tools[0]",
            ),
            "command on an allowlisted tool": (
                '```json\n{"schema": 2, "checks": {"tools": ['
                '{"name": "ruff", "command": ["ruff", "check"]}]}}\n```\n',
                "runs with the argv this skill ships",
            ),
            "a shell string": (
                '```json\n{"schema": 2, "checks": {"tools": ['
                '{"name": "deno", "command": ["deno lint"]}]}}\n```\n',
                "not a whole shell command",
            ),
            "empty command": (
                '```json\n{"schema": 2, "checks": {"tools": ['
                '{"name": "deno", "command": []}]}}\n```\n',
                "non-empty list",
            ),
            "non-string word": (
                '```json\n{"schema": 2, "checks": {"tools": ['
                '{"name": "deno", "command": ["deno", 7]}]}}\n```\n',
                "non-empty string",
            ),
            "unknown schema": ('```json\n{"schema": 3}\n```\n', "schema"),
        }
        for label, (text, expected) in cases.items():
            with self.subTest(case=label):
                path = self.write(text, f"{label.replace(' ', '-')}.md")
                with self.assertRaises(standards.Invalid) as caught:
                    standards.read(path)
                self.assertIn(expected, str(caught.exception))


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


class TemplateTests(unittest.TestCase):
    def test_the_shipped_template_declares_exactly_the_shipped_defaults(self):
        """The template is validated by the same reader users' files go through,
        so its published defaults cannot drift from the code's."""
        template = hook_install.ROOT / "structured-coding/standards-template.md"
        self.assertEqual(standards.read(template), standards.DEFAULTS)

    def test_the_template_prose_may_show_examples_without_being_read(self):
        text = (hook_install.ROOT / "structured-coding/standards-template.md").read_text()
        self.assertEqual(len(standards.blocks(text)), 1)


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

class TrustTests(WorktreeTest):
    """Layer comes from the filename; trust comes from Git. Never the other way."""

    def place(self, layer, track, text=None):
        relative = dict(standards.LAYERS)[layer]
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text or '```json\n{"schema": 1}\n```\n', encoding="utf-8")
        if track:
            self.git("add", "-f", "--", relative)
            self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", layer)
        return path

    def test_no_configuration_present_is_not_an_error(self):
        root, present = standards.discover(self.project)
        self.assertEqual(root, self.project)
        self.assertEqual(present, {})

    def test_the_ordinary_arrangement(self):
        self.place("base", track=True)
        self.place("overlay", track=False)
        _, present = standards.discover(self.project)
        self.assertEqual(present["base"]["trust"], "shared")
        self.assertEqual(present["overlay"]["trust"], "personal")

    def test_trust_follows_tracking_even_when_it_contradicts_the_filename(self):
        self.place("base", track=False)
        self.place("overlay", track=True)
        _, present = standards.discover(self.project)
        # Still the base and still the overlay; only the trust swapped.
        self.assertEqual(present["base"]["trust"], "personal")
        self.assertEqual(present["overlay"]["trust"], "shared")

    def test_a_tracked_file_stays_shared_after_being_gitignored(self):
        """.gitignore does not apply to an already-tracked file, so a filename
        rule would let a repository disguise a shared file as a personal one."""
        self.place("overlay", track=True)
        ignore = self.project / ".gitignore"
        ignore.write_text(dict(standards.LAYERS)["overlay"] + "\n", encoding="utf-8")
        _, present = standards.discover(self.project)
        self.assertEqual(present["overlay"]["trust"], "shared")

    def test_a_symlinked_configuration_is_refused_not_followed(self):
        real = self.project / "elsewhere.md"
        real.write_text('```json\n{"schema": 1}\n```\n', encoding="utf-8")
        relative = dict(standards.LAYERS)["base"]
        link = self.project / relative
        link.parent.mkdir(parents=True, exist_ok=True)
        link.symlink_to(real)
        with self.assertRaises(ValueError):
            standards.discover(self.project)

    def test_discovery_carries_the_declared_values_through(self):
        self.place("base", track=True, text=(
            '```json\n{"schema": 1, "checks": {"tools": [{"name": "mypy"}]}}\n```\n'
        ))
        _, present = standards.discover(self.project)
        declared = present["base"]["declared"]
        self.assertEqual(declared["checks"]["tools"][0]["name"], "mypy")

    def test_tools_are_classified_by_whether_they_execute_project_code(self):
        for name in standards.ANALYZERS:
            with self.subTest(tool=name):
                verdict, reason = standards.classify(name)
                self.assertEqual(verdict, "allowlisted")
                self.assertIn("without executing", reason)
        for name in standards.RUNNERS:
            with self.subTest(tool=name):
                verdict, _ = standards.classify(name)
                self.assertEqual(verdict, "approval required")
        verdict, reason = standards.classify("deno-lint")
        self.assertEqual(verdict, "approval required")
        self.assertIn("not a recognized tool", reason)


class SelectionTests(WorktreeTest):
    def commit(self, message):
        self.git("add", "-A")
        self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", message)

    def branch_with_changes(self):
        self.git("checkout", "-q", "-b", "feature")
        (self.project / "added file.py").write_text("x\n")
        (self.project / "code.py").write_text("modified\n")
        self.git("mv", "design.md", "renamed.md")
        (self.project / "contract.md").unlink()
        self.commit("feature")

    def test_changed_files_match_the_diff_and_exclude_what_is_gone(self):
        self.branch_with_changes()
        names = standards.changed_files(self.project, "main")
        self.assertIn("added file.py", names)   # a path with a space
        self.assertIn("code.py", names)
        self.assertIn("renamed.md", names)
        self.assertNotIn("design.md", names)    # the rename's old name
        self.assertNotIn("contract.md", names)  # deleted
        for name in names:
            self.assertTrue((self.project / name).is_file())

    def test_a_path_that_the_diff_lists_but_the_tree_lacks_is_dropped(self):
        self.branch_with_changes()
        (self.project / "added file.py").unlink()
        self.assertNotIn("added file.py", standards.changed_files(self.project, "main"))

    def test_an_unusable_base_is_refused_rather_than_guessed(self):
        for base in ("does-not-exist", "", None, "--upload-pack=evil"):
            with self.subTest(base=base):
                with self.assertRaises(standards.Invalid):
                    standards.changed_files(self.project, base)

    def test_repository_scope_needs_no_base_and_changed_scope_does(self):
        effective, _ = standards.resolve()
        self.assertTrue(standards.needs_base(effective))
        for tool in effective["checks"]["tools"]:
            tool["scope"] = "repository"
        self.assertFalse(standards.needs_base(effective))
        # A disabled changed-scope tool must not force a base either.
        effective["checks"]["tools"][0].update(scope="changed", enabled=False)
        self.assertFalse(standards.needs_base(effective))

    def test_an_empty_selection_is_a_reason_not_an_empty_success(self):
        self.git("checkout", "-q", "-b", "empty")
        paths, reason = standards.paths_for(
            self.project, {"name": "ruff", "scope": "changed"}, "main"
        )
        self.assertEqual(paths, [])
        self.assertIn("no files changed", reason)
        paths, reason = standards.paths_for(
            self.project, {"name": "ruff", "scope": "changed"}, None
        )
        self.assertIn("base revision is required", reason)
        self.assertEqual(
            standards.paths_for(self.project, {"name": "ruff", "scope": "repository"}, None),
            ([], None),
        )


class ApprovalTests(WorktreeTest):
    def config(self, text):
        relative = dict(standards.LAYERS)["base"]
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        self.git("add", "-f", "--", relative)
        self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "config")

    def declare(self, *tools):
        entries = ", ".join(tools)
        self.config(
            '```json\n{"schema": 2, "checks": {"tools": [' + entries + "]}}\n```\n"
        )

    def effective(self):
        _, present = standards.discover(self.project)
        base = present.get("base")
        value, _ = standards.resolve(
            None if base is None else (base["relative"], base["declared"])
        )
        return value

    def test_the_approval_record_lives_outside_the_working_tree(self):
        """A pull request must not be able to carry approval for its own command."""
        path = standards.approval_file(self.project)
        self.assertNotIn(self.project / ".structured-coding", path.parents)
        self.assertIn(self.project / ".git", path.parents)

    def test_nothing_needing_approval_records_nothing(self):
        pending, path = standards.grant(self.project, self.effective())
        self.assertEqual(pending, [])
        self.assertFalse(standards.approval_file(self.project).exists())
        self.assertTrue(standards.approved(self.project, pending))

    def test_a_declared_command_needs_approval_until_it_is_granted(self):
        self.declare('{"name": "deno-lint", "command": ["deno", "lint"]}')
        effective = self.effective()
        pending = standards.pending_approval(effective)
        self.assertEqual(pending, [["deno-lint", ["deno", "lint"]]])
        self.assertFalse(standards.approved(self.project, pending))
        standards.grant(self.project, effective)
        self.assertTrue(standards.approved(self.project, pending))

    def test_changing_a_command_revokes_the_approval(self):
        self.declare('{"name": "deno-lint", "command": ["deno", "lint"]}')
        standards.grant(self.project, self.effective())
        self.git("rm", "-q", "--cached", dict(standards.LAYERS)["base"])
        self.declare('{"name": "deno-lint", "command": ["deno", "lint", "--all"]}')
        effective = self.effective()
        self.assertFalse(
            standards.approved(self.project, standards.pending_approval(effective))
        )

    def test_an_unrelated_edit_does_not_revoke_the_approval(self):
        """Otherwise people learn to reapprove without reading."""
        self.declare('{"name": "deno-lint", "command": ["deno", "lint"]}')
        standards.grant(self.project, self.effective())
        approved = standards.pending_approval(self.effective())
        self.git("rm", "-q", "--cached", dict(standards.LAYERS)["base"])
        self.config(
            '```json\n{"schema": 2, "review": {"trigger": "commit"}, "checks":'
            ' {"tools": [{"name": "deno-lint", "command": ["deno", "lint"]}]}}\n```\n'
        )
        self.assertEqual(standards.pending_approval(self.effective()), approved)
        self.assertTrue(standards.approved(self.project, approved))

    def test_a_disabled_or_commandless_tool_needs_no_approval(self):
        self.declare(
            '{"name": "deno-lint", "command": ["deno"], "enabled": false}',
            '{"name": "mypy"}',
        )
        self.assertEqual(standards.pending_approval(self.effective()), [])

    def test_a_tampered_or_foreign_record_does_not_approve(self):
        self.declare('{"name": "deno-lint", "command": ["deno", "lint"]}')
        pending = standards.pending_approval(self.effective())
        path = standards.approval_file(self.project)
        path.parent.mkdir(parents=True, exist_ok=True)
        for content in ('{"schema": 1, "commands": "not-the-digest"}', "{}", "not json"):
            with self.subTest(content=content[:12]):
                path.write_text(content, encoding="utf-8")
                self.assertFalse(standards.approved(self.project, pending))

    def test_the_approve_command_lists_what_it_authorizes(self):
        self.declare('{"name": "deno-lint", "command": ["deno", "lint"]}')
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "approve", "--project", str(self.project)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("deno lint", result.stdout)
        self.assertIn("revokes it", result.stdout)


class InspectTests(WorktreeTest):
    def run_inspect(self):
        return subprocess.run(
            [sys.executable, str(RUNTIME), "inspect", "--project", str(self.project)],
            capture_output=True, text=True,
        )

    def place(self, layer, text, track=False):
        relative = dict(standards.LAYERS)[layer]
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if track:
            self.git("add", "-f", "--", relative)
            self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", layer)

    def test_a_project_without_configuration_reports_the_defaults(self):
        result = self.run_inspect()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(value["sources"], [])
        self.assertIn("defaults apply", value["note"])
        self.assertEqual(set(value["origins"].values()), {"default"})

    def test_every_effective_value_names_the_layer_it_came_from(self):
        self.place("base", '```json\n{"schema": 1, "checks": {"trigger": "pr"}}\n```\n', track=True)
        self.place("overlay", (
            '```json\n{"schema": 1, "checks": {"trigger": "commit",'
            ' "tools": [{"name": "ruff", "scope": "repository"}]}}\n```\n'
        ))
        result = self.run_inspect()
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        self.assertEqual(
            [(s["layer"], s["trust"]) for s in value["sources"]],
            [("base", "shared"), ("overlay", "personal")],
        )
        self.assertEqual(value["effective"]["checks"]["trigger"], "commit")
        self.assertEqual(value["origins"]["checks.trigger"], "overlay")
        self.assertEqual(value["origins"]["checks.tools.ruff.scope"], "overlay")
        self.assertEqual(value["origins"]["checks.tools.pyright"], "default")
        self.assertIn("runs no check", value["note"])

    def test_a_declared_runner_is_reported_as_needing_approval(self):
        self.place("base", (
            '```json\n{"schema": 1, "checks": {"tools": ['
            '{"name": "pytest", "enabled": true}, {"name": "deno-lint"}]}}\n```\n'
        ), track=True)
        value = json.loads(self.run_inspect().stdout)
        verdicts = {t["name"]: t["approval"] for t in value["effective"]["checks"]["tools"]}
        self.assertEqual(verdicts["ruff"], "allowlisted")
        self.assertEqual(verdicts["pytest"], "approval required")
        self.assertEqual(verdicts["deno-lint"], "approval required")

    def test_a_refusal_exits_nonzero_and_never_claims_the_defaults_apply(self):
        cases = {
            "relaxing overlay": (
                '```json\n{"schema": 1, "checks": {"trigger": "pr"}}\n```\n',
                '```json\n{"schema": 1, "checks": {"trigger": "off"}}\n```\n',
                "checks.trigger",
            ),
            "malformed base": ("# no block here\n", None, "json block"),
        }
        for label, (base, overlay, field) in cases.items():
            with self.subTest(case=label):
                self.setUp()
                self.place("base", base, track=True)
                if overlay is not None:
                    self.place("overlay", overlay)
                result = self.run_inspect()
                self.assertEqual(result.returncode, 1)
                self.assertIn(field, result.stderr)
                self.assertNotIn("defaults apply", result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), "")


class ExecutionTests(WorktreeTest):
    """Every outcome is produced by a real process, never by a mock."""

    def setUp(self):
        super().setUp()
        self.bin = self.root / "bin"
        self.bin.mkdir()
        environment = patch.dict(os.environ, {"PATH": f"{self.bin}{os.pathsep}{os.environ['PATH']}"})
        environment.start()
        self.addCleanup(environment.stop)

    def stub(self, name, body):
        path = self.bin / name
        path.write_text(f"#!/bin/sh\n{body}\n", encoding="utf-8")
        path.chmod(0o755)

    def config(self, text, track=True):
        relative = dict(standards.LAYERS)["base"]
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        if track:
            self.git("add", "-f", "--", relative)
            self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "c")

    def run_checks(self, base=None):
        effective, _ = standards.resolved(self.project)
        return {r["name"]: r for r in standards.outcomes(self.project, effective, base)}

    def test_each_outcome_comes_from_a_real_process(self):
        self.stub("ruff", "exit 0")
        self.stub("pyright", "echo 'error: x'; exit 1")
        self.config('```json\n{"schema": 1, "checks": {"tools": ['
                    '{"name": "ruff", "scope": "repository"},'
                    '{"name": "pyright", "scope": "repository"},'
                    '{"name": "pytest", "enabled": false}]}}\n```\n')
        results = self.run_checks()
        self.assertEqual(results["ruff"]["outcome"], "PASS")
        self.assertEqual(results["pyright"]["outcome"], "FAIL")
        self.assertIn("error: x", results["pyright"]["output"])
        self.assertEqual(results["pytest"]["outcome"], "NOT RUN")
        self.assertEqual(results["pytest"]["reason"], "disabled")

    def test_an_absent_tool_is_inconclusive_and_never_a_pass(self):
        self.config('```json\n{"schema": 1, "checks": {"tools": ['
                    '{"name": "ruff", "scope": "repository"}]}}\n```\n')
        result = self.run_checks()["ruff"]
        self.assertEqual(result["outcome"], "INCONCLUSIVE")
        self.assertIn("not installed", result["reason"])

    def test_a_tools_own_error_exit_is_inconclusive_not_a_failure(self):
        """ruff 2 and pyright 2/3/4 mean the tool could not run."""
        for name, code in (("ruff", 2), ("pyright", 3)):
            with self.subTest(tool=name):
                self.stub(name, f"exit {code}")
                self.config('```json\n{"schema": 1, "checks": {"tools": ['
                            f'{{"name": "{name}", "scope": "repository"}}]}}}}\n```\n',
                            track=False)
                result = self.run_checks()[name]
                self.assertEqual(result["outcome"], "INCONCLUSIVE")
                self.assertIn("own error mode", result["reason"])

    def test_a_hanging_tool_times_out_as_inconclusive(self):
        self.stub("ruff", "sleep 30")
        self.config('```json\n{"schema": 1, "checks": {"tools": ['
                    '{"name": "ruff", "scope": "repository"}]}}\n```\n')
        with patch.object(standards, "TOOL_SECONDS", 1):
            result = self.run_checks()["ruff"]
        self.assertEqual(result["outcome"], "INCONCLUSIVE")
        self.assertIn("no result within", result["reason"])

    def test_captured_output_is_bounded_and_marked(self):
        self.stub("ruff", "yes 0123456789 | head -c 200000; exit 1")
        self.config('```json\n{"schema": 1, "checks": {"tools": ['
                    '{"name": "ruff", "scope": "repository"}]}}\n```\n')
        result = self.run_checks()["ruff"]
        self.assertLessEqual(len(result["output"]), standards.MAX_OUTPUT + 40)
        self.assertIn("[output truncated]", result["output"])

    def test_an_unapproved_command_is_never_executed(self):
        # self.project contains a quote; keep the stub's shell string simple.
        marker = self.root / "ran"
        self.stub("deno", f"touch '{marker}'; exit 0")
        self.config('```json\n{"schema": 2, "checks": {"tools": ['
                    '{"name": "deno-lint", "scope": "repository",'
                    ' "command": ["deno", "lint"]}]}}\n```\n')
        result = self.run_checks()["deno-lint"]
        self.assertEqual(result["outcome"], "NOT RUN")
        self.assertIn("approval required", result["reason"])
        self.assertFalse(marker.exists())
        standards.grant(self.project, standards.resolved(self.project)[0])
        self.assertEqual(self.run_checks()["deno-lint"]["outcome"], "PASS")
        self.assertTrue(marker.exists())

    def test_a_project_command_records_that_its_exit_codes_are_unmapped(self):
        self.stub("deno", "exit 7")
        self.config('```json\n{"schema": 2, "checks": {"tools": ['
                    '{"name": "deno-lint", "scope": "repository",'
                    ' "command": ["deno", "lint"]}]}}\n```\n')
        standards.grant(self.project, standards.resolved(self.project)[0])
        result = self.run_checks()["deno-lint"]
        self.assertEqual(result["outcome"], "FAIL")
        self.assertIn("no exit-code map", result["reason"])

    def test_run_refuses_to_guess_a_base_for_changed_scope(self):
        self.stub("ruff", "exit 0")
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "run", "--project", str(self.project)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("--base is required", result.stderr)

    def test_run_reports_every_tool_end_to_end(self):
        self.stub("ruff", "exit 0")
        self.config('```json\n{"schema": 1, "checks": {"tools": ['
                    '{"name": "ruff", "scope": "repository"},'
                    '{"name": "pyright", "scope": "repository"}]}}\n```\n')
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "run", "--project", str(self.project)],
            capture_output=True, text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        value = json.loads(result.stdout)
        outcomes = {r["name"]: r["outcome"] for r in value["results"]}
        self.assertEqual(outcomes["ruff"], "PASS")
        self.assertEqual(outcomes["pyright"], "INCONCLUSIVE")
        self.assertIn("Nothing was registered as a hook", value["note"])


class BoundBaseTests(WorktreeTest):
    def bind(self, *extra):
        return subprocess.run(
            [sys.executable, str(hook_install.ROOT / "structured-coding/scripts/continuity.py"),
             "activate", "--host", "codex", "--project", str(self.project),
             "--session", self.session, "--pr", "P", "--design", "design.md",
             "--contract", "contract.md", "--handoff", "handoff.md", *extra],
            capture_output=True, text=True)

    def test_a_recorded_base_is_found(self):
        self.assertEqual(self.bind("--base", "main").returncode, 0)
        self.assertEqual(
            standards.bound_base(self.project, "codex", self.session), "main")

    def test_every_way_of_having_no_base_reads_the_same(self):
        cases = {
            "unbound session": lambda: None,
            "bound without a base": lambda: self.bind(),
            "unknown host": lambda: self.bind("--base", "main"),
        }
        for label, prepare in cases.items():
            with self.subTest(case=label):
                self.setUp()
                prepare()
                host = "claude-code" if label == "unknown host" else "codex"
                self.assertIsNone(
                    standards.bound_base(self.project, host, self.session))

    def test_a_closed_binding_supplies_nothing(self):
        self.bind("--base", "main")
        subprocess.run(
            [sys.executable, str(hook_install.ROOT / "structured-coding/scripts/continuity.py"),
             "deactivate", "--host", "codex", "--project", str(self.project),
             "--session", self.session], capture_output=True, check=True)
        self.assertIsNone(standards.bound_base(self.project, "codex", self.session))

    def test_run_uses_the_bound_base_and_an_explicit_one_wins(self):
        self.git("checkout", "-q", "-b", "feature")
        (self.project / "new file.py").write_text("x\n")
        self.git("add", "-A")
        self.git("-c", "user.email=a@b", "-c", "user.name=t", "commit", "-qm", "f")
        self.bind("--base", "main")
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "run", "--project", str(self.project),
             "--host", "codex", "--session", self.session],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["base"], "main")
        explicit = subprocess.run(
            [sys.executable, str(RUNTIME), "run", "--project", str(self.project),
             "--host", "codex", "--session", self.session, "--base", "feature"],
            capture_output=True, text=True)
        self.assertEqual(json.loads(explicit.stdout)["base"], "feature")

    def test_without_a_base_anywhere_run_reports_the_ordinary_reason(self):
        self.bind()
        result = subprocess.run(
            [sys.executable, str(RUNTIME), "run", "--project", str(self.project),
             "--host", "codex", "--session", self.session],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn("--base is required", result.stderr)


class ProcessGroupTests(WorktreeTest):
    """A timed-out tool must not leave a tree running behind it."""

    def alive(self, pid, seconds=5):
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            try:
                os.kill(pid, 0)
            except (OSError, ProcessLookupError):
                return False
            time.sleep(0.1)
        return True

    def test_a_timeout_ends_the_whole_tree_not_only_the_child(self):
        pidfile = self.root / "grandchild.pid"
        stub = self.root / "spawner"
        stub.write_text(
            "#!/bin/sh\n"
            "sh -c 'sleep 300' &\n"
            f"echo $! > '{pidfile}'\n"
            "sleep 300\n"
        )
        stub.chmod(0o755)
        outcome, reason, _ = standards.execute(
            self.project, {"name": "spawner"}, [str(stub)], 2
        )
        self.assertEqual(outcome, "INCONCLUSIVE")
        self.assertIn("no result within", reason)
        pid = int(pidfile.read_text().strip())
        self.assertFalse(self.alive(pid), "a grandchild outlived the timed-out tool")

    def test_a_tool_that_ignores_termination_is_still_ended(self):
        stub = self.root / "stubborn"
        stub.write_text("#!/bin/sh\ntrap '' TERM\nsleep 300\n")
        stub.chmod(0o755)
        started = time.monotonic()
        outcome, _, _ = standards.execute(
            self.project, {"name": "stubborn"}, [str(stub)], 2
        )
        self.assertEqual(outcome, "INCONCLUSIVE")
        # Terminated, then killed after the grace period, rather than hanging.
        self.assertLess(time.monotonic() - started, 2 + standards.GRACE_SECONDS * 2 + 5)

    def test_an_ordinary_tool_is_unaffected_by_the_new_session(self):
        stub = self.root / "quick"
        stub.write_text("#!/bin/sh\necho hello\nexit 1\n")
        stub.chmod(0o755)
        outcome, _, output = standards.execute(
            self.project, {"name": "quick"}, [str(stub)], 30
        )
        self.assertEqual(outcome, "FAIL")
        self.assertIn("hello", output)


if __name__ == "__main__":
    unittest.main()
