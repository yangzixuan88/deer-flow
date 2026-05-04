# R240-MA Asset Deep Audit

## Scope

- Unique root: `E:\OpenClaw-Base\deerflow`
- Audit type: read-only design/code/runtime mapping
- Primary design evidence:
  - `openclaw_project/docs/07_Digital_Asset_System.md`
  - `openclaw_project/OpenClaw超级工程项目_V1_Full_Archive.md`
  - `openclaw_project/docs/M00_System_Overview.md`

## Original Design Layer

The original Asset system is a first-class reusable capability system, not just a JSON registry.

### Definition

A digital asset is something that makes the system better, faster, cheaper, or safer when a similar situation appears again. Single-task outputs, raw conversation history, debug variables, and unverified emotional feedback are not assets.

### Asset Categories

| Category | Meaning |
|---|---|
| A1 Capability tool assets | Best tool parameters, call patterns, security boundaries, retry strategy |
| A2 External resource assets | API endpoints, docs, mirrors, source strategies |
| A3 Solution / workflow assets | Reusable workflow DAGs, SOPs, repeatable task strategies |
| A4 Execution experience assets | Environment-specific pitfalls, workarounds, failure recovery |
| A5 Cognitive method assets | Thinking templates, decomposition strategies |
| A6 Source / person-network assets | High-quality sources and information maps |
| A7 Prompt instruction assets | Optimized prompts, few-shots, GEPA/DSPy output |
| A8 User preference assets | Hard user preferences, safety rules, style requirements |
| A9 Domain knowledge maps | GraphRAG-derived knowledge maps |

### Lifecycle Tiers

| Tier | Score | Retrieval / protection |
|---|---:|---|
| Record | <30 | Raw captured log; no LLM retrieval; 180-day cleanup |
| General | 30-59 | Immature reusable asset; direct elimination if repeated failure |
| Available | 60-74 | Verified but not core; observation before elimination |
| Premium | 75-89 | Core working ammo; Feishu/user-visible downgrade path |
| Core | >=90 | Constitutional/protected; no automatic elimination |

### Scoring

Original scoring weights:

- Frequency: 25%
- Success rate: 30%
- Timeliness: 20%
- Coverage: 15%
- Uniqueness: 10%

### Promotion / Elimination / Evolution

Promotion requires score, success evidence, stability, and sometimes user confirmation. Elimination is tier-aware: low-tier assets can be removed or observed automatically, while core assets require explicit user decision. Evolution operations include CAPTURED, DERIVED, and FIX.

## Current Code Layer

### TypeScript AssetManager

Evidence paths:

- `backend/src/domain/asset_manager.ts`
- `backend/src/domain/asset_manager.test.ts`
- `backend/src/domain/memory/memory_asset_integration.test.ts`

This is the clearest implementation of tiering, scoring, usage result tracking, quality scoring, lifecycle evaluation, quick elimination, promotion checks, and ROI calculation. It partially matches the original five-tier design and scoring weights.

Important gap: the implemented categories are `search`, `task`, `tool`, `cognitive`, `network`, `combined`, `skill`, `document`, `metadata`, which overlap but do not exactly encode A1-A9.

### Nightly / Prompt / Skill Asset Paths

Evidence paths:

- `backend/src/domain/nightly_distiller.ts`
- `backend/src/domain/prompt_engine/layer5_asset.ts`
- `backend/src/domain/prompt_engine/layer4_nightly.ts`
- `backend/src/domain/skill_factory/skill_compiler.ts`

These support asset promotion concepts, prompt asset handling, and compiling L3 assets into skills. They are code-state evidence and partial bridge evidence, not full runtime closure.

### Python App DPBS / Governance Asset Path

Evidence paths:

- `backend/app/m07/asset_system.py`
- `backend/app/gateway/app.py`
- `backend/app/m11/governance_bridge.py`
- `backend/app/m11/governance_state.json`

DPBS is a real running subpath around platform/tool binding, sandbox evaluation, governance approval, binding reports, and governance outcome recording. It should not be mistaken for the complete original Asset system; it is one operational asset pipeline.

### DeerFlow Harness Asset Path

Evidence paths:

- `backend/packages/harness/deerflow/assets/asset_manager.py`
- `backend/packages/harness/deerflow/assets/review_engine.py`
- `backend/packages/harness/deerflow/assets/memory_manager.py`
- `backend/packages/harness/deerflow/assets/prompt_manager.py`
- `backend/packages/harness/deerflow/tools/builtins/autonomous_tools.py`
- `backend/packages/harness/deerflow/tools/builtins/review_evolution_tool.py`

This path models categories close to A1-A9, supports nightly review concepts, prompt/experience assets, and memory linkage. Some default paths still reference `Path.home()/.deerflow`, so current runtime-root alignment must be verified before production use.

## Current Runtime Layer

Runtime evidence:

| Artifact | Type | Evidence |
|---|---|---|
| `.deerflow/operation_assets/asset_registry.json` | Operation asset registry | Exists, 11,622 bytes, 12 assets |
| `.deerflow/reports/latest_report.json` | Review/report artifact | Exists; initialization-style report |
| `assets/asset-index.json` | Top-level asset index | Exists but effectively empty |
| `backend/app/m11/governance_state.json` | Governance outcomes | Exists, 100 outcome records, asset-related outcome strings found |
| `.deerflow/upgrade-center/reports/*` | Upgrade Center reports | Multiple runtime reports exist |
| `.deerflow/rtcm/dossiers/*/final_report.*` | RTCM candidate artifacts | Exists; candidate asset evidence, not automatic asset promotion |
| `C:\Users\win\.deerflow` | Old home runtime | Not active |
| `C:\Users\win\.deerflow__MIGRATED_DO_NOT_USE` | Frozen old home runtime | Archive only |

## Answers

### Q-A1: Original promotion system

Promotion is score/tier driven, using frequency, success rate, timeliness, coverage, uniqueness, stability, and in high tiers explicit user/Feishu confirmation.

### Q-A2: Original elimination system

Elimination is tier-aware. Record assets expire, General can be directly eliminated after repeated failure, Available/Premium enter observation, Core requires user decision.

### Q-A3: Asset categories

The original categories are A1-A9: tools, resources, workflows, experiences, cognitive methods, sources/networks, prompts, preferences, and knowledge maps.

### Q-A4: Current implemented stages

TS AssetManager implements scoring, tiering, usage updates, promotion checks, elimination status, reports, and ROI calculation. DPBS implements candidate evaluation, governance-mediated binding, and binding reports. DeerFlow Harness implements prompt/experience/asset review paths.

### Q-A5: Runtime closure

Runtime is partial. Operation assets and governance asset outcomes exist. Full A1-A9 lifecycle with promotion/elimination/nightly/user-confirmation is not fully proven.

### Q-A6: DPBS / governance / binding report status

They are a real operational asset path, not the complete Asset system.

### Q-A7: Asset-memory binding

Designed strongly and partially coded. Runtime binding is not yet uniform across all asset categories.

### Q-A8: Asset-nightly binding

Designed strongly and partially coded. Existing reports show runtime artifacts, but full nightly asset lifecycle closure is not proven.

### Q-A9: Asset-five-mode binding

Designed conceptually. Runtime binding is partial; the five modes do not yet share one asset contract.

### Q-A10: Asset / Upgrade Center / Governance relationship

Upgrade Center and Governance have become fact-path systems that can produce asset candidates and governance outcomes. They are now part of the practical asset ecosystem even if the original blueprint did not fully describe them.

## Conclusion

Asset is sufficiently mapped for foundation optimization planning. The original design is richer than current runtime. The current fact path is partial: operation assets, DPBS/governance signals, RTCM candidate reports, and upgrade-center outputs exist, but the full nine-category five-tier lifecycle is not yet proven as one closed loop.
