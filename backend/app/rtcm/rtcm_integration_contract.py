"""RTCM / Roundtable read-only integration instrumentation.

Roundtable is one of the five peer modes. RTCM is the current primary
roundtable executor, but roundtable mode is not RTCM itself. This module only
projects RTCM artifacts into truth/asset/memory/followup candidates and does
not mutate RTCM sessions, dossiers, governance, memory, or assets.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

try:
    from app.asset.asset_lifecycle_contract import project_asset_candidate
except Exception:  # pragma: no cover - safe optional integration
    project_asset_candidate = None  # type: ignore

try:
    from app.memory.memory_layer_contract import classify_memory_artifact
except Exception:  # pragma: no cover - safe optional integration
    classify_memory_artifact = None  # type: ignore


ROUNDTABLE_EXECUTORS = {"rtcm", "manual", "external", "unknown"}
ARTIFACT_TYPES = {
    "session_manifest",
    "dossier",
    "brief_report",
    "council_log",
    "evidence_ledger",
    "final_report",
    "issue_card",
    "signoff",
    "followup",
    "verdict",
    "unknown",
}
TRUTH_TYPES = {
    "rtcm_verdict",
    "signoff_decision",
    "final_report_conclusion",
    "evidence_summary",
    "followup_recommendation",
    "unknown",
}
STATE_PROJECTIONS = {"active", "paused", "waiting_for_user", "signed_off", "archived", "failed", "unknown"}
DEFAULT_SAMPLE_PATH = Path(
    r"E:\OpenClaw-Base\deerflow\migration_reports\foundation_audit\R241-7A_RTCM_ROUNDTABLE_INTEGRATION_SAMPLE.json"
)
DEFAULT_ROOT = Path(r"E:\OpenClaw-Base\deerflow")
EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv"}
RTCM_KEYWORDS = {
    ".deerflow/rtcm",
    "rtcm",
    "dossier",
    "final_report",
    "signoff",
    "council_log",
    "evidence_ledger",
    "followup",
    "verdict",
    "issue_card",
}


@dataclass(frozen=True)
class RoundtableSessionProjection:
    roundtable_session_ref_id: str
    executor: str
    status: str
    artifact_refs: List[str]
    truth_candidate_refs: List[str]
    asset_candidate_refs: List[str]
    memory_candidate_refs: List[str]
    followup_refs: List[str]
    warnings: List[str]
    observed_at: str
    rtcm_session_id: Optional[str] = None
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    gateway_thread_id: Optional[str] = None
    mode_session_id: Optional[str] = None
    mode_invocation_id: Optional[str] = None
    topic: Optional[str] = None
    source_path: Optional[str] = None


@dataclass(frozen=True)
class RTCMArtifactProjection:
    artifact_ref_id: str
    artifact_type: str
    source_path: str
    producer: str
    consumer_candidates: List[str]
    truth_event_eligible: bool
    asset_candidate_eligible: bool
    memory_candidate_eligible: bool
    long_term_memory_eligible: bool
    warnings: List[str]
    observed_at: str
    rtcm_session_id: Optional[str] = None
    context_id: Optional[str] = None


@dataclass(frozen=True)
class RTCMTruthProjection:
    truth_candidate_id: str
    truth_type: str
    truth_track: str
    source_artifact_ref: str
    subject_type: str
    evidence_refs: List[str]
    confidence: float
    warnings: List[str]
    observed_at: str
    rtcm_session_id: Optional[str] = None
    subject_id: Optional[str] = None


@dataclass(frozen=True)
class RTCMFollowupProjection:
    followup_ref_id: str
    source_artifact_ref: str
    suggested_target_mode: str
    suggested_action_type: str
    priority: str
    requires_user_confirmation: bool
    mode_invocation_candidate: Optional[Dict[str, Any]]
    warnings: List[str]
    observed_at: str
    rtcm_session_id: Optional[str] = None


def classify_rtcm_artifact(path_or_record: str | Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    source_path = path_or_record if isinstance(path_or_record, str) else path_or_record.get("source_path", "")
    text = _source_text(path_or_record, metadata)
    artifact_type = "unknown"
    warnings: List[str] = []

    if "final_report" in text or "final-report" in text:
        artifact_type = "final_report"
    elif "evidence_ledger" in text or "evidence-ledger" in text or "evidence ledger" in text:
        artifact_type = "evidence_ledger"
    elif "council_log" in text or "council-log" in text or "council log" in text:
        artifact_type = "council_log"
    elif "signoff" in text or "sign_off" in text:
        artifact_type = "signoff"
    elif "followup" in text or "follow_up" in text:
        artifact_type = "followup"
    elif "verdict" in text:
        artifact_type = "verdict"
    elif "issue_card" in text or "issue-card" in text:
        artifact_type = "issue_card"
    elif "manifest" in text or "session.json" in text:
        artifact_type = "session_manifest"
    elif "brief_report" in text or "brief-report" in text:
        artifact_type = "brief_report"
    elif "dossier" in text:
        artifact_type = "dossier"
    else:
        warnings.append("unknown_rtcm_artifact_type")

    truth = artifact_type in {"final_report", "signoff", "evidence_ledger", "verdict"}
    asset = artifact_type in {"final_report", "evidence_ledger", "issue_card", "brief_report"}
    memory = artifact_type in {"final_report", "evidence_ledger", "dossier", "issue_card", "brief_report"}
    long_term = artifact_type in {"final_report", "evidence_ledger"}
    consumer_candidates = _consumers_for_artifact(artifact_type)
    followup_candidate = artifact_type == "followup"

    if artifact_type == "council_log":
        truth = False
        asset = False
        memory = False
        long_term = False
        warnings.append("council_log_not_long_term_memory")
    if artifact_type == "signoff":
        asset = False
        memory = False
        long_term = False
    if followup_candidate:
        consumer_candidates.append("followup_projection")

    return {
        "artifact_type": artifact_type,
        "source_path": str(source_path),
        "truth_event_eligible": truth,
        "asset_candidate_eligible": asset,
        "memory_candidate_eligible": memory,
        "long_term_memory_eligible": long_term,
        "followup_candidate_eligible": followup_candidate,
        "consumer_candidates": _dedupe(consumer_candidates),
        "warnings": _dedupe(warnings),
    }


def project_rtcm_artifact(path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    classification = classify_rtcm_artifact(path, metadata)
    return asdict(
        RTCMArtifactProjection(
            artifact_ref_id=str(metadata.get("artifact_ref_id") or f"rtcmart_{uuid4().hex}"),
            artifact_type=classification["artifact_type"],
            source_path=str(path),
            rtcm_session_id=metadata.get("rtcm_session_id") or _infer_rtcm_session_id(path),
            context_id=metadata.get("context_id"),
            producer=str(metadata.get("producer") or "rtcm"),
            consumer_candidates=classification["consumer_candidates"],
            truth_event_eligible=bool(classification["truth_event_eligible"]),
            asset_candidate_eligible=bool(classification["asset_candidate_eligible"]),
            memory_candidate_eligible=bool(classification["memory_candidate_eligible"]),
            long_term_memory_eligible=bool(classification["long_term_memory_eligible"]),
            warnings=list(classification.get("warnings") or []),
            observed_at=_now(),
        )
    )


def project_roundtable_session(session_path_or_record: str | Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    record = session_path_or_record if isinstance(session_path_or_record, dict) else {}
    source_path = session_path_or_record if isinstance(session_path_or_record, str) else record.get("source_path")
    executor = _normalize_executor(metadata.get("executor") or record.get("executor") or "rtcm")
    status = _normalize_state(metadata.get("status") or record.get("status") or _infer_status(str(source_path or "")))
    artifacts = list(metadata.get("artifact_refs") or record.get("artifact_refs") or [])
    return asdict(
        RoundtableSessionProjection(
            roundtable_session_ref_id=str(metadata.get("roundtable_session_ref_id") or record.get("roundtable_session_ref_id") or f"rttbl_{uuid4().hex}"),
            executor=executor,
            rtcm_session_id=metadata.get("rtcm_session_id") or record.get("rtcm_session_id") or _infer_rtcm_session_id(str(source_path or "")),
            context_id=metadata.get("context_id") or record.get("context_id"),
            request_id=metadata.get("request_id") or record.get("request_id"),
            gateway_thread_id=metadata.get("gateway_thread_id") or record.get("gateway_thread_id"),
            mode_session_id=metadata.get("mode_session_id") or record.get("mode_session_id"),
            mode_invocation_id=metadata.get("mode_invocation_id") or record.get("mode_invocation_id"),
            status=status,
            topic=metadata.get("topic") or record.get("topic"),
            artifact_refs=artifacts,
            truth_candidate_refs=list(metadata.get("truth_candidate_refs") or record.get("truth_candidate_refs") or []),
            asset_candidate_refs=list(metadata.get("asset_candidate_refs") or record.get("asset_candidate_refs") or []),
            memory_candidate_refs=list(metadata.get("memory_candidate_refs") or record.get("memory_candidate_refs") or []),
            followup_refs=list(metadata.get("followup_refs") or record.get("followup_refs") or []),
            source_path=str(source_path) if source_path else None,
            warnings=[] if executor != "unknown" else ["unknown_roundtable_executor"],
            observed_at=_now(),
        )
    )


def project_rtcm_truth_candidates(artifact_projections: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []
    type_map = {
        "final_report": "final_report_conclusion",
        "signoff": "signoff_decision",
        "verdict": "rtcm_verdict",
        "evidence_ledger": "evidence_summary",
    }
    for artifact in artifact_projections or []:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "council_log":
            continue
        if not artifact.get("truth_event_eligible"):
            continue
        truth_type = type_map.get(str(artifact_type), "unknown")
        if truth_type == "unknown":
            warnings.append(f"unknown_truth_mapping:{artifact_type}")
        candidates.append(
            asdict(
                RTCMTruthProjection(
                    truth_candidate_id=f"rtcmtruth_{uuid4().hex}",
                    truth_type=truth_type,
                    truth_track="rtcm_truth",
                    source_artifact_ref=str(artifact.get("artifact_ref_id")),
                    rtcm_session_id=artifact.get("rtcm_session_id"),
                    subject_type="rtcm_artifact",
                    subject_id=artifact.get("source_path"),
                    evidence_refs=[str(artifact.get("artifact_ref_id"))],
                    confidence=0.9 if truth_type != "unknown" else 0.3,
                    warnings=[],
                    observed_at=_now(),
                )
            )
        )
    return {
        "candidate_count": len(candidates),
        "by_truth_type": dict(Counter(candidate["truth_type"] for candidate in candidates)),
        "candidates": candidates,
        "warnings": _dedupe(warnings),
    }


def project_rtcm_asset_candidates(artifact_projections: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []
    category_map = {
        "final_report": "A5_cognitive_method",
        "evidence_ledger": "A6_information_source_network",
        "issue_card": "A4_execution_experience",
        "brief_report": "A3_workflow_solution",
    }
    for artifact in artifact_projections or []:
        if artifact.get("artifact_type") == "council_log":
            continue
        if not artifact.get("asset_candidate_eligible"):
            continue
        category = category_map.get(str(artifact.get("artifact_type")), "unknown")
        projected_asset = None
        if project_asset_candidate is not None:
            try:
                projected_asset = project_asset_candidate(str(artifact.get("source_path")), {"source_system": "rtcm"})
            except Exception as exc:  # pragma: no cover
                warnings.append(f"asset_projection_error:{type(exc).__name__}")
        candidates.append(
            {
                "asset_candidate_ref": f"rtcmasset_{uuid4().hex}",
                "source_artifact_ref": artifact.get("artifact_ref_id"),
                "rtcm_session_id": artifact.get("rtcm_session_id"),
                "artifact_type": artifact.get("artifact_type"),
                "asset_category": category,
                "lifecycle_tier": "candidate",
                "projected_asset": projected_asset,
                "warnings": [] if category != "unknown" else ["unknown_asset_candidate_mapping"],
            }
        )
    return {
        "candidate_count": len(candidates),
        "by_asset_category": dict(Counter(candidate["asset_category"] for candidate in candidates)),
        "candidates": candidates,
        "warnings": _dedupe(warnings),
    }


def project_rtcm_memory_candidates(artifact_projections: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for artifact in artifact_projections or []:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "council_log":
            continue
        if not artifact.get("memory_candidate_eligible"):
            continue
        memory_layer = "L3_persistent" if artifact_type in {"final_report", "brief_report"} else "L4_knowledge_graph"
        if artifact_type == "dossier":
            memory_layer = "L2_session"
        classified_memory = None
        if classify_memory_artifact is not None:
            try:
                classified_memory = classify_memory_artifact(str(artifact.get("source_path")), {"source_system": "rtcm"})
            except Exception as exc:  # pragma: no cover
                warnings.append(f"memory_projection_error:{type(exc).__name__}")
        candidates.append(
            {
                "memory_candidate_ref": f"rtcmmem_{uuid4().hex}",
                "source_artifact_ref": artifact.get("artifact_ref_id"),
                "rtcm_session_id": artifact.get("rtcm_session_id"),
                "artifact_type": artifact_type,
                "memory_layer": memory_layer,
                "memory_scope": "rtcm",
                "long_term_memory_eligible": bool(artifact.get("long_term_memory_eligible")),
                "classified_memory": classified_memory,
                "warnings": [],
            }
        )
    return {
        "candidate_count": len(candidates),
        "by_memory_layer": dict(Counter(candidate["memory_layer"] for candidate in candidates)),
        "candidates": candidates,
        "warnings": _dedupe(warnings),
    }


def project_rtcm_followups(artifact_projections: List[Dict[str, Any]]) -> Dict[str, Any]:
    followups: List[Dict[str, Any]] = []
    for artifact in artifact_projections or []:
        if artifact.get("artifact_type") not in {"followup", "issue_card", "final_report"}:
            continue
        source = str(artifact.get("source_path") or "").lower()
        target_mode = _infer_followup_target_mode(source)
        followups.append(
            asdict(
                RTCMFollowupProjection(
                    followup_ref_id=f"rtcmfollow_{uuid4().hex}",
                    source_artifact_ref=str(artifact.get("artifact_ref_id")),
                    rtcm_session_id=artifact.get("rtcm_session_id"),
                    suggested_target_mode=target_mode,
                    suggested_action_type=_infer_followup_action(source),
                    priority="normal",
                    requires_user_confirmation=target_mode in {"autonomous_agent", "roundtable", "unknown"},
                    mode_invocation_candidate={
                        "from_mode": "roundtable",
                        "to_mode": target_mode,
                        "return_policy": "return_to_parent",
                    }
                    if target_mode != "unknown"
                    else None,
                    warnings=[] if target_mode != "unknown" else ["followup_without_target_mode"],
                    observed_at=_now(),
                )
            )
        )
    return {
        "followup_count": len(followups),
        "by_target_mode": dict(Counter(followup["suggested_target_mode"] for followup in followups)),
        "followups": followups,
        "warnings": _dedupe([w for followup in followups for w in followup.get("warnings", [])]),
    }


def link_rtcm_to_mode_invocation(
    roundtable_projection: Dict[str, Any],
    mode_invocation: Optional[Dict[str, Any]] = None,
    mode_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    projection = dict(roundtable_projection or {})
    invocation = dict(mode_invocation or {})
    metadata = dict(mode_metadata or {})
    warnings: List[str] = []
    if invocation:
        projection["mode_invocation_id"] = invocation.get("mode_invocation_id") or projection.get("mode_invocation_id")
        projection["mode_session_id"] = invocation.get("mode_session_id") or projection.get("mode_session_id")
    else:
        warnings.append("missing_mode_invocation")
    mode_session = metadata.get("mode_session") or {}
    projection["mode_session_id"] = projection.get("mode_session_id") or metadata.get("mode_session_id") or mode_session.get("mode_session_id")
    link_ok = invocation.get("to_mode") == "roundtable" and projection.get("executor") == "rtcm"
    if not link_ok:
        warnings.append("rtcm_roundtable_mode_invocation_link_not_confirmed")
    projection["warnings"] = _dedupe(list(projection.get("warnings") or []) + warnings)
    return {"linked_projection": projection, "link_ok": link_ok, "warnings": _dedupe(warnings)}


def scan_rtcm_artifacts(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    base = Path(root) if root else DEFAULT_ROOT
    max_files = max(0, min(int(max_files), 2000))
    records: List[Dict[str, Any]] = []
    warnings: List[str] = []
    scanned = 0
    if not base.exists():
        return {
            "root": str(base),
            "scanned_count": 0,
            "classified_count": 0,
            "by_artifact_type": {},
            "truth_eligible_count": 0,
            "asset_candidate_count": 0,
            "memory_candidate_count": 0,
            "followup_candidate_count": 0,
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
        text = str(path).lower().replace("\\", "/")
        if not any(keyword in text for keyword in RTCM_KEYWORDS):
            continue
        scanned += 1
        records.append(project_rtcm_artifact(str(path)))
    return {
        "root": str(base),
        "scanned_count": scanned,
        "classified_count": len(records),
        "by_artifact_type": dict(Counter(record["artifact_type"] for record in records)),
        "truth_eligible_count": sum(1 for record in records if record.get("truth_event_eligible")),
        "asset_candidate_count": sum(1 for record in records if record.get("asset_candidate_eligible")),
        "memory_candidate_count": sum(1 for record in records if record.get("memory_candidate_eligible")),
        "followup_candidate_count": sum(1 for record in records if record.get("artifact_type") == "followup"),
        "warnings": _dedupe(warnings),
        "records": records,
    }


def aggregate_rtcm_roundtable_projection(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    artifact_projection = scan_rtcm_artifacts(root, max_files=max_files)
    artifacts = artifact_projection.get("records", [])
    truth = project_rtcm_truth_candidates(artifacts)
    assets = project_rtcm_asset_candidates(artifacts)
    memory = project_rtcm_memory_candidates(artifacts)
    followups = project_rtcm_followups(artifacts)
    projection = {
        "artifact_projection": artifact_projection,
        "truth_candidates": truth,
        "asset_candidates": assets,
        "memory_candidates": memory,
        "followups": followups,
    }
    risks = detect_rtcm_integration_risks(projection)
    warnings = _dedupe(
        list(artifact_projection.get("warnings") or [])
        + list(truth.get("warnings") or [])
        + list(assets.get("warnings") or [])
        + list(memory.get("warnings") or [])
        + list(followups.get("warnings") or [])
        + list(risks.get("warnings") or [])
    )
    projection.update(
        {
            "risk_signals": risks,
            "summary": {
                "classified_count": artifact_projection.get("classified_count", 0),
                "truth_candidate_count": truth.get("candidate_count", 0),
                "asset_candidate_count": assets.get("candidate_count", 0),
                "memory_candidate_count": memory.get("candidate_count", 0),
                "followup_count": followups.get("followup_count", 0),
                "risk_count": risks.get("risk_count", 0),
            },
            "warnings": warnings,
        }
    )
    return projection


def detect_rtcm_integration_risks(projection: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = projection.get("artifact_projection", {}).get("records", [])
    truth_candidates = projection.get("truth_candidates", {}).get("candidates", [])
    followups = projection.get("followups", {}).get("followups", [])
    risk_records: List[Dict[str, Any]] = []
    risk_types: List[str] = []
    artifact_types = {a.get("artifact_type") for a in artifacts}
    truth_artifact_refs = {c.get("source_artifact_ref") for c in truth_candidates}

    for artifact in artifacts:
        artifact_type = artifact.get("artifact_type")
        if artifact_type == "unknown":
            _add_risk(risk_records, risk_types, "rtcm_artifact_unknown_type", artifact)
        if artifact_type == "council_log" and artifact.get("long_term_memory_eligible"):
            _add_risk(risk_records, risk_types, "council_log_marked_long_term", artifact)
        if artifact_type == "final_report":
            if artifact.get("artifact_ref_id") not in truth_artifact_refs:
                _add_risk(risk_records, risk_types, "final_report_missing_truth_projection", artifact)
            if not artifact.get("asset_candidate_eligible"):
                _add_risk(risk_records, risk_types, "final_report_not_asset_candidate", artifact)
        if artifact_type == "signoff" and not artifact.get("rtcm_session_id"):
            _add_risk(risk_records, risk_types, "signoff_without_session", artifact)
        if artifact_type == "evidence_ledger" and "final_report" not in artifact_types:
            _add_risk(risk_records, risk_types, "evidence_ledger_without_final_report", artifact)

    for followup in followups:
        if followup.get("suggested_target_mode") == "unknown":
            _add_risk(risk_records, risk_types, "followup_without_target_mode", followup)

    sessions = projection.get("roundtable_sessions", [])
    for session in sessions:
        if session.get("executor") == "rtcm" and not session.get("mode_invocation_id"):
            _add_risk(risk_records, risk_types, "rtcm_without_mode_invocation", session)
        if session.get("executor") == "rtcm" and not session.get("context_id"):
            _add_risk(risk_records, risk_types, "rtcm_session_without_context_link", session)
        if session.get("status") == "active" and session.get("stale"):
            _add_risk(risk_records, risk_types, "stale_active_session", session)
        if session.get("status") == "failed" and not session.get("followup_refs"):
            _add_risk(risk_records, risk_types, "failed_session_without_followup", session)

    return {
        "risk_count": len(risk_records),
        "risk_by_type": dict(Counter(risk_types)),
        "risk_records": risk_records,
        "warnings": [],
    }


def generate_rtcm_integration_sample(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    max_files: int = 500,
) -> Dict[str, Any]:
    result = aggregate_rtcm_roundtable_projection(root, max_files=max_files)
    result["generated_at"] = _now()
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _consumers_for_artifact(artifact_type: str) -> List[str]:
    if artifact_type == "final_report":
        return ["truth_projection", "asset_candidate_projection", "memory_candidate_projection", "followup_projection"]
    if artifact_type == "evidence_ledger":
        return ["truth_projection", "asset_candidate_projection", "memory_candidate_projection"]
    if artifact_type in {"signoff", "verdict"}:
        return ["truth_projection"]
    if artifact_type in {"dossier", "issue_card", "brief_report"}:
        return ["memory_candidate_projection", "asset_candidate_projection"]
    return []


def _infer_rtcm_session_id(path: str) -> Optional[str]:
    parts = [part for part in Path(path).parts if part and part not in {":", "\\"}]
    lowered = [part.lower() for part in parts]
    for marker in ("rtcm", ".deerflow"):
        if marker in lowered:
            idx = lowered.index(marker)
            if idx + 1 < len(parts):
                candidate = parts[idx + 1]
                if candidate.lower() not in {"dossiers", "reports", "final_report", "followup"}:
                    return candidate
    return None


def _infer_status(path: str) -> str:
    text = path.lower()
    if "archived" in text:
        return "archived"
    if "signed_off" in text or "signoff" in text:
        return "signed_off"
    if "failed" in text:
        return "failed"
    if "paused" in text:
        return "paused"
    if "waiting" in text:
        return "waiting_for_user"
    if "active" in text:
        return "active"
    return "unknown"


def _normalize_executor(executor: str) -> str:
    value = str(executor or "unknown").lower()
    return value if value in ROUNDTABLE_EXECUTORS else "unknown"


def _normalize_state(status: str) -> str:
    value = str(status or "unknown").lower()
    return value if value in STATE_PROJECTIONS else "unknown"


def _infer_followup_target_mode(text: str) -> str:
    if any(token in text for token in ["fix", "verify", "run_test", "run test", "test"]):
        return "task"
    if any(token in text for token in ["multi-step", "plan", "pipeline", "workflow"]):
        return "workflow"
    if any(token in text for token in ["monitor", "recurring", "long-running", "autonomous"]):
        return "autonomous_agent"
    if any(token in text for token in ["dispute", "review", "decision", "roundtable"]):
        return "roundtable"
    return "unknown"


def _infer_followup_action(text: str) -> str:
    if "verify" in text or "test" in text:
        return "verify"
    if "fix" in text:
        return "fix"
    if "monitor" in text:
        return "monitor"
    if "review" in text:
        return "review"
    return "followup"


def _source_text(path_or_record: str | Dict[str, Any], metadata: Dict[str, Any]) -> str:
    if isinstance(path_or_record, dict):
        value = " ".join(str(item) for item in path_or_record.values())
    else:
        value = str(path_or_record)
    return f"{value} {' '.join(str(item) for item in metadata.values())}".lower().replace("\\", "/")


def _add_risk(records: List[Dict[str, Any]], types: List[str], risk_type: str, record: Dict[str, Any]) -> None:
    types.append(risk_type)
    records.append(
        {
            "risk_type": risk_type,
            "source_path": record.get("source_path"),
            "artifact_type": record.get("artifact_type"),
            "rtcm_session_id": record.get("rtcm_session_id"),
        }
    )


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
