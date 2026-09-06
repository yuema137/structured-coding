# Structured Coding

[English source](README.md) · 英文是唯一权威源，本页是中文镜像。

一套逐层 planning、自主 agent coding、实时记录证据、merge 后更新下一步计划的工作流。

先读 [human workflow guide](structured-coding/README.zh-CN.md)。它解释 overall / step / PR 的层次、人在什么时候参与、哪些事情 agent 可以自主处理，以及 fresh session 和 backward update 的作用。

| 想看什么 | 入口 |
| --- | --- |
| 原理与人的交互方式 | [Human guide](structured-coding/README.zh-CN.md) |
| Agent 的简明入口 | [SKILL.md](structured-coding/SKILL.md) |
| 详细的 agent workflow | [Agent workflow](structured-coding/references/agent-workflow.zh-CN.md) |
| PR design doc 要求 | [PR requirements](structured-coding/prompts/pr-design-requirements.md) |
| 完整 execution prompt | [Implementation Working Rules](structured-coding/prompts/implementation-working-rules.md) |
| 完整 test 与 CI 规则 | [TEST / CI / GATE](structured-coding/prompts/test-ci-gate-rules.md) |
| Hook 行为与验收场景 | [Hook contract](structured-coding/references/hook-contract.md) |
| 原文保留与此前的有限改动 | [Prompt provenance](structured-coding/references/prompt-provenance.zh-CN.md) |

## 语言与权威来源

维护中的文档以英文为唯一权威源。工作流说明提供 `.zh-CN.md` 镜像；中文镜像保留 LLM、agent、coding、bug、PR、commit、review、hook 等英文专业术语。先改英文，再在同一项改动中同步对应的中文镜像。

specification 仅维护英文，包括 `SKILL.md`、PR requirements、execution prompt、test rules 和 hook contract。原始混合语言文档作为历史材料原样保留，不是现行 specification。详见 [language maintenance policy](structured-coding/references/language-policy.md)。

## 两个平台的包

| 平台 | 可复制目录 | Zip |
| --- | --- | --- |
| Codex | [dist/codex/structured-coding](dist/codex/structured-coding/SKILL.md) | [Codex skill](dist/structured-coding-codex.zip) |
| Claude Code | [dist/claude-code/structured-coding](dist/claude-code/structured-coding/SKILL.md) | [Claude Code skill](dist/structured-coding-claude-code.zip) |

将整个 skill 文件夹复制到目标项目的 `.agents/skills/`（Codex）或 `.claude/skills/`（Claude Code）。替换已有定制安装前先比较内容。个人安装目录、调用示例和官方依据见 [platform notes](structured-coding/references/platforms.zh-CN.md)。本仓库提供包，不修改个人配置。

两份包均从 `structured-coding/` 中的维护源生成；Codex 包额外包含 UI metadata。更新维护源和镜像后，从本仓库根目录重新构建：

```sh
python3 scripts/build_packages.py
python3 scripts/build_packages.py --check
```

构建脚本只写入 `dist/` 中已知的生成文件，遇到未知文件或 symlink 会拒绝，不删除文件。请修改维护源，因为重新构建会替换 `dist/` 中的生成副本。

原始 [Structured Coding skill.md](<Structured Coding skill.md>) 保持不变。检查覆盖完整 prompt 提取、此前批准的三条 PR 规则更新、镜像对应的英文版本指纹、内部链接，以及共享源、两份目录包和两份 zip 的一致性。这些检查不能证明翻译准确，也不代表工作流已经完成过真实 PR。

## 交付范围

本仓库提供两个平台的 skill、human 和 agent 说明、完整 prompt，以及 hook 行为约定。hook 尚未实现或安装。agent 当前按 skill 执行流程检查；后续平台集成必须满足 hook contract。
