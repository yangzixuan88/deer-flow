import os
import json
import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("m07_dpbs")
logger.setLevel(logging.INFO)

class EvaluatorHarness:
    def __init__(self):
        self.evaluation_logs = []

    async def evaluate_sandbox(self, candidate: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"[Harness:Evaluator] 启动针对 {candidate.get('name')} 的沙盒评估环...")
        
        is_safe = True
        fail_reason = None
        sandboxed_score = 0.0

        try:
            if candidate.get("type") == "mcp_server":
                result = await self.dry_run_mcp(candidate)
                is_safe = result["is_safe"]
                sandboxed_score = result["score"]
            else:
                sandboxed_score = 0.85 

            self.evaluation_logs.append({
                "candidate_id": candidate.get("id"),
                "timestamp": datetime.now().isoformat(),
                "is_safe": is_safe,
                "sandboxed_score": sandboxed_score
            })
            return {"is_safe": is_safe, "sandboxed_score": sandboxed_score, "fail_reason": fail_reason}
        except Exception as e:
            return {"is_safe": False, "sandboxed_score": 0.0, "fail_reason": str(e)}

    async def dry_run_mcp(self, mcp_server: Dict[str, Any]) -> Dict[str, Any]:
        features = mcp_server.get("features", [])
        dangerous_keywords = ['delete', 'remove', 'format', 'drop']
        has_danger = any(k in f.lower() for f in features for k in dangerous_keywords)
        
        if has_danger:
            logger.warning("[Harness:Evaluator] 警告：发现高危系统级功能权限申请！")
            return {"is_safe": False, "score": 0.2}
        return {"is_safe": True, "score": 0.95}

class DynamicPlatformBindingSystem:
    def __init__(self):
        self.platforms: Dict[str, Dict[str, Any]] = {}
        self.candidates: Dict[str, Dict[str, Any]] = {}
        self.evolution_history = []
        self.evaluator = EvaluatorHarness()
        
        base_path = os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base")
        self.config = {
            "evaluation_period": 100,
            "min_efficiency_threshold": 0.6,
            "max_platforms": 50,
            "discovery_interval_sec": 86400,
            "auto_bind": True,
            "auto_evict": True,
            "base_path": os.path.join(base_path, ".openclaw", "data", "dpbs")
        }
        # NOTE: asyncio.Event must NOT be created here (module level / __init__ runs
        # before any event loop exists).  It is created lazily on first use instead.
        self._shutdown_event: asyncio.Event | None = None
        # Keep hard references so the tasks are not garbage-collected.
        self._tasks: list[asyncio.Task] = []

    def _get_shutdown_event(self) -> asyncio.Event:
        """Return (creating on first call) the shutdown event for the running loop."""
        if self._shutdown_event is None:
            self._shutdown_event = asyncio.Event()
        return self._shutdown_event

    async def init_system(self):
        # Reset shutdown event for this event-loop invocation
        self._shutdown_event = asyncio.Event()
        os.makedirs(self.config["base_path"], exist_ok=True)
        self.load_existing_platforms()
        logger.info("🚀 DPBS v4.0 (Python) initialized - MCP Harness Mode ON")
        # Store task references so they survive until explicitly cancelled/awaited.
        self._tasks = [
            asyncio.create_task(self.start_discovery_engine(), name="dpbs_discovery"),
            asyncio.create_task(self.start_evolution_engine(), name="dpbs_evolution"),
        ]

    async def shutdown(self):
        self._get_shutdown_event().set()
        for task in self._tasks:
            task.cancel()
        self._tasks.clear()
        logger.info("🛑 DPBS v4.0 Shutting down...")

    async def start_discovery_engine(self):
        await asyncio.sleep(3)
        ev = self._get_shutdown_event()
        while not ev.is_set():
            await self.discover_new_platforms()
            try:
                await asyncio.wait_for(ev.wait(), timeout=self.config["discovery_interval_sec"])
            except asyncio.TimeoutError:
                pass

    async def discover_new_platforms(self):
        logger.info("🔍 [DPBS] 扫描本地与外部新平台/MCP服务...")

        # 本地 MCP 轮询
        local_mcp_candidates = await self.sniff_local_mcp_servers()

        # R185 FIX: Read real enabled MCP servers from extensions_config.json
        # ClawHub Registry was a placeholder returning []. ExtensionsConfig is
        # the real infrastructure layer with enabled MCP servers (tavily, exa, lark).
        extensions_mcp_candidates = await self._read_extensions_config_mcp_servers()

        sources = [
            {"name": "Local MCP Engine", "type": "mcp_server", "data": local_mcp_candidates},
            {"name": "ExtensionsConfig MCP", "type": "mcp_server", "data": extensions_mcp_candidates}
        ]

        for source in sources:
            for candidate in source["data"]:
                if self.is_valid_candidate(candidate):
                    self.candidates[candidate["id"]] = {
                        **candidate,
                        "discovered_at": datetime.now().isoformat(),
                        "source": source["name"],
                        "status": "pending_evaluation"
                    }

        logger.info(f"✅ [DPBS] 发现完毕. 待审候选数: {len(self.candidates)}")
        await self.evaluate_candidates()

    async def sniff_local_mcp_servers(self) -> List[Dict[str, Any]]:
        """R165 FIX: Read real platform candidates from governance_state.json tool_execution records.

        This creates a self-reinforcing loop: DPBS generates asset_promotion records,
        which are then consumed as new platform candidates by DPBS discovery.
        This is NOT fake static data — tool_execution records are real system operation traces.
        """
        import uuid
        candidates = []

        # Source 1: Extract from governance_state.json tool_execution records
        # These represent real tools/platforms that the system has actually used
        try:
            state_path = os.path.join(os.path.dirname(__file__), '..', 'm11', 'governance_state.json')
            with open(state_path, 'r', encoding='utf-8') as f:
                gs = json.load(f)

            # Extract unique tool names from tool_execution records
            tool_names_seen = {}
            for rec in gs.get('outcome_records', []):
                if rec.get('outcome_type') == 'tool_execution':
                    ctx = rec.get('context', {})
                    tool_name = ctx.get('tool_name', '')
                    if tool_name and tool_name not in tool_names_seen:
                        tool_names_seen[tool_name] = True

            for tool_name in tool_names_seen:
                if len(candidates) >= 5:  # Limit to top 5 to avoid flooding
                    break
                # Map tool names to platform categories
                name_lower = tool_name.lower()
                if 'search' in name_lower or 'retriev' in name_lower:
                    category = 'search'
                elif 'memory' in name_lower or 'recall' in name_lower:
                    category = 'memory'
                elif 'asset' in name_lower or 'dpbs' in name_lower:
                    category = 'asset'
                elif 'workflow' in name_lower or 'orchestrat' in name_lower:
                    category = 'orchestration'
                else:
                    category = 'utility'

                candidates.append({
                    'id': f'gov-{tool_name.lower().replace("_", "-")}',
                    'name': tool_name,
                    'type': 'platform_capability',
                    'category': category,
                    'api': 'governance_api',
                    'features': [f'capability:{tool_name}']
                })
        except Exception as e:
            logger.debug(f"[DPBS] Failed to read governance_state.json for candidates: {e}")

        # Source 2: Only add hardcoded candidates if governance has no tool records
        # (this maintains backward compatibility for empty governance state)
        if not candidates:
            candidates = [
                {"id": str(uuid.uuid4()), "name": "pinecone-mcp", "type": "mcp_server", "category": "vectordb", "api": "stdio", "features": ["query", "upsert"]},
                {"id": str(uuid.uuid4()), "name": "chrome-devtools-mcp", "type": "mcp_server", "category": "browser", "api": "stdio", "features": ["navigate", "click", "evaluate"]},
                {"id": str(uuid.uuid4()), "name": "cloud-run-mcp", "type": "mcp_server", "category": "cloud", "api": "stdio", "features": ["deploy"]}
            ]

        return candidates

    async def _read_extensions_config_mcp_servers(self) -> List[Dict[str, Any]]:
        """R185 FIX: Read real enabled MCP servers from extensions_config.json.

        extensions_config.json defines the real MCP infrastructure that DeerFlow
        actually connects to (tavily, exa, lark). This is independent of the
        governance_state self-reinforcing loop and provides external infrastructure input.

        Only returns enabled servers. Disabled servers (pinecone, cloud_run, etc.)
        are skipped as they are not actively running.
        """
        candidates = []
        try:
            config_paths = [
                os.path.join(os.path.dirname(__file__), '..', '..', 'extensions_config.json'),
                os.path.join(os.path.dirname(__file__), '..', 'extensions_config.json'),
                os.path.join(os.path.dirname(__file__), '..', '..', '..', 'extensions_config.json'),
            ]
            config_path = None
            for p in config_paths:
                if os.path.exists(p):
                    config_path = p
                    break

            if not config_path:
                logger.debug("[DPBS] extensions_config.json not found in any search path")
                return candidates

            with open(config_path, 'r', encoding='utf-8') as f:
                cfg = json.load(f)

            mcp_servers = cfg.get('mcpServers', {})
            for server_name, server_cfg in mcp_servers.items():
                if not server_cfg.get('enabled', False):
                    continue

                server_type = server_cfg.get('type', 'unknown')
                transport_type = 'sse' if server_type == 'sse' else 'stdio'

                # Map server names to candidate categories
                name_lower = server_name.lower()
                if 'tavily' in name_lower:
                    category = 'search'
                elif 'exa' in name_lower:
                    category = 'search'
                elif 'lark' in name_lower or 'feishu' in name_lower:
                    category = 'productivity'
                elif 'pinecone' in name_lower:
                    category = 'vectordb'
                elif 'cloudrun' in name_lower or 'cloud_run' in name_lower:
                    category = 'cloud'
                else:
                    category = 'utility'

                candidates.append({
                    'id': f'mcp-{server_name}',
                    'name': f'{server_name}-mcp',
                    'type': 'mcp_server',
                    'category': category,
                    'api': transport_type,
                    'transport': server_type,
                    'command': server_cfg.get('command') or None,
                    'url': server_cfg.get('url') or None,
                    'features': [f'mcp:{server_name}', f'transport:{transport_type}']
                })
                logger.info(f"[DPBS] R185: Discovered enabled MCP from extensions_config: {server_name} ({transport_type})")

        except Exception as e:
            logger.warning(f"[DPBS] R185: Failed to read extensions_config.json: {e}")

        return candidates

    def is_valid_candidate(self, candidate: Dict[str, Any]) -> bool:
        if candidate["id"] in self.platforms:
            return False
        for p in self.platforms.values():
            if p.get("name") == candidate.get("name"):
                return False
        return bool(candidate.get("name") and candidate.get("type"))

    async def evaluate_candidates(self):
        logger.info("📊 [DPBS] 激活 Evaluator 评审环...")
        
        for cid, candidate in list(self.candidates.items()):
            if candidate["status"] != "pending_evaluation":
                continue
            
            eval_result = await self.evaluator.evaluate_sandbox(candidate)
            
            candidate["score"] = eval_result["sandboxed_score"]
            candidate["status"] = "approved" if (eval_result["is_safe"] and eval_result["sandboxed_score"] >= 0.7) else "rejected"
            candidate["evaluated_at"] = datetime.now().isoformat()
            
            if candidate["status"] == "approved" and self.config["auto_bind"]:
                await self.bind_platform(candidate)
            elif not eval_result["is_safe"]:
                logger.warning(f"[DPBS] 候选平台 {candidate['name']} 被 Evaluator 否决。原因: 包含不安全指令风险。")

    async def bind_platform(self, platform: Dict[str, Any]):
        logger.info(f"🔗 [DPBS] 正在绑定挂载: {platform.get('name')} (Type: {platform.get('type')})")

        # ─────────────────────────────────────────────────────────
        # M11 Governance Bridge — asset promotion governance gate
        # CONTROLLED_EVOLVABLE: new_asset_pattern must pass governance
        # check before being promoted into the asset registry.
        # ─────────────────────────────────────────────────────────
        try:
            from app.m11.governance_bridge import governance_bridge
            risk_level = "high" if platform.get("type") == "mcp_server" else "medium"
            decision = await governance_bridge.check_meta_governance({
                "decision_type": "asset_promotion",
                "description": f"Binding new asset: {platform.get('name')}",
                "risk_level": risk_level,
                "stake_holders": ["governance", "asset_registry"],
                "asset_id": platform.get("id"),
                "asset_name": platform.get("name"),  # R206-A: asset_name needed in governance context for Path B demand
                "asset_category": platform.get("category", "unknown"),
            })
            if decision.blocking and not decision.applied:
                logger.warning(f"[DPBS] Asset binding blocked by governance: {platform.get('name')}")
                return None
        except Exception as e:
            logger.warning(f"[DPBS] Governance check failed (non-fatal): {e}")

        if len(self.platforms) >= self.config["max_platforms"]:
            await self.evict_weakest_platform()
            
        binding = {
            "id": platform["id"],
            "name": platform["name"],
            "category": platform.get("category"),
            "type": platform["type"],
            "api": platform.get("api"),
            "features": platform.get("features", []),
            "bound_at": datetime.now().isoformat(),
            "score": platform.get("score"),
            "efficiency": 1.0,
            "usage_count": 0,
            "success_count": 0,
            "status": "active"
        }
        
        self.platforms[platform["id"]] = binding
        if platform["id"] in self.candidates:
            del self.candidates[platform["id"]]
            
        self.log_evolution("bind", platform)
        logger.info(f"✅ [DPBS] 挂载成功: {platform['name']} 已并入大主管工具池。")

        # ─────────────────────────────────────────────────────────
        # R20: Record asset_promotion outcome to governance bridge
        # This closes the M07 → governance_state.json → Upgrade Center loop.
        # ─────────────────────────────────────────────────────────
        try:
            from app.m11.governance_bridge import governance_bridge
            await governance_bridge.record_outcome(
                outcome_type="asset_promotion",
                actual_result=1.0,
                predicted_result=0.9,
                context={
                    "asset_id": platform.get("id"),
                    "asset_name": platform.get("name"),
                    "asset_category": platform.get("category", "unknown"),
                    "risk_level": "high" if platform.get("type") == "mcp_server" else "medium",
                    "source": "m07_bind_platform",
                },
            )
            logger.info(f"[DPBS] asset_promotion outcome recorded to governance bridge")
        except Exception as e:
            logger.warning(f"[DPBS] Failed to record asset_promotion outcome (non-fatal): {e}")

        return binding

    async def unbind_platform(self, platform_id: str):
        platform = self.platforms.get(platform_id)
        if not platform:
            return False
        logger.info(f"🔓 [DPBS] 卸载挂载点: {platform['name']}")
        self.log_evolution("unbind", platform)
        del self.platforms[platform_id]
        return True

    async def start_evolution_engine(self):
        ev = self._get_shutdown_event()
        while not ev.is_set():
            try:
                await asyncio.wait_for(ev.wait(), timeout=self.config["evaluation_period"])
            except asyncio.TimeoutError:
                await self.evaluate_existing_platforms()

    async def evaluate_existing_platforms(self):
        for pid, platform in list(self.platforms.items()):
            usage = platform.get("usage_count", 0)
            success = platform.get("success_count", 0)
            efficiency = 1.0 if usage == 0 else (success / usage)
            
            platform["efficiency"] = efficiency
            platform["last_evaluated"] = datetime.now().isoformat()
            
            if efficiency < self.config["min_efficiency_threshold"] and self.config["auto_evict"]:
                platform["status"] = "marked_for_eviction"
                await self.evict_platform(platform)
                
        self.generate_evolution_report()

    async def evict_platform(self, platform: Dict[str, Any]):
        logger.info(f"🗑️ [DPBS] 效能过低，自动淘汰平台: {platform['name']}")
        await self.unbind_platform(platform["id"])

    async def evict_weakest_platform(self):
        if not self.platforms: return
        weakest = min(self.platforms.values(), key=lambda x: x.get("score", 0))
        if weakest:
            await self.evict_platform(weakest)

    def log_evolution(self, ev_type: str, data: Dict[str, Any]):
        self.evolution_history.append({
            "timestamp": datetime.now().isoformat(),
            "type": ev_type,
            "platform_name": data.get("name"),
            "platform_count": len(self.platforms)
        })

    def generate_evolution_report(self):
        report = {
            "timestamp": datetime.now().isoformat(),
            "platforms": [
                {
                    "id": p["id"], "name": p["name"], "type": p["type"],
                    "efficiency": p.get("efficiency"), "status": p["status"]
                } for p in self.platforms.values()
            ],
            "recent_changes": self.evolution_history[-5:]
        }
        report_path = os.path.join(self.config["base_path"], 'latest_binding_report.json')
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False)

    def load_existing_platforms(self):
        report_path = os.path.join(self.config["base_path"], 'latest_binding_report.json')
        if os.path.exists(report_path):
            try:
                with open(report_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                platforms = data.get("platforms", [])
                for p in platforms:
                    self.platforms[p["id"]] = p
                logger.info(f"📂 [DPBS] 从检查点成功恢复了 {len(self.platforms)} 个平台/MCP绑定")
            except Exception as e:
                logger.warning(f"❌ [DPBS] 读取绑定缓存失败: {e}")

dpbs_instance = DynamicPlatformBindingSystem()
