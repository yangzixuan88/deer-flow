# R240-FP Foundation Optimization Master Plan

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Status: planning only; implementation is not allowed in this round.

## 1. Current Real System Map Summary

The unique repository root is `E:\OpenClaw-Base\deerflow`. Repository Root Split has been resolved, old Chinese VSCode root has been frozen, runtime old-path references are zero, unresolved conflicts are zero, RootGuard scripts have been validated, and workspace/runtime reads are rooted in deerflow.

Current OpenClaw / DeerFlow is not a single main chain. It is a multi-chain system:

| Chain | Current role |
|---|---|
| DeerFlow Harness | Active agent/runtime/memory path, thread/checkpoint artifacts, file memory and partial Qdrant |
| OpenClaw TS Domain | Domain contracts, M01/M04, memory/asset/prompt abstractions, tests and wrappers |
| Python App Governance/Runtime | Governance bridge, DPBS, sandbox executor, queue/watchdog/upgrade-center runtime artifacts |
| RTCM Roundtable | Roundtable executor path, dossiers, final reports, signoff/followup artifacts |
| Frontend / Gateway | User-facing thread/workspace/memory surfaces and channel routing |

Five major capability domains are peer domains, not mutually exclusive branches:

- Search
- Task
- Workflow
- Autonomous agent
- Roundtable

Future mode design must use `primary_mode`, `active_modes`, `ModeInvocation`, and `ModeCallGraph`. A child mode should normally return control to its parent mode unless the user explicitly switches the primary mode.

Memory is a dual-track and five-layer system:

- OpenClaw native memory: `MEMORY.md`, `AGENTS.md`, project knowledge, user-governed durable rules.
- DeerFlow cognitive memory: runtime experience, semantic recall, file memory, graph/vector memory.
- L1 Working Memory / ReMe
- L2 Session Memory / SimpleMem
- L3 Persistent Memory / MemOS
- L4 Knowledge Graph / GraphRAG + Mem0
- L5 Visual Anchor Memory / CortexaDB

Asset is a first-class reusable capability system, not a JSON registry. It has A1-A9 categories and Record / General / Available / Premium / Core lifecycle tiers. DPBS is a real operational asset sub-chain, not the whole asset system.

## 2. Approved P0 Issue List

| P0 | Status | Master-plan decision |
|---|---|---|
| P0-1 Truth / State Contract | Approved for contract planning | Define TruthEvent, StateEvent, OutcomeContract; separate execution truth, observation signal, governance signal, rtcm_truth, asset_quality_signal |
| P0-2 Memory Contract | Approved after R240-MA | Build from dual-track + L1-L5; do not model from MemoryMiddleware or Qdrant alone |
| P0-3 Mode Orchestration | Approved principle | Five modes are peer domains; use primary/active mode and call graph |
| P0-4 Asset Lifecycle | Approved after R240-MA | Build from A1-A9, five tiers, score/provenance/verification/lifecycle |
| P0-5 Autonomous Tool Runtime | Approved principle | High autonomy by default; control risk through backup, rollback, audit, review |
| P0-6 Prompt Governance | Approved principle | M09 P1-P6 precedence; SOUL.md is base identity, not highest override |
| P0-7 Mode Call Graph | Approved principle | Child mode returns to parent unless user explicitly switches primary mode |
| P0-8 Nightly Review | Approved principle | Upgrade from UC local review to full Foundation Health Review |
| P0-9 Memory / Asset deep audit | Completed | R240-MA findings are input to the master plan |

## 3. Deferred / Special Attention Items

- Do not implement Mode Router yet.
- Do not replace M01, M04, RTCM, Gateway, or DeerFlow runtime paths in one step.
- Do not mutate `memory.json`, Qdrant, SQLite, asset registry, governance state, or RTCM artifacts during planning.
- Do not promote RTCM `final_report`, governance outcome, or memory facts directly into assets without verification and scoring.
- Do not treat DPBS as complete Asset System.
- Do not treat MemoryMiddleware or Qdrant as complete Memory System.
- Runtime roots are logically under deerflow, but active artifacts still span `.deerflow` and `backend\.deer-flow`; this is a runtime contract issue, not a repository root split.

## 4. Foundation Optimization Goals

1. Create a unified foundation protocol layer across Truth/State, Context, Mode, Memory, Asset, Tool Runtime, Prompt, RTCM, and Nightly Review.
2. Preserve existing working chains first; add wrappers and contracts before replacing behavior.
3. Make every future implementation stage user-confirmed, reversible, auditable, and testable.
4. Increase autonomy by making backup, rollback, archive, RootGuard, governance, and nightly review reliable.
5. Establish common provenance IDs across `request_id`, `thread_id`, `context_id`, `asset_id`, `candidate_id`, `governance_trace_id`, and `rtcm_session_id`.

## 5. Phased Implementation Roadmap

| Phase | Name | Goal | Implementation allowed now |
|---|---|---|---|
| 0 | Root uniqueness | Completed root consolidation | No |
| 1 | Truth / State Contract | Normalize truth/state/outcome semantics | No |
| 2 | Memory Layer + Scope Contract | Define MemoryLayer, MemoryScope, policies, retention | No |
| 3 | Asset Lifecycle Contract | Define A1-A9 lifecycle, scoring, verification, retirement | No |
| 4 | Mode Orchestration Contract | Define primary/active modes and call graph | No |
| 5 | Autonomous Tool Runtime Contract | Define high-autonomy tool policy and audit events | No |
| 6 | Prompt Governance Contract | Define prompt precedence, assetization, rollback | No |
| 7 | RTCM / Roundtable Integration Contract | Bind RTCM to roundtable mode and truth/assets/governance | No |
| 8 | Nightly Foundation Health Review | Expand nightly into full-system health review | No |
| 9 | Implementation Readiness Review | Confirm contracts, migration boundaries, test strategy | No |
| 10 | Staged implementation | Execute only after all contract reviews | No |

## 6. Per-Phase Change / No-Change Rules

| Phase | Change in that phase | Explicitly not changed |
|---|---|---|
| 1 | TruthEvent, StateEvent, OutcomeContract schemas and mapping | No runtime truth rewriting |
| 2 | Memory layer/scope/read/write/retention contracts | No memory cleanup, no Qdrant mutation |
| 3 | Asset categories, lifecycle, promotion/elimination contract | No asset promotion or retirement execution |
| 4 | ModeInvocation and ModeCallGraph contract | No Mode Router replacement |
| 5 | ToolExecutionEvent, ToolPolicy, RootGuard binding rules | No destructive tool expansion without safeguards |
| 6 | PromptGovernanceContract and prompt asset rules | No production prompt replacement |
| 7 | RTCM integration contract and roundtable truth mapping | No RTCM executor replacement |
| 8 | Nightly review contract and action queue semantics | No high-risk auto-fix |
| 9 | Readiness gates and acceptance checklist | No implementation |
| 10 | Future staged implementation | Only after user confirms each stage |

## 7. Risks

- Over-centralizing too early could break working M01/M04/RTCM/DeerFlow paths.
- Treating local runtime artifacts as full design truth could shrink Memory/Asset incorrectly.
- High autonomy without rollback would create unsafe irreversible behavior.
- Prompt optimization without backup/audit could silently degrade behavior.
- Asset retirement without tier protection could lose high-value Core assets.
- Memory cleanup without quarantine could delete valid long-term knowledge.
- Nightly auto-repair without governance could cause uncontrolled changes.

## 8. Acceptance Criteria

This planning round is accepted only if:

- All five R240-FP files are generated under `migration_reports/foundation_audit`.
- `R240-FP_PHASE_ROADMAP.json` is valid JSON and all phases have `implementation_allowed: false`.
- `R240-FP_CONTRACT_INDEX.json` is valid JSON and includes all required contracts.
- P0 decision log includes P0-1 through P0-9.
- Memory and Asset R240-MA conclusions are explicitly reflected.
- High-autonomy + backup/rollback philosophy is explicitly reflected.
- Five-mode peer/call-graph model is explicitly reflected.
- No business code or runtime data is modified.

## 9. Rollback Strategy

Planning documents can be superseded by later R240-FP revisions. No code rollback is needed because no code changes are allowed in this round.

Future implementation rollback principles:

- Critical config changes require pre-change backup.
- Important file deletion must be replaced by archive/quarantine first unless explicitly confirmed.
- Prompt changes require old-version preservation and rollback metadata.
- Asset retirement requires tier-aware protection and history retention.
- Memory cleanup requires observation/quarantine before deletion.
- Tool runtime changes require ToolExecutionEvent audit trails.
- Nightly actions require risk classification and governance review for high-risk changes.

## 10. User Confirmation Points

Before implementation, the user must review and confirm:

- Truth / State event semantics and source mapping.
- Memory layer/scope/write/retention policies.
- Asset category/lifecycle/scoring/promotion/elimination rules.
- Mode orchestration and mode-call graph semantics.
- Autonomous tool risk classes and backup/rollback rules.
- Prompt precedence and prompt asset promotion rules.
- RTCM roundtable integration boundaries.
- Nightly Foundation Health Review authority and auto-action limits.
- Implementation Readiness Review checklist.

## Final Route Principle

Current round still does not start implementation. This round only generates engineering planning files. Implementation is allowed only after all contract designs are reviewed and confirmed by the user, and future implementation must be staged, reversible, auditable, and verifiable.
