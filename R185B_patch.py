from pathlib import Path

root = Path("backend")

# 1) auth_middleware.py: add Any import
p = root / "app/gateway/auth_middleware.py"
t = p.read_text(encoding="utf-8-sig")
if "from typing import Any" not in t:
    t = t.replace(
        "from collections.abc import Callable\n",
        "from collections.abc import Callable\nfrom typing import Any\n",
    )
p.write_text(t, encoding="utf-8", newline="\n")

# 2) mode_router.py: Enum -> StrEnum, remove unused needs_confirm
p = root / "app/gateway/mode_router.py"
t = p.read_text(encoding="utf-8-sig")
t = t.replace("from enum import Enum", "from enum import StrEnum")
t = t.replace("class SelectedMode(str, Enum):", "class SelectedMode(StrEnum):")
t = t.replace("class DelegatedTo(str, Enum):", "class DelegatedTo(StrEnum):")
t = t.replace("        needs_confirm = True\n", "")
p.write_text(t, encoding="utf-8", newline="\n")

# 3) registry_manager.py: move DB_PATH import above logger
p = root / "app/m04/registry_manager.py"
t = p.read_text(encoding="utf-8-sig")
t = t.replace(
    "\nlogger = logging.getLogger(__name__)\n\nfrom app.m04.registry_db import DB_PATH\n",
    "\nfrom app.m04.registry_db import DB_PATH\n\nlogger = logging.getLogger(__name__)\n",
)
p.write_text(t, encoding="utf-8", newline="\n")

# 4) langgraph_auth.py: replace entire add_owner_filter with user_id version
p = root / "app/gateway/langgraph_auth.py"
t = p.read_text(encoding="utf-8-sig")
marker = "@auth.on\nasync def add_owner_filter"
idx = t.index(marker)

replacement = '''@auth.on
async def add_owner_filter(ctx: Auth.types.AuthContext, value: dict):
    """Inject user_id metadata on writes; filter by user_id on reads.

    Gateway stores thread ownership as ``metadata.user_id``.
    This handler ensures LangGraph Server enforces the same isolation.
    """
    metadata = value.setdefault("metadata", {})
    metadata["user_id"] = ctx.user.identity
    return {"user_id": ctx.user.identity}
'''

t = t[:idx] + replacement
p.write_text(t, encoding="utf-8", newline="\n")

print("R185B_PATCH_APPLIED")
