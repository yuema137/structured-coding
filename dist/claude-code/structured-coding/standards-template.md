# Project standards

Copy this file to `.structured-coding/standards.md` in your project and edit the
block at the bottom. Everything outside that block is for you, not the machine.

This file is optional. A project without one behaves exactly as it does today,
using the defaults shown below. Run
`python3 <skill>/scripts/standards.py inspect --project .` at any time to see
what is actually in effect and where each value came from.

Declare only what is true for your whole codebase. Anything specific to one PR
belongs in the conversation where you plan that PR, so that this file stays a
stable repository asset instead of competing with the frozen PR design.

## The two layers

| File | Role | Usually |
| --- | --- | --- |
| `.structured-coding/standards.md` | the team's standard | committed |
| `.structured-coding/standards.local.md` | your personal additions | not committed |

The personal file may **add and tighten only**. It can add a tool, enable one the
team left off, widen a scope, add a review convention, or ask for checks more
often. It cannot disable a team check, narrow a scope, drop a convention, or turn
a trigger off; attempting that is refused, naming the field, rather than quietly
ignored. If you genuinely need to skip a team check, that belongs in the PR as a
recorded deviation, where a reviewer can see it.

Trust is decided by whether Git tracks the file, never by its name. A tracked
file can be edited by any contributor in a pull request; an untracked one can
only have been written on your own machine.

## What you can set

### `review` — conventions a person or an LLM judges

`trigger` decides when the conventions are brought to the agent's attention.

| Value | Meaning |
| --- | --- |
| `off` | never |
| `pr` | when the PR reaches review readiness (**default**) |
| `commit` | at every semantic commit as well |

`conventions` is a list of plain sentences. Write the rule, not the rationale.
Good entries read like `Public functions carry docstrings` or
`Pydantic models validate at the boundary, not deep inside call chains`.

This is where a rule belongs when no command can decide it. Pydantic is a good
example: it is a validation library, not a checker you can run, so a requirement
about how your project uses it is a review convention rather than a tool.

### `checks` — commands with a pass or fail result

`trigger` uses the same three values and defaults to `pr`.

`tools` is a list. Each entry takes:

| Key | Values | Default |
| --- | --- | --- |
| `name` | short lowercase tool name | required |
| `enabled` | `true` / `false` | `true` for a tool you add |
| `scope` | `changed` / `repository` | `changed` for a tool you add |

`scope` is per tool on purpose, because the right answer differs by tool.
`changed` means only the files this PR touched. That is right for `ruff` and
`pyright`, which read the code you changed. It is wrong for `pytest`: the tests
that cover a change usually live in files the change did not touch, so a
changed-file selection silently skips them.

### Which tools need approval

Tools are grouped by whether they execute your project's code, not by whether the
name is familiar:

| Tool | Group | Why |
| --- | --- | --- |
| `ruff`, `pyright` | allowlisted | analyze the code without running it |
| `pytest` | approval required | imports `conftest.py`, which is arbitrary code |
| `mypy` | approval required | imports the plugins its configuration names |
| anything else | approval required | unrecognized |

A tool needing approval is not forbidden; it needs one deliberate decision
before anything runs it automatically. Nothing in this release runs any tool.

## The defaults

These apply when you have no file at all, and they are what the block below
declares. `pytest` is listed and switched off so that turning it on is a choice
you make rather than one you inherit.

```json
{
  "schema": 1,
  "review": {
    "trigger": "pr",
    "conventions": []
  },
  "checks": {
    "trigger": "pr",
    "tools": [
      {"name": "ruff", "enabled": true, "scope": "changed"},
      {"name": "pyright", "enabled": true, "scope": "changed"},
      {"name": "pytest", "enabled": false, "scope": "repository"}
    ]
  }
}
```

## What this does not do yet

Nothing here runs a tool, blocks a commit, or registers a hook. This release
reads the file and reports the result. Automatic execution, and the approval that
gates a tool outside the allowlist, are separate later work. Do not read a clean
`inspect` report as evidence that any check has run.
