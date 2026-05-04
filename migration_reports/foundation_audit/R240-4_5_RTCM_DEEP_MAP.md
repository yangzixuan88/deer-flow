# R240-4.5 RTCM (Roundtable Collaboration Meeting) Deep Map

## 1. RTCM Overview

**RTCM** = Roundtable Collaboration Meeting. A special session mode triggered by user keywords, where a council of AI agents collectively discuss and resolve issues.

**Key architectural property**: RTCM is a **completely independent state machine** that bypasses M01 orchestration AND M04 coordination, but **still writes governance outcomes** via Feishu API → M01 handoff.

---

## 2. RTCM Session State Machine

```
States: ACTIVE → PAUSED/WAITING_FOR_USER → ARCHIVED/FAILED
```

### 2.1 State Definitions

| State | Entry Condition | Exit Condition |
|-------|-----------------|----------------|
| `ACTIVE` | `activateRTCM()` called | User requests pause; or unrecoverable error |
| `PAUSED` / `WAITING_FOR_USER` | User sends message during active RTCM session | User resumes; or session expires (24h TTL) |
| `ARCHIVED` | Session completes successfully | — |
| `FAILED` | Unrecoverable error | — |

### 2.2 RTCM Activation Triggers

| Trigger | Keyword | Detection |
|---------|---------|-----------|
| Chinese | 开会 / 启动rtc / 圆桌会议 | `detectRTCMTrigger()` in `rtcm_main_agent_handoff.ts` |
| English | (not documented — TS-side only) | `needsRTCM()` in intent classifier |

---

## 3. RTCM Components

### 3.1 Core Components

| Component | Path | Role |
|-----------|------|------|
| `rtcm_main_agent_handoff.ts` | `backend/src/rtcm/` | Trigger detection, activation, intercept |
| `rtcm_orchestrator.ts` | `backend/src/rtcm/` | Session orchestration |
| `rtcm_session_manager.ts` | `backend/src/rtcm/` | Session lifecycle, state transitions |
| `dossier_writer.ts` | `backend/src/rtcm/` | Writes dossier artifacts |
| `rtcm_feishu_api_adapter.ts` | `backend/src/rtcm/` | Feishu card messages |
| `user_intervention_classifier.ts` | `backend/src/rtcm/` | Classifies user interventions |
| `main_agent_handoff.ts` | `backend/src/domain/m01/` | M01 calls `activateRTCM()` |

### 3.2 M01 Integration

**File**: `backend/src/domain/m01/orchestrator.ts:379`
```
handleRTCMTrigger()
  → mainAgentHandoff.activateRTCM()
  → M01 relinquishes control to RTCM
```

RTCM activation **does NOT** write governance directly. Feishu API calls flow through M01 handoff.

---

## 4. RTCM Dossier Artifacts

### 4.1 Dossier Structure

**Path**: `~/.deerflow/rtcm/dossiers/{project}/`

| File | Purpose |
|------|---------|
| `brief_report.json/md` | Executive summary |
| `council_log.json/jsonl` | All council agent contributions |
| `evidence_ledger.json` | Evidence collected during session |
| `final_report.json/md` | Final resolution report |
| `issue_cards/issue-*.json` | Individual issue records |
| `manifest.json` | Dossier manifest / index |

### 4.2 Dossier Lifecycle

```
RTCM session starts
  → DossierWriter.writeDossier() creates brief_report
  → Council agents contribute → council_log updated
  → Evidence collected → evidence_ledger updated
  → Session concludes → final_report written
  → Session ARCHIVED → dossier archived
```

### 4.3 Dossier on PAUSED/FAILED

Dossiers are **archived** (not deleted) when session transitions to PAUSED or FAILED state. Archived dossiers remain in `~/.deerflow/rtcm/dossiers/`.

---

## 5. RTCM Budget and Checkpoints

### 5.1 Budget System

**Path**: `~/.deerflow/rtcm/budget/session-budget-{sessionId}_{alerts|config|state}.json`

| File | Purpose |
|------|---------|
| `session-budget-{id}_config.json` | Budget limits (token cap, time cap) |
| `session-budget-{id}_state.json` | Current spend vs limits |
| `session-budget-{id}_alerts.json` | Warning thresholds |

**Lifecycle**: Per RTCM session. Created at session start, deleted at session end.

### 5.2 Checkpoint System

**Path**: `~/.deerflow/rtcm/checkpoints/checkpoint-{timestamp}-{hash}.json`

Used for RTCM recovery after process restart. Per-session checkpoint with timestamp + content hash.

---

## 6. Feishu Integration

### 6.1 RTCM → Feishu Flow

```
RTCM session creates issue card
  → rtcm_feishu_api_adapter.sendCardMessage()
  → Feishu card posted to configured channel
  → User interacts with card
  → Feishu event → ChannelService → MessageBus → ...
```

### 6.2 Feishu Card Types

| Card Type | Trigger |
|-----------|---------|
| Launch card | RTCM activation (`activateRTCM()`) |
| Issue card | New issue created by council |
| Follow-up notification | Pending user action reminder |

### 6.3 RTCM-Channel Interaction

RTCM uses **Feishu API directly** for cards, but **ChannelService** (MessageBus) for inbound messages. These are separate paths.

---

## 7. Governance Integration

### 7.1 RTCM Writes Governance

**Myth**: RTCM bypasses governance entirely.

**Reality**: RTCM outcomes flow to governance via:
1. **Feishu API → ChannelService → MessageBus → ChannelManager → DeerFlow** (if user responds via Feishu)
2. **RTCM → M01 handoff → governance_bridge.record_outcome()** (via Feishu adapter outcome backflow)

### 7.2 RTCM Independent State Machine

RTCM maintains its own session state (`rtcm_session_state`) independent of:
- M01's `m01_request_state`
- Gateway's `gateway_run_state`
- DeerFlow's `deerflow_thread_state`

**But**: `threadId` in RTCM refers to **rtcm thread**, NOT Gateway thread_id.

---

## 8. Key Gaps and Risks

| ID | Gap | Severity | Blocking R240-5? |
|----|-----|----------|------------------|
| RG-1 | RTCM independent state machine not integrated with Mode Router | High | Yes — Mode Router has no RTCM awareness |
| RG-2 | `threadId` collision: RTCM rtcm thread ≠ Gateway thread_id | High | Yes — requires disambiguation |
| RG-3 | RTCM session ID (`rtcm_session_id`) not in ContextEnvelope | Medium | Yes — lineage breaks |
| RG-4 | Dossier artifacts enter nightly review but no consumption | Low | No |
| RG-5 | RTCM-Governance path (Feishu→Channel→DeerFlow) bypasses M01/M04 | Medium | Yes — governance outcome missing context_id |
| RG-6 | Budget/checkpoint systems not integrated with ModeStateScope | Medium | No — future work |
