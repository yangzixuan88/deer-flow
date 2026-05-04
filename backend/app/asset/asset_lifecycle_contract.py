"""Read-only Asset Lifecycle / Candidate contract projection helpers.

This module classifies asset candidates and lifecycle signals without writing
asset registries, binding reports, DPBS state, or governance history.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from uuid import NAMESPACE_URL, uuid5


ASSET_CATEGORIES = {
    "A1_tool_capability",
    "A2_external_resource",
    "A3_workflow_solution",
    "A4_execution_experience",
    "A5_cognitive_method",
    "A6_information_source_network",
    "A7_prompt_instruction",
    "A8_user_preference",
    "A9_domain_knowledge_map",
    "unknown",
}

LIFECYCLE_TIERS = {
    "Record",
    "General",
    "Available",
    "Premium",
    "Core",
    "candidate",
    "unknown",
}

SCORE_WEIGHTS = {
    "frequency": 0.25,
    "success_rate": 0.30,
    "timeliness": 0.20,
    "coverage": 0.15,
    "uniqueness": 0.10,
}

DEFAULT_REPORT_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json"
)
DEFAULT_MEMORY_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-2B_MEMORY_PROJECTION_RUNTIME_SAMPLE.json"
)


@dataclass(frozen=True)
class AssetLifecycleRecord:
    asset_ref_id: str
    asset_category: str
    lifecycle_tier: str
    source_system: str
    source_type: str
    score: Optional[float]
    score_breakdown: Dict[str, Any]
    reusable_value_signal: Optional[str]
    verification_refs: List[Dict[str, Any]]
    truth_event_refs: List[Dict[str, Any]]
    usage_refs: List[Dict[str, Any]]
    allowed_modes: List[str]
    risk_level: str
    promotion_eligible: bool
    elimination_eligible: bool
    core_protected: bool
    warnings: List[str]
    observed_at: str
    asset_id: Optional[str] = None
    source_path: Optional[str] = None
    source_record_ref: Optional[Dict[str, Any]] = None
    origin_context_id: Optional[str] = None
    governance_trace_id: Optional[str] = None
    memory_ref_id: Optional[str] = None
    candidate_id: Optional[str] = None


def classify_asset_source(
    path_or_record: Union[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Classify an asset source into A1-A9 using path and metadata only."""
    metadata = metadata or {}
    text = _source_text(path_or_record, metadata)
    warnings: List[str] = []
    evidence_refs: List[Dict[str, Any]] = []

    def result(category: str, source_type: str, confidence: float, rule: str) -> Dict[str, Any]:
        evidence_refs.append({"rule": rule})
        return {
            "asset_category": category,
            "source_type": source_type,
            "source_system": _source_system(path_or_record, metadata),
            "confidence": confidence,
            "evidence_refs": evidence_refs,
            "warnings": warnings,
        }

    if any(token in text for token in ("qdrant", "graphrag", "knowledge_map", "domain_map", " graph", "/graph", "mem0")):
        return result("A9_domain_knowledge_map", "knowledge_map", 0.9, "knowledge_map_signal")

    if any(token in text for token in ("prompt", "dspy", "gepa", "signature", "fewshot", "few-shot")):
        return result("A7_prompt_instruction", "prompt", 0.9, "prompt_signal")

    if any(token in text for token in ("workflow", "dag", "sop", "pipeline", "automation")):
        return result("A3_workflow_solution", "workflow", 0.85, "workflow_signal")

    if "final_report" in text and ("rtcm" in text or "roundtable" in text):
        return result("A5_cognitive_method", "rtcm_final_report", 0.85, "rtcm_final_report_signal")

    if any(token in text for token in ("evidence_ledger", "source_map", "citation", "knowledge source", "source_network")):
        if any(token in text for token in ("graph", "domain_map", "knowledge_map")):
            return result("A9_domain_knowledge_map", "knowledge_map", 0.8, "evidence_knowledge_map_signal")
        return result("A6_information_source_network", "information_source", 0.85, "evidence_source_signal")

    if any(token in text for token in ("tool", "skill", "mcp", "cli", "executor")):
        return result("A1_tool_capability", "tool_capability", 0.85, "tool_capability_signal")

    if any(token in text for token in ("api", "source", "feed", "crawler", "search", "external")):
        return result("A2_external_resource", "external_resource", 0.75, "external_resource_signal")

    if any(token in text for token in ("fix", "repair", "rollback", "failure", "verification", "test_result", "execution_log")):
        return result("A4_execution_experience", "execution_experience", 0.8, "execution_experience_signal")

    if any(token in text for token in ("method", "reasoning", "rubric", "decision", "strategy")):
        return result("A5_cognitive_method", "cognitive_method", 0.75, "cognitive_method_signal")

    if any(token in text for token in ("preference", "user_profile", "user_rule", "user preference")):
        return result("A8_user_preference", "user_preference", 0.8, "user_preference_signal")

    warnings.append("unknown_asset_category")
    return {
        "asset_category": "unknown",
        "source_type": "unknown",
        "source_system": _source_system(path_or_record, metadata),
        "confidence": 0.0,
        "evidence_refs": evidence_refs,
        "warnings": warnings,
    }


def classify_lifecycle_tier(
    score: Optional[float],
    verification_state: Optional[str] = None,
    core_hint: bool = False,
) -> str:
    """Project lifecycle tier from score. Does not promote assets."""
    if core_hint:
        return "Core"
    if score is None:
        return "candidate"
    numeric = float(score)
    if numeric < 30:
        return "Record"
    if numeric < 60:
        return "General"
    if numeric < 75:
        return "Available"
    if numeric < 90:
        return "Premium"
    return "Core"


def compute_asset_score_signals(record: Dict[str, Any]) -> Dict[str, Any]:
    """Compute weighted score only when all components are present."""
    breakdown: Dict[str, Any] = {}
    missing: List[str] = []
    warnings: List[str] = []
    total = 0.0

    for component, weight in SCORE_WEIGHTS.items():
        value = _first_present(record, component, f"{component}_score")
        if value is None:
            missing.append(component)
            continue
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            missing.append(component)
            warnings.append(f"invalid_score_component:{component}")
            continue
        breakdown[component] = {"value": numeric, "weight": weight, "weighted": numeric * weight}
        total += numeric * weight

    if missing:
        warnings.append("missing_score_components")
        return {
            "score": None,
            "score_breakdown": breakdown,
            "missing_components": missing,
            "warnings": warnings,
        }

    return {
        "score": total,
        "score_breakdown": breakdown,
        "missing_components": [],
        "warnings": warnings,
    }


def project_asset_candidate(
    source: Union[str, Dict[str, Any]],
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Project one source into AssetLifecycleRecord without registry writes."""
    metadata = metadata or {}
    source_record = source if isinstance(source, dict) else {}
    source_path = _source_path(source, metadata)
    classification = classify_asset_source(source, metadata)
    score_result = compute_asset_score_signals({**source_record, **metadata})
    score = _first_present({**source_record, **metadata}, "score", "asset_score", "quality_score")
    if score is None:
        score = score_result["score"]
    else:
        try:
            score = float(score)
        except (TypeError, ValueError):
            score = None
    core_hint = bool(metadata.get("core_hint") or source_record.get("core_hint"))
    lifecycle_tier = classify_lifecycle_tier(score, metadata.get("verification_state"), core_hint)
    warnings = (
        list(classification.get("warnings") or [])
        + list(score_result.get("warnings") or [])
        + list(metadata.get("warnings") or [])
    )
    if core_hint or lifecycle_tier == "Core":
        warnings.append("core_requires_user_confirmation")
    if _is_raw_memory_source(source, metadata):
        warnings.append("raw_memory_not_asset")
    if _is_raw_governance_source(source, metadata):
        warnings.append("raw_governance_not_asset")

    record = AssetLifecycleRecord(
        asset_ref_id=_asset_ref_id(source, metadata),
        asset_id=metadata.get("asset_id") or source_record.get("asset_id"),
        asset_category=classification["asset_category"],
        lifecycle_tier=lifecycle_tier,
        source_system=classification["source_system"],
        source_type=classification["source_type"],
        source_path=source_path,
        source_record_ref=_source_record_ref(source, metadata),
        origin_context_id=metadata.get("origin_context_id") or source_record.get("origin_context_id"),
        governance_trace_id=metadata.get("governance_trace_id") or source_record.get("governance_trace_id"),
        memory_ref_id=metadata.get("memory_ref_id") or source_record.get("memory_ref_id"),
        candidate_id=metadata.get("candidate_id") or source_record.get("candidate_id"),
        score=score,
        score_breakdown=score_result["score_breakdown"],
        reusable_value_signal=metadata.get("reusable_value_signal") or source_record.get("reusable_value_signal"),
        verification_refs=list(metadata.get("verification_refs") or source_record.get("verification_refs") or []),
        truth_event_refs=list(metadata.get("truth_event_refs") or source_record.get("truth_event_refs") or []),
        usage_refs=list(metadata.get("usage_refs") or source_record.get("usage_refs") or []),
        allowed_modes=list(metadata.get("allowed_modes") or _default_allowed_modes(classification["asset_category"])),
        risk_level=str(metadata.get("risk_level") or source_record.get("risk_level") or "unknown"),
        promotion_eligible=_promotion_eligible(lifecycle_tier, score, metadata, source_record),
        elimination_eligible=_elimination_eligible(lifecycle_tier),
        core_protected=lifecycle_tier == "Core",
        warnings=_dedupe(warnings),
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    return asdict(record)


def project_memory_asset_candidates(memory_projection_result: Dict[str, Any]) -> Dict[str, Any]:
    """Project R241-2B memory asset candidates into asset lifecycle candidates."""
    candidates_input = memory_projection_result.get("candidates") or []
    warnings = list(memory_projection_result.get("warnings") or [])
    candidates = []
    for memory_candidate in candidates_input:
        metadata = {
            "memory_ref_id": memory_candidate.get("memory_ref_id"),
            "source_system": memory_candidate.get("source_system"),
            "warnings": memory_candidate.get("warnings") or [],
        }
        candidates.append(project_asset_candidate(memory_candidate, metadata))

    return {
        "candidate_count": len(candidates),
        "by_asset_category": dict(Counter(candidate["asset_category"] for candidate in candidates)),
        "by_lifecycle_tier": dict(Counter(candidate["lifecycle_tier"] for candidate in candidates)),
        "candidates": candidates,
        "warnings": _dedupe(warnings + [w for candidate in candidates for w in candidate.get("warnings", [])]),
        "note": "projection only; no asset promotion performed",
    }


def detect_asset_lifecycle_risks(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Return lifecycle risk diagnostics without processing assets."""
    risk_counter: Counter[str] = Counter()
    risk_records: List[Dict[str, Any]] = []
    for record in records:
        risks = _risk_types_for(record)
        for risk in risks:
            risk_counter[risk] += 1
        if risks:
            risk_records.append(
                {
                    "asset_ref_id": record.get("asset_ref_id"),
                    "asset_category": record.get("asset_category"),
                    "lifecycle_tier": record.get("lifecycle_tier"),
                    "source_path": record.get("source_path"),
                    "risk_types": risks,
                }
            )
    return {
        "risk_count": sum(risk_counter.values()),
        "risk_by_type": dict(risk_counter),
        "risk_records": risk_records,
        "warnings": [],
    }


def generate_asset_lifecycle_projection_report(output_path: Optional[str] = None) -> Dict[str, Any]:
    """Generate an audit-only asset lifecycle projection sample."""
    target = Path(output_path) if output_path else DEFAULT_REPORT_PATH
    memory_projection = _load_memory_projection_sample()
    memory_candidates = memory_projection.get("asset_candidates", {})
    memory_asset_projection = project_memory_asset_candidates(memory_candidates)
    lifecycle_risks = detect_asset_lifecycle_risks(memory_asset_projection["candidates"])
    warnings = _dedupe(
        list(memory_projection.get("warnings") or [])
        + list(memory_asset_projection.get("warnings") or [])
        + list(lifecycle_risks.get("warnings") or [])
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_policy": "asset lifecycle projection only; no registry writes and no asset promotion",
        "asset_projection_summary": {
            "candidate_count": memory_asset_projection["candidate_count"],
            "by_asset_category": memory_asset_projection["by_asset_category"],
            "by_lifecycle_tier": memory_asset_projection["by_lifecycle_tier"],
        },
        "memory_asset_candidates_projection": _truncate_candidates(memory_asset_projection),
        "lifecycle_risks": lifecycle_risks,
        "warnings": warnings,
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "output_path": str(target),
        "written": True,
        "generated_at": report["generated_at"],
        "warnings": warnings,
    }


def _load_memory_projection_sample() -> Dict[str, Any]:
    if not DEFAULT_MEMORY_SAMPLE_PATH.exists():
        return {"warnings": [f"memory_projection_sample_missing:{DEFAULT_MEMORY_SAMPLE_PATH}"], "asset_candidates": {}}
    try:
        return json.loads(DEFAULT_MEMORY_SAMPLE_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"warnings": [f"memory_projection_sample_read_failed:{type(exc).__name__}:{exc}"], "asset_candidates": {}}


def _risk_types_for(record: Dict[str, Any]) -> List[str]:
    risks: List[str] = []
    warnings = set(record.get("warnings") or [])
    if record.get("asset_category") == "unknown":
        risks.append("unknown_asset_category")
    if "missing_score_components" in warnings or record.get("score") is None:
        risks.append("missing_score_components")
    if record.get("core_protected"):
        risks.append("core_requires_user_confirmation")
    if not record.get("verification_refs"):
        risks.append("unverified_asset_candidate")
    if "raw_memory_not_asset" in warnings:
        risks.append("raw_memory_not_asset")
    if "raw_governance_not_asset" in warnings:
        risks.append("raw_governance_not_asset")
    if record.get("promotion_eligible") and not record.get("verification_refs"):
        risks.append("promotion_without_verification")
    if record.get("elimination_eligible") and record.get("lifecycle_tier") in {"Available", "Premium"}:
        risks.append("elimination_requires_observation")
    if record.get("lifecycle_tier") in {"Premium", "Core"} and record.get("elimination_eligible"):
        risks.append("premium_or_core_auto_elimination_forbidden")
    return _dedupe(risks)


def _source_text(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    if isinstance(source, str):
        base = source
    else:
        base = " ".join(_flatten_values(source))
    return f"{base} {' '.join(_flatten_values(metadata))}".replace("\\", "/").lower()


def _source_path(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> Optional[str]:
    if isinstance(source, str):
        return source
    return metadata.get("source_path") or source.get("source_path")


def _source_system(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    if metadata.get("source_system"):
        return str(metadata["source_system"])
    if isinstance(source, dict) and source.get("source_system"):
        return str(source["source_system"])
    text = _source_text(source, metadata)
    if "rtcm" in text:
        return "rtcm"
    if "memory" in text:
        return "memory_projection"
    if "governance" in text:
        return "governance"
    return "unknown"


def _source_record_ref(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(source, dict):
        return None
    return {
        "memory_ref_id": source.get("memory_ref_id"),
        "source_path": source.get("source_path"),
        "source_system": source.get("source_system"),
    }


def _asset_ref_id(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> str:
    source_record = source if isinstance(source, dict) else {}
    stable_key = (
        metadata.get("asset_id")
        or source_record.get("asset_id")
        or source_record.get("id")
        or metadata.get("candidate_id")
        or source_record.get("candidate_id")
        or metadata.get("memory_ref_id")
        or source_record.get("memory_ref_id")
        or _source_path(source, metadata)
        or _source_text(source, metadata)
    )
    return f"assetref_{uuid5(NAMESPACE_URL, str(stable_key)).hex}"


def _promotion_eligible(
    lifecycle_tier: str,
    score: Optional[float],
    metadata: Dict[str, Any],
    source_record: Dict[str, Any],
) -> bool:
    verified = bool(metadata.get("verification_refs") or source_record.get("verification_refs"))
    return verified and score is not None and lifecycle_tier in {"Available", "Premium"}


def _elimination_eligible(lifecycle_tier: str) -> bool:
    return lifecycle_tier in {"Record", "General", "Available"}


def _default_allowed_modes(category: str) -> List[str]:
    mapping = {
        "A1_tool_capability": ["task", "workflow", "autonomous_agent"],
        "A2_external_resource": ["search", "task", "workflow"],
        "A3_workflow_solution": ["workflow", "task", "autonomous_agent"],
        "A4_execution_experience": ["task", "workflow", "autonomous_agent"],
        "A5_cognitive_method": ["roundtable", "task", "autonomous_agent"],
        "A6_information_source_network": ["search", "roundtable"],
        "A7_prompt_instruction": ["task", "workflow", "autonomous_agent"],
        "A8_user_preference": ["task", "workflow", "autonomous_agent", "roundtable"],
        "A9_domain_knowledge_map": ["search", "task", "roundtable"],
    }
    return mapping.get(category, [])


def _is_raw_memory_source(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
    text = _source_text(source, metadata)
    return "raw memory fact" in text or "memory fact" in text and "final_report" not in text


def _is_raw_governance_source(source: Union[str, Dict[str, Any]], metadata: Dict[str, Any]) -> bool:
    text = _source_text(source, metadata)
    return "governance_state" in text or "raw governance" in text


def _first_present(mapping: Dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    return None


def _truncate_candidates(data: Dict[str, Any]) -> Dict[str, Any]:
    compact = dict(data)
    if "candidates" in compact:
        compact["candidate_total_count"] = len(compact["candidates"])
        compact["candidates"] = compact["candidates"][:50]
    return compact


def _dedupe(items: List[Any]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in items))


def _flatten_values(value: Any) -> List[str]:
    if isinstance(value, dict):
        flattened: List[str] = []
        for nested in value.values():
            flattened.extend(_flatten_values(nested))
        return flattened
    if isinstance(value, list):
        flattened = []
        for nested in value:
            flattened.extend(_flatten_values(nested))
        return flattened
    if value is None:
        return []
    return [str(value)]
