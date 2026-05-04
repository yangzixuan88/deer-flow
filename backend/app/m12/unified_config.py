import json
import yaml
import os
import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)

# Use OPENCLAW_BASE env var so the path is correct on Windows (HOME is not set by default).
# Falls back to the canonical project root if the variable is absent.
_OPENCLAW_BASE = os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base")
DEERFLOW_BACKEND_DIR = os.path.join(_OPENCLAW_BASE, "deerflow", "backend")

# All path definitions
EXTENSIONS_CONFIG_PATH = os.path.join(DEERFLOW_BACKEND_DIR, "extensions_config.json")
GATEWAY_YAML_PATH = os.path.join(_OPENCLAW_BASE, ".openclaw", "config", "gateway.yaml")
NODE_YAML_PATH = os.path.join(_OPENCLAW_BASE, ".openclaw", "config", "node.yaml")

class UnifiedConfig:
    """M12: 大一统配置中心，实现全局18项阈值参数+各路配置归口。"""
    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UnifiedConfig, cls).__new__(cls)
            cls._instance._load_all()
        return cls._instance

    def _load_all(self):
        """同时加载原有的多个配置到统一内存树中，并且初始化默认的18参数"""
        self._config = {
            "mcp": {},
            "gateway": {},
            "node": {},
            "thresholds": self._get_default_18_thresholds()
        }

        # Load JSON config
        if os.path.exists(EXTENSIONS_CONFIG_PATH):
            try:
                with open(EXTENSIONS_CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self._config["mcp"] = data.get("mcpServers", {})
            except Exception as e:
                logger.error(f"Failed to load {EXTENSIONS_CONFIG_PATH}: {e}")

        # Load gateway.yaml
        if os.path.exists(GATEWAY_YAML_PATH):
            try:
                with open(GATEWAY_YAML_PATH, "r", encoding="utf-8") as f:
                    self._config["gateway"] = yaml.safe_load(f) or {}
            except Exception as e:
                logger.error(f"Failed to load {GATEWAY_YAML_PATH}: {e}")

        # Load node.yaml
        if os.path.exists(NODE_YAML_PATH):
             try:
                 with open(NODE_YAML_PATH, "r", encoding="utf-8") as f:
                     self._config["node"] = yaml.safe_load(f) or {}
             except Exception as e:
                 logger.error(f"Failed to load {NODE_YAML_PATH}: {e}")
                 
        logger.info("M12 - All configurations merged into UnifiedConfig successfully.")

    def _get_default_18_thresholds(self) -> Dict[str, Any]:
        """原18个阈值关键参数"""
        return {
            "retrieval_threshold": 0.85,
            "promote_min_count": 3,
            "promote_min_success": 0.80,
            "clarity_threshold": 0.85,
            "max_questions": 4,
            "timeout_per_question": 120,
            "cancel_window": 300,
            "llm_judge_threshold": 0.70,
            "max_retry": 3,
            "gepa_improve_threshold": 0.05,
            "heartbeat_interval_seconds": 300,
            "nightly_review_cron": "0 2 * * *",
            "weekly_review_cron": "0 1 * * 0",
            "search_timeout_seconds": 30,
            "aal_default_budget": 1.0,
            "asset_watch_period_usable_days": 7,
            "asset_watch_period_quality_days": 14,
            "optimizer_shrink_threshold": 0.80
        }

    def get(self, key_path: str, default: Any = None) -> Any:
        """支持诸如 'thresholds.retrieval_threshold' 的点分嵌套获取"""
        keys = key_path.split(".")
        val = self._config
        try:
            for k in keys:
                val = val[k]
            return val
        except (KeyError, TypeError):
            return default

    def dump(self) -> str:
        """查看全量配置的 json"""
        return json.dumps(self._config, indent=2, ensure_ascii=False)

if __name__ == "__main__":
    uc = UnifiedConfig()
    print("M12 Unified Config OK. Threshold loaded: ", uc.get("thresholds.clarity_threshold"))
    # print(uc.dump())
