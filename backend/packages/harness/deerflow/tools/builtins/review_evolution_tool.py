from typing import List, Dict, Any, Optional
from langchain_core.tools import tool
from deerflow.assets.asset_manager import AssetManager, DigitalAsset
import logging

logger = logging.getLogger(__name__)

@tool
def list_pending_assets() -> str:
    """列出当前处于'待审核'状态的高价值资产(T1/T2)。
    
    这些资产由夜间复盘引擎识别，代表了系统进化的潜在机会。
    """
    am = AssetManager()
    all_assets = am.list_assets()
    pending = [a for a in all_assets if a.get("status") == "PENDING_REVIEW"]
    
    if not pending:
        return "✨ 当前没有待审核的进化资产。"
        
    res = ["### 🕒 待审核资产列表 (Phase 4 进化管理)"]
    for a in pending:
        res.append(f"- **ID**: `{a['id']}` | **名称**: `{a['name']}` | **分类**: `{a['category']}` | **等级**: `{a['tier']}` | **总分**: `{a.get('s_total', 0):.1f}`")
    
    res.append("\n使用 `approve_asset` 或 `reject_asset` 来决定这些资产的命运。")
    return "\n".join(res)

@tool
def approve_asset(asset_id: str) -> str:
    """批准一个处于 PENDING 状态的资产，使其正式成为系统的核心智力资产。
    
    Args:
        asset_id: 资产的唯一标识符。
    """
    am = AssetManager()
    asset_data = am.get_asset(asset_id)
    
    if not asset_data:
        return f"❌ 找不到 ID 为 `{asset_id}` 的资产。"
        
    if asset_data.get("status") != "PENDING_REVIEW":
        return f"⚠️ 资产 `{asset_id}` 的当前状态为 `{asset_data.get('status')}`，无需批准。"
        
    # 构建新对象并更新状态
    asset = DigitalAsset(
        id=asset_data["id"],
        name=asset_data["name"],
        category=asset_data["category"],
        content=asset_data["content"],
        metadata=asset_data.get("metadata"),
        scoring=asset_data.get("scoring"),
        status="APPROVED"
    )
    
    am.register_asset(asset)
    logger.info(f"User APPROVED asset evolution: {asset_id}")
    return f"✅ 资产 `{asset_data['name']}` ({asset_data['tier']}) 已成功批准并归档到系统核心资产库。"

@tool
def reject_asset(asset_id: str, reason: Optional[str] = None) -> str:
    """拒绝一个资产的进化提议，将其降级或标记为不通过。
    
    Args:
        asset_id: 资产的唯一标识符。
        reason: 可选的拒绝原因。
    """
    am = AssetManager()
    asset_data = am.get_asset(asset_id)
    
    if not asset_data:
        return f"❌ 找不到 ID 为 `{asset_id}` 的资产。"
        
    # 更新状态为 REJECTED
    asset = DigitalAsset(
        id=asset_data["id"],
        name=asset_data["name"],
        category=asset_data["category"],
        content=asset_data["content"],
        metadata=asset_data.get("metadata"),
        scoring=asset_data.get("scoring"),
        status="REJECTED"
    )
    
    am.register_asset(asset)
    logger.info(f"User REJECTED asset evolution: {asset_id}. Reason: {reason}")
    return f"❌ 已打回资产 `{asset_data['name']}` 的进化提议。状态已更新为 REJECTED。"
