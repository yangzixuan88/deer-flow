# R241-2A Memory Layer Contract Wrapper Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only MemoryLayerContract / MemoryScopeContract path projection.

## 1. 修改文件清单

Added:

- `backend/app/memory/__init__.py`
- `backend/app/memory/memory_layer_contract.py`
- `backend/app/memory/test_memory_layer_contract.py`
- `migration_reports/foundation_audit/R241-2A_MEMORY_LAYER_CONTRACT_WRAPPER_REPORT.md`
- `migration_reports/foundation_audit/R241-2A_MEMORY_LAYER_RUNTIME_SAMPLE.json`

Not modified:

- `backend/.deer-flow/.openclaw/memory.json`
- `backend/.deer-flow/data/qdrant/**`
- `backend/.deer-flow/.openclaw/checkpoints.db`
- `MemoryMiddleware`
- `FileMemoryStorage`
- `QdrantStorage`
- agent memory read/write paths

## 2. MemoryLayerRecord 字段

Implemented as a dataclass in `backend/app/memory/memory_layer_contract.py`.

Fields:

- `memory_ref_id`
- `memory_track`
- `memory_layer`
- `memory_scope`
- `source_system`
- `source_path`
- `content_kind`
- `associated_context_id`
- `associated_thread_id`
- `associated_asset_id`
- `governance_trace_id`
- `long_term_eligible`
- `asset_candidate_eligible`
- `retention_policy`
- `confidence`
- `evidence_refs`
- `warnings`
- `created_at`
- `observed_at`

## 3. 双轨 / 五层映射实现

Memory tracks:

- `openclaw_native`
- `deerflow_cognitive`
- `unknown`

Memory layers:

- `L1_working`
- `L2_session`
- `L3_persistent`
- `L4_knowledge_graph`
- `L5_visual_anchor`
- `unknown`

Memory scopes:

- `user_long_term`
- `project_native`
- `session`
- `thread`
- `task`
- `workflow`
- `rtcm`
- `governance`
- `asset`
- `prompt`
- `tool`
- `scratchpad`
- `system_internal`
- `visual_anchor`
- `unknown`

Retention policies:

- `ephemeral`
- `session_bound`
- `persistent`
- `graph_persistent`
- `visual_bound`
- `quarantine_candidate`
- `unknown`

## 4. Path classification 规则

Implemented functions:

- `classify_memory_path(path: str) -> dict`
- `classify_memory_artifact(path: str, metadata: dict | None = None) -> dict`
- `scan_memory_artifacts(root: str | None = None, max_files: int = 500) -> dict`
- `summarize_memory_layer_contract(records: list[dict]) -> dict`

Path rules:

- `MEMORY.md`, `AGENTS.md`, `boulder.json` -> `openclaw_native / L3_persistent / project_native`
- `backend/.deer-flow/.openclaw/memory.json` -> `deerflow_cognitive / L3_persistent / user_long_term`
- `backend/.deer-flow/data/qdrant/**` -> `deerflow_cognitive / L4_knowledge_graph / graph_persistent`
- `checkpoints.db` -> `deerflow_cognitive / L2_session / thread`, not long-term
- RTCM `council_log` -> `L2_session / rtcm`, not long-term
- RTCM `final_report` -> `L3_persistent / rtcm`, asset candidate eligible
- RTCM `evidence_ledger` -> `L4_knowledge_graph / governance`, asset candidate eligible
- screenshot / visual / Midscene / UI-TARS image artifacts -> `L5_visual_anchor / visual_anchor`
- scratchpad -> `L1_working / scratchpad`, not long-term
- raw governance outcome artifacts -> not long-term, not asset candidate
- unknown artifacts -> `unknown` with warning

## 5. long_term_eligible 规则

Allowed long-term candidates:

- `L3_persistent`
- `L4_knowledge_graph`
- verified or summarized RTCM `final_report`
- stable user/project native rules
- knowledge graph style artifacts

Explicitly not direct long-term:

- `L1_working`
- scratchpad
- `council_log`
- raw tool errors
- raw governance outcomes
- checkpoint state
- unverified single-run facts
- secrets / API keys

## 6. asset_candidate_eligible 规则

Allowed asset candidates:

- RTCM `final_report`
- RTCM `evidence_ledger` / reusable knowledge-map candidates
- verified task experience summaries
- prompt optimization candidates
- workflow patterns
- tool usage patterns

Explicitly not direct assets:

- raw memory fact
- raw conversation
- scratchpad
- `council_log`
- checkpoint
- unverified Qdrant point
- raw governance outcome

## 7. 只读 runtime sample 摘要

Generated:

```text
migration_reports/foundation_audit/R241-2A_MEMORY_LAYER_RUNTIME_SAMPLE.json
```

Sample content policy:

```text
paths and classifications only; no memory content included
```

Runtime sample summary with `max_files=300`:

```text
scanned_count=300
classified_count=245
by_track={"deerflow_cognitive": 245, "unknown": 55}
by_layer={"L2_session": 238, "L4_knowledge_graph": 2, "L3_persistent": 5, "unknown": 55}
by_scope={"thread": 24, "rtcm": 219, "governance": 2, "unknown": 55}
long_term_eligible_count=7
asset_candidate_eligible_count=7
warnings=[
  max_files_reached:300,
  checkpoint_not_long_term_memory,
  council_log_not_long_term_memory,
  unknown_memory_artifact
]
```

The sample hit the configured scan limit and mostly covered DeerFlow cognitive / RTCM / checkpoint / Qdrant artifacts. OpenClaw native classification is covered by unit tests and path rules.

## 8. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/memory/memory_layer_contract.py`: PASS

Memory tests:

- `python -m pytest backend/app/memory/test_memory_layer_contract.py -v`: PASS, 12 passed

Previous Truth/State tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: PASS, 33 passed

Existing gateway smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 9. 是否修改 memory.json / Qdrant / SQLite / checkpoints

No.

The implementation only classifies paths and metadata. It does not open large memory content, does not mutate memory files, and does not write runtime state.

## 10. 是否改变 MemoryMiddleware / agent memory 逻辑

No.

No changes were made to:

- MemoryMiddleware
- FileMemoryStorage
- QdrantStorage
- DeerFlow agent memory updater
- memory read/write strategy

## 11. 当前剩余断点

- This wrapper is not yet integrated into any Gateway/API or runtime report surface.
- Runtime sample is bounded by `max_files=300`; it is representative, not exhaustive.
- Content-based classification is intentionally deferred; this round only uses path and metadata.
- Visual anchor runtime artifacts were not present in the sample but are covered by path rules and tests.

## 12. 下一步建议

Proceed to R241-2B Memory Read-only Projection 接入:

- Add read-only projection helper over known memory artifact roots.
- Keep runtime memory files untouched.
- Use MemoryLayerRecord only as diagnostic/projection output.
- Do not implement memory cleanup, memory write policies, or asset promotion yet.

## Final Judgment

A. R241-2A 成功，可进入 R241-2B Memory Read-only Projection 接入。
