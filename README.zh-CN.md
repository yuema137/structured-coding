# Structured Coding

[English source](README.md) · 英文是唯一权威源，本页是中文镜像。

先商定一个 PR 要交付什么，让 agent 自己实现和检查，再由你 review、决定是否 merge。这一轮查明白的事，接着用来改下一轮计划。

Agent 边做边把进度、新发现和 validation 记进 PR design doc。你决定 goal、scope，以及哪些变化需要重新商量。局部实现细节和普通 bug，它可以自己处理，不用每个 commit 都回来问你。

想先捋明白怎么配合，就看 [human guide](structured-coding/README.zh-CN.md)。里面拿一个例子，从 planning 一直走到 implementation、review 和下一个 PR，也讲 compact 以后 agent 怎么续上、哪些决定还得找你。

| 你想看什么 | 到哪儿看 |
| --- | --- |
| 理解工作流，以及你在其中做什么 | [Human guide](structured-coding/README.zh-CN.md) |
| 加载给 agent 的指令 | [SKILL.md](structured-coding/SKILL.md) |
| 阅读详细 agent workflow | [Agent workflow](structured-coding/references/agent-workflow.zh-CN.md) |
| 核对 PR design 要求 | [PR requirements](structured-coding/prompts/pr-design-requirements.md) |
| 使用完整 execution prompt | [Implementation Working Rules](structured-coding/prompts/implementation-working-rules.md) |
| 核对 test 和 CI 要求 | [TEST / CI / GATE](structured-coding/prompts/test-ci-gate-rules.md) |
| 看未来的 hook 必须执行哪些检查 | [Hook contract](structured-coding/references/hook-contract.md) |
| 核对哪些 prompt 措辞保留了原文 | [Prompt provenance](structured-coding/references/prompt-provenance.zh-CN.md) |

## 中英文都能看，维护时先改英文

英文是唯一权威源。以 `.zh-CN.md` 结尾的文件是说明的中文镜像，LLM、agent、coding、bug、PR、commit、review、hook 等专业术语保留英文。改动时先改英文，再在同一项改动里同步中文镜像。

给人看的 README 和 guide 按 [DongbeiGPT 的讲法](https://github.com/yuema137/DongbeiGPT/tree/3f722628c4d91711771ddd46cb1d9e69e9ba9541) 来写：谁干了什么先说清楚，原来怎么走、现在改哪一步，拿一个小例子顺着走完，条件和成本也别漏。中文再加一点克制的东北口语节奏；英文保留同样的解释顺序和大白话，不加方言。这种写法调整不改 agent 指令。

Specification 只保留英文，包括 `SKILL.md`、PR requirements、execution prompt、test rules 和 hook contract。原始混合语言文档原样留作历史材料，当前要求看维护中的 specification。两种语言怎么同步，见 [language policy](structured-coding/references/language-policy.md)。

## 给你的 agent 装上对应的包

| 平台 | 要复制的文件夹 | Zip |
| --- | --- | --- |
| Codex | [dist/codex/structured-coding](dist/codex/structured-coding/SKILL.md) | [Codex skill](dist/structured-coding-codex.zip) |
| Claude Code | [dist/claude-code/structured-coding](dist/claude-code/structured-coding/SKILL.md) | [Claude Code skill](dist/structured-coding-claude-code.zip) |

把整个 `structured-coding/` 文件夹复制到目标项目：Codex 放进 `.agents/skills/`，Claude Code 放进 `.claude/skills/`。里面的文件会互相引用，得一起带过去。已经装过、还做过自己的定制，就先比较再替换。个人安装路径、调用示例和官方依据在 [platform notes](structured-coding/references/platforms.zh-CN.md)。提供这些包不会改变你的个人配置。

两份包都从 `structured-coding/` 这一份维护源生成，Codex 包另外带 UI metadata。改好维护源并同步中文镜像后，在 repo 根目录运行：

```sh
python3 scripts/build_packages.py
python3 scripts/build_packages.py --check
```

改动落在维护源里就行，别只改生成副本。重新 build 会替换 `dist/` 中已知的生成文件。遇到未知文件或 symlink，构建脚本会拒绝，不会删除文件。

检查会核对原始 [Structured Coding skill.md](<Structured Coding skill.md>) 的 hash、完整 prompt 提取、此前批准的三条 PR 规则改动、镜像 fingerprint 和内部链接，再比较两份目录包、zip 与维护源是否一致。Fingerprint 能说明对应的是哪个文档版本，不能替你判断翻译准不准。检查通过，也不等于这套工作流已经在真实 PR 上跑完一轮。

## 哪些现在能用，哪些还得实现

Skill、给人和 agent 的说明，以及完整 prompt，现在都可以用。hook contract 写的是将来在 implementation、compaction 恢复和 merge 前要做的检查。

可运行的 hook 还没有实现或安装。目前是 agent 按 skill 做这些检查。以后接入平台时，得按 hook contract 实现并验证，才能说某个动作已经会被机械拦截。
