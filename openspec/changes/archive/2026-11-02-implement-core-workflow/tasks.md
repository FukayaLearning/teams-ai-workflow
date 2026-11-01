## 1. 設定ファイルとデータスキーマの作成 (Step 1)

- [x] 1.1 `requirements.txt` および `run.bat` を作成し、必要な依存関係（`pydantic`, `pyyaml`, `httpx`, `pyperclip`, `pytest` 等）が定義されていることを確認する
- [x] 1.2 `config/settings.yaml.example`, `config/settings.yaml`, `config/user_profile.yaml.example`, `config/user_profile.yaml` を作成し、YAMLとして正しく読み込めることを確認する
- [x] 1.3 `app/__init__.py` および `app/config.py` を実装し、OneDrive環境変数（`OneDriveCommercial` 等）からの自動パス解決および設定読み込みの単体テストがパスすることを確認する
- [x] 1.4 `app/schemas.py` を実装し、入力キューJSONモデル（`IncomingMessage`）およびLLM出力モデル（`DecisionResult`, `ConsultationDetail`, `TaskDetail`）のPydanticバリデーションテストがパスすることを確認する

## 2. SQLiteデータベース層の実装 (Step 2)

- [x] 2.1 `app/storage/__init__.py` および `app/storage/database.py` を実装し、`messages`, `tasks`, `consultations` の3テーブルが初期化されることを単体テストで確認する
- [x] 2.2 `app/storage/repository.py` を実装し、メッセージ保存・`message_id` 重複チェック・タスク登録・相談履歴登録の各CRUD操作が動作することを単体テストで確認する

## 3. キューウォッチャーの実装 (Step 3)

- [x] 3.1 `app/watcher/__init__.py` および `app/watcher/queue_watcher.py` を実装し、`incoming/` のJSONファイル検知・読み込み、`processed/` および `failed/` へのファイル移動が正しく行われることを単体テストで確認する

## 4. LM Studio 連携 ＆ Decision Engine の実装 (Step 4)

- [x] 4.1 `app/ai/__init__.py` および `app/ai/prompts.py` を実装し、ユーザープロファイルを埋め込んだシステムプロンプト・ユーザープロンプトが生成されることを確認する
- [x] 4.2 `app/ai/lm_studio_client.py` を実装し、OpenAI互換API呼び出しと `<think>` タグ・Markdownコードブロック除去を含むJSON抽出およびリトライ処理が単体テストでパスすることを確認する
- [x] 4.3 `app/ai/decision_engine.py` を実装し、自己送信メッセージの即時スキップおよび `consultation` / `task` / `info` / `ignore` の判定パイプラインが単体テストでパスすることを確認する

## 5. Windowsアクション層・CLI・Hermes Skillの実装 (Step 5)

- [x] 5.1 `app/actions/__init__.py`, `app/actions/clipboard_helper.py`, `app/actions/desktop_notifier.py` を実装し、通知・クリップボードコピーおよび非対応環境でのフォールバック動作を単体テストで確認する
- [x] 5.2 `app/main.py` を実装し、ウォッチャー・Decision Engine・DB保存・アクション実行を一連のワークフローとして統合処理できることを確認する
- [x] 5.3 `app/cli.py` を実装し、`process-queue`, `list-tasks`, `update-task`, `list-consultations`, `copy-reply` の各サブコマンドが `--json` 出力込みで動作することを単体テストで確認する
- [x] 5.4 `.hermes/skills/teams-workflow/SKILL.md`（および `.agents/skills/teams-workflow/SKILL.md`）を作成し、Hermes Agent からキュー処理・タスク管理・相談返信ブラッシュアップやCron登録を行う手順が定義されていることを確認する

## 6. モックテストとドキュメント整備 (Step 6 & Step 7)

- [x] 6.1 `tests/` にエンドツーエンドのモックテスト（相談・タスク・無関係・重複・不正JSONの各シナリオ）を実装し、`pytest` で全テストがパスすることを確認する
- [x] 6.2 `docs/power_automate_setup.md` を作成し、Power Automateトリガー設定、自己送信メッセージ除外条件、JSONフォーマット、別テナント運用の手順が記載されていることを確認する
- [x] 6.3 `docs/TODO.md` の解決済み仕様を `README.md` および `docs/power_automate_setup.md` に統合した上で `docs/TODO.md` を削除し、未解決のTODOが残っていないことを確認する

