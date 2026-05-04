
import json
from pathlib import Path

root = Path(__file__).parent
manifest = json.loads((root / "project_dossier" / "manifest.json").read_text(encoding="utf-8"))
state = json.loads((root / "runtime" / "session_state.json").read_text(encoding="utf-8"))
issue = json.loads((root / "project_dossier" / "issue_cards" / f"{state['current_issue_id']}.json").read_text(encoding="utf-8"))
validation = json.loads((root / "project_dossier" / "validation_runs" / "validation_001.json").read_text(encoding="utf-8"))

print("=== RTCM 最小可运行原型 ===")
print(f"项目：{manifest['project_name']}")
print(f"当前状态：{state['status']}")
print(f"当前议题：{issue['issue_title']}")
print(f"当前阶段：{state['current_stage']}")
print()
print("【主席摘要】")
for k, v in state["latest_chair_summary"].items():
    print(f"- {k}: {v}")
print()
print("【当前议题裁决】")
print(f"- verdict: {issue['verdict']}")
print(f"- next_action: {issue['next_action']}")
print(f"- strongest_dissent: {issue['strongest_dissent']}")
print(f"- unresolved_uncertainties: {issue['unresolved_uncertainties']}")
print()
print("【验证结果】")
print(f"- pass_fail_summary: {validation['pass_fail_summary']}")
print(f"- reopen_reason_if_any: {validation['reopen_reason_if_any']}")
print()
print("【系统建议】")
if issue["status"] == "reopened":
    print("- 返会到 solution_generation")
    print("- 优先修正：角色一致性模板、自动配音稳定性")
    print("- 质量阈值达标后再扩大自动化覆盖率")
else:
    print("- 当前议题可继续推进")
