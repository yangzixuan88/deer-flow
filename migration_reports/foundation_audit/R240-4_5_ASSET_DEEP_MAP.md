# R240-4.5 Asset System (M07 DPBS) Deep Map

## 1. Asset as Event Byproduct

**Critical architectural finding**: Assets are not first-class planned entities. They emerge as **byproducts of governance outcome events**. There is no bidirectional reference between `asset_promotion` outcome records and the asset registry.

```
Governance outcome (asset_promotion)
  → DPBS reads outcome_records
  → Derives asset candidates
  → Binds platform → creates asset_id
  → Writes binding_report (no reference back to governance)
```

**Implication**: Asset lifecycle is driven entirely by governance events. If governance outcome is lost, asset orphaning can occur.

---

## 2. Asset Identity

### 2.1 Asset ID Schema

| Prefix | Source | Example |
|--------|--------|---------|
| `mcp-{server}` | MCP server tool asset | `mcp--filesystem` |
| `gov-{tool}` | Governance-proposed tool | `gov--search` |

### 2.2 Asset Provenance

Assets originate from two sources:
1. **MCP Server tools**: Discovered via `bind_platform()` when MCP server connects
2. **Governance outcome records**: Tool candidates proposed by governance decisions

---

## 3. DPBS Architecture

### 3.1 Components

| Component | Path | Role |
|-----------|------|------|
| `asset_system.py` | `backend/app/m07/` | Main DPBS logic |
| `governance_bridge.py` | `backend/app/m11/` | Reads `outcome_records` |
| `latest_binding_report.json` | `.openclaw/data/dpbs/` | Persistent binding state |
| `governance_state.json` | `backend/app/m11/` | Outcome records source |

### 3.2 Discovery Loop

```
DPBS.discovery_engine()
  → GovernanceBridge.get_outcome_records()
  → Filter: outcome_type == 'asset_promotion'
  → For each outcome:
      → Derive candidate_id, proposed_tool_name
      → Score asset (quality signals from governance)
      → If score > threshold: bind_platform()
      → Write to latest_binding_report.json
```

### 3.3 Bind Platform

```
bind_platform(asset_id, candidate_id, score, auto_bound)
  → asset_system.py:353 governance_bridge.record_outcome(
      outcome_type='asset_promotion',
      outcome={asset_id, candidate_id, score, auto_bound}
    )
  → Writes binding_report to .openclaw/data/dpbs/latest_binding_report.json
```

### 3.4 Self-Reinforcing Loop

```
Asset promotes governance
    ↓
Governance outcome → DPBS discovery
    ↓
Asset bound → more capabilities
    ↓
Future tasks use asset → more governance outcomes
```

This loop has no exit condition — assets never get deregistered automatically.

---

## 4. Asset State Storage

### 4.1 Storage Locations

| Storage | Path | Data |
|---------|------|------|
| `latest_binding_report.json` | `.openclaw/data/dpbs/` | All currently bound assets |
| `governance_state.json` | `backend/app/m11/` | Historical outcome records (last 100) |

### 4.2 Asset Record Fields

```json
{
  "asset_id": "mcp--filesystem",
  "candidate_id": "demand-20260315-github",
  "score": 0.85,
  "auto_bound": true,
  "bound_at": "2026-03-15T..."
}
```

---

## 5. Governance Bridge Integration

### 5.1 DPBS Reads Governance

**File**: `backend/app/m07/asset_system.py:165`
```python
governance_bridge.get_outcome_records(
    outcome_type='asset_promotion',
    since=...
)
```

### 5.2 DPBS Writes Governance

**File**: `backend/app/m07/asset_system.py:353`
```python
governance_bridge.record_outcome(
    outcome_type='asset_promotion',
    outcome={asset_id, candidate_id, score, auto_bound}
)
```

### 5.3 Asset State Interaction Matrix

```
governance_state ──reads──→ DPBS (get_outcome_records)
governance_state ←─writes── DPBS (record_outcome: asset_promotion)
governance_state ──reads──→ M08 (learning_system: asset hit quality)
```

---

## 6. M08 Learning System Integration

### 6.1 Asset Quality Signals

M08 reads governance outcome records to assess asset quality:

```
M08.learning_system
  → GovernanceBridge.get_outcome_records()
  → Filter: asset_promotion outcomes
  → Update asset quality scores
  → Influences future DPBS binding decisions
```

### 6.2 Feedback Loop

```
Asset bound → governance outcome (asset_promotion)
    ↓
M08 reads → updates quality score
    ↓
Quality score feeds into future binding threshold
```

---

## 7. Key Gaps and Risks

| ID | Gap | Severity | Blocking R240-5? |
|----|-----|----------|------------------|
| AG-1 | No bidirectional reference: asset_promotion outcome → binding_report | High | No — but makes audit difficult |
| AG-2 | No asset deregistration path | High | No — assets accumulate forever |
| AG-3 | No governance_trace_id in asset binding | Medium | No — but lineage is opaque |
| AG-4 | Self-reinforcing loop has no exit | Medium | No — but may cause asset bloat |
| AG-5 | `governance_trace_id` from ContextEnvelope not consistently carried | Medium | Yes — lineage breaks at M04→M11 boundary |
