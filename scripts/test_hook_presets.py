"""Configuration ownership and exact-state recovery, using real temporary Git roots."""

import copy
import hashlib
import json
import shlex
import sys
from pathlib import Path
from unittest.mock import patch

import hook_install as hooks
from test_continuity import WorktreeTest
from test_install import installer


class PresetTests(WorktreeTest):
    def setUp(self):
        super().setUp()
        versions = patch.object(hooks, "version", return_value="test-protocol")
        versions.start()
        self.addCleanup(versions.stop)

    def install(self, host, presets):
        plan = hooks.prepare(host, self.project, presets)
        if not plan["skill"].exists():
            installer.install(host, self.project)
        hooks.apply(plan)
        return plan

    def legacy(self, host):
        frozen = json.loads(
            (Path(__file__).parent / "fixtures/continuity-schema1.json").read_text()
        )
        self.assertEqual(
            frozen["source_commit"], "96c842aefd0b810f8d46b9709a9e7617f12f88bd"
        )
        value = copy.deepcopy(frozen["fixtures"][host])
        _, config, skill, receipt = hooks.locations(host, self.project)
        if not skill.exists():
            installer.install(host, self.project)
        for obj in (value["config"], value["receipt"]):
            for entries in obj.get("groups", obj.get("hooks", {})).values():
                for group in entries:
                    for entry in group["hooks"]:
                        words = shlex.split(entry["command"])
                        entry["command"] = shlex.join(
                            [
                                str(sys.executable)
                                if w == "PYTHON"
                                else w.replace("PROJECT", str(self.project))
                                for w in words
                            ]
                        )
        value["receipt"]["config"] = str(config)
        current = hooks.serialize(value["config"])
        value["receipt"]["after_sha256"] = hashlib.sha256(current).hexdigest()
        config.parent.mkdir(exist_ok=True)
        receipt.parent.mkdir(exist_ok=True)
        config.write_bytes(current)
        receipt.write_bytes(hooks.serialize(value["receipt"]))
        return config, skill, receipt

    def test_both_hosts_install_and_remove_orders_preserve_exact_original_and_state(
        self,
    ):
        original = b'{ "description": "keep", "hooks": {"SessionStart": []}}\n'
        for host in hooks.PATHS:
            for first in hooks.PRESETS:
                for removed in hooks.PRESETS:
                    with self.subTest(host=host, first=first, removed=removed):
                        _, config, _, receipt = hooks.locations(host, self.project)
                        config.parent.mkdir(exist_ok=True)
                        config.write_bytes(original)
                        self.install(host, [first])
                        second = next(p for p in hooks.PRESETS if p != first)
                        plan = self.install(host, [second])
                        state = json.loads(config.read_bytes())
                        self.assertEqual(sum(map(len, state["hooks"].values())), 5)
                        self.assertEqual(len(state["hooks"]["SessionStart"]), 1)
                        self.assertEqual(
                            json.loads(receipt.read_bytes())["presets"],
                            list(hooks.PRESETS),
                        )
                        before = config.read_bytes(), receipt.read_bytes()
                        self.install(host, [first])
                        self.assertEqual(
                            before, (config.read_bytes(), receipt.read_bytes())
                        )
                        hooks.remove(host, self.project, presets=[removed])
                        survivor = next(p for p in hooks.PRESETS if p != removed)
                        events = set(json.loads(config.read_bytes())["hooks"])
                        self.assertEqual(
                            events,
                            {"SessionStart", "PreCompact"}
                            if survivor == "continuity"
                            else {"SessionStart", "PreToolUse", "Stop"},
                        )
                        self.assertIn(survivor, hooks.doctor(host, self.project))
                        data = self.state(host) / "retained.json"
                        data.parent.mkdir(parents=True, exist_ok=True)
                        data.write_text("{}")
                        hooks.remove(host, self.project)
                        self.assertEqual(config.read_bytes(), original)
                        self.assertTrue(data.exists())
                        self.assertTrue(plan["skill"].exists())

    def test_check_hooks_names_a_changed_interpreter(self):
        """A groups mismatch caused by the interpreter must say so, not blame paths."""
        for host in hooks.PATHS:
            with self.subTest(host=host):
                registered = self.project.parent / f"fake-python-{host}"
                registered.write_bytes(b"")
                # Register the hooks as if a different interpreter had installed them.
                with patch.object(sys, "executable", str(registered)):
                    self.install(host, ["continuity"])
                    self.assertIn(str(registered), hooks.doctor(host, self.project))
                for state in ("still present", "no longer present"):
                    with self.subTest(state=state):
                        with self.assertRaises(ValueError) as caught:
                            hooks.doctor(host, self.project)
                        message = str(caught.exception)
                        self.assertIn("Registered interpreter", message)
                        self.assertIn(str(registered), message)
                        self.assertIn(state, message)
                        self.assertIn(sys.executable, message)
                    if state == "still present":
                        registered.unlink()

    def test_interpreter_hint_stays_silent_on_unreadable_groups(self):
        """An unrecognizable receipt must not produce a confident interpreter claim."""
        for owned in (
            "not-a-mapping",
            {"A": [{"hooks": [{"command": "/a/python x"}]}], "B": [{"hooks": [{"command": "/b/python y"}]}]},
            {"A": [{"hooks": [{"command": 17}]}]},
            {"A": [{"hooks": [{"command": "unclosed '"}]}]},
            {"A": [{"hooks": [{}]}]},
            {"A": "not-a-list"},
        ):
            with self.subTest(owned=owned):
                self.assertIsNone(hooks.interpreter(owned))
                self.assertEqual(hooks.interpreter_hint(owned), "")

    def test_legacy_noop_check_preview_upgrade_and_remove(self):
        for host in hooks.PATHS:
            config, _, receipt = self.legacy(host)
            original = hooks.decode(json.loads(receipt.read_bytes())["before"])
            before = config.read_bytes(), receipt.read_bytes()
            plan = hooks.prepare(host, self.project)
            self.assertTrue(plan["noop"])
            hooks.apply(plan)
            hooks.doctor(host, self.project)
            hooks.remove(host, self.project, dry_run=True)
            self.assertEqual(before, (config.read_bytes(), receipt.read_bytes()))
            hooks.prepare(host, self.project, ["checkpoints"])
            self.assertEqual(before, (config.read_bytes(), receipt.read_bytes()))
            self.install(host, ["checkpoints"])
            self.assertEqual(json.loads(receipt.read_bytes())["schema"], 2)
            hooks.remove(host, self.project, presets=["continuity"])
            hooks.remove(host, self.project)
            self.assertEqual(config.read_bytes(), original)
            self.legacy(host)
            hooks.remove(host, self.project)
            self.assertEqual(config.read_bytes(), original)

    def test_user_settings_edited_after_install_and_selective_absent_noop(self):
        plan = self.install("codex", ["checkpoints"])
        settings = json.loads(plan["config"].read_bytes())
        settings["permissions"] = {"deny": ["Bash(keep)"]}
        plan["config"].write_text(json.dumps(settings))
        before = plan["config"].read_bytes(), plan["receipt"].read_bytes()
        hooks.remove("codex", self.project, presets=["continuity"])
        self.assertEqual(
            before, (plan["config"].read_bytes(), plan["receipt"].read_bytes())
        )
        self.install("codex", ["continuity"])
        hooks.remove("codex", self.project, presets=["checkpoints"])
        hooks.remove("codex", self.project)
        self.assertEqual(
            json.loads(plan["config"].read_bytes()),
            {"permissions": {"deny": ["Bash(keep)"]}},
        )

    def test_journal_crash_boundaries_on_addition_and_removal(self):
        for operation in ("add", "remove"):
            for boundary in (1, 2, 3, 4):
                for after_write in (False, True):
                    with self.subTest(
                        operation=operation, boundary=boundary, after=after_write
                    ):
                        self.install("codex", ["continuity"])
                        plan = hooks.prepare("codex", self.project, ["checkpoints"])
                        if operation == "remove":
                            hooks.apply(plan)
                        real = hooks.replace
                        calls = 0

                        def interrupt(path, expected, replacement):
                            nonlocal calls
                            calls += 1
                            if calls == boundary and not after_write:
                                raise OSError("injected interruption")
                            real(path, expected, replacement)
                            if calls == boundary and after_write:
                                raise OSError("injected interruption")

                        with patch.object(hooks, "replace", side_effect=interrupt):
                            with self.assertRaises(OSError):
                                if operation == "add":
                                    hooks.apply(plan)
                                else:
                                    hooks.remove(
                                        "codex", self.project, presets=["checkpoints"]
                                    )
                        if hooks.pending(plan["receipt"]):
                            before = (
                                hooks.read(plan["config"]),
                                hooks.read(plan["receipt"]),
                                hooks.read(hooks.journal_path(plan["receipt"])),
                            )
                            with self.assertRaisesRegex(ValueError, "Pending"):
                                hooks.doctor("codex", self.project)
                            self.assertEqual(
                                before,
                                (
                                    hooks.read(plan["config"]),
                                    hooks.read(plan["receipt"]),
                                    hooks.read(hooks.journal_path(plan["receipt"])),
                                ),
                            )
                            hooks.recover("codex", self.project)
                        # Explicit retry, including pre-journal and post-cleanup interruptions.
                        if operation == "add":
                            self.install("codex", ["checkpoints"])
                        else:
                            hooks.remove("codex", self.project, presets=["checkpoints"])
                        self.assertFalse(hooks.pending(plan["receipt"]))
                        expected = (
                            ["continuity", "checkpoints"]
                            if operation == "add"
                            else ["continuity"]
                        )
                        self.assertEqual(
                            json.loads(plan["receipt"].read_bytes())["presets"],
                            expected,
                        )
                        hooks.remove("codex", self.project)

    def test_pending_recovery_refuses_either_unrecognized_target_before_writes(self):
        for target in ("config", "receipt"):
            plan = hooks.prepare("codex", self.project, ["checkpoints"])
            if not plan["skill"].exists():
                installer.install("codex", self.project)
            real = hooks.replace

            def fail_receipt(path, expected, replacement):
                if path == plan["receipt"]:
                    raise OSError("interrupted")
                return real(path, expected, replacement)

            with (
                patch.object(hooks, "replace", side_effect=fail_receipt),
                self.assertRaises(OSError),
            ):
                hooks.apply(plan)
            path = plan[target]
            known = hooks.read(path)
            path.write_text('{"user":"edit"}')
            before = hooks.read(plan["config"]), hooks.read(plan["receipt"])
            with self.assertRaisesRegex(ValueError, f"conflict in {target}"):
                hooks.recover("codex", self.project)
            self.assertEqual(
                before, (hooks.read(plan["config"]), hooks.read(plan["receipt"]))
            )
            if known is None:
                path.unlink()
            else:
                path.write_bytes(known)
            hooks.recover("codex", self.project)
            hooks.remove("codex", self.project)

    def test_ambiguous_receipts_and_owned_groups_refuse_all_paths(self):
        plan = self.install("codex", hooks.PRESETS)
        config, receipt = plan["config"], plan["receipt"]
        original_config, original_receipt = config.read_bytes(), receipt.read_bytes()
        for mutation in ("missing", "duplicate", "edited", "schema", "path"):
            settings = json.loads(original_config)
            record = json.loads(original_receipt)
            if mutation == "missing":
                settings["hooks"]["Stop"] = []
            elif mutation == "duplicate":
                settings["hooks"]["Stop"] *= 2
            elif mutation == "edited":
                settings["hooks"]["Stop"][0]["hooks"][0]["command"] = "custom"
            elif mutation == "schema":
                record["schema"] = 99
            else:
                record["config"] = "/elsewhere"
            config.write_text(json.dumps(settings))
            receipt.write_text(json.dumps(record))
            before = config.read_bytes(), receipt.read_bytes()
            for action in (
                lambda: hooks.prepare("codex", self.project, ["checkpoints"]),
                lambda: hooks.remove("codex", self.project),
                lambda: hooks.doctor("codex", self.project),
            ):
                with self.assertRaises(ValueError):
                    action()
                self.assertEqual(before, (config.read_bytes(), receipt.read_bytes()))
        config.write_bytes(original_config)
        receipt.write_bytes(original_receipt)

    def test_stale_noop_plan_concurrent_installer_and_selected_dependencies(self):
        plan = self.install("codex", ["continuity"])
        noop = hooks.prepare("codex", self.project)
        self.install("codex", ["checkpoints"])
        with self.assertRaisesRegex(ValueError, "changed"):
            hooks.apply(noop)
        plan = hooks.prepare("codex", self.project)
        with (
            hooks.locked(plan["receipt"]),
            self.assertRaisesRegex(ValueError, "Another"),
        ):
            hooks.apply(plan)
        path = plan["skill"] / "scripts/checkpoints.py"
        path.write_text("customized")
        with self.assertRaisesRegex(ValueError, "update the skill"):
            hooks.verify_skill(plan)
        self.assertEqual(path.read_text(), "customized")

    def test_redirected_journal_or_metadata_never_written(self):
        plan = self.install("codex", ["continuity"])
        target = self.root / "keep"
        target.write_text("private")
        hooks.journal_path(plan["receipt"]).symlink_to(target)
        with self.assertRaisesRegex(ValueError, "redirected"):
            hooks.recover("codex", self.project)
        self.assertEqual(target.read_text(), "private")

    def test_large_bounded_journal_and_interrupted_last_removal(self):
        _, config, _, _ = hooks.locations("codex", self.project)
        config.parent.mkdir()
        original = json.dumps({"description": "x" * 400000}).encode()
        config.write_bytes(original)
        plan = self.install("codex", ["checkpoints"])
        real = hooks.replace

        def fail_cleanup(path, expected, replacement):
            if path == hooks.journal_path(plan["receipt"]) and replacement is None:
                raise OSError("cleanup interruption")
            return real(path, expected, replacement)

        with (
            patch.object(hooks, "replace", side_effect=fail_cleanup),
            self.assertRaises(OSError),
        ):
            hooks.remove("codex", self.project)
        self.assertTrue(hooks.pending(plan["receipt"]))
        self.assertFalse(plan["receipt"].exists())
        hooks.remove("codex", self.project)
        self.assertEqual(config.read_bytes(), original)
        self.assertFalse(hooks.pending(plan["receipt"]))
