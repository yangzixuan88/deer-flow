# R240-FP Risk and Rollback Plan

Generated: 2026-04-24  
Status: planning only.

## Core Safety Philosophy

The target system should be more autonomous, stronger, more proactive, and more intelligent. High autonomy must not mean unsafe execution. The control model is:

- Backup before risky change.
- Rollback path before irreversible operation.
- Archive instead of delete.
- Audit every material tool action.
- Review and learn through governance and nightly health review.

Frequent user confirmation is not the primary safety mechanism. User confirmation is reserved for critical configuration, important deletion, irreversible external side effects, high-tier asset retirement, and high-risk prompt/runtime changes.

## Risk Classes

| Risk class | Examples | Default handling |
|---|---|---|
| Low | Search, read, static scan, non-destructive test, report generation | Allow automatically in implementation rounds |
| Medium | Ordinary code edits, generated planning files, local build/test, reversible config edits | Allow when scoped, auditable, and rollbackable |
| High | Critical config changes, prompt replacement, asset retirement, memory cleanup, runtime path rewiring | Require backup, rollback plan, audit, and often user confirmation |
| Critical | Important file deletion, irreversible external side effect, credential/security changes, Core asset retirement | Require explicit user confirmation or archive/quarantine first |

## Mandatory Rollback Rules

### Critical configuration

- Create pre-change backup.
- Record changed keys and old values.
- Provide rollback command or file restoration path.

### Important file deletion

- Do not delete by default.
- Prefer archive/quarantine with timestamp and reason.
- If true deletion is needed, require explicit user confirmation.

### Prompt replacement

- Preserve old prompt.
- Store new prompt as candidate before activation.
- Require tests or evaluation evidence.
- Provide rollback to previous prompt.
- GEPA/DSPy outputs cannot replace production prompts without audit.

### Asset retirement

- Record and General assets can follow lifecycle rules.
- Available/Premium assets require observation and review.
- Core assets cannot be automatically retired.
- Retirement must preserve history and provenance.

### Memory cleanup

- Never directly delete long-term memory in first pass.
- Use observation/quarantine.
- Preserve provenance and reason.
- Cleanup must respect layer, scope, retention, and privacy.

### Mode orchestration

- Do not replace M01/M04/RTCM in one step.
- Start with wrappers and instrumentation.
- Preserve legacy path fallback.
- Every mode handoff must be auditable through ModeInvocation and ModeCallGraph.

### Nightly review

- Nightly may generate action queue and low-risk checks.
- Nightly must not directly execute high-risk repairs.
- High-risk items must route to backup/rollback/governance/user confirmation.

## Specific Foundation Risks

| Risk | Control |
|---|---|
| Qdrant treated as complete memory system | Require MemoryLayerContract and runtime source mapping |
| MemoryMiddleware treated as complete memory system | Require dual-track + L1-L5 contract |
| DPBS treated as complete asset system | Require A1-A9 AssetLifecycleContract |
| RTCM final_report auto-promoted to asset | Require candidate verification and scoring |
| Governance outcome auto-promoted to asset | Require AssetPromotionContract gate |
| Single selected_mode becomes final model | Require ModeCallGraph |
| Prompt hierarchy overwritten by SOUL.md | Require PromptGovernanceContract P1-P6 |
| High autonomy becomes destructive | Require ToolPolicy, backup, rollback, audit, RootGuard |

## Audit and Review Requirements

Every future implementation phase must record:

- What changed.
- Why it changed.
- Which contract authorized it.
- Which files or runtime artifacts were touched.
- Backup location if applicable.
- Rollback path.
- Test/verification result.
- Governance/nightly followup if applicable.

## Current Round Constraint

This R240-FP round is planning only. No rollback is required for code because no business code or runtime data is modified. These rollback rules apply to later implementation rounds only after user confirmation.
