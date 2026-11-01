"""SQLiteデータベースに対するCRUDリポジトリモジュール."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas import DecisionResult, IncomingMessage, TaskStatusType
from app.storage.database import get_connection, init_db


class WorkflowRepository:
    """メッセージ履歴、タスク、相談履歴の永続化と検索を担うリポジトリ."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        init_db(self.db_path)

    def is_message_processed(self, message_id: str) -> bool:
        """指定された message_id が既に messages テーブルに存在するかを確認する."""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT 1 FROM messages WHERE message_id = ? LIMIT 1",
                (message_id,),
            ).fetchone()
            return row is not None

    def save_message(
        self,
        message: IncomingMessage,
        decision: DecisionResult,
        raw_json: str,
    ) -> int:
        """判定済みメッセージを messages テーブルに保存する."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO messages (
                    message_id, sender_name, chat_type, content, received_at,
                    is_relevant, action_type, reasoning, raw_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.message_id,
                    message.sender_name,
                    message.chat_type,
                    message.content,
                    message.received_at,
                    int(decision.is_relevant),
                    decision.action_type,
                    decision.reasoning,
                    raw_json,
                    now_iso,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def save_task(
        self,
        message_id: str,
        title: str,
        description: str = "",
        due_date: str | None = None,
        priority: str = "normal",
        status: TaskStatusType = "todo",
    ) -> int:
        """抽出されたタスクを tasks テーブルに登録する."""
        now_iso = datetime.now(timezone.utc).isoformat()
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO tasks (
                    message_id, title, description, due_date, priority, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, title, description, due_date, priority, status, now_iso),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def save_consultation(
        self,
        message_id: str,
        missing_points: list[str],
        suggested_reply: str,
        is_copied: bool = False,
    ) -> int:
        """相談事項の不足情報リストと返信質問案を consultations テーブルに保存する."""
        now_iso = datetime.now(timezone.utc).isoformat()
        missing_points_json = json.dumps(missing_points, ensure_ascii=False)
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                """
                INSERT INTO consultations (
                    message_id, missing_points, suggested_reply, is_copied, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    missing_points_json,
                    suggested_reply,
                    int(is_copied),
                    now_iso,
                ),
            )
            conn.commit()
            return int(cursor.lastrowid or 0)

    def mark_consultation_copied(
        self,
        message_id: str,
        updated_reply: str | None = None,
    ) -> bool:
        """相談返信案のコピー済みフラグ（および必要に応じた返信文）を更新する."""
        with get_connection(self.db_path) as conn:
            if updated_reply is not None:
                cursor = conn.execute(
                    """
                    UPDATE consultations
                    SET is_copied = 1, suggested_reply = ?
                    WHERE message_id = ?
                    """,
                    (updated_reply, message_id),
                )
            else:
                cursor = conn.execute(
                    """
                    UPDATE consultations
                    SET is_copied = 1
                    WHERE message_id = ?
                    """,
                    (message_id,),
                )
            conn.commit()
            return cursor.rowcount > 0

    def list_tasks(self, status: str | None = None) -> list[dict[str, Any]]:
        """タスク一覧を取得する（status指定時はフィルタリング）."""
        with get_connection(self.db_path) as conn:
            if status:
                rows = conn.execute(
                    """
                    SELECT t.id, t.message_id, t.title, t.description, t.due_date,
                           t.priority, t.status, t.created_at, m.sender_name
                    FROM tasks t
                    LEFT JOIN messages m ON t.message_id = m.message_id
                    WHERE t.status = ?
                    ORDER BY t.id DESC
                    """,
                    (status,),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT t.id, t.message_id, t.title, t.description, t.due_date,
                           t.priority, t.status, t.created_at, m.sender_name
                    FROM tasks t
                    LEFT JOIN messages m ON t.message_id = m.message_id
                    ORDER BY t.id DESC
                    """
                ).fetchall()
            return [dict(row) for row in rows]

    def update_task_status(self, task_id: int, status: TaskStatusType) -> bool:
        """指定されたタスクIDのステータスを更新する."""
        with get_connection(self.db_path) as conn:
            cursor = conn.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status, task_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def list_consultations(self, limit: int = 20) -> list[dict[str, Any]]:
        """相談履歴の一覧を取得する."""
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT c.id, c.message_id, c.missing_points, c.suggested_reply,
                       c.is_copied, c.created_at, m.sender_name, m.content
                FROM consultations c
                LEFT JOIN messages m ON c.message_id = m.message_id
                ORDER BY c.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
            results: list[dict[str, Any]] = []
            for row in rows:
                item = dict(row)
                try:
                    item["missing_points"] = json.loads(item["missing_points"])
                except Exception:
                    item["missing_points"] = []
                item["is_copied"] = bool(item["is_copied"])
                results.append(item)
            return results

    def get_consultation_by_message_id(self, message_id: str) -> dict[str, Any] | None:
        """message_id に対応する相談レコードを取得する."""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT c.id, c.message_id, c.missing_points, c.suggested_reply,
                       c.is_copied, c.created_at, m.sender_name, m.content
                FROM consultations c
                LEFT JOIN messages m ON c.message_id = m.message_id
                WHERE c.message_id = ?
                ORDER BY c.id DESC
                LIMIT 1
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                return None
            item = dict(row)
            try:
                item["missing_points"] = json.loads(item["missing_points"])
            except Exception:
                item["missing_points"] = []
            item["is_copied"] = bool(item["is_copied"])
            return item

