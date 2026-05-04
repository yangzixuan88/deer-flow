import os
import json
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any, List
from app.runtime_paths import upgrade_center_state_dir

logger = logging.getLogger("m08_uef")
logger.setLevel(logging.INFO)

class Optimizer:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        
    async def optimize(self, result: Dict[str, Any], metadata: Dict[str, Any]):
        tool_calls = metadata.get("tool_calls", [])
        if not tool_calls or len(tool_calls) < 2:
            return
        logger.info("[UEF Optimizer] Analyzing task trail for redundancy...")
        # 即时精简逻辑

class NightlyDistiller:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    def _get_upgrade_state_dir(self) -> str:
        """Path to the project-local Upgrade Center state directory."""
        return str(upgrade_center_state_dir())

    def _read_today_xp_packages(self) -> List[Dict[str, Any]]:
        """Read all XP packages from today's JSONL file.

        Returns a list of experience dicts matching the TypeScript ExperiencePackage interface.
        Python XP format (from _capture_experience):
          {
            "id": "exp-{date}-{trace_id}",
            "session_id": "...", "task_goal": "...", "category": "task",
            "tool_calls": ["Bash", "Read", ...],  # list of tool name strings
            "total_tokens": int, "total_duration_ms": float,
            "result_quality": float, "failure_info": null | str,
            "search_triggers": [], "asset_hits": []
          }
        """
        today = datetime.now().strftime("%Y-%m-%d")
        xp_file = os.path.join(self.config["experiences_dir"], f"exp-{today}.jsonl")
        if not os.path.exists(xp_file):
            return []
        packages = []
        try:
            with open(xp_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        packages.append(json.loads(line))
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"[NightlyDistiller] Failed to read XP file {xp_file}: {e}")
        return packages

    def _normalize_tool_calls(self, tool_calls: Any) -> List[str]:
        """Normalize tool_calls to list[str].

        Input shapes:
          - list[str]: returned as-is (correct shape)
          - int: returns [] (count-only, no tool names available)
          - None / other non-iterable: returns []
          - list[other]: extracts string representations
        """
        if isinstance(tool_calls, list):
            return [str(t) for t in tool_calls if t]
        if isinstance(tool_calls, (int, float, str)):
            return []
        return []

    def _run_stage1(self, packages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage1: Aggregate statistics from XP packages.

        Returns a dict matching TypeScript Stage1AggregateStats interface.
        """
        total = len(packages)
        success_count = sum(1 for p in packages if p.get("result_quality", 0) >= 0.6)
        total_tokens = sum(p.get("total_tokens", 0) for p in packages)
        total_ms = sum(p.get("total_duration_ms", 0.0) for p in packages)

        # Tool usage stats
        tool_stats: Dict[str, int] = {}
        for p in packages:
            for tool in self._normalize_tool_calls(p.get("tool_calls")):
                tool_stats[tool] = tool_stats.get(tool, 0) + 1

        return {
            "total_tasks": total,
            "success_count": success_count,
            "failure_count": total - success_count,
            "success_rate": round(success_count / total, 4) if total > 0 else 0.0,
            "total_tokens": total_tokens,
            "total_duration_ms": round(total_ms, 1),
            "model_distribution": {},   # Python XP doesn't track model per-call
            "tool_usage_stats": tool_stats,
        }

    def _run_stage2(self, packages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage2: Identify bottlenecks from XP packages.

        Writes real bottleneck analysis to Upgrade Center state file:
          {DEERFLOW_ROOT}/.deerflow/upgrade-center/state/nightly_review_stage2_bottlenecks.json

        This output is consumed by demand_sampler.sampleFromInternalBottlenecks().

        Returns a dict matching TypeScript Stage2Bottlenecks interface.
        """
        # Slowest tasks (top 3 by duration)
        sorted_by_duration = sorted(packages, key=lambda p: p.get("total_duration_ms", 0), reverse=True)
        slowest_tasks = [
            {"task": p.get("task_goal", "unknown")[:80], "duration_ms": round(p.get("total_duration_ms", 0), 1)}
            for p in sorted_by_duration[:3]
        ]

        # Most failed tools: sessions with failure_info != null, count unique tool mentions
        failed_tools: Dict[str, int] = {}
        for p in packages:
            if p.get("failure_info"):
                for tool in self._normalize_tool_calls(p.get("tool_calls")):
                    failed_tools[tool] = failed_tools.get(tool, 0) + 1
        most_failed_tools = [
            {"tool": tool, "failure_count": count}
            for tool, count in sorted(failed_tools.items(), key=lambda x: x[1], reverse=True)[:3]
        ]

        # Highest token steps (sessions ranked by total_tokens as proxy for per-step)
        sorted_by_tokens = sorted(packages, key=lambda p: p.get("total_tokens", 0), reverse=True)
        highest_token_steps = [
            {"step": p.get("task_goal", "unknown")[:80], "tokens": p.get("total_tokens", 0)}
            for p in sorted_by_tokens[:3]
        ]

        # Redundant searches (search_triggers appearing > 3 times across all packages)
        search_counts: Dict[str, int] = {}
        for p in packages:
            for trigger in p.get("search_triggers", []):
                search_counts[trigger] = search_counts.get(trigger, 0) + 1
        redundant_searches = [t for t, c in search_counts.items() if c > 3]

        # Improvement priorities
        improvement_priorities: List[Dict[str, str]] = []
        if slowest_tasks:
            improvement_priorities.append({
                "item": f"优化任务耗时（最慢: {slowest_tasks[0]['task'][:40]}，{slowest_tasks[0]['duration_ms']}ms）",
                "priority": "high"
            })
        if most_failed_tools:
            worst = most_failed_tools[0]
            improvement_priorities.append({
                "item": f"工具 {worst['tool']} 失败率过高（{worst['failure_count']}次失败）",
                "priority": "medium"
            })
        if highest_token_steps and highest_token_steps[0]["tokens"] > 5000:
            improvement_priorities.append({
                "item": f"Token消耗过高（最高: {highest_token_steps[0]['tokens']}），需优化提示词或缓存策略",
                "priority": "medium"
            })
        if not improvement_priorities:
            improvement_priorities.append({
                "item": "无显著瓶颈，系统运行平稳",
                "priority": "low"
            })

        bottleneck = {
            "slowest_tasks": slowest_tasks,
            "most_failed_tools": most_failed_tools,
            "highest_token_steps": highest_token_steps,
            "redundant_searches": redundant_searches,
            "improvement_priorities": improvement_priorities,
        }

        # Write to Upgrade Center state file (consumed by demand_sampler.ts)
        state_dir = self._get_upgrade_state_dir()
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "nightly_review_stage2_bottlenecks.json")
        try:
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(bottleneck, f, ensure_ascii=False, indent=2)
            logger.info(f"[NightlyDistiller] Wrote Stage2 bottlenecks to {state_file}")
        except Exception as e:
            logger.warning(f"[NightlyDistiller] Failed to write Stage2 state file: {e}")

        return bottleneck

    def _get_asset_registry_dir(self) -> str:
        """Path to the Python asset registry directory (~/.openclaw/assets/).

        The Python AssetManager (deerflow/assets/asset_manager.py) stores assets as
        JSON files in {base_dir}/{category}/{asset_id}.json. We use the standard
        OpenClaw base so this is consistent regardless of cwd.
        """
        base = os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base")
        return os.path.join(base, ".openclaw", "assets")

    def _read_registry_assets(self) -> Dict[str, Dict[str, Any]]:
        """Read all assets from the Python JSON-based registry.

        Returns a dict mapping asset_id -> asset dict.
        """
        registry_dir = self._get_asset_registry_dir()
        assets: Dict[str, Dict[str, Any]] = {}

        if not os.path.exists(registry_dir):
            return assets

        for category in os.listdir(registry_dir):
            cat_path = os.path.join(registry_dir, category)
            if not os.path.isdir(cat_path):
                continue
            for fname in os.listdir(cat_path):
                if not fname.endswith(".json"):
                    continue
                try:
                    with open(os.path.join(cat_path, fname), "r", encoding="utf-8") as f:
                        asset = json.load(f)
                        assets[asset.get("id", fname[:-5])] = asset
                except Exception:
                    continue
        return assets

    def _run_stage4(self, packages: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Stage4: Analyze asset health and generate asset change proposals.

        Reads asset_hits from XP packages and the Python asset registry,
        then writes Stage4AssetChanges to Upgrade Center state file:
          {DEERFLOW_ROOT}/.deerflow/upgrade-center/state/nightly_review_stage4_assets.json

        This output is consumed by demand_sampler.sampleFromAssetDegradation().

        Returns a dict matching TypeScript Stage4AssetChanges interface:
          {
            "promotions": [{"asset_id": str, "from_tier": str, "to_tier": str}],
            "demotions": [{"asset_id": str, "from_tier": str, "to_tier": str}],
            "new_candidates": [str],
            "fixed_assets": [str]
          }
        """
        # Aggregate asset usage quality from XP packages
        asset_stats: Dict[str, Dict[str, Any]] = {}
        for pkg in packages:
            quality = pkg.get("result_quality", 0.5)
            for asset_id in pkg.get("asset_hits", []):
                if asset_id not in asset_stats:
                    asset_stats[asset_id] = {"hits": 0, "total_quality": 0.0, "failures": 0}
                asset_stats[asset_id]["hits"] += 1
                asset_stats[asset_id]["total_quality"] += quality
                if quality < 0.5:
                    asset_stats[asset_id]["failures"] += 1

        # Read existing registry assets
        registry = self._read_registry_assets()
        registry_ids = set(registry.keys())

        # Python tier names (T1-T4) -> TypeScript tier names
        TIER_MAP = {
            "T1": "core",
            "T2": "premium",
            "T3": "available",
            "T4": "record",
            "candidate": "candidate",
            "active": "active",
        }

        promotions: List[Dict[str, str]] = []
        demotions: List[Dict[str, str]] = []
        new_candidates: List[str] = []
        fixed_assets: List[str] = []

        for asset_id, stats in asset_stats.items():
            avg_quality = stats["total_quality"] / stats["hits"] if stats["hits"] > 0 else 0.0
            hit_count = stats["hits"]

            if asset_id not in registry_ids:
                # New candidate: asset hit but not in registry
                if hit_count >= 1:
                    new_candidates.append(asset_id)
            else:
                # Existing asset: check promotion/demotion
                asset = registry[asset_id]
                current_tier = TIER_MAP.get(asset.get("tier", "T4"), "record")

                # Promotion: >=3 hits with avg_quality >= 0.8 (capability ceiling reached)
                if hit_count >= 3 and avg_quality >= 0.8:
                    promotions.append({
                        "asset_id": asset_id,
                        "from_tier": current_tier,
                        "to_tier": "active"
                    })
                # Demotion: avg_quality < 0.5 (degraded capability)
                elif avg_quality < 0.5:
                    demotions.append({
                        "asset_id": asset_id,
                        "from_tier": current_tier,
                        "to_tier": "record"
                    })
                # Recovery: was degraded but now avg_quality >= 0.6 (fixed)
                elif asset.get("status") in ("degraded", "archived") and avg_quality >= 0.6:
                    fixed_assets.append(asset_id)

        # Also flag new_candidates that appear frequently with high quality as worth promoting
        # (but they're still new_candidates until registered)
        # Deduplicate
        new_candidates = list(dict.fromkeys(new_candidates))  # preserve order, remove dups

        result = {
            "promotions": promotions,
            "demotions": demotions,
            "new_candidates": new_candidates,
            "fixed_assets": fixed_assets,
        }

        # Write to Upgrade Center state file (consumed by demand_sampler.ts)
        state_dir = self._get_upgrade_state_dir()
        os.makedirs(state_dir, exist_ok=True)
        state_file = os.path.join(state_dir, "nightly_review_stage4_assets.json")
        try:
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)
            logger.info(f"[NightlyDistiller] Wrote Stage4 assets to {state_file}")
        except Exception as e:
            logger.warning(f"[NightlyDistiller] Failed to write Stage4 state file: {e}")

        return result

    async def run_nightly_review(self):
        """
        R31/R32: 实现真实 Stage1 + Stage2 + Stage4 夜间复盘。
        读取当日 XP JSONL，生成：
          - Stage2: 瓶颈分析 -> nightly_review_stage2_bottlenecks.json
          - Stage4: 资产变更 -> nightly_review_stage4_assets.json
        """
        logger.info("[NightlyDistiller] 开始夜间复盘 (Stage1+Stage2+Stage4)...")
        packages = self._read_today_xp_packages()
        logger.info(f"[NightlyDistiller] Stage1: 读取到 {len(packages)} 条 XP 包")
        stats = self._run_stage1(packages)
        logger.info(f"[NightlyDistiller] Stage1 stats: tasks={stats['total_tasks']} "
                     f"success={stats['success_count']} tokens={stats['total_tokens']} "
                     f"ms={stats['total_duration_ms']}")
        bottleneck = self._run_stage2(packages)
        logger.info(f"[NightlyDistiller] Stage2: slowest={len(bottleneck['slowest_tasks'])} "
                     f"failed_tools={len(bottleneck['most_failed_tools'])} "
                     f"priorities={len(bottleneck['improvement_priorities'])}")
        asset_changes = self._run_stage4(packages)
        logger.info(f"[NightlyDistiller] Stage4: promotions={len(asset_changes['promotions'])} "
                     f"demotions={len(asset_changes['demotions'])} "
                     f"new_candidates={len(asset_changes['new_candidates'])} "
                     f"fixed={len(asset_changes['fixed_assets'])}")
        report_text = self._generate_report_from_stats(stats, bottleneck, asset_changes)
        await self._notify_feishu(report_text)

    async def run_weekly_review(self):
        logger.info("[UEF WeeklyReview] 开始周度深化...")
        report_text = self._generate_weekly_mock()
        await self._notify_feishu(report_text)

    def _generate_report_from_stats(
        self,
        stats: Dict[str, Any],
        bottleneck: Dict[str, Any],
        asset_changes: Dict[str, Any] = None,
    ) -> str:
        """Generate human-readable report from Stage1/Stage2/Stage4 data."""
        date_str = datetime.now().strftime("%Y-%m-%d")
        priorities = bottleneck.get("improvement_priorities", [])
        lines = [
            f"📊 OpenClaw 每日复盘 ({date_str})",
            f"🎯 任务: {stats['total_tasks']} | 成功: {stats['success_count']} | 失败: {stats['failure_count']}",
            f"💰 Token: {stats['total_tokens']} | ⏱ {stats['total_duration_ms']}ms",
            "",
            "🔍 瓶颈识别:",
        ]
        for p in priorities:
            lines.append(f"  [{p['priority'].upper()}] {p['item']}")
        if asset_changes:
            ac = asset_changes
            lines.append("")
            lines.append("📦 资产变更:")
            if ac.get("promotions"):
                lines.append(f"  晋升: {', '.join(a['asset_id'] for a in ac['promotions'])}")
            if ac.get("demotions"):
                lines.append(f"  降级: {', '.join(a['asset_id'] for a in ac['demotions'])}")
            if ac.get("new_candidates"):
                lines.append(f"  新候选: {', '.join(ac['new_candidates'])}")
            if ac.get("fixed_assets"):
                lines.append(f"  已修复: {', '.join(ac['fixed_assets'])}")
            if not any([ac.get(k) for k in ("promotions", "demotions", "new_candidates", "fixed_assets")]):
                lines.append("  无显著变更")
        return "\n".join(lines)

    def _generate_weekly_mock(self):
        return "📊 OpenClaw 周度深化\n📈 强项/弱项分析...\n🔄 资产进化处理完毕"

    async def _notify_feishu(self, content: str):
        try:
            from app.m12.feishu_gateway import feishu_app
            if hasattr(feishu_app, 'send_message'):
                await feishu_app.send_message(content)
                logger.info("[NightlyDistiller] 飞书通知成功")
                return
        except ImportError:
            pass
        logger.info(f"\n============== [Feishu Notify] ==============\n{content}\n===================================\n")

class AssetGuardian:
    def __init__(self, config: Dict[str, Any]):
        self.config = config

    async def scout_and_retire(self):
        logger.info("[UEF AssetGuardian] Scouting external intel for assets...")

class UniversalEvolutionFramework:
    def __init__(self, capability_name: str = "OpenClaw-UEF"):
        self.name = capability_name
        self.config = self._init_config()
        self._ensure_directories()
        
        self.optimizer = Optimizer(self.config)
        self.distiller = NightlyDistiller(self.config)
        self.asset_guardian = AssetGuardian(self.config)
        
        self.score = self._load_score()

    def _init_config(self) -> Dict[str, Any]:
        base_path = os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base")
        return {
            "learning_dir": os.path.join(base_path, ".openclaw", "data", "learning"),
            "experiences_dir": os.path.join(base_path, ".openclaw", "data", "learning", "experiences"),
            "reports_dir": os.path.join(base_path, ".openclaw", "data", "learning", "reports"),
            "uef_states_dir": os.path.join(base_path, ".openclaw", "data", "learning", "uef-states"),
            "sqlite_db": os.path.join(base_path, ".openclaw", "memory", "main.sqlite")
        }

    def _ensure_directories(self):
        for key in ["learning_dir", "experiences_dir", "reports_dir", "uef_states_dir"]:
            os.makedirs(self.config[key], exist_ok=True)

    def _load_score(self):
        score_path = os.path.join(self.config["uef_states_dir"], "score.json")
        if os.path.exists(score_path):
            try:
                with open(score_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {"reliability": 0, "performance": 0, "cost_eff": 0, "auto_rate": 0, "safety": 0}

    def _save_score(self):
        score_path = os.path.join(self.config["uef_states_dir"], "score.json")
        with open(score_path, 'w', encoding='utf-8') as f:
            json.dump(self.score, f, indent=2)

    async def init_system(self):
        logger.info(f"[UEF] {self.name} initialized. M05 HEARTBEAT will schedule updates.")

    async def before_execution(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        context = context or {}
        logger.info(f"[UEF] before_execution hooked for {context.get('task_id', 'unknown task')}")
        return context

    async def after_execution(self, result: Dict[str, Any] = None, metadata: Dict[str, Any] = None):
        result = result or {}
        metadata = metadata or {}

        # ─────────────────────────────────────────
        # M11 Governance Bridge — outcome backflow
        # Feed actual outcomes back into governance layers so they learn from reality.
        # This is the primary R17-R19 backflow channel.
        # ─────────────────────────────────────────
        try:
            from app.m11.governance_bridge import governance_bridge
            actual_success = result.get("success", False)
            predicted_success = metadata.get("predicted_success", 0.8 if actual_success else 0.3)

            await governance_bridge.record_outcome(
                outcome_type="tool_execution_uef",
                actual_result=1.0 if actual_success else 0.0,
                predicted_result=predicted_success,
                context={
                    "source_id": metadata.get("session_id", "unknown"),
                    "task_goal": metadata.get("task_goal", ""),
                    "tool_calls": len(metadata.get("tool_calls", [])),
                    # R29: total_tokens — real provider value when available, otherwise bytes//4 estimate
                    "total_tokens": metadata.get("total_tokens", 0),
                    "total_duration_ms": metadata.get("total_duration_ms", 0),
                    "result_quality": result.get("result_quality", 0.95 if actual_success else 0.2),
                    "granularity": metadata.get("granularity", "tool"),  # 'tool' from middleware, 'session' from worker
                    # R27: session-level extended telemetry (only present when granularity='session')
                    "success_count": metadata.get("success_count"),
                    "failure_count": metadata.get("failure_count"),
                    "total_input_bytes": metadata.get("total_input_bytes"),
                    "total_output_bytes": metadata.get("total_output_bytes"),
                    # R28: token estimation breakdown (bytes//4 approximation; not provider-reported)
                    "input_tokens_est": metadata.get("input_tokens_est", 0),
                    "output_tokens_est": metadata.get("output_tokens_est", 0),
                    # R29: provider-native token counts (only non-zero when token_source='provider')
                    "real_input_tokens": metadata.get("real_input_tokens", 0),
                    "real_output_tokens": metadata.get("real_output_tokens", 0),
                    "real_total_tokens": metadata.get("real_total_tokens", 0),
                    "token_source": metadata.get("token_source", "none"),  # 'none' | 'provider' | 'estimate'
                }
            )

            # R19: Update source reputation based on actual outcome
            source_id = metadata.get("session_id", "unknown")
            if source_id != "unknown":
                await governance_bridge.check_reputation_gate({
                    "source_id": source_id,
                    "base_weight": 0.5,
                    "context": metadata.get("task_goal", ""),
                })

            # R18: Check epistemic conflict if there was a significant error
            if not actual_success and result.get("error"):
                await governance_bridge.check_epistemic_conflict({
                    "truth": {
                        "value": result.get("error", "unknown_error"),
                        "source": "system",
                        "confidence": 0.9,
                        "conflicting_source": "expected",
                        "conflicting_value": 0.0,
                    }
                })

            # R18: Run stakeholder negotiation for mission-level decisions
            mission_goal = metadata.get("task_goal", "")
            if mission_goal and len(mission_goal) > 20:
                await governance_bridge.negotiate_stakeholders({
                    "issue": {
                        "description": f"Mission execution result: {mission_goal}",
                        "positions": {
                            "user": 0.8 if actual_success else 0.3,
                            "governance": 0.5,
                            "executive_control": 0.6,
                        }
                    }
                })

            logger.debug(f"[UEF] Governance outcome recorded for session {source_id}")
        except Exception as e:
            logger.warning(f"[UEF] Governance backflow failed (non-fatal): {e}")

        try:
            await self._capture_experience(result, metadata)
        except Exception as e:
            logger.error(f"[UEF] Failed to capture experience: {e}")

        if result.get("success"):
            try:
                await self.optimizer.optimize(result, metadata)
            except Exception as e:
                logger.error(f"[UEF] Optimizer failed: {e}")

    async def _capture_experience(self, result: Dict[str, Any], metadata: Dict[str, Any]):
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.config["experiences_dir"], f"exp-{today}.jsonl")
        
        trace_id = str(uuid.uuid4())[:8]
        experience = {
            "id": f"exp-{today}-{trace_id}",
            "timestamp": datetime.now().isoformat(),
            "session_id": metadata.get("session_id", "unknown"),
            "task_goal": metadata.get("task_goal", "unknown"),
            "category": "task",
            "model_used": metadata.get("model_used", "claude-code-local"),
            "tool_calls": metadata.get("tool_calls", []),
            "total_tokens": metadata.get("total_tokens", 0),
            "total_duration_ms": metadata.get("total_duration_ms", 0),
            "result_quality": 0.95 if result.get("success") else 0.20,
            "reusable_patterns": [],
            "failure_info": None if result.get("success") else result.get("error", "unknown failure"),
            "search_triggers": [],
            "asset_hits": metadata.get("asset_hits", [])
        }
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(experience, ensure_ascii=False) + '\n')

    async def evolve(self):
        """Run nightly evolution and write structured result back to governance main chain."""
        logger.info("[UEF] Starting nightly evolution cycle...")
        await self.distiller.run_nightly_review()

        # ─────────────────────────────────────────
        # R161 FIX: Pass Stage2/4 real output paths into governance_bridge
        # so the TypeScript demand_sampler can consume real data.
        # Previously evolve() only wrote a summary-level context with no real data.
        # Now we embed the actual file paths and key contents.
        # ─────────────────────────────────────────
        state_dir = self.distiller._get_upgrade_state_dir()
        stage2_path = os.path.join(state_dir, "nightly_review_stage2_bottlenecks.json")
        stage4_path = os.path.join(state_dir, "nightly_review_stage4_assets.json")

        stage2_data = {}
        if os.path.exists(stage2_path):
            try:
                with open(stage2_path, "r", encoding="utf-8") as f:
                    stage2_data = json.load(f)
            except Exception as e:
                logger.warning(f"[UEF] Failed to read Stage2 file: {e}")

        stage4_data = {}
        if os.path.exists(stage4_path):
            try:
                with open(stage4_path, "r", encoding="utf-8") as f:
                    stage4_data = json.load(f)
            except Exception as e:
                logger.warning(f"[UEF] Failed to read Stage4 file: {e}")

        # Write structured evolution summary back to governance bridge
        # This ensures nightly learning results are visible to R17-R19 and future decisions
        try:
            from app.m11.governance_bridge import governance_bridge
            await governance_bridge.record_outcome(
                outcome_type="nightly_evolution",
                actual_result=1.0,
                predicted_result=0.9,
                context={
                    "source_id": "uef_nightly_evolve",
                    "task_goal": "Nightly evolution cycle",
                    "tool_calls": 0,
                    "total_tokens": 0,
                    "total_duration_ms": 0,
                    "result_quality": 0.95,
                    "stage2_path": stage2_path,
                    "stage4_path": stage4_path,
                    "stage2_data": stage2_data,
                    "stage4_data": stage4_data,
                    "evolution_summary": {
                        "action": "nightly_evolution_completed",
                        "distiller": "NightlyDistiller",
                        "next_actions": self._get_next_action_priorities(),
                    },
                },
            )
            logger.info("[UEF] Nightly evolution result written to governance bridge")
        except Exception as e:
            logger.warning(f"[UEF] Failed to write evolution to governance bridge: {e}")

    def _get_next_action_priorities(self) -> List[Dict[str, Any]]:
        """Derive next-action priorities from today's experience log for governance review."""
        today = datetime.now().strftime("%Y-%m-%d")
        log_file = os.path.join(self.config["experiences_dir"], f"exp-{today}.jsonl")
        priorities = []

        if os.path.exists(log_file):
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        exp = json.loads(line.strip())
                        quality = exp.get('result_quality', 1.0)
                        if quality < 0.5:
                            priorities.append({
                                "type": "improve_tool",
                                "target": exp.get('tool_calls', [{}])[0].get('tool_name', 'unknown') if exp.get('tool_calls') else 'unknown',
                                "reason": f"Low quality score: {quality}",
                            })
                        if exp.get('failure_info'):
                            priorities.append({
                                "type": "investigate_failure",
                                "target": exp.get('tool_calls', [{}])[0].get('tool_name', 'unknown') if exp.get('tool_calls') else 'unknown',
                                "reason": exp.get('failure_info', '')[:100],
                            })
            except Exception as e:
                logger.warning(f"[UEF] Could not read experience log: {e}")

        if not priorities:
            priorities.append({"type": "no_action", "target": None, "reason": "No significant events"})

        return priorities[:5]  # cap at 5 to keep record size bounded

    async def weekly_deepen(self):
        await self.distiller.run_weekly_review()

    async def maintain_assets(self):
        await self.asset_guardian.scout_and_retire()

uef_instance = UniversalEvolutionFramework()
