"""Test Runtime Optimization Plan (R241-15C).

This module is a report-only helper for measuring and planning pytest
runtime improvements after the R241-15B slow-test split.

It does not delete tests, skip safety coverage, call network/webhooks,
write audit JSONL, write runtime state, or execute auto-fix actions.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
DEFAULT_PLAN_PATH = REPORT_DIR / "R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json"
DEFAULT_REPORT_PATH = REPORT_DIR / "R241-15C_TEST_RUNTIME_OPTIMIZATION_REPORT.md"

ORIGINAL_BASELINE_RUNTIME = "6m40s+"
ORIGINAL_BASELINE_SECONDS = 400.0

REQUIRED_MARKERS = [
    "smoke",
    "unit",
    "integration",
    "slow",
    "full",
    "no_network",
    "no_runtime_write",
    "no_secret",
]

SLOW_IN_FAST_PATTERNS = [
    {
        "pattern": re.compile(r"generate_.*sample|sample_generation|write.*sample", re.IGNORECASE),
        "reason": "sample generation",
        "recommended_marker_change": "add @pytest.mark.slow to sample/report artifact generation tests",
    },
    {
        "pattern": re.compile(r"scan_|discover_.*paths|discover_.*surfaces|glob\(|rglob\(", re.IGNORECASE),
        "reason": "filesystem scan",
        "recommended_marker_change": "add @pytest.mark.slow when the test scans real repository trees",
    },
    {
        "pattern": re.compile(r"aggregate_|run_all_diagnostics|foundation_health|all_diagnostics", re.IGNORECASE),
        "reason": "aggregate diagnostic",
        "recommended_marker_change": "add @pytest.mark.slow for multi-domain aggregate diagnostics",
    },
    {
        "pattern": re.compile(r"main\(\[|foundation_diagnose|CLI|cli smoke|subprocess", re.IGNORECASE),
        "reason": "CLI smoke",
        "recommended_marker_change": "add @pytest.mark.integration and @pytest.mark.slow for real CLI smoke paths",
    },
    {
        "pattern": re.compile(
            r"generate_trend_report_artifact_bundle|run_guarded_audit_trend_cli_projection|query_audit_trail",
            re.IGNORECASE,
        ),
        "reason": "slow helper in fast path",
        "recommended_marker_change": "mark tests that call full projection/query helpers as slow",
    },
]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _to_seconds(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    mm_ss = re.match(r"^(?:(\d+)m)?\s*(?:(\d+(?:\.\d+)?)s)?\+?$", text)
    if mm_ss and (mm_ss.group(1) or mm_ss.group(2)):
        minutes = float(mm_ss.group(1) or 0)
        seconds = float(mm_ss.group(2) or 0)
        return minutes * 60 + seconds
    try:
        return float(text)
    except ValueError:
        return None


def _format_seconds(seconds: Optional[float]) -> Optional[str]:
    if seconds is None:
        return None
    minutes = int(seconds // 60)
    remain = seconds - minutes * 60
    if minutes:
        return f"{minutes}m{remain:.2f}s"
    return f"{remain:.2f}s"


def _measurement_summary(measurements: Dict[str, Any], key: str) -> Dict[str, Any]:
    raw = measurements.get(key, {}) if measurements else {}
    if isinstance(raw, (str, int, float)):
        raw = {"runtime": raw}
    runtime = raw.get("runtime", raw.get("duration", raw.get("seconds")))
    seconds = _to_seconds(runtime)
    return {
        "runtime": runtime if runtime is not None else None,
        "runtime_seconds": seconds,
        "passed": raw.get("passed"),
        "failed": raw.get("failed"),
        "skipped": raw.get("skipped"),
        "status": raw.get("status", "measured" if runtime is not None else "not_measured"),
    }


def build_runtime_baseline_summary(measurements: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Aggregate measured runtimes into a baseline summary."""
    measurements = measurements or {}
    keys = [
        "foundation_fast_runtime",
        "audit_fast_runtime",
        "slow_suite_runtime",
        "safety_suite_runtime",
        "collect_only_runtime",
        "stabilization_tests_runtime",
    ]
    summary = {
        "generated_at": _utc_now(),
        "original_baseline_runtime": ORIGINAL_BASELINE_RUNTIME,
        "original_baseline_seconds": ORIGINAL_BASELINE_SECONDS,
    }
    for key in keys:
        summary[key] = _measurement_summary(measurements, key)

    foundation_seconds = summary["foundation_fast_runtime"]["runtime_seconds"] or 0
    audit_seconds = summary["audit_fast_runtime"]["runtime_seconds"] or 0
    fast_seconds = foundation_seconds + audit_seconds
    improvement_seconds = max(0.0, ORIGINAL_BASELINE_SECONDS - fast_seconds) if fast_seconds else None
    improvement_percent = (
        round((improvement_seconds / ORIGINAL_BASELINE_SECONDS) * 100, 2)
        if improvement_seconds is not None
        else None
    )
    summary["fast_combined_runtime_seconds"] = fast_seconds or None
    summary["fast_combined_runtime"] = _format_seconds(fast_seconds) if fast_seconds else None
    summary["improvement_estimate"] = {
        "baseline": ORIGINAL_BASELINE_RUNTIME,
        "fast_combined_runtime": summary["fast_combined_runtime"],
        "seconds_saved_estimate": improvement_seconds,
        "percent_saved_estimate": improvement_percent,
        "notes": "Estimate compares foundation_fast + audit_fast against the pre-split 6m40s+ baseline.",
    }
    return summary


def _iter_test_files(root_path: Path) -> Iterable[Path]:
    search_roots = [root_path / "backend" / "app" / "foundation", root_path / "backend" / "app" / "audit"]
    if (root_path / "app").exists():
        search_roots.append(root_path / "app")
    if root_path.name in {"foundation", "audit"}:
        search_roots.append(root_path)
    for search_root in search_roots:
        if search_root.exists():
            yield from search_root.rglob("test_*.py")


def _has_nearby_slow_marker(lines: List[str], index: int) -> bool:
    start = max(0, index - 4)
    nearby = "\n".join(lines[start : index + 1])
    return "pytest.mark.slow" in nearby or "pytestmark = pytest.mark.slow" in "\n".join(lines[:20])


def _sanitize_test_hint(text: str) -> str:
    sanitized = re.sub(r"https?://\S+", "[redacted-url]", text)
    sanitized = re.sub(r"open\.feishu[\w.\-/]*", "[redacted-feishu-host]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"webhook[\w.\-/]*", "[redacted-webhook]", sanitized, flags=re.IGNORECASE)
    sanitized = re.sub(r"(token|secret|api_key)\s*=\s*['\"][^'\"]+['\"]", r"\1=[redacted]", sanitized, flags=re.IGNORECASE)
    return sanitized[:160]


def detect_remaining_slow_in_fast(root: Optional[str] = None) -> Dict[str, Any]:
    """Heuristically identify tests likely to stay slow in `-m 'not slow'`."""
    root_path = Path(root) if root else ROOT
    candidates: List[Dict[str, Any]] = []
    warnings: List[str] = []
    seen = set()

    for test_file in _iter_test_files(root_path):
        try:
            lines = test_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            warnings.append(f"failed_to_read:{test_file}:{exc}")
            continue
        function_starts = [idx for idx, line in enumerate(lines) if re.match(r"\s*def test_", line)]
        for position, idx in enumerate(function_starts):
            line = lines[idx]
            end = function_starts[position + 1] if position + 1 < len(function_starts) else len(lines)
            block = "\n".join(lines[idx:end])
            if _has_nearby_slow_marker(lines, idx):
                continue
            for slow_pattern in SLOW_IN_FAST_PATTERNS:
                if slow_pattern["pattern"].search(block):
                    rel = str(test_file.relative_to(root_path)) if test_file.is_relative_to(root_path) else str(test_file)
                    key = (rel, idx + 1, slow_pattern["reason"])
                    if key in seen:
                        continue
                    seen.add(key)
                    candidates.append(
                        {
                            "file": rel,
                            "line": idx + 1,
                            "test_hint": _sanitize_test_hint(line.strip()),
                            "reason": slow_pattern["reason"],
                            "recommended_marker_change": slow_pattern["recommended_marker_change"],
                            "safe_to_mark_slow": True,
                        }
                    )
                    break

    return {
        "detected_at": _utc_now(),
        "remaining_slow_in_fast_count": len(candidates),
        "remaining_slow_in_fast": candidates,
        "warnings": warnings,
    }


def _configured_markers(root_path: Path) -> List[str]:
    pyproject_candidates = [root_path / "backend" / "pyproject.toml", root_path / "pyproject.toml"]
    marker_names: List[str] = []
    for pyproject in pyproject_candidates:
        if not pyproject.exists():
            continue
        content = pyproject.read_text(encoding="utf-8", errors="ignore")
        in_markers = False
        for raw_line in content.splitlines():
            line = raw_line.strip()
            if line.startswith("markers"):
                in_markers = True
                continue
            if in_markers and line.startswith("]"):
                break
            if in_markers:
                match = re.search(r'"([a-zA-Z_][a-zA-Z0-9_]*)\s*:', line)
                if match:
                    marker_names.append(match.group(1))
        if marker_names:
            break
    return sorted(set(marker_names))


def audit_marker_quality(root: Optional[str] = None) -> Dict[str, Any]:
    """Audit marker quality without changing marker definitions."""
    root_path = Path(root) if root else ROOT
    configured = _configured_markers(root_path)
    missing_required = [marker for marker in REQUIRED_MARKERS if marker not in configured]
    slow_marker_lines: List[Dict[str, Any]] = []
    safety_marker_lines: List[Dict[str, Any]] = []
    file_level_slow: List[str] = []
    warnings: List[str] = []

    for test_file in _iter_test_files(root_path):
        try:
            lines = test_file.read_text(encoding="utf-8", errors="ignore").splitlines()
        except OSError as exc:
            warnings.append(f"failed_to_read:{test_file}:{exc}")
            continue
        rel = str(test_file.relative_to(root_path)) if test_file.is_relative_to(root_path) else str(test_file)
        for idx, line in enumerate(lines):
            stripped = line.strip()
            if "pytestmark" in stripped and "slow" in stripped:
                file_level_slow.append(rel)
            if "pytest.mark.slow" in stripped:
                slow_marker_lines.append({"file": rel, "line": idx + 1})
            if any(f"pytest.mark.{marker}" in stripped for marker in ("no_network", "no_runtime_write", "no_secret")):
                safety_marker_lines.append({"file": rel, "line": idx + 1, "marker_line": stripped})

    slow_marker_too_broad = len(file_level_slow) > 0
    safety_markers_runnable = all(marker in configured for marker in ("no_network", "no_runtime_write", "no_secret"))
    safety_all_slow = bool(safety_marker_lines) and all(
        any(s["file"] == slow["file"] and abs(s["line"] - slow["line"]) <= 3 for slow in slow_marker_lines)
        for s in safety_marker_lines
    )

    if missing_required:
        warnings.append("missing_required_markers")
    if slow_marker_too_broad:
        warnings.append("file_level_slow_marker_detected")
    if safety_all_slow:
        warnings.append("all_detected_safety_markers_are_near_slow_marker")

    return {
        "audited_at": _utc_now(),
        "required_markers": REQUIRED_MARKERS,
        "configured_markers": configured,
        "marker_count": len(configured),
        "missing_required_markers": missing_required,
        "pytest_markers_contains_8_required": len(missing_required) == 0,
        "slow_marker_count": len(slow_marker_lines),
        "safety_marker_count": len(safety_marker_lines),
        "slow_marker_too_broad": slow_marker_too_broad,
        "pure_unit_likely_mis_marked_slow": [],
        "safety_tests_all_marked_slow": safety_all_slow,
        "safety_markers_runnable": safety_markers_runnable,
        "no_network_runnable": "no_network" in configured,
        "no_runtime_write_runnable": "no_runtime_write" in configured,
        "no_secret_runnable": "no_secret" in configured,
        "warnings": warnings,
    }


def build_runtime_optimization_options() -> Dict[str, Any]:
    """Return the runtime optimization options A-E."""
    options = [
        {
            "option_id": "Option A",
            "name": "Marker Refinement",
            "description": "Correct missed/over-broad markers without deleting tests or safety assertions.",
            "allowed_changes": ["add slow marker", "add integration marker", "add safety marker"],
            "forbidden_changes": ["test removal", "safety-test bypass", "safety-test xfail"],
            "recommended": True,
        },
        {
            "option_id": "Option B",
            "name": "Fixture Caching",
            "description": "Cache read-only synthetic projection inputs in pytest fixtures.",
            "allowed_changes": ["session scoped synthetic fixtures", "tmp_path cached sample inputs"],
            "forbidden_changes": ["runtime-state caching", "secret caching", "audit-trail mutation"],
            "recommended": True,
        },
        {
            "option_id": "Option C",
            "name": "Synthetic Fixture Replacement",
            "description": "Replace real repository scans with tmp_path synthetic fixtures when the test only validates classification logic.",
            "allowed_changes": ["tmp_path synthetic trees", "small JSON fixtures"],
            "forbidden_changes": ["remove real scan coverage from slow suite"],
            "recommended": True,
        },
        {
            "option_id": "Option D",
            "name": "Split CLI Smoke from Unit Tests",
            "description": "Keep CLI smoke under integration/slow marker and keep pure helper tests in fast path.",
            "allowed_changes": ["integration marker for CLI smoke", "slow marker for full CLI aggregation"],
            "forbidden_changes": ["change CLI behavior", "skip CLI smoke"],
            "recommended": True,
        },
        {
            "option_id": "Option E",
            "name": "CI Stage Matrix",
            "description": "Run fast, slow, safety, and full stages separately.",
            "allowed_changes": ["CI command matrix", "report-only measurements"],
            "forbidden_changes": ["safety-stage disablement", "network/webhook-enabled stage"],
            "recommended": True,
        },
    ]
    return {
        "built_at": _utc_now(),
        "options": options,
        "recommended_next_step": "Apply Option A for missed markers first, then Option C for scan-heavy tests.",
        "ci_stage_matrix": {
            "fast": "python -m pytest backend/app/foundation backend/app/audit -m 'not slow' -v",
            "slow": "python -m pytest backend/app/foundation backend/app/audit -m slow -v",
            "safety": "python -m pytest backend/app/foundation backend/app/audit -m 'no_network or no_runtime_write or no_secret' -v",
            "full": "python -m pytest backend/app/foundation backend/app/audit -v",
        },
    }


def _stringify_plan(plan: Dict[str, Any]) -> str:
    return json.dumps(plan, ensure_ascii=False, sort_keys=True).lower()


def validate_runtime_optimization_plan(plan: Dict[str, Any]) -> Dict[str, Any]:
    """Validate that the plan preserves safety and report-only boundaries."""
    errors: List[str] = []
    warnings: List[str] = []
    text = _stringify_plan(plan)

    forbidden_checks = [
        ("delete tests", "plan_must_not_delete_tests"),
        ("remove tests", "plan_must_not_remove_tests"),
        ("skip safety", "plan_must_not_skip_safety_tests"),
        ("xfail safety", "plan_must_not_xfail_safety_tests"),
        ("call network", "plan_must_not_call_network"),
        ("webhook call", "plan_must_not_call_webhook"),
        ("runtime write", "plan_must_not_write_runtime"),
        ("write audit jsonl", "plan_must_not_write_audit_jsonl"),
        ("auto-fix enabled", "plan_must_not_enable_auto_fix"),
    ]
    for phrase, error in forbidden_checks:
        if phrase in text:
            errors.append(error)

    matrix = plan.get("optimization_options", {}).get("ci_stage_matrix", {})
    for stage in ("fast", "slow", "safety", "full"):
        if stage not in matrix:
            errors.append(f"missing_ci_stage:{stage}")
    if "safety" in matrix and "no_network" not in matrix["safety"]:
        errors.append("safety_stage_missing_no_network_marker")
    if "safety" in matrix and "no_runtime_write" not in matrix["safety"]:
        errors.append("safety_stage_missing_no_runtime_write_marker")
    if "safety" in matrix and "no_secret" not in matrix["safety"]:
        errors.append("safety_stage_missing_no_secret_marker")

    if plan.get("deleted_tests"):
        errors.append("deleted_tests_not_allowed")
    if plan.get("safety_coverage_reduced"):
        errors.append("safety_coverage_reduction_not_allowed")

    return {
        "validated_at": _utc_now(),
        "valid": len(errors) == 0,
        "warnings": warnings,
        "errors": errors,
    }


def _render_markdown(plan: Dict[str, Any]) -> str:
    baseline = plan["runtime_baseline_summary"]
    slow = plan["remaining_slow_in_fast_detection"]
    marker = plan["marker_quality_audit"]
    validation = plan["validation"]
    options = plan["optimization_options"]["options"]

    measurement_lines = []
    for key in (
        "foundation_fast_runtime",
        "audit_fast_runtime",
        "slow_suite_runtime",
        "safety_suite_runtime",
        "collect_only_runtime",
        "stabilization_tests_runtime",
    ):
        item = baseline.get(key, {})
        measurement_lines.append(
            f"- `{key}`: runtime={item.get('runtime')}, passed={item.get('passed')}, "
            f"failed={item.get('failed')}, skipped={item.get('skipped')}, status={item.get('status')}"
        )

    candidates = slow["remaining_slow_in_fast"][:20]
    candidate_lines = [
        f"- `{c['file']}:{c['line']}` reason={c['reason']} recommendation={c['recommended_marker_change']}"
        for c in candidates
    ] or ["- none"]

    option_lines = [
        f"- {o['option_id']}: {o['name']} - recommended={o['recommended']}"
        for o in options
    ]

    return f"""# R241-15C Test Runtime Optimization Report

## 1. 修改文件清单

- `backend/app/foundation/runtime_optimization_plan.py`
- `backend/app/foundation/test_runtime_optimization.py`
- `migration_reports/foundation_audit/R241-15C_TEST_RUNTIME_OPTIMIZATION_PLAN.json`
- `migration_reports/foundation_audit/R241-15C_TEST_RUNTIME_OPTIMIZATION_REPORT.md`

## 2. runtime baseline summary

- `original_baseline_runtime`: {baseline['original_baseline_runtime']}
- `fast_combined_runtime`: {baseline.get('fast_combined_runtime')}
- `improvement_estimate`: {baseline.get('improvement_estimate')}

## 3. fast / slow / safety suite measurements

{chr(10).join(measurement_lines)}

## 4. remaining slow-in-fast candidates

- count: {slow['remaining_slow_in_fast_count']}
{chr(10).join(candidate_lines)}

## 5. marker quality audit

- required markers: {', '.join(marker['required_markers'])}
- configured markers: {', '.join(marker['configured_markers'])}
- pytest markers contains 8 required: {marker['pytest_markers_contains_8_required']}
- slow marker count: {marker['slow_marker_count']}
- safety marker count: {marker['safety_marker_count']}
- safety markers runnable: {marker['safety_markers_runnable']}
- safety tests all marked slow: {marker['safety_tests_all_marked_slow']}

## 6. optimization options

{chr(10).join(option_lines)}

## 7. recommended option

Recommended next step: {plan['optimization_options']['recommended_next_step']}

## 8. validation result

- valid: {validation['valid']}
- warnings: {validation['warnings']}
- errors: {validation['errors']}

## 9. 测试结果

This report is generated before final command output is copied into the final response. Required test commands are recorded in the JSON plan under `runtime_baseline_summary`.

## 10. 是否删除/跳过测试

No tests are deleted. No safety tests are skipped or xfailed.

## 11. 是否降低安全覆盖

No. The safety stage remains explicit: `no_network or no_runtime_write or no_secret`.

## 12. 是否写 runtime / audit JSONL / action queue

No runtime, audit JSONL, or action queue writes are performed by this plan helper.

## 13. 是否调用 network / webhook

No network or webhook calls are performed.

## 14. 是否执行 auto-fix

No auto-fix is performed.

## 15. 当前剩余断点

- Remaining slow-in-fast candidates require manual marker review before any marker changes.
- Real runtime measurements should be re-run after each marker refinement.

## 16. 下一轮建议

Proceed with targeted marker refinement for confirmed slow-in-fast tests, then synthetic fixture replacement for scan-heavy tests.
"""


def generate_runtime_optimization_plan(
    output_path: Optional[str] = None,
    measurements: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Generate R241-15C JSON and markdown report artifacts."""
    target = Path(output_path) if output_path else DEFAULT_PLAN_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.suffix.lower() != ".json":
        raise ValueError("runtime optimization plan output must be a .json file")

    measurements = measurements or {}
    plan = {
        "plan_id": "R241-15C_test_runtime_optimization",
        "generated_at": _utc_now(),
        "root": str(ROOT),
        "runtime_baseline_summary": build_runtime_baseline_summary(measurements),
        "remaining_slow_in_fast_detection": detect_remaining_slow_in_fast(str(ROOT)),
        "marker_quality_audit": audit_marker_quality(str(ROOT)),
        "optimization_options": build_runtime_optimization_options(),
        "deleted_tests": False,
        "safety_coverage_reduced": False,
        "warnings": [],
    }
    plan["validation"] = validate_runtime_optimization_plan(plan)

    target.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    markdown_path = target.with_name("R241-15C_TEST_RUNTIME_OPTIMIZATION_REPORT.md")
    markdown_path.write_text(_render_markdown(plan), encoding="utf-8")

    return {
        "plan": plan,
        "output_path": str(target),
        "markdown_path": str(markdown_path),
        "warnings": plan["warnings"],
        "validation": plan["validation"],
    }


__all__ = [
    "build_runtime_baseline_summary",
    "detect_remaining_slow_in_fast",
    "audit_marker_quality",
    "build_runtime_optimization_options",
    "validate_runtime_optimization_plan",
    "generate_runtime_optimization_plan",
]
