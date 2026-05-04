# R240-MA Memory Design / Code / Runtime Gap

| Sub-capability | Original design state | Current code state | Current runtime state | Difference type | Repair direction |
|---|---|---|---|---|---|
| Five memory layers | L1-L5 explicitly designed | `backend/src/domain/memory/*` models layers | Active runtime mainly FileMemory/Qdrant/checkpoints | runtime_partial | Define one Memory Contract that maps active stores to L1-L5 |
| Working memory | ReMe active-context compaction | `layer1/working_memory.ts` | Checkpoints and thread artifacts exist | wired_not_runtime_verified | Bind request/thread context to L1 explicitly |
| Session memory | SimpleMem session compression | `layer2/session_memory.ts`, DeerFlow file memory overlaps | `backend/.deer-flow/.openclaw/memory.json` and threads | runtime_partial | Separate session summaries from global persistent facts |
| Persistent memory | MemOS local plugin | `layer3/persistent_memory.ts`, `FileMemoryStorage` | `memory.json` has 100 facts | fully_closed_loop | Add scope/provenance/retention metadata |
| Knowledge graph | GraphRAG + Mem0 nightly graph | `layer4/knowledge_graph.ts`, Qdrant storage | Qdrant SQLite exists with sparse points | wired_not_runtime_verified | Verify graph extraction path and nightly producer |
| Visual anchor memory | CortexaDB / UI automation anchors | `layer5/visual_anchor.ts` | Thread user-data exists but no active visual anchor registry proven | code_exists_not_wired | Define visual memory producer and retention rules |
| Semantic write pipeline | 7-stage PostToolUse write | `pipeline/semantic_writer.ts` | No clear active invocation chain proven | code_exists_not_wired | Wire through ModeExecutionResult and governance gates |
| Memory scope | Shared/isolated memory required by modes | Config/API concepts exist | Cross-mode enforcement not proven | runtime_partial | Implement memory_scope in Context Contract before optimization |
| Memory cleanup | Forgetting, retention, privacy filtering | Updater filters uploaded file mentions | Cleanup/retention not proven across all stores | wired_not_runtime_verified | Define retention policy per layer |
| Memory-to-asset promotion | Nightly can promote reusable memory | Tests and asset integration hints exist | Not fully closed loop | runtime_partial | Gate promotion through Asset Lifecycle Contract |
