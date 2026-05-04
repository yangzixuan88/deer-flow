import json
import time
import datetime
from pathlib import Path

# OpenClaw Architecture 2.0 Watchdog Sentinel
# Purpose: Maintain a 24/7 persistent heartbeat for the AAL sovereignty.
# Aligns with "Non-intrusive 24/7 Ops" rule.

BOULDER_PATH = Path(__file__).parent / "boulder.json"
TASK_QUEUE_PATH = Path(__file__).parent / "task_queue.json"

# Day/Night mode hour ranges
DAY_MODE_START = 6  # 06:00 AM
DAY_MODE_END = 22   # 10:00 PM
NIGHTLY_REVIEW_HOUR = 2  # 02:00 AM trigger for nightly distillation

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

def run_watchdog():
    print("[Watchdog] Sentinel Started. Monitoring AAL Sovereignty 24/7.")
    print(f"[Watchdog] Day Mode: {DAY_MODE_START}:00-{DAY_MODE_END}:00 (5min intervals)")
    print(f"[Watchdog] Night Mode: {DAY_MODE_END}:00-{DAY_MODE_START}:00 (30min intervals)")
    print(f"[Watchdog] Nightly Review Trigger: {NIGHTLY_REVIEW_HOUR}:00 AM")

    while True:
        interval_mins = update_heartbeat()

        # 扫描任务队列
        pending_count, stale_tasks, overdue_tasks = scan_task_queue()

        # 协调NightlyDistiller
        coordinate_with_distiller(pending_count, stale_tasks, overdue_tasks)

        # Check for nightly review trigger
        if check_nightly_review_trigger():
            print("[Watchdog] Nightly Review triggered! Coordination with NightlyDistiller active.")

        # Sleep in smaller increments to be more responsive to time-sensitive events
        time.sleep(interval_mins * 60)

if __name__ == "__main__":
    run_watchdog()