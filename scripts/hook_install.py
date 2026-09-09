"""Composable project-local hook registration with guarded transaction recovery."""

import base64
import copy
import fcntl
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FLOORS = {"codex": (0, 153, 4), "claude-code": (2, 1, 261)}
PRESETS = ("continuity", "checkpoints")
MAX_FILE = 1024 * 1024
MAX_JOURNAL = 8 * MAX_FILE

PATHS = {
    "codex": (".codex/hooks.json", ".agents"),
    "claude-code": (".claude/settings.json", ".claude"),
}

# A receipt's schema fixes the command shape that produced it, so an installation
# stays verifiable and removable after the shape written by new installs changes.
ABSOLUTE = "absolute"
SCHEMA_SHAPES = {1: ABSOLUTE, 2: ABSOLUTE}


def shape_for_schema(schema):
    if schema not in SCHEMA_SHAPES:
        raise ValueError("Installation receipt does not match a supported schema")
    return SCHEMA_SHAPES[schema]


def safe(root, relative):
    path = root
    for part in Path(relative).parts:
        if part in ("..", "/"):
            raise ValueError("Invalid installation path")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Refusing redirected installation path: {path}")
    return path


def read(path, limit=MAX_FILE):
    if path.is_symlink():
        raise ValueError(f"Refusing redirected file: {path}")
    if path.exists() and (not path.is_file() or path.stat().st_size > limit):
        raise ValueError(f"Missing regular file or size limit exceeded: {path}")
    return path.read_bytes() if path.exists() else None


def parse(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(
                    "Duplicate settings key; resolve it before hook installation"
                )
            result[key] = value
        return result

    value = json.loads(data, object_pairs_hook=unique) if data is not None else {}
    if not isinstance(value, dict) or not isinstance(value.get("hooks", {}), dict):
        raise ValueError("Host settings and hooks must be JSON objects")
    return value


def serialize(value):
    return (json.dumps(value, ensure_ascii=True, indent=2) + "\n").encode()


def version(host):
    executable = shutil.which("codex" if host == "codex" else "claude")
    if not executable:
        raise ValueError(f"Install {host} before enabling hooks")
    result = subprocess.run(
        [executable, "--version"], capture_output=True, text=True, timeout=5
    )
    match = re.search(r"\b(\d+)\.(\d+)\.(\d+)\b", result.stdout)
    if result.returncode or not match:
        raise ValueError(f"Cannot determine {host} version")
    actual = tuple(map(int, match.groups()))
    if actual < FLOORS[host]:
        minimum = ".".join(map(str, FLOORS[host]))
        raise ValueError(
            f"This preset requires {host} >= {minimum}; older protocols are not supported"
        )
    return ".".join(map(str, actual))


def locations(host, project):
    project = Path(project).expanduser().resolve(strict=True)
    result = subprocess.run(
        [
            "git",
            "-C",
            str(project),
            "rev-parse",
            "--show-toplevel",
            "--absolute-git-dir",
        ],
        capture_output=True,
        text=True,
        timeout=5,
    )
    if result.returncode or len(result.stdout.splitlines()) != 2:
        raise ValueError("Hooks require an existing, non-bare Git worktree")
    top, gitdir = result.stdout.splitlines()
    if Path(top).resolve() != project:
        raise ValueError("For hooks, --project must be the Git worktree root")
    config_path, skill_parent = PATHS[host]
    config = safe(project, config_path)
    skill = safe(project, f"{skill_parent}/skills/structured-coding")
    state = safe(Path(gitdir).resolve(), "structured-coding-continuity")
    receipt = safe(state, f"installation-{host}.json")
    return project, config, skill, receipt


def selection(presets):
    values = tuple(presets)
    if not values or len(set(values)) != len(values) or set(values) - set(PRESETS):
        raise ValueError(
            "Select each supported preset at most once: continuity checkpoints"
        )
    return tuple(p for p in PRESETS if p in values)


def registered_command(shape, host, project, skill, script, mode):
    """One registered command in the requested shape."""
    if shape != ABSOLUTE:
        raise ValueError(f"Unsupported command shape: {shape}")
    return shlex.join(
        [
            sys.executable,
            str(skill / f"scripts/{script}.py"),
            "event",
            "--host",
            host,
            "--project",
            str(project),
            "--event",
            mode,
        ]
    )


def groups(host, project, skill, presets=("continuity",), shape=ABSOLUTE):
    presets = selection(presets)
    capabilities = []
    if "continuity" in presets:
        capabilities.extend(
            [
                ("PreCompact", "^manual$", "continuity", "pre-manual"),
                ("PreCompact", "^auto$", "continuity", "pre-auto"),
            ]
        )
    capabilities.append(
        (
            "SessionStart",
            "^(startup|resume|compact|clear)$",
            "continuity",
            "session-start",
        )
    )
    if "checkpoints" in presets:
        capabilities.extend(
            [
                ("PreToolUse", "^Bash$", "checkpoints", "pre-commit"),
                ("Stop", None, "checkpoints", "stop"),
            ]
        )
    result = {}
    for event, matcher, script, mode in capabilities:
        command = registered_command(shape, host, project, skill, script, mode)
        group = {"hooks": [{"type": "command", "command": command, "timeout": 12}]}
        if matcher is not None:
            group = {"matcher": matcher, **group}
        result.setdefault(event, []).append(group)
    return result


def check_local_disablers(host, project, settings):
    if settings.get("disableAllHooks") or settings.get("allowManagedHooksOnly"):
        raise ValueError(
            "Project settings disable optional hooks; resolve this yourself before installing"
        )
    if host == "codex":
        path = safe(project, ".codex/config.toml")
        data = read(path)
        if data and (
            re.search(rb"(?m)^\s*(?:hooks|codex_hooks)\s*=\s*false\b", data)
            or re.search(rb"(?m)^\s*allow_managed_hooks_only\s*=\s*true\b", data)
        ):
            raise ValueError(
                "Project config disables optional hooks; no permission/config bypass will be installed"
            )
    else:
        data = read(safe(project, ".claude/settings.local.json"))
        if data:
            local = parse(data)
            if local.get("disableAllHooks") or local.get("allowManagedHooksOnly"):
                raise ValueError("Local project settings disable optional hooks")


def decode(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("Invalid encoded installation state")
    data = base64.b64decode(value, validate=True)
    if len(data) > MAX_FILE:
        raise ValueError("Installation state exceeds 1 MiB")
    return data


def encode(value):
    return None if value is None else base64.b64encode(value).decode()


def interpreter(owned):
    """The single Python path embedded in every owned command, if there is one."""
    found = set()
    if not isinstance(owned, dict):
        return None
    for entries in owned.values():
        for group in entries if isinstance(entries, list) else ():
            hooks = group.get("hooks") if isinstance(group, dict) else None
            for entry in hooks if isinstance(hooks, list) else ():
                command = entry.get("command") if isinstance(entry, dict) else None
                if not isinstance(command, str):
                    return None
                try:
                    words = shlex.split(command)
                except ValueError:
                    return None
                if not words:
                    return None
                found.add(words[0])
    return found.pop() if len(found) == 1 else None


def interpreter_hint(recorded):
    """A changed interpreter is the common cause of an otherwise puzzling mismatch."""
    previous = interpreter(recorded)
    if previous is None or previous == sys.executable:
        return ""
    state = "still present" if Path(previous).is_file() else "no longer present"
    return (
        f". Registered interpreter {previous} ({state}) differs from the current "
        f"{sys.executable}; reinstall with the interpreter the hooks should use"
    )


def validate_record(raw, host, project, skill, config):
    record = parse(raw)
    if record.get("schema") not in (1, 2) or record.get("config") != str(config):
        raise ValueError(
            "Installation receipt does not match this project or supported schema"
        )
    presets = (
        ("continuity",)
        if record["schema"] == 1
        else selection(record.get("presets", ()))
    )
    shape = shape_for_schema(record["schema"])
    if record.get("groups") != groups(host, project, skill, presets, shape):
        raise ValueError(
            "Owned capability paths/groups differ; inspect and explicitly upgrade the "
            "installation" + interpreter_hint(record.get("groups"))
        )
    parse(decode(record["before"]))
    return record, presets


def validate_owned(settings, owned):
    for event, entries in owned.items():
        existing = settings.get("hooks", {}).get(event, [])
        if not isinstance(existing, list) or any(
            existing.count(g) != 1 for g in entries
        ):
            raise ValueError(
                "Owned hook was changed or removed or duplicated; inspect manually instead of deleting user edits"
            )


def without_owned(settings, owned, original):
    validate_owned(settings, owned)
    result = copy.deepcopy(settings)
    for event, entries in owned.items():
        existing = result["hooks"][event]
        for group in entries:
            existing.remove(group)
        if not existing and event not in original.get("hooks", {}):
            del result["hooks"][event]
    if not result.get("hooks") and "hooks" not in original:
        result.pop("hooks", None)
    return result


def add_groups(settings, additions):
    result = copy.deepcopy(settings)
    for event, entries in additions.items():
        existing = result.setdefault("hooks", {}).setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"Invalid {event} hook list")
        for group in entries:
            if group in existing:
                raise ValueError(
                    "Owned hook exists without matching receipt; inspect manually"
                )
            existing.append(group)
    return result


def journal_path(receipt):
    return safe(receipt.parent, receipt.name + ".transaction.json")


def pending(receipt):
    return read(journal_path(receipt), MAX_JOURNAL) is not None


def prepare(host, project, presets=("continuity",)):
    requested = selection(presets)
    project, config, skill, receipt = locations(host, project)
    if pending(receipt):
        raise ValueError(
            "Pending installation recovery; retry an explicit mutating install/removal"
        )
    host_version = version(host)
    before, old_receipt = read(config), read(receipt)
    settings = parse(before)
    check_local_disablers(host, project, settings)
    original = before
    installed = ()
    if old_receipt is not None:
        record, installed = validate_record(old_receipt, host, project, skill, config)
        validate_owned(settings, record["groups"])
        original = decode(record["before"])
    selected = tuple(p for p in PRESETS if p in set(installed) | set(requested))
    # The shape a new installation writes; deliberately still the default here.
    additions = groups(host, project, skill, selected)
    noop = bool(old_receipt is not None and selected == installed)
    clean = (
        without_owned(settings, record["groups"], parse(original))
        if installed
        else settings
    )
    after = before if noop else serialize(add_groups(clean, additions))
    updated = (
        old_receipt
        if noop
        else serialize(
            {
                "schema": 2,
                "presets": list(selected),
                "groups": additions,
                "config": str(config),
                "before": encode(original),
                "after_sha256": hashlib.sha256(after).hexdigest(),
                "host_version": host_version,
            }
        )
    )
    return dict(
        noop=noop,
        host=host,
        project=project,
        skill=skill,
        config=config,
        receipt=receipt,
        version=host_version,
        presets=selected,
        before=before,
        after=after,
        groups=additions,
        old_receipt=old_receipt,
        new_receipt=updated,
    )


@contextmanager
def locked(receipt):
    directory = receipt.parent
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = safe(directory, receipt.name + ".lock")
    with lock.open("a") as stream:
        try:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(
                "Another hook installer is running; retry after it finishes"
            ) from None
        yield


def replace(path, expected, replacement):
    """Atomic file replacement with a last-moment stale-plan check."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if read(path, MAX_JOURNAL) != expected:
        raise ValueError(
            "Configuration changed during installation; no overwrite attempted"
        )
    if replacement is None:
        path.unlink(missing_ok=True)
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(replacement)
            stream.flush()
            os.fsync(stream.fileno())
            stream.close()
            if expected is not None:
                os.chmod(temporary, path.stat().st_mode & 0o777)
            if read(path, MAX_JOURNAL) != expected:
                raise ValueError("Configuration changed during installation; retry")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def verify_skill(plan):
    source = ROOT / "structured-coding"
    dependencies = {"scripts/continuity.py", "references/continuity.md"}
    if "checkpoints" in plan.get("presets", ("continuity",)):
        dependencies.update({"scripts/checkpoints.py", "references/checkpoints.md"})
    for relative in sorted(dependencies):
        path = safe(plan["skill"], relative)
        if read(path) != (source / relative).read_bytes():
            raise ValueError(
                "Installed skill lacks this preset version; compare/back up and update the skill first"
            )


def finish_transaction(host, project, config, skill, receipt):
    path = journal_path(receipt)
    raw = read(path, MAX_JOURNAL)
    if raw is None:
        return
    record = parse(raw)
    if (
        record.get("schema") != 1
        or record.get("config") != str(config)
        or record.get("receipt") != str(receipt)
    ):
        raise ValueError("Transaction journal does not match installation paths/schema")
    states = {}
    for name, target in (("config", config), ("receipt", receipt)):
        before, after = (
            decode(record[f"{name}_{phase}"]) for phase in ("before", "after")
        )
        if name == "config":
            parse(before)
            parse(after)
        else:
            for value in (before, after):
                if value is not None:
                    validate_record(value, host, project, skill, config)
        current = read(target)
        if current != before and current != after:
            raise ValueError(
                f"Pending recovery conflict in {name}; preserve user edits and reconcile manually"
            )
        states[name] = (target, current, after)
    # Both files were checked before changing either. Each replace checks again.
    for name in ("config", "receipt"):
        target, current, after = states[name]
        if current != after:
            replace(target, current, after)
    if read(config) != states["config"][2] or read(receipt) != states["receipt"][2]:
        raise ValueError(
            "Installation changed before transaction cleanup; recovery retained"
        )
    replace(path, raw, None)


def recover(host, project):
    """Only explicit mutating callers may complete an interrupted operation."""
    project, config, skill, receipt = locations(host, project)
    if pending(receipt):
        with locked(receipt):
            finish_transaction(host, project, config, skill, receipt)
        return True
    return False


def transaction(plan):
    host = plan["host"]
    project, config, skill, receipt = locations(host, plan["project"])
    with locked(receipt):
        if pending(receipt):
            finish_transaction(host, project, config, skill, receipt)
        if read(config) == plan["after"] and read(receipt) == plan["new_receipt"]:
            return
        if read(config) != plan["before"] or read(receipt) != plan["old_receipt"]:
            raise ValueError(
                "Hook installation state changed; retry without overwriting it"
            )
        if plan["noop"]:
            return
        if any(
            value is not None and len(value) > MAX_FILE
            for value in (
                plan["before"],
                plan["after"],
                plan["old_receipt"],
                plan["new_receipt"],
            )
        ):
            raise ValueError(
                "Configuration/receipt exceeds 1 MiB; no transaction started"
            )
        journal = serialize(
            {
                "schema": 1,
                "config": str(config),
                "receipt": str(receipt),
                "config_before": encode(plan["before"]),
                "config_after": encode(plan["after"]),
                "receipt_before": encode(plan["old_receipt"]),
                "receipt_after": encode(plan["new_receipt"]),
            }
        )
        if len(journal) > MAX_JOURNAL:
            raise ValueError("Installation journal exceeds 8 MiB")
        replace(journal_path(receipt), None, journal)
        finish_transaction(host, project, config, skill, receipt)


def apply(plan):
    verify_skill(plan)
    transaction(plan)


def remove(host, project, dry_run=False, presets=None):
    requested = selection(presets) if presets is not None else None
    recovered = recover(host, project) if not dry_run else False
    project, config, skill, receipt = locations(host, project)
    if pending(receipt):
        raise ValueError("Pending installation recovery; dry-run never changes it")
    raw_receipt = read(receipt)
    if raw_receipt is None:
        if recovered:
            return config
        raise ValueError("No owned hook registration found; nothing was removed")
    record, installed = validate_record(raw_receipt, host, project, skill, config)
    current = read(config)
    settings = parse(current)
    original = decode(record["before"])
    remaining = tuple(
        p for p in installed if requested is not None and p not in requested
    )
    installed_shape = shape_for_schema(record["schema"])
    # Legacy receipt-first interrupted installation remains removable without config writes.
    legacy_interrupted = record["schema"] == 1 and current == original
    if legacy_interrupted:
        remaining = ()
        after = current
    else:
        clean = without_owned(settings, record["groups"], parse(original))
        after_settings = (
            add_groups(clean, groups(host, project, skill, remaining, installed_shape))
            if remaining
            else clean
        )
        after = (
            current
            if remaining == installed
            else (
                original
                if not remaining and after_settings == parse(original)
                else serialize(after_settings)
            )
        )
    updated = raw_receipt
    if not remaining:
        updated = None
    elif remaining != installed:
        updated = serialize(
            {
                **record,
                "schema": 2,
                "presets": list(remaining),
                "groups": groups(host, project, skill, remaining, installed_shape),
                "after_sha256": hashlib.sha256(after).hexdigest(),
            }
        )
    if not dry_run:
        transaction(
            dict(
                host=host,
                project=project,
                before=current,
                after=after,
                old_receipt=raw_receipt,
                new_receipt=updated,
                noop=remaining == installed,
            )
        )
    return config


def doctor(host, project):
    project, config, skill, receipt = locations(host, project)
    if pending(receipt):
        raise ValueError(
            "Pending installation recovery; doctor is read-only; retry an explicit mutating operation"
        )
    current = parse(read(config))
    check_local_disablers(host, project, current)
    version_string = version(host)
    record, presets = validate_record(read(receipt), host, project, skill, config)
    validate_owned(current, record["groups"])
    verify_skill({"skill": skill, "presets": presets})
    return (
        f"Installed presets: {', '.join(presets)}. Registration and runtime files match "
        f"({host} {version_string}), registered interpreter {interpreter(record['groups'])}. "
        "Trust/enabled state and real host delivery still require /hooks verification."
    )
