import os, sys
sys.path.insert(0, '.')

os.environ["TEST_OPENCLAW_ENV_A"] = "alpha"
os.environ["TEST_OPENCLAW_ENV_B"] = "beta"

from packages.harness.deerflow.config.app_config import AppConfig

cfg = AppConfig.__new__(AppConfig)

cases = {
    "dollar": "$TEST_OPENCLAW_ENV_A",
    "braced": "${TEST_OPENCLAW_ENV_B}",
    "literal": "literal-value",
    "list": ["$TEST_OPENCLAW_ENV_A", "${TEST_OPENCLAW_ENV_B}"],
    "dict": {"a": "$TEST_OPENCLAW_ENV_A", "b": "${TEST_OPENCLAW_ENV_B}"}
}

print("=== Config regression test ===")
all_pass = True

for k, v in cases.items():
    result = cfg.resolve_env_variables(v)
    expected_map = {
        "dollar": "alpha",
        "braced": "beta",
        "literal": "literal-value",
        "list": ["alpha", "beta"],
        "dict": {"a": "alpha", "b": "beta"}
    }
    exp = expected_map[k]
    passed = result == exp
    status = "PASS" if passed else "FAIL"
    print(f"{k}: {status} — got {repr(result)}, expected {repr(exp)}")
    if not passed:
        all_pass = False

# Test missing variable raises ValueError
print("\n=== Missing variable error test ===")
try:
    cfg.resolve_env_variables("${TEST_OPENCLAW_MISSING}")
    print("missing: FAIL — no error raised")
    all_pass = False
except ValueError as e:
    err_msg = str(e)
    # Check it contains the var name without braces
    if "{TEST_OPENCLAW_MISSING}" not in err_msg and "TEST_OPENCLAW_MISSING" in err_msg:
        print(f"missing: PASS — ValueError correctly reports env name (no braces)")
    elif "{TEST_OPENCLAW_MISSING}" in err_msg:
        print(f"missing: FAIL — ValueError still reports with braces: {err_msg}")
        all_pass = False
    else:
        print(f"missing: PASS — ValueError: {err_msg}")

# Test $VAR format still works
print("\n=== $VAR format test ===")
try:
    result = cfg.resolve_env_variables("$TEST_OPENCLAW_ENV_A")
    passed = result == "alpha"
    print(f"$VAR: {'PASS' if passed else 'FAIL'} — got {repr(result)}")
    if not passed:
        all_pass = False
except Exception as e:
    print(f"$VAR: FAIL — {e}")
    all_pass = False

print("\n=== OVERALL ===")
print("ALL_PASS" if all_pass else "SOME_FAILED")