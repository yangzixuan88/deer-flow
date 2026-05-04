# R241-3A Asset Lifecycle Contract Wrapper Report

Generated: 2026-04-24  
Root: `E:\OpenClaw-Base\deerflow`  
Scope: read-only AssetLifecycleContract / AssetCandidateContract projection.

## 1. 修改文件清单

Added:

- `backend/app/asset/__init__.py`
- `backend/app/asset/asset_lifecycle_contract.py`
- `backend/app/asset/test_asset_lifecycle_contract.py`
- `migration_reports/foundation_audit/R241-3A_ASSET_LIFECYCLE_CONTRACT_WRAPPER_REPORT.md`
- `migration_reports/foundation_audit/R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json`

Not modified:

- `asset_registry.json`
- binding reports
- DPBS runtime files
- `governance_state.json`
- Memory / Prompt / RTCM / Gateway / M01 / M04 main logic

## 2. AssetLifecycleRecord 字段

Implemented as dataclass:

- `asset_ref_id`
- `asset_id`
- `asset_category`
- `lifecycle_tier`
- `source_system`
- `source_type`
- `source_path`
- `source_record_ref`
- `origin_context_id`
- `governance_trace_id`
- `memory_ref_id`
- `candidate_id`
- `score`
- `score_breakdown`
- `reusable_value_signal`
- `verification_refs`
- `truth_event_refs`
- `usage_refs`
- `allowed_modes`
- `risk_level`
- `promotion_eligible`
- `elimination_eligible`
- `core_protected`
- `warnings`
- `observed_at`

## 3. A1-A9 分类实现

Implemented categories:

- `A1_tool_capability`
- `A2_external_resource`
- `A3_workflow_solution`
- `A4_execution_experience`
- `A5_cognitive_method`
- `A6_information_source_network`
- `A7_prompt_instruction`
- `A8_user_preference`
- `A9_domain_knowledge_map`
- `unknown`

Classification examples:

- tool / skill / MCP / CLI / executor -> A1
- API / source / feed / crawler / search / external -> A2
- workflow / DAG / SOP / pipeline / automation -> A3
- fix / repair / rollback / failure / verification / execution log -> A4
- method / reasoning / rubric / strategy / RTCM final_report -> A5
- evidence_ledger / source_map / citation -> A6 or A9 by semantic signal
- prompt / DSPy / GEPA / signature / fewshot -> A7
- preference / user_profile / user_rule -> A8
- graph / GraphRAG / qdrant / domain_map -> A9

## 4. 五级生命周期实现

Implemented tiers:

- `candidate`
- `Record`
- `General`
- `Available`
- `Premium`
- `Core`
- `unknown`

Projection rules:

- `score is None` -> `candidate`
- `<30` -> `Record`
- `30 <= score < 60` -> `General`
- `60 <= score < 75` -> `Available`
- `75 <= score < 90` -> `Premium`
- `>=90` -> `Core`
- `core_hint=True` -> `Core` projection with `core_requires_user_confirmation`

This is projection only. No registry write or promotion occurred.

## 5. 评分模型实现

Implemented original weights:

- frequency: 25%
- success_rate: 30%
- timeliness: 20%
- coverage: 15%
- uniqueness: 10%

If any component is missing or invalid:

- `score=None`
- missing components are listed
- `missing_score_components` warning is emitted
- no synthetic score is generated

Asset score is modeled as asset quality signal and is not execution success rate.

## 6. Memory asset candidates projection 摘要

Input: R241-2B memory projection sample.

Projection result:

```text
candidate_count=7
by_asset_category={
  A9_domain_knowledge_map: 2,
  A5_cognitive_method: 5
}
by_lifecycle_tier={
  candidate: 7
}
```

All projected memory asset candidates remain candidates. No asset was promoted or registered.

## 7. Lifecycle risk signals

Runtime sample risks:

```text
risk_count=14
risk_by_type={
  missing_score_components: 7,
  unverified_asset_candidate: 7
}
```

These risks are diagnostic only. No observation, promotion, retirement, cleanup, or governance write was executed.

## 8. 测试结果

RootGuard:

- `python scripts\root_guard.py`: PASS
- `powershell -ExecutionPolicy Bypass -File scripts\root_guard.ps1`: PASS

Compile:

- `python -m py_compile backend/app/asset/asset_lifecycle_contract.py`: PASS

Asset tests:

- `python -m pytest backend/app/asset/test_asset_lifecycle_contract.py -v`: PASS, 18 passed

Previous Memory tests:

- `python -m pytest backend/app/memory/test_memory_layer_contract.py backend/app/memory/test_memory_projection.py -v`: PASS, 24 passed

Previous Truth/State tests:

- `python -m pytest backend/app/m11/test_truth_state_contract.py backend/app/m11/test_governance_truth_projection.py backend/app/m11/test_queue_sandbox_truth_projection.py -v`: PASS, 33 passed

Gateway smoke:

- `python -m pytest backend/app/gateway/test_context_envelope_smoke.py -v`: PASS, 11 passed

## 9. 是否修改 asset registry / binding report / DPBS / governance_state

No.

The wrapper reads R241-2B projection sample and writes only the R241-3A audit sample/report under `migration_reports/foundation_audit`.

## 10. 是否执行 asset promotion / elimination

No.

No asset promotion, asset retirement, downgrade, cleanup, deletion, registry write, or DPBS mutation was executed.

## 11. 当前剩余断点

- This wrapper is not yet exposed through an API or runtime dashboard.
- Score computation requires complete score components; current memory candidates lack those fields, so they remain candidate tier.
- Verification/truth/usage references are modeled but not yet populated by an asset projection surface.
- Actual asset registry integration is intentionally deferred.

## 12. 下一步建议

Proceed to R241-3B Asset Read-only Projection 接入:

- Add read-only projection over existing asset registry / binding reports / governance asset outcomes.
- Keep all projected candidates non-mutating.
- Do not promote, retire, or modify asset records until lifecycle and verification policy are reviewed.

## Final Judgment

A. R241-3A 成功，可进入 R241-3B Asset Read-only Projection 接入。
