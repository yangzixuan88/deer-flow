# R240-1A Blueprint Gaps

## Scope

Root: `E:\OpenClaw-Base\deerflow`

This report separates planning_state, code_state, and runtime_state. It does not treat planning documents as runtime fact.

## blueprint_only

- Full M00-M13 ideal architecture is documented in `openclaw_project/docs/*` and `OpenClaw超级工程项目_V1_Full_Archive.md`, but several planned modules do not have equal runtime evidence.
- Hermes/OpenCLI deep integration is strongly represented in docs such as `docs/OPENCLI_INTEGRATION_PLAN.md` and `docs/hermes_opencli_deep_改造计划.md`; current code shows partial adapters/registries but not full runtime closure.
- Feishu CLI deep plan exists in `openclaw_project/docs/FEISHU_CLI深度接入计划.md`; runtime evidence exists for Feishu/RTCM, but full CLI mode is not proven as a unified main-chain capability.
- Disaster recovery playbooks and automated recovery plans exist in docs, but automated DR runtime closure was not proven in this discovery pass.
- OMO Agent Matrix / Ralph Loop / AAL sovereignty concepts exist in planning and partial code, but no single runtime state machine proves full autonomous loop closure.

## code_only

- `backend/packages/harness/deerflow/` is a substantial DeerFlow harness with agents, tools, MCP, memory, runtime, sandbox, subagents, and assets. This is larger than the OpenClaw M00-M13 documents alone.
- `backend/src/rtcm/` contains a large roundtable/council/debate system with adapters, dossier writer, Feishu integration, policy/budget/recovery/follow-up/sign-off modules. It appears later-added and not fully covered by original module docs.
- `backend/src/upgrade_center/` contains a full upgrade/evolution candidate pipeline: sampler, scorer, approval tier, sandbox planner, queue manager, report generator, runner.
- `backend/app/m11/` contains Python governance bridge, sandbox executor, queue consumer, Claude Code router, external backend selector, webhook, and adapters. This is a second runtime/governance execution plane beside TypeScript M11.
- `backend/app/gateway/routers/*` and `frontend/src/core/*` expose API/UI surfaces that are not mapped cleanly to M01/M04/M11 contracts.
- Multiple memory/prompt/tool registries exist independently: DeerFlow memory/tools, OpenClaw domain memory/prompt_engine, frontend memory API, M04 skill router, MCP tools.

## runtime_only

- `C:\Users\win\.deerflow\upgrade-center\state\experiment_queue.json` contains completed/failed sandbox validation tasks with verify/rollback paths, `predicted`, `tier`, `ltv`, `filter_result`, and execution timestamps.
- `C:\Users\win\.deerflow\upgrade-center\sandbox\verify_scripts` and `rollback_templates` contain many generated runtime scripts. Their lifecycle exceeds the static blueprint.
- `backend/app/m11/governance_state.json` contains persisted decisions and 100 outcome records.
- `C:\Users\win\.deerflow\rtcm\` contains runtime directories for sessions, dossiers, threads, interventions, exports, followups, checkpoints, telemetry, and Feishu artifacts.
- `backend/src/infrastructure/upgrade_center_result.json` exists but has malformed JSON in the sampled file, so producer/consumer robustness is uncertain.

## later_added

- Repository Root / RootGuard / root migration audit system: `scripts/root_guard.py`, `scripts/root_guard.ps1`, `migration_reports/root_migration/*`.
- RTCM roundtable/council/debate mode: `backend/src/rtcm/*`, `C:\Users\win\.deerflow\rtcm\*`.
- Upgrade Center and Sandbox validation queue: `backend/src/upgrade_center/*`, `backend/app/m11/queue_consumer.py`, `sandbox_executor.py`, `~\.deerflow\upgrade-center\*`.
- Governance bridge with outcome backflow and controlled evolution: `backend/app/m11/governance_bridge.py`, `governance_state.json`.
- Nightly watchdog queue health and upgrade backflow: `backend/src/infrastructure/watchdog.py`.
- Asset promotion and governance learning chain: `backend/app/m07`, `backend/app/m08`, governance outcome types, verify/rollback artifacts.

## missing_blueprint

- Roundtable / RTCM is a core mode in current code and runtime state, but original blueprint coverage is insufficient. It needs its own design contract.
- A unified Mode Router blueprint is missing: M01, M04, DeerFlow harness, frontend chat mode, and RTCM all participate in routing.
- Runtime artifact governance is missing: generated verify/rollback scripts, `experiment_queue.json`, governance outcomes, RTCM dossiers, and watchdog results need a lifecycle contract.
- Tool safety contract is incomplete across DeerFlow tools, MCP, M11 Executor, Claude Code, OpenCLI, Feishu/Lark, Midscene, and UI-TARS.
- Memory and prompt write/read boundaries are not fully specified across M06, DeerFlow memory, RTCM dossiers, governance records, and prompt_engine.

## conclusion

The local system exceeds the M00-M13 original module boundary. The blueprint is partially stale: it remains useful as design intent, but current Foundation Audit must include later-added runtime systems as first-class subsystems.
