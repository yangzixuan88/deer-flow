"""Local CI dry-run CLI for R241-16B.

Default mode is plan-only. The script does not create workflow files, call
network/webhooks, write runtime state, write audit JSONL, read secrets, or
execute auto-fix.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.foundation.ci_local_dryrun import (  # noqa: E402
    format_local_ci_result,
    generate_local_ci_dryrun_report,
    run_local_ci_dryrun,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local foundation CI dry-run stages.")
    parser.add_argument(
        "--selection",
        default="all_pr",
        choices=[
            "smoke",
            "fast",
            "safety",
            "slow",
            "full",
            "collect_only",
            "all_pr",
            "all_nightly",
            "all",
        ],
        help="Stage selection to plan or execute.",
    )
    parser.add_argument("--execute", action="store_true", help="Execute selected predefined pytest stage commands.")
    parser.add_argument("--format", default="json", choices=["json", "markdown", "text"], help="Output format.")
    parser.add_argument("--timeout-seconds", type=int, default=None, help="Optional per-stage timeout.")
    parser.add_argument("--write-report", action="store_true", help="Write R241-16B local CI dry-run report.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = run_local_ci_dryrun(
        selection=args.selection,
        execute=args.execute,
        timeout_seconds=args.timeout_seconds,
    )
    if args.write_report:
        report = generate_local_ci_dryrun_report()
        result["report_path"] = report["output_path"]

    formatted = format_local_ci_result(result, args.format)
    if args.format == "json":
        print(json.dumps(formatted, ensure_ascii=False, indent=2))
    else:
        print(formatted)

    return 1 if result.get("overall_status") == "failed" else 0


if __name__ == "__main__":
    raise SystemExit(main())
