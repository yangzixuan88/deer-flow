# R240-2 Intent / Mode Contract Draft

Status: design draft, not implemented.
Root: `E:\OpenClaw-Base\deerflow`
Scope: read-only inspection plus report/schema generation under `migration_reports\foundation_audit`.

## 1. Main Calibration

This round verified the current intent and mode entry points from code, not from blueprint assumptions. The present system is not a single-router architecture. It is a multi-chain system with M01, M04, RTCM, DeerFlow Harness, Gateway/Channels, and frontend thread state all able to influence execution routing.

Final design judgment: B. Mode entry is mostly clear, but Context Contract must be normalized before implementing a Mode Router. Direct implementation now would risk mixing `sessionId`, `thread_id`, `task_id`, `workflow_id`, `rtcm_session_id`, and governance trace state.

## 2. Current Intent / Mode Entry Inventory

Detected 10 entry families:

1. `backend/src/domain/m01/intent_classifier.ts` - `IntentClassifier.classify(input)` maps requests to `direct`, `clarify`, or `orchestrate`.
2. `backend/src/domain/m01/intent_classifier.ts` - `IntentClassifier.needsRTCM(input)` detects explicit or suggested RTCM triggers.
3. `backend/src/domain/m01/orchestrator.ts` - `Orchestrator.execute(request)` checks active RTCM interception before normal classification.
4. `backend/src/domain/m01/dag_planner.ts` - M01 DAG planning maps orchestration nodes to M04 `SystemType`.
5. `backend/src/domain/m04/coordinator.ts` - `Coordinator.execute(...)` dispatches by `SystemType`.
6. `backend/src/domain/m04/skill_router.ts` and `skill_loader.ts` - skill-level routing can select capability paths beneath M04.
7. `backend/src/domain/m11/*` - M11 operation classification and executor adapters influence web, desktop, CLI, Claude Code, Lark, and runtime execution paths.
8. `backend/src/rtcm/rtcm_main_agent_handoff.ts`, `rtcm_entry_adapter.ts`, `rtcm_user_intervention.ts` - RTCM has its own trigger, intervention, handoff, and state flow.
9. `backend/app/gateway/routers/thread_runs.py` and `backend/app/gateway/services.py` - LangGraph-compatible thread/run API starts DeerFlow runs directly.
10. `backend/app/channels/message_bus.py`, `backend/app/channels/manager.py`, and `frontend/src/core/threads/hooks.ts` - channel and frontend thread paths perform chat/command/run submission without a unified Mode Contract.

## 3. Five Core Modes

Search mode: partially represented by M01 suggested `SystemType.SEARCH`, M04 `SearchAdapter`, `SearchEngine`, and coordinator tests. It is not a top-level M01 route; it is embedded under orchestration.

Task mode: represented by M04 `SystemType.TASK`, `Task`, `TaskDAG`, and task status models. It competes with M01 DAG orchestration and DeerFlow thread/run execution.

Workflow mode: represented by M04 `SystemType.WORKFLOW`, unified workflow builder/executor/registry, N8N/Dify engines, and workflow checkpoints. It is not globally distinguished from task at the Gateway/frontend entry.

Autonomous agent mode: represented by DeerFlow Harness `DeerFlowClient`, LangGraph runs, lead agent, subagent configuration, tools, middleware, and thread context. It can be reached independently through Gateway and channels, not only through M01.

Roundtable mode: represented by RTCM modules, M01 `needsRTCM`, active-session interception, dossier writer, round orchestrator, intervention, follow-up, sign-off, Feishu adapter, and `.deerflow/rtcm` artifacts. It lacks a first-class M01 route enum and M04 `SystemType`.

## 4. Entry Contention and Conflicts

M01 vs M04: M01 owns `IntentRoute` and DeerFlow/local fallback, while M04 owns richer `SystemType`. Search/task/workflow are not selected as M01 routes; they are pushed down into M04 or DAG nodes.

M01 vs RTCM: M01 can intercept active RTCM sessions and trigger RTCM before normal routing, but returns `IntentRoute.ORCHESTRATION` rather than a distinct roundtable mode.

M04 vs DeerFlow: local M01 fallback uses M04, but DeerFlow delegation bypasses M04. Gateway and channels also invoke DeerFlow runs directly.

Gateway/frontend vs backend domain: frontend `AgentThreadContext` and Gateway `RunCreateRequest.context` carry model, plan mode, subagent, and agent fields but not unified mode decisions.

Feishu/channel vs normal chat: channel messages classify `CHAT` vs `COMMAND`, resolve assistant/session settings, and dispatch to LangGraph runs. This precedes any M01/M04 mode decision.

## 5. ModeRequest Schema Draft

Generated: `R240-2_ModeRequest.schema.json`

Required fields: `request_id`, `session_id`, `channel`, `raw_input`, `created_at`.

Core fields: `user_id`, `attachments`, `files`, `links`, `current_context_ref`, `memory_scope`, `requested_mode_hint`, `safety_constraints`, and `execution_permissions`.

Design intent: every frontend, channel, API, RTCM, or system-originated request should be normalized before any M01/M04/RTCM/Gateway dispatch.

## 6. ModeDecision Schema Draft

Generated: `R240-2_ModeDecision.schema.json`

Allowed `selected_mode` values:

- `search`
- `task`
- `workflow`
- `autonomous_agent`
- `roundtable`
- `direct_answer`
- `clarification`
- `governance_review`
- `mixed_mode`

Core fields: `candidate_modes`, `confidence`, `decision_reason`, `priority_rule_applied`, `needs_clarification`, `delegated_to`, `fallback_mode`, `allowed_tools`, `denied_tools`, `state_scope`, and `result_sink`.

## 7. ModeExecutionResult Schema Draft

Generated: `R240-2_ModeExecutionResult.schema.json`

Core fields: `request_id`, `selected_mode`, `executor`, `status`, `success`, `output_refs`, `memory_writes`, `asset_writes`, `governance_writes`, `tool_calls`, `errors`, `truth_track`, `created_at`, and `finished_at`.

Result sink guidance:

- frontend thread: user-visible messages, stream state, and run metadata.
- memory: only after explicit memory scope and write policy.
- asset: reusable outputs, promoted workflows, templates, or artifacts.
- governance: approvals, rollback, high-risk operations, predicted/actual outcomes.
- runtime artifact: RTCM dossiers, sandbox outputs, queue/upgrade artifacts.
- nightly review: governed outcomes, asset promotions, RTCM exports, failures.

## 8. ModePriorityRules Draft

Generated: `R240-2_ModePriorityRules.json`

Default priority order:

1. `governance_review`
2. `clarification`
3. `roundtable`
4. `autonomous_agent`
5. `workflow`
6. `task`
7. `search`
8. `direct_answer`
9. `mixed_mode`

Key conflict rules:

- Roundtable beats autonomous agent for explicit RTCM/roundtable requests, high-stakes architecture, strategy, irreversible decisions, or multi-party dissent.
- Roundtable must not steal clear low-risk execution, bounded search, direct answers, or explicit implementation commands.
- Suggested roundtable requires human confirmation.
- Workflow beats task for reusable, recurring, DAG-like, multi-system, or checkpointed work.
- Search beats direct answer when current/external/verifiable facts are needed.
- Clarification beats execution when target, permission, context, or acceptance criteria are missing.
- Governance review beats ordinary task for policy, approval, rollback, and controlled evolution.
- Explicit user mode hint wins unless blocked by safety, governance, missing context, or permissions.

## 9. Current Implementation Blockers

The main blocker is Context Contract, not Mode enum. The following identifiers are not unified:

- M01 `requestId` / `sessionId`
- frontend/Gateway `thread_id` / `run_id`
- M04 `task_id` / `workflow_id`
- RTCM `session_id` / dossier project slug
- governance trace/outcome ids
- DeerFlow checkpointer/store thread state

Roundtable mode also lacks a first-class M01 route and M04 system type, but that can be handled after context normalization.

## 10. Next Priority

Next round should define Context Contract before implementing Mode Router. The minimum target is a stable mapping between request, session, thread, run, task, workflow, RTCM session, memory scope, governance trace, and runtime artifact root.

After that, implement a minimal Mode Router as a wrapper that emits `ModeDecision` and delegates without rewriting M01/M04/RTCM internals.
