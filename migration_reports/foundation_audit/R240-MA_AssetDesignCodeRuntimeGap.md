# R240-MA Asset Design / Code / Runtime Gap

| Sub-capability | Original design state | Current code state | Current runtime state | Difference type | Repair direction |
|---|---|---|---|---|---|
| Nine asset categories | A1-A9 explicitly designed | TS and Python categories overlap but differ | Operation registry mostly tool/platform assets | runtime_partial | Normalize category enum across TS, Python, Harness |
| Five lifecycle tiers | Record/General/Available/Premium/Core | `AssetTier` exists in TS | Runtime registry does not prove full tier workflow | wired_not_runtime_verified | Make tier state mandatory in registry artifacts |
| Scoring model | 25/30/20/15/10 weights | TS quality calculation implements similar weights | Runtime scoring not consistently visible | runtime_partial | Persist score breakdown and evidence |
| Promotion | Score + success + stability + user confirmation for high tiers | TS `checkPromotion`; DPBS governance promotion | Asset promotion outcomes appear in governance | runtime_partial | Use one promotion event contract |
| Elimination | Tier-aware retirement and observation | TS elimination state exists | No full elimination history proven | wired_not_runtime_verified | Add non-destructive retirement ledger |
| CAPTURED/DERIVED/FIX | Explicit asset evolution operations | Nightly and tests reference captured/derived/fix concepts | Not fully proven in runtime artifacts | code_exists_not_wired | Bind nightly outputs to asset registry |
| DPBS binding | Not the whole original system | `backend/app/m07/asset_system.py` is real operational path | Governance/binding runtime evidence exists | runtime_exists_not_blueprinted | Document DPBS as sub-pipeline, not whole Asset |
| Prompt assets | A7 prompt instruction assets | Prompt asset code exists | Runtime prompt asset registry not proven | wired_not_runtime_verified | Route prompt optimization outputs through Asset Contract |
| RTCM reports as assets | Reusable reports can become candidates | No direct auto-promotion proven | RTCM final reports exist | runtime_partial | Treat RTCM final reports as candidates requiring validation |
| Asset-memory binding | Strongly designed | Harness memory_manager and tests exist | Partial evidence only | runtime_partial | Define MemoryAssetLink and shared provenance IDs |
