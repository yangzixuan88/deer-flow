# R240-FP P0 Decision Log

Generated: 2026-04-24  
Status: planning decision record; not implementation.

## Decision Principles

- Every issue must pass user confirmation before implementation.
- Final implementation must match the user's architecture intent.
- This round only creates master planning files.
- All contract details must be settled before staged optimization begins.

## User Permission Philosophy

Confirmed for master plan:

- The system goal is to become more autonomous, stronger, more proactive, and more intelligent.
- Tool permissions should follow a high-autonomy model.
- Except for self-critical config changes, important file deletion, and irreversible high-impact operations, the system should execute as automatically as safely possible.
- Irreversible operations must have backup, rollback, archive, or recovery paths.
- The safety base for high autonomy is backup, rollback, audit, and review, not frequent user prompts.

## P0 Decisions

| P0 | Decision status | Decision |
|---|---|---|
| P0-1 Truth / State Contract | Temporarily passed | Separate predicted / actual / state / status / success / signal / outcome. `sandbox_execution_result.actual` is execution truth. Observation pool actual=0.5 is observation signal. UC approval/execution values are governance or approval signals unless mapped otherwise. RTCM signoff/final_report maps to `rtcm_truth`. Asset score maps to `asset_quality_signal`. |
| P0-2 Memory Contract | Accepted after R240-MA | Memory must use OpenClaw native + DeerFlow cognitive dual track and L1-L5. Do not model from MemoryMiddleware or Qdrant alone. Define MemoryLayerContract before ReadPolicy, WritePolicy, Scope, and Retention. |
| P0-3 Mode Orchestration | Accepted | Search, task, workflow, autonomous agent, and roundtable are peer capability domains. They can call, nest, and hand off to each other in one conversation. |
| P0-4 Asset Lifecycle | Accepted after R240-MA | Asset is first-class reusable capability, not registry JSON. Use A1-A9 and five lifecycle tiers. Asset candidates require verification, score, provenance, and lifecycle before becoming assets. |
| P0-5 Autonomous Tool Runtime | Accepted | Use high autonomy with backup/rollback/audit/review. Ordinary code edits, tests, builds, search, and file generation should generally be allowed in implementation rounds. Critical config, important deletion, and irreversible external side effects require protection. |
| P0-6 Prompt Governance | Temporarily passed | Use M09 P1-P6. P1 hard constraints are highest. User high-autonomy preference belongs to P2. SOUL.md is identity base, not highest override. GEPA/DSPy prompt products require test, backup, rollback, and audit. |
| P0-7 Mode Call Graph | Temporarily passed | Do not use single `selected_mode` as final model. Use `primary_mode`, `active_modes`, `ModeInvocation`, and `ModeCallGraph`. Child modes return to parent unless user explicitly switches primary mode. |
| P0-8 Nightly Review | Temporarily passed | Upgrade Nightly from UC local review to Foundation Health Review covering modes, tools, assets, memory, prompts, RTCM, Governance, and runtime artifacts. |
| P0-9 Memory / Asset Deep Audit | Completed | R240-MA found Memory/Asset sufficiently mapped for foundation optimization planning. |

## Deferred Implementation Rule

No P0 contract is considered implemented by this decision log. Each contract requires its own user review before any code or runtime wiring changes.
