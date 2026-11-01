"""teams-ai-workflow の単体テストおよびエンドツーエンドモックテスト一式."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

from app.actions.clipboard_helper import ClipboardHelper
from app.actions.desktop_notifier import DesktopNotifier
from app.ai.decision_engine import DecisionEngine
from app.ai.lm_studio_client import LMStudioClient, LMStudioError, extract_json_object
from app.ai.prompts import build_system_prompt, build_user_prompt
from app.cli import run_cli
from app.config import (
    AppSettings,
    DatabaseConfig,
    LMStudioConfig,
    QueueConfig,
    UserProfile,
    load_settings,
    resolve_queue_directories,
)
from app.main import WorkflowProcessor
from app.schemas import DecisionResult, IncomingMessage
from app.storage.repository import WorkflowRepository
from app.watcher.queue_watcher import QueueFileReadError, QueueWatcher


class TestConfigAndSchemas(unittest.TestCase):
    """Step 1: 設定ファイル・OneDriveパス解決・Pydanticスキーマのテスト."""

    def test_load_default_yaml_files(self) -> None:
        settings = load_settings("config/settings.yaml", "config/user_profile.yaml")
        self.assertEqual(settings.lm_studio.base_url, "http://127.0.0.1:1234/v1")
        self.assertEqual(settings.queue.queue_folder_name, "TeamsQueue")
        self.assertTrue(len(settings.user_profile.responsibilities) > 0)
        self.assertTrue(settings.user_profile.is_self_sender("佐藤 健太"))
        self.assertTrue(
            settings.user_profile.is_self_sender("Other Name", "kenta.sato@example.com")
        )
        self.assertFalse(
            settings.user_profile.is_self_sender("山田 太郎", "yamada@example.com")
        )

    def test_resolve_queue_directories_from_onedrive_commercial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fake_onedrive = Path(tmp) / "OneDrive - ExampleCorp"
            queue_cfg = QueueConfig(base_dir="auto", queue_folder_name="TeamsQueue")
            dirs = resolve_queue_directories(
                queue_cfg,
                environ={"OneDriveCommercial": str(fake_onedrive)},
                ensure_exists=True,
            )
            self.assertEqual(dirs.root, fake_onedrive / "TeamsQueue")
            self.assertTrue(dirs.incoming.is_dir())
            self.assertTrue(dirs.processed.is_dir())
            self.assertTrue(dirs.failed.is_dir())

    def test_resolve_queue_directories_explicit_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            explicit = Path(tmp) / "CustomQueue"
            queue_cfg = QueueConfig(base_dir=str(explicit), queue_folder_name="TeamsQueue")
            dirs = resolve_queue_directories(queue_cfg, ensure_exists=True)
            self.assertEqual(dirs.root, explicit / "TeamsQueue")
            self.assertTrue(dirs.incoming.exists())

    def test_incoming_message_and_decision_schemas(self) -> None:
        msg = IncomingMessage.model_validate(
            {
                "message_id": "1730345678901",
                "sender_name": "山田 太郎",
                "sender_email": "yamada.taro@example.com",
                "chat_type": "group",
                "chat_name": "プロジェクトX 連絡用",
                "is_mentioned": False,
                "content": "ステージング環境でAPIエラーが出ています。",
                "received_at": "2026-10-31T15:20:00Z",
            }
        )
        self.assertEqual(msg.message_id, "1730345678901")

        decision = DecisionResult.model_validate(
            {
                "is_relevant": True,
                "action_type": "task",
                "reasoning": "証明書更新の依頼",
                "task": {
                    "title": "証明書更新",
                    "description": "ステージング環境のSSL証明書更新",
                    "due_date": "2026-11-05",
                    "priority": "HIGH",
                },
            }
        )
        self.assertEqual(decision.task.priority, "high")


class TestDatabaseAndRepository(unittest.TestCase):
    """Step 2: SQLiteデータベースとRepository CRUDのテスト."""

    def test_repository_crud_operations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            db_path = Path(tmp) / "test_workflow.db"
            repo = WorkflowRepository(db_path)

            msg = IncomingMessage(
                message_id="msg-100",
                sender_name="鈴木 一郎",
                chat_type="1on1",
                content="本番デプロイ手順の相談です",
                received_at="2026-10-31T10:00:00Z",
            )
            decision = DecisionResult(
                is_relevant=True,
                action_type="consultation",
                reasoning="担当インフラの相談",
            )

            self.assertFalse(repo.is_message_processed("msg-100"))
            repo.save_message(msg, decision, raw_json="{}")
            self.assertTrue(repo.is_message_processed("msg-100"))

            repo.save_consultation(
                message_id="msg-100",
                missing_points=["対象サービス名", "希望日時"],
                suggested_reply="対象サービス名と希望日時を教えてください。",
                is_copied=True,
            )
            consultations = repo.list_consultations()
            self.assertEqual(len(consultations), 1)
            self.assertEqual(consultations[0]["missing_points"], ["対象サービス名", "希望日時"])

            task_id = repo.save_task(
                message_id="msg-100",
                title="デプロイ手順書確認",
                description="手順書レビュー",
                due_date="2026-11-10",
                priority="high",
            )
            todo_tasks = repo.list_tasks(status="todo")
            self.assertEqual(len(todo_tasks), 1)
            self.assertEqual(todo_tasks[0]["id"], task_id)

            updated = repo.update_task_status(task_id, "done")
            self.assertTrue(updated)
            self.assertEqual(len(repo.list_tasks(status="todo")), 0)
            self.assertEqual(len(repo.list_tasks(status="done")), 1)


class TestLMStudioAndDecisionEngine(unittest.TestCase):
    """Step 4: LM Studio JSON抽出・リトライおよびDecision Engineのテスト."""

    def test_extract_json_with_think_tags_and_fences(self) -> None:
        raw_output = """
        <think>
        ユーザーはバックエンド担当なのでAPIエラーは関連あり。
        </think>
        以下の通り判定しました：
        ```json
        {
          "is_relevant": true,
          "action_type": "consultation",
          "reasoning": "APIエラーに関する相談",
          "consultation": {
            "missing_points": ["エラーログ"],
            "suggested_reply": "エラーログを共有いただけますか？"
          },
          "task": {
            "title": "",
            "description": "",
            "due_date": null,
            "priority": "normal"
          }
        }
        ```
        """
        extracted = extract_json_object(raw_output)
        self.assertTrue(extracted["is_relevant"])
        self.assertEqual(extracted["action_type"], "consultation")

    def test_lm_studio_client_retry_on_invalid_json(self) -> None:
        responses = [
            "これは不正なJSON出力です {broken",
            json.dumps(
                {
                    "is_relevant": True,
                    "action_type": "task",
                    "reasoning": "リトライ成功",
                    "task": {
                        "title": "DBインデックス追加",
                        "description": "ordersテーブルへのインデックス追加",
                        "due_date": "2026-11-03",
                        "priority": "high",
                    },
                },
                ensure_ascii=False,
            ),
        ]
        call_count = 0

        def fake_transport(payload: dict[str, Any]) -> str:
            nonlocal call_count
            idx = call_count
            call_count += 1
            return responses[idx]

        client = LMStudioClient(
            LMStudioConfig(max_retries=2),
            transport_fn=fake_transport,
        )
        result = client.request_decision("system", "user")
        self.assertEqual(call_count, 2)
        self.assertEqual(result.action_type, "task")
        self.assertEqual(result.task.title, "DBインデックス追加")

    def test_decision_engine_skips_self_message_without_llm_call(self) -> None:
        def fail_if_called(payload: dict[str, Any]) -> str:
            raise AssertionError("LLM should not be called for self-sent messages")

        profile = UserProfile(
            name="佐藤 健太",
            self_emails=["kenta.sato@example.com"],
        )
        engine = DecisionEngine(
            client=LMStudioClient(LMStudioConfig(), transport_fn=fail_if_called),
            user_profile=profile,
        )
        msg = IncomingMessage(
            message_id="self-001",
            sender_name="佐藤 健太",
            sender_email="kenta.sato@example.com",
            chat_type="group",
            content="私からの連絡です",
            received_at="2026-10-31T12:00:00Z",
        )
        decision = engine.evaluate(msg)
        self.assertFalse(decision.is_relevant)
        self.assertEqual(decision.action_type, "ignore")


class TestEndToEndWorkflowAndCLI(unittest.TestCase):
    """Step 3, 5, 6: ウォッチャー・アクション・エンドツーエンド統合・Hermes CLIのテスト."""

    def test_full_workflow_and_cli_subcommands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            queue_cfg = QueueConfig(base_dir=str(tmp_path), queue_folder_name="TeamsQueue")
            dirs = resolve_queue_directories(queue_cfg, ensure_exists=True)
            db_path = tmp_path / "teams_workflow.db"

            # 1. 相談メッセージ
            (dirs.incoming / "01_consultation.json").write_text(
                json.dumps(
                    {
                        "message_id": "msg-consult-1",
                        "sender_name": "山田 太郎",
                        "sender_email": "yamada@example.com",
                        "chat_type": "group",
                        "chat_name": "開発チャネル",
                        "is_mentioned": False,
                        "content": "昨日の夜からステージング環境でAPIエラーが多発しています。確認できますか？",
                        "received_at": "2026-10-31T15:20:00Z",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            # 2. タスク依頼メッセージ
            (dirs.incoming / "02_task.json").write_text(
                json.dumps(
                    {
                        "message_id": "msg-task-1",
                        "sender_name": "高橋 花子",
                        "chat_type": "1on1",
                        "is_mentioned": True,
                        "content": "来週金曜までにステージング環境のSSL証明書更新をお願いします。",
                        "received_at": "2026-10-31T15:25:00Z",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            # 3. 無関係な雑談メッセージ
            (dirs.incoming / "03_ignore.json").write_text(
                json.dumps(
                    {
                        "message_id": "msg-ignore-1",
                        "sender_name": "総務部",
                        "chat_type": "channel",
                        "is_mentioned": False,
                        "content": "本日のオフィス清掃は18時から実施します。",
                        "received_at": "2026-10-31T15:30:00Z",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            # 4. 重複メッセージ (msg-consult-1 と同じ message_id)
            (dirs.incoming / "04_duplicate.json").write_text(
                json.dumps(
                    {
                        "message_id": "msg-consult-1",
                        "sender_name": "山田 太郎",
                        "chat_type": "group",
                        "content": "重複ファイル",
                        "received_at": "2026-10-31T15:20:00Z",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            # 5. 破損した不正JSONファイル
            (dirs.incoming / "05_broken.json").write_text(
                "{invalid json file",
                encoding="utf-8",
            )

            def mock_llm_transport(payload: dict[str, Any]) -> str:
                user_text = payload["messages"][1]["content"]
                if "msg-consult-1" in user_text:
                    return json.dumps(
                        {
                            "is_relevant": True,
                            "action_type": "consultation",
                            "reasoning": "担当領域のAPI障害相談",
                            "consultation": {
                                "missing_points": ["具体的なステータスコード", "対象エンドポイント"],
                                "suggested_reply": "お疲れ様です。ステータスコードとエンドポイントを教えていただけますか？",
                            },
                        },
                        ensure_ascii=False,
                    )
                if "msg-task-1" in user_text:
                    return json.dumps(
                        {
                            "is_relevant": True,
                            "action_type": "task",
                            "reasoning": "SSL証明書更新の明確な依頼",
                            "task": {
                                "title": "ステージング環境SSL証明書更新",
                                "description": "来週金曜までに証明書を更新する",
                                "due_date": "2026-11-06",
                                "priority": "high",
                            },
                        },
                        ensure_ascii=False,
                    )
                return json.dumps(
                    {
                        "is_relevant": False,
                        "action_type": "ignore",
                        "reasoning": "総務の清掃連絡のため対象外",
                    },
                    ensure_ascii=False,
                )

            settings = AppSettings(
                lm_studio=LMStudioConfig(),
                queue=queue_cfg,
                database=DatabaseConfig(path=str(db_path)),
                user_profile=UserProfile(name="佐藤 健太", role="SRE"),
            )

            watcher = QueueWatcher(dirs)
            repo = WorkflowRepository(db_path)
            client = LMStudioClient(settings.lm_studio, transport_fn=mock_llm_transport)
            engine = DecisionEngine(client, settings.user_profile)
            copied_texts: list[str] = []
            notifications: list[tuple[str, str]] = []
            clipboard = ClipboardHelper(enabled=True, copy_backend=copied_texts.append)
            notifier = DesktopNotifier(
                enabled=True,
                notify_backend=lambda title, body: notifications.append((title, body)),
            )

            processor = WorkflowProcessor(
                watcher=watcher,
                repository=repo,
                decision_engine=engine,
                notifier=notifier,
                clipboard=clipboard,
            )

            # CLI: process-queue --json
            buf = io.StringIO()
            with redirect_stdout(buf):
                exit_code = run_cli(
                    ["process-queue", "--json"],
                    settings_override=settings,
                    processor_override=processor,
                )
            self.assertEqual(exit_code, 0)
            summary = json.loads(buf.getvalue())
            self.assertEqual(summary["scanned_files"], 5)
            self.assertEqual(summary["processed_count"], 3)
            self.assertEqual(summary["duplicate_skipped_count"], 1)
            self.assertEqual(summary["failed_count"], 1)
            self.assertEqual(summary["consultations_count"], 1)
            self.assertEqual(summary["tasks_count"], 1)
            self.assertEqual(summary["ignored_count"], 1)

            # ファイル移動の確認
            self.assertEqual(len(list(dirs.incoming.glob("*.json"))), 0)
            self.assertEqual(len(list(dirs.processed.glob("*.json"))), 4)
            self.assertEqual(len(list(dirs.failed.glob("*.json"))), 1)

            # 通知とクリップボードの確認
            self.assertEqual(len(copied_texts), 1)
            self.assertIn("ステータスコード", copied_texts[0])
            self.assertEqual(len(notifications), 2)
            self.assertIn("【相談受信】山田 太郎さん", notifications[0][0])
            self.assertIn("【タスク登録】「ステージング環境SSL証明書更新」", notifications[1][0])

            # CLI: list-tasks --status todo --json
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_cli(["list-tasks", "--status", "todo", "--json"], settings_override=settings)
            tasks_out = json.loads(buf.getvalue())
            self.assertEqual(tasks_out["count"], 1)
            task_id = tasks_out["tasks"][0]["id"]

            # CLI: update-task <id> --status done --json
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_cli(
                    ["update-task", str(task_id), "--status", "done", "--json"],
                    settings_override=settings,
                )
            update_out = json.loads(buf.getvalue())
            self.assertTrue(update_out["updated"])

            # CLI: list-consultations --json
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_cli(["list-consultations", "--json"], settings_override=settings)
            consult_out = json.loads(buf.getvalue())
            self.assertEqual(consult_out["count"], 1)

            # CLI: copy-reply <message_id> --text "..." --json
            buf = io.StringIO()
            with redirect_stdout(buf):
                run_cli(
                    [
                        "copy-reply",
                        "msg-consult-1",
                        "--text",
                        "修正後の丁寧な返信案です。",
                        "--json",
                    ],
                    settings_override=settings,
                )
            copy_out = json.loads(buf.getvalue())
            self.assertTrue(copy_out["copied"])
            self.assertEqual(copy_out["suggested_reply"], "修正後の丁寧な返信案です。")


if __name__ == "__main__":
    unittest.main()

