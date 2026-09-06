"""Deterministic adapter/state tests; these do not claim native host delivery."""

import copy
import importlib.util
import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

from test_continuity import WorktreeTest
from test_continuity import runtime as continuity

sys.dont_write_bytecode = True
sys.modules["continuity"] = continuity
SCRIPT = continuity.Path(continuity.__file__).with_name("checkpoints.py")
spec = importlib.util.spec_from_file_location("checkpoints", SCRIPT)
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class CheckpointsTests(WorktreeTest):
    def helper(self, action, host="codex"):
        return self.command(action, host=host, script=SCRIPT)

    def report(self, host="codex"):
        return json.loads(self.helper("inspect", host).stdout)

    def payload(self, mode, session=None):
        return {
            "hook_event_name": "Stop" if mode == "stop" else "PreToolUse",
            "session_id": session or self.session,
            "cwd": str(self.project),
            "stop_hook_active": False,
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "semantic milestone"'},
        }

    def event(self, mode, host="codex", payload=None):
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "event",
                "--host",
                host,
                "--project",
                str(self.project),
                "--event",
                mode,
            ],
            input=json.dumps(payload or self.payload(mode)),
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        output = json.loads(result.stdout)
        self.assertFalse(
            {"decision", "continue", "permissionDecision", "updatedInput"}
            & output.keys()
        )
        if mode == "stop":
            self.assertFalse(set(output) - {"systemMessage"})
        return output, result.stderr

    def test_freshness_both_hosts_and_inspection_has_no_writes(self):
        for host in runtime.HOSTS:
            self.assertEqual(self.report(host)["freshness"], "unbound")
            self.assertFalse(self.state(host).exists())
            self.activate(host)
            self.assertEqual(self.report(host)["freshness"], "missing")
            self.checkpoint(host)
            before = {p.name: p.read_bytes() for p in self.state(host).iterdir()}
            self.assertEqual(self.report(host)["freshness"], "fresh")
            self.assertEqual(
                before, {p.name: p.read_bytes() for p in self.state(host).iterdir()}
            )
            (self.project / "code.py").write_text(host)
            self.assertEqual(self.report(host)["freshness"], "stale")
            self.command("deactivate", host=host)
            self.assertEqual(self.report(host)["freshness"], "closed")
            self.assertNotEqual(self.helper("prepare-review", host).returncode, 0)

    def test_ignored_document_missing_unreadable_and_cancel(self):
        self.git("rm", "--cached", "handoff.md")
        (self.project / ".gitignore").write_text("handoff.md\n")
        self.activate()
        self.checkpoint()
        self.assertEqual(self.helper("prepare-review").returncode, 0)
        checkpoint = (self.state() / "checkpoint.json").read_bytes()
        (self.project / "handoff.md").write_text("new ignored handoff")
        self.assertEqual(self.report()["freshness"], "stale")
        (self.project / "handoff.md").unlink()
        self.assertEqual(self.report()["freshness"], "missing")
        self.assertNotEqual(self.helper("inspect").returncode, 0)
        self.assertEqual(self.helper("cancel-review").returncode, 0)
        (self.project / "handoff.md").symlink_to(self.project / "design.md")
        self.assertEqual(self.report()["freshness"], "unavailable")
        self.assertEqual(checkpoint, (self.state() / "checkpoint.json").read_bytes())
        self.assertEqual(self.event("stop")[0], {})

    def test_recognition_scope_and_unchanged_input(self):
        self.activate()
        for command in [
            "git commit",
            '/usr/bin/git commit -m "two words"',
            "git commit -m 'message'",
        ]:
            payload = self.payload("pre-commit")
            payload["tool_input"]["command"] = command
            original = copy.deepcopy(payload)
            output = runtime.event(self.project, "codex", "pre-commit", payload)
            self.assertEqual(payload, original)
            self.assertEqual(
                set(output["hookSpecificOutput"]),
                {"hookEventName", "additionalContext"},
            )
        for command in [
            "echo git commit",
            "git -C . commit",
            "env git commit",
            "git commit; pwd",
            "git commit && pwd",
            "git commit > log",
            'git commit -m "$(pwd)"',
            "git commit -m `pwd`",
            "GIT_DIR=.git git commit",
            "sh script",
            "git commit\npwd",
            'git commit -m "unterminated',
            "./git commit",
        ]:
            with self.subTest(command=command):
                payload = self.payload("pre-commit")
                payload["tool_input"]["command"] = command
                self.assertEqual(self.event("pre-commit", payload=payload)[0], {})
        nested = self.project / "nested"
        nested.mkdir()
        subprocess.run(["git", "-C", str(nested), "init", "-q"], check=True)
        payload = self.payload("pre-commit")
        payload["cwd"] = str(nested)
        self.assertEqual(self.event("pre-commit", payload=payload)[0], {})
        payload = self.payload("pre-commit")
        payload["tool_name"] = "mcp__exec"
        self.assertEqual(self.event("pre-commit", payload=payload)[0], {})

    def test_explicit_intent_is_at_most_once_for_both_hosts(self):
        for host in runtime.HOSTS:
            self.activate(host)
            self.assertEqual(self.event("stop", host)[0], {})
            self.assertEqual(self.helper("prepare-review", host).returncode, 0)
            self.assertFalse((self.state(host) / "checkpoint.json").exists())
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(
                    pool.map(lambda _, host=host: self.event("stop", host)[0], range(2))
                )
            self.assertEqual(sum("systemMessage" in r for r in results), 1)
            record = json.loads(
                (self.state(host) / "checkpoints-review.json").read_text()
            )
            self.assertEqual(record["state"], "consumed")
            self.assertFalse({"approved", "ready", "passed"} & record.keys())
            self.assertEqual(
                json.loads(self.helper("prepare-review", host).stdout)["notice"],
                "consumed",
            )
            self.assertEqual(self.event("stop", host)[0], {})
            (self.project / "code.py").write_text(host + " changed")
            self.assertEqual(
                json.loads(self.helper("prepare-review", host).stdout)["notice"],
                "pending",
            )
            self.assertEqual(self.helper("cancel-review", host).returncode, 0)
            self.assertEqual(
                json.loads(self.helper("prepare-review", host).stdout)["notice"],
                "cancelled",
            )

    def test_stop_active_invalid_fields_and_prose_do_not_consume(self):
        self.activate()
        self.helper("prepare-review")
        for value in [True, None, "false", 0]:
            payload = self.payload("stop")
            payload["stop_hook_active"] = value
            self.assertEqual(self.event("stop", payload=payload)[0], {})
        payload = self.payload("stop")
        del payload["cwd"]
        self.assertEqual(self.event("stop", payload=payload)[0], {})
        self.assertEqual(
            json.loads((self.state() / "checkpoints-review.json").read_text())["state"],
            "pending",
        )
        payload = self.payload("stop")
        payload["last_assistant_message"] = "Budget exhausted; pending check not run."
        self.assertIn("systemMessage", self.event("stop", payload=payload)[0])
        self.assertEqual(self.event("stop", payload=payload)[0], {})

    def test_branch_rebind_and_document_identity_cancel(self):
        self.activate()
        self.helper("prepare-review")
        self.git("switch", "-c", "other")
        self.assertEqual(self.report()["freshness"], "unavailable")
        self.assertIn("cancelled", self.event("stop")[0]["systemMessage"])
        self.assertEqual(self.event("stop")[0], {})
        self.command("deactivate")
        self.activate()
        self.helper("prepare-review")
        self.command("deactivate")
        self.activate()
        self.assertIn("cancelled", self.event("stop")[0]["systemMessage"])
        self.helper("prepare-review")
        path = self.state() / "active.json"
        active = json.loads(path.read_text())
        active["handoff"] = "design.md"
        path.write_text(json.dumps(active))
        self.assertIn("cancelled", self.event("stop")[0]["systemMessage"])

    def test_failed_consumption_emits_no_notice_and_does_not_change_intent(self):
        self.activate()
        self.helper("prepare-review")
        before = (self.state() / "checkpoints-review.json").read_bytes()
        with (
            patch.object(runtime, "atomic_json", side_effect=OSError("private detail")),
            self.assertRaises(OSError),
        ):
            runtime.event(self.project, "codex", "stop", self.payload("stop"))
        self.assertEqual(
            before, (self.state() / "checkpoints-review.json").read_bytes()
        )
        with runtime.locked(self.state()):
            output, diagnostic = self.event("stop")
        self.assertEqual(output, {})
        self.assertIn("unavailable", diagnostic)
        self.assertIn("systemMessage", self.event("stop")[0])

    def test_metadata_symlink_session_isolation_and_output_budget(self):
        self.activate()
        self.helper("prepare-review")
        payload = self.payload("stop", session="session-B")
        self.assertEqual(self.event("stop", payload=payload)[0], {})
        self.assertNotEqual(
            self.command(
                "inspect", "--project", str(self.project / ".git"), script=SCRIPT
            ).returncode,
            0,
        )
        path = self.state() / "checkpoints-review.json"
        saved = path.read_bytes()
        path.unlink()
        path.symlink_to(self.project / "design.md")
        output, diagnostic = self.event("stop")
        self.assertEqual(output, {})
        self.assertIn("unavailable", diagnostic)
        path.unlink()
        path.write_bytes(saved)
        text = runtime.bounded("界" * 12000)
        self.assertLessEqual(len(json.dumps(text, ensure_ascii=True)), 8000)
        self.assertIn("omitted", text)
