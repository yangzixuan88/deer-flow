# R146: MCP Credential / Runtime Repair Plan

## Status: PASSED

## Preceded By: R145
## Proceeding To: R147A_MCP_CONFIG_SANITIZE_AND_RUNTIME_HEALTH

## Pressure: XXL

---

## Summary

R146 is a read-only planning phase (no code execution, no model calls, no MCP startup) for MCP credential and runtime repair. The goal is to map the current MCP inventory, check credential presence, identify config debt, and design a repair strategy for R147.

**Key findings:**
- 3 MCP servers enabled: Tavily (key-in-URL + 405 risk), Exa (missing credentials), Lark (ready)
- 3 MCP servers disabled: Pinecone, cloud_run, chrome_devtools
- Tavily key embedded in URL; 405 documented in config
- Exa: EXA_API_KEY missing from environment; server would fail at runtime
- Lark: credentials present, stdio — easiest to probe first
- MultiServerMCPClient has no per-server isolation — single failure blocks all tools
- Recommended strategy: disable all → verify baseline → enable lark → probe → then tavily → then exa

---

## LANE 0: Pressure Assessment

| Check | Result |
|---|---|
| previous_phase | R145 |
| current_phase | R146 |
| recommended_pressure | XXL |
| reason | Internal tool-call gate passed; plan MCP credential/runtime repair without starting external MCP |

---

## LANE 1: Workspace / Dirty Guard

| Check | Result |
|---|---|
| workspace_dirty | true |
| dirty_files_count | 412 |
| modified_files_count | 3 |
| untracked_files_count | 409 |
| unexpected_production_dirty_files | [] |
| safe_to_continue | true |

**Dirty file breakdown:**
- 3 modified: `.gitignore`, R142C patch files (thread_meta `__init__.py`, `sql.py`)
- 409 untracked: staging files, temp harnesses, app modules, test scripts, workspace files
- No unexpected production dirty files

---

## LANE 2: MCP Inventory

**Config source**: `backend/extensions_config.json`

| Server | Enabled | Transport | Command/URL | Credential Env | Risk |
|---|---|---|---|---|---|
| tavily | ✅ | SSE | `https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-dev-***` | TAVILY_API_KEY | HIGH |
| exa | ✅ | stdio | `npx.cmd -y exa-mcp` | EXA_API_KEY | HIGH |
| lark | ✅ | stdio | `pnpm.cmd dlx @larksuiteoapi/lark-mcp mcp -a $LARK_APP_ID -s $LARK_APP_SECRET` | LARK_APP_ID, LARK_APP_SECRET | HIGH |
| pinecone | ❌ | stdio | `npx.cmd -y @pinecone-database/mcp-server` | PINECONE_API_KEY | LOW |
| cloud_run | ❌ | stdio | `npx.cmd -y @googlecloud/cloud-run-mcp` | — | LOW |
| chrome_devtools | ❌ | stdio | `npx.cmd -y @vincit/chrome-devtools-mcp` | — | LOW |

**Enabled**: 3 servers | **Disabled**: 3 servers | **Total**: 6

---

## LANE 3: Credential Presence Check

**Environment source**: `backend/.env`

| Server | Env Var | Status | Config Status | Secret Printed |
|---|---|---|---|---|
| tavily | TAVILY_API_KEY | PRESENT | Key also in URL | NO |
| exa | EXA_API_KEY | MISSING | Hardcoded in config | NO |
| lark | LARK_APP_ID | PRESENT | From .env | NO |
| lark | LARK_APP_SECRET | PRESENT | From .env | NO |
| pinecone | PINECONE_API_KEY | MISSING | Empty in config | NO |

---

## LANE 4: Tavily Config Debt Analysis

| Property | Value |
|---|---|
| key_embedded_in_url | true |
| URL | `https://mcp.tavily.com/mcp/?tavilyApiKey=tvly-dev-***` |
| 405 risk documented | YES — config description explicitly states "MCP endpoint returns 405" |
| transport | SSE |
| env key matches URL key | YES |
| recommended_fix | Remove key from URL; use Authorization header with Bearer ${TAVILY_API_KEY} |

**Config migration path**: Change `url` to `https://mcp.tavily.com/mcp` (no query params); set `Authorization: Bearer ${TAVILY_API_KEY}` in headers via config.

**Risk if not fixed**: Key exposure in logs/URL; 405 errors blocking Tavily MCP at runtime.

---

## LANE 5: Exa / Lark Credential Gap Analysis

| Server | Gap | Would Fail at Runtime? | Should Disable? |
|---|---|---|---|
| exa | EXA_API_KEY MISSING from environment; hardcoded in config | ✅ Yes — npx spawn fails with auth error | ✅ Yes (R147A) |
| lark | No gap — LARK_APP_ID + LARK_APP_SECRET both PRESENT | ❌ No — env vars resolve via placeholders | ❌ No — ready to probe |

**Aggregate**: Missing credentials block runtime for exa. Lark is credential-ready.

---

## LANE 6: Runtime Init Risk Mapping

| Property | Value |
|---|---|
| single_server_failure_affects_all | ✅ true |
| isolation_possible | ❌ false |
| langchain_mcp_adapters_behavior | `MultiServerMCPClient.get_tools()` calls all servers; one failure can block entire call |
| timeout_configured | ❌ false |
| failure_modes | tavily: 405 error; exa: missing key; lark: should succeed |

**Probe order recommended**: lark → tavily → exa

---

## LANE 7: Repair Strategy Options

| Option | Name | Speed | Risk | Recommended |
|---|---|---|---|---|
| A | Disable missing-credential servers | fast | low | ❌ |
| B | User provides missing credentials | slow | medium | ❌ |
| C | Tavily-only first (fix URL + 405) | medium | medium | ❌ |
| D | MCP all-disabled → per-server enable | fast | lowest | ✅ |
| E | Composite: disable exa + sanitize tavily URL | medium | low | ❌ |

**Recommended: Option D** — Start from all-disabled baseline, verify agent works without MCP, then enable servers one at a time with health probes.

**Practical composite (R147A)**: Option D + E combined — disable exa, sanitize tavily URL, keep lark enabled; probe lark first.

---

## LANE 8: R147 Authorization Package

**Recommended phase sequence**:
1. `R147A_MCP_CONFIG_SANITIZE_AND_RUNTIME_HEALTH` — Config sanitize (disable exa, fix tavily URL) + smoke test
2. `R147B_MCP_LARK_RUNTIME_HEALTH_PROBE` — Lark isolated probe (credentials present, stdio)
3. `R147C_MCP_TAVILY_RUNTIME_HEALTH_PROBE` — Tavily probe (URL fixed, 405 investigated)
4. `R147D_MCP_EXA_ENABLE` — Exa re-enable (after user provides EXA_API_KEY)

**R147A authorization**:
- `patch_required`: true
- `files_allowed`: `backend/extensions_config.json` (sanitize tavily URL + disable exa)
- `files_forbidden`: All Python files in `packages/harness/deerflow/mcp/`, `tools/`, `agents/`
- `runtime_probe_allowed`: true (MCP server health probe only; no external tool calls)
- `external_tool_call_allowed`: false

**Validation plan**:
1. Disable exa in extensions_config.json
2. Remove `?tavilyApiKey=...` from tavily URL in extensions_config.json
3. Keep lark enabled
4. Create smoke harness: `create_deerflow_agent(tools=[])` — verify no MCP init
5. Enable only lark; run single lark health probe (no tool calls)
6. Verify no 405 on tavily after URL fix
7. If probe passes, enable tavily; if 405 persists, investigate

**Rollback**: Restore extensions_config.json from git; R146 snapshot preserved in migration_reports.

---

## LANE 9: MCP Readiness Matrix

| Server | Config Ready | Credentials Ready | Probe Ready | Tool Smoke Ready | Blocker |
|---|---|---|---|---|---|
| tavily | ❌ | ✅ | ❌ | ❌ | Key in URL + 405 documented |
| exa | ❌ | ❌ | ❌ | ❌ | EXA_API_KEY missing |
| lark | ✅ | ✅ | ✅ | ❌ | None — probe first |
| pinecone | ✅ | ❌ | ❌ | ❌ | Disabled |
| cloud_run | ✅ | ❌ | ❌ | ❌ | Disabled |
| chrome_devtools | ✅ | ❌ | ❌ | ❌ | Disabled |

**Lark is the first probe target** — it has credentials, uses stdio (easiest to validate), and is already enabled.

---

## LANE 10: Unknown Registry Updates

| ID | Description | Priority | Fix |
|---|---|---|---|
| U-tavily-url-key-debt | Key embedded in URL; should use Authorization header | high | R147A: remove from URL |
| U-tavily-405-endpoint | Config notes "MCP endpoint returns 405" | high | R147A: investigate 405 root cause |
| U-exa-credential-gap | EXA_API_KEY missing; server would fail at runtime | high | R147A: disable; R147D: re-enable after user provides key |
| U-lark-credential-ready | LARK_APP_ID + LARK_APP_SECRET both present | low | R147B: probe lark first |
| U-mcp-server-isolation | MultiServerMCPClient has no per-server isolation | high | Sequential enable + probe strategy |
| U-mcp-runtime-probe-order | Probe order: lark → tavily → exa | medium | R147B, R147A, R147D |
| U-mcp-config-sanitize | extensions_config.json needs sanitization | high | R147A authorized |

---

## R146 Classification: PASSED

| Metric | Value |
|---|---|
| code_modified | false |
| db_written | false |
| jsonl_written | false |
| gateway_started | false |
| model_api_called | false |
| mcp_runtime_called | false |
| external_tool_called | false |
| push_executed | false |
| merge_executed | false |
| blockers_preserved | true |
| safety_violations | [] |

**Recommended next phase**: `R147A_MCP_CONFIG_SANITIZE_AND_RUNTIME_HEALTH`

---

## R146 EXECUTION SUCCESS