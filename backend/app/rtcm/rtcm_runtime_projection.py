"""RTCM runtime read-only projection surface.

This module classifies RTCM support/runtime/source paths and groups them into
session-level projections. It does not mutate RTCM runtime files, state
machines, dossiers, governance, memory, or assets.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import uuid4

from app.rtcm.rtcm_integration_contract import (
    classify_rtcm_artifact,
    project_rtcm_artifact,
    project_rtcm_asset_candidates,
    project_rtcm_followups,
    project_rtcm_memory_candidates,
    project_rtcm_truth_candidates,
)


DEFAULT_ROOT = Path(r"E:\OpenClaw-Base\deerflow")
USER_RTCM_ROOT = Path(r"C:\Users\win\.deerflow\rtcm")
DEFAULT_SAMPLE_PATH = DEFAULT_ROOT / "migration_reports" / "foundation_audit" / "R241-7B_RTCM_RUNTIME_PROJECTION_SAMPLE.json"
EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv"}
SURFACE_TYPES = {
    "rtcm_session_runtime",
    "rtcm_project_dossier",
    "rtcm_config_spec",
    "rtcm_prompt_template",
    "rtcm_source_code",
    "rtcm_test_file",
    "rtcm_docs",
    "rtcm_example_project",
    "rtcm_runtime_state",
    "rtcm_evidence_extract",
    "rtcm_validation_run",
    "rtcm_report",
    "rtcm_schema_spec",
    "rtcm_feishu_bridge",
    "rtcm_recovery_component",
    "rtcm_observability_component",
    "rtcm_unknown",
}
RUNTIME_ROLES = {
    "session_state",
    "session_manifest",
    "project_context",
    "council_transcript",
    "evidence",
    "final_decision",
    "followup_action",
    "config",
    "prompt",
    "source",
    "test",
    "documentation",
    "adapter",
    "runtime_cache",
    "validation",
    "unknown",
}
RTCM_SCAN_KEYWORDS = {
    "rtcm",
    "dossier",
    "project_dossier",
    "final_report",
    "signoff",
    "council_log",
    "evidence_ledger",
    "evidence_extract",
    "followup",
    "verdict",
    "issue_card",
    "session_state",
    "manifest",
    "prompts",
    "config",
}


@dataclass(frozen=True)
class RTCMRuntimePathProjection:
    runtime_ref_id: str
    source_path: str
    surface_type: str
    runtime_role: str
    artifact_type: Optional[str]
    rtcm_session_id: Optional[str]
    context_id: Optional[str]
    gateway_thread_id: Optional[str]
    mode_session_id: Optional[str]
    mode_invocation_id: Optional[str]
    is_runtime_state: bool
    is_source_code: bool
    is_config: bool
    is_prompt: bool
    is_report: bool
    is_session_artifact: bool
    truth_candidate_eligible: bool
    asset_candidate_eligible: bool
    memory_candidate_eligible: bool
    followup_candidate_eligible: bool
    should_output_content: bool
    warnings: List[str]
    observed_at: str


@dataclass(frozen=True)
class RTCMSessionRuntimeProjection:
    session_projection_id: str
    rtcm_session_id: str
    session_root: str
    status: str
    manifest_refs: List[str]
    runtime_state_refs: List[str]
    dossier_refs: List[str]
    final_report_refs: List[str]
    signoff_refs: List[str]
    evidence_refs: List[str]
    council_log_refs: List[str]
    followup_refs: List[str]
    context_links: List[Dict[str, Any]]
    mode_links: List[Dict[str, Any]]
    truth_candidate_refs: List[str]
    asset_candidate_refs: List[str]
    memory_candidate_refs: List[str]
    warnings: List[str]
    observed_at: str


@dataclass(frozen=True)
class RTCMContextLinkProjection:
    link_projection_id: str
    link_type: str
    confidence: float
    warnings: List[str]
    observed_at: str
    rtcm_session_id: Optional[str] = None
    context_id: Optional[str] = None
    request_id: Optional[str] = None
    gateway_thread_id: Optional[str] = None
    mode_session_id: Optional[str] = None
    mode_invocation_id: Optional[str] = None
    source_path: Optional[str] = None


def discover_rtcm_runtime_roots(root: Optional[str] = None) -> Dict[str, Any]:
    base = Path(root) if root else DEFAULT_ROOT
    candidates = [
        base / "rtcm",
        base / ".deerflow" / "rtcm",
        USER_RTCM_ROOT,
        base / "backend" / "src" / "rtcm",
        base / "migration_reports" / "foundation_audit" / "R241-7A_RTCM_ROUNDTABLE_INTEGRATION_SAMPLE.json",
    ]
    discovered: List[Dict[str, Any]] = []
    missing: List[str] = []
    for candidate in candidates:
        if candidate.exists():
            discovered.append(
                {
                    "path": str(candidate),
                    "is_dir": candidate.is_dir(),
                    "is_file": candidate.is_file(),
                    "kind": _root_kind(candidate),
                }
            )
        else:
            missing.append(str(candidate))
    return {
        "root": str(base),
        "discovered_roots": discovered,
        "missing_roots": missing,
        "warnings": ["no_rtcm_roots_discovered"] if not discovered else [],
    }


def classify_rtcm_runtime_path(path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    text = str(path).replace("\\", "/").lower()
    name = Path(text).name
    artifact = classify_rtcm_artifact(path, metadata)
    surface = "rtcm_unknown"
    role = "unknown"
    warnings: List[str] = []

    if "/config/" in text or name.endswith((".yaml", ".yml", ".toml", ".ini")) and "rtcm" in text:
        surface, role = "rtcm_config_spec", "config"
    elif "/prompts/" in text or "prompt" in name:
        surface, role = "rtcm_prompt_template", "prompt"
    elif "/docs/" in text or "readme" in name or name.endswith(".md") and "docs" in text:
        surface, role = "rtcm_docs", "documentation"
    elif "backend/src/rtcm" in text or "/src/rtcm" in text or "backend\\src\\rtcm" in str(path).lower():
        if "_test." in name or ".test." in name or name.startswith("test_"):
            surface, role = "rtcm_test_file", "test"
        else:
            surface, role = "rtcm_source_code", "source"
    elif "/tests/" in text or "_test." in name or ".test." in name or name.startswith("test_"):
        surface, role = "rtcm_test_file", "test"
    elif "session_state.json" in name or "/runtime/" in text and "state" in name:
        surface, role = "rtcm_runtime_state", "session_state"
    elif "/runtime/evidence_extracts/" in text or "evidence_extract" in name:
        surface, role = "rtcm_evidence_extract", "evidence"
    elif "/project_dossier/" in text or "/dossiers/" in text:
        surface = "rtcm_project_dossier"
        role = _role_from_artifact(artifact["artifact_type"])
    elif "examples" in text and "rtcm" in text:
        surface, role = "rtcm_example_project", "project_context"
    elif "validation" in text or "validate" in name:
        surface, role = "rtcm_validation_run", "validation"
    elif "schema" in name:
        surface, role = "rtcm_schema_spec", "config"
    elif "feishu" in text or "lark" in text:
        surface, role = "rtcm_feishu_bridge", "adapter"
    elif "recovery" in text or "rollback" in text:
        surface, role = "rtcm_recovery_component", "adapter"
    elif "observability" in text or "watchdog" in text or "monitor" in text:
        surface, role = "rtcm_observability_component", "adapter"
    elif artifact["artifact_type"] in {"final_report", "brief_report", "signoff", "verdict"}:
        surface, role = "rtcm_report", _role_from_artifact(artifact["artifact_type"])
    elif artifact["artifact_type"] != "unknown":
        surface, role = "rtcm_session_runtime", _role_from_artifact(artifact["artifact_type"])
    else:
        warnings.append("unknown_rtcm_runtime_surface")

    if artifact["artifact_type"] == "council_log":
        warnings.append("council_log_not_long_term_memory")

    truth = bool(artifact.get("truth_event_eligible")) and surface not in {"rtcm_source_code", "rtcm_test_file", "rtcm_prompt_template", "rtcm_config_spec", "rtcm_docs"}
    asset = bool(artifact.get("asset_candidate_eligible")) and surface not in {"rtcm_source_code", "rtcm_test_file", "rtcm_prompt_template", "rtcm_config_spec", "rtcm_docs"}
    memory = bool(artifact.get("memory_candidate_eligible")) or surface == "rtcm_evidence_extract"
    followup = artifact.get("artifact_type") in {"followup", "issue_card"} or role == "followup_action"

    if surface in {"rtcm_source_code", "rtcm_test_file", "rtcm_prompt_template", "rtcm_config_spec", "rtcm_docs"}:
        memory = False
        followup = False

    return {
        "surface_type": surface,
        "runtime_role": role,
        "artifact_type": artifact.get("artifact_type"),
        "truth_candidate_eligible": truth,
        "asset_candidate_eligible": asset,
        "memory_candidate_eligible": memory,
        "followup_candidate_eligible": followup,
        "warnings": _dedupe(warnings + list(artifact.get("warnings") or [])),
    }


def project_rtcm_runtime_path(path: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    classification = classify_rtcm_runtime_path(path, metadata)
    artifact = project_rtcm_artifact(path, metadata)
    surface = classification["surface_type"]
    role = classification["runtime_role"]
    return asdict(
        RTCMRuntimePathProjection(
            runtime_ref_id=str(metadata.get("runtime_ref_id") or f"rtcmrun_{uuid4().hex}"),
            source_path=str(path),
            surface_type=surface,
            runtime_role=role,
            artifact_type=classification.get("artifact_type"),
            rtcm_session_id=metadata.get("rtcm_session_id") or artifact.get("rtcm_session_id") or _infer_session_id_from_runtime_path(path),
            context_id=metadata.get("context_id"),
            gateway_thread_id=metadata.get("gateway_thread_id"),
            mode_session_id=metadata.get("mode_session_id"),
            mode_invocation_id=metadata.get("mode_invocation_id"),
            is_runtime_state=surface == "rtcm_runtime_state",
            is_source_code=surface == "rtcm_source_code",
            is_config=surface in {"rtcm_config_spec", "rtcm_schema_spec"},
            is_prompt=surface == "rtcm_prompt_template",
            is_report=surface == "rtcm_report" or role == "final_decision",
            is_session_artifact=surface in {"rtcm_session_runtime", "rtcm_project_dossier", "rtcm_runtime_state", "rtcm_evidence_extract", "rtcm_report"},
            truth_candidate_eligible=bool(classification["truth_candidate_eligible"]),
            asset_candidate_eligible=bool(classification["asset_candidate_eligible"]),
            memory_candidate_eligible=bool(classification["memory_candidate_eligible"]),
            followup_candidate_eligible=bool(classification["followup_candidate_eligible"]),
            should_output_content=False,
            warnings=list(classification.get("warnings") or []),
            observed_at=_now(),
        )
    )


def discover_rtcm_sessions(root: Optional[str] = None, max_files: int = 1000) -> Dict[str, Any]:
    base = Path(root) if root else DEFAULT_ROOT
    max_files = max(0, min(int(max_files), 5000))
    warnings: List[str] = []
    if not base.exists():
        return {"session_count": 0, "sessions": [], "warnings": ["root_missing"]}

    candidate_roots: Dict[str, List[Path]] = {}
    scanned = 0
    for path in base.rglob("*"):
        if scanned >= max_files:
            warnings.append("max_files_reached")
            break
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        scanned += 1
        text = str(path).replace("\\", "/").lower()
        if not any(marker in text for marker in ["project_dossier", "session_state.json", "final_report", "evidence_ledger", "council_log", ".deerflow/rtcm/sessions", "rtcm/examples"]):
            continue
        root_path = _infer_session_root(path)
        candidate_roots.setdefault(str(root_path), []).append(path)

    sessions = [_session_descriptor(root_path, files) for root_path, files in candidate_roots.items()]
    return {"session_count": len(sessions), "sessions": sessions, "warnings": _dedupe(warnings)}


def project_rtcm_session_runtime(session_root: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    metadata = dict(metadata or {})
    root = Path(session_root)
    warnings: List[str] = []
    if not root.exists():
        warnings.append("session_root_missing")
        files: List[Path] = []
    else:
        files = [path for path in root.rglob("*") if path.is_file() and not any(part in EXCLUDED_DIRS for part in path.parts)]
    projections = [project_rtcm_runtime_path(str(path), metadata) for path in files]
    artifact_like = [project_rtcm_artifact(p["source_path"], {"rtcm_session_id": p.get("rtcm_session_id")}) for p in projections if p["is_session_artifact"]]
    truth = project_rtcm_truth_candidates(artifact_like)
    assets = project_rtcm_asset_candidates(artifact_like)
    memory = project_rtcm_memory_candidates(artifact_like)
    session_id = metadata.get("rtcm_session_id") or _session_id_from_root(root)
    return asdict(
        RTCMSessionRuntimeProjection(
            session_projection_id=f"rtcmsess_{uuid4().hex}",
            rtcm_session_id=session_id,
            session_root=str(root),
            status=metadata.get("status") or _infer_status_from_files(projections),
            manifest_refs=_refs_by_role(projections, {"session_manifest"}),
            runtime_state_refs=_refs_by_role(projections, {"session_state"}),
            dossier_refs=_refs_by_surface(projections, {"rtcm_project_dossier"}),
            final_report_refs=_refs_by_role(projections, {"final_decision"}),
            signoff_refs=_refs_by_artifact(projections, {"signoff"}),
            evidence_refs=_refs_by_role(projections, {"evidence"}),
            council_log_refs=_refs_by_role(projections, {"council_transcript"}),
            followup_refs=_refs_by_role(projections, {"followup_action"}),
            context_links=[],
            mode_links=[],
            truth_candidate_refs=[c["truth_candidate_id"] for c in truth.get("candidates", [])],
            asset_candidate_refs=[c["asset_candidate_ref"] for c in assets.get("candidates", [])],
            memory_candidate_refs=[c["memory_candidate_ref"] for c in memory.get("candidates", [])],
            warnings=_dedupe(warnings + [w for p in projections for w in p.get("warnings", []) if w == "council_log_not_long_term_memory"]),
            observed_at=_now(),
        )
    )


def project_rtcm_context_links(
    session_projection: Dict[str, Any],
    mode_metadata: Optional[Dict[str, Any]] = None,
    context_envelope: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(mode_metadata or {})
    context = dict(context_envelope or {})
    mode_session = metadata.get("mode_session") or {}
    warnings: List[str] = []
    links: List[Dict[str, Any]] = []
    session_id = session_projection.get("rtcm_session_id")

    if context.get("context_id"):
        links.append(_context_link(session_id, "belongs_to_context", context_id=context.get("context_id"), request_id=context.get("request_id")))
    else:
        warnings.append("missing_context_link")
    if context.get("thread_id"):
        links.append(_context_link(session_id, "belongs_to_thread", gateway_thread_id=context.get("thread_id")))
    if mode_session.get("mode_session_id") or metadata.get("mode_session_id"):
        links.append(
            _context_link(
                session_id,
                "belongs_to_mode_session",
                mode_session_id=metadata.get("mode_session_id") or mode_session.get("mode_session_id"),
                mode_invocation_id=metadata.get("mode_invocation_id"),
            )
        )
    return {"links": links, "warnings": _dedupe(warnings)}


def project_rtcm_runtime_truth_asset_memory_followup(session_projection: Dict[str, Any]) -> Dict[str, Any]:
    root = session_projection.get("session_root")
    if not root:
        return {
            "truth_candidates": {"candidate_count": 0, "candidates": [], "warnings": ["session_root_missing"]},
            "asset_candidates": {"candidate_count": 0, "candidates": [], "warnings": ["session_root_missing"]},
            "memory_candidates": {"candidate_count": 0, "candidates": [], "warnings": ["session_root_missing"]},
            "followup_candidates": {"followup_count": 0, "followups": [], "warnings": ["session_root_missing"]},
        }
    files = [path for path in Path(root).rglob("*") if path.is_file()] if Path(root).exists() else []
    artifacts = [project_rtcm_artifact(str(path), {"rtcm_session_id": session_projection.get("rtcm_session_id")}) for path in files]
    return {
        "truth_candidates": project_rtcm_truth_candidates(artifacts),
        "asset_candidates": project_rtcm_asset_candidates(artifacts),
        "memory_candidates": project_rtcm_memory_candidates(artifacts),
        "followup_candidates": project_rtcm_followups(artifacts),
    }


def scan_rtcm_runtime_projection(root: Optional[str] = None, max_files: int = 1000) -> Dict[str, Any]:
    base = Path(root) if root else DEFAULT_ROOT
    max_files = max(0, min(int(max_files), 5000))
    records: List[Dict[str, Any]] = []
    warnings: List[str] = []
    if not base.exists():
        return _empty_scan(str(base), ["root_missing"])
    scanned = 0
    for path in base.rglob("*"):
        if scanned >= max_files:
            warnings.append("max_files_reached")
            break
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if not path.is_file():
            continue
        text = str(path).replace("\\", "/").lower()
        if not any(keyword in text for keyword in RTCM_SCAN_KEYWORDS):
            continue
        scanned += 1
        records.append(project_rtcm_runtime_path(str(path)))
    sessions = discover_rtcm_sessions(root, max_files=max_files)
    return {
        "root": str(base),
        "scanned_count": scanned,
        "classified_count": len(records),
        "by_surface_type": dict(Counter(r["surface_type"] for r in records)),
        "by_runtime_role": dict(Counter(r["runtime_role"] for r in records)),
        "unknown_count": sum(1 for r in records if r["surface_type"] == "rtcm_unknown"),
        "session_count": sessions.get("session_count", 0),
        "truth_candidate_count": sum(1 for r in records if r["truth_candidate_eligible"]),
        "asset_candidate_count": sum(1 for r in records if r["asset_candidate_eligible"]),
        "memory_candidate_count": sum(1 for r in records if r["memory_candidate_eligible"]),
        "followup_candidate_count": sum(1 for r in records if r["followup_candidate_eligible"]),
        "warnings": _dedupe(warnings + sessions.get("warnings", [])),
        "records": records,
    }


def detect_rtcm_runtime_projection_risks(projection: Dict[str, Any]) -> Dict[str, Any]:
    records = projection.get("runtime_path_projection", projection).get("records", [])
    sessions = projection.get("session_discovery", {}).get("sessions", [])
    risk_records: List[Dict[str, Any]] = []
    risk_types: List[str] = []
    for record in records:
        if record.get("surface_type") == "rtcm_unknown":
            _add_risk(risk_records, risk_types, "unknown_rtcm_runtime_surface", record)
        if record.get("artifact_type") == "council_log" and record.get("long_term_memory_eligible"):
            _add_risk(risk_records, risk_types, "council_log_marked_long_term", record)
        if record.get("surface_type") == "rtcm_runtime_state" and not record.get("rtcm_session_id"):
            _add_risk(risk_records, risk_types, "runtime_state_without_session", record)
        if record.get("followup_candidate_eligible") and record.get("runtime_role") == "unknown":
            _add_risk(risk_records, risk_types, "followup_without_target_mode", record)
        if record.get("is_source_code") and record.get("truth_candidate_eligible"):
            _add_risk(risk_records, risk_types, "source_code_misclassified_as_session_artifact", record)
        if record.get("is_prompt") and record.get("truth_candidate_eligible"):
            _add_risk(risk_records, risk_types, "prompt_template_misclassified_as_truth", record)
        if record.get("is_config") and record.get("asset_candidate_eligible"):
            _add_risk(risk_records, risk_types, "config_spec_misclassified_as_asset", record)

    for session in sessions:
        if not session.get("has_manifest"):
            _add_risk(risk_records, risk_types, "session_missing_manifest", session)
        if not session.get("has_final_report") and session.get("has_signoff"):
            _add_risk(risk_records, risk_types, "signoff_without_final_report", session)
        if session.get("has_final_report") and not session.get("has_evidence_ledger"):
            _add_risk(risk_records, risk_types, "final_report_missing_evidence_ledger", session)
        if session.get("has_evidence_ledger") and not session.get("has_final_report"):
            _add_risk(risk_records, risk_types, "evidence_ledger_without_final_report", session)
        if not session.get("context_links"):
            _add_risk(risk_records, risk_types, "session_missing_context_link", session)

    return {
        "risk_count": len(risk_records),
        "risk_by_type": dict(Counter(risk_types)),
        "risk_records": risk_records,
        "warnings": [],
    }


def generate_rtcm_runtime_projection_report(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    max_files: int = 1000,
) -> Dict[str, Any]:
    discovered = discover_rtcm_runtime_roots(root)
    runtime_scan = scan_rtcm_runtime_projection(root, max_files=max_files)
    session_discovery = discover_rtcm_sessions(root, max_files=max_files)
    session_projections = [project_rtcm_session_runtime(session["session_root"]) for session in session_discovery.get("sessions", [])]
    context_links = [project_rtcm_context_links(session) for session in session_projections]
    tamf = [project_rtcm_runtime_truth_asset_memory_followup(session) for session in session_projections]
    risk_signals = detect_rtcm_runtime_projection_risks(
        {
            "runtime_path_projection": runtime_scan,
            "session_discovery": session_discovery,
            "session_projections": session_projections,
        }
    )
    warnings = _dedupe(
        list(discovered.get("warnings") or [])
        + list(runtime_scan.get("warnings") or [])
        + list(session_discovery.get("warnings") or [])
        + [w for links in context_links for w in links.get("warnings", [])]
        + list(risk_signals.get("warnings") or [])
    )
    result = {
        "discovered_roots": discovered,
        "runtime_path_projection": runtime_scan,
        "session_discovery": session_discovery,
        "session_projections": session_projections,
        "context_link_projection": context_links,
        "truth_asset_memory_followup_projection": tamf,
        "risk_signals": risk_signals,
        "generated_at": _now(),
        "warnings": warnings,
    }
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _role_from_artifact(artifact_type: str) -> str:
    return {
        "session_manifest": "session_manifest",
        "dossier": "project_context",
        "brief_report": "project_context",
        "council_log": "council_transcript",
        "evidence_ledger": "evidence",
        "final_report": "final_decision",
        "issue_card": "followup_action",
        "signoff": "final_decision",
        "followup": "followup_action",
        "verdict": "final_decision",
    }.get(artifact_type, "unknown")


def _root_kind(path: Path) -> str:
    text = str(path).lower().replace("\\", "/")
    if text.endswith(".json"):
        return "report_sample"
    if "backend/src/rtcm" in text:
        return "source_root"
    if ".deerflow/rtcm" in text or str(USER_RTCM_ROOT).lower().replace("\\", "/") in text:
        return "runtime_root"
    return "project_rtcm_root"


def _infer_session_root(path: Path) -> Path:
    parts = list(path.parts)
    lowered = [p.lower() for p in parts]
    if "project_dossier" in lowered:
        return Path(*parts[: lowered.index("project_dossier")])
    if "runtime" in lowered:
        return Path(*parts[: lowered.index("runtime")])
    if "sessions" in lowered:
        idx = lowered.index("sessions")
        if idx + 1 < len(parts):
            return Path(*parts[: idx + 2])
    if "examples" in lowered:
        idx = lowered.index("examples")
        if idx + 1 < len(parts):
            return Path(*parts[: idx + 2])
    return path.parent


def _session_descriptor(root_path: str, files: List[Path]) -> Dict[str, Any]:
    texts = [str(path).lower().replace("\\", "/") for path in files]
    return {
        "rtcm_session_id": _session_id_from_root(Path(root_path)),
        "session_root": root_path,
        "detected_files": [str(path) for path in files],
        "has_manifest": any("manifest" in text or "session.json" in text for text in texts),
        "has_runtime_state": any("session_state.json" in text for text in texts),
        "has_final_report": any("final_report" in text for text in texts),
        "has_signoff": any("signoff" in text for text in texts),
        "has_followup": any("followup" in text or "issue_card" in text for text in texts),
        "has_evidence_ledger": any("evidence_ledger" in text for text in texts),
        "has_council_log": any("council_log" in text for text in texts),
        "context_links": [],
    }


def _session_id_from_root(root: Path) -> str:
    return root.name or "unknown_session"


def _infer_session_id_from_runtime_path(path: str) -> Optional[str]:
    text_path = Path(path)
    root = _infer_session_root(text_path)
    if root == text_path.parent and "rtcm" not in str(path).lower():
        return None
    return _session_id_from_root(root)


def _infer_status_from_files(projections: List[Dict[str, Any]]) -> str:
    if any(p.get("artifact_type") == "signoff" for p in projections):
        return "signed_off"
    if any(p.get("is_runtime_state") for p in projections):
        return "active"
    return "unknown"


def _refs_by_role(projections: List[Dict[str, Any]], roles: set[str]) -> List[str]:
    return [p["runtime_ref_id"] for p in projections if p.get("runtime_role") in roles]


def _refs_by_surface(projections: List[Dict[str, Any]], surfaces: set[str]) -> List[str]:
    return [p["runtime_ref_id"] for p in projections if p.get("surface_type") in surfaces]


def _refs_by_artifact(projections: List[Dict[str, Any]], artifact_types: set[str]) -> List[str]:
    return [p["runtime_ref_id"] for p in projections if p.get("artifact_type") in artifact_types]


def _context_link(
    session_id: Optional[str],
    link_type: str,
    context_id: Optional[str] = None,
    request_id: Optional[str] = None,
    gateway_thread_id: Optional[str] = None,
    mode_session_id: Optional[str] = None,
    mode_invocation_id: Optional[str] = None,
) -> Dict[str, Any]:
    return asdict(
        RTCMContextLinkProjection(
            link_projection_id=f"rtcmlink_{uuid4().hex}",
            rtcm_session_id=session_id,
            context_id=context_id,
            request_id=request_id,
            gateway_thread_id=gateway_thread_id,
            mode_session_id=mode_session_id,
            mode_invocation_id=mode_invocation_id,
            source_path=None,
            link_type=link_type,
            confidence=0.85,
            warnings=[],
            observed_at=_now(),
        )
    )


def _empty_scan(root: str, warnings: List[str]) -> Dict[str, Any]:
    return {
        "root": root,
        "scanned_count": 0,
        "classified_count": 0,
        "by_surface_type": {},
        "by_runtime_role": {},
        "unknown_count": 0,
        "session_count": 0,
        "truth_candidate_count": 0,
        "asset_candidate_count": 0,
        "memory_candidate_count": 0,
        "followup_candidate_count": 0,
        "warnings": warnings,
        "records": [],
    }


def _add_risk(records: List[Dict[str, Any]], types: List[str], risk_type: str, record: Dict[str, Any]) -> None:
    types.append(risk_type)
    records.append(
        {
            "risk_type": risk_type,
            "source_path": record.get("source_path") or record.get("session_root"),
            "surface_type": record.get("surface_type"),
            "runtime_role": record.get("runtime_role"),
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
