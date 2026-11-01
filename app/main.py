"""メインオーケストレーターと常駐監視ループモジュール."""

from __future__ import annotations

import argparse
import logging
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.actions.clipboard_helper import ClipboardHelper
from app.actions.desktop_notifier import DesktopNotifier
from app.ai.decision_engine import DecisionEngine
from app.ai.lm_studio_client import LMStudioClient
from app.config import AppSettings, load_settings, resolve_queue_directories
from app.storage.repository import WorkflowRepository
from app.watcher.queue_watcher import QueueFileReadError, QueueWatcher

logger = logging.getLogger(__name__)


@dataclass
class BatchSummary:
    """1パス（バッチ）あたりのキュー処理結果サマリ."""

    scanned_files: int = 0
    processed_count: int = 0
    duplicate_skipped_count: int = 0
    failed_count: int = 0
    consultations_count: int = 0
    tasks_count: int = 0
    ignored_count: int = 0
    info_count: int = 0
    items: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class WorkflowProcessor:
    """キューウォッチャー・Decision Engine・DB保存・デスクトップアクションを統合するプロセッサ."""

    def __init__(
        self,
        watcher: QueueWatcher,
        repository: WorkflowRepository,
        decision_engine: DecisionEngine,
        notifier: DesktopNotifier,
        clipboard: ClipboardHelper,
    ) -> None:
        self.watcher = watcher
        self.repository = repository
        self.decision_engine = decision_engine
        self.notifier = notifier
        self.clipboard = clipboard

    @classmethod
    def from_settings(cls, settings: AppSettings) -> WorkflowProcessor:
        directories = resolve_queue_directories(settings.queue, ensure_exists=True)
        watcher = QueueWatcher(directories)
        repository = WorkflowRepository(settings.database.path)
        lm_client = LMStudioClient(settings.lm_studio)
        decision_engine = DecisionEngine(lm_client, settings.user_profile)
        notifier = DesktopNotifier(enabled=settings.actions.enable_toast_notification)
        clipboard = ClipboardHelper(enabled=settings.actions.enable_auto_clipboard)
        return cls(
            watcher=watcher,
            repository=repository,
            decision_engine=decision_engine,
            notifier=notifier,
            clipboard=clipboard,
        )

    def process_pending_queue(self) -> BatchSummary:
        """incoming/ 内の未処理JSONファイルを1パスですべて処理する."""
        summary = BatchSummary()
        pending_files = self.watcher.list_pending_files()
        summary.scanned_files = len(pending_files)

        for file_path in pending_files:
            self._process_single_file(file_path, summary)

        return summary

    def _process_single_file(self, file_path: Path, summary: BatchSummary) -> None:
        try:
            message, raw_json = self.watcher.read_message_file(file_path)
        except QueueFileReadError as exc:
            logger.error("Invalid queue file %s: %s", file_path.name, exc)
            self.watcher.move_to_failed(file_path)
            summary.failed_count += 1
            summary.items.append(
                {
                    "file": file_path.name,
                    "status": "failed",
                    "error": str(exc),
                }
            )
            return

        if self.repository.is_message_processed(message.message_id):
            logger.info("Duplicate message_id %s detected; moving to processed.", message.message_id)
            self.watcher.move_to_processed(file_path)
            summary.duplicate_skipped_count += 1
            summary.items.append(
                {
                    "file": file_path.name,
                    "message_id": message.message_id,
                    "status": "duplicate_skipped",
                }
            )
            return

        try:
            decision = self.decision_engine.evaluate(message)
            self.repository.save_message(message=message, decision=decision, raw_json=raw_json)

            if decision.action_type == "consultation":
                reply_text = decision.consultation.suggested_reply
                copied = self.clipboard.copy(reply_text)
                self.repository.save_consultation(
                    message_id=message.message_id,
                    missing_points=decision.consultation.missing_points,
                    suggested_reply=reply_text,
                    is_copied=copied or bool(self.clipboard.last_copied_text),
                )
                self.notifier.notify_consultation(
                    sender_name=message.sender_name,
                    suggested_reply=reply_text,
                )
                summary.consultations_count += 1

            elif decision.action_type == "task":
                task_title = decision.task.title or f"{message.sender_name}からの依頼"
                self.repository.save_task(
                    message_id=message.message_id,
                    title=task_title,
                    description=decision.task.description or message.content,
                    due_date=decision.task.due_date,
                    priority=decision.task.priority,
                    status="todo",
                )
                self.notifier.notify_task(task_title=task_title)
                summary.tasks_count += 1

            elif decision.action_type == "info":
                summary.info_count += 1

            else:
                summary.ignored_count += 1

            self.watcher.move_to_processed(file_path)
            summary.processed_count += 1
            summary.items.append(
                {
                    "file": file_path.name,
                    "message_id": message.message_id,
                    "status": "processed",
                    "action_type": decision.action_type,
                    "is_relevant": decision.is_relevant,
                }
            )
        except Exception as exc:
            logger.error("Failed to process message %s (%s): %s", message.message_id, file_path.name, exc)
            self.watcher.move_to_failed(file_path)
            summary.failed_count += 1
            summary.items.append(
                {
                    "file": file_path.name,
                    "message_id": message.message_id,
                    "status": "failed",
                    "error": str(exc),
                }
            )


def run_forever(
    settings_path: str = "config/settings.yaml",
    profile_path: str = "config/user_profile.yaml",
    once: bool = False,
) -> BatchSummary:
    """常駐監視ループ（または --once 指定時は1回のみ）を実行する."""
    settings = load_settings(settings_path=settings_path, user_profile_path=profile_path)
    processor = WorkflowProcessor.from_settings(settings)

    logger.info(
        "teams-ai-workflow started. Watching: %s",
        processor.watcher.directories.incoming,
    )

    if once:
        return processor.process_pending_queue()

    poll_interval = max(1, settings.queue.poll_interval_seconds)
    last_summary = BatchSummary()
    try:
        while True:
            last_summary = processor.process_pending_queue()
            time.sleep(poll_interval)
    except KeyboardInterrupt:
        logger.info("Stopped teams-ai-workflow watcher loop.")
    return last_summary


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    parser = argparse.ArgumentParser(description="teams-ai-workflow daemon")
    parser.add_argument("--settings", default="config/settings.yaml", help="Path to settings.yaml")
    parser.add_argument(
        "--profile", default="config/user_profile.yaml", help="Path to user_profile.yaml"
    )
    parser.add_argument("--once", action="store_true", help="Process pending queue once and exit")
    args = parser.parse_args()

    run_forever(
        settings_path=args.settings,
        profile_path=args.profile,
        once=args.once,
    )


if __name__ == "__main__":
    main()

