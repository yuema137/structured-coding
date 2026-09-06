# 应用保留的 prompt

[English source](adaptation.md) · 英文是唯一权威源，本页是中文镜像。

本文解释如何将 prompt 应用于不同项目，不替代其中的详细指令。

## 按 scope 和阶段理解规则

- 遵循当前用户指令和已有授权。填写好的 contract 记录授权；带有示例值的模板不会自行产生授权。
- 应用已批准的 PR contract 和 binding parent invariants。更严格的项目限制优先于通用默认值。不能通过修改 child doc 静默放宽 binding 限制。
- Implementation 自主性和 lifecycle 以 working rules 为依据；validation ownership 和成本控制以 TEST / CI / GATE rules 为依据。
- 用 PR requirements 构建可 audit 的 design 和 commit plan。commit 时的检查不要求人回复，记录后继续 execution。
- Source/document audit 后仍存在实质冲突时，指出不兼容的条款，准备具体解决方案，再请求决定。对于已经受批准意图约束的普通细节，不应停下来询问。

Repository/git/process 事实确定实际状态，也能说明文档已经过时，但不能静默重定义预期行为。实际行为与 invariant 冲突时，记录事实，并判断这是 implementation bug，还是需要 operator 作出的 design 决策。

## 有意保留的项目专属措辞

| 原文措辞 | 在其他仓库中的应用 |
| --- | --- |
| `SIDERIUS` | Test prompt 中的历史项目名。将规则关联到当前 `PROJECT / PR`，不要重命名用户项目。 |
| `shuffle`、`file_order`、visited sequence、random seed、step count | 适用于 ordering/default-parity 改动；其他情况标记不适用，不要为满足模板而引入这些选项。 |
| Planner exposure、production-default changes | 相关时保留原文排除范围。有意修改这些内容需要明确纳入已批准 scope，并提供所需证据。 |
| Gate 1 / Gate 2 | 本工作流中分别指真实 LLM 和真实 lifecycle 证据。映射到项目真实 command；claim 不需要该层时记录 `NOT REQUIRED`。 |
| Ruff、Pyright、Pydantic、pytest | Ownership 和 command 的示例。使用仓库实际工具；skill 不要求引入新的语言或工具 dependency。 |
| Scorer、metric、model、training、GPU | 项目具备相关语义时应用。非 ML 项目按需使用确定性和真实 integration 证据。 |
| `before_end_memory.md` | 建议的 handoff 文件名。复用既有文件或选择 PR 专属路径；不要覆盖用户无关笔记。 |
| Final handoff 中的 full-suite result | 运行过则报告 canonical result；未运行则记录 `NOT RUN`、原因和实际选择的 CI 证据。不能仅为填写该字段再跑一次 full suite。 |

## Budget 与 approval 的解释

Working rules 描述了约一小时的自主运行总范围。更具体的 test rules 默认将**每次 Gate run** 控制在约十分钟内，除非 frozen contract 允许更长。填写 contract 时记录单次与总限制，以及相关 CPU/GPU/API/费用约束。失败和 retry 也计入总范围。

十分钟默认值不意味着可以伪造真实 lifecycle。缩小真实 workload，同时保持 acceptance claim 可观察。如果授权范围内无法做到，为 operator 准备最小有意义的运行方案及成本估算。

Real-training approval 可以在 execution 前通过 implementation contract 给出。每次已授权且有界的运行前无需重复请求。项目没有该授权时，不能仅凭继承示例模板措辞而获得授权。

## Freeze 与持续更新

`DESIGN FROZEN` 固定已商定的 objective、scope、invariants、acceptance 和重要约束。Checklist、audit 发现、实现事实、test evidence 和有界 design 修正仍可写入。记录改变的假设及其原因，不要将其伪装成原计划。

有界发现可以改变达成已批准结果的路径，不能改变结果本身或 binding constraint。实质修订需要将相关 design 重新交给 review；保留已完成工作，在执行修订后的 scope 前记录新的 approval。

## PR review、CI 与 merge

Operator 可以在 CI 运行时 review diff。这种并行不表示 agent 已达到 terminal condition，也不表示已获 merge 授权。`READY FOR OPERATOR REVIEW` 要求完成约定的 implementation/review/validation，并取得准确最终 head 的 canonical CI。

已批准 execution contract 包含时，可以自主创建或更新 PR、修复 CI。仅 planning 或 local-only 的请求不会自动授权 branch 发布。用户明确选择 local-only endpoint 时，应在 execution 前记录，并报告本地完成，不要称为已通过远程验证的 PR。

已有必需 CI checks 仍然有效。Prompt 中 selective-CI 和 stacked-PR 的指引，不授权在无关 feature PR 中禁用检查或重建 CI 基础设施。

## Skill 指令与 runtime enforcement

本版本提供指令与 hook 行为约定，不安装平台 hook，也不修改权限。当前按流程执行 freeze、恢复和 merge 检查；后续集成可以机械执行同样的决策。不要仅为了消除所有可能的中断而请求大范围权限变更。
