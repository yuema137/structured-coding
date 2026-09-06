---
name: structured-coding
description: "Plan and execute substantial coding work through overall, step, and PR design documents, frozen implementation contracts, autonomous execution, and post-merge plan updates. Use for the Structured Coding workflow, detailed PR commit plans, approved PR execution or recovery, and backward planning updates; do not impose the full workflow on unrelated small edits or reviews."
---

# Structured Coding

Use progressively detailed planning, a live PR design ledger, and autonomous implementation within an approved contract. Keep human decisions at requirements, design freeze, material deviations, and merge review.

## Start with the current phase

Identify the requested phase from the user, existing documents, and repository state. Continue an existing workflow at its current checkpoint. A planning request does not authorize implementation; loading this skill does not authorize a merge.

Read [agent-workflow.md](references/agent-workflow.md) and [adaptation.md](references/adaptation.md). Then load the complete resources for the current phase:

| Phase | Additional reading | Deliverable / boundary |
| --- | --- | --- |
| Overall planning | None | Agreed requirements, module-level approach, step boundaries |
| Step planning | None | PR scopes, dependencies, integration checkpoints and adversarial criteria |
| PR design / freeze | [PR requirements](prompts/pr-design-requirements.md); [test rules](prompts/test-ci-gate-rules.md); the project-specific contract in [working rules](prompts/implementation-working-rules.md) | Audited commit plan; user-approved frozen design and execution contract |
| Execute / resume | Full [working rules](prompts/implementation-working-rules.md) and [test rules](prompts/test-ci-gate-rules.md); filled contract; current PR design in full | Implement, validate, review, commit, and iterate through authorized PR/CI work |
| Operator review / merge | Working rules §§21–22; current PR design and exact-head evidence | Review-ready handoff; merge only with explicit operator authorization |
| After merge | Confirmed merge result; current PR, step, and overall documents | Update PR → step → overall; detail the immediate next PR |
| Hook design / integration | [hook contract](references/hook-contract.md); [platform notes](references/platforms.md) | A host-specific implementation only when requested; this package contains the contract only |

The original long prompts are deliberately preserved. Do not replace them with this entrypoint or a summary during execution. Resolve relative resource links against this skill directory, not the target repository.

## Essential operating rules

1. Audit real source, callers, tests, and relevant evidence before specifying file/function-level work. Do not invent repository structure.
2. Plan overall → step → PR. If a step needs one PR, expand the step document in place into the PR design; keep one authority for that work.
3. Every PR supplies a meaningful integration checkpoint. Each planned commit tracks implementation, deterministic validation, and LLM logic review separately with `[ ]` / `[x]` and evidence.
4. Require a user-approved `DESIGN FROZEN` header and an authorized implementation contract before starting implementation. Freeze scope, invariants, and acceptance; keep progress, evidence, and bounded discoveries live.
5. Start each new PR in a fresh implementation session. Resume after compaction as the same PR. Recover repository/process truth and re-read the current PR design and execution rules before editing.
6. Within the approved contract, investigate, implement, run sufficient validation, review, update the ledger, and create semantic commits autonomously. Commit inspection is a checkpoint, not a request for approval.
7. Audit uncertainty before asking. Resolve bounded details and ordinary failures autonomously. Record departures immediately. Escalate material changes or work outside existing authorization with concrete evidence and a proposed next step.
8. Respect test ownership and the approved cost envelope. Real Gates require real evidence. CI evidence must match the exact final PR head; do not repeat expensive full suites without an independent reason.
9. Continue authorized execution until the PR is ready for operator review, including CI repair when needed. Present the complete handoff and retain the explicit merge-approval boundary.
10. After confirmed merge, update progress and implications in the step and overall documents. Detail one step ahead; do not begin the next PR in the old implementation context.

## Authority and packaging boundaries

The filled, approved project contract specializes these reusable rules. User instructions and existing authorization control task scope. Repository reality establishes what exists; it does not authorize changing frozen intent. A lower-level document or stale handoff cannot silently override a binding invariant.

`SIDERIUS`, `shuffle`, `file_order`, Gate labels, tool names, and scientific examples in the prompts retain their source wording. Apply them where relevant using [adaptation.md](references/adaptation.md); do not create those systems in an unrelated project.

Hook enforcement is **specified, not installed**. Do not claim that freeze, merge, or compaction guards are active. A missing hook does not block work the user has authorized in this instruction-only edition; follow the same checks procedurally and report the enforcement status accurately.

For the human explanation and interaction examples, use [README.md](README.md). It is not required reading during routine execution.
