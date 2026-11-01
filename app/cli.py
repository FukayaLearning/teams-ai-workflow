"""Hermes Agent および Cron 連携用の CLI サブコマンドモジュール."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Sequence

from app.actions.clipboard_helper import ClipboardHelper
from app.config import AppSettings, load_settings
from app.main import WorkflowProcessor
from app.schemas import TaskStatusType
from app.storage.repository import WorkflowRepository


def _print_output(data: Any, as_json: bool) -> None:
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
        return

    if isinstance(data, dict):
        for k, v in data.items():
            print(f"{k}: {v}")
    elif isinstance(data, list):
        for item in data:
            print(item)
    else:
        print(data)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m app.cli",
        description="teams-ai-workflow CLI for Hermes Agent and Cron integration",
    )
    parser.add_argument(
        "--settings",
        default="config/settings.yaml",
        help="Path to settings.yaml",
    )
    parser.add_argument(
        "--profile",
        default="config/user_profile.yaml",
        help="Path to user_profile.yaml",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # process-queue
    p_queue = subparsers.add_parser(
        "process-queue",
        help="Process all pending JSON files in incoming/ directory once",
    )
    p_queue.add_argument("--json", action="store_true", help="Output result as JSON")

    # list-tasks
    p_tasks = subparsers.add_parser("list-tasks", help="List tasks stored in SQLite DB")
    p_tasks.add_argument(
        "--status",
        choices=["todo", "in_progress", "done"],
        default=None,
        help="Filter tasks by status",
    )
    p_tasks.add_argument("--json", action="store_true", help="Output result as JSON")

    # update-task
    p_update = subparsers.add_parser("update-task", help="Update task status")
    p_update.add_argument("task_id", type=int, help="Task ID to update")
    p_update.add_argument(
        "--status",
        choices=["todo", "in_progress", "done"],
        required=True,
        help="New status for the task",
    )
    p_update.add_argument("--json", action="store_true", help="Output result as JSON")

    # list-consultations
    p_consult = subparsers.add_parser(
        "list-consultations",
        help="List consultation records and suggested replies",
    )
    p_consult.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of consultations to return",
    )
    p_consult.add_argument("--json", action="store_true", help="Output result as JSON")

    # copy-reply
    p_copy = subparsers.add_parser(
        "copy-reply",
        help="Copy suggested reply (or refined text) for a consultation to clipboard",
    )
    p_copy.add_argument("message_id", help="Message ID of the consultation")
    p_copy.add_argument(
        "--text",
        default=None,
        help="Optional custom/refined reply text to copy and save",
    )
    p_copy.add_argument("--json", action="store_true", help="Output result as JSON")

    return parser


def run_cli(
    argv: Sequence[str] | None = None,
    settings_override: AppSettings | None = None,
    processor_override: WorkflowProcessor | None = None,
) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    settings = settings_override or load_settings(
        settings_path=args.settings,
        user_profile_path=args.profile,
    )

    if args.command == "process-queue":
        processor = processor_override or WorkflowProcessor.from_settings(settings)
        summary = processor.process_pending_queue()
        _print_output(summary.to_dict(), as_json=args.json)
        return 0

    repository = WorkflowRepository(settings.database.path)

    if args.command == "list-tasks":
        tasks = repository.list_tasks(status=args.status)
        _print_output({"tasks": tasks, "count": len(tasks)}, as_json=args.json)
        return 0

    if args.command == "update-task":
        status_val: TaskStatusType = args.status
        updated = repository.update_task_status(args.task_id, status_val)
        result = {
            "task_id": args.task_id,
            "status": status_val,
            "updated": updated,
        }
        _print_output(result, as_json=args.json)
        return 0 if updated else 1

    if args.command == "list-consultations":
        consultations = repository.list_consultations(limit=args.limit)
        _print_output(
            {"consultations": consultations, "count": len(consultations)},
            as_json=args.json,
        )
        return 0

    if args.command == "copy-reply":
        record = repository.get_consultation_by_message_id(args.message_id)
        if record is None and args.text is None:
            _print_output(
                {
                    "message_id": args.message_id,
                    "copied": False,
                    "error": "Consultation record not found",
                },
                as_json=args.json,
            )
            return 1

        reply_to_copy = args.text if args.text is not None else str(record["suggested_reply"])
        clipboard = ClipboardHelper(enabled=True)
        os_copied = clipboard.copy(reply_to_copy)
        if record is not None:
            repository.mark_consultation_copied(
                message_id=args.message_id,
                updated_reply=args.text,
            )

        _print_output(
            {
                "message_id": args.message_id,
                "copied": os_copied or bool(clipboard.last_copied_text),
                "suggested_reply": reply_to_copy,
            },
            as_json=args.json,
        )
        return 0

    return 1


def main() -> None:
    sys.exit(run_cli())


if __name__ == "__main__":
    main()

