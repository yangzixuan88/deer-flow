import os
import json
import logging
import traceback
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("m03_shars")
logger.setLevel(logging.INFO)

class SelfHardeningSystem:
    """M03 自我加固与自主修复系统 (SHARS)"""
    def __init__(self):
        self.components = {}
        self.vulnerabilities = []
        self.repair_log = []
        
        base_path = os.environ.get("OPENCLAW_BASE", r"E:\OpenClaw-Base")
        self.report_dir = os.path.join(base_path, "04-MEMORY-BANK", "hardening-reports")
        os.makedirs(self.report_dir, exist_ok=True)
        
    async def init_system(self):
        logger.info("🔒 SHARS V4.0 (Python) initialized")
        
    async def check_logs_for_anomalies(self):
        """由 M05 定期调用的自检扫描 (模拟防卫)"""
        logger.debug("[SHARS] 定期扫描异常系统日志，判断组件健康...")
        # 实际投产可分析 logs/app.log 寻找 Timeout 与 ERROR
        if self.vulnerabilities:
            logger.warning(f"[SHARS] 侦测到未解决的弱点事件数量: {len(self.vulnerabilities)}")
            
    def handle_global_exception(self, exc: Exception, scope_info: str = "Unknown Context"):
        """作为全局异常拦截器的回调"""
        logger.error(f"💥 [SHARS] 侦测到全局崩溃异常: {str(exc)}")
        
        analysis = self._analyze_crash(exc)
        
        event = {
            "timestamp": datetime.now().isoformat(),
            "type": analysis["type"],
            "scope": scope_info,
            "error_message": str(exc),
            "stack_trace": traceback.format_exc()
        }
        
        self.vulnerabilities.append(event)
        self._record_vulnerability_incident(event)
        
    def _analyze_crash(self, exc: Exception) -> Dict[str, Any]:
        """识别由于网络超时、断连引起的特征"""
        error_msg = str(exc)
        if "timeout" in error_msg.lower():
            return {"type": "timeout", "fixable": True}
        if "refused" in error_msg.lower() or "ECONNREFUSED" in error_msg:
            return {"type": "connection_error", "fixable": False}
        if "not found" in error_msg.lower() or "enoent" in error_msg.lower():
            return {"type": "file_not_found", "fixable": True}
        if "mcp" in error_msg.lower():
            return {"type": "mcp_tool_fail", "fixable": True}
            
        return {"type": "unknown", "fixable": False}

    def _record_vulnerability_incident(self, event: Dict[str, Any]):
        """生成安全防卫记录"""
        report_file = os.path.join(self.report_dir, f"hardening-{datetime.now().strftime('%Y%m%d')}.json")
        try:
            records = []
            if os.path.exists(report_file):
                with open(report_file, 'r', encoding='utf-8') as f:
                    records = json.load(f)
            records.append(event)
            with open(report_file, 'w', encoding='utf-8') as f:
                json.dump(records, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"[SHARS] 无法回写防卫日志: {e}")

shars_instance = SelfHardeningSystem()
