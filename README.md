# Structured Coding

[Chinese mirror](README.zh-CN.md)

A workflow for layered planning, autonomous agent coding, live evidence, and updating the next plan after merge.

Start with the [human workflow guide](structured-coding/README.md). It explains the overall / step / PR hierarchy, where people participate, what agents can handle autonomously, and why fresh sessions and backward updates matter.

| What to read | Entry point |
| --- | --- |
| Principles and human interaction | [Human guide](structured-coding/README.md) |
| Concise agent entry point | [SKILL.md](structured-coding/SKILL.md) |
| Detailed agent workflow | [Agent workflow](structured-coding/references/agent-workflow.md) |
| PR design doc requirements | [PR requirements](structured-coding/prompts/pr-design-requirements.md) |
| Complete execution prompt | [Implementation Working Rules](structured-coding/prompts/implementation-working-rules.md) |
| Complete test and CI rules | [TEST / CI / GATE](structured-coding/prompts/test-ci-gate-rules.md) |
| Hook behavior and acceptance scenarios | [Hook contract](structured-coding/references/hook-contract.md) |
| Source preservation and limited historical changes | [Prompt provenance](structured-coding/references/prompt-provenance.md) |

## Language and authority

English is the only authoritative source for maintained documentation. Workflow explanations have `.zh-CN.md` mirrors; the mirrors retain English technical terms such as LLM, agent, coding, bug, PR, commit, review, and hook. Update English first, then synchronize the corresponding Chinese mirror in the same change.

Specifications remain English-only: `SKILL.md`, PR requirements, execution prompts, test rules, and the hook contract. The original mixed-language source is an unchanged historical archive, not the current specification. See the [language maintenance policy](structured-coding/references/language-policy.md).

## Packages for both platforms

| Platform | Copyable directory | Zip |
| --- | --- | --- |
| Codex | [dist/codex/structured-coding](dist/codex/structured-coding/SKILL.md) | [Codex skill](dist/structured-coding-codex.zip) |
| Claude Code | [dist/claude-code/structured-coding](dist/claude-code/structured-coding/SKILL.md) | [Claude Code skill](dist/structured-coding-claude-code.zip) |

Copy the entire skill folder into the target project's `.agents/skills/` for Codex or `.claude/skills/` for Claude Code. Compare existing content before replacing a customized installation. Personal installation paths, invocation examples, and official sources are in [platform notes](structured-coding/references/platforms.md). This repository provides packages without changing personal configuration.

Both packages are built from the maintained source in `structured-coding/`; the Codex package additionally contains UI metadata. After updating the source and its mirrors, rebuild from this repository's root:

```sh
python3 scripts/build_packages.py
python3 scripts/build_packages.py --check
```

The builder writes only known generated files under `dist/`. It refuses unknown files or symlinks and deletes nothing. Customize the maintained source, since rebuilding replaces generated copies in `dist/`.

The original [Structured Coding skill.md](<Structured Coding skill.md>) remains unchanged. Checks verify complete prompt extraction, the three previously approved PR-rule updates, mirror source fingerprints, local links, and agreement between the shared source, both directory packages, and both zip files. These checks do not establish translation accuracy or prove the workflow has completed a real PR.

## Delivery scope

This repository provides skills for both platforms, human and agent explanations, complete prompts, and the hook behavior contract. Hooks are not implemented or installed. The agent follows the procedural checks in the skill; future host integration must satisfy the hook contract.
