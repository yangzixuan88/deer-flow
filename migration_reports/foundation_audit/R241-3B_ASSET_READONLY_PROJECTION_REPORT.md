# R241-3B Asset Read-only Projection Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only asset registry / binding / governance / memory-candidate projection.

## 1. 修改文件清单

Added:

- `backend/app/asset/asset_projection.py`
- `backend/app/asset/test_asset_projection.py`
- `migration_reports/foundation_audit/R241-3B_ASSET_READONLY_PROJECTION_REPORT.md`
- `migration_reports/foundation_audit/R241-3B_ASSET_PROJECTION_RUNTIME_SAMPLE.json`

Modified:

- `backend/app/asset/asset_lifecycle_contract.py`
  - Refined read-only classification text extraction to avoid metadata key false positives.
  - Refined `asset_ref_id` generation to prefer stable asset/candidate/memory IDs over registry file path.

Not modified:

- `.deerflow/operation_assets/asset_registry.json`
- latest binding report / binding reports
- DPBS runtime files
- `backend/app/m11/governance_state.json`
- Memory / Prompt / RTCM / Gateway / M01 / M04 main logic

## 2. 新增 projection helper 函数

New module: `backend/app/asset/asset_projection.py`

Functions:

- `discover_asset_runtime_paths(root=None)`
- `load_asset_registry_snapshot(path=None)`
- `load_binding_report_snapshot(path=None)`
- `project_registry_assets(limit=200)`
- `project_binding_assets(limit=200)`
- `project_governance_asset_outcomes(limit=200)`
- `aggregate_asset_projection(limit=200)`
- `detect_asset_projection_risks(projection)`
- `generate_asset_projection_report(output_path=None, limit=200)`

The module reuses `asset_lifecycle_contract.py`; it does not duplicate category, lifecycle, scoring, or risk logic.

## 3. asset runtime paths discovery 结果

Discovered:

- `.deerflow/operation_assets/asset_registry.json`
- `assets/asset-index.json`
- `backend/app/m11/governance_state.json`
- `migration_reports/foundation_audit/R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json`

Missing:

- `.deerflow/operation_assets/latest_binding_report.json`

Warning:

- `path_missing:E:\OpenClaw-Base\deerflow\.deerflow\operation_assets\latest_binding_report.json`

## 4. asset registry snapshot 摘要

Registry snapshot:

```text
exists=True
asset_count=12
registry_format=dict.assets
sample_keys=[
  executor_sequence,
  id,
  instruction_pattern,
  metadata,
  name,
  steps,
  task_signature,
  task_type,
  verification_pattern,
  web_target
]
```

The registry was read only. It was not rewritten or normalized.

## 5. binding report snapshot 摘要

Binding snapshot:

```text
exists=False
record_count=0
source_path=E:\OpenClaw-Base\deerflow\.deerflow\operation_assets\latest_binding_report.json
warnings=[binding_report_missing]
```

Missing binding report is diagnostic only and not treated as a runtime failure.

## 6. governance asset outcome projection 摘要

Governance projection:

```text
scanned_count=100
asset_related_count=7
projected_count=7
by_asset_category={A5_cognitive_method: 7}
by_lifecycle_tier={candidate: 7}
warnings=[missing_score_components]
```

These records remain projections. No governance history was changed.

## 7. aggregate asset projection 摘要

Aggregate projection:

```text
total_projected=26
by_source_surface={
  registry: 12,
  binding: 0,
  governance: 7,
  memory_candidates: 7
}
by_asset_category={
  A1_tool_capability: 6,
  A5_cognitive_method: 12,
  A9_domain_knowledge_map: 2,
  unknown: 6
}
by_lifecycle_tier={candidate: 26}
candidate_count=26
formal_asset_count=12
```

Memory candidates remain candidates and were not registered as assets.

## 8. risk signals

Risk diagnostics:

```text
missing_score_components=26
unverified_asset_candidate=26
unknown_asset_category=6
binding_report_missing=1
duplicate_asset_candidate=6
formal_asset_without_verification_refs=12
memory_candidate_not_registered=7
```

These are diagnostics only. No repair, promotion, retirement, downgrade, or write was performed.

## 9. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/asset/asset_lifecycle_contract.py backend/app/asset/asset_projection.py`: PASS

Asset tests:

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py backend/app/asset/test_asset_projection.py -v`: PASS, 32 passed

Previous Memory tests:

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: PASS, 24 passed

Previous Truth/State tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: PASS, 33 passed

Gateway smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 10. 是否修改 asset runtime

No.

No changes were made to:

- `asset_registry.json`
- binding report files
- operation_assets runtime path
- DPBS runtime files
- `governance_state.json`

The only generated runtime sample is an audit report under `migration_reports/foundation_audit`.

## 11. 是否执行 promotion / elimination

No.

No asset promotion, elimination, retirement, downgrade, registration, registry write, binding write, or DPBS mutation was executed.

## 12. 当前剩余断点

- Binding report is missing at the expected runtime path.
- Six registry records remain `unknown` category under current path/field heuristics.
- All projected records are currently candidate-tier because score components and verification refs are incomplete.
- Duplicate candidate diagnostics require later review before any promotion logic.

## 13. 下一步建议

Proceed to R241-4A ModeInvocation / ModeCallGraph instrumentation:

- Keep asset projection read-only.
- Do not promote or retire assets.
- Use projected asset diagnostics as context for future ModeInvocation and ModeCallGraph instrumentation only.

## Final Judgment

A. R241-3B 成功，可进入 R241-4A ModeInvocation / ModeCallGraph instrumentation。
