"""Read-only Prompt Governance projection surface.

This module scans prompt-related paths and projects source, replacement risk,
and A7 prompt asset candidate diagnostics. It never modifies prompt files,
enables GEPA/DSPy optimization, or writes prompt runtime state.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.prompt.prompt_governance_contract import (
    assess_prompt_replacement_risk,
    classify_prompt_source,
    project_prompt_asset_candidate,
    scan_prompt_sources,
)


DEFAULT_ROOT = Path(r"E:\OpenClaw-Base\deerflow")
DEFAULT_SAMPLE_PATH = DEFAULT_ROOT / "migration_reports" / "foundation_audit" / "R241-6B_PROMPT_PROJECTION_RUNTIME_SAMPLE.json"
MAX_FILES_LIMIT = 2000
EXCLUDED_DIRS = {"node_modules", ".git", "__pycache__", "dist", "build", ".venv"}
PROMPT_PATH_KEYWORDS = {
    "prompt",
    "prompts",
    "soul.md",
    "memory.md",
    "agents.md",
    "dspy",
    "gepa",
    "signature",
    "fewshot",
    "skill.md",
    "agent",
    "rtcm",
    "mode",
    "orchestration",
    "system",
    "instruction",
}


def discover_prompt_runtime_paths(root: Optional[str] = None) -> Dict[str, Any]:
    """Discover prompt-related paths without reading prompt bodies."""
    base = Path(root) if root else DEFAULT_ROOT
    discovered: List[Dict[str, Any]] = []
    missing_expected: List[str] = []
    warnings: List[str] = []
    if not base.exists():
        return {
            "root": str(base),
            "discovered_paths": [],
            "missing_expected_paths": [str(base)],
            "warnings": ["root_missing"],
        }

    expected = [
        base / "SOUL.md",
        base / "MEMORY.md",
        base / "AGENTS.md",
        base / "backend" / "app" / "prompt",
        base / "backend" / "packages" / "harness" / "deerflow" / "agents",
        base / "migration_reports" / "foundation_audit" / "R241-6A_PROMPT_GOVERNANCE_SAMPLE.json",
    ]
    for path in expected:
        if path.exists():
            discovered.append(_path_entry(path, "expected_path"))
        else:
            missing_expected.append(str(path))

    search_roots = [
        base / "backend" / "src",
        base / "backend" / "app",
        base / "backend" / "packages" / "harness" / "deerflow",
        base / "openclaw_project",
        base / "skills",
        base / "docs",
    ]
    seen = {entry["path"] for entry in discovered}
    for search_root in search_roots:
        if not search_root.exists():
            continue
        for path in search_root.rglob("*"):
            if any(part in EXCLUDED_DIRS for part in path.parts):
                continue
            text = str(path).lower()
            if not any(keyword in text for keyword in PROMPT_PATH_KEYWORDS):
                continue
            if str(path) in seen:
                continue
            seen.add(str(path))
            discovered.append(_path_entry(path, "keyword_path"))

    if not discovered:
        warnings.append("no_prompt_paths_discovered")
    return {
        "root": str(base),
        "discovered_paths": discovered,
        "missing_expected_paths": missing_expected,
        "warnings": warnings,
    }


def load_prompt_source_snapshot(path: str) -> Dict[str, Any]:
    """Read lightweight metadata for a single prompt source."""
    source = Path(path)
    warnings: List[str] = []
    if not source.exists():
        return {
            "exists": False,
            "source_path": str(source),
            "size_bytes": 0,
            "extension": source.suffix,
            "sha256": None,
            "classified_source": None,
            "warnings": ["source_missing"],
        }
    if not source.is_file():
        return {
            "exists": True,
            "source_path": str(source),
            "size_bytes": 0,
            "extension": source.suffix,
            "sha256": None,
            "classified_source": classify_prompt_source(str(source)),
            "warnings": ["source_not_file"],
        }

    try:
        size = source.stat().st_size
        preview = _preview_first_line(source)
        return {
            "exists": True,
            "source_path": str(source),
            "size_bytes": size,
            "extension": source.suffix,
            "sha256": _sha256_file(source),
            "first_line_preview": preview,
            "classified_source": classify_prompt_source(str(source)),
            "warnings": warnings,
        }
    except Exception as exc:
        return {
            "exists": True,
            "source_path": str(source),
            "size_bytes": 0,
            "extension": source.suffix,
            "sha256": None,
            "classified_source": classify_prompt_source(str(source)),
            "warnings": [f"snapshot_error:{type(exc).__name__}"],
        }


def project_prompt_sources(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    """Project real prompt sources without prompt bodies."""
    max_files = max(0, min(int(max_files), MAX_FILES_LIMIT))
    scan = scan_prompt_sources(root, max_files=max_files)
    records = [_compact_record(record) for record in scan.get("records", [])]
    warnings = list(scan.get("warnings") or [])
    return {
        "root": scan.get("root"),
        "scanned_count": scan.get("scanned_count", 0),
        "classified_count": len(records),
        "by_layer": scan.get("by_layer", {}),
        "by_source_type": scan.get("by_source_type", {}),
        "by_risk_level": scan.get("by_risk_level", {}),
        "critical_sources_count": sum(1 for record in records if record.get("risk") == "critical"),
        "optimization_candidates_count": sum(1 for record in records if record.get("optimization_status") in {"candidate", "experimental"}),
        "asset_candidate_count": sum(1 for record in records if record.get("asset_candidate_eligible")),
        "rollback_missing_count": sum(
            1
            for record in records
            if record.get("risk") in {"high", "critical"} and not record.get("rollback_available")
        ),
        "records": records,
        "warnings": warnings,
    }


def project_prompt_replacement_risks(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    risks = [assess_prompt_replacement_risk(_to_prompt_record(record)) for record in records or []]
    warnings: List[str] = []
    for risk in risks:
        warnings.extend(risk.get("warnings") or [])
    return {
        "total": len(risks),
        "by_risk_level": dict(Counter(risk.get("risk_level", "unknown") for risk in risks)),
        "critical_replacement_count": sum(1 for risk in risks if risk.get("risk_level") == "critical"),
        "high_replacement_count": sum(1 for risk in risks if risk.get("risk_level") == "high"),
        "rollback_required_count": sum(1 for risk in risks if risk.get("requires_rollback")),
        "backup_required_count": sum(1 for risk in risks if risk.get("requires_backup")),
        "test_required_count": sum(1 for risk in risks if risk.get("requires_test")),
        "user_confirmation_required_count": sum(1 for risk in risks if risk.get("requires_user_confirmation")),
        "governance_review_required_count": sum(1 for risk in risks if risk.get("requires_governance_review")),
        "risks": risks,
        "warnings": _dedupe(warnings),
    }


def project_prompt_asset_candidates(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    candidates: List[Dict[str, Any]] = []
    protected: List[Dict[str, Any]] = []
    warnings: List[str] = []
    for record in records or []:
        prompt_record = _to_prompt_record(record)
        projection = project_prompt_asset_candidate(prompt_record)
        entry = {
            "path": record.get("path") or prompt_record.get("source_path"),
            "source_type": prompt_record.get("source_type"),
            "layer": prompt_record.get("priority_layer"),
            **projection,
        }
        warnings.extend(projection.get("warnings") or [])
        if projection.get("asset_candidate_eligible"):
            candidates.append(entry)
        elif projection.get("asset_category") in {"protected_identity_source", "protected_hard_constraint_source"}:
            protected.append(entry)

    return {
        "candidate_count": len(candidates),
        "by_source_type": dict(Counter(candidate.get("source_type", "unknown") for candidate in candidates)),
        "by_layer": dict(Counter(candidate.get("layer", "unknown") for candidate in candidates)),
        "candidates": candidates,
        "protected_sources": protected,
        "warnings": _dedupe(warnings),
    }


def detect_prompt_governance_risks(projection: Dict[str, Any]) -> Dict[str, Any]:
    source_projection = projection.get("source_projection", projection)
    records = source_projection.get("records", [])
    replacement = projection.get("replacement_risks") or project_prompt_replacement_risks(records)
    asset_candidates = projection.get("asset_candidates") or project_prompt_asset_candidates(records)
    risk_records: List[Dict[str, Any]] = []
    risk_types: List[str] = []

    for record in records:
        source_type = record.get("source_type")
        layer = record.get("layer")
        risk = record.get("risk")
        if risk == "critical" and not record.get("rollback_available"):
            _add_risk(risk_records, risk_types, "critical_prompt_without_rollback", record)
        if source_type == "soul":
            _add_risk(risk_records, risk_types, "soul_replacement_requires_user_confirmation", record)
        if layer == "P1_hard_constraints" and not record.get("rollback_available"):
            _add_risk(risk_records, risk_types, "p1_prompt_without_backup", record)
        if source_type in {"dspy_candidate", "gepa_candidate"}:
            _add_risk(risk_records, risk_types, "generated_prompt_candidate_without_test", record)
            _add_risk(risk_records, risk_types, "dspy_gepa_direct_replace_forbidden", record)
        if source_type == "unknown":
            _add_risk(risk_records, risk_types, "unknown_prompt_source", record)
        if layer == "unknown":
            _add_risk(risk_records, risk_types, "unknown_prompt_layer", record)
        if layer == "P5_runtime_context":
            _add_risk(risk_records, risk_types, "runtime_context_prompt_leakage_review_required", record)
        if risk in {"high", "critical"} and not record.get("rollback_available"):
            _add_risk(risk_records, risk_types, "rollback_missing", record)
            _add_risk(risk_records, risk_types, "backup_missing", record)

    for candidate in asset_candidates.get("candidates", []):
        if not candidate.get("required_evidence"):
            _add_risk(risk_records, risk_types, "prompt_asset_candidate_without_evidence", candidate)

    for risk in replacement.get("risks", []):
        if "same_layer_conflict_requires_review" in risk.get("warnings", []):
            _add_risk(risk_records, risk_types, "same_layer_conflict_requires_review", risk)

    return {
        "risk_count": len(risk_records),
        "risk_by_type": dict(Counter(risk_types)),
        "risk_records": risk_records,
        "warnings": _dedupe(list(source_projection.get("warnings") or [])),
    }


def aggregate_prompt_projection(root: Optional[str] = None, max_files: int = 500) -> Dict[str, Any]:
    discovered = discover_prompt_runtime_paths(root)
    source_projection = project_prompt_sources(root, max_files=max_files)
    replacement = project_prompt_replacement_risks(source_projection.get("records", []))
    asset_candidates = project_prompt_asset_candidates(source_projection.get("records", []))
    risk_signals = detect_prompt_governance_risks(
        {
            "source_projection": source_projection,
            "replacement_risks": replacement,
            "asset_candidates": asset_candidates,
        }
    )
    warnings = _dedupe(
        list(discovered.get("warnings") or [])
        + list(source_projection.get("warnings") or [])
        + list(replacement.get("warnings") or [])
        + list(asset_candidates.get("warnings") or [])
        + list(risk_signals.get("warnings") or [])
    )
    return {
        "discovered_paths": discovered,
        "source_projection": source_projection,
        "replacement_risks": replacement,
        "asset_candidates": asset_candidates,
        "risk_signals": risk_signals,
        "summary": {
            "discovered_count": len(discovered.get("discovered_paths", [])),
            "classified_count": source_projection.get("classified_count", 0),
            "critical_sources_count": source_projection.get("critical_sources_count", 0),
            "asset_candidate_count": asset_candidates.get("candidate_count", 0),
            "risk_count": risk_signals.get("risk_count", 0),
        },
        "warnings": warnings,
    }


def generate_prompt_projection_report(
    output_path: Optional[str] = None,
    root: Optional[str] = None,
    max_files: int = 500,
) -> Dict[str, Any]:
    aggregate = aggregate_prompt_projection(root, max_files=max_files)
    result = {
        **aggregate,
        "generated_at": _now(),
    }
    path = Path(output_path) if output_path else DEFAULT_SAMPLE_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"output_path": str(path), **result}


def _path_entry(path: Path, reason: str) -> Dict[str, Any]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "is_file": path.is_file(),
        "is_dir": path.is_dir(),
        "reason": reason,
        "classification_hint": classify_prompt_source(str(path)).get("source_type"),
    }


def _compact_record(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "path": record.get("source_path"),
        "hash": record.get("source_hash"),
        "source_type": record.get("source_type"),
        "layer": record.get("priority_layer"),
        "risk": record.get("risk_level"),
        "optimization_status": record.get("optimization_status"),
        "asset_candidate_eligible": bool(record.get("asset_candidate_eligible")),
        "rollback_available": bool(record.get("rollback_available")),
        "warnings": list(record.get("warnings") or []),
    }


def _to_prompt_record(record: Dict[str, Any]) -> Dict[str, Any]:
    if "priority_layer" in record:
        return record
    return {
        "prompt_source_id": record.get("prompt_source_id") or record.get("path") or "unknown",
        "source_path": record.get("path"),
        "source_type": record.get("source_type", "unknown"),
        "priority_layer": record.get("layer", "unknown"),
        "risk_level": record.get("risk", "unknown"),
        "optimization_status": record.get("optimization_status", "unknown"),
        "asset_candidate_eligible": record.get("asset_candidate_eligible", False),
        "rollback_available": record.get("rollback_available", False),
        "warnings": list(record.get("warnings") or []),
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _preview_first_line(path: Path) -> str:
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        first_line = handle.readline().strip()
    if len(first_line) <= 120:
        return first_line
    return first_line[:117] + "..."


def _add_risk(records: List[Dict[str, Any]], types: List[str], risk_type: str, record: Dict[str, Any]) -> None:
    types.append(risk_type)
    records.append(
        {
            "risk_type": risk_type,
            "path": record.get("path") or record.get("source_path"),
            "source_type": record.get("source_type"),
            "layer": record.get("layer") or record.get("priority_layer"),
            "risk": record.get("risk") or record.get("risk_level"),
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
