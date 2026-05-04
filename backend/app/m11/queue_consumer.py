"""
app/m11/queue_consumer.py
R211: 最小 Sandbox Queue Consumer
R212: 治理回写 — 执行完成后调用 governance_bridge.record_outcome(sandbox_execution_result)
消费 experiment_queue.json 中的 pending task，执行 verify_script_path，
将状态写回 experiment_queue.json 和 governance_state。
"""

import json
import os
import subprocess
import logging
import asyncio
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from app.runtime_paths import upgrade_center_state_dir

logger = logging.getLogger(__name__)

STATE_DIR = upgrade_center_state_dir()
QUEUE_FILE = STATE_DIR / "experiment_queue.json"

# R230-fix: DEERFLOW_ROOT — resolved bash path per platform
DEERFLOW_ROOT = "/e/OpenClaw-Base/deerflow"
# R230-fix: Use shutil.which() for Windows Git bash path so shell=False works
# R211 originally said shell=False couldn't call bash on Windows — that was wrong
# when using the Windows-native path (C:\Program Files\Git\usr\bin\bash.EXE).
# shell=False + list args properly passes env= vars to bash subprocess.
BASH_BIN = shutil.which("bash") or "/usr/bin/bash"

# R212: Governance Bridge — 延迟导入避免循环依赖
_bridge = None

def _get_governance_bridge():
    global _bridge
    if _bridge is None:
        from app.m11.governance_bridge import governance_bridge
        _bridge = governance_bridge
    return _bridge


def load_queue() -> dict:
    """加载队列（UTF-8，避免 GBK 编码问题）"""
    if not QUEUE_FILE.exists():
        return {"date": "", "experiment_tasks": [], "pending_verification": []}
    try:
        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"[QueueConsumer] 加载队列失败: {e}")
        return {"date": "", "experiment_tasks": [], "pending_verification": []}


def save_queue(queue: dict) -> None:
    """保存队列（UTF-8）"""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(queue, f, indent=2, ensure_ascii=False)


def find_pending_task(queue: dict) -> Optional[dict]:
    """
    找第一个 pending 且有 verify_script_path 的 task。
    优先选 R210+ 的 task（有脚本路径）。
    """
    for task in queue.get("experiment_tasks", []):
        if task.get("status") == "pending" and task.get("verify_script_path"):
            return task
    return None


def execute_script(script_path: str, env_override: dict) -> tuple[int, str, str]:
    """
    通过 Git Bash 执行脚本（shell=False + list args 解决 Windows env 传递问题）。
    R230-fix: R211 误判 — Windows Python 可以用 shell=False + bash Windows 路径调用 bash，
    同时正确传递 env= 变量。改用 list args 而非 string command + shell=True。
    返回 (exit_code, stdout, stderr)
    """
    env = os.environ.copy()
    env.update(env_override)

    # R230-fix: shell=False + list args 正确传递 env 到 bash 子进程
    try:
        result = subprocess.run(
            [BASH_BIN, script_path],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=300,
            shell=False,
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -2, "", f"Bash not found at {BASH_BIN}"
    except subprocess.TimeoutExpired:
        return -1, "", "Execution timeout (>300s)"
    except Exception as e:
        return -3, "", str(e)


def run_verification(task: dict) -> tuple[int, str, str]:
    """
    执行 verify_script。
    R211: DEERFLOW_ROOT 通过环境变量传入 bash 子进程。
    """
    verify_script = task.get("verify_script_path")
    if not verify_script:
        return -99, "", "No verify_script_path"

    logger.info(f"[QueueConsumer] 执行验证: {verify_script}")

    return execute_script(
        verify_script,
        env_override={"DEERFLOW_ROOT": DEERFLOW_ROOT}
    )


def run_rollback(task: dict) -> tuple[int, str, str]:
    """
    执行 rollback_script（若存在）。
    仅在 verify 失败后调用。
    """
    rollback_script = task.get("rollback_script_path")
    if not rollback_script:
        return 0, "", "No rollback_script_path (non-blocking)"

    logger.info(f"[QueueConsumer] 执行回滚: {rollback_script}")

    return execute_script(
        rollback_script,
        env_override={"DEERFLOW_ROOT": DEERFLOW_ROOT}
    )


def update_task_in_queue(queue: dict, task_id: str, updates: dict) -> None:
    """在内存中更新 task 对象"""
    for task in queue.get("experiment_tasks", []):
        if task.get("id") == task_id:
            task.update(updates)
            break


def write_governance_outcome(exec_result: dict) -> None:
    """
    R212: 将真实执行结果写入 governance_state。
    使用 asyncio.new_event_loop() 在同步上下文中调用 async record_outcome。
    """
    try:
        bridge = _get_governance_bridge()

        candidate_id = exec_result.get("candidate_id", "")
        verify_exit_code = exec_result.get("verify_exit_code", -999)
        rollback_invoked = exec_result.get("rollback_invoked", False)
        execution_status = exec_result.get("status", "unknown")  # completed / failed

        # R212: actual_result — execution truth
        # verify_exit_code=0 → success(1.0), non-0 → failure(0.0)
        actual_result = 1.0 if verify_exit_code == 0 else 0.0

        # R212: execution_status 语义映射
        if execution_status == "completed":
            exec_status = "success"
        elif execution_status == "failed":
            exec_status = "failed" if rollback_invoked else "failed_no_rollback"
        else:
            exec_status = execution_status

        # R212: predicted_result — now sourced from task provenance metadata (R227-fix)
        predicted_result = exec_result.get("predicted")

        # R212: context — 完整执行上下文
        # R227-fix: includes filter_result, execution_stage, tier, ltv for ground truth segmentation
        context = {
            "candidate_id": candidate_id,
            "execution_status": exec_status,
            "verify_exit_code": verify_exit_code,
            "rollback_invoked": rollback_invoked,
            "rollback_exit_code": exec_result.get("rollback_exit_code"),
            "executed_at": exec_result.get("finished_at"),
            "started_at": exec_result.get("started_at"),
            "task_id": exec_result.get("task_id"),
            "source": "sandbox_executor",
            "last_error": exec_result.get("last_error"),
            # R227-fix: pipeline provenance for segmented ground truth analysis
            "filter_result": exec_result.get("filter_result"),
            "execution_stage": exec_result.get("execution_stage"),
            "tier": exec_result.get("tier"),
            "ltv": exec_result.get("ltv"),
        }

        # R212: 异步调用 governance_bridge.record_outcome（sync wrapper）
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                bridge.record_outcome(
                    outcome_type="sandbox_execution_result",
                    actual_result=actual_result,
                    predicted_result=predicted_result,
                    context=context,
                )
            )
        finally:
            loop.close()

        logger.info(f"[QueueConsumer] R212: governance 回写完成: {candidate_id} actual={actual_result}")
    except Exception as e:
        logger.warning(f"[QueueConsumer] R212: governance 回写失败: {e}")


def consume_one_task() -> dict:
    """
    R211 主入口：消费一条 pending task。
    返回执行结果摘要。
    """
    queue = load_queue()
    task = find_pending_task(queue)

    if task is None:
        return {"status": "no_pending_task", "message": "没有待消费的 pending task 或所有 task 缺少 verify_script_path"}

    task_id = task["id"]
    candidate_id = task["candidate_id"]
    now = datetime.now(timezone.utc).isoformat()

    # 1. status: pending → running
    update_task_in_queue(queue, task_id, {
        "status": "running",
        "started_at": now,
    })
    save_queue(queue)  # 立即写回，确认 running 状态
    logger.info(f"[QueueConsumer] {candidate_id}: pending → running")

    # 2. 执行 verify
    verify_exit_code, stdout, stderr = run_verification(task)

    # 3. 收集结果
    finished_at = datetime.now(timezone.utc).isoformat()
    result_updates = {
        "finished_at": finished_at,
        "verify_exit_code": verify_exit_code,
    }

    if verify_exit_code == 0:
        # 验证成功
        result_updates["status"] = "completed"
        logger.info(f"[QueueConsumer] {candidate_id}: completed (exit=0)")
    else:
        # 验证失败 → 执行 rollback
        result_updates["status"] = "failed"
        result_updates["last_error"] = (stderr or stdout or "").strip()[:500]
        logger.warning(f"[QueueConsumer] {candidate_id}: failed (exit={verify_exit_code}), 执行 rollback")

        rollback_code, rollback_out, rollback_err = run_rollback(task)
        result_updates["rollback_invoked"] = True
        result_updates["rollback_exit_code"] = rollback_code

    # 4. 写回队列
    update_task_in_queue(queue, task_id, result_updates)
    save_queue(queue)

    # R212: 写治理回写（execution truth → governance_state）
    # R227-fix: Pass pipeline provenance metadata from task to governance backflow
    write_governance_outcome({
        "status": result_updates["status"],
        "candidate_id": candidate_id,
        "task_id": task_id,
        "verify_exit_code": verify_exit_code,
        "rollback_invoked": result_updates.get("rollback_invoked", False),
        "rollback_exit_code": result_updates.get("rollback_exit_code"),
        "last_error": result_updates.get("last_error"),
        "started_at": now,
        "finished_at": finished_at,
        # R227-fix: provenance from task object
        "filter_result": task.get("filter_result"),
        "execution_stage": task.get("execution_stage"),
        "predicted": task.get("predicted"),
        "tier": task.get("tier"),
        "ltv": task.get("ltv"),
    })

    return {
        "status": result_updates["status"],
        "candidate_id": candidate_id,
        "task_id": task_id,
        "verify_exit_code": verify_exit_code,
        "rollback_invoked": result_updates.get("rollback_invoked", False),
        "started_at": now,
        "finished_at": finished_at,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Queue Consumer")
    parser.add_argument("--once", action="store_true", help="Consume only one task and exit")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [QueueConsumer] %(levelname)s %(message)s"
    )
    result = consume_one_task()
    print(json.dumps(result, indent=2, ensure_ascii=False))
