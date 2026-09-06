# Codex and Claude Code

[Chinese mirror](platforms.zh-CN.md)

Both packages use the same `SKILL.md`, agent workflow, human guide, and complete prompts. The Codex package adds `agents/openai.yaml` for display metadata. The Claude Code package uses the common skill entry point without adding fork, subagent, model, or permission settings. Neither package installs hooks.

## Placement and invocation

Copy the entire `structured-coding/` folder from the appropriate package to the target location, preserving internal relative paths. Compare existing content first to avoid overwriting local customizations.

| Platform | Project directory | Personal directory | Explicit invocation |
| --- | --- | --- | --- |
| Codex | `.agents/skills/structured-coding/` | `~/.agents/skills/structured-coding/` | `$structured-coding` |
| Claude Code | `.claude/skills/structured-coding/` | `~/.claude/skills/structured-coding/` | `/structured-coding` |

Codex paths and invocation follow the [official OpenAI skills documentation](https://learn.chatgpt.com/docs/build-skills); Claude Code follows its [official skills documentation](https://code.claude.com/docs/en/skills). Verified on 2026-09-05. Environments with customized installation paths should follow their actual discovery rules and avoid duplicate installations.

For a new PR, prepare the complete approved design and filled contract in the planning session, then invoke the skill with those paths in a fresh implementation session. For compact/resume, read the current PR's handoff and continue the same PR.

## Mapping hooks to platforms

This table guides future adapters; it is not a configuration file. Implement and validate event payloads, return values, permission behavior, and tool coverage against the target version.

| Workflow behavior | Candidate Codex event | Candidate Claude Code event |
| --- | --- | --- |
| Freeze check before implementation; authorization check before merge | `PreToolUse` | `PreToolUse` |
| Checks before manual/automatic compact | `PreCompact`, distinguishing `manual` / `auto` | `PreCompact`, distinguishing `manual` / `auto` |
| Recover the current PR on compact/resume | `SessionStart`, matching `compact` / `resume` | `SessionStart`, matching `compact` / `resume` |
| Check handoff and state when execution ends | `Stop` or relevant ending events, adapting loop semantics | `Stop` or relevant ending events, adapting loop semantics |

These mappings come from [OpenAI Hooks](https://learn.chatgpt.com/docs/hooks) and the [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks). Identical event names do not guarantee identical return protocols; do not copy blocking JSON between hosts without checking its meaning.

OpenAI documents tool paths that may bypass hooks, including subsequent input to an existing exec session that does not repeat the original command's pre-tool check. An adapter must inspect actual tool coverage and bypass routes. The presence of `PreToolUse` alone does not establish that every write and merge is guarded. See [OpenAI Hooks: tool coverage](https://learn.chatgpt.com/docs/hooks#tool-coverage).

Both platforms need separate behavior for blocking stale manual compact and allowing automatic compact with recovery. On resume, prioritize current PR identity, document paths, and recovery instructions. If long prompts cannot be injected in full, require complete file reads. A summary retained by the host after compaction is not proof that the complete execution template has been reloaded.

This package sets no global auto-approval, permission bypass, or continuous-execution switch, and does not depend on the `/goal` command mentioned in the historical source. Continuous execution and hook enforcement belong to host integration; task semantics and stop conditions are defined in the skill and behavior contract.
