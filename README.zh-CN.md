<!-- Generated file. Source: docs/content.zh-CN.json in the structured-coding repository, built by scripts/build_human_docs.py. Direct edits here are overwritten by the next build. -->

# Structured Coding

[English source](README.md) · [图文 HTML 阅读页](docs/index.zh-CN.html) · [一步一步使用](TUTORIAL.zh-CN.md)

先商量好要改什么，让 agent 放手做，再把结果写回计划。

[快速开始](#start) · [用起来是什么样](#example) · [先做完一个 PR，再规划下一个。](#workflow) · [想了解更多](#further)

<a id="start"></a>

## 快速开始

你需要 Git、Python 3.9 或更新版本，以及 Codex 或 Claude Code 中的一个。在 macOS、Linux 或 WSL 里打开 terminal。下面的命令会下载这个 toolkit，并把 skill 安装到已有项目里，不会替你创建要开发的应用。

```sh
git clone --depth 1 https://github.com/yuema137/structured-coding.git
```

Terminal 保持在刚才 clone 所在的父目录，里面现在应该有 structured-coding 文件夹。把 /path/to/your-project 换成你要让 agent 修改的项目，不是 toolkit 目录。下面两条安装命令选一条就行，路径有空格就加引号。已经下载过 toolkit 的话，跳过 clone，使用现有副本。

Codex:

```sh
./structured-coding/scripts/install codex --project /path/to/your-project
```

Claude Code:

```sh
./structured-coding/scripts/install claude-code --project /path/to/your-project
```

Codex 的请求开头加 $structured-coding，Claude Code 加 /structured-coding。说清 feature 和约束，先让它规划，不要直接开始实现。

Codex 安装后，文件夹在目标项目的 .agents/skills/structured-coding；Claude Code 则在 .claude/skills/structured-coding。接着在目标项目里开新的 agent 会话，明确调用 skill。默认安装带上完整指令和资源，但不注册 hook。如果提示已经有一份，先比较或备份再更新，installer 不会覆盖你的修改。全局设置和权限都不变。

[想加 continuity 或 checkpoints？下面有选装命令和限制说明。](#hooks)

<a id="example"></a>

## 用起来是什么样

三条消息把一个功能从想法带到可以 review 的 PR。你点两次头，中间的活儿由 agent 干。

### 1. 规划 feature

```text
Use the structured-coding workflow for this feature. First agree with me on
requirements, module-level direction, and overall step boundaries; then detail
the current step. Work on planning for now.
Requirements: ...
```

Agent 会问它推断不出来的东西，检查你真实的代码，然后写出总体计划和 step 边界。这一步不写任何实现。

### 2. 准备下一个 PR

```text
Read the overall and step documents, audit the current code, and prepare the
PR 01a design doc and filled execution contract. Follow the original PR
requirements for the commit checklist. Separate implementation, validation,
and review, and prepare the design for my approval.
```

你会拿到一份 PR 设计：经过代码审计的 commit 计划，加一份填好的执行 contract。读它、要求修改，等它确实描述了你想要的东西再批准。

### 3. 批准后，用新 session 执行

```text
Execute PR 01a. The approved DESIGN FROZEN document is docs/plan/pr-01a.md,
and the filled contract is docs/plan/pr-01a-contract.md.
Use structured-coding. Read Implementation Working Rules and TEST / CI / GATE
in full, reconcile actual state, and begin.
Continue autonomously to READY FOR OPERATOR REVIEW under the contract.
Do not merge.
```

一个全新 session 负责实现、验证、review 自己的逻辑、提交，停在 review handoff。你读 diff，决定要不要 merge。

整个循环就这些。确认 merge 之后，agent 会把学到的东西写回计划，下一个 PR 从那里开始。

## 为啥要用 Structured Coding？

计划能写清想做什么，但光有计划，还没说清 agent 怎么执行、拿什么证据算完成、什么时候找你，以及 context 丢了以后怎么接着干。这个 skill 把这些决定连成一套能反复使用的 workflow。

- **眼前的工作，才写细**: 你先和 agent 定好整体方向。下一个 PR 的细节，要等 agent 检查过真实 code 再写。
- **做过的事，能接得上**: Agent 把新发现和证据写进 PR design。换会话以后，可以据此接着做，不必只靠聊天记忆。
- **放手执行，也有边界**: Agent 自己修普通 bug、创建 commit。需要改变原有约定，或者准备 merge 时，再由你作决定。

<a id="workflow"></a>

## 先做完一个 PR，再规划下一个。

![先做完一个 PR，再规划下一个。](docs/assets/workflow.zh-CN.svg)

顺着 01 → 06 看。确认 merge 后，用这次的发现设计下一个 PR。

普通 bug 由 agent 修复；改变约定时，先找你决定。

## 你在哪些地方参与？

不用每次 commit 都点头。但会改变约定的决定，得由你来做。

![你在哪些地方参与？](docs/assets/people.zh-CN.svg)

设计批准以后，agent 自己调查、实现、验证、review、记录并 commit。PR 和 CI 工作如果已经授权，它也会继续做完，不用你一步一步催。

遇到实质性范围变化，或者现有授权以外的操作，agent 带着证据和方案回来找你。

<a id="further"></a>

## 想了解更多

| 资源 | 内容 |
| --- | --- |
| [分步教程](TUTORIAL.zh-CN.md) | 同一个循环，用一个真实功能一条消息一条消息地走一遍。 |
| [工作流参考](structured-coding/references/agent-workflow.zh-CN.md) | Agent 在每个阶段做什么，以及它的权限到哪里为止。 |
| [PR 规范](structured-coding/prompts/pr-design-requirements.md) | 一份 PR 设计在被批准之前必须包含什么。 |
| [可选 hook](structured-coding/references/platforms.zh-CN.md) | 安装方式、覆盖范围，以及 hook 能强制什么、不能强制什么。 |
| [行为契约](structured-coding/references/hook-contract.md) | 完整的目标行为，包括尚未实现的部分。 |

<a id="standards"></a>

## 项目规范（可选）

项目可以把整个 codebase 层面成立的规矩写下来一次，不用每次 planning 都重说一遍。把模板复制到 .structured-coding/standards.md，编辑其中一个块就行。这个文件是可选的：没有它就用下面的 default，行为完全不变。只属于某一个 PR 的要求留在那个 PR 的对话里，这样这份文件才能一直是稳定的仓库资产。

| 你能设置什么 | 写在哪 | Default |
| --- | --- | --- |
| 由 LLM 判断的规范 | review.conventions | 空；你用普通句子写 |
| 这些规范什么时候被提出来 | review.trigger | PR 到达 review 就绪时 |
| 有明确通过/失败的命令 | checks.tools | ruff 和 pyright 只查改动文件；pytest 列出但关闭 |
| 这些检查什么时候适用 | checks.trigger | PR 到达 review 就绪时 |
| 你自己的补充 | .structured-coding/standards.local.md | 只能增加和收紧，不能放松团队的 |

scope 按工具分别设置，因为正确答案本来就因工具而异：只查改动文件适合 ruff 和 pyright，对 pytest 却是误导，因为覆盖这次改动的测试通常在改动没碰过的文件里。工具按「会不会执行你的代码」分组，所以 pytest 和 mypy 是认识的名字但仍需一次明确批准。这一版只读取文件并报告解析结果，同时标注每个值来自哪一层；它不运行任何工具，也不注册 hook，报告干净不等于任何检查跑过。

## 细节，用到时再展开。

按你现在的问题往下看。完整 specification 可以从上面的资源链接打开。

<details id="kit">
<summary>这套 package 具体提供什么？</summary>

<p>我们提供的是一套能接着用的东西：工作流告诉你怎么推进，specification 规定什么才算合格，prompt template 告诉 agent 怎么执行，可选 hook 在特定时刻帮忙检查或提醒。你不用自己把这些零件拼起来。不过，装好了 skill，不代表每条文字规则都已经变成程序强制检查。</p><div class="table-wrap"><table><thead><tr><th scope='col'>资源</th><th scope='col'>提供什么</th></tr></thead><tbody><tr><td>Workflow</td><td>你和 agent 先规划整体目标，再拆 step、细化下一个 PR。Merge 后，agent 把新发现写回这些计划。</td></tr><tr><td>PR specification</td><td>PR requirements 告诉 agent，design 必须包括已检查的 code、commit plan、可观察的验收要求，以及分别记录的 implementation、validation 和 review 证据。</td></tr><tr><td>Execution templates</td><td>Working rules 告诉 agent 怎么推进。填好的 execution contract 记录你的项目允许做什么、什么必须不变、预算是多少，以及在哪里停止。</td></tr><tr><td>Validation rules</td><td>Test rules 帮助 agent 选择能观察到承诺行为的检查。如果一个结论依赖真实 model 或完整 lifecycle，Unit test 通过不能替代相应的真实验证。</td></tr><tr><td>可选 hook preset</td><td>Continuity 帮助 agent 在 compact 前后保存和恢复工作。Checkpoints 提供 commit 和 review 提醒。两者都不提供 merge guard。</td></tr><tr><td>两套平台 package</td><td>项目 installer 给 Codex 和 Claude Code 安装相同的核心 skill。你选一个 host 就行，不需要两个都用，也不会修改全局设置。</td></tr></tbody></table></div>

</details>

<details id="roles">
<summary>你、specification、agent 和 hook，到底各管什么？</summary>

<p>Specification 是写下来的要求，不是一个盯着所有操作的程序。agent 读这些要求，再结合你的项目执行。Hook 则是 host 在特定事件发生时运行的小程序，比如 compact 或调用工具的时候。它能检查什么、提醒什么，要看我们实际实现了什么，不能光看 specification 里写了什么。</p><div class="table-wrap"><table><thead><tr><th scope='col'>谁来负责</th><th scope='col'>具体做什么</th><th scope='col'>不能替代什么</th></tr></thead><tbody><tr><td>你</td><td>你决定要做出什么行为，批准当前 PR design，对实质变化作出选择，并在 review 后明确授权 merge。</td><td>已经在约定范围内的普通修复、test 和 commit，不用每次再等你点头。</td></tr><tr><td>Specification 和 prompt template</td><td>它们规定 PR design 要写什么、agent 怎么执行、什么算有效的验证，以及哪些地方必须有授权。</td><td>文字规则不会自动拦住工具。Hook contract 还包括未来要实现的要求，不全是已经提供的功能。</td></tr><tr><td>Agent</td><td>它读完整的相关规则，检查 code，写计划，实现、运行 test、review 逻辑，并持续更新 design 和 handoff。</td><td>打完勾或说得很有把握，都不能替代 test evidence 和你的批准。即使没装 hook，agent 也得遵守工作流。</td></tr><tr><td>可选 hook</td><td>Continuity 在手动 compact 前检查已记录的 checkpoint，自动 compact 时尝试保存现场，并在恢复时提供读文档的指令。Checkpoints 提供 commit 准备提醒和 review 提醒。</td><td>它们不能理解每项设计取舍，不能证明 test 通过，不能强制 design freeze，也不能拦住所有 merge。它们不会让 agent 自动一轮接一轮地继续。</td></tr></tbody></table></div><p>比如，specification 要求 PR design 里记录验证证据。agent 得真的运行 test，再把结果写进去。Checkpoints 可以提醒它检查缺失的证据，但不能替它认定 test 通过。最后你看结果，再决定是否批准 merge。多装几个 hook，也不能省掉这些责任。</p>

</details>

<details id="sessions">
<summary>到底要开几个会话？</summary>

<p>一个方便的安排是：保留一个 planning 会话，每个 PR 再开一个新的 implementation 会话。需求、overall plan、当前 step 和下一个 PR design，可以在同一个 planning 会话里讨论，不用各开一个。工作流要求的是每个新 PR 用新的 implementation context，不是每次 commit 或 test 都换聊天。 这样分开，是因为 planning 里常有被否决的方案和后来改变的假设。新的 implementation 会话从已批准的文件和当前 code 开始，减少把讨论中的旧想法当成最终要求的机会。</p><div class="table-wrap"><table><thead><tr><th scope='col'>会话</th><th scope='col'>你在这里做什么</th><th scope='col'>什么时候切换</th></tr></thead><tbody><tr><td>Planning 会话</td><td>讨论需求，让 agent 检查 repo、写计划，review 当前 PR design，并批准 execution contract。</td><td>当前 PR 批准后，让 agent 准备带真实文档路径的 kickoff，再开新的 implementation 会话。</td></tr><tr><td>PR A 的 implementation 会话</td><td>把已批准的 design 和 contract 交给 agent，让它实现、验证、review、commit，并完成已授权的 PR 和 CI 工作。</td><td>普通修复、commit、compact 和 resume 都继续处理这个 PR，不在这里启动 PR B。</td></tr><tr><td>PR A 的 review</td><td>你看 diff 和 handoff。有问题，就在原 implementation 会话里要求修复；满意以后，再明确授权 merge。</td><td>可以另开 reviewer 会话，但不是必须。修复后，要更新证据，并确认最终 HEAD 的 CI。</td></tr><tr><td>PR B 的 planning 和 implementation</td><td>确认 A 已 merge 后，让 agent 更新 A 的记录、所属 step 和 overall plan，再据此设计并批准 B。</td><td>你可以回原 planning 会话，也可以新开一个，让它读已保存的计划。B 的 implementation 必须另开新会话。</td></tr></tbody></table></div><p>比如一个功能拆成两个 PR，通常就是三个工作会话：planning、implementation A、implementation B。这是示例，不是硬性数量限制。Planning 聊得太长可以换会话，implementation 中断了也可以恢复。会话之间传递约定，靠的是项目里保存的文档，不是指望另一个聊天自动记得前面的事。 Handoff 就是 agent 保存的接续说明，告诉恢复后的会话：做到哪儿了、什么还在跑、下一步是什么。</p>

</details>

<details id="records">
<summary>agent 到底维护哪些文档？</summary>

<div class="table-wrap"><table><tbody><tr><td>Overall</td><td>它记录整体目标、需求和主要步骤，让后面的 PR 知道在完成哪件事。</td></tr><tr><td>Step</td><td>它说明当前步骤要拆成哪些 PR、谁依赖谁，以及怎样观察到它们配合起来了。</td></tr><tr><td>PR design</td><td>它记录检查过的 code、commit plan，以及实施中持续更新的决定、进度和证据。</td></tr><tr><td>Execution contract</td><td>它记录当前 PR 允许改什么、允许执行哪些操作、预算和停止条件是什么。</td></tr><tr><td>Handoff</td><td>它记录当前 PR、branch 和 HEAD、仍在运行的 job、log 位置，以及恢复后具体接着做什么。</td></tr></tbody></table></div><p>DESIGN FROZEN 固定的是你批准的要求，不是整份文档。Agent 仍要记录新发现和进度。Implementation、validation 和 review 分开记录，只有对应工作真的完成了才能打勾。如果一个 step 只有一个 PR，就展开原 step doc，不必复制成两份。</p>

</details>

<details id="compact">
<summary>compact 或 resume 时，怎么接着干？</summary>

<p>Compact 是 host 为腾出 context 而压缩聊天历史的过程，不是新建一个 PR。新 PR 要开新的 implementation 会话；compact 或 resume 则继续原来的 PR。可选 continuity preset 检查已记录的机械状态是否仍然匹配、尝试保存 snapshot，并提供恢复指令。Design 和 handoff 写得是否准确、恢复时有没有真正核对清楚，仍由 agent 负责。</p><img src="docs/assets/compact.zh-CN.svg" alt="compact 或 resume 时，怎么接着干？" width="900"><p>恢复时，重新读取当前 design、填好的 contract 和完整 execution rules；改 code 前核对 repo 和已有任务。snapshot 不能编决定或测试结果。自动 compact 不能因为 handoff 不完美就一直卡住。</p>

</details>

<details id="hooks">
<summary>可选 hook：安装、覆盖范围和限制</summary>

<p class="status">可选 CONTINUITY + CHECKPOINTS · 尚无 MERGE GUARD</p><p>需要 compact 恢复可选 continuity，需要 commit/review 提醒可选 checkpoints，也可同时安装。默认都不开。Checkpoints 提供建议，不拦截 commit，也不证明已达到交付条件。Protocol 测试不能证明 native 事件送达或模型遵守了提示。agent 不会动态注册自己的 hook。</p><h4>选择需要的 preset</h4><pre><code>./structured-coding/scripts/install codex --project /path/to/project --hooks checkpoints --dry-run
./structured-coding/scripts/install codex --project /path/to/project --hooks checkpoints
./structured-coding/scripts/install codex --project /path/to/project --hooks continuity checkpoints
./structured-coding/scripts/install codex --project /path/to/project --check-hooks
./structured-coding/scripts/install codex --project /path/to/project --upgrade-registration
./structured-coding/scripts/install codex --project /path/to/project --remove-hooks checkpoints
./structured-coding/scripts/install codex --project /path/to/project --remove-hooks</code></pre><p>这些命令和上面的普通安装一样，在包含 toolkit 的父目录里运行。/path/to/project 必须换成目标项目准确的 Git root；Claude Code 用户把 codex 换成 claude-code。先用 --dry-run 预览，再运行你选择的安装命令，不需要把每一行都执行一遍。Installation 会添加选中的 preset；只移除一个 preset，另一个仍可继续用。不带名称的 --remove-hooks 会移除本工具拥有的全部 hook。更改后重启 host，并在 /hooks 里检查注册与信任状态，installer 不会替你授予信任。注册的命令不含任何只属于你这台机器的路径，所以提交到共享设置文件里的注册对同事同样有效，而每个人仍然要在自己机器上审阅并信任这些 hook。旧版本装出来的注册保留其绝对路径，仍然可用；--upgrade-registration 会重写它，这会改变每一条命令，因此需要重新信任这些 hook。Agent 还要绑定当前 session，在 commit 前检查 staged diff，并明确准备 review handoff。提醒不能把没运行、没定论或仍在等待的检查变成通过。已有设置、skill 文件和 session 数据会保留。</p><a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/continuity.md">Continuity preset interface →</a> · <a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/checkpoints.md">Checkpoints preset interface →</a><div class="table-wrap"><table><thead><tr><th scope='col'>功能</th><th scope='col'>候选事件</th><th scope='col'>应有的行为</th><th scope='col'>已提供的支持</th></tr></thead><tbody><tr><td>H1 · 实现前</td><td>PreToolUse</td><td>核对已批准设计、contract、repo 状态和恢复情况。不匹配就拒绝依赖这些条件的修改；audit 和设计准备仍然允许。</td><td>尚未实现</td></tr><tr><td>H2 · commit 前</td><td>PreToolUse</td><td>检查或提示 diff review、ledger、证据和偏离记录。agent 修好再试，不增加每个 commit 都找人批准的步骤。</td><td>Checkpoints：明确的准备步骤，以及 Bash 直接 git commit 的提示；不强制执行</td></tr><tr><td>H3 · merge 前</td><td>PreToolUse + merge 路径覆盖</td><td>要求来自可信通道、对应具体 PR、目标 branch 和候选 HEAD 的明确授权，并核对完成条件及 CI/Gate 证据。覆盖 CLI、API、auto-merge 和直接操作目标 branch 的绕行路径。</td><td>尚未实现</td></tr><tr><td>H4 · 手动 compact</td><td>PreCompact: manual</td><td>handoff 过时就先拦住，同步后再允许 compact。</td><td>Continuity：只检查机械 checkpoint 是否仍然对应当前状态</td></tr><tr><td>H5 · 自动 compact</td><td>PreCompact: auto</td><td>允许 compact；必要时保存机械 snapshot。保存失败也要留警告，并要求恢复。</td><td>Continuity：限时尝试 snapshot，不主动阻断自动 compact</td></tr><tr><td>H6 · compact/resume</td><td>SessionStart + 修改前检查</td><td>动态确认当前 PR，完整读取规则，核对 repo 和进程状态再继续，别重复启动任务。</td><td>Continuity：提供 session 绑定的 PR 和完整读取指令；没有修改 guard，也不能证明恢复完成</td></tr><tr><td>H7 · 准备交付 review</td><td>Stop / 完成事件</td><td>核对真实完成条件、最终 HEAD 的 CI、证据和 handoff。准备好 review 不等于允许 merge。</td><td>Checkpoints：明确 intent 后最多一次 operator 提醒；不自动续跑，也不判定证据通过</td></tr><tr><td>H7 · merge 后</td><td>已观察结果 / 核对远端状态</td><td>确认 merge，再要求并检查 PR → step → overall 更新。agent 写经验，下一个 PR 用新 session。</td><td>尚未实现</td></tr></tbody></table></div><p>有事件名，不等于一定能拦截。adapter 得处理各 host 的 protocol、可信授权来源和 tool 覆盖缺口。merge 后的检查不能倒过来阻止 merge。实现 adapter 前，先看 contract 的验收场景。</p><p>比如：批准 PR 12 的 HEAD A，不等于允许 merge 后来的 HEAD B。实现中的 agent 也不能自己写个“已批准”，就把它当成人的授权。</p><a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/hook-contract.md">Hook behavior contract →</a>

</details>

<details id="format">
<summary>这是 skill、skillset，还是 plugin？</summary>

<p>当前是一个独立 skill，带配套资源和可选 hook preset。多个能独立使用的 skill 可以组成 skillset；plugin 可以把它们和其他 host 接入一起打包。项目安装保持简单，不托管更新，hook 也需要明确选装；未来仍然可以提供 plugin 分发。</p>

</details>

<details id="fit">
<summary>什么工作值得走完整流程？</summary>

<p>适合跨 PR 或 session 的较大改动。改错别字、修一个独立小 bug，通常不用搬出整套流程。计划、测试和 LLM review 仍可能出错；这套 workflow 让假设和证据能被检查。</p>

</details>

---

[完整 human guide](structured-coding/README.zh-CN.md) · [一步一步使用](TUTORIAL.zh-CN.md) · [图文 HTML 阅读页](docs/index.zh-CN.html)

Clone 后，可以在浏览器里打开 docs/index.zh-CN.html 或 docs/index.html。HTML 页面提供同一份完整教程和可复制的消息，核心步骤不用展开折叠框就能读到。GitHub 的文件页显示 HTML 源码，不会直接显示这个页面布局。

英文是唯一正确源；中文是同步镜像，保留英文专业术语。给人看的解释沿用 DongbeiGPT。specification 和可复用 prompt 全部使用英文。
