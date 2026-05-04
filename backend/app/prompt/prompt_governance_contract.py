"""Prompt governance wrapper.

This module classifies prompt sources and projects replacement risk. It does
not modify prompts, enable GEPA/DSPy optimization, replace SOUL.md, register
assets, or write prompt runtime state.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4


PROMPT_LAYERS = {
    "P1_hard_constraints",
    "P2_user_preferences",
    "P3_mode_collaboration",
    "P4_task_skill",
    "P5_runtime_context",
    "P6_identity_base",
    "unknown",
}

LAYER_RANK = {
    "P1_hard_constraints": 1,
    "P2_user_preferences": 2,
    "P3_mode_collaboration": 3,
    "P4_task_skill": 4,
    "P5_runtime_context": 5,
    "P6_identity_base": 6,
    "unknown": 99,
}

SOURCE_TYPES = {
    "soul",
    "system_base",
    "user_preference",
    "mode_prompt",
    "task_prompt",
    "skill_prompt",
    "tool_prompt",
    "memory_injection",
    "asset_prompt",
    "rtcm_prompt",
    "deerflow_agent_prompt",
    "m09_prompt_engine",
    "dspy_candidate",
    "gepa_candidate",
    "fewshot",
    "runtime_context",
    "unknown",
}

RISK_LEVELS = {"low", "medium", "high", "critical", "unknown"}
OPTIMIZATION_STATUSES = {"production", "candidate", "experimental", "deprecated", "rollback_candidate", "unknown"}

DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-6A_PROMPT_GOVERNANCE_SAMPLE.json"
)

EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv"}
PROMPT_KEYWORDS = {
    "prompt",
    "prompts",
    "soul.md",
    "dspy",
    "gepa",
    "signature",
    "fewshot",
    "skill",
    "agent",
    "rtcm",
    "mode",
    "orchestration",
    "system",
    "instruction",
}


@dataclass(frozen=True)
class PromptSourceRecord:
    prompt_source_id: str
    source_type: str
    owner_system: str
    priority_layer: str
    allowed_modes: List[str]
    denied_modes: List[str]
    can_override_lower_layer: bool
    can_be_optimized: bool
    optimization_status: str
    rollback_available: bool
    backup_refs: List[str]
    rollback_refs: List[str]
    asset_candidate_eligible: bool
    risk_level: str
    warnings: List[str]
    observed_at: str
    source_path: Optional[str] = None
    version: Optional[str] = None
    source_hash: Optional[str] = None
    last_verified_at: Optional[str] = None


@dataclass(frozen=True)
class PromptConflictDecision:
    higher_priority_source: Optional[str]
    lower_priority_source: Optional[str]
    winning_layer: str
    losing_layer: str
    conflict_type: str
    decision: str
    warnings: List[str]
    required_followups: List[str]


@dataclass(frozen=True)
class PromptReplacementRisk:
    prompt_source_id: str
    risk_level: str
    replacement_allowed: bool
    requires_backup: bool
    requires_rollback: bool
    requires_test: bool
    requires_governance_review: bool
    requires_user_confirmation: bool
    asset_candidate_required: bool
    warnings: List[str]
    required_followups: List[str]


def classify_prompt_source(path_or_record: str | Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    source_path = path_or_record if isinstance(path_or_record, str) else path_or_record.get("source_path")
    record = path_or_record if isinstance(path_or_record, dict) else {}
    text = _source_text(path_or_record, metadata)
    warnings: List[str] = []

    source_type = _classify_source_type(text, source_path, metadata, warnings)
    priority_layer = classify_prompt_layer(source_type, source_path, metadata)
    optimization_status = _optimization_status(source_type, metadata)
    risk_level = _risk_for_layer(priority_layer)
    can_be_optimized = priority_layer not in {"P1_hard_constraints"} and source_type != "soul"
    asset_candidate_eligible = source_type in {"dspy_candidate", "gepa_candidate", "fewshot", "skill_prompt", "task_prompt", "mode_prompt"}
    rollback_refs = list(metadata.get("rollback_refs") or record.get("rollback_refs") or [])
    backup_refs = list(metadata.get("backup_refs") or record.get("backup_refs") or [])
    rollback_available = bool(metadata.get("rollback_available") or rollback_refs)

    if source_type == "soul":
        risk_level = "critical"
        can_be_optimized = False
        warnings.append("soul_is_identity_base_not_highest_override")
    if priority_layer == "P1_hard_constraints":
        risk_level = "critical"
        asset_candidate_eligible = False
        can_be_optimized = False
    if source_type in {"dspy_candidate", "gepa_candidate"}:
        optimization_status = "candidate"
        risk_level = "high"
        asset_candidate_eligible = True
        warnings.append("generated_prompt_requires_test_backup_rollback")
    if priority_layer == "unknown" or source_type == "unknown":
        warnings.append("unknown_prompt_source")

    return asdict(
        PromptSourceRecord(
            prompt_source_id=str(record.get("prompt_source_id") or metadata.get("prompt_source_id") or f"promptsrc_{uuid4().hex}"),
            source_type=source_type,
            source_path=str(source_path) if source_path else None,
            owner_system=str(metadata.get("owner_system") or record.get("owner_system") or _owner_system_from_path(source_path)),
            priority_layer=priority_layer,
            allowed_modes=list(metadata.get("allowed_modes") or record.get("allowed_modes") or []),
            denied_modes=list(metadata.get("denied_modes") or record.get("denied_modes") or []),
            can_override_lower_layer=priority_layer in {"P1_hard_constraints", "P2_user_preferences", "P3_mode_collaboration"},
            can_be_optimized=can_be_optimized,
            optimization_status=optimization_status,
            version=metadata.get("version") or record.get("version"),
            rollback_available=rollback_available,
            backup_refs=backup_refs,
            rollback_refs=rollback_refs,
            asset_candidate_eligible=asset_candidate_eligible,
            risk_level=risk_level,
            source_hash=metadata.get("source_hash") or _path_hash(source_path),
            last_verified_at=metadata.get("last_verified_at") or record.get("last_verified_at"),
            warnings=_dedupe(warnings),
            observed_at=_now(),
        )
    )


def classify_prompt_layer(source_type: str, path: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None) -> str:
    metadata = dict(metadata or {})
    text = " ".join([str(source_type or ""), str(path or ""), _flatten_values(metadata)]).lower().replace("\\", "/")
    if metadata.get("priority_layer") in PROMPT_LAYERS:
        return metadata["priority_layer"]
    if "root_guard" in text or "hard_constraint" in text or "safety" in text or "secret" in text or "irreversible" in text:
        return "P1_hard_constraints"
    if source_type == "soul" or "soul.md" in text:
        return "P6_identity_base"
    if source_type == "user_preference" or "preference" in text or "user_rule" in text or "high autonomy" in text or "高自主" in text:
        return "P2_user_preferences"
    if source_type in {"mode_prompt", "rtcm_prompt"} or any(token in text for token in ["mode", "orchestration", "roundtable", "workflow", "autonomous", "modeinvocation", "modecallgraph"]):
        return "P3_mode_collaboration"
    if source_type in {"task_prompt", "skill_prompt", "tool_prompt", "m09_prompt_engine", "deerflow_agent_prompt"}:
        if source_type == "deerflow_agent_prompt" and ("base" in text or "identity" in text or "lead_agent/prompt.py" in text):
            return "P6_identity_base"
        return "P4_task_skill"
    if source_type in {"memory_injection", "asset_prompt", "runtime_context"} or any(
        token in text for token in ["context", "memory", "asset", "tool event", "governance", "state", "truth", "runtime"]
    ):
        return "P5_runtime_context"
    if source_type in {"dspy_candidate", "gepa_candidate", "fewshot"}:
        return "P4_task_skill"
    if source_type == "system_base":
        return "P6_identity_base"
    return "unknown"


def resolve_prompt_conflict(source_a: Dict[str, Any], source_b: Dict[str, Any]) -> Dict[str, Any]:
    layer_a = source_a.get("priority_layer", "unknown")
    layer_b = source_b.get("priority_layer", "unknown")
    warnings: List[str] = []
    followups: List[str] = []
    rank_a = LAYER_RANK.get(layer_a, 99)
    rank_b = LAYER_RANK.get(layer_b, 99)

    if rank_a == rank_b:
        decision = "requires_review"
        warnings.append("same_layer_conflict_requires_review")
        followups.append("manual_prompt_conflict_review")
        higher = source_a.get("prompt_source_id")
        lower = source_b.get("prompt_source_id")
        winning_layer = layer_a
        losing_layer = layer_b
    elif rank_a < rank_b:
        decision = "source_a_wins"
        higher = source_a.get("prompt_source_id")
        lower = source_b.get("prompt_source_id")
        winning_layer = layer_a
        losing_layer = layer_b
    else:
        decision = "source_b_wins"
        higher = source_b.get("prompt_source_id")
        lower = source_a.get("prompt_source_id")
        winning_layer = layer_b
        losing_layer = layer_a

    if "unknown" in {layer_a, layer_b} and layer_a != layer_b:
        warnings.append("unknown_layer_cannot_override_known_layer")

    return asdict(
        PromptConflictDecision(
            higher_priority_source=higher,
            lower_priority_source=lower,
            winning_layer=winning_layer,
            losing_layer=losing_layer,
            conflict_type="layer_priority",
            decision=decision,
            warnings=_dedupe(warnings),
            required_followups=_dedupe(followups),
        )
    )


def assess_prompt_replacement_risk(prompt_source: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    layer = prompt_source.get("priority_layer", "unknown")
    source_type = prompt_source.get("source_type", "unknown")
    warnings: List[str] = []
    followups: List[str] = []
    requires_backup = True
    requires_rollback = True
    requires_test = True
    requires_governance_review = False
    requires_user_confirmation = False
    asset_candidate_required = False
    replacement_allowed = True
    risk_level = "unknown"

    if layer == "P1_hard_constraints":
        risk_level = "critical"
        requires_governance_review = True
        requires_user_confirmation = True
        replacement_allowed = bool(metadata.get("user_confirmation") and metadata.get("rollback_refs"))
        followups.extend(["user_confirmation_required", "governance_review_required", "backup_required", "rollback_required", "test_required"])
    elif layer == "P2_user_preferences":
        risk_level = "high"
        requires_governance_review = True
        requires_user_confirmation = True
        followups.extend(["user_confirmation_or_governance_review_required", "backup_required", "rollback_required"])
    elif layer == "P3_mode_collaboration":
        risk_level = "high"
        followups.extend(["test_required", "rollback_required"])
    elif layer == "P4_task_skill":
        risk_level = "high" if prompt_source.get("optimization_status") == "production" else "medium"
        followups.extend(["test_required", "rollback_required"])
    elif layer == "P5_runtime_context":
        risk_level = "medium"
        followups.extend(["context_leakage_review_required", "test_required"])
    elif layer == "P6_identity_base":
        risk_level = "critical" if source_type == "soul" else "high"
        requires_user_confirmation = True
        followups.extend(["user_confirmation_required", "backup_required", "rollback_required"])
    else:
        risk_level = "unknown"
        requires_user_confirmation = True
        replacement_allowed = False
        warnings.append("unknown_prompt_layer_replacement_requires_review")
        followups.append("manual_prompt_source_review")

    if source_type in {"dspy_candidate", "gepa_candidate"}:
        replacement_allowed = False
        asset_candidate_required = True
        warnings.append("generated_candidate_cannot_directly_replace_production")
        followups.extend(["candidate_path_required", "asset_candidate_required", "test_required", "backup_required", "rollback_required"])
    if source_type == "soul":
        warnings.append("soul_replacement_requires_user_confirmation_backup_rollback")

    return asdict(
        PromptReplacementRisk(
            prompt_source_id=str(prompt_source.get("prompt_source_id", "unknown")),
            risk_level=risk_level,
            replacement_allowed=replacement_allowed,
            requires_backup=requires_backup,
            requires_rollback=requires_rollback,
            requires_test=requires_test,
            requires_governance_review=requires_governance_review,
            requires_user_confirmation=requires_user_confirmation,
            asset_candidate_required=asset_candidate_required,
            warnings=_dedupe(warnings),
            required_followups=_dedupe(followups),
        )
    )


def project_prompt_asset_candidate(prompt_source: Dict[str, Any]) -> Dict[str, Any]:
    source_type = prompt_source.get("source_type", "unknown")
    layer = prompt_source.get("priority_layer", "unknown")
    warnings: List[str] = []
    eligible = False
    asset_category = "unknown"
    required_evidence: List[str] = []

    if source_type == "soul":
        asset_category = "protected_identity_source"
        warnings.append("soul_not_ordinary_a7_prompt_asset")
    elif layer == "P1_hard_constraints":
        asset_category = "protected_hard_constraint_source"
        warnings.append("p1_hard_constraint_not_ordinary_prompt_asset")
    elif source_type in {"dspy_candidate", "gepa_candidate", "fewshot", "skill_prompt", "task_prompt", "mode_prompt"}:
        eligible = True
        asset_category = "A7_prompt_instruction"
        required_evidence = ["tests", "rollback_ref", "usage_context", "governance_review_if_production"]
    else:
        warnings.append("prompt_source_not_asset_candidate")

    return {
        "asset_candidate_eligible": eligible,
        "asset_category": asset_category,
        "lifecycle_tier": "candidate",
        "required_evidence": required_evidence,
        "warnings": _dedupe(warnings),
    }


def scan_prompt_sources(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    base = Path(root or r"E:\OpenClaw-Base\deerflow")
    max_files = max(0, min(int(max_files), 2000))
    records: List[Dict[str, Any]] = []
    scanned = 0
    warnings: List[str] = []
    if not base.exists():
        return {
            "root": str(base),
            "scanned_count": 0,
            "classified_count": 0,
            "by_layer": {},
            "by_source_type": {},
            "by_risk_level": {},
            "asset_candidate_count": 0,
            "warnings": ["root_missing"],
            "records": [],
        }

    for path in base.rglob("*"):
        if scanned >= max_files:
            warnings.append("max_files_reached")
            break
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        text = str(path).lower()
        if not any(keyword in text for keyword in PROMPT_KEYWORDS):
            continue
        scanned += 1
        records.append(classify_prompt_source(str(path)))

    return {
        "root": str(base),
        "scanned_count": scanned,
        "classified_count": len(records),
        "by_layer": dict(Counter(record["priority_layer"] for record in records)),
        "by_source_type": dict(Counter(record["source_type"] for record in records)),
        "by_risk_level": dict(Counter(record["risk_level"] for record in records)),
        "asset_candidate_count": sum(1 for record in records if record.get("asset_candidate_eligible")),
        "warnings": _dedupe(warnings),
        "records": records,
    }


def summarize_prompt_governance(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    warnings: List[str] = []
    for record in records:
        warnings.extend(record.get("warnings") or [])
    return {
        "total": len(records),
        "by_layer": dict(Counter(record.get("priority_layer", "unknown") for record in records)),
        "by_source_type": dict(Counter(record.get("source_type", "unknown") for record in records)),
        "by_risk_level": dict(Counter(record.get("risk_level", "unknown") for record in records)),
        "optimization_candidates": sum(1 for record in records if record.get("optimization_status") in {"candidate", "experimental"}),
        "asset_candidates": sum(1 for record in records if record.get("asset_candidate_eligible")),
        "critical_sources": sum(1 for record in records if record.get("risk_level") == "critical"),
        "rollback_missing_count": sum(1 for record in records if record.get("risk_level") in {"high", "critical"} and not record.get("rollback_available")),
        "warnings_summary": dict(Counter(warnings)),
    }


def generate_prompt_governance_sample(output_path: Optional[str] = None) -> Dict[str, Any]:
    samples = [
        classify_prompt_source("SOUL.md"),
        classify_prompt_source({"source_path": "user/preferences/high_autonomy.md"}, {"source_type": "user_preference"}),
        classify_prompt_source("prompts/mode_orchestration_prompt.md"),
        classify_prompt_source("skills/code/SKILL.md"),
        classify_prompt_source("runtime/context_prompt.md"),
        classify_prompt_source("experiments/dspy/signature.json"),
        classify_prompt_source("experiments/gepa/generated_prompt.md"),
        classify_prompt_source("prompts/hard_constraints/root_guard_prompt.md"),
    ]
    risks = [assess_prompt_replacement_risk(record) for record in samples]
    conflicts = [
        resolve_prompt_conflict(samples[1], classify_prompt_source("prompts/conservative_task_prompt.md")),
        resolve_prompt_conflict(samples[7], samples[0]),
    ]
    asset_candidates = [project_prompt_asset_candidate(record) for record in samples]
    result = {
        "records": samples,
        "replacement_risks": risks,
        "conflicts": conflicts,
        "asset_candidate_projection": asset_candidates,
        "summary": summarize_prompt_governance(samples),
        "generated_at": _now(),
        "warnings": _dedupe([warning for record in samples for warning in record.get("warnings", [])]),
    }
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _classify_source_type(text: str, source_path: Optional[str], metadata: Dict[str, Any], warnings: List[str]) -> str:
    explicit = metadata.get("source_type")
    if explicit in SOURCE_TYPES:
        return explicit
    path_text = str(source_path or "").lower().replace("\\", "/")
    combined = f"{text} {path_text}"
    if "soul.md" in combined:
        return "soul"
    if "dspy" in combined or "signature" in combined:
        return "dspy_candidate"
    if "gepa" in combined:
        return "gepa_candidate"
    if "fewshot" in combined:
        return "fewshot"
    if "root_guard" in combined or "hard_constraint" in combined or "safety" in combined:
        return "system_base"
    if "user" in combined and ("preference" in combined or "rule" in combined):
        return "user_preference"
    if "rtcm" in combined or "roundtable" in combined:
        return "rtcm_prompt"
    if "mode" in combined or "orchestration" in combined or "workflow" in combined or "autonomous" in combined:
        return "mode_prompt"
    if "memory" in combined:
        return "memory_injection"
    if "asset" in combined:
        return "asset_prompt"
    if "context" in combined or "truth" in combined or "state" in combined or "governance" in combined:
        return "runtime_context"
    if "deerflow" in combined and "prompt" in combined:
        return "deerflow_agent_prompt"
    if "m09" in combined or "prompt_engine" in combined:
        return "m09_prompt_engine"
    if "skill" in combined:
        return "skill_prompt"
    if "tool" in combined:
        return "tool_prompt"
    if "task" in combined or "prompt" in combined or "instruction" in combined:
        return "task_prompt"
    warnings.append("unknown_prompt_source_type")
    return "unknown"


def _optimization_status(source_type: str, metadata: Dict[str, Any]) -> str:
    if metadata.get("optimization_status") in OPTIMIZATION_STATUSES:
        return metadata["optimization_status"]
    if source_type in {"dspy_candidate", "gepa_candidate"}:
        return "candidate"
    if source_type == "unknown":
        return "unknown"
    return "production"


def _risk_for_layer(layer: str) -> str:
    if layer == "P1_hard_constraints":
        return "critical"
    if layer in {"P2_user_preferences", "P3_mode_collaboration"}:
        return "high"
    if layer in {"P4_task_skill", "P5_runtime_context"}:
        return "medium"
    if layer == "P6_identity_base":
        return "high"
    return "unknown"


def _owner_system_from_path(path: Optional[str]) -> str:
    text = str(path or "").lower().replace("\\", "/")
    if "deerflow" in text:
        return "deerflow"
    if "rtcm" in text:
        return "rtcm"
    if "m09" in text:
        return "m09_prompt_engine"
    if "skill" in text:
        return "skill"
    return "prompt_governance"


def _path_hash(path: Optional[str]) -> Optional[str]:
    if not path:
        return None
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()


def _source_text(path_or_record: str | Dict[str, Any], metadata: Dict[str, Any]) -> str:
    if isinstance(path_or_record, dict):
        values = _flatten_values(path_or_record)
    else:
        values = str(path_or_record)
    return f"{values} {_flatten_values(metadata)}".lower().replace("\\", "/")


def _flatten_values(value: Any) -> str:
    if isinstance(value, dict):
        return " ".join(_flatten_values(item) for item in value.values())
    if isinstance(value, list):
        return " ".join(_flatten_values(item) for item in value)
    if value is None:
        return ""
    return str(value)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    result: List[str] = []
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
