"""OneDrive同期フォルダ (incoming/) の監視・JSON読み取り・ファイル移動モジュール."""

from __future__ import annotations

import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from app.config import QueueDirectories
from app.schemas import IncomingMessage

logger = logging.getLogger(__name__)


class QueueFileReadError(Exception):
    """キューJSONファイルの読み込みまたはスキーマ検証エラー."""


class QueueWatcher:
    """TeamsQueue/incoming フォルダの未処理JSONを検出・検証し、processed/failedへ移動する."""

    def __init__(self, directories: QueueDirectories) -> None:
        self.directories = directories
        self.directories.incoming.mkdir(parents=True, exist_ok=True)
        self.directories.processed.mkdir(parents=True, exist_ok=True)
        self.directories.failed.mkdir(parents=True, exist_ok=True)

    def list_pending_files(self) -> list[Path]:
        """incoming/ 内の .json ファイルを名前順（時系列順）で返す."""
        if not self.directories.incoming.exists():
            return []
        return sorted(
            p for p in self.directories.incoming.iterdir()
            if p.is_file() and p.suffix.lower() == ".json"
        )

    def read_message_file(self, file_path: Path) -> tuple[IncomingMessage, str]:
        """JSONファイルを読み込み、IncomingMessage モデルとして検証して返す."""
        try:
            raw_text = file_path.read_text(encoding="utf-8-sig")
        except Exception as exc:
            raise QueueFileReadError(f"Failed to read file {file_path.name}: {exc}") from exc

        if not raw_text.strip():
            raise QueueFileReadError(f"File {file_path.name} is empty")

        try:
            data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise QueueFileReadError(f"Invalid JSON in {file_path.name}: {exc}") from exc

        if not isinstance(data, dict):
            raise QueueFileReadError(f"JSON root in {file_path.name} must be an object")

        try:
            message = IncomingMessage.model_validate(data)
        except ValidationError as exc:
            raise QueueFileReadError(
                f"Schema validation failed for {file_path.name}: {exc}"
            ) from exc

        return message, raw_text

    def move_to_processed(self, file_path: Path) -> Path:
        """処理完了したファイルを processed/ へ移動する."""
        return self._safe_move(file_path, self.directories.processed)

    def move_to_failed(self, file_path: Path) -> Path:
        """エラーが発生したファイルを failed/ へ退避する."""
        return self._safe_move(file_path, self.directories.failed)

    @staticmethod
    def _safe_move(source: Path, target_dir: Path) -> Path:
        """同名ファイルが存在する場合でも上書き衝突を避けて移動する."""
        target_dir.mkdir(parents=True, exist_ok=True)
        destination = target_dir / source.name
        if destination.exists():
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
            destination = target_dir / f"{source.stem}_{timestamp}{source.suffix}"
        shutil.move(str(source), str(destination))
        return destination

