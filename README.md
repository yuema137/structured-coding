# Structured Coding

[Chinese mirror](README.zh-CN.md)

Agree on what one PR should deliver, let the agent implement and check it, then review the result before merge. Use what that PR taught you to plan the next one.

The agent records progress, discoveries, and validation in the PR design doc as it works. You decide the goal, scope, and changes that need a new agreement. Local implementation details and ordinary bugs can be handled without asking you at every commit.

Start with the [human guide](structured-coding/README.md). It follows one example through planning, implementation, review, and the next PR. It also explains how the agent resumes after compaction and which decisions still need you.

| What you need | Where to look |
| --- | --- |
| Understand the workflow and your part in it | [Human guide](structured-coding/README.md) |
| Load the agent's instructions | [SKILL.md](structured-coding/SKILL.md) |
| Read the detailed agent workflow | [Agent workflow](structured-coding/references/agent-workflow.md) |
| Check the PR design requirements | [PR requirements](structured-coding/prompts/pr-design-requirements.md) |
| Use the complete execution prompt | [Implementation Working Rules](structured-coding/prompts/implementation-working-rules.md) |
| Check test and CI requirements | [TEST / CI / GATE](structured-coding/prompts/test-ci-gate-rules.md) |
| See what future hooks must enforce | [Hook contract](structured-coding/references/hook-contract.md) |
| Check which prompt wording was preserved | [Prompt provenance](structured-coding/references/prompt-provenance.md) |

## Read either language; maintain English first

English is the only authoritative source. Files ending in `.zh-CN.md` mirror the explanations in Chinese and retain English technical terms, including LLM, agent, coding, bug, PR, commit, review, and hook. Change the English explanation first, then update its Chinese mirror in the same change.

The human README and guide follow [DongbeiGPT's explanation method](https://github.com/yuema137/DongbeiGPT/tree/3f722628c4d91711771ddd46cb1d9e69e9ba9541): name the actors and actions, show what changes, walk through a small example, and keep the conditions and costs visible. Chinese also uses its restrained Dongbei conversational rhythm. English uses the same explanatory structure and plain language without dialect. This writing choice does not change the agent instructions.

Specifications stay English-only: `SKILL.md`, PR requirements, execution prompts, test rules, and the hook contract. The original mixed-language document remains an unchanged historical archive. Current requirements come from the maintained specifications. The [language policy](structured-coding/references/language-policy.md) explains how to keep the two languages aligned.

## Install the package for your agent

| Platform | Folder to copy | Zip |
| --- | --- | --- |
| Codex | [dist/codex/structured-coding](dist/codex/structured-coding/SKILL.md) | [Codex skill](dist/structured-coding-codex.zip) |
| Claude Code | [dist/claude-code/structured-coding](dist/claude-code/structured-coding/SKILL.md) | [Claude Code skill](dist/structured-coding-claude-code.zip) |

Copy the whole `structured-coding/` folder into the target project's `.agents/skills/` for Codex or `.claude/skills/` for Claude Code. The files refer to one another, so keep the directory together. If you already have a customized installation, compare it before replacing it. Personal installation paths, invocation examples, and official sources are in [platform notes](structured-coding/references/platforms.md). Providing these packages does not change your personal configuration.

Both packages come from the same maintained folder, `structured-coding/`. The Codex package additionally includes UI metadata. After editing the source and synchronizing its mirrors, run these commands from the repo root:

```sh
python3 scripts/build_packages.py
python3 scripts/build_packages.py --check
```

Edit the maintained source rather than a generated copy: rebuilding replaces the known generated files in `dist/`. The builder refuses unknown files or symlinks and deletes nothing.

The checks compare the original [Structured Coding skill.md](<Structured Coding skill.md>) with its recorded hash, verify complete prompt extraction and the three previously approved PR-rule edits, check mirror fingerprints and local links, and compare both directory packages and zip files with the shared source. A fingerprint identifies the document version; it cannot tell whether a translation is accurate. Passing these checks also does not prove that the workflow has completed a real PR.

## What works now, and what still needs implementation

The skills, human and agent explanations, and complete prompts are ready to use. The hook contract describes future checks before implementation, compaction recovery, and merge.

No executable hooks are implemented or installed. For now, the agent performs those checks by following the skill. A future host integration must implement and verify the hook contract before claiming that it mechanically blocks an action.
