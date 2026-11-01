"""クリップボード自動コピーと非対応環境向けフォールバックヘルパー."""

from __future__ import annotations

import logging
from typing import Callable

logger = logging.getLogger(__name__)


class ClipboardHelper:
    """OSクリップボードへのテキストコピーを管理するヘルパー."""

    def __init__(
        self,
        enabled: bool = True,
        copy_backend: Callable[[str], None] | None = None,
    ) -> None:
        self.enabled = enabled
        self._copy_backend = copy_backend
        self.last_copied_text: str | None = None

    def copy(self, text: str) -> bool:
        """テキストをクリップボードへコピーする。GUI非対応環境では安全にフォールバックする."""
        if not self.enabled or not text:
            return False

        self.last_copied_text = text

        if self._copy_backend is not None:
            try:
                self._copy_backend(text)
                return True
            except Exception as exc:
                logger.warning("Custom clipboard backend failed (fallback used): %s", exc)
                return False

        try:
            import pyperclip  # type: ignore

            pyperclip.copy(text)
            return True
        except Exception as exc:
            logger.warning(
                "Clipboard mechanism unavailable in current environment (stored in memory): %s",
                exc,
            )
            return False

