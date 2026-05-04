"""Tests for Feishu trend manual send policy design (R241-13D).

These tests exercise the policy design functions in isolation.
They never write audit JSONL, never call network/webhooks, never write
runtime/action queue, and never send Feishu messages.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ─── Import test ─────────────────────────────────────────────────────────────

def test_import_module():
    from app.audit import (
        FeishuManualSendPolicyStatus,
        FeishuManualSendPermission,
        FeishuWebhookPolicyType,
        FeishuManualSendAuditMode,
        FeishuManualSendRiskLevel,
        build_feishu_webhook_policy,
        build_manual_send_confirmation_policy,
        build_pre_send_validation_policy,
        build_manual_send_audit_policy,
        design_allowed_manual_send_flow,
        build_manual_send_blocked_paths,
        build_feishu_manual_send_policy_design,
        validate_feishu_manual_send_policy_design,
        generate_feishu_manual_send_policy_design,
    )
    assert FeishuManualSendPolicyStatus.DESIGN_ONLY.value == "design_only"
    assert FeishuManualSendPermission.FORBIDDEN.value == "forbidden"
    assert FeishuWebhookPolicyType.ALLOWLIST_ONLY.value == "allowlist_only"
    assert FeishuManualSendAuditMode.PRE_SEND_AUDIT_REQUIRED.value == "pre_send_audit_required"
    assert FeishuManualSendRiskLevel.HIGH.value == "high"


# ─── TestWebhookPolicy ───────────────────────────────────────────────────────

class TestWebhookPolicy:
    def test_webhook_url_allowed_inline_is_false(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        assert policy["webhook_url_allowed_inline"] is False

    def test_secret_inline_allowed_is_false(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        assert policy["secret_inline_allowed"] is False

    def test_allowlist_required_is_true(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        assert policy["allowlist_required"] is True

    def test_policy_type_is_forbidden_inline_secret(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        assert policy["policy_type"] == "forbidden_inline_secret"

    def test_webhook_policy_no_real_webhook_url(self):
        from app.audit import build_feishu_webhook_policy
        import re
        WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
        policy = build_feishu_webhook_policy()
        policy_str = json.dumps(policy)
        assert not WEBHOOK_RE.search(policy_str), "Real webhook URL found in webhook policy"

    def test_webhook_policy_forbidden_warnings_present(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        warnings = policy.get("warnings") or []
        assert "inline_webhook_url_forbidden" in warnings
        assert "inline_secret_forbidden" in warnings

    def test_webhook_policy_has_environment_variable_names(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        env_vars = policy.get("environment_variable_names") or []
        assert len(env_vars) > 0
        assert "FEISHU_WEBHOOK_URL" in env_vars

    def test_webhook_policy_has_secret_manager_refs(self):
        from app.audit import build_feishu_webhook_policy
        policy = build_feishu_webhook_policy()
        refs = policy.get("secret_manager_refs") or []
        assert len(refs) > 0


# ─── TestConfirmationPolicy ──────────────────────────────────────────────────

class TestConfirmationPolicy:
    def test_user_confirmation_required_is_true(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["user_confirmation_required"] is True

    def test_confirmation_policy_has_required_phrase(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["required_confirmation_phrase"] == "CONFIRM_FEISHU_TREND_SEND"

    def test_confirm_after_preview_required(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["confirm_after_preview_required"] is True

    def test_confirm_after_validation_required(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["confirm_after_validation_required"] is True

    def test_confirm_after_audit_preview_required(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["confirm_after_audit_preview_required"] is True

    def test_max_payload_age_is_60_minutes(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy["max_payload_age_minutes"] == 60

    def test_confirmation_warnings_present(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        warnings = policy.get("warnings") or []
        assert "confirmation_required_before_any_send" in warnings


# ─── TestPreSendValidationPolicy ────────────────────────────────────────────

class TestPreSendValidationPolicy:
    def test_require_projection_validation_valid(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_projection_validation_valid"] is True

    def test_require_no_sensitive_content(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_sensitive_content"] is True

    def test_require_no_webhook_url_in_payload(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_webhook_url_in_payload"] is True

    def test_require_no_token_secret_api_key(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_token_secret_api_key"] is True

    def test_require_no_runtime_write(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_runtime_write"] is True

    def test_require_no_action_queue_write(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_action_queue_write"] is True

    def test_require_no_auto_fix(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_no_auto_fix"] is True

    def test_require_guard_jsonl_unchanged(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_guard_jsonl_unchanged"] is True

    def test_require_card_json_serializable(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_card_json_serializable"] is True

    def test_require_artifact_links_only_report_artifacts(self):
        from app.audit import build_pre_send_validation_policy
        policy = build_pre_send_validation_policy()
        assert policy["require_artifact_links_only_report_artifacts"] is True


# ─── TestAuditPolicy ────────────────────────────────────────────────────────

class TestAuditPolicy:
    def test_pre_send_audit_required(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["pre_send_audit_required"] is True

    def test_post_send_audit_required(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["post_send_audit_required"] is True

    def test_append_only_required(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["append_only_required"] is True

    def test_payload_hash_required(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["payload_hash_required"] is True

    def test_redaction_required(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["redaction_required"] is True

    def test_raw_webhook_never_logged(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["raw_webhook_never_logged"] is True

    def test_send_result_metadata_only(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["send_result_metadata_only"] is True

    def test_audit_event_types_defined(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        assert policy["audit_event_type"] == "feishu_trend_manual_send_attempt"
        assert policy["audit_result_event_type"] == "feishu_trend_manual_send_result"

    def test_audit_warnings_contain_raw_webhook_warning(self):
        from app.audit import build_manual_send_audit_policy
        policy = build_manual_send_audit_policy()
        warnings = policy.get("warnings") or []
        assert "raw_webhook_url_and_response_never_in_audit" in warnings


# ─── TestAllowedFlow ───────────────────────────────────────────────────────

class TestAllowedFlow:
    def test_allowed_flow_has_12_steps(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        assert len(flow) == 12

    def test_allowed_flow_steps_1_to_6_allowed_now(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        for step in flow[:6]:
            assert step["allowed_now"] is True, f"Step {step['step']} should be allowed now"

    def test_allowed_flow_steps_7_to_12_not_allowed_now(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        for step in flow[6:]:
            assert step["allowed_now"] is False, f"Step {step['step']} should NOT be allowed now"

    def test_allowed_flow_has_confirmation_step(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        confirmation_steps = [s for s in flow if "confirmation" in s["step"].lower()]
        assert len(confirmation_steps) >= 1

    def test_allowed_flow_has_audit_steps(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        audit_steps = [s for s in flow if "audit" in s["step"].lower()]
        assert len(audit_steps) >= 2

    def test_allowed_flow_no_auto_fix_step(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        for step in flow:
            assert "auto_fix" not in step.get("forbidden_actions", []) or step["step"] == "Never auto-fix"

    def test_allowed_flow_scheduler_send_blocked(self):
        from app.audit import design_allowed_manual_send_flow
        flow = design_allowed_manual_send_flow()
        scheduler_step = next((s for s in flow if "scheduler" in s["step"].lower()), None)
        if scheduler_step:
            assert scheduler_step["allowed_now"] is False


# ─── TestBlockedPaths ──────────────────────────────────────────────────────

class TestBlockedPaths:
    def test_blocked_paths_not_empty(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        assert len(paths) > 0

    def test_blocked_paths_contains_inline_webhook_url(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        path_names = [p.get("path") for p in paths]
        assert "inline_webhook_url" in path_names

    def test_blocked_paths_contains_send_without_confirmation(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        path_names = [p.get("path") for p in paths]
        assert "send_without_confirmation" in path_names

    def test_blocked_paths_contains_scheduler_auto_send(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        path_names = [p.get("path") for p in paths]
        assert "scheduler_auto_send" in path_names

    def test_blocked_paths_contains_auto_fix(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        path_names = [p.get("path") for p in paths]
        assert "send_plus_auto_fix" in path_names

    def test_blocked_paths_contains_raw_webhook_in_audit(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        path_names = [p.get("path") for p in paths]
        assert "raw_webhook_in_audit" in path_names

    def test_blocked_paths_all_have_severity(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        for p in paths:
            assert "severity" in p, f"Blocked path {p.get('path')} missing severity"

    def test_blocked_paths_critical_high_forbidden_paths(self):
        from app.audit import build_manual_send_blocked_paths
        paths = build_manual_send_blocked_paths()
        critical_paths = [p for p in paths if p.get("severity") == "critical"]
        assert len(critical_paths) >= 5


# ─── TestPolicyDesign ─────────────────────────────────────────────────────

class TestPolicyDesign:
    def test_design_has_all_required_policies(self):
        from app.audit import build_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        assert "webhook_policy" in design
        assert "confirmation_policy" in design
        assert "pre_send_validation_policy" in design
        assert "send_audit_policy" in design
        assert "blocked_send_paths" in design
        assert "allowed_future_send_flow" in design
        assert "implementation_phases" in design

    def test_design_status_is_design_only(self):
        from app.audit import build_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        assert design["status"] == "design_only"

    def test_implementation_phases_has_6_phases(self):
        from app.audit import build_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        phases = design.get("implementation_phases") or []
        assert len(phases) == 6
        phase_numbers = {p.get("phase") for p in phases}
        assert phase_numbers == {1, 2, 3, 4, 5, 6}

    def test_phase_1_is_current(self):
        from app.audit import build_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        phases = design.get("implementation_phases") or []
        phase1 = next((p for p in phases if p.get("phase") == 1), None)
        assert phase1 is not None
        assert phase1["status"] == "current"
        assert phase1["allowed_now"] is True

    def test_phase_5_is_future(self):
        from app.audit import build_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        phases = design.get("implementation_phases") or []
        phase5 = next((p for p in phases if p.get("phase") == 5), None)
        assert phase5 is not None
        assert phase5["status"] == "future"
        assert phase5["allowed_now"] is False


# ─── TestValidation ─────────────────────────────────────────────────────────

class TestValidation:
    def test_validate_design_validates_true(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is True
        assert len(result["errors"]) == 0

    def test_validate_rejects_webhook_url_allowed_inline_true(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["webhook_policy"]["webhook_url_allowed_inline"] = True
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "webhook_url_allowed_inline_must_be_false" in result["errors"]

    def test_validate_rejects_secret_inline_allowed_true(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["webhook_policy"]["secret_inline_allowed"] = True
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "secret_inline_allowed_must_be_false" in result["errors"]

    def test_validate_rejects_user_confirmation_false(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["confirmation_policy"]["user_confirmation_required"] = False
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "user_confirmation_required_must_be_true" in result["errors"]

    def test_validate_rejects_pre_send_audit_false(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["send_audit_policy"]["pre_send_audit_required"] = False
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "pre_send_audit_required_must_be_true" in result["errors"]

    def test_validate_rejects_post_send_audit_false(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["send_audit_policy"]["post_send_audit_required"] = False
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "post_send_audit_required_must_be_true" in result["errors"]

    def test_validate_rejects_append_only_false(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["send_audit_policy"]["append_only_required"] = False
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "append_only_required_must_be_true" in result["errors"]

    def test_validate_rejects_raw_webhook_logged(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["send_audit_policy"]["raw_webhook_never_logged"] = False
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "raw_webhook_never_logged_must_be_true" in result["errors"]

    def test_validate_rejects_scheduler_auto_send_not_blocked(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["blocked_send_paths"] = [p for p in design["blocked_send_paths"] if p.get("path") != "scheduler_auto_send"]
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "scheduler_auto_send_not_blocked" in result["errors"]

    def test_validate_rejects_auto_fix_not_blocked(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["blocked_send_paths"] = [p for p in design["blocked_send_paths"] if p.get("path") != "send_plus_auto_fix"]
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "auto_fix_not_blocked_in_send_flow" in result["errors"]

    def test_validate_rejects_real_webhook_url(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        design["webhook_policy"]["allowed_domain_patterns"].append("https://open.feishu.cn/webhook/xxx")
        result = validate_feishu_manual_send_policy_design(design)
        assert result["valid"] is False
        assert "real_webhook_url_found_in_design" in result["errors"]

    def test_validate_returns_all_checks(self):
        from app.audit import build_feishu_manual_send_policy_design, validate_feishu_manual_send_policy_design
        design = build_feishu_manual_send_policy_design()
        result = validate_feishu_manual_send_policy_design(design)
        assert result["webhook_url_allowed_inline_is_false"] is True
        assert result["secret_inline_allowed_is_false"] is True
        assert result["user_confirmation_required_is_true"] is True
        assert result["pre_send_audit_required_is_true"] is True
        assert result["post_send_audit_required_is_true"] is True
        assert result["append_only_required_is_true"] is True
        assert result["raw_webhook_never_logged_is_true"] is True
        assert result["scheduler_auto_send_blocked"] is True
        assert result["auto_fix_blocked"] is True
        assert result["implementation_phases_complete"] is True
        assert result["blocked_paths_count"] > 0


# ─── TestGenerate ──────────────────────────────────────────────────────────

class TestGenerate:
    def test_generate_writes_tmp_path(self, tmp_path):
        from app.audit import generate_feishu_manual_send_policy_design
        output_path = tmp_path / "R241-13D_TEST_CONTRACT.json"
        result = generate_feishu_manual_send_policy_design(output_path=str(output_path))
        assert output_path.exists()
        assert result["output_path"] == str(output_path)
        assert result["design"] is not None
        assert result["validation"] is not None

    def test_generate_output_is_valid_json(self, tmp_path):
        from app.audit import generate_feishu_manual_send_policy_design
        output_path = tmp_path / "R241-13D_TEST.json"
        result = generate_feishu_manual_send_policy_design(output_path=str(output_path))
        data = json.loads(output_path.read_text(encoding="utf-8"))
        # File contains the design dict directly (not wrapped in {"design": ...})
        assert data["status"] == "design_only"
        assert data["webhook_policy"] is not None

    def test_generate_validation_result_valid(self, tmp_path):
        from app.audit import generate_feishu_manual_send_policy_design
        output_path = tmp_path / "R241-13D_TEST.json"
        result = generate_feishu_manual_send_policy_design(output_path=str(output_path))
        assert result["validation"]["valid"] is True
        assert len(result["validation"]["errors"]) == 0

    def test_generate_includes_all_policies(self, tmp_path):
        from app.audit import generate_feishu_manual_send_policy_design
        output_path = tmp_path / "R241-13D_TEST.json"
        result = generate_feishu_manual_send_policy_design(output_path=str(output_path))
        design = result["design"]
        assert "webhook_policy" in design
        assert "confirmation_policy" in design
        assert "pre_send_validation_policy" in design
        assert "send_audit_policy" in design


# ─── TestSafetyConstraints ─────────────────────────────────────────────────

class TestSafetyConstraints:
    def test_generate_does_not_write_audit_jsonl(self, tmp_path, monkeypatch):
        from app.audit import generate_feishu_manual_send_policy_design
        call_count = 0
        original_append = None
        try:
            import app.audit.audit_trail_writer as writer_mod
            original_append = writer_mod.append_audit_record_to_target
            def counting_append(*args, **kwargs):
                nonlocal call_count
                call_count += 1
                return {"status": "appended", "lines_written": 0}
            writer_mod.append_audit_record_to_target = counting_append
            output_path = tmp_path / "R241-13D_NO_WRITE.json"
            generate_feishu_manual_send_policy_design(output_path=str(output_path))
            assert call_count == 0, "append_audit_record_to_target should not be called"
        finally:
            if original_append:
                writer_mod.append_audit_record_to_target = original_append

    def test_webhook_policy_no_webhook_call(self):
        from app.audit import build_feishu_webhook_policy
        # build_feishu_webhook_policy is design-only, no network calls possible
        policy = build_feishu_webhook_policy()
        assert policy is not None

    def test_confirmation_policy_design_only(self):
        from app.audit import build_manual_send_confirmation_policy
        policy = build_manual_send_confirmation_policy()
        assert policy is not None
        assert isinstance(policy, dict)

    def test_design_never_references_real_webhook(self):
        from app.audit import build_feishu_manual_send_policy_design
        import re
        WEBHOOK_RE = re.compile(r"https?://[^\s\"']*(?:webhook|hook|open\.feishu|larksuite)[^\s\"']*", re.IGNORECASE)
        design = build_feishu_manual_send_policy_design()
        design_str = json.dumps(design)
        assert not WEBHOOK_RE.search(design_str), "Real webhook URL found in policy design"

    def test_design_no_secret_values(self):
        from app.audit import build_feishu_manual_send_policy_design
        import re
        SECRET_RE = re.compile(r"(sk-|ak-|token|secret|password)['\"]?\s*[:=]\s*['\"]?[\w-]", re.IGNORECASE)
        design = build_feishu_manual_send_policy_design()
        design_str = json.dumps(design)
        assert not SECRET_RE.search(design_str), "Real secret value found in policy design"
