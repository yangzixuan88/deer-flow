import sys
import logging
import hashlib
import json
from collections import OrderedDict
from typing import Dict, Any, List

logger = logging.getLogger("m09_toas")
logger.setLevel(logging.INFO)

class LRUCache:
    """基于内存的 LRU Cache 回退缓存机制 (最小 MVP 投产)"""
    def __init__(self, capacity: int):
        self.cache = OrderedDict()
        self.capacity = capacity

    def get(self, key: str):
        if key not in self.cache:
            return None
        self.cache.move_to_end(key)
        return self.cache[key]

    def put(self, key: str, value: Any):
        if key in self.cache:
            self.cache.move_to_end(key)
        self.cache[key] = value
        if len(self.cache) > self.capacity:
            self.cache.popitem(last=False)

class TokenOptimizer:
    """M09 全局 Token 统筹优化器 (TOAS)"""
    def __init__(self):
        self.score = 100
        self.history = []
        self.cache = LRUCache(capacity=500)  # 本地 LRU 缓存保护
        self.config = {
            "enable_compression": True,
            "cache_enabled": True,
            "max_history_size": 1000,
            "evolution_interval": 100
        }
        self.stats = {
            "total_tokens": 0,
            "total_interactions": 0,
            "cache_hits": 0,
            "average_efficiency": 0.0
        }

    def _generate_cache_key(self, query: str, context_hash: str) -> str:
        s = f"{query}_{context_hash}"
        return hashlib.md5(s.encode('utf-8')).hexdigest()

    async def think_before_act(self, query: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """发往模型前置调度，决定直接回传缓存或放行"""
        context = context or {}
        
        # 1. 检查缓存
        if self.config["cache_enabled"]:
            context_str = json.dumps(context, sort_keys=True)
            ctx_hash = hashlib.md5(context_str.encode('utf-8')).hexdigest()
            cache_key = self._generate_cache_key(query, ctx_hash)
            cached_res = self.cache.get(cache_key)
            if cached_res:
                self.stats["cache_hits"] += 1
                self.reward("cache_hit")
                logger.info(f"[TOAS] 拦截击中缓存，直接返回. Score={self.score}")
                return {"use_cache": True, "data": cached_res, "cache_key": cache_key}
                
            return {"use_cache": False, "cache_key": cache_key}
            
        return {"use_cache": False, "cache_key": None}

    def save_to_cache(self, cache_key: str, data: Any):
        if cache_key and self.config["cache_enabled"]:
            self.cache.put(cache_key, data)

    def compress_context(self, history: List[Dict[str, Any]], max_tokens: int = 2000) -> List[Dict[str, Any]]:
        """实现上下文智能压缩策略（超限自动削减并保护首尾）"""
        if not history:
            return history
            
        estimated_tokens = sum(len(str(msg.get("content", ""))) * 1.5 for msg in history)
        if estimated_tokens <= max_tokens or not self.config["enable_compression"]:
            return history

        logger.info(f"[TOAS] Context exceeds {max_tokens} threshold ({estimated_tokens}), enabling aggressive compression...")
        
        # 策略: 保护第一条(SYSTEM)和最后两条(RECENT)，中间的折叠
        if len(history) <= 3:
            # 只有 3 条但超标，暴力截断内容
            for h in history:
                content = str(h.get("content", ""))
                if len(content) > 500:
                    keep = 200
                    h["content"] = content[:keep] + " \n...[TOAS Compressed]... \n" + content[-keep:]
            return history
            
        compressed = [history[0]]  # System prompt
        
        # 中间的被舍弃或高度浓缩 (MVP 这里选择直接移除多余中间以防溢出)
        compressed.append({"role": "system", "content": "...[历史对话被主动压缩]..."})
        
        compressed.extend(history[-2:])  # Last user and assistant
        return compressed

    def reward(self, rtype: str):
        rewards = {"high_efficiency": 10, "cache_hit": 5, "context_compression": 3}
        self.score += rewards.get(rtype, 1)

    def penalize(self, ptype: str):
        penalties = {"redundant_fetch": -3, "cache_miss": -2, "over_token_budget": -5}
        self.score += penalties.get(ptype, -1)

    def self_monitor(self, used_tokens: int, quality_score: float = 0.8):
        """挂接到请求后的回调中监控积分成本"""
        self.stats["total_tokens"] += used_tokens
        self.stats["total_interactions"] += 1
        efficiency = (quality_score * 100) / max(1, used_tokens)
        
        if efficiency >= 0.8:
            self.reward("high_efficiency")
        elif efficiency < 0.4:
            self.penalize("over_token_budget")
            
        logger.debug(f"[TOAS] 监控效能:{efficiency:.2f}, 当前总积分:{self.score}")

toas_instance = TokenOptimizer()
