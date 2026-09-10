# Project standards configuration

Status: **RUNS ONLY WHEN INVOKED.** This release reads the configuration and,
on the `run` command, executes the declared checks and classifies each result.
It registers no hook, so nothing happens automatically, and it blocks no commit
and no merge. Automatic triggering is later work; the target behaviour for a hook
remains in the [hook contract](hook-contract.md).

A project uses this to state, once, what is true of its whole codebase, so the
operator does not restate it in every planning conversation. Requirements
specific to one PR stay in that PR's conversation and its frozen design; putting
them here would create a second authority over the same decision.

## Files

| Path, relative to the Git worktree root | Layer |
| --- | --- |
| `.structured-coding/standards.md` | base |
| `.structured-coding/standards.local.md` | overlay |

Copy [the template](../standards-template.md) to the base path and edit its
single fenced `json` block. The surrounding prose is never read, which is the
point: it carries the options, the alternatives and the reasons that JSON cannot.
Exactly one top-level `json` block is read. A block nested inside another fence
is prose. Zero blocks, several, or unparsable content is refused, naming the file.

Both files are optional. With neither present the shipped defaults apply and
behaviour is unchanged.

## Two determinations, decided separately

**Layer comes from the filename.** The base states the project's standard. The
overlay may add and tighten only.

**Trust comes from `git ls-files`.** A tracked file is shared: any contributor can
change it in a pull request, so a tool it declares outside the allowlist needs
approval. An untracked file is personal: it is absent from a fresh clone and can
only have been written by the machine's owner, so authoring it is the approval.

The two are independent, which removes the special cases. A tracked overlay is an
overlay that happens to be shared. An untracked base is the base and happens to
be personal. Filename must not decide trust, because `.gitignore` does not apply
to a file Git already tracks, so a repository could otherwise commit a file under
the personal name and have it treated as locally authored.

## Resolution

Defaults, then base, then overlay. The base may relax the shipped defaults: those
defaults are a suggestion and the project's standard is the authority. Only the
overlay is restricted.

```text
trigger:  off  <  pr  <  commit
scope:    changed  <  repository
```

The overlay may raise a rank, enable a disabled tool, add a tool, and add a
convention. It may not lower a rank, disable a tool, or narrow a scope. Overlay
conventions are additions, so removing one has no representation at all.

A relaxing overlay is **refused, naming the field**. Ignoring it would leave a
developer believing a local skip took effect. Applying it would let one machine
opt out of the team's standard while its report still read as compliant. A
genuine local skip belongs in the PR as a recorded deviation. This is the same
rule the workflow already states for documents: a child may not silently relax a
binding restriction.

## Tool classification

Grouped by whether the tool executes project code, not by whether the name is
recognized. `ruff` and `pyright` analyze without running anything. `pytest`
imports `conftest.py` by design and `mypy` imports configured plugins, so both are
recognized and still require approval. Anything else is unrecognized and also
requires approval. Recognition is not trust.

## Commands

```sh
python3 <installed skill>/scripts/standards.py inspect --project .
python3 <installed skill>/scripts/standards.py run     --project . --base main
python3 <installed skill>/scripts/standards.py approve --project .
```

`inspect` prints the files found with their trust, the effective values, the
layer every value came from, each tool's approval verdict, and a note. It runs
nothing. A refusal exits non-zero with an empty stdout, so a failure cannot be
mistaken for a defaults report.

`run` adds the result of every enabled check. A base is required while any
enabled check uses changed-file scope, and there is no fallback to a guessed
default branch: guessing which branch a project treats as its base is how a check
silently examines the wrong range.

The base comes from `--base`, or from the session binding when `--host` and
`--session` identify one that recorded it. An explicit `--base` wins, because a
person naming a revision is more specific than a record made when the PR was
bound. With neither, a changed-scope check reports that it was not run.

## Outcomes

| Outcome | Meaning |
| --- | --- |
| `PASS` | the tool ran and reported nothing |
| `FAIL` | the tool ran and reported findings |
| `INCONCLUSIVE` | it could not run or could not finish: absent, timed out, killed, or exited in its own error mode |
| `NOT RUN` | disabled, no files in scope, no command declared, or approval missing |

An absent tool is `INCONCLUSIVE`, never `PASS`: nothing was examined, so nothing
was established. An empty changed-file selection is `NOT RUN` for the same
reason.

Exit codes are mapped per tool, because tools disagree. `ruff check` returns 2
when it terminates abnormally; `pyright` returns 2 for a fatal error, 3 for a
config file it could not read and 4 for illegal parameters. Those mean the tool
could not run. A command the project supplied has no such map, so a non-zero exit
is reported as `FAIL` and the report says its exit codes are unmapped.

Runs are bounded: a per-tool timeout, a total budget, and captured output
truncated with the truncation marked.

## Commands this skill does not ship

`ruff` and `pyright` run with argv this skill supplies, and a configuration
declaring `command` for them is refused: those names mean that argv, and letting
a project redefine them would make the allowlist meaningless.

Any other tool must supply `command` as argv words, which requires schema 2, and
must be approved before it runs:

```sh
python3 <installed skill>/scripts/standards.py approve --project .
```

`approve` prints every command it authorizes and records the approval under the
Git directory, outside the working tree, so a pull request cannot carry approval
for the command it introduces. The record is bound to those commands alone:
changing one revokes it, while an unrelated edit to the configuration does not,
because a prompt that appears after harmless changes is one people learn to
accept without reading. Until an approval matches, those tools are `NOT RUN` and
nothing is executed.

**A disclosed limit:** `approve` is an operator command, and nothing in this
skill prevents an agent from running it, exactly as nothing prevents an agent
from running the installer. It records a decision; it does not enforce who made
it.

## Limits

Stdlib and Git only; Python 3.9 or newer. A declared command is argv and is never
passed to a shell. The configuration itself is read as data and never executed. A refusal names the file and the field and never carries the
file's contents. Symlinked, non-regular, oversized and non-UTF-8 configuration
files are refused rather than parsed. Reading a file proves nothing about whether
the agent followed it.
