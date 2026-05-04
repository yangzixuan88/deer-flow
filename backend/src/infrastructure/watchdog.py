import json
import time
import datetime
import subprocess
import sys
import asyncio
import os
from pathlib import Path

# OpenClaw Architecture 2.0 Watchdog Sentinel
# Purpose: Maintain a 24/7 persistent heartbeat for the AAL sovereignty.
# Aligns with "Non-intrusive 24/7 Ops" rule.

BOULDER_PATH = Path(__file__).parent / "boulder.json"
DEERFLOW_ROOT = Path(__file__).resolve().parent.parent.parent  # deerflow root (E:/OpenClaw-Base/deerflow/)
UPGRADE_CENTER_RUNNER = DEERFLOW_ROOT / "backend" / "src" / "upgrade_center" / "upgrade_center_runner.ts"
RESULT_PATH = Path(__file__).parent / "upgrade_center_result.json"
TASK_QUEUE_PATH = Path(__file__).parent / "task_queue.json"
# queue_manager.ts writes to the project-local .deerflow/upgrade-center/state/.
# This must match that path so _check_experiment_queue() can read experiment_queue.json.
DEERFLOW_RUNTIME_ROOT = Path(os.environ.get("DEERFLOW_RUNTIME_ROOT", str(DEERFLOW_ROOT / ".deerflow"))).resolve()
UPGRADE_CENTER_STATE_DIR = DEERFLOW_RUNTIME_ROOT / "upgrade-center" / "state"

# ─────────────────────────────────────────────────────────────────────────────
# Governance Bridge Import (M11 R17-R19)
# Ensures watchdog can backflow upgrade results to the governance system.
# Only imports the Python-side bridge (no TS subprocess is spawned here).
# ─────────────────────────────────────────────────────────────────────────────
_GOVERNANCE_BRIDGE_LOADED = False
_governance_bridge = None

def _ensure_governance_bridge():
    """Lazily import the governance_bridge singleton to avoid init-order issues."""
    global _governance_bridge, _GOVERNANCE_BRIDGE_LOADED
    if _GOVERNANCE_BRIDGE_LOADED:
        return _governance_bridge
    try:
        # governance_bridge lives at backend/app/m11/governance_bridge.py
        # Add backend/ to sys.path so 'from app.m11.governance_bridge import ...' works
        backend_root = str(DEERFLOW_ROOT / "backend")
        if backend_root not in sys.path:
            sys.path.insert(0, backend_root)
        from app.m11.governance_bridge import governance_bridge as _gb
        _governance_bridge = _gb
        _GOVERNANCE_BRIDGE_LOADED = True
        print("[Watchdog] Governance bridge loaded for backflow.")
        return _governance_bridge
    except Exception as e:
        print(f"[Watchdog] Could not load governance_bridge: {e}")
        return None

def _record_upgrade_outcome(executed_at: str, success: bool, result_record: dict = None, execution_time_s: float = 0.0):
    """
    Backflow upgrade center execution result to governance_bridge.

    ROUND 6 CLOSED LOOP:
    watchdog (Python) → npx tsx UC runner → U0-U8 pipeline executes
      → upgrade_center_result.json written
      → watchdog reads result.json → HERE (Python main chain)
      → governance_bridge.record_outcome() records to governance_state.json
      → /health/governance API exposes outcome_records (observable consumer)

    ROUND 10 ENHANCEMENT:
    Now emits TWO additional outcome types for main-chain structured consumption:
      - upgrade_center_summary: key metrics + top approval candidates
      - upgrade_queue_snapshot: Top-N experiment queue candidates
    These go through the same governance_bridge.record_outcome() channel.
    """
    try:
        import asyncio
        import logging
        logger = logging.getLogger("watchdog_upgrade_backflow")

        report = result_record.get("report") if result_record else None

        # Build minimum context from upgrade result (existing behavior)
        context = {
            "source_id": "upgrade_center_watchdog",
            "task_goal": "Upgrade Center U0-U8 nightly execution",
            "tool_calls": 0,
            "total_tokens": 0,
            "total_duration_ms": int(execution_time_s * 1000),
            "executed_at": executed_at,
            "success": success,
        }

        if report:
            context.update({
                "demands_scanned": report.get("summary", {}).get("demands_scanned", 0),
                "experiment_pool_size": report.get("summary", {}).get("experiment_pool", 0),
                "observation_pool_size": report.get("summary", {}).get("observation_pool", 0),
                "pending_approvals": report.get("pending_approvals", 0),
                "stages_completed": report.get("stages_completed", []),
                "candidates_for_approval": len(report.get("candidates_for_approval", [])),
                "outcome_source": "upgrade_center",
            })
        else:
            context.update({
                "demands_scanned": 0,
                "experiment_pool_size": 0,
                "pending_approvals": 0,
                "outcome_source": "upgrade_center",
            })

        gb = _ensure_governance_bridge()
        if gb is None:
            print("[Watchdog] Governance bridge unavailable — skipping backflow.")
            return

        # Call record_outcome (async) — use asyncio.run for synchronous context
        async def _do_record():
            # Existing: upgrade_center_execution outcome
            await gb.record_outcome(
                outcome_type="upgrade_center_execution",
                actual_result=1.0 if success else 0.0,
                predicted_result=0.9,
                context=context,
            )

            # ROUND 10: upgrade_center_summary — main-chain structured summary
            summary = result_record.get("upgrade_center_summary") if result_record else None
            if summary:
                await gb.record_outcome(
                    outcome_type="upgrade_center_summary",
                    actual_result=1.0 if success else 0.0,
                    predicted_result=0.9,
                    context={
                        "source_id": "upgrade_center_watchdog",
                        "demands_scanned": summary.get("demands_scanned", 0),
                        "experiment_pool_size": summary.get("experiment_pool_size", 0),
                        "observation_pool_size": summary.get("observation_pool_size", 0),
                        "pending_approvals": summary.get("pending_approvals", 0),
                        "top_candidates_for_approval": summary.get("candidates_for_approval", []),
                        "executed_at": executed_at,
                        "success": success,
                    },
                )
            else:
                # degraded mode: record empty summary marker
                await gb.record_outcome(
                    outcome_type="upgrade_center_summary",
                    actual_result=0.0,
                    predicted_result=0.9,
                    context={
                        "source_id": "upgrade_center_watchdog",
                        "state": "degraded",
                        "reason": "upgrade_center_summary not in result_record",
                        "executed_at": executed_at,
                    },
                )

            # ROUND 10: upgrade_queue_snapshot — main-chain Top-N queue candidates
            queue_snapshot = result_record.get("upgrade_queue_snapshot") if result_record else None
            if queue_snapshot:
                await gb.record_outcome(
                    outcome_type="upgrade_queue_snapshot",
                    actual_result=1.0 if success else 0.0,
                    predicted_result=0.9,
                    context={
                        "source_id": "upgrade_center_watchdog",
                        "top_n_count": len(queue_snapshot),
                        "candidates": queue_snapshot,
                        "executed_at": executed_at,
                        "success": success,
                    },
                )
            else:
                # degraded mode: record empty queue marker
                await gb.record_outcome(
                    outcome_type="upgrade_queue_snapshot",
                    actual_result=0.0,
                    predicted_result=0.9,
                    context={
                        "source_id": "upgrade_center_watchdog",
                        "state": "degraded",
                        "reason": "upgrade_queue_snapshot not in result_record",
                        "executed_at": executed_at,
                    },
                )

        asyncio.run(_do_record())
        print(f"[Watchdog] Upgrade outcome backflowed to governance_bridge: success={success}")
        if report:
            print(f"[Watchdog]   demands={context['demands_scanned']} "
                  f"experiment_pool={context['experiment_pool_size']} "
                  f"pending_approvals={context['pending_approvals']}")

    except Exception as e:
        # Non-fatal: backflow failure should not break the watchdog loop
        print(f"[Watchdog] WARNING: Failed to backflow upgrade outcome to governance: {e}")

def _check_experiment_queue():
    """
    P1: Queue-awareness — read experiment_queue.json and backflow health signal to governance.

    This is a READ-ONLY operation that does NOT modify experiment_queue.json or queue state.
    It only reads queue metadata and emits a governance signal so the Python main chain
    can observe queue health without being coupled to UC execution semantics.

    Runs on every watchdog tick (not just UC execution cycles) so that empty queue,
    stale backlog, and other queue health issues are always observable.
    """
    import time

    EQ_PATH = UPGRADE_CENTER_STATE_DIR / "experiment_queue.json"
    if not EQ_PATH.exists():
        return  # Queue file not yet created — UC hasn't run, nothing to observe

    try:
        import json
        with open(EQ_PATH, "r", encoding="utf-8") as f:
            queue = json.load(f)

        tasks = queue.get("experiment_tasks", [])
        pending = [t for t in tasks if t.get("status") == "pending"]
        pending_verification = queue.get("pending_verification", [])

        # Calculate staleness
        now_ts = time.time()
        stale_count = 0
        oldest_age_seconds = None
        if pending:
            # Get mtime of queue file as proxy for oldest task age (conservative)
            file_mtime = EQ_PATH.stat().st_mtime
            oldest_age_seconds = now_ts - file_mtime

            # Stale = pending for more than 24 hours
            stale_threshold = 24 * 3600
            stale_count = sum(1 for t in pending if (now_ts - EQ_PATH.stat().st_mtime) > stale_threshold)

        # Determine status label
        if not pending and not pending_verification:
            status = "empty"
        elif stale_count > 0:
            status = "stale"
        elif len(pending) > 5:
            status = "backlog"
        else:
            status = "healthy"

        context = {
            "source_id": "watchdog_queue_observer",
            "queue_date": queue.get("date", "unknown"),
            "pending_count": len(pending),
            "pending_verification_count": len(pending_verification),
            "stale_pending_count": stale_count,
            "oldest_task_age_seconds": int(oldest_age_seconds) if oldest_age_seconds else 0,
            "status": status,
            "snapshot_top_tasks": [
                {"candidate_id": t.get("candidate_id", "unknown"), "status": t.get("status", "unknown")}
                for t in pending[:3]
            ],
        }

        gb = _ensure_governance_bridge()
        if gb:
            import asyncio
            async def _do_queue_record():
                await gb.record_outcome(
                    outcome_type="queue_health_signal",
                    actual_result=1.0,
                    predicted_result=0.9,
                    context=context,
                )
            asyncio.run(_do_queue_record())
            print(f"[Watchdog] Queue health signal backflowed: status={status} pending={len(pending)} stale={stale_count}")
    except Exception as e:
        print(f"[Watchdog] WARNING: Failed to check experiment_queue: {e}")

# Day/Night mode hour ranges
DAY_MODE_START = 6  # 06:00 AM
DAY_MODE_END = 22   # 10:00 PM
NIGHTLY_REVIEW_HOUR = 2  # 02:00 AM trigger for nightly distillation
NIGHTLY_UPGRADE_TRIGGER_HOUR = 3  # 03:00 AM trigger for upgrade center

def is_daytime():
    """Check if current hour is within day mode (06:00-22:00)."""
    current_hour = datetime.datetime.now().hour
    return DAY_MODE_START <= current_hour < DAY_MODE_END

def get_interval_for_mode():
    """Get heartbeat interval based on day/night mode.
    Day mode (06:00-22:00): 5 minutes (high frequency)
    Night mode (22:00-06:00): 30 minutes (low frequency)
    """
    return 5 if is_daytime() else 30

def should_trigger_nightly_review():
    """Check if it's time to trigger the nightly review (02:00 AM).
    Returns True only once per night to prevent duplicate triggers.
    """
    current_hour = datetime.datetime.now().hour
    current_minute = datetime.datetime.now().minute

    # Trigger only at exactly 02:00 (within the first 5 minutes of the hour)
    if current_hour == NIGHTLY_REVIEW_HOUR and current_minute < 5:
        # Check if we already triggered tonight (prevent duplicate)
        if BOULDER_PATH.exists():
            try:
                with open(BOULDER_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                last_review = data.get("heartbeat", {}).get("last_nightly_review", "")
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                if last_review.startswith(today):
                    return False  # Already triggered today
            except Exception:
                pass
        return True
    return False

def should_trigger_upgrade_center():
    """Check if it's time to trigger the upgrade center (03:00 AM).
    Returns True only once per night to prevent duplicate triggers.
    """
    current_hour = datetime.datetime.now().hour
    current_minute = datetime.datetime.now().minute

    # Trigger only at exactly 03:00 (within the first 5 minutes of the hour)
    if current_hour == NIGHTLY_UPGRADE_TRIGGER_HOUR and current_minute < 5:
        # Check if we already triggered tonight (prevent duplicate)
        if BOULDER_PATH.exists():
            try:
                with open(BOULDER_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                last_run = data.get("upgrade_center", {}).get("last_full_run", "")
                today = datetime.datetime.now().strftime("%Y-%m-%d")
                if last_run.startswith(today):
                    return False  # Already triggered today
            except Exception:
                pass
        return True
    return False

# =============================================================================
# 任务队列扫描 (Task Queue Scanning)
# Reference: docs/11_Execution_And_Daemons.md
# =============================================================================

def scan_task_queue():
    """扫描任务队列，检查待处理任务状态。
    Returns: (pending_count, stale_tasks, overdue_tasks)
    """
    if not TASK_QUEUE_PATH.exists():
        return 0, [], []

    try:
        with open(TASK_QUEUE_PATH, "r", encoding="utf-8") as f:
            queue_data = json.load(f)

        tasks = queue_data.get("tasks", [])
        pending_tasks = [t for t in tasks if t.get("status") == "pending"]
        pending_count = len(pending_tasks)

        # 检查超时任务（超过预期完成时间）
        stale_tasks = []
        overdue_tasks = []
        now = datetime.datetime.now()

        for task in pending_tasks:
            expected = task.get("expected_completion")
            if expected:
                try:
                    expected_dt = datetime.datetime.fromisoformat(expected)
                    if now > expected_dt:
                        overdue_tasks.append(task)
                except:
                    pass

            # 检查长期未完成任务（超过1小时无更新）
            updated = task.get("last_updated")
            if updated:
                try:
                    updated_dt = datetime.datetime.fromisoformat(updated)
                    age_mins = (now - updated_dt).total_seconds() / 60
                    if age_mins > 60:
                        stale_tasks.append({**task, "stale_minutes": age_mins})
                except:
                    pass

        return pending_count, stale_tasks, overdue_tasks

    except Exception as e:
        print(f"[Watchdog] Error scanning task queue: {e}")
        return 0, [], []

def coordinate_with_distiller(pending_count: int, stale_tasks: list, overdue_tasks: list):
    """协调NightlyDistiller执行清理任务队列。
    当发现积压或异常任务时，触发协调逻辑。
    """
    if not BOULDER_PATH.exists():
        return

    try:
        with open(BOULDER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        coordination = data.get("heartbeat", {}).get("distiller_coordination", {})

        # 如果有待处理任务或异常任务，通知distiller
        if pending_count > 0 or len(stale_tasks) > 0 or len(overdue_tasks) > 0:
            coordination["needs_attention"] = True
            coordination["pending_count"] = pending_count
            coordination["stale_count"] = len(stale_tasks)
            coordination["overdue_count"] = len(overdue_tasks)
            coordination["last_check"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            print(f"[Watchdog] Task Queue Alert: {pending_count} pending, {len(stale_tasks)} stale, {len(overdue_tasks)} overdue")
        else:
            coordination["needs_attention"] = False

        data["heartbeat"]["distiller_coordination"] = coordination

        with open(BOULDER_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    except Exception as e:
        print(f"[Watchdog] Error coordinating with distiller: {e}")

def update_heartbeat():
    if not BOULDER_PATH.exists():
        print(f"[Watchdog] boulder.json not found at {BOULDER_PATH}")
        return None

    try:
        with open(BOULDER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        mode = data.get("heartbeat", {}).get("mode", "ACTIVE")
        interval_mins = get_interval_for_mode()

        # Determine effective mode based on time of day
        effective_mode = "DAY" if is_daytime() else "NIGHT"
        if mode != effective_mode:
            mode = effective_mode
            data["heartbeat"]["mode"] = mode

        # Update timestamp
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        data["heartbeat"]["last_sync"] = now
        data["heartbeat"]["interval_minutes"] = interval_mins
        data["heartbeat"]["effective_mode"] = effective_mode

        # Check if nightly review should be triggered
        if should_trigger_nightly_review():
            data["heartbeat"]["nightly_review_pending"] = True
            data["heartbeat"]["nightly_review_triggered_at"] = now
            print(f"[Watchdog] Nightly Review trigger detected! Pending execution at 02:00 AM")
        else:
            data["heartbeat"]["nightly_review_pending"] = False

        # Check if upgrade center should be triggered
        if should_trigger_upgrade_center():
            data["upgrade_center"] = data.get("upgrade_center", {})
            data["upgrade_center"]["nightly_upgrade_pending"] = True
            data["upgrade_center"]["upgrade_center_triggered_at"] = now
            print(f"[Watchdog] Upgrade Center trigger detected! Pending execution at 03:00 AM")

        with open(BOULDER_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[Watchdog] Heartbeat Sync: {now} (Mode: {effective_mode}, Interval: {interval_mins}m)")
        return interval_mins
    except Exception as e:
        print(f"[Watchdog] Error during heartbeat sync: {e}")
        return 5

def check_nightly_review_trigger():
    """Check and execute nightly review trigger.
    Called during heartbeat to coordinate with nightly_distiller.ts.
    """
    if not BOULDER_PATH.exists():
        return False

    try:
        with open(BOULDER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("heartbeat", {}).get("nightly_review_pending"):
            triggered_at = data["heartbeat"].get("nightly_review_triggered_at", "")
            print(f"[Watchdog] Executing Nightly Review! Triggered at: {triggered_at}")

            # Mark as executed
            data["heartbeat"]["nightly_review_pending"] = False
            data["heartbeat"]["last_nightly_review"] = triggered_at

            with open(BOULDER_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            return True
    except Exception as e:
        print(f"[Watchdog] Error checking nightly review: {e}")

    return False

def check_upgrade_center_trigger():
    """Check and execute upgrade center trigger.

    CLOSED LOOP (Round 5 + Round 6):
    - Round 5: When nightly_upgrade_pending=True (03:00 AM),
      spawns TypeScript runner as real subprocess (not just setting a flag).
    - Round 6: After UC executes, reads upgrade_center_result.json,
      then calls _record_upgrade_outcome() → governance_bridge.record_outcome()
      to backflow TS execution result into Python governance system.

    Before Round 5: only set flags in boulder.json (no real execution).
    """
    if not BOULDER_PATH.exists():
        return False

    try:
        with open(BOULDER_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)

        if not data.get("upgrade_center", {}).get("nightly_upgrade_pending"):
            return False

        triggered_at = data["upgrade_center"].get("upgrade_center_triggered_at", "")
        print(f"[Watchdog] Executing Upgrade Center! Triggered at: {triggered_at}")

        # Spawn the TypeScript runner as a real subprocess
        # This is the minimum physical execution — not just setting a flag
        runner_path = UPGRADE_CENTER_RUNNER.resolve()
        if not runner_path.exists():
            print(f"[Watchdog] ERROR: Upgrade Center runner not found at {runner_path}")
            # Mark as executed to avoid repeated attempts
            data["upgrade_center"]["nightly_upgrade_pending"] = False
            data["upgrade_center"]["last_full_run"] = triggered_at
            with open(BOULDER_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return False

        try:
            # Use npx tsx to run the TypeScript runner
            # Run from deerflow root so governance_state.json path resolution works
            result = subprocess.run(
                ["npx", "tsx", str(runner_path.resolve())],
                cwd=str(DEERFLOW_ROOT.resolve()),
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for full U0-U8 run
            )

            if result.returncode == 0:
                print(f"[Watchdog] Upgrade Center subprocess completed successfully.")
                if result.stdout:
                    for line in result.stdout.strip().split("\n"):
                        if line.strip():
                            print(f"  [UC] {line}")
            else:
                print(f"[Watchdog] Upgrade Center subprocess failed (code {result.returncode}).")
                if result.stderr:
                    for line in result.stderr.strip().split("\n"):
                        if line.strip():
                            print(f"  [UC ERROR] {line}")

        except subprocess.TimeoutExpired:
            print(f"[Watchdog] Upgrade Center subprocess timed out after 600s.")
        except FileNotFoundError:
            print(f"[Watchdog] npx/tsx not found — cannot execute TypeScript runner.")
            print(f"[Watchdog] Install tsx with: npm install -g tsx")
        except Exception as e:
            print(f"[Watchdog] Error spawning Upgrade Center subprocess: {e}")

        # Verify result.json was written (proof of execution)
        # Then backflow result to governance_bridge (Python main chain)
        executed_at = None
        success = False
        result_record = None
        if RESULT_PATH.exists():
            try:
                with open(RESULT_PATH, "r", encoding="utf-8") as f:
                    result_record = json.load(f)
                executed_at = result_record.get("executed_at", "unknown")
                success = result_record.get("success", False)
                print(f"[Watchdog] Upgrade Center result verified: success={success}, at={executed_at}")
            except Exception:
                print(f"[Watchdog] Could not read upgrade_center_result.json")
        else:
            print(f"[Watchdog] WARNING: upgrade_center_result.json not found — execution may have failed silently")

        # ─────────────────────────────────────────────────────────────
        # ROUND 6: TS → Python 回流闭环
        # watchdog reads result.json → calls governance_bridge.record_outcome()
        # This backflows the upgrade execution result into the Python governance
        # system so it becomes visible to /health/governance and future decisions.
        # ROUND 10: Also emits upgrade_center_summary + upgrade_queue_snapshot
        # ROUND 226: After UC run, automatically invoke queue_consumer to consume pending tasks
        # ─────────────────────────────────────────────────────────────
        _record_upgrade_outcome(
            executed_at=executed_at or triggered_at,
            success=success,
            result_record=result_record,
        )

        # R226: Invoke queue_consumer to consume pending sandbox verification tasks
        # This closes the sandbox execution loop: UC run → pending tasks in queue → queue_consumer executes → governance backflow
        _invoke_queue_consumer()

        # Mark as executed regardless of subprocess outcome (don't re-trigger all night)
        data["upgrade_center"]["nightly_upgrade_pending"] = False
        data["upgrade_center"]["last_full_run"] = triggered_at

        with open(BOULDER_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return True
    except Exception as e:
        print(f"[Watchdog] Error checking upgrade center: {e}")

    return False

def _invoke_queue_consumer():
    """
    R226: After UC run completes, invoke queue_consumer to consume pending sandbox tasks.
    This closes the sandbox execution loop:
      UC run → pending tasks in experiment_queue.json → queue_consumer executes verify script → governance backflow

    Runs as a synchronous subprocess call from the watchdog main loop.
    """
    try:
        import subprocess as _subprocess
        from pathlib import Path as _Path

        backend_dir = DEERFLOW_ROOT / "backend"
        queue_consumer_script = backend_dir / "app" / "m11" / "queue_consumer.py"

        if not queue_consumer_script.exists():
            print(f"[Watchdog] R226: queue_consumer.py not found at {queue_consumer_script}")
            return

        # Check if there are pending tasks first
        EQ_PATH = UPGRADE_CENTER_STATE_DIR / "experiment_queue.json"
        has_pending = False
        if EQ_PATH.exists():
            try:
                with open(EQ_PATH, "r", encoding="utf-8") as f:
                    queue = json.load(f)
                tasks = queue.get("experiment_tasks", [])
                pending = [t for t in tasks if t.get("status") == "pending"]
                has_pending = len(pending) > 0
                print(f"[Watchdog] R226: Found {len(pending)} pending tasks in queue")
            except Exception:
                pass

        if not has_pending:
            print(f"[Watchdog] R226: No pending tasks, skipping queue_consumer invocation")
            return

        print(f"[Watchdog] R226: Invoking queue_consumer to process pending tasks...")

        # Run queue_consumer with --once flag
        result = _subprocess.run(
            ["python", "-m", "app.m11.queue_consumer", "--once"],
            cwd=str(backend_dir.resolve()),
            capture_output=True,
            text=True,
            timeout=300,
        )

        if result.returncode == 0:
            print(f"[Watchdog] R226: queue_consumer completed successfully")
            if result.stdout:
                for line in result.stdout.strip().split("\n"):
                    if line.strip():
                        print(f"  [QC] {line}")
        else:
            print(f"[Watchdog] R226: queue_consumer failed (exit={result.returncode})")
            if result.stderr:
                for line in result.stderr.strip().split("\n"):
                    if line.strip():
                        print(f"  [QC ERROR] {line}")
    except Exception as e:
        print(f"[Watchdog] R226: Error invoking queue_consumer: {e}")

def run_watchdog():
    print("[Watchdog] Sentinel Started. Monitoring AAL Sovereignty 24/7.")
    print(f"[Watchdog] Day Mode: {DAY_MODE_START}:00-{DAY_MODE_END}:00 (5min intervals)")
    print(f"[Watchdog] Night Mode: {DAY_MODE_END}:00-{DAY_MODE_START}:00 (30min intervals)")
    print(f"[Watchdog] Nightly Review Trigger: {NIGHTLY_REVIEW_HOUR}:00 AM")
    print(f"[Watchdog] Upgrade Center Trigger: {NIGHTLY_UPGRADE_TRIGGER_HOUR}:00 AM")

    while True:
        interval_mins = update_heartbeat()

        # 扫描任务队列
        pending_count, stale_tasks, overdue_tasks = scan_task_queue()

        # 协调NightlyDistiller
        coordinate_with_distiller(pending_count, stale_tasks, overdue_tasks)

        # Check for nightly review trigger
        if check_nightly_review_trigger():
            print("[Watchdog] Nightly Review triggered! Coordination with NightlyDistiller active.")

        # Check for upgrade center trigger
        if check_upgrade_center_trigger():
            print("[Watchdog] Upgrade Center triggered! Coordination with UpgradeCenter active.")

        # P1: Queue-awareness — always check experiment_queue.json for health signals
        _check_experiment_queue()

        # Sleep in smaller increments to be more responsive to time-sensitive events
        time.sleep(interval_mins * 60)

if __name__ == "__main__":
    run_watchdog()
