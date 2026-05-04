from pathlib import Path
import json, yaml, sys

root = Path(__file__).parent
errors = []

# 1) parse all yaml/json
for p in root.rglob("*"):
    if p.is_file():
        if p.suffix in [".yaml", ".yml"]:
            try:
                yaml.safe_load(p.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"YAML parse error: {p} -> {e}")
        elif p.suffix == ".json":
            try:
                json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                errors.append(f"JSON parse error: {p} -> {e}")

# 2) presence checks
must_exist = [
    "config/integration_manifest.yaml",
    "config/role_registry.final.yaml",
    "config/agent_registry.rtcm.final.yaml",
    "config/issue_debate_protocol.final.yaml",
    "config/project_dossier_schema.final.yaml",
    "config/prompt_loader_and_assembly_spec.final.yaml",
    "config/runtime_orchestrator_spec.final.yaml",
    "config/feishu_rendering_spec.final.yaml",
    "prompts/chair.md",
    "prompts/supervisor.md",
    "prompts/trend.md",
    "prompts/value.md",
    "prompts/architecture.md",
    "prompts/automation.md",
    "prompts/quality.md",
    "prompts/efficiency.md",
    "prompts/challenger.md",
    "prompts/validator.md",
    "examples/ai_manju_project/project_dossier/manifest.json",
    "examples/ai_manju_project/project_dossier/issue_cards/issue_001.json",
    "examples/ai_manju_project/project_dossier/issue_cards/issue_002.json",
    "examples/ai_manju_project/project_dossier/validation_runs/validation_001.json",
    "examples/ai_manju_project/project_dossier/evidence_ledger.json",
    "examples/ai_manju_project/project_dossier/issue_graph.json",
]
for rel in must_exist:
    if not (root / rel).exists():
        errors.append(f"Missing required file: {rel}")

# 3) example dossier completeness vs schema declaration
schema = yaml.safe_load((root / "config" / "project_dossier_schema.final.yaml").read_text(encoding="utf-8"))
files = schema["directory_layout"]["files"]
ex_root = root / "examples" / "ai_manju_project" / "project_dossier"
for _, rel in files.items():
    if not (ex_root / rel).exists():
        errors.append(f"Example dossier missing schema-declared file: {rel}")

# 4) prompt loader configurable path check
pls = yaml.safe_load((root / "config" / "prompt_loader_and_assembly_spec.final.yaml").read_text(encoding="utf-8"))
if not isinstance(pls.get("root_paths", {}).get("prompt_root"), dict):
    errors.append("prompt_root should be configurable dict")
if not isinstance(pls.get("root_paths", {}).get("dossier_root"), dict):
    errors.append("dossier_root should be configurable dict")

if errors:
    print("BUNDLE VALIDATION FAILED")
    for e in errors:
        print("-", e)
    sys.exit(1)

print("BUNDLE VALIDATION PASSED")
