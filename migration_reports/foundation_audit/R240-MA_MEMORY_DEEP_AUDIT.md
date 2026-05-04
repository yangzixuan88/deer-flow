# R240-MA Memory Deep Audit

## Scope

- Unique root: `E:\OpenClaw-Base\deerflow`
- Audit type: read-only design/code/runtime mapping
- Primary design evidence:
  - `openclaw_project/docs/06_Memory_Architecture.md`
  - `openclaw_project/OpenClaw超级工程项目_V1_Full_Archive.md`
  - `openclaw_project/PHASE_10_5_DETAILED_PLAN.md`

## Original Design Layer

The original Memory design is not a single storage path. It defines a dual-track architecture plus five memory layers.

### Dual Track

| Track | Responsibility | Ownership | Lifecycle |
|---|---|---|---|
| OpenClaw native memory | User-controlled project knowledge, `MEMORY.md`, `AGENTS.md`, `boulder.json`, task state, cross-round behavior rules | Human / explicit project process | Immediate to permanent |
| DeerFlow cognitive memory | Execution experience, semantic memory, knowledge graph, vector recall, agent experience | AI-maintained runtime | Days to years |

`MEMORY.md` is designed as a stable user-controlled memory file and should not be silently appended by agents.

### Five Layers

| Layer | Name | Engine / design reference | Main content | Lifecycle |
|---|---|---|---|---|
| L1 | Working Memory | ReMe | Current task context, recent tokens, scratchpad, compacted active state | Current task only; sinks to L2 |
| L2 | Session Memory | SimpleMem | Recent sessions, compressed session summaries, multimodal context | Session-scale; can consolidate upward |
| L3 | Persistent Memory | MemOS Local Plugin | Stable preferences, skills, tool usage, capability maps, persistent facts | Long-term local persistence |
| L4 | Knowledge Graph | GraphRAG + Mem0 | Entities, relations, semantic memory network, structured cross-task knowledge | Nightly-distilled long-term graph |
| L5 | Visual Anchor Memory | CortexaDB | GUI snapshots, visual anchors, UI-TARS/Midscene automation anchors | Task/UI-workflow scoped; reusable if verified |

The user requirement mentions two open-source memory projects. The design documents actually name more than two. The two principal long-term projects are:

- MemOS: L3 persistent local structured memory.
- GraphRAG + Mem0: L4 knowledge graph and semantic memory network.

Other named projects are ReMe, SimpleMem, CortexaDB, and agentmemory.

### Long-Term vs Temporary

Long-term eligible:

- Stable user preferences and safety constraints.
- Verified facts and reusable domain knowledge.
- Successful reusable execution experiences.
- Tool/skill/capability maps.
- Knowledge graph entities and relations.
- Visual anchors only when reusable and verified.

Temporary only:

- Uploaded file bookkeeping.
- Intermediate tool messages.
- Debug variables and transient outputs.
- Unverified single-task conclusions.
- Sensitive secrets, API keys, private raw credentials.

### Nightly Relationship

The design expects nightly consolidation:

- Dreaming promotes qualified short-term signals to stable memory.
- GraphRAG distills daily experience packages into entity-relation graph updates.
- Low-quality or privacy-sensitive fragments should be dropped before persistence.

## Current Code Layer

### TypeScript Domain Memory

Evidence paths:

- `backend/src/domain/memory/types.ts`
- `backend/src/domain/memory/layer1/working_memory.ts`
- `backend/src/domain/memory/layer2/session_memory.ts`
- `backend/src/domain/memory/layer3/persistent_memory.ts`
- `backend/src/domain/memory/layer4/knowledge_graph.ts`
- `backend/src/domain/memory/layer5/visual_anchor.ts`
- `backend/src/domain/memory/pipeline/semantic_writer.ts`
- `backend/src/domain/memory/memory_asset_integration.test.ts`

The TS layer explicitly models the five-layer design and a semantic write pipeline. The semantic pipeline follows the intended sequence: dedupe, sanitization, compression, validation, quality scoring, embedding, and storage. This is strong code-state evidence, but not sufficient proof that all five layers are the active production path.

### DeerFlow Harness Memory

Evidence paths:

- `backend/packages/harness/deerflow/agents/memory/storage.py`
- `backend/packages/harness/deerflow/agents/memory/vector_storage.py`
- `backend/packages/harness/deerflow/agents/memory/updater.py`
- `backend/packages/harness/deerflow/agents/middlewares/memory_middleware.py`
- `backend/packages/harness/deerflow/config/memory_config.py`
- `backend/packages/harness/deerflow/config/paths.py`

This is the strongest current runtime-facing implementation:

- `MemoryMiddleware` injects semantic or contextual memory before agent execution.
- `FileMemoryStorage` persists global/per-agent memory JSON.
- `QdrantMemoryStorage` can sync facts into vector storage.
- `MemoryUpdater` filters uploaded file references and updates facts/user/history.

### Gateway / Frontend Memory

Evidence paths:

- `backend/app/gateway/routers/memory.py`
- `frontend/src/components/workspace/settings/memory-settings-page.tsx`
- `frontend/src/core/memory/api.ts`
- `frontend/src/core/memory/hooks.ts`

These expose memory inspection/import/export/control surfaces, but the audit did not execute mutating endpoints.

## Current Runtime Layer

Runtime evidence:

| Artifact | Type | Evidence |
|---|---|---|
| `backend/.deer-flow/.openclaw/memory.json` | File memory | Exists, 44,964 bytes, 100 facts; strongest active memory evidence |
| `backend/.deer-flow/data/qdrant/collection/deerflow_memory/storage.sqlite` | Qdrant local vector store | Exists, 73,728 bytes, `points` table has 4 rows |
| `backend/.deer-flow/.openclaw/checkpoints.db` | LangGraph checkpoint / thread state | Exists, large checkpoint DB; context/runtime state, not canonical long-term memory |
| `backend/.deer-flow/threads/*` | Thread artifacts | Exists; stores user data and task/thread outputs |
| `C:\Users\win\.deerflow` | Old home runtime | Not active; removed or migrated |
| `C:\Users\win\.deerflow__MIGRATED_DO_NOT_USE` | Frozen old home runtime | Exists as frozen archive, not active root |

## Answers

### Q-M1: Original five layers

L1 Working, L2 Session, L3 Persistent, L4 Knowledge Graph, L5 Visual Anchor.

### Q-M2: Two open-source memory projects

The design names more than two. The two main long-term memory projects are MemOS for L3 and GraphRAG + Mem0 for L4. ReMe, SimpleMem, CortexaDB, and agentmemory also appear in the original design and must not be ignored.

### Q-M3: Implemented parts

The TS domain implements layer types, storage classes, and semantic writer concepts. DeerFlow Harness implements active file/vector memory, middleware injection, and updater logic.

### Q-M4: Current runtime path

The strongest runtime path is DeerFlow Harness file memory at `backend/.deer-flow/.openclaw/memory.json`, with sparse Qdrant support under `backend/.deer-flow/data/qdrant`.

### Q-M5: MemoryMiddleware / QdrantStorage status

`MemoryMiddleware` is a current fact path. `QdrantStorage` exists and has runtime storage, but observed vector population is sparse; it should be treated as partial, not the whole memory system.

### Q-M6: memory_scope status

`memory_scope` exists as design/config/API intent, but a unified cross-mode enforcement contract is not proven at runtime.

### Q-M7: Long-term eligible memory

Verified facts, stable preferences, reusable successful experiences, capability maps, domain knowledge, and validated visual anchors.

### Q-M8: Never long-term

Secrets, raw uploaded file bookkeeping, transient tool output, unverified debug data, and single-task-only noisy context.

### Q-M9: Relationship with five modes

All five modes need memory, but with different scopes. Search should write low unless verified. Task/workflow can write execution learnings. Autonomous agent needs stricter permission and provenance. Roundtable can produce high-value summaries but should not auto-persist all deliberation.

### Q-M10: Relationship with Asset/Nightly/Governance

Memory supplies reusable candidates to asset promotion, nightly performs consolidation and quality gates, and governance should record high-impact memory or asset decisions. This relationship is designed, partially coded, and partially runtime-evidenced.

## Conclusion

Memory is sufficiently mapped for foundation optimization planning. The original design is broader than the current active runtime path. The current fact path is DeerFlow Harness file memory plus partial Qdrant, while the TypeScript five-layer architecture is code-state evidence that still needs integration verification.
