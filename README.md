# Structured Coding

[Chinese mirror](README.zh-CN.md) · [Visual HTML guide](docs/index.html)

Agree on the change. Let the agent build it. Bring the result back into the plan.

## Why use Structured Coding?

A plan describes what you intend to build. It does not, on its own, tell an agent how to execute, what counts as evidence, when to ask you, or how to resume after losing context. This skill connects those decisions into one repeatable workflow.

- **Plan what is knowable**: Keep the overall direction clear. Audit real code before detailing the next PR.
- **Keep the work recoverable**: Record discoveries and evidence in the PR design, not only in the chat.
- **Give autonomy a boundary**: Let the agent fix ordinary bugs and commit. Keep material decisions and merge authorization with you.

## One PR at a time. One continuous loop.

![One PR at a time. One continuous loop.](docs/assets/workflow.svg)

Follow 01 → 06. After a confirmed merge, use the findings to design the next PR.

Ordinary bugs: repair and continue. Material changes: return for approval.

## A complete workflow kit.

Not just a place to write a plan. A process, its specifications, the prompts to run it, optional hook presets, and a contract for future guards.

| Resource | What it provides |
| --- | --- |
| [Workflow](structured-coding/references/agent-workflow.md) | Overall → step → PR, autonomous execution, and post-merge plan updates. |
| [PR specification](structured-coding/prompts/pr-design-requirements.md) | An audited commit plan, observable acceptance, and separate implementation, validation, and review evidence. |
| [Execution templates](structured-coding/prompts/implementation-working-rules.md) | Execution working rules and a project-specific contract for scope, permissions, budget, and stopping. |
| [Validation rules](structured-coding/prompts/test-ci-gate-rules.md) | Static checks, Unit, real Gates, and final-HEAD CI. Choose evidence that actually observes the claim. |
| [Optional hook presets](structured-coding/references/platforms.md) | Continuity for compact recovery; checkpoints for commit and review reminders. Freeze and merge guards remain future work. |
| [Two platform packages](structured-coding/references/platforms.md) | One shared skill for Codex and Claude Code, with a project installer. No global configuration changes. |

## Install it. Start with a request.

Git + Python 3.9 or later. Install Codex or Claude Code first. These commands work on macOS/Linux and in WSL.

```sh
git clone --depth 1 https://github.com/yuema137/structured-coding.git
```

Replace /path/to/your-project with your existing project root. Run the installer from the directory where you cloned this repo.

Codex:

```sh
./structured-coding/scripts/install codex --project /path/to/your-project
```

Claude Code:

```sh
./structured-coding/scripts/install claude-code --project /path/to/your-project
```

Prefix your request with $structured-coding in Codex or /structured-coding in Claude Code. Describe the feature and its constraints; ask for planning first, not implementation.

Default installation copies the full skill without registering hooks or overwriting an existing copy. Global settings and permissions are unchanged.

[Want continuity or checkpoints? See the opt-in commands and limits below.](#hooks)

## Where you step in.

You do not need to approve every commit. You do need to own the decisions that change the agreement.

![Where you step in.](docs/assets/people.svg)

Between approval and review: the agent investigates, implements, validates, reviews, records, and commits. Authorized PR/CI work continues too.

A material scope change or an action outside existing authorization comes back to you with evidence and a proposal.

## The details, when you need them.

Open the part relevant to your current question. Use the resource links above for the complete specifications.

<details id="records">
<summary>What documents does the agent maintain?</summary>

<div class="table-wrap"><table><tbody><tr><td>Overall</td><td>Direction, requirements, and step boundaries</td></tr><tr><td>Step</td><td>PR boundaries, dependencies, and integration checkpoints</td></tr><tr><td>PR design</td><td>Audited commit plan + live decisions, progress, and evidence</td></tr><tr><td>Execution contract</td><td>The approved scope, authority, budget, and stopping conditions</td></tr><tr><td>Handoff</td><td>Current PR, branch/HEAD, jobs, logs, checkpoint, and next action</td></tr></tbody></table></div><p>DESIGN FROZEN freezes the agreement, not the running record. Track implementation, validation, and review separately. If one step is one PR, expand the step doc in place instead of duplicating it.</p>

</details>

<details id="compact">
<summary>What happens at compact or resume?</summary>

<p>A new PR starts in a fresh session. A compact/resume continues the same PR. The optional continuity preset checks mechanical freshness, attempts snapshots, and supplies recovery instructions. Semantic synchronization and recovery remain the agent&#x27;s responsibility.</p><img src="docs/assets/compact.svg" alt="What happens at compact or resume?" width="900"><p>On resume, reload the current design, filled contract, and full execution rules; check the repo and existing jobs before editing. A snapshot cannot invent decisions or test results. Automatic compact must not get stuck waiting for a perfect handoff.</p>

</details>

<details id="hooks">
<summary>Optional hooks: installation, coverage, and limits</summary>

<p class="status">OPTIONAL CONTINUITY + CHECKPOINTS · NO MERGE GUARD</p><p>Choose continuity for compact recovery, checkpoints for commit/review reminders, or both. Both are off by default. Checkpoints advises; it does not enforce commits or certify readiness. Protocol tests do not establish native event delivery or model compliance. The agent does not dynamically register its own hooks.</p><h4>Choose your optional presets</h4><pre><code>./scripts/install codex --project /path/to/project --hooks checkpoints --dry-run
./scripts/install codex --project /path/to/project --hooks checkpoints
./scripts/install codex --project /path/to/project --hooks continuity checkpoints
./scripts/install codex --project /path/to/project --check-hooks
./scripts/install codex --project /path/to/project --remove-hooks checkpoints
./scripts/install codex --project /path/to/project --remove-hooks</code></pre><p>Use the exact project Git root; replace codex with claude-code for Claude Code. Installation adds presets; selective removal keeps the other usable. Bare --remove-hooks removes all owned presets. Restart the host and inspect /hooks; trust is not granted. The agent binds its session, inspects staged changes before commit, and explicitly prepares the review handoff. Reminders do not turn pending, inconclusive or not-run checks into passes. Existing settings, skill files and session data are preserved.</p><a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/continuity.md">Continuity preset interface →</a> · <a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/checkpoints.md">Checkpoints preset interface →</a><div class="table-wrap"><table><thead><tr><th scope='col'>Function</th><th scope='col'>Candidate event</th><th scope='col'>Intended behavior</th><th scope='col'>Shipped support</th></tr></thead><tbody><tr><td>H1 · Before implementation</td><td>PreToolUse</td><td>Check approved design, contract, repo state, and recovery. Deny dependent mutations when they do not match; still allow audit/design preparation.</td><td>Not implemented</td></tr><tr><td>H2 · Before commit</td><td>PreToolUse</td><td>Check or surface diff inspection, ledger, evidence, and deviations. Repair and retry autonomously; no per-commit human gate.</td><td>Checkpoints: explicit preparation and advice for direct git commit via Bash; no enforcement</td></tr><tr><td>H3 · Before merge</td><td>PreToolUse + merge-route coverage</td><td>Require trusted explicit approval for the exact PR, target branch, and candidate HEAD, plus readiness and CI/Gate evidence. Cover CLI, API, auto-merge, and direct target-branch bypasses.</td><td>Not implemented</td></tr><tr><td>H4 · Manual compact</td><td>PreCompact: manual</td><td>Block a stale handoff until synchronized, then allow compact.</td><td>Continuity: mechanical checkpoint freshness only</td></tr><tr><td>H5 · Automatic compact</td><td>PreCompact: auto</td><td>Allow compact; save a mechanical snapshot when needed. Preserve failures as warnings and require recovery.</td><td>Continuity: bounded snapshot attempt; never intentionally blocks automatic compact</td></tr><tr><td>H6 · Compact/resume</td><td>SessionStart + mutation guard</td><td>Resolve the current PR dynamically. Reload full rules and reconcile repo/process state before continuing; do not duplicate jobs.</td><td>Continuity: session-bound PR and full-read instructions; no mutation guard or proof of recovery</td></tr><tr><td>H7 · Review readiness</td><td>Stop / completion event</td><td>Verify real completion conditions, exact-final-HEAD CI, evidence, and handoff. Readiness does not authorize merge.</td><td>Checkpoints: explicit intent and at-most-once operator notice; no automatic continuation or evidence verdict</td></tr><tr><td>H7 · After merge</td><td>Observed result / remote-state check</td><td>Confirm merge, then request and verify PR → step → overall updates. The agent writes the lessons; the next PR uses a fresh session.</td><td>Not implemented</td></tr></tbody></table></div><p>An event name alone does not guarantee blocking. Adapters must handle each host&#x27;s protocol, trusted approval source, and tool-coverage gaps. A check after merge cannot prevent it. Read the contract&#x27;s acceptance scenarios before implementing an adapter.</p><p>Example: approval for PR 12 at HEAD A does not authorize merging a later HEAD B. The implementing agent cannot turn its own “approved” field into human authorization.</p><a href="https://github.com/yuema137/structured-coding/blob/main/structured-coding/references/hook-contract.md">Hook behavior contract →</a>

</details>

<details id="prompts">
<summary>What should I say to the agent?</summary>

<p>These are entry requests, not substitutes for the preserved prompts. The agent still reads the complete required files.</p><h4>Plan the feature</h4><pre><code>Use the structured-coding workflow for this feature. First agree with me on
requirements, module-level direction, and overall step boundaries; then detail
the current step. Work on planning for now.
Requirements: ...</code></pre><h4>Prepare the next PR</h4><pre><code>Read the overall and step documents, audit the current code, and prepare the
PR 01a design doc and filled execution contract. Follow the original PR
requirements for the commit checklist. Separate implementation, validation,
and review, and prepare the design for my approval.</code></pre><h4>Execute after approval, in a fresh session</h4><pre><code>Execute PR 01a. The approved DESIGN FROZEN document is docs/plan/pr-01a.md,
and the filled contract is docs/plan/pr-01a-contract.md.
Use structured-coding. Read Implementation Working Rules and TEST / CI / GATE
in full, reconcile actual state, and begin.
Continue autonomously to READY FOR OPERATOR REVIEW under the contract.
Do not merge.</code></pre>

</details>

<details id="format">
<summary>A skill, a skillset, or a plugin?</summary>

<p>Today this is one standalone skill with supporting resources and optional hook presets. A skillset would contain several independently useful skills; a plugin can package those skills and other host integrations. Project installation stays simple. Updates are not managed, and hook registration is explicit and optional; plugin packaging remains an option for future distribution.</p>

</details>

<details id="fit">
<summary>When is the full workflow worth it?</summary>

<p>Use it for substantial changes spanning PRs or sessions. A typo fix or isolated small bug usually does not need this ceremony. Plans, tests, and LLM reviews can still be wrong; the workflow makes their assumptions and evidence inspectable.</p>

</details>

---

[Detailed human guide](structured-coding/README.md) · [Visual HTML guide](docs/index.html)

After cloning, open docs/index.html or docs/index.zh-CN.html in a browser. GitHub shows HTML source rather than this page layout.

English is the authoritative source; Chinese is a synchronized mirror with English technical terms. The human explanation follows DongbeiGPT. Specifications and reusable prompts are in English.
