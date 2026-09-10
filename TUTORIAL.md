<!-- Generated file. Source: docs/content.en.json in the structured-coding repository, built by scripts/build_human_docs.py. Direct edits here are overwritten by the next build. -->

[Chinese mirror](TUTORIAL.zh-CN.md) · [Back to the README](README.md)

# Your first feature, from installation to the next PR

Follow this example in order. Suppose your application reads files and you want an optional alphabetical order while preserving the current default. The paths and PR label in the sample messages are placeholders, not files supplied by this toolkit. Ask the planning agent to create the real documents first, then replace the placeholders before execution. The English entry messages below are identical in both language versions; they do not replace the full original prompts.

## 1. Open the planning conversation and explain the result you want.

Open your target project in your chosen agent host. Invoke $structured-coding in Codex or /structured-coding in Claude Code, then send the planning request below with your actual requirements.

For the example, say that alphabetical mode must visit [c, a, b] as [a, b, c], and that leaving the option off must preserve the old behavior. Explain what is outside scope, such as changing the resume mechanism in this PR. The agent should inspect the repo, ask about unresolved product decisions, and propose an overall direction. It should not start implementing merely because you asked for a plan.

```text
Use the structured-coding skill for this feature. Read its SKILL.md
entrypoint first and load the complete resources its table lists for the
current phase.
First agree with me on requirements, module-level direction, and overall
step boundaries; then detail the current step. Work on planning for now.
Requirements: ...
```

**Before you move on**

Before moving on, you should be able to explain the goal and main steps in your own words. Ask the agent to rewrite anything you cannot review; you do not have to author its design document yourself.

## 2. Ask the same planning agent to detail only the next PR.

The overall plan describes the feature and its main steps. A step plan explains which PRs fit together. The current PR design goes deeper: the agent reads real code and callers before naming the files, functions, commits, and checks. Later PRs can remain less detailed because this implementation may reveal new facts. The PR requirements define the detailed format. Ask the agent to follow that complete specification; you do not need to reconstruct the template yourself.

For the alphabetical-order PR, acceptance must observe the reader visiting [a, b, c], not just a configuration value being stored. Ask for a check that would fail if a caller silently dropped the option. Each commit needs separate implementation, validation, and logic-review items. If a step needs only one PR, the agent can expand the step document in place instead of maintaining a duplicate.

```text
Read the overall and step documents, audit the current code, and prepare the
PR 01a design doc and filled execution contract. Use structured-coding:
start from its SKILL.md entrypoint and load what the PR design row lists.
Follow the original PR requirements for the commit checklist. Separate
implementation, validation, and review, and prepare the design for my
approval.
```

**Before you move on**

The agent should give you the real PR design path and a filled execution contract. Agree where these records live and which, if any, belong in Git. Private planning notes and raw logs do not automatically belong in the published product.

## 3. Review the agreement and explicitly approve this PR.

Check what changes, what stays unchanged, what is excluded, and what observable result will count as done. The execution contract should also say whether the agent may commit, push a branch, open or update a PR, and repair CI, and where it must stop. These are separate permissions; asking for local implementation alone does not authorize publication.

When the design matches your intent, explicitly approve that concrete design and contract. The agent records DESIGN FROZEN and the approval reference. Freeze protects the agreed scope, invariants, and acceptance, not the whole file: the agent must still update discoveries, progress, and evidence. Approval of implementation is not approval to merge.

For authorized validation, existing subscription-covered usage does not need another provider/account or billing question. Metered API calls and separately charged usage need applicable spending authorization. Existing time limits, quotas, and explicit restrictions still apply; the agent must not switch accounts or enable paid fallback to evade them. Separate approval requirements for real training still apply when the task has them.

**Before you move on**

Ask for a kickoff that identifies the approved design, filled contract, implementation base, next action, and stopping condition. Do not copy a template containing unresolved paths into execution and assume it is ready.

## 4. Open a fresh implementation conversation for this PR.

Start a genuinely new conversation in the same target project. Do not just rename the planning conversation. Invoke the skill again and give it the kickoff with the actual paths. The new agent does not need the entire planning chat: it needs the durable agreement and the source files that establish current state.

Before editing, the agent must re-read the skill entrypoint and its execute row, then the approved design, filled contract, and complete execution and test rules. It checks the branch, HEAD, existing edits, merged prerequisites, and relevant running jobs. It preserves unrelated work. If you explicitly enabled a preset, it also reads that preset's interface and binds this session to the current PR; it must not assume installation selected an active PR for it.

```text
Execute PR 01a. The approved DESIGN FROZEN document is
.structured-coding/plans/order-flag/pr-01a.md, and the filled contract is
.structured-coding/plans/order-flag/pr-01a-contract.md.
Use structured-coding: read its SKILL.md entrypoint, then the complete
resources its execute row lists, including Implementation Working Rules and
TEST / CI / GATE in full. Reconcile actual state, and begin.
Continue autonomously to READY FOR OPERATOR REVIEW under the contract.
Do not merge.
```

**Before you move on**

Confirm that the agent is working on the intended PR and has loaded the approved paths. The kickoff delegates execution within the contract; it does not grant extra host permissions or enable hooks.

## 5. Let the agent complete the agreed implementation loop.

The agent implements a coherent piece, runs relevant checks, reviews the logic and callers, records what happened, and commits. A Unit test failure or an extra caller inside the agreed scope normally means investigate, fix, and continue. It should not ask you to approve every commit. If branch publication and PR/CI work are authorized, it continues through those steps too.

You step in when the proposed solution changes a frozen requirement, public interface, material scope, or approved budget. The agent should bring evidence and a concrete choice, not merely say it is blocked. Review that choice before the dependent work proceeds.

If the conversation reaches compact, you are still working on the same PR. Before manual compact, the agent updates its design and handoff. After compact or resume, it rereads the full rules and checks actual Git and process state. A running test must be checked before launching a duplicate. Continuity helps with mechanical checks and recovery instructions; it does not write a correct semantic handoff for the agent.

**Before you move on**

You should be able to ask for the current milestone, evidence, and next action and get an answer grounded in saved records. A hook notice is not proof that the agent performed a review or completed a test.

## 6. Review the finished PR, then decide whether to merge.

For an authorized PR workflow, READY FOR OPERATOR REVIEW means the agreed implementation, validation, and logic review are complete, the PR is published or updated, and required CI passes on its exact final HEAD. HEAD identifies the current commit. A green result for an earlier commit does not prove a later edit passed.

Read the diff alongside the promised behavior, deviations, test evidence, and remaining limits. If something is wrong, request repairs in the same implementation conversation. The agent should update the evidence and final-head CI before handing it back. You can use a separate reviewer agent, but the workflow does not require another conversation for review.

When satisfied, explicitly authorize merging the specific PR and reviewed candidate. Without that approval, the agent stops at review readiness. The shipped presets do not provide a merge guard, so this boundary remains an instruction and any separately configured host/repository protection. A local-only contract has a local endpoint; the agent must not pretend it created or validated a remote PR.

**Before you move on**

After an authorized merge, require confirmation of the actual remote result and merge commit. A merge command being requested is not the same as a completed merge.

## 7. Update the plans before starting the next PR.

After merge is confirmed, ask the agent to mark the current PR merged, update its parent step, and update the overall plan. The updates should record both completed work and discoveries that change what comes next. Hooks do not currently verify this post-merge planning work.

For example, the alphabetical-order implementation may reveal that resume stores only a filename. A later PR may need a clearer way to identify the next occurrence of a repeated filename. Bring that discovery into the next PR's design instead of continuing from an old assumption.

Return to your planning conversation, or open a new planning conversation that reads the updated files. Detail and approve the next PR, then start another fresh implementation conversation. The previous PR's agent may finish its records and prepare a handoff; it must not quietly begin implementing the next PR in the old context.

**Before you move on**

One PR is finished when its result and implications are recorded, not merely when a merge notification appears. You now repeat the same cycle with a smaller amount of uncertainty.

---

[Back to the README](README.md) · [Visual HTML guide](docs/index.html)
