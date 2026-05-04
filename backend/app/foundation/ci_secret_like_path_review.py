"""R241-16X: Secret-like dirty path review.

This module performs a read-only, redacted review of frontend/.env.example
after R241-16W blocked closure on a secret-like dirty path. It never emits
complete file contents or raw secret-like values.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
import subprocess
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from backend.app.foundation import ci_working_tree_closure_condition as wt_closure


ROOT = Path(__file__).resolve().parents[3]
REPORT_DIR = ROOT / "migration_reports" / "foundation_audit"
R241_16W_PATH = REPORT_DIR / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json"
TARGET_PATH = "frontend/.env.example"


class SecretLikePathReviewStatus(str, Enum):
    REVIEWED_TEMPLATE_SAFE = "reviewed_template_safe"
    REVIEWED_REAL_SECRET_DETECTED = "reviewed_real_secret_detected"
    REVIEWED_NO_SECRET_LIKE_CONTENT = "reviewed_no_secret_like_content"
    BLOCKED_FILE_MISSING = "blocked_file_missing"
    BLOCKED_UNREADABLE_FILE = "blocked_unreadable_file"
    BLOCKED_HIGH_RISK_SECRET = "blocked_high_risk_secret"
    BLOCKED_UNKNOWN_SECRET_PATTERN = "blocked_unknown_secret_pattern"
    UNKNOWN = "unknown"


class SecretLikePathDecision(str, Enum):
    ALLOW_CLOSURE_WITH_SECRET_TEMPLATE_WARNING = "allow_closure_with_secret_template_warning"
    ALLOW_CLOSURE_NO_SECRET = "allow_closure_no_secret"
    BLOCK_UNTIL_SECRET_REVIEW = "block_until_secret_review"
    BLOCK_UNTIL_SECRET_REMOVED = "block_until_secret_removed"
    UNKNOWN = "unknown"


class SecretLikeFindingType(str, Enum):
    TEMPLATE_PLACEHOLDER = "template_placeholder"
    EMPTY_VALUE = "empty_value"
    LOCAL_EXAMPLE_VALUE = "local_example_value"
    SUSPICIOUS_TOKEN = "suspicious_token"
    WEBHOOK_URL = "webhook_url"
    PRIVATE_KEY = "private_key"
    PASSWORD_LIKE_VALUE = "password_like_value"
    API_KEY_LIKE_VALUE = "api_key_like_value"
    UNKNOWN = "unknown"


class SecretLikeRiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


SENSITIVE_KEY_RE = re.compile(
    r"(secret|token|password|passwd|pwd|api[_-]?key|private[_-]?key|webhook|credential)",
    re.IGNORECASE,
)
ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$")
WEBHOOK_RE = re.compile(r"https://[^\s'\"\)]+(?:hook|webhook|hooks|bot/v2/hook)[^\s'\"\)]*", re.IGNORECASE)
JWT_RE = re.compile(r"^[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}$")
GITHUB_TOKEN_RE = re.compile(r"^(ghp_|github_pat_)[A-Za-z0-9_]{20,}")
PROVIDER_KEY_RE = re.compile(r"^(sk-|sk-ant-)[A-Za-z0-9_-]{12,}")
PRIVATE_KEY_RE = re.compile(r"BEGIN (?:RSA |OPENSSH |EC |DSA )?PRIVATE KEY")

PLACEHOLDER_MARKERS = [
    "your_",
    "<your_",
    "replace_me",
    "example",
    "example.com",
    "localhost",
    "dummy",
    "test",
    "placeholder",
    "changeme",
    "xxx",
    "***",
]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _root(root: Optional[str]) -> Path:
    return Path(root).resolve() if root else ROOT


def _run_git(argv: list[str], root: Optional[str] = None, timeout: int = 30) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(_root(root)),
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
        )
        return {
            "argv": argv,
            "command_executed": True,
            "exit_code": completed.returncode,
            "stdout": completed.stdout,
            "stderr": completed.stderr,
        }
    except Exception as exc:  # pragma: no cover - defensive
        return {
            "argv": argv,
            "command_executed": False,
            "exit_code": None,
            "stdout": "",
            "stderr": str(exc),
        }


def _mask_value(value: str) -> str:
    if value == "":
        return "[EMPTY]"
    stripped = value.strip().strip("\"'")
    digest = hashlib.sha256(stripped.encode("utf-8", errors="ignore")).hexdigest()[:8]
    prefix = stripped[:3]
    suffix = stripped[-2:] if len(stripped) >= 2 else stripped
    return f"[REDACTED length={len(stripped)} prefix={prefix!r} suffix={suffix!r} sha256_8={digest}]"


def _strip_inline_comment(value: str) -> str:
    quote: Optional[str] = None
    for idx, char in enumerate(value):
        if char in ('"', "'"):
            quote = char if quote is None else None if quote == char else quote
        if char == "#" and quote is None:
            return value[:idx].strip()
    return value.strip()


def _is_placeholder(value: str, context: str = "") -> bool:
    v = value.strip().strip("\"'").lower()
    ctx = context.lower()
    if not v:
        return False
    return any(marker in v for marker in PLACEHOLDER_MARKERS) or any(
        marker in ctx for marker in ("example", "template", "not secret", "placeholder")
    )


def _shannon_entropy(value: str) -> float:
    if not value:
        return 0.0
    counts = {ch: value.count(ch) for ch in set(value)}
    length = len(value)
    return -sum((count / length) * math.log2(count / length) for count in counts.values())


def _finding(
    *,
    path: str,
    line_number: int,
    key_name: str,
    finding_type: str,
    risk_level: str,
    value: str,
    is_template_placeholder: bool,
    is_real_secret_candidate: bool,
    evidence_summary: str,
) -> dict[str, Any]:
    return {
        "finding_id": f"{path}:{line_number}:{key_name}:{finding_type}",
        "path": path,
        "line_number": line_number,
        "key_name": key_name,
        "finding_type": finding_type,
        "risk_level": risk_level,
        "value_present": bool(value),
        "value_masked_preview": _mask_value(value),
        "is_template_placeholder": is_template_placeholder,
        "is_real_secret_candidate": is_real_secret_candidate,
        "evidence_summary": evidence_summary,
        "warnings": [],
        "errors": [],
    }


def _classify_assignment(path: str, line_number: int, key: str, value: str, context: str) -> dict[str, Any]:
    normalized = value.strip().strip("\"'")
    key_is_sensitive = bool(SENSITIVE_KEY_RE.search(key))

    if normalized == "":
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=SecretLikeFindingType.EMPTY_VALUE.value,
            risk_level=SecretLikeRiskLevel.LOW.value,
            value=normalized,
            is_template_placeholder=True,
            is_real_secret_candidate=False,
            evidence_summary="empty value in env example",
        )

    if _is_placeholder(normalized, context):
        finding_type = SecretLikeFindingType.TEMPLATE_PLACEHOLDER.value
        if "localhost" in normalized.lower() or "example" in normalized.lower():
            finding_type = SecretLikeFindingType.LOCAL_EXAMPLE_VALUE.value
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=finding_type,
            risk_level=SecretLikeRiskLevel.LOW.value,
            value=normalized,
            is_template_placeholder=True,
            is_real_secret_candidate=False,
            evidence_summary="explicit template/example placeholder",
        )

    if WEBHOOK_RE.search(normalized):
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=SecretLikeFindingType.WEBHOOK_URL.value,
            risk_level=SecretLikeRiskLevel.HIGH.value,
            value=normalized,
            is_template_placeholder=False,
            is_real_secret_candidate=True,
            evidence_summary="webhook URL pattern",
        )

    if GITHUB_TOKEN_RE.search(normalized) or PROVIDER_KEY_RE.search(normalized) or JWT_RE.search(normalized):
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=SecretLikeFindingType.API_KEY_LIKE_VALUE.value,
            risk_level=SecretLikeRiskLevel.HIGH.value,
            value=normalized,
            is_template_placeholder=False,
            is_real_secret_candidate=True,
            evidence_summary="known provider token/key pattern",
        )

    if key_is_sensitive:
        finding_type = SecretLikeFindingType.SUSPICIOUS_TOKEN.value
        if "password" in key.lower() or "pwd" in key.lower() or "passwd" in key.lower():
            finding_type = SecretLikeFindingType.PASSWORD_LIKE_VALUE.value
        elif "api" in key.lower() or "key" in key.lower():
            finding_type = SecretLikeFindingType.API_KEY_LIKE_VALUE.value
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=finding_type,
            risk_level=SecretLikeRiskLevel.HIGH.value,
            value=normalized,
            is_template_placeholder=False,
            is_real_secret_candidate=True,
            evidence_summary="sensitive key with non-placeholder value",
        )

    if len(normalized) >= 32 and _shannon_entropy(normalized) >= 3.5:
        return _finding(
            path=path,
            line_number=line_number,
            key_name=key,
            finding_type=SecretLikeFindingType.SUSPICIOUS_TOKEN.value,
            risk_level=SecretLikeRiskLevel.MEDIUM.value,
            value=normalized,
            is_template_placeholder=False,
            is_real_secret_candidate=False,
            evidence_summary="long high-entropy value under non-sensitive key",
        )

    return _finding(
        path=path,
        line_number=line_number,
        key_name=key,
        finding_type=SecretLikeFindingType.UNKNOWN.value,
        risk_level=SecretLikeRiskLevel.LOW.value,
        value=normalized,
        is_template_placeholder=False,
        is_real_secret_candidate=False,
        evidence_summary="non-sensitive env example value",
    )


def load_r241_16w_secret_like_condition(root: str | None = None) -> dict[str, Any]:
    root_path = _root(root)
    report_path = root_path / "migration_reports" / "foundation_audit" / "R241-16W_WORKING_TREE_CLOSURE_CONDITION.json"
    warnings: list[str] = []
    errors: list[str] = []
    data: dict[str, Any] = {}

    if not report_path.exists():
        return {"loaded": False, "exists": False, "condition": {}, "passed": False, "warnings": warnings, "errors": ["R241-16W report missing"]}
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return {"loaded": False, "exists": True, "condition": {}, "passed": False, "warnings": warnings, "errors": [f"malformed R241-16W JSON: {exc}"]}

    if data.get("status") != "blocked_unknown_dirty_state":
        errors.append("R241-16W status is not blocked_unknown_dirty_state")
    if data.get("decision") != "block_closure_until_worktree_review":
        errors.append("R241-16W decision is not block_closure_until_worktree_review")

    checks = data.get("closure_checks", [])
    no_secret_check = next((c for c in checks if c.get("check_id") == "no_secret_like_paths"), None)
    if not no_secret_check or no_secret_check.get("passed") is not False:
        errors.append("R241-16W no_secret_like_paths failed check not found")
    blocked_text = json.dumps(no_secret_check or {}, ensure_ascii=False)
    dirty_text = json.dumps(data.get("dirty_files", []), ensure_ascii=False)
    if TARGET_PATH not in blocked_text and TARGET_PATH not in dirty_text:
        errors.append("frontend/.env.example is not present as secret-like path")
    if data.get("staged_files") != []:
        errors.append("R241-16W staged_files is not empty")
    if len(data.get("delivery_scope_dirty_files", [])) != 0:
        errors.append("R241-16W delivery_scope_dirty_files is not empty")
    if len(data.get("workflow_scope_dirty_files", [])) != 0:
        errors.append("R241-16W workflow_scope_dirty_files is not empty")

    safety = data.get("safety_summary", {})
    if safety.get("runtime_scope_clean") is not True:
        errors.append("R241-16W runtime_scope_clean is not true")
    if safety.get("delivery_artifacts_verified") is not True:
        errors.append("R241-16W delivery_artifacts_verified is not true")
    if safety.get("workflow_files_verified") is not True:
        errors.append("R241-16W workflow_files_verified is not true")

    return {
        "loaded": True,
        "exists": True,
        "condition": data,
        "passed": len(errors) == 0,
        "failed_check": "no_secret_like_paths" if no_secret_check else None,
        "secret_like_path": TARGET_PATH if TARGET_PATH in blocked_text + dirty_text else None,
        "warnings": warnings,
        "errors": errors,
    }


def inspect_secret_like_target_file(root: str | None = None, path: str = TARGET_PATH) -> dict[str, Any]:
    root_path = _root(root)
    target = root_path / path
    warnings: list[str] = []
    errors: list[str] = []
    result: dict[str, Any] = {
        "path": path,
        "exists": target.exists(),
        "is_file": target.is_file(),
        "tracked": False,
        "ignored": False,
        "file_size_bytes": 0,
        "line_count": 0,
        "diff_status": [],
        "content_readable": False,
        "warnings": warnings,
        "errors": errors,
    }
    if not target.exists():
        errors.append("target file missing")
        return result
    if not target.is_file():
        errors.append("target path is not a file")
        return result

    try:
        text = target.read_text(encoding="utf-8")
        result["content_readable"] = True
        result["file_size_bytes"] = target.stat().st_size
        result["line_count"] = len(text.splitlines())
    except Exception as exc:
        errors.append(f"target file unreadable: {exc}")

    ls_files = _run_git(["git", "ls-files", "--", path], root)
    result["tracked"] = ls_files["exit_code"] == 0 and bool(ls_files["stdout"].strip())

    ignored = _run_git(["git", "check-ignore", "-v", path], root)
    result["ignored"] = ignored["exit_code"] == 0 and bool(ignored["stdout"].strip())

    diff = _run_git(["git", "diff", "--name-status", "--", path], root)
    if diff["exit_code"] == 0:
        result["diff_status"] = [line.strip() for line in diff["stdout"].splitlines() if line.strip()]
    else:
        warnings.append("git diff name-status unavailable")

    return result


def scan_env_example_for_secret_findings(root: str | None = None, path: str = TARGET_PATH) -> dict[str, Any]:
    root_path = _root(root)
    target = root_path / path
    warnings: list[str] = []
    errors: list[str] = []
    findings: list[dict[str, Any]] = []
    total_lines = 0
    env_key_count = 0
    comment_count = 0

    try:
        lines = target.read_text(encoding="utf-8").splitlines()
    except Exception as exc:
        return {
            "findings": [],
            "total_lines": 0,
            "env_key_count": 0,
            "comment_count": 0,
            "empty_value_count": 0,
            "placeholder_count": 0,
            "real_secret_candidate_count": 0,
            "suspicious_value_count": 0,
            "warnings": warnings,
            "errors": [f"cannot read target file: {exc}"],
        }

    total_lines = len(lines)
    previous_comments: list[str] = []
    private_key_open = False

    for idx, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("#"):
            comment_count += 1
            previous_comments.append(stripped)
            previous_comments = previous_comments[-3:]
            continue

        if PRIVATE_KEY_RE.search(stripped):
            private_key_open = True
            findings.append(_finding(
                path=path,
                line_number=idx,
                key_name="PRIVATE_KEY_BLOCK",
                finding_type=SecretLikeFindingType.PRIVATE_KEY.value,
                risk_level=SecretLikeRiskLevel.CRITICAL.value,
                value=stripped,
                is_template_placeholder=False,
                is_real_secret_candidate=True,
                evidence_summary="private key block marker",
            ))
            continue
        if private_key_open and "END " in stripped and "PRIVATE KEY" in stripped:
            private_key_open = False
            continue

        match = ASSIGNMENT_RE.match(line)
        if not match:
            previous_comments = []
            continue

        key = match.group(1)
        value = _strip_inline_comment(match.group(2))
        context = "\n".join(previous_comments)
        env_key_count += 1
        findings.append(_classify_assignment(path, idx, key, value, context))
        previous_comments = []

    empty_count = sum(1 for f in findings if f["finding_type"] == SecretLikeFindingType.EMPTY_VALUE.value)
    placeholder_count = sum(1 for f in findings if f["is_template_placeholder"])
    real_count = sum(1 for f in findings if f["is_real_secret_candidate"])
    suspicious_count = sum(
        1 for f in findings
        if f["finding_type"] == SecretLikeFindingType.SUSPICIOUS_TOKEN.value and not f["is_real_secret_candidate"]
    )

    return {
        "findings": findings,
        "total_lines": total_lines,
        "env_key_count": env_key_count,
        "comment_count": comment_count,
        "empty_value_count": empty_count,
        "placeholder_count": placeholder_count,
        "real_secret_candidate_count": real_count,
        "suspicious_value_count": suspicious_count,
        "warnings": warnings,
        "errors": errors,
    }


def classify_secret_like_findings(findings: list) -> dict[str, Any]:
    real_count = sum(1 for f in findings if f.get("is_real_secret_candidate"))
    suspicious_count = sum(
        1 for f in findings
        if f.get("finding_type") == SecretLikeFindingType.SUSPICIOUS_TOKEN.value
        and not f.get("is_real_secret_candidate")
    )
    placeholder_count = sum(1 for f in findings if f.get("is_template_placeholder"))
    empty_count = sum(1 for f in findings if f.get("finding_type") == SecretLikeFindingType.EMPTY_VALUE.value)
    sensitive_count = sum(1 for f in findings if SENSITIVE_KEY_RE.search(str(f.get("key_name", ""))))

    if real_count:
        risk = SecretLikeRiskLevel.CRITICAL.value if any(f.get("risk_level") == "critical" for f in findings) else SecretLikeRiskLevel.HIGH.value
        return {
            "classification": "real_secret_candidate",
            "risk_level": risk,
            "allow_closure": False,
            "warnings": [],
            "errors": [],
        }
    if suspicious_count:
        return {
            "classification": "needs_manual_secret_review",
            "risk_level": SecretLikeRiskLevel.MEDIUM.value,
            "allow_closure": False,
            "warnings": ["suspicious high-entropy non-sensitive value requires manual review"],
            "errors": [],
        }
    if sensitive_count and (placeholder_count + empty_count >= sensitive_count):
        return {
            "classification": "secret_template_path",
            "risk_level": SecretLikeRiskLevel.LOW.value,
            "allow_closure": True,
            "warnings": ["secret-like path contains template placeholders or empty values only"],
            "errors": [],
        }
    return {
        "classification": "no_secret_like_content",
        "risk_level": SecretLikeRiskLevel.LOW.value,
        "allow_closure": True,
        "warnings": [],
        "errors": [],
    }


def _check(check_id: str, passed: bool, risk: str, description: str, observed: Any, expected: Any, reasons: Optional[list[str]] = None) -> dict[str, Any]:
    return {
        "check_id": check_id,
        "passed": passed,
        "risk_level": risk,
        "description": description,
        "observed_value": str(observed),
        "expected_value": str(expected),
        "evidence_refs": [],
        "required_for_closure": True,
        "blocked_reasons": reasons or [],
        "warnings": [],
        "errors": [],
    }


def evaluate_secret_like_path_review(root: str | None = None) -> dict[str, Any]:
    condition = load_r241_16w_secret_like_condition(root)
    target = inspect_secret_like_target_file(root, TARGET_PATH)
    scan = scan_env_example_for_secret_findings(root, TARGET_PATH) if target.get("content_readable") else {
        "findings": [],
        "total_lines": 0,
        "env_key_count": 0,
        "comment_count": 0,
        "empty_value_count": 0,
        "placeholder_count": 0,
        "real_secret_candidate_count": 0,
        "suspicious_value_count": 0,
        "warnings": [],
        "errors": target.get("errors", []),
    }
    classification = classify_secret_like_findings(scan.get("findings", []))

    status = SecretLikePathReviewStatus.UNKNOWN.value
    decision = SecretLikePathDecision.UNKNOWN.value
    if not target.get("exists"):
        status = SecretLikePathReviewStatus.BLOCKED_FILE_MISSING.value
        decision = SecretLikePathDecision.BLOCK_UNTIL_SECRET_REVIEW.value
    elif not target.get("content_readable"):
        status = SecretLikePathReviewStatus.BLOCKED_UNREADABLE_FILE.value
        decision = SecretLikePathDecision.BLOCK_UNTIL_SECRET_REVIEW.value
    elif classification["classification"] == "secret_template_path":
        status = SecretLikePathReviewStatus.REVIEWED_TEMPLATE_SAFE.value
        decision = SecretLikePathDecision.ALLOW_CLOSURE_WITH_SECRET_TEMPLATE_WARNING.value
    elif classification["classification"] == "no_secret_like_content":
        status = SecretLikePathReviewStatus.REVIEWED_NO_SECRET_LIKE_CONTENT.value
        decision = SecretLikePathDecision.ALLOW_CLOSURE_NO_SECRET.value
    elif classification["classification"] == "needs_manual_secret_review":
        status = SecretLikePathReviewStatus.BLOCKED_UNKNOWN_SECRET_PATTERN.value
        decision = SecretLikePathDecision.BLOCK_UNTIL_SECRET_REVIEW.value
    else:
        status = SecretLikePathReviewStatus.BLOCKED_HIGH_RISK_SECRET.value
        decision = SecretLikePathDecision.BLOCK_UNTIL_SECRET_REMOVED.value

    closure_reclassification = classification["classification"]
    checks = [
        _check("r241_16w_condition_loaded", condition.get("passed", False), SecretLikeRiskLevel.MEDIUM.value, "R241-16W condition matches expected secret-like path block", condition.get("passed"), True, condition.get("errors", [])),
        _check("target_file_readable", target.get("content_readable", False), SecretLikeRiskLevel.HIGH.value, "Target env example is readable", target.get("content_readable"), True, target.get("errors", [])),
        _check("no_real_secret_candidates", scan.get("real_secret_candidate_count", 0) == 0, SecretLikeRiskLevel.CRITICAL.value, "No real secret candidates detected", scan.get("real_secret_candidate_count", 0), 0),
        _check("no_raw_values_emitted", True, SecretLikeRiskLevel.HIGH.value, "Findings use masked previews only", "masked", "masked"),
    ]

    safety_summary = {
        "git_commit_executed": False,
        "git_push_executed": False,
        "git_reset_restore_revert_executed": False,
        "git_am_apply_executed": False,
        "gh_workflow_run_executed": False,
        "secret_environment_read": False,
        "workflow_modified": False,
        "runtime_write": False,
        "audit_jsonl_write": False,
        "action_queue_write": False,
        "auto_fix_executed": False,
        "raw_secret_value_emitted": False,
    }

    review = {
        "review_id": f"r241-16x-secret-like-path-review-{hashlib.sha256(_now().encode()).hexdigest()[:8]}",
        "generated_at": _now(),
        "status": status,
        "decision": decision,
        "target_path": TARGET_PATH,
        "target_exists": target.get("exists", False),
        "target_is_tracked": target.get("tracked", False),
        "target_is_ignored": target.get("ignored", False),
        "r241_16w_status": condition.get("condition", {}).get("status"),
        "r241_16w_decision": condition.get("condition", {}).get("decision"),
        "r241_16w_failed_check": condition.get("failed_check"),
        "target_file_inspection": target,
        "scan_summary": {k: v for k, v in scan.items() if k != "findings"},
        "findings": scan.get("findings", []),
        "finding_count": len(scan.get("findings", [])),
        "real_secret_candidate_count": scan.get("real_secret_candidate_count", 0),
        "template_placeholder_count": scan.get("placeholder_count", 0),
        "empty_value_count": scan.get("empty_value_count", 0),
        "suspicious_value_count": scan.get("suspicious_value_count", 0),
        "finding_classification": classification,
        "closure_reclassification": closure_reclassification,
        "closure_checks": checks,
        "receiver_next_steps": [
            "Do not commit or clean unrelated working tree files in this review.",
            "If accepted, re-run final closure re-evaluation with secret_template_path treated as external worktree condition.",
        ] if classification.get("allow_closure") else [
            "Block closure until the suspicious value is reviewed manually.",
            "Do not print or commit raw values during remediation.",
        ],
        "safety_summary": safety_summary,
        "validation_result": {"valid": True, "warnings": [], "errors": []},
        "warnings": condition.get("warnings", []) + target.get("warnings", []) + scan.get("warnings", []) + classification.get("warnings", []),
        "errors": condition.get("errors", []) + target.get("errors", []) + scan.get("errors", []) + classification.get("errors", []),
    }
    review["validation_result"] = validate_secret_like_path_review(review)
    return review


def _contains_raw_secret_like_value(obj: Any) -> bool:
    text = json.dumps(obj, ensure_ascii=False)
    forbidden = [
        "BEGIN PRIVATE KEY",
        "BEGIN RSA PRIVATE KEY",
        "BEGIN OPENSSH PRIVATE KEY",
        "https://open.feishu.cn/open-apis/bot/v2/hook/",
        "https://hooks.slack.com/",
        "ghp_",
        "github_pat_",
        "sk-ant-",
    ]
    return any(token in text for token in forbidden)


def validate_secret_like_path_review(review: dict) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    safety = review.get("safety_summary", {})

    for key in [
        "git_commit_executed",
        "git_push_executed",
        "git_reset_restore_revert_executed",
        "git_am_apply_executed",
        "gh_workflow_run_executed",
        "secret_environment_read",
        "workflow_modified",
        "runtime_write",
        "audit_jsonl_write",
        "action_queue_write",
        "auto_fix_executed",
        "raw_secret_value_emitted",
    ]:
        if safety.get(key):
            errors.append(f"{key} must be false")

    allow_decisions = {
        SecretLikePathDecision.ALLOW_CLOSURE_WITH_SECRET_TEMPLATE_WARNING.value,
        SecretLikePathDecision.ALLOW_CLOSURE_NO_SECRET.value,
    }
    if review.get("decision") in allow_decisions and review.get("real_secret_candidate_count", 0) != 0:
        errors.append("allow closure requires real_secret_candidate_count=0")
    if review.get("decision") in allow_decisions and review.get("closure_reclassification") not in {
        "secret_template_path",
        "no_secret_like_content",
    }:
        errors.append("allow closure requires safe closure_reclassification")

    serialized = json.dumps(review, ensure_ascii=False)
    if "frontend/.env.example content" in serialized.lower():
        errors.append("full .env.example content appears embedded")
    if _contains_raw_secret_like_value(review):
        errors.append("raw secret-like value appears embedded")
    for finding in review.get("findings", []):
        preview = str(finding.get("value_masked_preview", ""))
        if finding.get("value_present") and not (preview.startswith("[REDACTED") or preview == "[EMPTY]"):
            errors.append(f"finding {finding.get('finding_id')} has unmasked preview")

    return {"valid": len(errors) == 0, "warnings": warnings, "errors": errors}


def generate_secret_like_path_review_report(
    review: dict | None = None,
    output_path: str | None = None,
) -> dict[str, Any]:
    if review is None:
        review = evaluate_secret_like_path_review()
    validation = validate_secret_like_path_review(review)
    review["validation_result"] = validation

    base = Path(output_path).resolve() if output_path else REPORT_DIR / "R241-16X_SECRET_LIKE_PATH_REVIEW.json"
    if base.suffix.lower() == ".md":
        json_path = base.with_suffix(".json")
        md_path = base
    else:
        json_path = base
        md_path = base.with_suffix(".md")
    json_path.parent.mkdir(parents=True, exist_ok=True)

    payload = {"generated_at": _now(), "review": review, "validation": validation}
    json_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    lines = [
        "# R241-16X Secret-like Path Review",
        "",
        "## 1. 修改文件清单",
        "- backend/app/foundation/ci_secret_like_path_review.py",
        "- backend/app/foundation/test_ci_secret_like_path_review.py",
        "- migration_reports/foundation_audit/R241-16X_SECRET_LIKE_PATH_REVIEW.json",
        "- migration_reports/foundation_audit/R241-16X_SECRET_LIKE_PATH_REVIEW.md",
        "",
        "## 2. SecretLikePathReviewStatus / Decision / FindingType / RiskLevel",
        f"- Status: `{review.get('status')}`",
        f"- Decision: `{review.get('decision')}`",
        f"- Finding types: `{', '.join(t.value for t in SecretLikeFindingType)}`",
        f"- Risk levels: `{', '.join(r.value for r in SecretLikeRiskLevel)}`",
        "",
        "## 3. SecretLikeFinding 字段",
        "- finding_id, path, line_number, key_name, finding_type, risk_level, value_present, value_masked_preview, is_template_placeholder, is_real_secret_candidate, evidence_summary, warnings, errors",
        "",
        "## 4. SecretLikePathReviewCheck 字段",
        "- check_id, passed, risk_level, description, observed_value, expected_value, evidence_refs, required_for_closure, blocked_reasons, warnings, errors",
        "",
        "## 5. SecretLikePathReview 字段",
        "- review_id, generated_at, status, decision, target_path, target_exists, target_is_tracked, target_is_ignored, r241_16w_status, r241_16w_decision, r241_16w_failed_check, findings, counts, closure_reclassification, closure_checks, receiver_next_steps, safety_summary, validation_result, warnings, errors",
        "",
        "## 6. R241-16W Loading Result",
        f"- r241_16w_status: `{review.get('r241_16w_status')}`",
        f"- r241_16w_decision: `{review.get('r241_16w_decision')}`",
        f"- r241_16w_failed_check: `{review.get('r241_16w_failed_check')}`",
        "",
        "## 7. Target File Inspection Result",
        f"- target_path: `{review.get('target_path')}`",
        f"- target_exists: `{review.get('target_exists')}`",
        f"- target_is_tracked: `{review.get('target_is_tracked')}`",
        f"- target_is_ignored: `{review.get('target_is_ignored')}`",
        f"- line_count: `{review.get('target_file_inspection', {}).get('line_count')}`",
        "",
        "## 8. Secret Finding Scan Summary",
        f"- finding_count: `{review.get('finding_count')}`",
        f"- real_secret_candidate_count: `{review.get('real_secret_candidate_count')}`",
        f"- template_placeholder_count: `{review.get('template_placeholder_count')}`",
        f"- empty_value_count: `{review.get('empty_value_count')}`",
        f"- suspicious_value_count: `{review.get('suspicious_value_count')}`",
        "",
        "## 9. Finding Classification Result",
        f"- classification: `{review.get('closure_reclassification')}`",
        f"- risk_level: `{review.get('finding_classification', {}).get('risk_level')}`",
        "",
        "## 10. Closure Reclassification Result",
        f"- closure_reclassification: `{review.get('closure_reclassification')}`",
        f"- decision: `{review.get('decision')}`",
        "",
        "## 11. Validation Result",
        f"- valid: `{validation.get('valid')}`",
        f"- errors: `{validation.get('errors')}`",
        "",
        "## 12. 测试结果",
        "- See final execution log for pytest command results.",
        "",
        "## 13-22. Safety Summary",
    ]
    safety = review.get("safety_summary", {})
    for key in [
        "git_commit_executed",
        "git_push_executed",
        "git_reset_restore_revert_executed",
        "git_am_apply_executed",
        "gh_workflow_run_executed",
        "secret_environment_read",
        "raw_secret_value_emitted",
        "workflow_modified",
        "runtime_write",
        "audit_jsonl_write",
        "action_queue_write",
        "auto_fix_executed",
    ]:
        lines.append(f"- {key}: `{safety.get(key)}`")
    lines.extend([
        "",
        "## 23. 当前剩余断点",
        "- Working tree still has unrelated dirty files; this review only reclassifies frontend/.env.example if safe.",
        "",
        "## 24. 下一轮建议",
        "- Run R241-16Y Final Closure Re-evaluation using this review as evidence.",
    ])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    return {
        "json_path": str(json_path),
        "markdown_path": str(md_path),
        "review": review,
        "validation": validation,
        "warnings": [],
        "errors": [],
    }

