# Agent workflow

[Chinese mirror](agent-workflow.zh-CN.md)

This is the detailed operational explanation. The prompts provide the complete planning and execution requirements. Read the resources routed by `SKILL.md` for the active phase; do not use this explanation as a shortened replacement for the execution prompts.

## 1. Identify the active work

Inspect the user's request and the repository's existing planning conventions. Locate the overall, step, and current PR documents if they exist. Inspect branch, HEAD, working tree, relevant history, and active work before deciding that an old checkpoint is current.

Choose the requested phase: overall planning, step planning, PR design/freeze, execution, same-PR recovery, operator review, or post-merge update. Explain the chosen phase briefly. Continue from usable existing artifacts instead of regenerating the hierarchy.

Keep a single active PR identity per implementation context. Record repository/worktree, PR identifier, branch/base, primary design, parent documents, and filled execution contract. Paths below are examples, not prescribed filenames:

```text
docs/plan/overall.md
docs/plan/step-01.md
docs/plan/pr-01a.md
docs/plan/pr-01a-contract.md
before_end_memory.md
```

Do not create additional tracking documents that compete with the primary PR ledger. The contract can be a section of the PR design or a separate linked document. The handoff is a continuation aid, not another design authority.

## 2. Overall planning: agree on the destination

Work with the operator to establish the final requirement, major use cases, observable project outcome, high-level implementation, scope/non-goals, major risks, and step boundaries. Use repository inspection to ground architectural claims.

Describe modules and large capabilities. Leave file/function details for the PR that will implement them. Explain meaningful tradeoffs and ask about missing product or direction decisions that the available evidence cannot settle. Continue independent audit and drafting while those decisions are pending.

Use a form suited to the project. An overall document is ready when the operator understands and agrees on what will be delivered and the broad route. Do not infer agreement from silence or proceed into code merely because an overall document exists.

## 3. Step planning: choose useful PR checkpoints

Read the agreed overall direction and inspect the relevant subsystem. Determine whether the step needs one PR or several.

For multiple PRs, describe each PR's medium scope: likely files or file groups, their relationships, dependencies, and excluded follow-up work. Define a meaningful integration checkpoint for each PR, with observable pass conditions and adversarial criteria. Avoid splitting PRs solely by file count or arbitrary size.

For one PR, first establish the step scope, then expand that same document in place to PR-level detail. Label its combined step/PR role and link it directly to the overall document. Do not maintain two separate copies of the same plan.

Keep later PRs at medium scope until evidence from earlier implementation justifies their detailed design. A known dependency that invalidates a later step should be flagged immediately, even though only the next PR is fully detailed.

## 4. PR design: audit before prescribing

Read the complete [PR requirements](../prompts/pr-design-requirements.md), [test rules](../prompts/test-ci-gate-rules.md), and the project-specific contract block in [working rules](../prompts/implementation-working-rules.md).

Audit the relevant code, callers, downstream consumers, tests, schemas, preserved evidence, and history as needed. The design should state:

- The PR's goal, approved scope, non-goals, invariants, and parent dependencies.
- The source audit: actual files/symbols inspected, findings, and unresolved assumptions.
- The final observable acceptance and the integration/adversarial checkpoint.
- An ordered commit plan using all eight sections in the preserved requirements.
- Test ownership: which failure class belongs to static checks, Unit, real-LLM Gate, real-lifecycle Gate, or terminal CI; mark inapplicable layers explicitly.
- Execution base, validation budget, publication authority, stop condition, and merge boundary.

Implementation items must be concrete atomic operations, at file/function detail when the audit supports it. Do not fabricate low-level steps that require discoveries only available during implementation.

For every commit, maintain separate checkable implementation, validation, and LLM review work. For example, after verifying the actual repository paths:

```markdown
- [ ] Implementation: thread the new option through the audited caller chain.
- [ ] Validation: observe the selected item sequence under a fixed input.
- [ ] Review: inspect every caller for a silently dropped option or stale default.
```

Validation is deterministic or empirical execution evidence for a specified claim. Review is LLM analysis of logic, contracts, consumers, and overlooked cases. One does not automatically complete the other. A review may be performed by the implementing agent; separate-agent review is optional and depends on the user's workflow and available authority.

Use `[x]` only with the corresponding completed work and recorded evidence. If an item turns out not to apply, record `N/A` and the audited reason rather than claiming a test or review occurred.

## 5. Freeze the approved design

Iterate the PR design with the operator. Prepare a filled implementation contract from the original template; preserve its working-rule body. Unknown required values remain unresolved until audited or decided; use `N/A` only for actual non-applicability.

The contract must distinguish the per-Gate limit from the total runtime/cost envelope and identify whether commit, branch publication, PR updates, and validation are authorized. Reuse existing session authorization; do not ask again for a decision already made.

When the operator approves the concrete design for implementation, record a visible header such as:

```markdown
# PR 01a — <title>

## DESIGN FROZEN

Design revision: <stable revision or fingerprint of the approved design sections>
Approved by / evidence: <operator approval reference>
Implementation base: <branch and exact commit>
Execution contract: <section or relative path>
Lifecycle: FROZEN
```

This is a documentation convention, not a cryptographic authorization mechanism. Never manufacture approval or mark a design frozen merely because the agent finished drafting it.

Freeze semantic requirements and acceptance, while leaving the live ledger writable. A whole-file hash is unsuitable as the permanent freeze identity because evidence and progress will change. The future hook must distinguish frozen sections from live sections.

## 6. Prepare the fresh execution session

Prepare a kickoff using the filled project contract plus the complete original working rules and test rules. A kickoff can reference those files for full reading; do not substitute a short paraphrase of the rules. The operator starts a fresh implementation session for each new PR.

Before implementation edits, the new session must:

1. Inspect branch, HEAD, status, recent history, and relevant running jobs.
2. Read the PR design in full, its filled contract, and the needed binding parents.
3. Verify approved design identity, implementation authorization, base, and merged prerequisites.
4. Read both execution prompt files completely and inspect the source/tests for the first milestone.
5. Initialize the handoff for this PR with the fields required by the original contract.

Archive or replace prior-PR state only in the designated workflow handoff. Preserve unrelated notes and work. An isolated worktree may be appropriate when existing edits overlap; do not discard those edits.

If a fresh session cannot be started by the agent, produce the complete kickoff artifact and report that execution has not started. A planning conversation does not become a fresh session through a status label.

## 7. Execute each semantic milestone

Re-read the current file section before editing. Implement within the frozen contract, inspect relevant consumers, run the cheapest sufficient validation, perform the planned logic review, and record evidence as each checkpoint completes.

Keep the primary design current throughout the work. Record new findings when discovered, including failed assumptions and failed attempts, not just the successful final implementation. Record decisions with enough evidence to explain what was chosen and why; private internal reasoning is not a deliverable.

Before each semantic commit, inspect the exact diff and staged files, confirm scope, record tests and deviations, and synchronize the ledger. Commit and continue autonomously. A planned commit can become several coherent commits when that improves reviewability; record the mapping back to the plan.

Refresh the handoff at semantic milestones and material checkpoint changes. It should normally be no more than one milestone stale. Record background job identifiers, log/artifact paths, runtime expectations, and next actions so a resumed session does not start duplicate work.

### Uncertainty and deviation

First inspect the design, actual source, consumers, tests/evidence, and relevant history. Consult authoritative external sources when an external technical fact remains uncertain. Record consequential external findings and their sources in the PR ledger.

If the answer is bounded by approved intent, proceed and record the discovery, alternatives, decision, rationale, impact, and validation. Routine defects, extra callers, narrow helpers, and more appropriate test seams do not automatically require operator input.

If the honest solution changes a frozen invariant, public contract, ownership boundary, material dependency/architecture, or scope, prepare the evidence and smallest reviewable proposed revision. Stop the dependent action and obtain the material decision. Keep unaffected authorized work moving when useful.

Do not expand the PR indefinitely to fix unrelated repository defects. Establish their relationship to the change and record material follow-ups; continue if current acceptance is unaffected.

### Validation and evidence

Use the complete test rules. Define the claim and its owner before expensive runs. Keep real Gates real and bounded; classify each result as `PASS`, `FAIL`, or `INCONCLUSIVE` from actual evidence, not just the exit code.

Record commands, test counts, wall time, environment, artifacts, and decisive observations as appropriate. A test not run is not a pass. Do not weaken assertions or fake expected values to produce green output.

Associate evidence with the actual tested state. For a pre-commit working-tree run, record the base HEAD plus diff/untracked-content fingerprint and relevant configuration. Associate it with the subsequent commit only after verifying that the tested executable content matches. A HEAD alone cannot describe uncommitted changes.

Preserve measurement evidence and frozen parity references. Store durable evidence in the project's established location and link it from the design; temporary logs alone are not the handoff.

## 8. Recover the same PR after compaction

Compaction does not reset progress or initialize a new PR. Recover the active PR from the handoff, verify it against repository identity and branch/base, and follow the source authority order: repository/git/process truth → primary design → binding parents → handoff → emergency snapshot → conversational memory.

Re-read the current PR design in full, the filled contract, and both execution prompts. Inspect active processes and CI runs before launching replacements. Re-open the source seam for the exact next action and reconcile stale checkbox/evidence claims before editing.

For planned manual compaction, synchronize the design, handoff, HEAD, and working-tree fingerprint first. For unavoidable automatic compaction, a stale semantic handoff should produce a mechanical rescue snapshot and recovery warning, not a compaction deadlock. The hook must not invent a semantic summary.

Detailed event behavior and acceptance cases are in the [hook contract](hook-contract.md). In this instruction-only edition these are procedural obligations, not installed guards.

## 9. Reach operator review readiness

Finish implementation, planned reviews, ledger updates, and required validation. Commit the intended final content, perform authorized publication/PR work, inspect the PR diff/body, and track canonical CI for the exact final PR HEAD. Repair routine failures, push the resulting head, and verify the new CI evidence.

Operator review can happen while CI runs. Do not stop the autonomous execution loop merely because the PR exists or CI has started. Do not treat old-head green CI as proof of the current head.

Prepare the complete handoff listed in working rules §22: PR/base/head, semantic changes, discoveries/deviations, document updates, actual evidence by layer, limitations, and working-tree state. Record final executable HEAD and final PR HEAD distinctly when they differ.

Set lifecycle to `READY FOR OPERATOR REVIEW` only when the contract's requirements are met. Mark the implementation context `CLOSED / AWAITING OPERATOR ACTION`; this closes the autonomous run, not the PR itself. Do not merge without explicit operator authorization.

Avoid a self-referential final-SHA loop: a commit cannot contain its own hash. Keep final CI/head pointers in the designated handoff or PR metadata when appropriate; track all acceptance-affecting design content before final CI. Never create another acceptance-affecting commit and claim previous-head CI applies to it.

If review requests a repair, explicitly reopen work on the same PR, reconcile its state, and revalidate affected claims. It remains the same PR context; the rule about a fresh context applies to the next PR.

## 10. Merge and update backward

Once explicit merge authorization exists, confirm its target and verify the current head and required checks before the authorized merge. Approval for a prior candidate cannot be assumed to cover a materially changed candidate. Confirm the actual merge result; do not mark merged on intent or a queued operation.

After confirmed merge:

1. Update the PR document to `MERGED` and record the actual merge commit/result.
2. Update the parent step with completed capability, implementation facts, achieved checkpoint, and remaining work.
3. Update the overall document with resulting progress and material direction/dependency implications.
4. Re-audit and detail the immediate next PR using the merged code and new findings. Flag wider implications at their proper level without rewriting every future PR in detail.

For a combined step/PR document, update it once and then the overall document; do not invent a separate parent or create a self-reference.

Make status updates through the repository's established documentation process. If the implementation branch is closed or protected, prepare/use the appropriate documentation change rather than silently pushing to a protected branch. Do not claim parent synchronization is complete until it is recorded in the authoritative location.

The next PR design must obtain its own freeze/implementation authorization and begin in a fresh execution session. Its knowledge comes from merged state and binding documents, not unfinished memory from the previous PR.
