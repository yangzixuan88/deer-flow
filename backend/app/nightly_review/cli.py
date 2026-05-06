from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .reporter import NightlyReviewReporter
from .scheduler import NightlyReviewScheduler
from .store import NightlyReviewStore


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    store = NightlyReviewStore()
    reporter = NightlyReviewReporter()
    scheduler = NightlyReviewScheduler(store, reporter)

    if args.command == "list":
        return _cmd_list(store)
    elif args.command == "dry-run":
        return _cmd_dry_run(store, reporter)
    elif args.command == "export":
        return _cmd_export(store, args)
    elif args.command == "clear":
        return _cmd_clear(store, args)
    elif args.command == "send":
        return _cmd_send(store, reporter, args)
    elif args.command == "schedule-dry-run":
        return _cmd_schedule_dry_run(scheduler, args)
    elif args.command == "run-once":
        return _cmd_run_once(scheduler, args)
    else:
        parser.print_help()
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deerflow nightreview",
        description="Nightly Review dry-run pipeline CLI.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("list", help="List all pending review items")

    sub.add_parser("dry-run", help="Print a dry-run report to stdout")

    export_parser = sub.add_parser("export", help="Export items to a JSONL file")
    export_parser.add_argument(
        "--path",
        type=Path,
        required=True,
        help="Output path for JSONL export",
    )

    clear_parser = sub.add_parser("clear", help="Clear all review items")
    clear_parser.add_argument(
        "--force",
        action="store_true",
        help="Skip confirmation prompt",
    )

    send_parser = sub.add_parser("send", help="Send review report (real or dry-run)")
    send_parser.add_argument(
        "--real",
        action="store_true",
        help="Perform a real send. Without this flag, always operates in dry-run mode.",
    )

    sched_parser = sub.add_parser(
        "schedule-dry-run",
        help="Build and print a review report (manual scheduler, dry-run)",
    )
    sched_parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="Path to the store JSONL file (optional; uses default if not set)",
    )
    sched_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to include",
    )
    sched_parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Write report to this path instead of stdout",
    )

    runonce_parser = sub.add_parser(
        "run-once",
        help="Build review payload and optionally mark items reviewed (manual scheduler)",
    )
    runonce_parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="Path to the store JSONL file (optional; uses default if not set)",
    )
    runonce_parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Maximum number of items to include",
    )
    runonce_parser.add_argument(
        "--mark-reviewed",
        action="store_true",
        help="Mark items as reviewed after building the payload",
    )

    return parser


def _cmd_list(store: NightlyReviewStore) -> int:
    items = store.list_pending()
    if not items:
        print("No pending review items.")
        return 0
    print(f"{len(items)} pending item(s):")
    for it in items:
        print(f"  [{it.id}] {it.mode} — {it.reason}")
    return 0


def _cmd_dry_run(store: NightlyReviewStore, reporter: NightlyReviewReporter) -> int:
    items = store.list_pending()
    if not items:
        print("No pending review items.")
        return 0
    payload = reporter.build_payload(items, dry_run=True)
    report = reporter.build_markdown(payload)
    print(report)
    return 0


def _cmd_export(store: NightlyReviewStore, args: argparse.Namespace) -> int:
    count = store.export_jsonl(args.path)
    print(f"Exported {count} item(s) to {args.path}")
    return 0


def _cmd_clear(store: NightlyReviewStore, args: argparse.Namespace) -> int:
    if not args.force:
        confirm = input("Clear all review items? [y/N] ")
        if confirm.strip().lower() != "y":
            print("Aborted.")
            return 1
    count = store.clear()
    print(f"Cleared {count} item(s).")
    return 0


def _cmd_send(
    store: NightlyReviewStore,
    reporter: NightlyReviewReporter,
    args: argparse.Namespace,
) -> int:
    if not args.real:
        items = store.list_pending()
        if not items:
            print("No pending review items.")
            return 0
        payload = reporter.build_payload(items, dry_run=True)
        print("[DRY-RUN] Would send report with the following payload:")
        card = reporter.build_feishu_card_payload(payload)
        import json

        print(json.dumps(card, indent=2, ensure_ascii=False))
        return 0
    else:
        raise NotImplementedError("Real Feishu/Lark send is not implemented in R212X. Please update to a later phase that implements --real send.")


def _cmd_schedule_dry_run(
    scheduler: NightlyReviewScheduler,
    args: argparse.Namespace,
) -> int:
    """Build review payload via scheduler and output as markdown."""
    store = _store_from_args(args)
    scheduler._store = store  # inject store with optional custom path
    limit = args.limit
    output = args.output

    payload = scheduler.build_review_payload(limit=limit)
    report = scheduler.build_markdown_report(limit=limit)

    if output is not None:
        written = scheduler.export_markdown_report(output, limit=limit)
        print(f"Wrote {payload.total} item(s) to {written}")
    else:
        print(report)
    return 0


def _cmd_run_once(
    scheduler: NightlyReviewScheduler,
    args: argparse.Namespace,
) -> int:
    """Build review payload via scheduler and optionally mark reviewed."""
    store = _store_from_args(args)
    scheduler._store = store  # inject store with optional custom path
    limit = args.limit
    mark_reviewed = args.mark_reviewed

    payload = scheduler.run_once(limit=limit, mark_reviewed=mark_reviewed)

    print(f"[DRY-RUN] Built payload: {payload.total} total, {payload.pending} pending, {payload.reviewed} reviewed")
    if mark_reviewed:
        print("(items marked as reviewed)")
    return 0


def _store_from_args(args: argparse.Namespace) -> NightlyReviewStore:
    """Create a store, optionally overriding the storage path from args."""
    if getattr(args, "store", None) is not None:
        return NightlyReviewStore(storage_path=args.store)
    return NightlyReviewStore()


if __name__ == "__main__":
    sys.exit(main())
