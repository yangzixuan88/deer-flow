from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .models import NightlyReviewItem


def mode_decision_to_review_item(
    mode_result: Any,
    *,
    thread_id: str | None = None,
    run_id: str | None = None,
    user_id: str | None = None,
    reason: str | None = None,
    source: str = "mode_router",
    payload_summary: str = "",
) -> NightlyReviewItem | None:
    """Convert a ModeDecision with nightly_review=True into a NightlyReviewItem.

    This function is the integration point between mode_router and the
    nightly_review pipeline. It is called by the caller of ensure_mode_decision(),
    NOT by mode_router itself.

    mode_router.py is NEVER modified by this function.

    Parameters
    ----------
    mode_result:
        A ModeDecision object or dict with a `result_sink` attribute/field.
        If it has result_sink.nightly_review == True, an item is returned.
        Otherwise returns None.
    thread_id, run_id, user_id:
        Optional context IDs extracted from the run payload.
    reason:
        Optional override for the review reason.
        If not provided, extracted from mode_result.decision_reason.
    source:
        How this item was created:
        - "mode_router": from ensure_mode_decision with AUTONOMOUS_AGENT keyword
        - "explicit_flag": passed directly with nightly_review=True
        - "api": created via API call
    payload_summary:
        Optional truncated input text for the review item.

    Returns
    -------
    NightlyReviewItem | None
        A new item, or None if nightly_review flag is False or absent.
    """
    from .models import NightlyReviewItem

    nightly_review = _get_nightly_review_flag(mode_result)
    if not nightly_review:
        return None

    mode_value = _get_mode_value(mode_result)
    decision_reason = reason or _get_decision_reason(mode_result)
    created_at = _get_created_at(mode_result)
    effective_thread_id = thread_id or _get_thread_id(mode_result)
    effective_run_id = run_id or _get_run_id(mode_result)

    return NightlyReviewItem.new(
        thread_id=effective_thread_id,
        run_id=effective_run_id,
        user_id=user_id,
        mode=mode_value,
        reason=decision_reason,
        created_at=created_at,
        source=source,
        payload_summary=payload_summary,
    )


# -------------------------------------------------------------------------
# Private extraction helpers — handle both dict and object modes
# -------------------------------------------------------------------------


def _get_nightly_review_flag(obj: Any) -> bool:
    try:
        if isinstance(obj, dict):
            rs = obj.get("result_sink", {})
            return bool(rs.get("nightly_review", False))
        return bool(obj.result_sink.nightly_review)
    except Exception:
        return False


def _get_mode_value(obj: Any) -> str:
    try:
        if isinstance(obj, dict):
            mode = obj.get("selected_mode", "")
            return getattr(mode, "value", str(mode))
        return getattr(obj.selected_mode, "value", str(obj.selected_mode))
    except Exception:
        return "unknown"


def _get_decision_reason(obj: Any) -> str:
    try:
        if isinstance(obj, dict):
            return str(obj.get("decision_reason", ""))
        return str(getattr(obj, "decision_reason", ""))
    except Exception:
        return ""


def _get_created_at(obj: Any) -> str:
    try:
        if isinstance(obj, dict):
            return str(obj.get("created_at", ""))
        return str(getattr(obj, "created_at", ""))
    except Exception:
        return ""


def _get_thread_id(obj: Any) -> str | None:
    try:
        if isinstance(obj, dict):
            return obj.get("context_id") or None
        return getattr(obj, "context_id", None) or None
    except Exception:
        return None


def _get_run_id(obj: Any) -> str | None:
    try:
        if isinstance(obj, dict):
            return obj.get("request_id") or None
        return getattr(obj, "request_id", None) or None
    except Exception:
        return None
