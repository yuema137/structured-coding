#!/usr/bin/env python3
"""Checks for the project standards configuration reader.

Run with: python3 -m unittest discover -s scripts -p 'test_standards.py'
No browser, network, or third-party dependencies are required.
"""

import importlib.util
import json
import subprocess
import sys
import tempfile
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


if __name__ == "__main__":
    unittest.main()
