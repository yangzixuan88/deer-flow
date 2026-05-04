"""Read-only asset projection surface.

This module projects existing asset-related runtime artifacts into
AssetLifecycleRecord diagnostics without modifying registries, binding reports,
DPBS state, or governance history.
"""

from __future__ import annotations

import copy
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.app.asset.asset_lifecycle_contract import (
    detect_asset_lifecycle_risks,
    project_asset_candidate,
)


DEFAULT_ROOT = Path(r"E:\OpenClaw-Base\deerflow")
DEFAULT_REPORT_PATH = (
    DEFAULT_ROOT
    / "migration_reports"
    / "foundation_audit"
    / "R241-3B_ASSET_PROJECTION_RUNTIME_SAMPLE.json"
)
DEFAULT_MEMORY_ASSET_SAMPLE = (
    DEFAULT_ROOT
    / "migration_reports"
    / "foundation_audit"
    / "R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json"
)


def discover_asset_runtime_paths(root: Optional[str] = None) -> Dict[str, Any]:
    """Discover known asset-related runtime paths without mutating them."""
    base = Path(root) if root else DEFAULT_ROOT
    expected = [
        base / ".deerflow" / "operation_assets" / "asset_registry.json",
        base / "assets" / "asset-index.json",
        base / ".deerflow" / "operation_assets" / "latest_binding_report.json",
        base / "backend" / "app" / "m11" / "governance_state.json",
        base / "migration_reports" / "foundation_audit" / "R241-3A_ASSET_LIFECYCLE_RUNTIME_SAMPLE.json",
    ]
    discovered_paths: List[str] = []
    missing_paths: List[str] = []
    warnings: List[str] = []

    for path in expected:
        if path.exists():
            discovered_paths.append(str(path))
        else:
            missing_paths.append(str(path))
            warnings.append(f"path_missing:{path}")

    for directory in (base / ".deerflow" / "operation_assets", base / "migration_reports"):
        if not directory.exists():
            continue
        for pattern in ("binding_report*.json", "*binding_report*.json"):
            for path in list(directory.rglob(pattern))[:20]:
                if str(path) not in discovered_paths:
                    discovered_paths.append(str(path))

    return {
        "root": str(base),
        "discovered_paths": discovered_paths,
        "missing_paths": missing_paths,
        "warnings": _dedupe(warnings),
    }


def load_asset_registry_snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """Load asset registry records read-only."""
    target = Path(path) if path else DEFAULT_ROOT / ".deerflow" / "operation_assets" / "asset_registry.json"
    if not target.exists() and path is None:
        for candidate in discover_asset_runtime_paths()["discovered_paths"]:
            p = Path(candidate)
            if p.name in {"asset_registry.json", "asset-index.json"}:
                target = p
                break

    result = {
        "source_path": str(target),
        "exists": target.exists(),
        "asset_count": 0,
        "registry_format": "missing",
        "sample_keys": [],
        "records": [],
        "warnings": [],
    }
    if not target.exists():
        result["warnings"].append(f"registry_missing:{target}")
        return result

    data, warning = _read_json_readonly(target)
    if warning:
        result["warnings"].append(warning)
        return result

    records, registry_format = _records_from_registry(data)
    result["registry_format"] = registry_format
    result["records"] = records
    result["asset_count"] = len(records)
    result["sample_keys"] = sorted(records[0].keys())[:20] if records else []
    if not records:
        result["warnings"].append("registry_empty")
    return result


def load_binding_report_snapshot(path: Optional[str] = None) -> Dict[str, Any]:
    """Load latest binding report or binding_report*.json read-only."""
    target = Path(path) if path else _default_binding_report_path()
    result = {
        "exists": target.exists() if target else False,
        "report_count": 0,
        "record_count": 0,
        "source_path": str(target) if target else None,
        "records": [],
        "warnings": [],
    }
    if not target or not target.exists():
        result["warnings"].append("binding_report_missing")
        return result

    data, warning = _read_json_readonly(target)
    if warning:
        result["warnings"].append(warning)
        return result

    records = _records_from_binding(data)
    result["records"] = records
    result["record_count"] = len(records)
    result["report_count"] = 1 if records or data is not None else 0
    return result


def project_registry_assets(limit: int = 200) -> Dict[str, Any]:
    """Project asset registry records into AssetLifecycleRecord diagnostics."""
    snapshot = load_asset_registry_snapshot()
    records = copy.deepcopy(snapshot.get("records") or [])[:_clamp_limit(limit)]
    projected = []
    for record in records:
        metadata = {
            "asset_id": record.get("id") or record.get("asset_id"),
            "source_system": "asset_registry",
            "source_path": snapshot.get("source_path"),
        }
        if isinstance(record.get("metadata"), dict):
            meta = record["metadata"]
            if meta.get("success_rate") is not None:
                metadata["success_rate"] = _normalize_score(meta.get("success_rate"))
            if meta.get("use_count") is not None:
                metadata["frequency"] = _normalize_frequency(meta.get("use_count"))
        projected.append(project_asset_candidate(record, metadata))

    return _projection_result("registry", projected, snapshot.get("warnings") or [])


def project_binding_assets(limit: int = 200) -> Dict[str, Any]:
    """Project binding report records into AssetLifecycleRecord diagnostics."""
    snapshot = load_binding_report_snapshot()
    records = copy.deepcopy(snapshot.get("records") or [])[:_clamp_limit(limit)]
    projected = []
    for record in records:
        projected.append(
            project_asset_candidate(
                record,
                {
                    "source_system": "binding_report",
                    "source_path": snapshot.get("source_path"),
                },
            )
        )
    return _projection_result("binding", projected, snapshot.get("warnings") or [])


def project_governance_asset_outcomes(limit: int = 200) -> Dict[str, Any]:
    """Project asset-related governance outcomes read-only."""
    records, warnings = _load_governance_records_readonly()
    selected = [
        record for record in records
        if _is_asset_related_governance_record(record)
    ][-_clamp_limit(limit):]
    projected = []
    for record in selected:
        context = record.get("context") if isinstance(record.get("context"), dict) else {}
        metadata = {
            "source_system": "governance",
            "candidate_id": context.get("candidate_id"),
            "governance_trace_id": record.get("governance_trace_id") or context.get("governance_trace_id"),
            "risk_level": context.get("risk_level"),
            "score": context.get("score") or context.get("quality_score"),
        }
        projected.append(project_asset_candidate(record, metadata))
    result = _projection_result("governance", projected, warnings)
    result["scanned_count"] = len(records)
    result["asset_related_count"] = len(selected)
    return result


def aggregate_asset_projection(limit: int = 200) -> Dict[str, Any]:
    """Aggregate registry, binding, governance, and memory-candidate projections."""
    registry = project_registry_assets(limit)
    binding = project_binding_assets(limit)
    governance = project_governance_asset_outcomes(limit)
    memory = _load_memory_candidate_projection()
    surfaces = {
        "registry": registry.get("projected_assets", []),
        "binding": binding.get("projected_assets", []),
        "governance": governance.get("projected_assets", []),
        "memory_candidates": memory.get("candidates", []),
    }
    all_records = [record for records in surfaces.values() for record in records]
    risk_summary = detect_asset_projection_risks(
        {
            "registry_projection": registry,
            "binding_projection": binding,
            "governance_asset_projection": governance,
            "memory_candidate_projection": memory,
            "all_records": all_records,
        }
    )

    return {
        "total_projected": len(all_records),
        "by_source_surface": {key: len(value) for key, value in surfaces.items()},
        "by_asset_category": dict(Counter(record.get("asset_category", "unknown") for record in all_records)),
        "by_lifecycle_tier": dict(Counter(record.get("lifecycle_tier", "unknown") for record in all_records)),
        "candidate_count": sum(1 for record in all_records if record.get("lifecycle_tier") == "candidate"),
        "formal_asset_count": len(surfaces["registry"]) + len(surfaces["binding"]),
        "risk_summary": risk_summary,
        "warnings": _dedupe(
            list(registry.get("warnings") or [])
            + list(binding.get("warnings") or [])
            + list(governance.get("warnings") or [])
            + list(memory.get("warnings") or [])
        ),
    }


def detect_asset_projection_risks(projection: Dict[str, Any]) -> Dict[str, Any]:
    """Detect projection risks without modifying assets."""
    records = projection.get("all_records") or []
    risks = detect_asset_lifecycle_risks(records)
    risk_counter = Counter(risks.get("risk_by_type") or {})
    risk_records = list(risks.get("risk_records") or [])
    warnings = list(projection.get("warnings") or [])

    registry_projection = projection.get("registry_projection") or {}
    binding_projection = projection.get("binding_projection") or {}
    governance_projection = projection.get("governance_asset_projection") or {}
    memory_projection = projection.get("memory_candidate_projection") or {}

    if any(str(w).startswith("registry_missing") for w in registry_projection.get("warnings", [])):
        risk_counter["registry_missing"] += 1
    if any(str(w).startswith("binding_report_missing") for w in binding_projection.get("warnings", [])):
        risk_counter["binding_report_missing"] += 1
    if registry_projection.get("projected_count") == 0:
        risk_counter["registry_empty"] += 1

    _add_duplicate_candidate_risks(records, risk_counter, risk_records)

    for record in records:
        if _is_formal(record) and not record.get("verification_refs"):
            risk_counter["formal_asset_without_verification_refs"] += 1
        if record.get("lifecycle_tier") == "candidate" and not (record.get("source_path") or record.get("source_record_ref")):
            risk_counter["candidate_without_source"] += 1
        if record.get("core_protected") and "core_requires_user_confirmation" not in record.get("warnings", []):
            risk_counter["core_asset_without_user_confirmation"] += 1

    if memory_projection.get("candidate_count", 0):
        risk_counter["memory_candidate_not_registered"] += memory_projection.get("candidate_count", 0)
    if governance_projection.get("asset_related_count", 0) and governance_projection.get("projected_count", 0) == 0:
        risk_counter["governance_asset_outcome_without_asset_record"] += governance_projection.get("asset_related_count", 0)

    return {
        "risk_count": sum(risk_counter.values()),
        "risk_by_type": dict(risk_counter),
        "risk_records": risk_records[:50],
        "warnings": _dedupe(warnings),
    }


def generate_asset_projection_report(output_path: Optional[str] = None, limit: int = 200) -> Dict[str, Any]:
    """Generate an audit-only asset projection report."""
    target = Path(output_path) if output_path else DEFAULT_REPORT_PATH
    discovered = discover_asset_runtime_paths()
    registry_snapshot = load_asset_registry_snapshot()
    binding_snapshot = load_binding_report_snapshot()
    registry_projection = project_registry_assets(limit)
    binding_projection = project_binding_assets(limit)
    governance_projection = project_governance_asset_outcomes(limit)
    aggregate = aggregate_asset_projection(limit)
    risk_signals = aggregate["risk_summary"]
    warnings = _dedupe(
        list(discovered.get("warnings") or [])
        + list(registry_snapshot.get("warnings") or [])
        + list(binding_snapshot.get("warnings") or [])
        + list(registry_projection.get("warnings") or [])
        + list(binding_projection.get("warnings") or [])
        + list(governance_projection.get("warnings") or [])
        + list(aggregate.get("warnings") or [])
        + list(risk_signals.get("warnings") or [])
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "content_policy": "read-only asset projection; no registry, binding, DPBS, or governance writes",
        "discovered_paths": discovered,
        "registry_snapshot_summary": _snapshot_summary(registry_snapshot),
        "binding_snapshot_summary": _snapshot_summary(binding_snapshot),
        "registry_projection": _compact_projection(registry_projection),
        "binding_projection": _compact_projection(binding_projection),
        "governance_asset_projection": _compact_projection(governance_projection),
        "aggregate_projection": aggregate,
        "risk_signals": risk_signals,
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


def _read_json_readonly(path: Path) -> Tuple[Any, Optional[str]]:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig")), None
    except Exception as exc:
        return None, f"json_read_failed:{path}:{type(exc).__name__}:{exc}"


def _records_from_registry(data: Any) -> Tuple[List[Dict[str, Any]], str]:
    if isinstance(data, dict):
        if isinstance(data.get("assets"), list):
            return [r for r in data["assets"] if isinstance(r, dict)], "dict.assets"
        if isinstance(data.get("records"), list):
            return [r for r in data["records"] if isinstance(r, dict)], "dict.records"
        if all(isinstance(v, dict) for v in data.values()):
            return [dict(v, id=k) for k, v in data.items()], "dict.asset_map"
        return [], "dict.unknown"
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)], "list"
    return [], "unknown"


def _records_from_binding(data: Any) -> List[Dict[str, Any]]:
    if isinstance(data, list):
        return [r for r in data if isinstance(r, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("bindings", "records", "items", "platform_bindings", "results"):
        value = data.get(key)
        if isinstance(value, list):
            return [r for r in value if isinstance(r, dict)]
    return [data] if data else []


def _default_binding_report_path() -> Optional[Path]:
    direct = DEFAULT_ROOT / ".deerflow" / "operation_assets" / "latest_binding_report.json"
    if direct.exists():
        return direct
    operation_assets = DEFAULT_ROOT / ".deerflow" / "operation_assets"
    if operation_assets.exists():
        matches = list(operation_assets.glob("*binding_report*.json"))
        if matches:
            return matches[0]
    return direct


def _projection_result(surface: str, projected: List[Dict[str, Any]], warnings: List[str]) -> Dict[str, Any]:
    return {
        "source_surface": surface,
        "projected_count": len(projected),
        "by_asset_category": dict(Counter(record.get("asset_category", "unknown") for record in projected)),
        "by_lifecycle_tier": dict(Counter(record.get("lifecycle_tier", "unknown") for record in projected)),
        "projected_assets": projected,
        "warnings": _dedupe(warnings + [w for record in projected for w in record.get("warnings", [])]),
    }


def _load_governance_records_readonly() -> Tuple[List[Dict[str, Any]], List[str]]:
    try:
        from backend.app.m11 import governance_bridge

        return governance_bridge._read_outcome_records_readonly()
    except Exception as exc:
        return [], [f"governance_read_failed:{type(exc).__name__}:{exc}"]


def _is_asset_related_governance_record(record: Dict[str, Any]) -> bool:
    text = json.dumps(record, ensure_ascii=False).lower()
    return any(token in text for token in ("asset", "promotion", "binding", "dpbs", "registry"))


def _load_memory_candidate_projection() -> Dict[str, Any]:
    if not DEFAULT_MEMORY_ASSET_SAMPLE.exists():
        return {"candidate_count": 0, "candidates": [], "warnings": [f"memory_asset_sample_missing:{DEFAULT_MEMORY_ASSET_SAMPLE}"]}
    data, warning = _read_json_readonly(DEFAULT_MEMORY_ASSET_SAMPLE)
    if warning:
        return {"candidate_count": 0, "candidates": [], "warnings": [warning]}
    projection = data.get("memory_asset_candidates_projection") if isinstance(data, dict) else None
    if not isinstance(projection, dict):
        return {"candidate_count": 0, "candidates": [], "warnings": ["memory_asset_projection_missing"]}
    return projection


def _add_duplicate_candidate_risks(records: List[Dict[str, Any]], counter: Counter, risk_records: List[Dict[str, Any]]) -> None:
    keys = Counter(
        record.get("asset_id")
        or record.get("candidate_id")
        or record.get("source_path")
        or (record.get("source_record_ref") or {}).get("source_path")
        for record in records
    )
    for key, count in keys.items():
        if key and count > 1:
            counter["duplicate_asset_candidate"] += count
            risk_records.append({"duplicate_key": key, "risk_types": ["duplicate_asset_candidate"], "count": count})


def _is_formal(record: Dict[str, Any]) -> bool:
    source = record.get("source_system")
    return source in {"asset_registry", "binding_report"}


def _normalize_score(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric * 100 if 0 <= numeric <= 1 else numeric


def _normalize_frequency(value: Any) -> Optional[float]:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return min(numeric * 10, 100)


def _snapshot_summary(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    return {k: v for k, v in snapshot.items() if k != "records"}


def _compact_projection(projection: Dict[str, Any]) -> Dict[str, Any]:
    compact = dict(projection)
    if "projected_assets" in compact:
        compact["projected_assets_total_count"] = len(compact["projected_assets"])
        compact["projected_assets"] = compact["projected_assets"][:20]
    return compact


def _clamp_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 200
    return max(0, min(parsed, 200))


def _dedupe(items: List[Any]) -> List[str]:
    return list(dict.fromkeys(str(item) for item in items))
