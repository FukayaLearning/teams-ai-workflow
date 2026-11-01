"""Windowsデスクトップ通知（トースト）表示と非対応環境向けフォールバックモジュール."""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass
from typing import Callable

logger = logging.getLogger(__name__)


@dataclass
class NotificationRecord:
    title: str
    body: str


class DesktopNotifier:
    """Windowsトースト通知を発行し、非対応環境ではログ出力にフォールバックするクラス."""

    def __init__(
        self,
        enabled: bool = True,
        notify_backend: Callable[[str, str], None] | None = None,
    ) -> None:
        self.enabled = enabled
        self._notify_backend = notify_backend
        self.history: list[NotificationRecord] = []

    def notify(self, title: str, body: str = "") -> bool:
        """デスクトップ通知を表示する."""
        if not self.enabled:
            return False

        record = NotificationRecord(title=title, body=body)
        self.history.append(record)

        if self._notify_backend is not None:
            try:
                self._notify_backend(title, body)
                return True
            except Exception as exc:
                logger.warning("Custom notify backend failed: %s", exc)
                return False

        if sys.platform == "win32":
            try:
                from windows_toasts import Toast, WindowsToaster  # type: ignore

                toaster = WindowsToaster("teams-ai-workflow")
                toast = Toast()
                toast.text_fields = [title, body] if body else [title]
                toaster.show_toast(toast)
                return True
            except Exception as exc:
                logger.warning("windows-toasts failed, falling back to log output: %s", exc)

        logger.info("[Desktop Notification] %s | %s", title, body)
        return True

    def notify_consultation(self, sender_name: str, suggested_reply: str = "") -> bool:
        """相談受信時の定型通知を表示する."""
        title = f"【相談受信】{sender_name}さんからの相談に対する質問案を作成しました"
        body = suggested_reply[:120] + ("..." if len(suggested_reply) > 120 else "")
        return self.notify(title=title, body=body)

    def notify_task(self, task_title: str) -> bool:
        """タスク登録時の定型通知を表示する."""
        title = f"【タスク登録】「{task_title}」をToDoに登録しました"
        return self.notify(title=title, body="")

