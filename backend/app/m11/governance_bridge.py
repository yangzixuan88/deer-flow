"""
M11 Governance Bridge — R17-R19 TypeScript Governance Engine Integration
========================================================================
Purpose: Connect the TypeScript governance/cognition/doctrine layers (R17-R19)
         to the actual deerflow Python runtime via subprocess invocation.

Architecture:
  Python Runtime → governance_bridge → tsx (TypeScript Engine) → JSON decisions
                         ↑                        ↓
                   State (bridge._decisions,    Governance
                   outcome_records.json)        Signals
                         ← ← ← ← ← ← ← ← ← ←

====================================================================
SYSTEM STATUS: CORE_ARCHITECTURE_FROZEN | CONTROLLED_EVOLUTION_ENABLED
====================================================================

CORE_IMMUTABLE (never change without人工审批):
  - governance_bridge as sole governance entry point
  - DECISION_MODE = FAIL_CLOSED (no PASS_THROUGH)
  - local anchoring to deerflow app/ directory
  - no floating new layers above R19
  - _STATE_FILE path and persistence contract
  - all R17-R19 layer class names and their governance boundaries

CONTROLLED_EVOLVABLE (can evolve within existing layer structure):
  - doctrine candidates (evolve_doctrine, new doctrine_id)
  - norm candidates (registerNorm, new norm patterns)
  - reputation scores (processReputationUpdate)
  - strategy patches (strategyLearner.applyPatch)
  - evaluation metrics (MissionEvaluationEngine.updateMetrics)
  - new playbook/pattern assets (AssetRegistry.promoteAsset)
  - new execution capabilities (SandboxExecutor extensions)
  - new learning signals (LearningSystem.captureExperience)

FORBIDDEN_EXPANSION (always blocked):
  - new parallel learning systems bypassing M08
  - new parallel asset systems bypassing M07
  - new runtime/governance/mission systems as standalone layers
  - any new "layer above R19" abstractions
  - shadow clones of existing system-of-record stores
"""

import subprocess
import shutil
import json
import os
import logging
import threading
import asyncio
import time
import copy
from typing import Dict, Any, Optional, List
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, asdict, field
from enum import Enum

logger = logging.getLogger("m11_governance_bridge")

# Path to the TypeScript governance engine entry point
_BACKEND_SRC = Path(__file__).parent.parent.parent / "src"
_GOVERNANCE_ENGINE_TS = _BACKEND_SRC / "domain" / "m11" / "_governance_subprocess_entry.mjs"

# State file for governance decisions (local anchor)
_STATE_FILE = Path(__file__).parent / "governance_state.json"

# Decision mode: FAIL_OPEN = pass through on errors, FAIL_CLOSED = block on errors
DECISION_MODE = "FAIL_CLOSED"

try:
    from backend.app.m11.truth_state_contract import (
        is_success_rate_eligible,
        map_legacy_outcome_to_state_events,
        map_legacy_outcome_to_truth_events,
        summarize_outcome_contract,
    )
    _TRUTH_STATE_IMPORT_ERROR = None
except Exception as exc:
    try:
        from app.m11.truth_state_contract import (
            is_success_rate_eligible,
            map_legacy_outcome_to_state_events,
            map_legacy_outcome_to_truth_events,
            summarize_outcome_contract,
        )
        _TRUTH_STATE_IMPORT_ERROR = None
    except Exception as fallback_exc:
        is_success_rate_eligible = None
        map_legacy_outcome_to_state_events = None
        map_legacy_outcome_to_truth_events = None
        summarize_outcome_contract = None
        _TRUTH_STATE_IMPORT_ERROR = f"{exc}; fallback={fallback_exc}"


_MAX_PROJECTION_LIMIT = 200
_SUPPORTED_METRIC_SCOPES = {
    "execution_success_rate",
    "tool_success_rate",
    "asset_quality_score",
    "rtcm_decision_quality",
}


def project_truth_state(record: Dict[str, Any]) -> Dict[str, Any]:
    """
    Read-only Truth/State projection for one legacy outcome record.

    This helper does not mutate the input record and does not persist projection
    results. Projection failures are returned as warnings so record_outcome()
    semantics remain unaffected.
    """
    result = {
        "truth_events": [],
        "state_events": [],
        "summary": {},
        "warnings": [],
    }
    if _TRUTH_STATE_IMPORT_ERROR:
        result["warnings"].append(f"truth_state_contract_import_failed:{_TRUTH_STATE_IMPORT_ERROR}")
        return result
    if not isinstance(record, dict):
        result["warnings"].append("invalid_record:not_dict")
        return result

    try:
        projection_record = copy.deepcopy(record)
        truth_events = map_legacy_outcome_to_truth_events(projection_record)
        state_events = map_legacy_outcome_to_state_events(projection_record)
        summary = summarize_outcome_contract(projection_record)
        result["truth_events"] = truth_events
        result["state_events"] = state_events
        result["summary"] = summary
        result["warnings"] = list(summary.get("warnings") or [])
        return result
    except Exception as exc:
        result["warnings"].append(f"projection_failed:{type(exc).__name__}:{exc}")
        return result


def project_recent_outcomes(limit: int = 20, outcome_type: Optional[str] = None) -> Dict[str, Any]:
    """
    Read-only projection over recent governance outcome records.

    Reads _STATE_FILE without saving or mutating governance_state.json.
    """
    result = {
        "total_scanned": 0,
        "projected_count": 0,
        "truth_events_count": 0,
        "state_events_count": 0,
        "summaries": [],
        "warnings": [],
    }
    records, warnings = _read_outcome_records_readonly()
    result["warnings"].extend(warnings)
    if warnings and not records:
        return result

    filtered = [
        record for record in records
        if not outcome_type or record.get("outcome_type") == outcome_type
    ]
    clamped_limit = _clamp_projection_limit(limit)
    selected = filtered[-clamped_limit:] if clamped_limit else []
    result["total_scanned"] = len(selected)

    for record in selected:
        projection = project_truth_state(record)
        if projection["truth_events"] or projection["state_events"] or projection["summary"]:
            result["projected_count"] += 1
        result["truth_events_count"] += len(projection["truth_events"])
        result["state_events_count"] += len(projection["state_events"])
        if projection["summary"]:
            result["summaries"].append(projection["summary"])
        result["warnings"].extend(projection["warnings"])

    return result


def get_success_rate_candidates(
    metric_scope: str = "execution_success_rate",
    limit: int = 100,
) -> Dict[str, Any]:
    """
    Return projected TruthEvents eligible for a metric scope.

    This does not calculate the final success rate. It only filters typed truth
    events so observation/governance/asset/RTCM signals cannot leak into the
    execution success-rate input set.
    """
    result = {
        "metric_scope": metric_scope,
        "eligible_count": 0,
        "ineligible_count": 0,
        "eligible_events": [],
        "excluded_reasons": {},
        "warnings": [],
    }
    if metric_scope not in _SUPPORTED_METRIC_SCOPES:
        result["warnings"].append(f"unsupported_metric_scope:{metric_scope}")
        return result

    records, warnings = _read_outcome_records_readonly()
    result["warnings"].extend(warnings)
    if warnings and not records:
        return result

    selected = records[-_clamp_projection_limit(limit):] if records else []
    for record in selected:
        projection = project_truth_state(record)
        result["warnings"].extend(projection["warnings"])
        for event in projection["truth_events"]:
            if is_success_rate_eligible and is_success_rate_eligible(event, metric_scope):
                result["eligible_events"].append(event)
            else:
                result["ineligible_count"] += 1
                reason = _exclusion_reason(event, metric_scope)
                result["excluded_reasons"][reason] = result["excluded_reasons"].get(reason, 0) + 1

    result["eligible_count"] = len(result["eligible_events"])
    return result


def _read_outcome_records_readonly() -> tuple[List[Dict[str, Any]], List[str]]:
    warnings: List[str] = []
    try:
        if not _STATE_FILE.exists():
            return [], [f"governance_state_missing:{_STATE_FILE}"]
        with open(_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as exc:
        return [], [f"governance_state_read_failed:{type(exc).__name__}:{exc}"]

    records = data.get("outcome_records") if isinstance(data, dict) else None
    if not isinstance(records, list):
        warnings.append("governance_state_malformed:outcome_records_not_list")
        return [], warnings
    return [record for record in records if isinstance(record, dict)], warnings


def _clamp_projection_limit(limit: int) -> int:
    try:
        parsed = int(limit)
    except (TypeError, ValueError):
        parsed = 20
    return max(0, min(parsed, _MAX_PROJECTION_LIMIT))


def _exclusion_reason(event: Dict[str, Any], metric_scope: str) -> str:
    truth_track = event.get("truth_track")
    truth_type = event.get("truth_type")
    if metric_scope == "execution_success_rate":
        if truth_track != "execution_truth":
            return f"not_execution_truth:{truth_track}"
        return f"not_execution_success_type:{truth_type}"
    return f"not_eligible:{truth_track}:{truth_type}"


class GovernanceDecision(Enum):
    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"
    VETO = "veto"
    MODIFY = "modify"


@dataclass
class GovernanceDecisionRecord:
    decision_id: str
    timestamp: str
    layer: str          # meta_governance | epistemic | stakeholder | foresight | reputation | norm | doctrine
    decision: str       # allow | block | escalate | veto | modify
    context: Dict[str, Any]
    reason: str
    blocking: bool     # whether this decision can halt execution
    applied: bool       # whether the decision was acted upon
    subprocess_result: Optional[Dict[str, Any]] = None


class GovernanceBridge:
    """
    Subprocess bridge to the TypeScript R17-R19 governance engine.
    Runs governance/cognition/doctrine decisions by invoking tsx on the
    TypeScript engine and parsing JSON responses.

    Decision mode: FAIL_CLOSED — when TS engine is unavailable or errors,
    governance defaults to BLOCK rather than allowing everything through.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock = threading.RLock()
        self._decisions: List[GovernanceDecisionRecord] = []
        self._outcome_records: List[Dict[str, Any]] = []
        # P0: Low-frequency critical outcomes — immediate save to prevent loss on restart
        self._KEY_OUTCOME_TYPES = {
            "nightly_evolution",
            "doctrine_drift_detected",
            "upgrade_center_execution",
            "upgrade_center_summary",
            "upgrade_queue_snapshot",
            "queue_health_signal",
            "asset_promotion",
            # R198: Feishu approval results — must persist immediately
            "upgrade_center_approval_result",
            # R207: execution_result — must persist immediately for candidate-level sample chain
            "upgrade_center_execution_result",
            # R212: sandbox_execution_result — must persist immediately for execution truth backflow
            "sandbox_execution_result",
        }
        # P2: Non-blocking outcome types — bypass _run_ts_governance() sync wait
        # These outcomes are logged locally and returned immediately without TS engine wait.
        self._NON_BLOCKING_OUTCOME_TYPES = {
            "nightly_evolution",
            "doctrine_drift_detected",
            "tool_execution",
            "tool_execution_uef",
            "upgrade_center_execution",
            "upgrade_center_summary",
            "upgrade_queue_snapshot",
            "queue_health_signal",
            "asset_promotion",
            # R198: Feishu approval results — write-only, no TS engine needed
            "upgrade_center_approval_result",
            # R207-C: execution_result — write-only backflow record, no TS engine needed.
            # Adding to NON_BLOCKING fixes the Windows Python 3.13 subprocess.run hang
            # (second invocation of npx tsx blocks indefinitely on stdin).
            # This is architecturally correct: backflow records do not need governance engine.
            "upgrade_center_execution_result",
            # R212: sandbox_execution_result — write-only, no TS engine needed.
            "sandbox_execution_result",
        }
        self._health_status = "not_initialized"
        self._ts_available = False
        self._process_pool: Optional[subprocess.Popen] = None
        self._last_check_time = 0
        self._check_interval = 60  # seconds between re-checks
        self._load_state()
        self._check_ts_engine()

    # ─────────────────────────────────────────
    # State persistence
    # ─────────────────────────────────────────

    def _load_state(self):
        """Load persisted governance decisions from state file."""
        try:
            if _STATE_FILE.exists():
                with open(_STATE_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self._decisions = [
                        GovernanceDecisionRecord(**r) for r in data.get('decisions', [])
                    ][-100:]  # keep last 100
                    self._outcome_records = data.get('outcome_records', [])[-100:]
                    logger.info(f"[M11-GB] Loaded {len(self._decisions)} governance decisions from state")
        except Exception as e:
            logger.warning(f"[M11-GB] Could not load governance state: {e}")

    def _save_state(self):
        """Persist governance decisions to state file."""
        try:
            data = {
                'decisions': [asdict(d) for d in self._decisions[-100:]],
                'outcome_records': self._outcome_records[-100:],
                'last_updated': datetime.now().isoformat(),
            }
            with open(_STATE_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"[M11-GB] Failed to save governance state: {e}")

    def _add_decision(self, record: GovernanceDecisionRecord):
        """Add a governance decision to the in-memory and persisted log."""
        with self._lock:
            record.applied = True
            self._decisions.append(record)
            # Persist every 10 decisions
            if len(self._decisions) % 10 == 0:
                self._save_state()

    # ─────────────────────────────────────────
    # Engine health check
    # ─────────────────────────────────────────


    def _resolve_npx_path(self) -> str:
        npx_path = shutil.which("npx") or shutil.which("npx.cmd")
        if not npx_path:
            raise FileNotFoundError("npx not found in PATH")
        return npx_path

    def _recheck_engine(self):
        """Recheck engine availability periodically (every _check_interval seconds)."""
        now = time.time()
        if now - self._last_check_time > self._check_interval:
            self._last_check_time = now
            self._check_ts_engine()

    def _check_ts_engine(self):
        """Verify tsx and TypeScript engine are available."""
        if not _GOVERNANCE_ENGINE_TS.exists():
            logger.warning(
                f"[M11-GB] TypeScript governance engine not found at {_GOVERNANCE_ENGINE_TS}. "
                "Governance bridge operating in FAIL_CLOSED mode."
            )
            self._health_status = "engine_missing"
            self._ts_available = False
            return

        try:
            npx_path = self._resolve_npx_path()
            result = subprocess.run(
                f'"{npx_path}" tsx --version',
                capture_output=True,
                text=True,
                timeout=10,
                cwd=str(_BACKEND_SRC.parent),
                shell=True,
            )
            if result.returncode == 0:
                self._health_status = "ready"
                self._ts_available = True
                logger.info(f"[M11-GB] TypeScript governance engine ready: {result.stdout.strip()}")
            else:
                self._health_status = "tsx_missing"
                self._ts_available = False
                logger.warning("[M11-GB] tsx not available. Operating in FAIL_CLOSED mode.")
        except FileNotFoundError:
            self._health_status = "tsx_missing"
            self._ts_available = False
            logger.warning("[M11-GB] npx/tsx not found. Operating in FAIL_CLOSED mode.")
        except Exception as e:
            self._health_status = f"error: {e}"
            self._ts_available = False
            logger.warning(f"[M11-GB] Error checking TypeScript engine: {e}")


    def _run_ts_governance(
        self,
        command: str,
        payload: Dict[str, Any],
        timeout: float = 5.0
    ) -> Optional[Dict[str, Any]]:
        """
        Run a governance command via tsx subprocess.
        Uses FAIL_CLOSED mode: returns None only when engine is truly unavailable,
        and the caller should treat None as BLOCK.
        """
        if not self.enabled:
            return None

        self._recheck_engine()

        if not self._ts_available:
            return None  # FAIL_CLOSED: unavailable = blocked

        if not _GOVERNANCE_ENGINE_TS.exists():
            return None

        try:
            input_json = json.dumps({
                "command": command,
                "payload": payload,
                "timestamp": datetime.now().isoformat(),
            }, ensure_ascii=False)

            npx_path = self._resolve_npx_path()
            result = subprocess.run(
                f'"{npx_path}" tsx "{_GOVERNANCE_ENGINE_TS}"',
                input=input_json,
                capture_output=True,
                text=True,
                timeout=max(timeout, 10.0),
                cwd=str(_BACKEND_SRC.parent),
                shell=True,
                encoding='utf-8',
                errors='replace',
            )

            if result.returncode == 0 and result.stdout.strip():
                try:
                    parsed = json.loads(result.stdout.strip())
                    if parsed.get('status') == 'ok':
                        return parsed.get('result')
                    else:
                        logger.warning(f"[M11-GB] TS engine error: {parsed.get('message')}")
                        return None  # FAIL_CLOSED on engine error
                except json.JSONDecodeError:
                    logger.warning(f"[M11-GB] Invalid JSON from TS engine")
                    return None
            else:
                logger.warning(f"[M11-GB] tsx governance returned {result.returncode}: {result.stderr[:100]}")
                return None

        except subprocess.TimeoutExpired:
            logger.warning(f"[M11-GB] Governance engine timeout ({timeout}s) for command {command}")
            return None  # FAIL_CLOSED on timeout
        except Exception as e:
            logger.error(f"[M11-GB] Governance engine error: {e}")
            return None

    # ─────────────────────────────────────────
    # Decision recording helpers
    # ─────────────────────────────────────────

    def _record(
        self,
        layer: str,
        raw_result: Optional[Dict[str, Any]],
        context: Dict[str, Any],
        default_decision: str,
        blocking: bool = False
    ) -> GovernanceDecisionRecord:
        # R206-A FIX: Changed from async def to def.
        # _record() does NOT perform any I/O — it only creates a GovernanceDecisionRecord
        # in memory and calls _add_decision(). Making it async was a bug: all callers wrote
        # `record = self._record(...)` without `await`, so the function body never executed
        # and _decisions never grew. Synchronous def fixes this — all callers now work correctly.
        """Record a governance decision."""
        decision_id = f"gov_{len(self._decisions) + 1}_{int(time.time() * 1000)}"

        if raw_result is None:
            # FAIL_CLOSED: no result means block
            record = GovernanceDecisionRecord(
                decision_id=decision_id,
                timestamp=datetime.now().isoformat(),
                layer=layer,
                decision="BLOCK",
                context=context,
                reason="engine_unavailable_or_timeout",
                blocking=True,
                applied=False,
                subprocess_result=None
            )
        else:
            # Extract decision from subprocess result
            allowed = raw_result.get('allowed', True)
            escalated = raw_result.get('escalated', False)
            suppressed = raw_result.get('suppressed', False)

            if suppressed:
                decision = "VETO"
                reason = "source_suppressed"
                blocking = True
            elif escalated:
                decision = "ESCALATE"
                reason = raw_result.get('reason', 'escalation_required')
                blocking = False
            elif not allowed:
                decision = "BLOCK"
                reason = raw_result.get('reason', 'not_allowed')
                blocking = True
            else:
                decision = "ALLOW"
                reason = raw_result.get('reason', 'approved')
                blocking = False

            record = GovernanceDecisionRecord(
                decision_id=decision_id,
                timestamp=datetime.now().isoformat(),
                layer=layer,
                decision=decision,
                context=context,
                reason=reason,
                blocking=blocking,
                applied=False,
                subprocess_result=raw_result
            )

        self._add_decision(record)
        return record

    # ─────────────────────────────────────────
    # R17: Meta-Governance integration
    # ─────────────────────────────────────────

    async def check_meta_governance(
        self,
        decision_context: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Check if a decision passes the meta-governance/constitutional gate.
        This is a SYNCHRONOUS check used in the hot path — returns immediately.
        BLOCK decisions should prevent the operation from proceeding.
        """
        payload = {"context": decision_context}
        raw = self._run_ts_governance("meta_governance_check", payload, timeout=3.0)

        # FAIL_CLOSED for high-risk decisions
        ctx = decision_context or {}
        risk = ctx.get('risk_level', 'medium')
        is_high_risk = risk in ('high', 'critical')

        if raw is None and is_high_risk:
            # Engine unavailable for high-risk = block
            record = self._record("meta_governance", None, decision_context, "BLOCK", blocking=True)
            logger.warning(f"[M11-GB] HIGH-RISK decision BLOCKED (engine unavailable): {ctx.get('description', '')}")
            return record

        record = self._record("meta_governance", raw, decision_context, "ALLOW", blocking=is_high_risk)

        if record.decision == "BLOCK":
            logger.warning(f"[M11-GB] Meta-governance BLOCKED: {record.reason} | context={ctx.get('description', '')}")
        else:
            logger.info(f"[M11-GB] Meta-governance ALLOWED: {ctx.get('description', '')}")

        return record

    async def apply_rule_patch(
        self,
        patch_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """Submit a rule patch for meta-governance review."""
        raw = self._run_ts_governance("apply_rule_patch", patch_data, timeout=5.0)
        record = self._record("meta_governance", raw, {"patch": patch_data}, "BLOCK", blocking=True)
        self._save_state()
        return record

    async def record_outcome(
        self,
        outcome_type: str,
        actual_result: Any,
        predicted_result: Any,
        context: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Record an actual outcome for backflow into governance layers.
        This is how truth/conflict/reputation/norm systems learn from reality.
        """
        # R240-4: Extract optional context_id from context.context_envelope
        ctx_envelope = context.get("context_envelope") if context else None
        context_id = None
        if ctx_envelope and isinstance(ctx_envelope, dict):
            context_id = ctx_envelope.get("context_id")
        if context_id:
            logger.info(f"[R240-4] record_outcome context_id=%s outcome_type=%s", context_id[:8], outcome_type)

        outcome_record = {
            "outcome_type": outcome_type,
            "actual": actual_result,
            "predicted": predicted_result,
            "context": context,
            "context_id": context_id,  # R240-4: optional linkage to ContextEnvelope
            "timestamp": datetime.now().isoformat(),
        }
        with self._lock:
            self._outcome_records.append(outcome_record)
            # P0 fix: immediate save for critical low-frequency outcomes
            if outcome_type in self._KEY_OUTCOME_TYPES or len(self._outcome_records) % 10 == 0:
                self._save_state()

        # P2: Non-blocking outcomes — return immediately without waiting for TS engine
        if outcome_type in self._NON_BLOCKING_OUTCOME_TYPES:
            # R206-A FIX: outcome_record has two levels:
            #   outer: { outcome_type, actual, predicted, context: {...governance...}, timestamp }
            #   inner context: { asset_id, asset_name, asset_category, risk_level, source }
            # When TS engine is unavailable, _record() receives governance_context which needs
            # BOTH outcome_type (from outer) AND governance fields (from inner context).
            # Merge: flat governance_context + outcome_type at top.
            # R220 FIX: outcome_record 顶层有 actual_result/predicted_result，
            # 但旧代码只传了 inner context（无 actual/predicted）给 _record()。
            # R218 配对分析需要 decisions[] 有 predicted 值才能计算 mean_error，
            # 因此把 actual/predicted 注入 governance_context 供 _record() 使用。
            governance_context = dict(outcome_record.get("context") or {})
            governance_context["outcome_type"] = outcome_type
            governance_context["actual"] = outcome_record.get("actual")   # R220 FIX: keys are actual/predicted (not actual_result/predicted_result)
            governance_context["predicted"] = outcome_record.get("predicted")
            record = self._record("outcome_record", {}, governance_context, "ALLOW", blocking=False)
            logger.info(f"[M11-GB] Outcome recorded (non-blocking): {outcome_type}")
            return record

        # Blocking path: wait for TS governance engine
        raw = self._run_ts_governance("record_outcome", outcome_record, timeout=3.0)

        record = self._record("outcome_record", raw, outcome_record, "ALLOW", blocking=False)
        logger.info(f"[M11-GB] Outcome recorded: {outcome_type} | actual={actual_result} predicted={predicted_result}")
        return record

    # ─────────────────────────────────────────
    # R18: Epistemic/Cognition integration
    # ─────────────────────────────────────────

    async def check_epistemic_conflict(
        self,
        truth_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Check if a truth claim has conflicts and get resolution guidance.
        """
        raw = self._run_ts_governance("epistemic_conflict_check", truth_data, timeout=3.0)
        record = self._record("epistemic", raw, truth_data, "ALLOW", blocking=False)

        if record.decision == "BLOCK":
            logger.warning(f"[M11-GB] Epistemic conflict BLOCKED: {record.reason}")
        return record

    async def negotiate_stakeholders(
        self,
        issue_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Run stakeholder negotiation for a decision with multiple interests.
        """
        raw = self._run_ts_governance("stakeholder_negotiation", issue_data, timeout=5.0)
        record = self._record("stakeholder", raw, issue_data, "ALLOW", blocking=False)

        if record.decision == "ESCALATE":
            logger.warning(f"[M11-GB] Stakeholder negotiation ESCALATED: {record.reason}")
        elif record.decision == "BLOCK":
            logger.warning(f"[M11-GB] Stakeholder negotiation BLOCKED: {record.reason}")
        return record

    async def check_strategic_foresight(
        self,
        scenario_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Analyze a decision scenario for future risks and opportunities.
        """
        raw = self._run_ts_governance("strategic_foresight", scenario_data, timeout=5.0)
        record = self._record("foresight", raw, scenario_data, "ALLOW", blocking=False)

        if record.decision == "BLOCK":
            logger.warning(f"[M11-GB] Strategic foresight BLOCKED: {record.reason}")
        return record

    # ─────────────────────────────────────────
    # R19: Identity/Reputation/Norm/Doctrine integration
    # ─────────────────────────────────────────

    async def check_reputation_gate(
        self,
        source_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Check if a source's reputation allows its input to be weighted.
        BLOCK/suppressed sources should be excluded from decision-making.
        """
        raw = self._run_ts_governance("reputation_gate", source_data, timeout=3.0)
        record = self._record("reputation", raw, source_data, "ALLOW", blocking=False)

        if record.decision == "VETO":
            logger.warning(f"[M11-GB] Reputation VETO: source={source_data.get('source_id')} suppressed")
        return record

    async def check_norm_compliance(
        self,
        norm_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Check if a behavior complies with active norms.
        """
        raw = self._run_ts_governance("norm_compliance", norm_data, timeout=3.0)
        record = self._record("norm", raw, norm_data, "ALLOW", blocking=False)

        if record.decision == "BLOCK":
            logger.warning(f"[M11-GB] Norm violation detected: {record.reason}")
        return record

    async def check_doctrine_drift(
        self,
        doctrine_data: Optional[Dict[str, Any]] = None
    ) -> GovernanceDecisionRecord:
        """
        Check if any active doctrines are drifting (effectiveness declining).
        This is typically called by the daemon tick, not in the hot path.
        """
        raw = self._run_ts_governance(
            "doctrine_drift_check",
            doctrine_data or {},
            timeout=10.0
        )
        record = self._record("doctrine", raw, doctrine_data or {}, "ALLOW", blocking=False)

        if raw and raw.get('has_drift'):
            signals = raw.get('signals', [])
            logger.warning(f"[M11-GB] Doctrine drift detected: {len(signals)} signals")
        return record

    async def evolve_doctrine(
        self,
        doctrine_data: Dict[str, Any]
    ) -> GovernanceDecisionRecord:
        """
        Advance a doctrine through its lifecycle (candidate→reviewing→accepted→active).
        """
        raw = self._run_ts_governance("evolve_doctrine", doctrine_data, timeout=5.0)
        record = self._record("doctrine", raw, doctrine_data, "ALLOW", blocking=False)
        self._save_state()
        return record

    # ─────────────────────────────────────────
    # Query interface
    # ─────────────────────────────────────────

    def get_last_decisions(self, layer: Optional[str] = None, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent governance decisions."""
        with self._lock:
            decisions = self._decisions[-limit:]
            if layer:
                decisions = [d for d in decisions if d.layer == layer]
            return [asdict(d) for d in decisions]

    def get_outcome_records(
        self,
        limit: int = 50,
        outcome_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Get recent outcome records, optionally filtered by outcome_type.

        ROUND 11: Added outcome_type filter for Upgrade Center result observability.
        """
        with self._lock:
            records = list(self._outcome_records[-limit:])
            if outcome_type:
                records = [r for r in records if r.get("outcome_type") == outcome_type]
            return records

    def get_last_result(self, layer: str) -> Optional[Dict[str, Any]]:
        """Get the last governance result for a layer."""
        with self._lock:
            for d in reversed(self._decisions):
                if d.layer == layer:
                    return asdict(d)
        return None

    def get_health_status(self) -> str:
        """Get the health status of the governance bridge."""
        self._recheck_engine()
        return self._health_status

    def get_state_anchors(self) -> Dict[str, str]:
        """Return local state anchor paths used by this bridge."""
        return {
            "governance_state_file": str(_STATE_FILE),
            "meta_governance": "governance_state.governance_decisions",
            "outcome_records": "governance_state.outcome_records",
            "epistemic": "governance_state.epistemic_trace",
            "stakeholder": "governance_state.negotiation_trace",
            "foresight": "governance_state.foresight_trace",
            "reputation": "governance_state.reputation_trace",
            "norm": "governance_state.norm_trace",
            "doctrine": "governance_state.doctrine_trace",
        }

    # ─────────────────────────────────────────
    # Layer Cap Enforcement — Architecture Freeze
    # R19 is the TOPMOST layer. No layers above R19.
    # This is the constitutional guarantee that the system will not grow
    # unbounded governance abstractions above the established ceiling.
    # ─────────────────────────────────────────

    MAX_LAYER_ROUND = 19

    def is_layer_addition_allowed(self, new_layer_name: str) -> tuple[bool, str]:
        """
        Check if a new layer addition is allowed under the architecture cap.

        Returns (allowed, reason):
          - (True, "allowed")                     → CONTROLLED_EVOLVABLE within existing layers
          - (False, "FORBIDDEN_EXPANSION: R19_cap") → new layer above R19 ceiling

        This method enforces the architecture cap from the Python side so that
        any attempt to grow the system beyond R19 is blocked at the governance
        entry point.
        """
        import re
        # Extract round number from layer name (e.g. "meta_governance_round17" → 17)
        match = re.search(r'_round(\d+)', new_layer_name)
        if match:
            round_num = int(match.group(1))
            if round_num > self.MAX_LAYER_ROUND:
                logger.warning(
                    f"[M11-GB] LAYER CAP BLOCKED: {new_layer_name} is R{round_num} "
                    f"— exceeds R{self.MAX_LAYER_ROUND} ceiling. "
                    f"FORBIDDEN_EXPANSION: new_layer_above_r19"
                )
                return (False, f"FORBIDDEN_EXPANSION: R{round_num} > R{self.MAX_LAYER_ROUND} cap")
            elif round_num <= self.MAX_LAYER_ROUND:
                return (True, f"allowed (R{round_num} within cap)")

        # New layers without round suffix — allow within existing layer structure
        # but flag for governance review
        logger.info(f"[M11-GB] New layer '{new_layer_name}' — permitting for governance review")
        return (True, "allowed for governance review")

    def get_evolution_status(self) -> Dict[str, Any]:
        """
        Return the current system evolution status.
        Used by health endpoints and governance dashboards.
        """
        # Import here to avoid circular imports at module load time
        try:
            from app.m11.external_backend_selector import get_backend_manifest
            external_backends = get_backend_manifest()
        except Exception as e:
            logger.warning(f"[M11-GB] Could not load external backend manifest: {e}")
            external_backends = {"error": str(e), "backends": []}

        # Claude Code primary operator status
        try:
            from app.m11.claude_code_router import get_coproc_status_summary
            coproc_status = get_coproc_status_summary()
        except Exception as e:
            logger.warning(f"[M11-GB] Could not load coprocessor status: {e}")
            coproc_status = {"error": str(e)}

        return {
            "status": "CORE_ARCHITECTURE_FROZEN",
            "evolution": "CONTROLLED_EVOLUTION_ENABLED",
            "layer_cap": f"R{self.MAX_LAYER_ROUND}",
            "immutable_core": "governance_bridge | FAIL_CLOSED | no_floating_layers | local_anchors",
            "evolvable_surface": "doctrine | norm | reputation | strategy | evaluation | playbook | execution_capability | external_backends | coprocessors_for_claude_code",
            "forbidden": "no_parallel_systems | no_bypass_routes | no_new_layers_above_R19",
            "external_backends": external_backends,
            "primary_operator": {
                "name": "Claude Code CLI",
                "roles": ["primary_operator", "general_problem_solver", "engineering_executor",
                          "capability_orchestrator", "fallback_brain", "capability_builder"],
                "routing_policy": "claude_code_primary | coprocessors_subordinate | no_direct_bypass",
                "coprocessor_status": coproc_status,
            },
        }

    def get_external_capability_registry(self) -> Dict[str, Any]:
        """
        Return the full external capability registry from claude_code_router.
        Replaced DEPRECATED external_backend_selector with claude_code_router.get_coproc_status_summary().
        """
        try:
            from app.m11.claude_code_router import get_coproc_status_summary
            return get_coproc_status_summary()
        except Exception as e:
            logger.warning(f"[M11-GB] Could not load external capability registry: {e}")
            return {"error": str(e)}

    def shutdown(self):
        """Persist state on shutdown."""
        self._save_state()
        logger.info("[M11-GB] Governance bridge shutdown, state persisted.")


# Singleton instance
governance_bridge = GovernanceBridge()
