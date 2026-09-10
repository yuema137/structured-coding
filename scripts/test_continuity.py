"""Continuity protocol and installer tests in disposable, real Git worktrees."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import hook_install
from test_install import installer

RUNTIME = hook_install.ROOT / "structured-coding/scripts/continuity.py"
spec = importlib.util.spec_from_file_location("continuity", RUNTIME)
runtime = importlib.util.module_from_spec(spec)
with patch.object(sys, "dont_write_bytecode", True):
    spec.loader.exec_module(runtime)


class WorktreeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.project = self.root / "project with spaces and 'quotes'"
        self.project.mkdir()
        self.environment = patch.dict(
            os.environ,
            {
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_CONFIG_NOSYSTEM": "1",
            },
        )
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.git("init", "-b", "main")
        # Background housekeeping writes .git/objects/maintenance.lock at
        # unpredictable moments, which breaks tests that compare the whole tree.
        self.git("config", "maintenance.auto", "false")
        self.git("config", "gc.auto", "0")
        for name in ("code.py", "design.md", "contract.md", "handoff.md"):
            (self.project / name).write_text(f"Initial {name}\n")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "-c",
            "core.hooksPath=/dev/null",
            "commit",
            "-m",
            "initial",
        )
        self.session = "session-A"

    def git(self, *args):
        return subprocess.check_output(
            ["git", "-C", str(self.project), *args], stderr=subprocess.DEVNULL
        )

    def command(self, action, *args, session=None, host="codex", script=RUNTIME):
        return subprocess.run(
            [
                sys.executable,
                str(script),
                action,
                "--host",
                host,
                "--project",
                str(self.project),
                "--session",
                session or self.session,
                *args,
            ],
            capture_output=True,
            text=True,
        )

    def activate(self, host="codex", session=None, script=RUNTIME):
        result = self.command(
            "activate",
            "--pr",
            "PR-1",
            "--design",
            "design.md",
            "--contract",
            "contract.md",
            "--handoff",
            "handoff.md",
            host=host,
            session=session,
            script=script,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def checkpoint(self, host="codex", script=RUNTIME):
        result = self.command("checkpoint", host=host, script=script)
        self.assertEqual(result.returncode, 0, result.stderr)

    def payload(self, mode, session=None):
        return {
            "session_id": session or self.session,
            "cwd": str(self.project),
            "hook_event_name": "SessionStart"
            if mode == "session-start"
            else "PreCompact",
            **(
                {"source": "compact"}
                if mode == "session-start"
                else {"trigger": mode[4:]}
            ),
        }

    def skill_copy(self, remove=()):
        """A relocated installation, so a message must resolve its own paths."""
        destination = self.root / "installed"
        if not destination.exists():
            shutil.copytree(hook_install.ROOT / "structured-coding", destination)
        for relative in remove:
            (destination / relative).unlink()
        return destination / "scripts/continuity.py"

    def event(self, mode, host="codex", session=None, raw=None, cwd=None,
              script=RUNTIME):
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "event",
                "--host",
                host,
                "--project",
                str(self.project),
                "--event",
                mode,
            ],
            input=raw if raw is not None else json.dumps(self.payload(mode, session)),
            text=True,
            capture_output=True,
            cwd=cwd,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout), result.stderr

    def state(self, host="codex", session=None):
        repo = runtime.Repository(self.project)
        return repo.session_dir(host, session or self.session)


class ContinuityTests(WorktreeTest):
    def test_unbound_session_in_nested_repository_is_not_blocked(self):
        nested = self.project / "nested-repo"
        nested.mkdir()
        subprocess.check_call(["git", "-C", str(nested), "init", "-q"])
        payload = self.payload("pre-manual")
        payload["cwd"] = str(nested)
        self.assertEqual(runtime.event(self.project, "codex", "pre-manual", payload), {})

    def test_a_binding_records_an_optional_base_revision(self):
        self.assertEqual(self.command("activate", "--pr", "P", "--design", "design.md",
                                      "--contract", "contract.md", "--handoff", "handoff.md",
                                      "--base", "main").returncode, 0)
        record = json.loads((self.state() / "active.json").read_text())
        self.assertEqual(record["schema"], 2)
        self.assertEqual(record["base"], "main")

    def test_a_binding_without_a_base_is_ordinary(self):
        self.activate()
        record = json.loads((self.state() / "active.json").read_text())
        self.assertEqual(record["schema"], 2)
        self.assertNotIn("base", record)
        self.checkpoint()  # the binding is still usable end to end

    def test_a_base_that_reads_as_an_option_is_refused(self):
        """argparse rejects a bare -x value; --base=-x reaches our own check."""
        for options in (["--base", "--upload-pack=evil"],
                        ["--base=--upload-pack=evil"],
                        ["--base", ""],
                        ["--base", "   "]):
            with self.subTest(options=" ".join(options)):
                result = self.command("activate", "--pr", "P", "--design", "design.md",
                                      "--contract", "contract.md",
                                      "--handoff", "handoff.md", *options)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse((self.state() / "active.json").exists())

    def test_a_previous_release_binding_still_loads_with_its_digest_intact(self):
        """Rewriting a schema-1 record would invalidate every checkpoint hashed from it."""
        self.activate()
        path = self.state() / "active.json"
        record = json.loads(path.read_text())
        record["schema"] = 1
        legacy = runtime.encoded(record)
        path.write_bytes(legacy)
        digest_before = runtime.digest(legacy)
        loaded = runtime.active_record(
            runtime.Repository(self.project), self.state(), "codex", self.session
        )
        self.assertEqual(loaded["schema"], 1)
        self.assertEqual(runtime.digest(runtime.encoded(loaded)), digest_before)
        self.assertEqual(path.read_bytes(), legacy)

    @unittest.skipIf(sys.version_info < (3, 11), "-P and PYTHONSAFEPATH are 3.11+")
    def test_every_runtime_script_imports_without_a_path_default(self):
        """A hook launched under python3 -P must still reach its shared helpers.

        The import sits above main()'s try, so failing there exits non-zero
        without the empty result a hook is required to return. Older interpreters
        have no safe-path mode, so the failure cannot arise there."""
        skill = hook_install.ROOT / "structured-coding/scripts"
        for name in ("continuity", "checkpoints", "standards"):
            with self.subTest(script=name):
                result = subprocess.run(
                    [sys.executable, "-P", "-c",
                     "import importlib.util,sys;"
                     f"spec=importlib.util.spec_from_file_location({name!r},"
                     f" {str(skill / f'{name}.py')!r});"
                     "m=importlib.util.module_from_spec(spec);"
                     "spec.loader.exec_module(m)"],
                    capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_fixture_disables_git_background_maintenance(self):
        """Housekeeping locks otherwise appear mid-test in whole-tree comparisons."""
        for key, expected in (("maintenance.auto", "false"), ("gc.auto", "0")):
            with self.subTest(key=key):
                self.assertEqual(
                    self.git("config", "--get", key).decode().strip(), expected
                )

    def test_absent_cwd_does_not_fall_back_to_the_process_directory(self):
        """A payload without cwd must not be read as "the hook ran in the project"."""
        self.activate()
        self.checkpoint()
        payload = self.payload("pre-manual")
        del payload["cwd"]
        # Run from the project root: a fallback to the process directory would pass.
        output, _ = self.event("pre-manual", raw=json.dumps(payload), cwd=self.project)
        self.assertFalse(output["continue"])
        self.assertIn("cwd", output["stopReason"])
        # The same refusal must never block an unavoidable automatic compaction.
        automatic = self.payload("pre-auto")
        del automatic["cwd"]
        output, stderr = self.event(
            "pre-auto", raw=json.dumps(automatic), cwd=self.project
        )
        self.assertEqual(output, {})
        self.assertIn("Recovery required", stderr)

    def test_relative_or_malformed_cwd_is_refused_for_a_bound_session(self):
        self.activate()
        self.checkpoint()
        for value in ("relative/path", "", 17, None):
            with self.subTest(cwd=value):
                payload = self.payload("pre-manual")
                payload["cwd"] = value
                output, _ = self.event(
                    "pre-manual", raw=json.dumps(payload), cwd=self.project
                )
                self.assertFalse(output["continue"])
                self.assertIn("cwd", output["stopReason"])

    def test_malformed_cwd_does_not_impose_on_an_unbound_session(self):
        payload = self.payload("pre-manual")
        del payload["cwd"]
        self.assertEqual(
            self.event("pre-manual", raw=json.dumps(payload), cwd=self.project)[0], {}
        )

    def test_unbound_chat_is_not_blocked(self):
        self.assertEqual(self.event("pre-manual")[0], {})
        self.assertEqual(self.event("pre-auto")[0], {})
        self.assertFalse((self.project / ".git/structured-coding-continuity").exists())
        self.assertIn(
            "no PR is bound",
            self.event("session-start")[0]["hookSpecificOutput"]["additionalContext"],
        )

    def test_manual_compact_needs_checkpoint_then_passes_on_both_hosts(self):
        for host in runtime.HOSTS:
            self.activate(host)
            denied = self.event("pre-manual", host)[0]
            if host == "codex":
                self.assertIs(denied["continue"], False)
                self.assertNotIn("decision", denied)
            else:
                self.assertEqual(denied["decision"], "block")
                self.assertNotIn("continue", denied)
            self.checkpoint(host)
            self.assertEqual(self.event("pre-manual", host)[0], {})

    def test_content_change_with_restored_mtime_is_detected(self):
        self.activate()
        self.checkpoint()
        file = self.project / "code.py"
        before = file.stat()
        original = file.read_bytes()
        file.write_bytes(b"X" * len(original))
        os.utime(file, ns=(before.st_atime_ns, before.st_mtime_ns))
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_staging_changes_invalidate_checkpoint(self):
        self.activate()
        (self.project / "code.py").write_text("changed\n")
        self.checkpoint()
        self.git("add", "code.py")
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_untracked_contents_and_deletion_invalidate_checkpoint(self):
        self.activate()
        self.checkpoint()
        file = self.project / "new.py"
        file.write_text("one")
        self.assertIs(self.event("pre-manual")[0]["continue"], False)
        self.checkpoint()
        file.write_text("two")
        self.assertIs(self.event("pre-manual")[0]["continue"], False)
        self.checkpoint()
        (self.project / "code.py").unlink()
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_explicit_ignored_handoff_is_hashed(self):
        self.git("rm", "--cached", "handoff.md")
        (self.project / ".gitignore").write_text("handoff.md\n")
        self.activate()
        self.checkpoint()
        (self.project / "handoff.md").write_text("changed ignored handoff")
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_automatic_snapshot_is_content_free_and_does_not_make_manual_fresh(self):
        self.activate()
        secret = "PRIVATE_BODY_DO_NOT_COPY_123456"
        (self.project / "code.py").write_text(secret)
        self.assertEqual(self.event("pre-auto")[0], {})
        path = self.state() / "rescue.json"
        first = path.read_bytes()
        rescue = json.loads(first)
        self.assertTrue(rescue["recovery_required"])
        self.assertNotIn(secret.encode(), first)
        self.assertNotIn("test_result", rescue)
        self.assertEqual(self.event("pre-auto")[0], {})
        self.assertEqual(first, path.read_bytes())
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_automatic_snapshot_failure_warns_and_allows(self):
        self.activate()
        with patch.object(
            runtime.Repository, "snapshot", side_effect=OSError("disk failure")
        ):
            self.assertEqual(
                runtime.event(
                    self.project, "codex", "pre-auto", self.payload("pre-auto")
                ),
                {},
            )
        rescue = json.loads((self.state() / "rescue.json").read_bytes())
        self.assertIn("warning", rescue)
        message = self.event("session-start")[0]["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("Snapshot unavailable", message)

    def test_snapshot_write_failure_does_not_block_automatic_compact(self):
        self.activate()
        rescue = self.state() / "rescue.json"
        rescue.mkdir()
        output, stderr = self.event("pre-auto")
        self.assertEqual(output, {})
        self.assertIn("snapshot failed", stderr)
        self.assertIn(
            "RECOVERY REQUIRED",
            self.event("session-start")[0]["hookSpecificOutput"]["additionalContext"],
        )

    def test_malformed_input_has_host_specific_manual_denial_but_never_blocks_auto(
        self,
    ):
        for host in runtime.HOSTS:
            for raw in ("{bad", "[]", "{}", "x" * (runtime.MAX_INPUT + 1)):
                with self.subTest(host=host, raw=raw[:8]):
                    manual = self.event("pre-manual", host, raw=raw)[0]
                    self.assertTrue(
                        manual.get("continue") is False
                        or manual.get("decision") == "block"
                    )
                    self.assertEqual(self.event("pre-auto", host, raw=raw)[0], {})

    def test_sessions_are_isolated_and_resume_requires_full_reads(self):
        self.activate()
        self.checkpoint()
        self.assertEqual(self.event("pre-manual", session="session-B")[0], {})
        message = self.event("session-start")[0]["hookSpecificOutput"][
            "additionalContext"
        ]
        for value in (
            "PR-1",
            "design.md",
            "contract.md",
            "handoff.md",
            "IN FULL",
            "implementation-working-rules.md",
            "test-ci-gate-rules.md",
            "reuse existing jobs",
        ):
            self.assertIn(value, message)
        self.assertNotIn("Initial design.md", message)

    def context(self, script=RUNTIME):
        return self.event("session-start", script=script)[0]["hookSpecificOutput"][
            "additionalContext"
        ]

    def test_session_start_names_the_installed_entrypoint_absolutely(self):
        relocated = self.skill_copy()
        self.assertNotEqual(relocated.parents[1], RUNTIME.parents[1])
        for script in (RUNTIME, relocated):
            with self.subTest(script=str(script), state="unbound"):
                expected = str(script.resolve().parents[1] / "SKILL.md")
                self.assertTrue(Path(expected).is_absolute())
                message = self.context(script)
                self.assertIn(expected, message)
                self.assertIn("required", message)
        self.activate()
        for script in (RUNTIME, relocated):
            with self.subTest(script=str(script), state="recovery"):
                expected = str(script.resolve().parents[1] / "SKILL.md")
                message = self.context(script)
                self.assertIn(expected, message)
                # The entrypoint leads the read list; the prompts follow it.
                self.assertLess(
                    message.index(expected),
                    message.index("implementation-working-rules.md"),
                )

    def test_absent_entrypoint_is_omitted_rather_than_fabricated(self):
        script = self.skill_copy(remove=("SKILL.md",))
        absent = str(script.resolve().parents[1] / "SKILL.md")
        unbound = self.context(script)
        self.assertNotIn(absent, unbound)
        self.assertIn("no PR is bound", unbound)
        self.activate()
        recovery = self.context(script)
        self.assertNotIn(absent, recovery)
        self.assertIn("IN FULL", recovery)
        self.assertIn("implementation-working-rules.md", recovery)

    def test_changed_branch_cannot_reuse_checkpoint(self):
        self.activate()
        self.checkpoint()
        self.git("switch", "-c", "other")
        self.assertIs(self.event("pre-manual")[0]["continue"], False)
        message = self.event("session-start")[0]["hookSpecificOutput"][
            "additionalContext"
        ]
        self.assertIn("Branch mismatch", message)

    def test_closed_binding_is_not_executed_and_rebinding_invalidates_checkpoint(self):
        self.activate()
        self.checkpoint()
        self.assertEqual(self.command("deactivate").returncode, 0)
        self.assertIn(
            "CLOSED",
            self.event("session-start")[0]["hookSpecificOutput"]["additionalContext"],
        )
        self.assertEqual(self.event("pre-manual")[0], {})
        self.activate()
        self.assertIs(self.event("pre-manual")[0]["continue"], False)

    def test_active_binding_cannot_be_silently_replaced(self):
        self.activate()
        result = self.command(
            "activate",
            "--pr",
            "other",
            "--design",
            "design.md",
            "--contract",
            "contract.md",
            "--handoff",
            "handoff.md",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(
            json.loads((self.state() / "active.json").read_bytes())["pr"], "PR-1"
        )

    def test_symlink_document_and_metadata_are_rejected(self):
        outside = self.root / "outside.md"
        outside.write_text("private")
        (self.project / "link.md").symlink_to(outside)
        result = self.command(
            "activate",
            "--pr",
            "one",
            "--design",
            "link.md",
            "--contract",
            "contract.md",
            "--handoff",
            "handoff.md",
        )
        self.assertNotEqual(result.returncode, 0)
        self.activate()
        (self.state() / "checkpoint.json").symlink_to(outside)
        self.assertIs(self.event("pre-manual")[0]["continue"], False)
        self.assertNotEqual(self.command("checkpoint").returncode, 0)
        self.assertEqual(outside.read_text(), "private")

    def test_worktree_binding_cannot_be_copied_to_another_worktree(self):
        self.activate()
        second = self.root / "second"
        self.git("worktree", "add", "-b", "second", str(second))
        repo = runtime.Repository(second)
        second_state = repo.session_dir("codex", self.session)
        runtime.atomic_json(
            second_state / "active.json",
            json.loads((self.state() / "active.json").read_bytes()),
        )
        with self.assertRaisesRegex(ValueError, "another worktree"):
            runtime.active_record(repo, second_state, "codex", self.session)

    def test_metadata_does_not_invalidate_its_own_checkpoint(self):
        self.activate()
        self.checkpoint()
        self.event("pre-auto")
        self.assertEqual(self.event("pre-manual")[0], {})

    def test_snapshot_budget_failure_is_explicit(self):
        self.activate()
        repo = runtime.Repository(self.project)
        active = json.loads((self.state() / "active.json").read_bytes())
        with patch.object(runtime, "MAX_FILES", 1):
            with self.assertRaisesRegex(ValueError, "10000-file"):
                repo.snapshot(active)


class HookInstallTests(WorktreeTest):
    def test_cli_opt_in_check_repeat_and_remove(self):
        for options in (("--hooks", "continuity"), ("--hooks", "continuity"),
                        ("--check-hooks",), ("--remove-hooks",)):
            with self.subTest(options=options), patch.object(sys, "argv", [
                "install", "codex", "--project", str(self.project), *options
            ]):
                self.assertEqual(installer.main(), 0)
        self.assertFalse((self.project / ".codex/hooks.json").exists())
        self.assertTrue((self.project / ".agents/skills/structured-coding/SKILL.md").exists())

    def setUp(self):
        super().setUp()
        versions = patch.object(hook_install, "version", return_value="test-protocol")
        versions.start()
        self.addCleanup(versions.stop)

    def install_hooks(self, host="codex"):
        plan = hook_install.prepare(host, self.project)
        if not plan["skill"].exists():
            installer.install(host, self.project)
        hook_install.apply(plan)
        return plan

    def portable_groups(self, host):
        """Install both presets, then build the same registration portably."""
        presets = ("continuity", "checkpoints")
        plan = hook_install.prepare(host, self.project, presets)
        if not plan["skill"].exists():
            installer.install(host, self.project)
        hook_install.apply(plan)
        return plan, hook_install.groups(
            host, self.project, plan["skill"], presets, hook_install.PORTABLE
        )

    def shell(self, command, payload, cwd, host, root=None):
        """Run a registered command the way a host does: through a shell."""
        environment = dict(os.environ)
        environment.pop("CLAUDE_PROJECT_DIR", None)
        if host == "claude-code" and root is not None:
            environment["CLAUDE_PROJECT_DIR"] = str(root)
        return subprocess.run(
            command,
            shell=True,
            cwd=str(cwd),
            env=environment,
            input=json.dumps(payload),
            text=True,
            capture_output=True,
        )

    def commit_payload(self):
        return {
            "session_id": self.session,
            "cwd": str(self.project),
            "hook_event_name": "PreToolUse",
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m portable"},
        }

    def test_portable_commands_run_and_resolve_the_bound_project(self):
        """The only proof that a portable registration actually reaches the project."""
        nested = self.project / "nested"
        nested.mkdir(exist_ok=True)
        for host in runtime.HOSTS:
            with self.subTest(host=host):
                plan, portable = self.portable_groups(host)
                self.activate(host, script=plan["skill"] / "scripts/continuity.py")
                self.checkpoint(host, plan["skill"] / "scripts/continuity.py")
                for event, index, payload in (
                    ("SessionStart", 0, self.payload("session-start")),
                    ("PreToolUse", 0, self.commit_payload()),
                ):
                    with self.subTest(event=event):
                        command = portable[event][index]["hooks"][0]["command"]
                        self.assertNotIn(str(self.project), command)
                        self.assertNotIn(sys.executable, command)
                        if event == "SessionStart":
                            payload["cwd"] = str(nested)
                        result = self.shell(
                            command, payload, nested, host, root=self.project
                        )
                        self.assertEqual(result.returncode, 0, result.stderr)
                        context = json.loads(result.stdout)["hookSpecificOutput"]
                        # Naming the bound PR proves the correct project resolved.
                        self.assertIn("PR-1", context["additionalContext"])

    def test_portable_commands_do_not_silently_serve_a_linked_worktree(self):
        """The two hosts resolve a worktree differently; neither may claim success."""
        linked = self.root / "linked worktree with 'quote'"
        self.git("worktree", "add", "-q", "-b", "linked", str(linked))
        for host in runtime.HOSTS:
            with self.subTest(host=host):
                plan, portable = self.portable_groups(host)
                self.activate(host, script=plan["skill"] / "scripts/continuity.py")
                command = portable["SessionStart"][0]["hooks"][0]["command"]
                payload = self.payload("session-start")
                payload["cwd"] = str(linked)
                result = self.shell(command, payload, linked, host, root=self.project)
                # Codex resolves the worktree root and finds no installed skill;
                # Claude Code keeps the original root and reports the cwd mismatch.
                # Either way the bound PR must not be presented as current here.
                self.assertNotIn("PR-1", result.stdout)

    def test_portable_claude_command_fails_loudly_without_its_variable(self):
        """An unexpanded root must not look like an ordinary quiet hook result."""
        plan, portable = self.portable_groups("claude-code")
        self.activate("claude-code", script=plan["skill"] / "scripts/continuity.py")
        command = portable["SessionStart"][0]["hooks"][0]["command"]
        result = self.shell(command, self.payload("session-start"), self.project,
                            "claude-code", root=None)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("PR-1", result.stdout)

    def test_each_host_installs_and_removes_only_owned_groups(self):
        for host in runtime.HOSTS:
            with self.subTest(host=host):
                _, config, _, _ = hook_install.locations(host, self.project)
                config.parent.mkdir(exist_ok=True)
                original = b'{ "permissions": {"deny": ["Bash(keep)"]}, "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo existing"}]}]}}\n'
                config.write_bytes(original)
                plan = self.install_hooks(host)
                settings = json.loads(config.read_bytes())
                self.assertEqual(
                    settings["permissions"], json.loads(original)["permissions"]
                )
                self.assertEqual(len(settings["hooks"]["SessionStart"]), 2)
                self.assertEqual(len(settings["hooks"]["PreCompact"]), 2)
                self.assertIn("match", hook_install.doctor(host, self.project))
                second = self.install_hooks(host)
                self.assertTrue(second["noop"])
                hook_install.remove(host, self.project)
                self.assertEqual(config.read_bytes(), original)
                self.assertTrue(plan["skill"].is_dir())

    def test_remove_preserves_settings_added_after_install(self):
        plan = self.install_hooks()
        settings = json.loads(plan["config"].read_bytes())
        settings["description"] = "added later"
        plan["config"].write_text(json.dumps(settings))
        hook_install.remove("codex", self.project)
        self.assertEqual(
            json.loads(plan["config"].read_bytes()), {"description": "added later"}
        )

    def test_new_config_removed_but_runtime_state_retained(self):
        plan = self.install_hooks()
        self.activate()
        hook_install.remove("codex", self.project)
        self.assertFalse(plan["config"].exists())
        self.assertTrue((self.state() / "active.json").exists())

    def test_dry_run_never_writes(self):
        before = set(self.project.rglob("*"))
        with patch.object(
            sys,
            "argv",
            [
                "install",
                "codex",
                "--project",
                str(self.project),
                "--hooks",
                "continuity",
                "--dry-run",
            ],
        ):
            self.assertEqual(installer.main(), 0)
        self.assertEqual(before, set(self.project.rglob("*")))

    def test_modified_owned_group_is_not_removed(self):
        plan = self.install_hooks()
        settings = json.loads(plan["config"].read_bytes())
        settings["hooks"]["PreCompact"][0]["hooks"][0]["command"] = "customized"
        content = json.dumps(settings).encode()
        plan["config"].write_bytes(content)
        with self.assertRaisesRegex(ValueError, "changed or removed"):
            hook_install.remove("codex", self.project)
        self.assertEqual(plan["config"].read_bytes(), content)

    def test_stale_plan_never_overwrites_a_config_edit(self):
        plan = hook_install.prepare("codex", self.project)
        installer.install("codex", self.project)
        plan["config"].parent.mkdir()
        plan["config"].write_text('{"description":"keep"}')
        with self.assertRaisesRegex(ValueError, "changed"):
            hook_install.apply(plan)
        self.assertEqual(
            json.loads(plan["config"].read_bytes()), {"description": "keep"}
        )
        self.assertFalse(plan["receipt"].exists())

    def test_failed_config_publication_removes_only_our_receipt(self):
        plan = hook_install.prepare("codex", self.project)
        installer.install("codex", self.project)
        original_replace = hook_install.replace

        def fail_config(path, expected, replacement):
            if path == plan["config"]:
                raise OSError("disk full")
            return original_replace(path, expected, replacement)

        with patch.object(hook_install, "replace", side_effect=fail_config):
            with self.assertRaises(OSError):
                hook_install.apply(plan)
        self.assertFalse(plan["receipt"].exists())
        self.assertFalse(plan["config"].exists())
        self.assertTrue(plan["skill"].exists())

    def test_malformed_and_duplicate_settings_are_not_overwritten(self):
        _, config, _, _ = hook_install.locations("codex", self.project)
        config.parent.mkdir()
        for value in (b"{bad", b'{"hooks":[],"hooks":{}}', b"[]"):
            config.write_bytes(value)
            with self.assertRaises(ValueError):
                hook_install.prepare("codex", self.project)
            self.assertEqual(config.read_bytes(), value)

    def test_symlink_config_cannot_redirect_install(self):
        outside = self.root / "outside.json"
        outside.write_text("{}")
        (self.project / ".codex").mkdir()
        (self.project / ".codex/hooks.json").symlink_to(outside)
        with self.assertRaisesRegex(ValueError, "redirected"):
            hook_install.prepare("codex", self.project)
        self.assertEqual(outside.read_text(), "{}")

    def test_installed_command_runs_from_subdirectory_with_quoted_paths(self):
        for host in runtime.HOSTS:
            plan = self.install_hooks(host)
            script = plan["skill"] / "scripts/continuity.py"
            self.activate(host, script=script)
            self.checkpoint(host, script)
            nested = self.project / "nested"
            nested.mkdir(exist_ok=True)
            for mode, event_name, index in (
                ("pre-manual", "PreCompact", 0),
                ("pre-auto", "PreCompact", 1),
                ("session-start", "SessionStart", 0),
            ):
                command = plan["groups"][event_name][index]["hooks"][0]["command"]
                payload = self.payload(mode)
                payload["cwd"] = str(nested)
                result = self.shell(command, payload, nested, host, root=self.project)
                self.assertEqual(result.returncode, 0, result.stderr)
                output = json.loads(result.stdout)
                if mode == "session-start":
                    self.assertIn(
                        "PR-1", output["hookSpecificOutput"]["additionalContext"]
                    )
                else:
                    self.assertEqual(output, {})

    def test_disabled_project_hooks_are_not_silently_enabled(self):
        (self.project / ".codex").mkdir()
        (self.project / ".codex/config.toml").write_text("[features]\nhooks = false\n")
        with self.assertRaisesRegex(ValueError, "disables"):
            hook_install.prepare("codex", self.project)
        (self.project / ".claude").mkdir()
        (self.project / ".claude/settings.local.json").write_text(
            '{"disableAllHooks":true}'
        )
        with self.assertRaisesRegex(ValueError, "disable"):
            hook_install.prepare("claude-code", self.project)


class VersionTests(unittest.TestCase):
    def test_old_missing_and_unknown_host_versions_fail(self):
        with patch.object(hook_install.shutil, "which", return_value=None):
            with self.assertRaises(ValueError):
                hook_install.version("codex")
        for host, text in (("codex", "codex-cli 0.1.0"), ("claude-code", "unknown")):
            with (
                patch.object(hook_install.shutil, "which", return_value="fake"),
                patch.object(
                    hook_install.subprocess,
                    "run",
                    return_value=subprocess.CompletedProcess([], 0, text, ""),
                ),
            ):
                with self.assertRaises(ValueError):
                    hook_install.version(host)


if __name__ == "__main__":
    unittest.main()
