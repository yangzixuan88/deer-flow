# R241-2B Memory Read-only Projection Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only memory projection surface over MemoryLayerContract.

## 1. 修改文件清单

Added:

- `backend/app/memory/memory_projection.py`
- `backend/app/memory/test_memory_projection.py`
- `migration_reports/foundation_audit/R241-2B_MEMORY_READONLY_PROJECTION_REPORT.md`
- `migration_reports/foundation_audit/R241-2B_MEMORY_PROJECTION_RUNTIME_SAMPLE.json`

Not modified:

- `backend/.deer-flow/.openclaw/memory.json`
- Qdrant / SQLite / vector artifacts
- `checkpoints.db`
- RTCM dossiers
- MemoryMiddleware
- FileMemoryStorage / QdrantStorage
- agent memory read/write logic

## 2. 新增 projection helper 函数

New module: `backend/app/memory/memory_projection.py`

Functions:

- `project_memory_artifact(path, metadata=None)`
- `project_memory_roots(root=None, max_files=500)`
- `get_long_term_memory_candidates(root=None, max_files=1000)`
- `get_memory_asset_candidates(root=None, max_files=1000)`
- `detect_memory_risk_signals(root=None, max_files=1000)`
- `generate_memory_projection_report(output_path=None, root=None, max_files=500)`

All helpers reuse `memory_layer_contract.py`. No classification logic is copied.

## 3. Memory roots projection 摘要

Runtime sample generated with `max_files=500`:

```text
scanned_count=500
classified_count=262
by_track={
  deerflow_cognitive: 256,
  openclaw_native: 6,
  unknown: 238
}
by_layer={
  L2_session: 245,
  L3_persistent: 12,
  L4_knowledge_graph: 5,
  unknown: 238
}
by_scope={
  thread: 31,
  rtcm: 219,
  governance: 3,
  project_native: 6,
  user_long_term: 1,
  system_internal: 3,
  unknown: 237
}
```

Representative records are capped at 50 and contain paths/classification only.

## 4. Long-term candidates 筛选结果

Read-only long-term candidate result:

```text
candidate_count=17
by_layer={
  L3_persistent: 12,
  L4_knowledge_graph: 5
}
by_scope={
  governance: 2,
  rtcm: 5,
  project_native: 6,
  user_long_term: 1,
  system_internal: 3
}
```

Excluded by rule:

- checkpoint
- scratchpad
- council_log
- raw governance outcome

This is candidate projection only. No consolidation or write was performed.

## 5. Asset candidates 筛选结果

Read-only memory asset candidate result:

```text
candidate_count=7
by_source_system={rtcm: 7}
by_layer={
  L3_persistent: 5,
  L4_knowledge_graph: 2
}
```

Included examples by rule:

- RTCM `final_report`
- RTCM `evidence_ledger`

Excluded by rule:

- scratchpad
- council_log
- checkpoint
- raw governance outcome
- raw memory fact

No asset promotion was performed.

## 6. Risk signals 检测结果

Read-only risk signal result:

```text
risk_count=274
risk_by_type={
  checkpoint_not_long_term_memory: 31,
  council_log_not_long_term_memory: 3,
  unknown_memory_artifact: 238,
  possible_raw_governance_memory: 1,
  max_files_reached: 1
}
```

These are diagnostics only. No cleanup, quarantine, deletion, or migration was performed.

## 7. Runtime sample 位置与摘要

Generated:

```text
migration_reports/foundation_audit/R241-2B_MEMORY_PROJECTION_RUNTIME_SAMPLE.json
```

Sample policy:

```text
paths, classifications, and summaries only; no full memory content included
```

Warnings:

- `max_files_reached:500`
- `checkpoint_not_long_term_memory`
- `council_log_not_long_term_memory`
- `unknown_memory_artifact`
- `memory_scope_agent_or_user_not_fully_proven`
- `unverified_qdrant_point_not_asset`
- `raw_governance_outcome_not_long_term_memory`

## 8. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/memory/memory_layer_contract.py backend/app/memory/memory_projection.py`: PASS

Memory tests:

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: PASS, 24 passed

Previous Truth/State tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: PASS, 33 passed

Gateway smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 9. 是否触碰 memory runtime

No.

The implementation does not modify:

- `memory.json`
- Qdrant / SQLite / vector artifacts
- `checkpoints.db`
- RTCM dossiers
- Memory runtime directories

The runtime sample is written only to `migration_reports/foundation_audit`.

## 10. 是否改变 MemoryMiddleware / agent memory 逻辑

No.

No changes were made to:

- MemoryMiddleware
- FileMemoryStorage
- QdrantStorage
- DeerFlow memory updater
- agent memory read/write policy

## 11. 当前剩余断点

- Projection is not yet exposed through Gateway/API.
- Content-aware memory classification is intentionally not implemented.
- Runtime scan hit `max_files=500`; unknown artifacts require later focused classification if needed.
- Long-term and asset candidate outputs are projections only, not approval or promotion decisions.

## 12. 下一步建议

Proceed to R241-3A Asset Lifecycle Contract Wrapper:

- Keep memory projection read-only.
- Do not promote memory artifacts to assets.
- Define AssetLifecycleRecord and AssetPromotion eligibility before any asset registry integration.

## Final Judgment

A. R241-2B 成功，可进入 R241-3A Asset Lifecycle Contract Wrapper。
