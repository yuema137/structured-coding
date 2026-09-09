<!-- Generated file. Source: docs/content.zh-CN.json in the structured-coding repository, built by scripts/build_human_docs.py. Direct edits here are overwritten by the next build. -->

[English source](TUTORIAL.md) · [返回 README](README.zh-CN.md)

# 第一次使用，照着走完一个功能

下面按实际操作顺序走一遍。假设你的应用会读取文件，你想加一个可选的字母排序模式，同时保留当前默认行为。示例消息里的路径和 PR 编号都需要替换，不是这个 toolkit 已经替你创建好的文件。先让 planning agent 写出真实文档，再把真实路径填进 execution 消息。下面的英文入口消息在中英文页面里完全相同，也不能代替原始长 prompt。

## 1. 开 planning 会话，先说清楚你要什么结果。

在选好的 agent host 里打开目标项目。Codex 用 $structured-coding，Claude Code 用 /structured-coding 调用 skill，然后发送下面的 planning 请求，把需求换成你自己的。

拿这个例子来说，你要说明：输入是 [c, a, b]，启用字母排序后应按 [a, b, c] 读取；不开这个选项，旧行为必须不变。也要说清楚这次不做什么，比如这个 PR 先不改 resume 机制。Agent 应该先检查 repo，把未确定的产品问题问清楚，再提出整体方向。你说的是做计划，它就不能直接开始 implementation。

```text
Use the structured-coding workflow for this feature. First agree with me on
requirements, module-level direction, and overall step boundaries; then detail
the current step. Work on planning for now.
Requirements: ...
```

**进入下一步前，确认这件事**

进入下一步前，你应该能用自己的话讲清楚目标和主要步骤。哪里看不懂，就让 agent 重写到你能 review 为止，不需要你替它写 design doc。

## 2. 让同一个 planning agent 细化下一个 PR。

Overall plan 讲整个功能和主要步骤，step plan 讲几个 PR 怎么配合，当前 PR design 才深入到具体修改。Agent 先读真实 code 和调用方，再写要改的文件、函数、commit 和检查。后面的 PR 可以先粗一些，因为这次 implementation 可能会带来新发现。 具体格式由 PR requirements 管；你让 agent 按完整 specification 准备，不需要自己重新拼一份模板。

字母排序这个 PR，验收要观察 reader 是否真的按 [a, b, c] 读取，不能只检查配置里存进了一个值。你可以要求：如果某个调用方漏传了选项，这个检查必须失败。每个 commit 的 implementation、validation 和逻辑 review 要分别记录。一个 step 如果只需要一个 PR，就把 step doc 直接展开，不用再维护一份重复计划。

```text
Read the overall and step documents, audit the current code, and prepare the
PR 01a design doc and filled execution contract. Follow the original PR
requirements for the commit checklist. Separate implementation, validation,
and review, and prepare the design for my approval.
```

**进入下一步前，确认这件事**

Agent 应该交给你真实的 PR design 路径和填好的 execution contract。一起确定这些记录放在哪儿、哪些需要进 Git。私下的 planning 笔记和原始 log，不会因为产生了就自动成为对外发布的内容。

## 3. Review 这份约定，明确批准当前 PR。

你要看清楚：这次改什么、保留什么、不做什么，以及观察到什么结果才算完成。Execution contract 还得写明，agent 能不能 commit、push branch、创建或更新 PR、修复 CI，以及应该停在哪儿。这些是不同的授权。只让它在本地实现，不代表允许它发布到远程。

Design 符合你的意思后，明确批准这份具体的 design 和 contract。Agent 再记录 DESIGN FROZEN 和批准依据。Freeze 固定的是已约定的 scope、invariants 和验收要求，不是把整份文件锁住。新发现、进度和证据仍然要接着写。批准 implementation，也不等于批准 merge。

已授权的验证，现有 subscription 能覆盖，就不用再问一次 provider、账户或费用。按量计费 API 和其他额外收费，需要适用的费用授权。已有时间限制、配额和明确约束仍然有效；agent 不能为了绕过限制就换账户或启用付费 fallback。任务如果另有真实 training 的授权要求，也仍然要遵守。

**进入下一步前，确认这件事**

让 agent 准备一份 kickoff，写清已批准的 design、填好的 contract、implementation base、下一步和停止条件。不要把还留着占位路径的模板直接粘过去，就当 execution 已经准备好了。

## 4. 为这个 PR 新开一个 implementation 会话。

在同一个目标项目里，真正新开一个会话，不是给 planning 会话改个名字。重新调用 skill，把带真实路径的 kickoff 发过去。新的 agent 不需要整段 planning 聊天记录，但需要已经保存的约定，以及能确认当前状态的源文件。

修改前，agent 必须读已批准的 design、填好的 contract，以及完整的 execution 和 test rules。它还要检查 branch、HEAD、已有改动、前置 PR 是否 merge，以及相关 job 是否仍在运行。无关改动要保留。如果你明确启用了某个 preset，它还要读对应说明，把当前 session 绑定到这个 PR。安装了 hook，不等于已经替它选好了当前 PR。

```text
Execute PR 01a. The approved DESIGN FROZEN document is docs/plan/pr-01a.md,
and the filled contract is docs/plan/pr-01a-contract.md.
Use structured-coding. Read Implementation Working Rules and TEST / CI / GATE
in full, reconcile actual state, and begin.
Continue autonomously to READY FOR OPERATOR REVIEW under the contract.
Do not merge.
```

**进入下一步前，确认这件事**

确认 agent 找对了 PR，也读到了已批准的真实路径。Kickoff 让它在 contract 范围内执行，不会额外授予 host 权限，也不会替你启用 hook。

## 5. 让 agent 把约定范围内的实现循环做完。

Agent 做完一块有意义的修改，运行相关检查，review 逻辑和调用方，记录结果，然后 commit。Unit test 失败，或者在约定范围内发现漏掉的调用方，通常就是查原因、修复、继续。不该每个 commit 都来问你一次。发布 branch、创建 PR 和处理 CI 已经授权的话，它也应该接着做完。

需要你回来决定的是：解决办法要改变已冻结的要求、public interface、重要 scope，或者超出批准预算。Agent 应该带上证据和具体选择，而不是只说一句卡住了。你决定以后，它才能继续受影响的工作。

聊到需要 compact 时，做的还是同一个 PR。手动 compact 前，agent 更新 design 和 handoff。Compact 或 resume 后，它重新读完整规则，核对真实 Git 状态和 process 状态。原来有 test 在跑，就先检查它，别直接再开一份。Continuity 能帮助做机械检查、提供恢复指令，但不会替 agent 写出语义正确的 handoff。

**进入下一步前，确认这件事**

你问当前做到哪一步、有什么证据、接下来做什么，agent 应该能根据已保存的记录回答。收到 hook 提醒，不代表它已经 review，也不代表某个 test 已完成。

## 6. Review 做完的 PR，再决定是否 merge。

对于已授权的 PR 工作流，READY FOR OPERATOR REVIEW 表示约定的 implementation、validation 和逻辑 review 已完成，PR 已创建或更新，而且准确最终 HEAD 的必需 CI 已通过。HEAD 标识当前 commit。旧 commit 的 CI 绿了，不能证明后来又改的内容也通过了。

你把 diff 和原先答应交付的行为对起来，看偏离原因、test evidence 和剩余限制。有问题，就在原 implementation 会话里要求修复。Agent 要更新证据和最终 HEAD 的 CI，再交回来。你可以另找一个 reviewer agent，但工作流不要求必须为 review 多开一个会话。

满意后，明确授权 merge 这个 PR 和你 review 过的版本。没拿到这份授权，agent 就停在可 review 的状态。目前提供的 preset 没有 merge guard，所以这条边界仍靠指令，以及另外配置的 host 或 repo 保护来维持。Contract 如果只授权本地工作，就按本地终点交付，不能假装已经创建或验证了远程 PR。

**进入下一步前，确认这件事**

授权 merge 后，要确认远程确实完成了，并拿到 merge commit。发起了 merge 请求，不等于 merge 已经成功。

## 7. 更新计划，再开始下一个 PR。

确认 merge 后，让 agent 把当前 PR 标为已 merge，再更新所属 step，最后更新 overall plan。不光写完成了什么，还要写这次发现会怎样影响后面的工作。目前 hook 不会验证这些 merge 后的 planning 更新。

比如实现字母排序时，发现 resume 只保存一个文件名。后面的 PR 可能需要更明确地标识：同名文件重复出现时，下次到底从哪一次继续。把这个发现带进下一个 PR design，别沿着已经过时的假设接着做。

你可以回原 planning 会话，也可以新开一个，让它读更新后的文件。细化并批准下一个 PR，再开新的 implementation 会话。上一个 PR 的 agent 可以把记录补完、准备交接，但不能在旧 context 里悄悄开始实现下一个 PR。

**进入下一步前，确认这件事**

一个 PR 的收尾，不只是收到 merge 通知，还要把结果和对后续工作的影响写下来。接着重复这套流程时，你就比上次少了一些没弄清楚的问题。

---

[返回 README](README.zh-CN.md) · [图文 HTML 阅读页](docs/index.zh-CN.html)
