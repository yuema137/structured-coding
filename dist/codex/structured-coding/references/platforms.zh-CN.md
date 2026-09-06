# Codex 与 Claude Code

[English source](platforms.md) · 英文是唯一权威源，本页是中文镜像。

两份包使用同一份 `SKILL.md`、agent workflow、human guide 和完整 prompt。Codex 包另带 `agents/openai.yaml` 展示信息。Claude Code 包使用通用 skill 入口，不添加 fork、子 agent、模型或权限设置。两边均未安装 hook。

## 放置与调用

把对应包中的整个 `structured-coding/` 文件夹复制到目标位置，保留内部相对路径。目标已存在时，先比较内容，避免覆盖已有定制。

| 平台 | 项目级目录 | 个人级目录 | 显式调用 |
| --- | --- | --- | --- |
| Codex | `.agents/skills/structured-coding/` | `~/.agents/skills/structured-coding/` | `$structured-coding` |
| Claude Code | `.claude/skills/structured-coding/` | `~/.claude/skills/structured-coding/` | `/structured-coding` |

Codex 的目录和调用方式依据 [OpenAI 官方 skills 文档](https://learn.chatgpt.com/docs/build-skills)；Claude Code 依据 [官方 skills 文档](https://code.claude.com/docs/en/skills)。核对日期：2026-09-05。已有定制安装目录的环境应遵循其实际发现规则，避免同时安装重复副本。

开始新 PR 时，先在 planning session 准备完整、已批准的 design 与填好的 contract，再在新的 implementation session 调用 skill 并指向这些文件。compact/resume 则读取当前 PR 的 handoff，继续同一个 PR。

## Hook 的平台映射

下表是后续适配依据，不是配置文件。事件的 payload、返回值、权限策略和工具覆盖必须按目标版本实现并验证。

| 工作流行为 | Codex 候选事件 | Claude Code 候选事件 |
| --- | --- | --- |
| 实现前的 freeze 检查、merge 前的授权检查 | `PreToolUse` | `PreToolUse` |
| 手动/自动 compact 前检查 | `PreCompact`，区分 `manual` / `auto` | `PreCompact`，区分 `manual` / `auto` |
| compact/resume 恢复当前 PR | `SessionStart`，匹配 `compact` / `resume` | `SessionStart`，匹配 `compact` / `resume` |
| 结束时核对 handoff 与状态 | `Stop` 等结束事件，需适配循环语义 | `Stop` 等结束事件，需适配循环语义 |

事件映射来自 [OpenAI Hooks 文档](https://learn.chatgpt.com/docs/hooks)和 [Claude Code Hooks reference](https://code.claude.com/docs/en/hooks)。两边事件同名不意味着返回协议完全相同；尤其不能直接复制一边的阻断 JSON 到另一边。

Codex 官方文档说明部分工具路径可能不经过 hook，持续 exec 会话的后续输入也不会重新触发同一次命令的前置检查。因此后续实现必须核查真正可用的工具路径与绕行方式，不能只凭存在 `PreToolUse` 就宣称所有写入和 merge 已被拦截。[OpenAI Hooks：工具覆盖](https://learn.chatgpt.com/docs/hooks#tool-coverage)

两个平台都需要分别实现手动 compact 的阻断和自动 compact 的放行恢复。恢复时优先注入当前 PR 身份、文档路径和恢复要求；长模板若无法完整注入，要求 agent 从文件完整读取。不要把 compact 后平台自动保留的摘要当成已加载完整 execution 模板的保证。

本包没有设置全局自动批准、绕过权限或持续执行开关，也不依赖原文提到的某个 `/goal` 命令。持续执行与 hook enforcement 是宿主集成问题；本次交付的任务语义与停止条件已在 skill 和行为约定中完整定义。
