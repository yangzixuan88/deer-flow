"""
Scrapling Adapter — web_extraction_coprocessor_for_claude_code
==============================================================

ROLE: Subordinate coprocessor serving Claude Code CLI as primary operator.

STATUS: EXPERIMENTAL_DISABLED (see ADAPTER_STATUS below)

CAPABILITY SHAPE ONLY — no Scrapling runtime/main-loop is imported or executed.

Claude Code CLI invokes Scrapling as web_extraction_coprocessor_for_claude_code.
Scrapling NEVER:
  - Accepts tasks directly from users or other sources
  - Claims task completion authority
  - Bypasses Claude Code to update M08/M07 directly

ADAPTER_STATUS: "FUTURE_COPROCESSOR_ORCHESTRATION"
  当前状态: 物理不可达（not merely disabled — unreachable by design in current arch）

  为什么不可达:
    1. claude_code_route() 是 sync 函数，其 coprocessor 分支（_route_scrapling 等）
       物理上不可达——这是架构设计，不是 bug。
    2. 即使 _route_scrapling 被调用（它永远不会被调用），request_scrapling_capability()
       是 async 函数，需要 await；但 claude_code_route 是 sync 函数，不能 await。
    3. 当前真实的执行治理通过 HarnessReviewMiddleware (OCHA L2) 实现，
       工具在执行前已经过 OCHA L2 audit。
    4. _validate_routing_context() 在工具执行后调用 claude_code_route() 作为
       "路由策略验证器"（S1 语义闭环），不是物理执行入口。

  本适配器不是"待启用的 disabled"，而是"架构中当前物理不存在的未来编排路径"。
  不建议通过补 await 来"启用"——这会引入架构混淆（sync 函数 await async 协程）。
  若未来需要 Claude Code → Scrapling 真实编排，应通过独立 async 入口实现。

CONTROLLED_EVOLVABLE:
  - Fetcher (HTTP/curl_cffi)
  - DynamicFetcher (Playwright browser rendering)
  - Spider (concurrent crawl with pause/resume)
  - Selector (adaptive DOM parsing)
  - ProxyRotator (session-capable proxy rotation)
  - ScraplingMCPServer (MCP protocol bridge)

QUARANTINED (must NOT enter execution chain):
  - StealthyFetcher (anti-bot / CAPTCHA bypass)
  - solve_cloudflare
  - hide_canvas / block_webrtc

M08回流 record shape (via claude_code_router.record_outcome_through_claude_code):
  primary_operator: "Claude Code CLI"
  supporting_capability: "Scrapling"
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("m11_scrapling_adapter")

EXTERNAL_VENDOR_PATH = "e:/OpenClaw-Base/deerflow/backend/external/Scrapling"


@dataclass
class ScraplingCapability:
    """Shape of a available Scrapling capability for routing decisions."""
    name: str
    type: str  # 'http' | 'browser' | 'crawl' | 'parse' | 'mcp'
    risk_level: str  # 'low' | 'medium' | 'high'
    governance_required: bool = True
    quarantined: bool = False


AVAILABLE_CAPABILITIES: List[ScraplingCapability] = [
    # HTTP fetcher — low risk, governance gate on first use
    ScraplingCapability(name="scrapling.Fetcher", type="http", risk_level="low"),
    # Browser rendering fetcher — medium risk, governance gate required
    ScraplingCapability(name="scrapling.DynamicFetcher", type="browser", risk_level="medium"),
    # Concurrent spider with pause/resume — medium risk
    ScraplingCapability(name="scrapling.Spider", type="crawl", risk_level="medium"),
    # Adaptive DOM parser — low risk
    ScraplingCapability(name="scrapling.Selector", type="parse", risk_level="low"),
    # Proxy rotation — medium risk (exit-node diversity)
    ScraplingCapability(name="scrapling.ProxyRotator", type="http", risk_level="medium"),
    # MCP server bridge — medium risk
    ScraplingCapability(name="scrapling.ScraplingMCPServer", type="mcp", risk_level="medium"),
]

QUARANTINED_CAPABILITIES: List[ScraplingCapability] = [
    # Anti-bot / stealth infrastructure — NEVER admit
    ScraplingCapability(name="scrapling.StealthyFetcher", type="http", risk_level="high", quarantined=True),
    ScraplingCapability(name="scrapling.solve_cloudflare", type="http", risk_level="high", quarantined=True),
    ScraplingCapability(name="scrapling.hide_canvas", type="parse", risk_level="high", quarantined=True),
    ScraplingCapability(name="scrapling.block_webrtc", type="parse", risk_level="high", quarantined=True),
]


def is_quarantined(capability_name: str) -> bool:
    """Return True if a capability is in the QUARANTINED list."""
    return any(
        q.name == capability_name or capability_name.endswith(f".{q.name.split('.')[-1]}")
        for q in QUARANTINED_CAPABILITIES
    )


async def request_scrapling_capability(
    capability_name: str,
    config: Dict[str, Any],
    governance_bridge: Any,
) -> Dict[str, Any]:
    """
    Request a Scrapling capability through governance gate.

    Returns governance decision. If approved, returns a shape descriptor
    that tells the caller HOW to invoke the capability (not the runtime itself).

    CONTROLLED_EVOLVABLE: new scraper pattern → governance_bridge.check_meta_governance
    """
    if is_quarantined(capability_name):
        logger.warning(f"[ScraplingAdapter] QUARANTINED capability requested: {capability_name}")
        return {
            "approved": False,
            "blocked": True,
            "reason": f"QUARANTINED_CAPABILITY: {capability_name} is blocked by policy",
            "quarantined": True,
        }

    # Governance gate for new capability admission
    try:
        decision = await governance_bridge.check_meta_governance({
            "decision_type": "capability_admission",
            "description": f"Scrapling capability: {capability_name}",
            "risk_level": _risk_level(capability_name),
            "stake_holders": ["governance", "M07_asset_registry"],
            "capability_name": capability_name,
            "capability_type": _capability_type(capability_name),
        })
        approved = decision.applied or not decision.blocking
    except Exception as e:
        logger.warning(f"[ScraplingAdapter] Governance check failed: {e}")
        approved = False

    return {
        "approved": approved,
        "blocked": not approved,
        "capability_name": capability_name,
        "type": _capability_type(capability_name),
        "invocation_shape": _invocation_shape(capability_name, config),
        "governance_required": True,
    }


def _risk_level(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES if c.name == capability_name), None)
    return cap.risk_level if cap else "high"


def _capability_type(capability_name: str) -> str:
    cap = next((c for c in AVAILABLE_CAPABILITIES + QUARANTINED_CAPABILITIES
                if c.name == capability_name), None)
    return cap.type if cap else "unknown"


def _invocation_shape(capability_name: str, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return the invocation SHAPE for the requested capability.
    This is a descriptor only — no actual runtime import.
    """
    short_name = capability_name.split(".")[-1]

    shapes = {
        "Fetcher": {
            "module": "scrapling.fetchers",
            "class": "Fetcher",
            "params": {
                "url": config.get("url"),
                "headers": config.get("headers", {}),
                "cookies": config.get("cookies", {}),
                "timeout": config.get("timeout", 30),
            },
            "note": "Uses curl_cffi for HTTP; use DynamicFetcher for JS-rendered pages",
        },
        "DynamicFetcher": {
            "module": "scrapling.fetchers",
            "class": "DynamicFetcher",
            "params": {
                "url": config.get("url"),
                "wait_for": config.get("wait_for", "networkidle"),
                "screenshot": config.get("screenshot", False),
            },
            "note": "Playwright-based; requires browser runtime; high resource cost",
        },
        "Spider": {
            "module": "scrapling.spiders",
            "class": "Spider",
            "params": {
                "start_urls": config.get("start_urls", []),
                "max_concurrency": config.get("max_concurrency", 5),
                "respect_robots": config.get("respect_robots", True),
            },
            "note": "Concurrent crawl engine; supports pause/resume via session_manager",
        },
        "Selector": {
            "module": "scrapling.parser",
            "class": "Selector",
            "params": {
                "html": config.get("html"),
                "selector": config.get("selector", "body"),
            },
            "note": "Adaptive DOM selector; supports xpath and css paths",
        },
        "ProxyRotator": {
            "module": "scrapling.fetchers",
            "class": "ProxyRotator",
            "params": {
                "proxy_list": config.get("proxy_list", []),
                "rotation_strategy": config.get("rotation_strategy", "round_robin"),
            },
            "note": "Session-capable proxy rotation; use with Fetcher for exit-node diversity",
        },
        "ScraplingMCPServer": {
            "module": "scrapling.core.ai",
            "class": "ScraplingMCPServer",
            "params": {
                "command": config.get("command", "uvicorn"),
                "port": config.get("port", 8765),
            },
            "note": "MCP protocol bridge; advertises tools via JSON-RPC",
        },
    }

    return shapes.get(short_name, {"error": f"Unknown capability: {capability_name}"})


def list_safe_capabilities() -> List[Dict[str, str]]:
    """List all non-quarantined Scrapling capabilities with their risk levels."""
    return [
        {"name": c.name, "type": c.type, "risk_level": c.risk_level}
        for c in AVAILABLE_CAPABILITIES
    ]


def list_quarantined_capabilities() -> List[Dict[str, str]]:
    """List all QUARANTINED Scrapling capabilities."""
    return [
        {"name": c.name, "type": c.type, "risk_level": c.risk_level}
        for c in QUARANTINED_CAPABILITIES
    ]
