#!/usr/bin/env python3
"""Read a project's declared coding standards. Runs nothing and enforces nothing.

See references/standards.md for the contract, the two layers, and the limits.
Uses only Python 3.9+ and Git; never invokes an LLM, a tool, or a remote API.
"""

import json
import re
import sys

# Installed helpers must not create files in the published skill tree.
sys.dont_write_bytecode = True

MAX_INPUT = 256 * 1024
SCHEMA = 1
TRIGGERS = ("off", "pr", "commit")
SCOPES = ("changed", "repository")
NAME = re.compile(r"\A[a-z][a-z0-9_-]{0,31}\Z")
OPENING = re.compile(r"\A\s{0,3}(`{3,}|~{3,})[ \t]*json[ \t]*\Z")
FENCE = re.compile(r"\A\s{0,3}(`{3,}|~{3,})(.*)\Z")


class Invalid(ValueError):
    """Names the file and the offending field, never the file's contents."""

    def __init__(self, path, field, problem):
        super().__init__(f"{path}: {field}: {problem}")


def blocks(text):
    """Every top-level ```json block. A fence inside another fence is content."""
    found, capturing, marker, lines = [], False, None, []
    for line in text.splitlines():
        match = FENCE.match(line)
        if marker is None:
            if match and OPENING.match(line):
                marker, capturing, lines = match.group(1), True, []
            elif match:
                marker, capturing = match.group(1), False
            continue
        closing, tail = match.groups() if match else ("", "x")
        if closing[:1] == marker[0] and len(closing) >= len(marker) and not tail.strip():
            if capturing:
                found.append("\n".join(lines))
            marker, capturing = None, False
        elif capturing:
            lines.append(line)
    return found


def read(path):
    """The declared configuration in one file, or a precise refusal."""
    if path.is_symlink():
        raise Invalid(path, "file", "symlinked configuration files are not read")
    if not path.is_file():
        raise Invalid(path, "file", "not a regular file")
    if path.stat().st_size > MAX_INPUT:
        raise Invalid(path, "file", f"larger than {MAX_INPUT} bytes")
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise Invalid(path, "file", "not valid UTF-8") from None
    found = blocks(text)
    if len(found) != 1:
        raise Invalid(
            path, "json block", f"expected exactly one ```json block, found {len(found)}"
        )
    try:
        value = json.loads(found[0])
    except json.JSONDecodeError:
        raise Invalid(path, "json block", "is not valid JSON") from None
    return validate(path, value)


def section(path, value, name, extra):
    if not isinstance(value, dict):
        raise Invalid(path, name, "must be an object")
    unknown = set(value) - ({"trigger"} | set(extra))
    if unknown:
        raise Invalid(path, name, f"unknown keys: {', '.join(sorted(unknown))}")
    if "trigger" in value and value["trigger"] not in TRIGGERS:
        raise Invalid(path, f"{name}.trigger", f"must be one of {', '.join(TRIGGERS)}")
    return value


def conventions(path, value):
    if not isinstance(value, list):
        raise Invalid(path, "review.conventions", "must be a list")
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise Invalid(
                path, f"review.conventions[{index}]", "must be a non-empty string"
            )
    return list(value)


def tools(path, value):
    if not isinstance(value, list):
        raise Invalid(path, "checks.tools", "must be a list")
    seen = set()
    for index, item in enumerate(value):
        field = f"checks.tools[{index}]"
        if not isinstance(item, dict):
            raise Invalid(path, field, "must be an object")
        unknown = set(item) - {"name", "enabled", "scope"}
        if unknown:
            raise Invalid(path, field, f"unknown keys: {', '.join(sorted(unknown))}")
        name = item.get("name")
        if not isinstance(name, str) or not NAME.match(name):
            raise Invalid(path, f"{field}.name", "must be a short lowercase tool name")
        if name in seen:
            raise Invalid(path, f"{field}.name", f"{name} is declared more than once")
        seen.add(name)
        if "enabled" in item and not isinstance(item["enabled"], bool):
            raise Invalid(path, f"{field}.enabled", "must be true or false")
        if "scope" in item and item["scope"] not in SCOPES:
            raise Invalid(path, f"{field}.scope", f"must be one of {', '.join(SCOPES)}")
    return [dict(item) for item in value]


def validate(path, value):
    if not isinstance(value, dict):
        raise Invalid(path, "json block", "must be an object")
    if value.get("schema") != SCHEMA:
        raise Invalid(path, "schema", f"must be {SCHEMA}")
    unknown = set(value) - {"schema", "review", "checks"}
    if unknown:
        raise Invalid(path, "json block", f"unknown keys: {', '.join(sorted(unknown))}")
    declared = {"schema": SCHEMA}
    if "review" in value:
        review = section(path, value["review"], "review", ("conventions",))
        declared["review"] = dict(review)
        if "conventions" in review:
            declared["review"]["conventions"] = conventions(path, review["conventions"])
    if "checks" in value:
        checks = section(path, value["checks"], "checks", ("tools",))
        declared["checks"] = dict(checks)
        if "tools" in checks:
            declared["checks"]["tools"] = tools(path, checks["tools"])
    return declared


# Ranked from permissive to strict. An overlay may raise a rank, never lower it.
TRIGGER_RANK = {name: rank for rank, name in enumerate(TRIGGERS)}
SCOPE_RANK = {name: rank for rank, name in enumerate(SCOPES)}

DEFAULTS = {
    "schema": SCHEMA,
    "review": {"trigger": "pr", "conventions": []},
    "checks": {
        "trigger": "pr",
        "tools": [
            {"name": "ruff", "enabled": True, "scope": "changed"},
            {"name": "pyright", "enabled": True, "scope": "changed"},
            {"name": "pytest", "enabled": False, "scope": "repository"},
        ],
    },
}


def defaults():
    """A fresh copy, so a caller can never mutate the shipped values."""
    return json.loads(json.dumps(DEFAULTS))


def trigger(effective, origins, declared, name, layer, path, restrict):
    if "trigger" not in declared:
        return
    value, current = declared["trigger"], effective[name]["trigger"]
    if restrict and TRIGGER_RANK[value] < TRIGGER_RANK[current]:
        raise Invalid(
            path,
            f"{name}.trigger",
            f"a personal file may not relax {current} to {value}",
        )
    effective[name]["trigger"] = value
    origins[f"{name}.trigger"] = layer


def merge_conventions(effective, origins, declared, layer):
    """Overlay entries are additions, so removal is impossible by construction."""
    if "conventions" not in declared:
        return
    existing = effective["review"]["conventions"]
    for item in declared["conventions"]:
        if item not in existing:
            existing.append(item)
            origins[f"review.conventions[{existing.index(item)}]"] = layer


def merge_tools(effective, origins, declared, layer, path, restrict):
    if "tools" not in declared:
        return
    known = {tool["name"]: tool for tool in effective["checks"]["tools"]}
    for item in declared["tools"]:
        name = item["name"]
        current = known.get(name)
        if current is None:
            tool = {"name": name, "enabled": True, "scope": "changed", **item}
            effective["checks"]["tools"].append(tool)
            known[name] = tool
            origins[f"checks.tools.{name}"] = layer
            continue
        field = f"checks.tools.{name}"
        if "enabled" in item:
            if restrict and current["enabled"] and not item["enabled"]:
                raise Invalid(
                    path,
                    f"{field}.enabled",
                    "a personal file may not disable a shared check",
                )
            if current["enabled"] != item["enabled"]:
                current["enabled"] = item["enabled"]
                origins[f"{field}.enabled"] = layer
        if "scope" in item:
            if restrict and SCOPE_RANK[item["scope"]] < SCOPE_RANK[current["scope"]]:
                raise Invalid(
                    path,
                    f"{field}.scope",
                    f"a personal file may not narrow {current['scope']} to {item['scope']}",
                )
            if current["scope"] != item["scope"]:
                current["scope"] = item["scope"]
                origins[f"{field}.scope"] = layer


def apply_layer(effective, origins, layer, path, declared, restrict):
    for name in ("review", "checks"):
        if name not in declared:
            continue
        trigger(effective, origins, declared[name], name, layer, path, restrict)
    if "review" in declared:
        merge_conventions(effective, origins, declared["review"], layer)
    if "checks" in declared:
        merge_tools(effective, origins, declared["checks"], layer, path, restrict)


def resolve(base=None, overlay=None):
    """Defaults, then the shared file, then the personal one which may only tighten."""
    effective = defaults()
    origins = {
        "review.trigger": "default",
        "checks.trigger": "default",
        **{f"checks.tools.{tool['name']}": "default" for tool in effective["checks"]["tools"]},
    }
    for layer, source, restrict in (("base", base, False), ("overlay", overlay, True)):
        if source is not None:
            path, declared = source
            apply_layer(effective, origins, layer, path, declared, restrict)
    return effective, origins
