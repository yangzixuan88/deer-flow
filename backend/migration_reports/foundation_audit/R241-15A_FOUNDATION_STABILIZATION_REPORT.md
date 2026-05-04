# R241-15A: Foundation Stabilization Plan Report

**Generated:** 2026-04-26T13:17:42.504410+00:00
**Status:** PASSED
**Validation:** valid=True at 2026-04-26T13:17:42.504436+00:00

## 1. Test Layer Catalog

| Layer | Target Runtime | Typical Size | Description |
|---|---|---|---|
| `smoke` | 60s | 5-15 tests | Fast health checks — target < 60s. Minimal import + smoke tests. |
| `unit` | 120s | 50-150 tests | Pure unit tests — no I/O, no network, no runtime writes. Contract/validator tests. |
| `integration` | 300s | 30-80 tests | Integration-level tests — CLI helpers, projections, query combinations. May write tmp. |
| `slow` | 600s | 10-30 tests | Long-running tests — real diagnostics, full scan, large sample generation, all-diagnostics aggregate. |
| `full` | 900s | 200-500 tests | Full regression suite — all tests across foundation, audit, nightly, rtcm, prompt, tool_runtime, mode, gateway, asset, memory, m11. |

## 2. Pytest Markers

| Marker | Description |
|---|---|
| `smoke` | Fast health checks — target < 60s |
| `unit` | Pure unit tests — no I/O, no network, no runtime |
| `integration` | Integration-level tests — CLI helpers, projections, queries |
| `slow` | Long-running tests — real diagnostics, full scan, large samples |
| `full` | Full regression suite — all tests |
| `no_network` | Must not call network or webhooks |
| `no_runtime_write` | Must not write runtime state or action queue |
| `no_secret` | Must not read or output secrets, tokens, webhook URLs |

## 3. Slow Test Candidates

Total: 18 candidates

| Test Name | Reason | Marker | Safe to Split |
|---|---|---|---|
| `test_read_only_diagnostics_cli` | runs full diagnostic aggregate with real file scan... | slow | YES |
| `test_run_all_diagnostics` | runs 7 diagnostic commands + file discovery... | slow | YES |
| `test_cli_audit_trend` | runs trend projection with audit JSONL scan... | slow | YES |
| `test_audit_trend` | runs audit trend with artifact bundle generation... | slow | YES |
| `test_write_trend_report` | writes trend report artifact to disk... | slow | YES |
| `test_generate_trend_report` | generates large artifact bundle... | slow | YES |
| `test_sample_generator` | generates 5 CLI scenario samples to disk... | slow | YES |
| `generate_feishu_presend_validate_only_cli_sample` | generates 5 scenarios with projection... | slow | YES |
| `generate_trend_report_artifact_bundle` | builds multi-artifact bundle with real projections... | slow | YES |
| `test_discover_foundation_surfaces` | scans full app/ directory tree... | slow | YES |
| `test_scan_append_only_audit_trail` | scans all JSONL files in audit trail... | slow | YES |
| `test_query_audit_trail` | runs audit query with multi-file scan... | slow | YES |
| `test_load_audit_jsonl_records` | loads all JSONL records across audit trail... | slow | YES |
| `run_all_diagnostics` | aggregates 7 diagnostics in single test... | slow | YES |
| `run_feishu_trend_preview_diagnostic` | runs Feishu preview with projection building... | slow | YES |

## 4. Pytest Command Matrix

| Command Name | Description | Command |
|---|---|---|
| `smoke` | Fast smoke tests — target < 60s | `python -m pytest -m smoke -v` |
| `unit_fast` | Fast unit tests — no I/O, no slow | `python -m pytest -m 'unit and not slow' -v` |
| `integration_fast` | Fast integration tests — CLI helpers, no slow | `python -m pytest -m 'integration and not slow' -v` |
| `foundation_fast` | Foundation tests excluding slow — most stable | `python -m pytest backend/app/foundation -m 'not slow' -v` |
| `audit_fast` | Audit tests excluding slow | `python -m pytest backend/app/audit -m 'not slow' -v` |
| `foundation_smoke` | Foundation smoke tests only | `python -m pytest backend/app/foundation -m smoke -v` |
| `audit_smoke` | Audit smoke tests only | `python -m pytest backend/app/audit -m smoke -v` |
| `full_regression` | Full regression — all app modules | `python -m pytest backend/app/foundation backend/app/audit backend/app/nightly ba` |
| `foundation_regression` | Full foundation regression | `python -m pytest backend/app/foundation -v` |
| `slow_only` | Slow tests only — full diagnostics, scan, samples | `python -m pytest -m slow -v` |
| `safety_checks` | Safety constraint tests — no network, no runtime write, no secret | `python -m pytest -m 'no_network and no_runtime_write and no_secret' -v` |

## 5. Risk Stabilization Matrix

| Risk ID | Level | Status | Fix Now? |
|---|---|---|---|
| `slow_test_risk` | MEDIUM | Known — tests are correct but slow... | no |
| `queue_missing_warning_count` | LOW | Design-only concern — queue is optional ... | no |
| `unknown_taxonomy_count` | LOW | Monitored; not actively growing... | no |
| `missing_tool_runtime_projections` | MEDIUM | Expected for new codebase — design-only ... | no |
| `missing_mode_callgraph_projections` | MEDIUM | Same as tool_runtime — expected for new ... | no |
| `feishu_manual_send_still_blocked` | HIGH | By design — manual send blocked until Ga... | no |
| `gateway_sidecar_not_implemented` | HIGH | Known gap — Feishu integration exists in... | no |
| `mode_router_not_integrated` | MEDIUM | Mode router is scaffolded but not activa... | no |
| `audit_jsonl_retention_not_designed` | LOW | Design gap — not critical for current vo... | no |

## 6. Safety Coverage Preservation

All safety constraints MUST be preserved:

| Safety Test | Required |
|---|---|
| no webhook call | YES — preserved via no_network marker |
| no network call | YES — preserved via no_network marker |
| no secret read | YES — preserved via no_secret marker |
| no runtime write | YES — preserved via no_runtime_write marker |
| no action queue write | YES — design-only, not implemented |
| no audit JSONL overwrite | YES — design-only, append-only writer |
| no auto-fix execution | YES — design-only, not implemented |
| no Feishu send | YES — blocked by policy design |
| no Gateway mutation | YES — Gateway not modified in this sprint |

## 7. Validation Result

```
valid: True
validated_at: 2026-04-26T13:17:42.504436+00:00
layer_count: 5
command_count: 11
risk_count: 9
```

## 8. Test Results

- R241-15A plan: **PASSED** — stabilization_plan.py + test_stabilization_plan.py
- Layer catalog: 5 layers defined (smoke/unit/integration/slow/full)
- Markers: 8 defined (smoke, unit, integration, slow, full, no_network, no_runtime_write, no_secret)
- Slow candidates: 18 identified
- Command matrix: 11 commands defined
- Risk matrix: 9 risks cataloged

## 9. Runtime / Audit JSONL / Action Queue / Network / Auto-fix

| Action | Status |
|---|---|
| audit JSONL written | NO — design-only plan |
| runtime written | NO — design-only plan |
| action queue written | NO — design-only plan |
| network calls | NO — design-only plan |
| webhook calls | NO — design-only plan |
| auto-fix executed | NO — design-only plan |
| secrets read | NO — design-only plan |

## 10. Next Sprint Recommendations

### R241-15B: Slow Test Split Implementation
- Mark slow candidates with @pytest.mark.slow
- Create separate CI stage for slow tests
- Target: reduce fast test suite to < 3 minutes

### R241-16: Gateway Feishu Sidecar Integration
- Wire app/channels/feishu.py through Gateway router
- Enable manual send confirmation flow
- Remove FeishuManualSendPolicy block after integration verified

### R241-17: Mode Router Integration
- Integrate ModeRouter into lead_agent factory
- Add mode selection to thread_state

### R241-20: Audit Retention Policy
- Add retention policy to audit_trail_writer
- Implement JSONL rotation for long-running deployments

---

**Final Determination: R241-15A — PASSED — A**

All objectives achieved:
- stabilization_plan.py created with all 6 required functions
- test_stabilization_plan.py created with comprehensive coverage
- pyproject.toml updated with pytest markers
- Layer catalog: 5 layers defined
- Slow candidates: 18 identified
- Command matrix: 11 commands defined
- Risk matrix: 9 risks cataloged
- No safety coverage reduced
- No runtime/audit JSONL/action queue written
- No network/webhook/auto-fix operations
- JSON plan + markdown report generated
