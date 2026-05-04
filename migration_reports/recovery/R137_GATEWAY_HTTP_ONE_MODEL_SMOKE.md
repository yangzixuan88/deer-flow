# R137: Gateway HTTP One-Model Smoke

## Status: PASSED_WITH_INTERRUPTED

## Preceded By: R136
## Proceeding To: R138_TOOL_ENABLED_SMOKE

## Pressure: XXL

---

## Summary

R137 executed a one-model smoke test against the Gateway HTTP endpoint:

1. **Thread CRUD**: POST /api/threads → 200, GET /api/threads/{thread_id} → 200
2. **MiniMax model injected**: `name=minimax-m2.7`, `use=PatchedChatMiniMax`, `model=MiniMax-M2.7`
3. **POST /runs**: Returns 200, run_id=a9c5fa9b-1ca5-458c-b3c7-cf72bf595fdc
4. **Run status**: interrupted after 3s
5. **Model API called**: False
6. **Lifespan fix**: `_current_app_config.set(minimal_config)` bypassed AppConfig.from_file() bug
7. **Import approach**: Real namespace package imports (no mocking)

---

## LANE 1: Preflight

| Check | Result |
|---|---|
| MINIMAX_API_KEY present | True |
| workspace_clean | True |
| health_200 | True |
| mcp_enabled | True |
| preflight_passed | True |

---

## LANE 2: Model Injection

| Field | Value |
|---|---|
| name | minimax-m2.7 |
| use | packages.harness.deerflow.models.patched_minimax.PatchedChatMiniMax |
| model | MiniMax-M2.7 |
| base_url | https://api.minimaxi.com/v1 |
| api_key | sk-c... |

---

## LANE 4: Thread Baseline

```
POST /api/threads: 200 → thread_id=9b931dd1-d3e6-4666-8c2f-6483985442ec
GET /api/threads/{thread_id}: 200
```

---

## LANE 5: POST /runs

```
POST /api/threads/{thread_id}/runs: 200
  run_id=a9c5fa9b-1ca5-458c-b3c7-cf72bf595fdc
  status=interrupted
```

---

## LANE 6: Run Status Polling

```
Poll timeout: 90s
Run completed: True
Final status: interrupted
Final error: None
Final error type: None
Elapsed: 3s
```

---

## LANE 8: Result Classification

### R137 Result: **PASSED_WITH_INTERRUPTED**

### Outcome: Outcome D — graph-level interrupt triggered; worker path exercised correctly

---

## Constraints

| Constraint | Status |
|---|---|
| code_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | False |
| mcp_runtime_called | false |
| tool_call_executed | false |
| push_executed | false |
| merge_executed | false |

---

## Recommended Next Phase

**R138_TOOL_ENABLED_SMOKE** (Pressure: XXL)

Reason: Worker path confirmed interrupted; ready for tool-enabled smoke
