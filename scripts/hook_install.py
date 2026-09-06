"""Opt-in, project-local continuity registration. Never edits global settings."""

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
PATHS = {
    "codex": (".codex/hooks.json", ".agents"),
    "claude-code": (".claude/settings.json", ".claude"),
}


def safe(root, relative):
    path = root
    for part in Path(relative).parts:
        if part in ("..", "/"):
            raise ValueError("Invalid installation path")
        path = path / part
        if path.is_symlink():
            raise ValueError(f"Refusing redirected installation path: {path}")
    return path


def read(path):
    if path.is_symlink():
        raise ValueError(f"Refusing redirected file: {path}")
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


def groups(host, project, skill):
    command = [
        sys.executable,
        str(skill / "scripts/continuity.py"),
        "event",
        "--host",
        host,
        "--project",
        str(project),
        "--event",
    ]
    result = {}
    for event, matcher, mode in (
        ("PreCompact", "^manual$", "pre-manual"),
        ("PreCompact", "^auto$", "pre-auto"),
        ("SessionStart", "^(startup|resume|compact|clear)$", "session-start"),
    ):
        result.setdefault(event, []).append(
            {
                "matcher": matcher,
                "hooks": [
                    {
                        "type": "command",
                        "command": shlex.join(command + [mode]),
                        "timeout": 12,
                    }
                ],
            }
        )
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


def prepare(host, project):
    project, config, skill, receipt = locations(host, project)
    host_version = version(host)
    before = read(config)
    settings = parse(before)
    check_local_disablers(host, project, settings)
    additions = groups(host, project, skill)
    if receipt.exists():
        installed = parse(read(receipt))
        if installed.get("groups") == additions and all(
            settings.get("hooks", {}).get(event, []).count(group) == 1
            for event, entries in additions.items()
            for group in entries
        ):
            return {
                "noop": True,
                "project": project,
                "skill": skill,
                "config": config,
                "receipt": receipt,
                "version": host_version,
            }
        raise ValueError(
            "Existing continuity registration differs; inspect it and remove hooks before reinstalling"
        )
    after = copy.deepcopy(settings)
    hooks = after.setdefault("hooks", {})
    for event, entries in additions.items():
        existing = hooks.setdefault(event, [])
        if not isinstance(existing, list):
            raise ValueError(f"Invalid {event} hook list")
        for group in entries:
            if group in existing:
                raise ValueError(
                    "Continuity hook exists without its installation receipt; inspect manually"
                )
            existing.append(group)
    return {
        "noop": False,
        "project": project,
        "skill": skill,
        "config": config,
        "receipt": receipt,
        "version": host_version,
        "before": before,
        "after": serialize(after),
        "groups": additions,
    }


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
    if read(path) != expected:
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
            if read(path) != expected:
                raise ValueError("Configuration changed during installation; retry")
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)


def verify_skill(plan):
    source = ROOT / "structured-coding"
    for relative in ("scripts/continuity.py", "references/continuity.md"):
        path = safe(plan["skill"], relative)
        if read(path) != (source / relative).read_bytes():
            raise ValueError(
                "Installed skill lacks this continuity version; compare/back up and update the skill first"
            )


def apply(plan):
    verify_skill(plan)
    if plan["noop"]:
        return
    # Recheck parents after the skill copy; never follow a newly redirected path.
    _, config, _, receipt = locations(
        "codex" if plan["config"].name == "hooks.json" else "claude-code",
        plan["project"],
    )
    with locked(receipt):
        if read(receipt) is not None or read(config) != plan["before"]:
            raise ValueError(
                "Hook installation state changed; retry without overwriting it"
            )
        backup = {
            "schema": 1,
            "groups": plan["groups"],
            "config": str(config),
            "before": None
            if plan["before"] is None
            else base64.b64encode(plan["before"]).decode(),
            "after_sha256": hashlib.sha256(plan["after"]).hexdigest(),
            "host_version": plan["version"],
        }
        replace(receipt, None, serialize(backup))
        try:
            replace(config, plan["before"], plan["after"])
        except (OSError, ValueError):
            # This receipt belongs to this operation. The skill copy remains inert.
            receipt.unlink()
            raise


def remove(host, project, dry_run=False):
    project, config, _, receipt = locations(host, project)
    raw_receipt = read(receipt)
    if raw_receipt is None:
        raise ValueError("No owned continuity registration found; nothing was removed")
    record = parse(raw_receipt)
    if record.get("schema") != 1 or record.get("config") != str(config):
        raise ValueError("Installation receipt does not match this project")
    current = read(config)
    settings = parse(current)
    before = (
        base64.b64decode(record["before"], validate=True)
        if record["before"] is not None
        else None
    )
    # Recover an interrupted install that wrote only the receipt.
    if current == before:
        after = current
    else:
        after_settings = copy.deepcopy(settings)
        for event, entries in record["groups"].items():
            existing = after_settings.get("hooks", {}).get(event, [])
            for group in entries:
                if existing.count(group) != 1:
                    raise ValueError(
                        "Owned hook was changed or removed; inspect manually instead of deleting user edits"
                    )
                existing.remove(group)
            if not existing and event not in parse(before).get("hooks", {}):
                del after_settings["hooks"][event]
        if not after_settings.get("hooks") and "hooks" not in parse(before):
            after_settings.pop("hooks", None)
        after = before if after_settings == parse(before) else serialize(after_settings)
    if not dry_run:
        with locked(receipt):
            if read(receipt) != raw_receipt:
                raise ValueError("Installation receipt changed; retry")
            replace(config, current, after)
            receipt.unlink()
    return config


def doctor(host, project):
    project, config, skill, receipt = locations(host, project)
    current = parse(read(config))
    check_local_disablers(host, project, current)
    version_string = version(host)
    record = parse(read(receipt))
    if record.get("config") != str(config) or record.get("schema") != 1:
        raise ValueError("No matching installation receipt")
    for event, entries in record["groups"].items():
        for group in entries:
            if current.get("hooks", {}).get(event, []).count(group) != 1:
                raise ValueError(
                    "A registered continuity hook is missing, changed, or duplicated"
                )
    verify_skill({"skill": skill})
    return f"Registration and runtime files match ({host} {version_string}). Trust/enabled state and real host delivery still require /hooks verification."
