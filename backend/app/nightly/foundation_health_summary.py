"""Read-only Nightly Foundation summary and Feishu payload projection.

This module formats a NightlyFoundationHealthReview for users/operators and
projects a Feishu/Lark card payload. It never sends network requests, never
writes action queues, and never executes remediation.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.nightly.foundation_health_review import (
    DEFAULT_SAMPLE_PATH as DEFAULT_REVIEW_SAMPLE_PATH,
    REPORT_DIR,
)


SUMMARY_AUDIENCES = {"user_brief", "operator_detail", "feishu_card", "machine_json", "unknown"}
SUMMARY_SECTION_TYPES = {
    "headline",
    "severity_overview",
    "domain_summary",
    "critical_actions",
    "high_priority_actions",
    "blocked_actions",
    "diagnostic_findings",
    "next_step",
    "warnings",
    "unknown",
}
FEISHU_PAYLOAD_STATUSES = {
    "projection_only",
    "ready_to_send",
    "blocked_no_webhook",
    "blocked_by_policy",
    "unknown",
}

DEFAULT_SUMMARY_SAMPLE_PATH = REPORT_DIR / "R241-8B_NIGHTLY_FEISHU_SUMMARY_SAMPLE.json"

SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4, "unknown": 5}
PERMISSION_RANK = {
    "forbidden_auto": 0,
    "requires_user_confirmation": 1,
    "requires_rollback": 2,
    "requires_backup": 3,
    "report_only": 4,
    "auto_allowed_low_risk": 5,
    "unknown": 6,
}
PRIORITY_KEYWORDS = {
    "prompt": 0,
    "rollback": 0,
    "tool": 1,
    "level_3": 1,
    "rtcm": 2,
    "unknown_rtcm": 2,
    "memory": 3,
    "queue": 4,
    "mismatch": 4,
}


@dataclass
class NightlySummarySection:
    section_id: str
    section_type: str
    title: str
    severity: Optional[str] = None
    content: str = ""
    items: List[Dict[str, Any]] = field(default_factory=list)
    source_signal_ids: List[str] = field(default_factory=list)
    source_action_candidate_ids: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class NightlyReadableSummary:
    summary_id: str
    generated_at: str
    audience: str
    title: str
    headline: str
    severity_counts: Dict[str, int]
    critical_count: int
    high_count: int
    action_candidate_count: int
    requires_confirmation_count: int
    blocked_high_risk_count: int
    sections: List[Dict[str, Any]]
    warnings: List[str] = field(default_factory=list)


@dataclass
class FeishuCardPayloadProjection:
    payload_id: str
    generated_at: str
    status: str
    title: str
    template: str
    card_json: Dict[str, Any]
    source_review_id: Optional[str]
    send_allowed: bool = False
    send_blocked_reason: str = "projection_only_no_webhook_call"
    webhook_required: bool = True
    warnings: List[str] = field(default_factory=list)


def load_latest_nightly_review_sample(path: Optional[str] = None) -> Dict[str, Any]:
    target = Path(path) if path else DEFAULT_REVIEW_SAMPLE_PATH
    warnings: List[str] = []
    if not target.exists():
        return {"exists": False, "review": {}, "source_path": str(target), "warnings": [f"missing_review_sample:{target}"]}
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"exists": True, "review": {}, "source_path": str(target), "warnings": [f"malformed_review_sample:{exc}"]}
    review = data.get("review") if isinstance(data, dict) else None
    if not isinstance(review, dict):
        warnings.append("review_payload_missing_or_invalid")
        review = {}
    return {"exists": True, "review": review, "source_path": str(target), "warnings": warnings}


def summarize_review_for_user(review: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    review = _review_dict(review, warnings)
    severity_counts = _severity_counts(review)
    critical = int(review.get("critical_count") or severity_counts.get("critical", 0))
    high = int(review.get("high_count") or severity_counts.get("high", 0))
    actions = review.get("action_candidates") or []
    top_actions = select_top_action_candidates(review, max_items=8)
    domain_summary = summarize_review_by_domain(review)
    blocked_actions = [action for action in actions if action.get("permission") == "forbidden_auto"]
    confirmation_actions = [action for action in actions if action.get("requires_user_confirmation")]

    headline = (
        f"Nightly Foundation Health Review: critical={critical}, high={high}, "
        f"actions={review.get('action_candidate_count', len(actions))}, "
        f"blocked={review.get('blocked_high_risk_count', len(blocked_actions))}. "
        "本摘要为 projection，不会自动修复。"
    )
    sections = [
        _section(
            "headline",
            "总体结论",
            headline,
            severity="critical" if critical else "high" if high else "medium",
        ),
        _section(
            "severity_overview",
            "风险分级",
            f"critical={critical}, high={high}, counts={severity_counts}",
            items=[{"severity": key, "count": value} for key, value in severity_counts.items()],
        ),
        _section(
            "critical_actions",
            "Critical Signals",
            "最高风险信号必须人工审查，不会自动执行。",
            items=_compact_signals(_signals_by_severity(review, "critical"), 5),
        ),
        _section(
            "high_priority_actions",
            "High Signals",
            "高风险信号需要备份、回滚或确认策略。",
            items=_compact_signals(_signals_by_severity(review, "high"), 5),
        ),
        _section(
            "blocked_actions",
            "Blocked Actions",
            "forbidden_auto action candidates 仅提示，不会执行。",
            items=_compact_actions(blocked_actions, 5),
            source_action_candidate_ids=[str(action.get("action_candidate_id")) for action in blocked_actions[:5]],
        ),
        _section(
            "domain_summary",
            "Domain Summary",
            "按 domain 聚合的 signal 与 action 状态。",
            items=domain_summary.get("domains", []),
        ),
        _section(
            "next_step",
            "下一步建议",
            "进入 R241-9A Foundation Integration Readiness Review，审查哪些 wrapper 可进入只读集成准备。",
        ),
    ]

    summary = asdict(
        NightlyReadableSummary(
            summary_id=_make_id("nightly_summary", review.get("review_id"), "user_brief"),
            generated_at=_now(),
            audience="user_brief",
            title="Nightly Foundation Health Review Summary",
            headline=headline,
            severity_counts=severity_counts,
            critical_count=critical,
            high_count=high,
            action_candidate_count=int(review.get("action_candidate_count") or len(actions)),
            requires_confirmation_count=int(review.get("requires_confirmation_count") or len(confirmation_actions)),
            blocked_high_risk_count=int(review.get("blocked_high_risk_count") or len(blocked_actions)),
            sections=sections,
            warnings=_dedupe(warnings + top_actions.get("warnings", []) + domain_summary.get("warnings", [])),
        )
    )
    summary["top_action_candidates"] = top_actions
    return summary


def summarize_review_by_domain(review: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    review = _review_dict(review, warnings)
    signals = review.get("signals") or []
    actions = review.get("action_candidates") or []
    domains = ["truth_state", "queue_sandbox", "memory", "asset", "mode", "tool_runtime", "prompt", "rtcm"]
    grouped_signals: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    grouped_actions: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        grouped_signals[str(signal.get("domain") or "unknown")].append(signal)
    for action in actions:
        grouped_actions[str(action.get("domain") or "unknown")].append(action)

    rows = []
    for domain in domains:
        domain_signals = grouped_signals.get(domain, [])
        domain_actions = grouped_actions.get(domain, [])
        sev = Counter(str(signal.get("severity") or "unknown") for signal in domain_signals)
        signal_types = Counter(str(signal.get("signal_type") or "unknown") for signal in domain_signals)
        action_types = Counter(str(action.get("action_type") or "unknown") for action in domain_actions)
        rows.append(
            {
                "domain": domain,
                "signal_count": len(domain_signals),
                "critical_count": sev.get("critical", 0),
                "high_count": sev.get("high", 0),
                "medium_count": sev.get("medium", 0),
                "top_signal_types": _top_counts(signal_types, 5),
                "recommended_action_types": _top_counts(action_types, 5),
                "blocked_count": sum(1 for action in domain_actions if action.get("permission") == "forbidden_auto"),
                "requires_confirmation_count": sum(1 for action in domain_actions if action.get("requires_user_confirmation")),
            }
        )
    return {"domains": rows, "warnings": warnings}


def select_top_action_candidates(review: Dict[str, Any], max_items: int = 10) -> Dict[str, Any]:
    warnings: List[str] = []
    review = _review_dict(review, warnings)
    try:
        limit = max(0, min(int(max_items), 50))
    except Exception:
        limit = 10
        warnings.append("invalid_max_items_defaulted")
    actions = list(review.get("action_candidates") or [])
    actions.sort(key=_action_sort_key)
    return {"selected_count": min(limit, len(actions)), "actions": _compact_actions(actions[:limit], limit), "warnings": warnings}


def build_feishu_card_payload_projection(review: Dict[str, Any], summary: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    warnings: List[str] = []
    review = _review_dict(review, warnings)
    summary = summary or summarize_review_for_user(review)
    top_actions = summary.get("top_action_candidates") or select_top_action_candidates(review, 5)
    severity_counts = _severity_counts(review)
    title = "Nightly Foundation Health Review Projection"
    card_json = {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": title},
            "template": "red" if int(review.get("critical_count") or 0) else "orange" if int(review.get("high_count") or 0) else "blue",
        },
        "elements": [
            {"tag": "markdown", "content": f"**总体状态**\\n{summary.get('headline', '')}"},
            {"tag": "markdown", "content": f"**Severity Counts**\\n{severity_counts}"},
            {"tag": "markdown", "content": f"**Blocked High Risk**: {review.get('blocked_high_risk_count', 0)}"},
            {
                "tag": "markdown",
                "content": "**Top Action Candidates**\\n"
                + "\\n".join(f"- {item.get('severity')} / {item.get('permission')}: {item.get('title')}" for item in top_actions.get("actions", [])[:5]),
            },
            {"tag": "markdown", "content": "**提示**：本消息为 projection，不会自动修复，不会写 action queue。"},
        ],
    }
    payload = asdict(
        FeishuCardPayloadProjection(
            payload_id=_make_id("feishu_payload", review.get("review_id"), _now()),
            generated_at=_now(),
            status="projection_only",
            title=title,
            template="foundation_health_review",
            card_json=card_json,
            source_review_id=review.get("review_id"),
            send_allowed=False,
            send_blocked_reason="projection_only_no_webhook_call",
            webhook_required=True,
            warnings=_dedupe(warnings + summary.get("warnings", [])),
        )
    )
    payload["no_webhook_call"] = True
    payload["no_runtime_write"] = True
    return payload


def build_plaintext_nightly_summary(review: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    review = _review_dict(review, warnings)
    summary = summarize_review_for_user(review)
    domain_summary = summarize_review_by_domain(review)
    top_actions = select_top_action_candidates(review, max_items=5)
    lines = [
        "Nightly Foundation Health Review 摘要",
        summary.get("headline", ""),
        "",
        f"风险分布：{summary.get('severity_counts', {})}",
        f"Action candidates：{summary.get('action_candidate_count', 0)}，需要确认：{summary.get('requires_confirmation_count', 0)}，禁止自动执行：{summary.get('blocked_high_risk_count', 0)}",
        "",
        "重点 Domain：",
    ]
    for row in domain_summary.get("domains", []):
        if row.get("signal_count"):
            lines.append(
                f"- {row['domain']}: signals={row['signal_count']}, critical={row['critical_count']}, high={row['high_count']}, medium={row['medium_count']}"
            )
    lines.append("")
    lines.append("Top Actions：")
    for item in top_actions.get("actions", []):
        lines.append(f"- {item.get('severity')} / {item.get('permission')}: {item.get('title')}")
    lines.extend(
        [
            "",
            "本摘要为只读 projection：不会推送 Feishu，不会写 action queue，不会执行自动修复。",
            "下一步建议：进入 R241-9A Foundation Integration Readiness Review。",
        ]
    )
    return {"text": "\\n".join(lines), "warnings": _dedupe(warnings + summary.get("warnings", []) + top_actions.get("warnings", []))}


def validate_feishu_payload_projection(payload: Dict[str, Any]) -> Dict[str, Any]:
    warnings: List[str] = []
    blocked_reasons: List[str] = []
    valid = True
    if not payload.get("card_json"):
        valid = False
        warnings.append("card_json_missing")
    if not payload.get("title"):
        valid = False
        warnings.append("title_missing")
    if payload.get("send_allowed") is not False:
        valid = False
        blocked_reasons.append("send_allowed_must_be_false")
    if payload.get("status") != "projection_only":
        valid = False
        blocked_reasons.append("status_must_be_projection_only")
    if payload.get("webhook_required") is not True:
        valid = False
        warnings.append("webhook_required_must_be_true")
    if payload.get("no_webhook_call") is not True:
        valid = False
        blocked_reasons.append("no_webhook_call_flag_missing")
    if payload.get("no_runtime_write") is not True:
        valid = False
        blocked_reasons.append("no_runtime_write_flag_missing")
    return {"valid": valid, "warnings": warnings, "blocked_reasons": blocked_reasons}


def generate_nightly_summary_projection_report(
    output_path: Optional[str] = None,
    review_path: Optional[str] = None,
) -> Dict[str, Any]:
    loaded = load_latest_nightly_review_sample(review_path)
    review = loaded.get("review") or {}
    user_summary = summarize_review_for_user(review)
    domain_summary = summarize_review_by_domain(review)
    top_actions = select_top_action_candidates(review)
    feishu_payload = build_feishu_card_payload_projection(review, user_summary)
    plaintext = build_plaintext_nightly_summary(review)
    validation = validate_feishu_payload_projection(feishu_payload)
    warnings = _dedupe(
        loaded.get("warnings", [])
        + user_summary.get("warnings", [])
        + domain_summary.get("warnings", [])
        + top_actions.get("warnings", [])
        + feishu_payload.get("warnings", [])
        + plaintext.get("warnings", [])
        + validation.get("warnings", [])
        + validation.get("blocked_reasons", [])
    )
    payload = {
        "loaded_review_summary": {
            "exists": loaded.get("exists"),
            "source_path": loaded.get("source_path"),
            "review_id": review.get("review_id"),
            "total_signals": review.get("total_signals", 0),
            "action_candidate_count": review.get("action_candidate_count", 0),
        },
        "user_summary": user_summary,
        "domain_summary": domain_summary,
        "top_action_candidates": top_actions,
        "feishu_payload_projection": feishu_payload,
        "plaintext_summary": plaintext,
        "validation": validation,
        "generated_at": _now(),
        "warnings": warnings,
    }
    target = Path(output_path) if output_path else DEFAULT_SUMMARY_SAMPLE_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(target), **payload}


def _review_dict(review: Any, warnings: List[str]) -> Dict[str, Any]:
    if isinstance(review, dict):
        return review
    warnings.append("malformed_review_defaulted")
    return {}


def _section(
    section_type: str,
    title: str,
    content: str,
    severity: Optional[str] = None,
    items: Optional[List[Dict[str, Any]]] = None,
    source_signal_ids: Optional[List[str]] = None,
    source_action_candidate_ids: Optional[List[str]] = None,
) -> Dict[str, Any]:
    return asdict(
        NightlySummarySection(
            section_id=_make_id("summary_section", section_type, title),
            section_type=section_type if section_type in SUMMARY_SECTION_TYPES else "unknown",
            title=title,
            severity=severity,
            content=content,
            items=items or [],
            source_signal_ids=source_signal_ids or [],
            source_action_candidate_ids=source_action_candidate_ids or [],
        )
    )


def _signals_by_severity(review: Dict[str, Any], severity: str) -> List[Dict[str, Any]]:
    return [signal for signal in (review.get("signals") or []) if signal.get("severity") == severity]


def _compact_signals(signals: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return [
        {
            "signal_id": signal.get("signal_id"),
            "domain": signal.get("domain"),
            "severity": signal.get("severity"),
            "signal_type": signal.get("signal_type"),
            "message": signal.get("message"),
            "recommended_action_type": signal.get("recommended_action_type"),
        }
        for signal in signals[:limit]
    ]


def _compact_actions(actions: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return [
        {
            "action_candidate_id": action.get("action_candidate_id"),
            "domain": action.get("domain"),
            "severity": action.get("severity"),
            "permission": action.get("permission"),
            "title": action.get("title"),
            "action_type": action.get("action_type"),
            "auto_executable": action.get("auto_executable"),
            "requires_user_confirmation": action.get("requires_user_confirmation"),
            "blocked_reason": action.get("blocked_reason"),
        }
        for action in actions[:limit]
    ]


def _action_sort_key(action: Dict[str, Any]) -> tuple[int, int, int, str]:
    severity_rank = SEVERITY_RANK.get(str(action.get("severity") or "unknown"), 5)
    permission_rank = PERMISSION_RANK.get(str(action.get("permission") or "unknown"), 6)
    text = " ".join(str(action.get(key) or "") for key in ["domain", "action_type", "title", "description"]).lower()
    keyword_rank = min((rank for key, rank in PRIORITY_KEYWORDS.items() if key in text), default=9)
    return (severity_rank, permission_rank, keyword_rank, str(action.get("title") or ""))


def _severity_counts(review: Dict[str, Any]) -> Dict[str, int]:
    counts = review.get("by_severity")
    if isinstance(counts, dict):
        return {str(k): int(v) for k, v in counts.items() if isinstance(v, int)}
    return dict(Counter(str(signal.get("severity") or "unknown") for signal in (review.get("signals") or [])))


def _top_counts(counter: Counter, limit: int) -> List[Dict[str, Any]]:
    return [{"name": name, "count": count} for name, count in counter.most_common(limit)]


def _make_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(part) for part in parts if part is not None)
    return f"{prefix}_{abs(hash(raw)) % 10_000_000_000:010d}"


def _dedupe(items: List[Any]) -> List[str]:
    result: List[str] = []
    seen = set()
    for item in items:
        text = str(item)
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

