## Why

現在、`README.md` および `docs/TODO.md` にて「OneDriveファイル同期 ＋ ローカルSQLite ＋ LM Studio Decisionモデル」による `teams-ai-workflow` の全体アーキテクチャおよび仕様が確定しているが、実装コード・設定ファイル・テスト・セットアップ手順書が未作成（TODO状態）となっている。社内イントラ環境でTeamsメッセージを取りこぼさずAI判定（相談に対するヒアリング質問生成・タスク自動登録）を行うため、`docs/TODO.md` に記載された残存検討事項および実装ロードマップ（Step 1〜7）を解消し、システム一式を実装する。

## What Changes

- **設定・データスキーマの追加 (Step 1)**:
  - `config/settings.yaml` / `config/settings.yaml.example`（LM Studio接続先、OneDrive環境変数からのローカルパス自動解決を含むフォルダ設定）
  - `config/user_profile.yaml` / `config/user_profile.yaml.example`（担当業務・役職・キーワード定義）
  - `app/config.py`（設定読み込みとパス解決）
  - `app/schemas.py`（入力キューJSONモデル、LLM出力の構造化Pydanticモデル）
- **SQLiteデータベース層の追加 (Step 2)**:
  - `app/storage/database.py`（`teams_workflow.db` の `messages`, `tasks`, `consultations` テーブル初期化）
  - `app/storage/repository.py`（メッセージ重複チェック、タスク登録、相談履歴保存などのCRUD操作）
- **キューウォッチャーの追加 (Step 3)**:
  - `app/watcher/queue_watcher.py`（`TeamsQueue/incoming/` の監視・JSON読み取り、`processed/` および `failed/` への移動処理）
- **LM Studio連携 & Decision Engine の追加 (Step 4)**:
  - `app/ai/lm_studio_client.py`（OpenAI互換APIクライアント、JSON出力パース失敗時のリトライ・フォールバック処理）
  - `app/ai/prompts.py`（ユーザープロファイルに基づく関与度判定・相談の不足情報特定・タスク抽出プロンプト）
  - `app/ai/decision_engine.py`（推論実行とPydanticスキーマ検証）
- **Windowsアクション層の追加 (Step 5)**:
  - `app/actions/desktop_notifier.py`（トースト通知表示および非Windows/ヘッドレス環境向けのフォールバック）
  - `app/actions/clipboard_helper.py`（`pyperclip` 等を用いたクリップボード自動コピーとフォールバック）
  - `app/main.py` および `run.bat` / `requirements.txt`（メイン常駐ループ・ワンクリック実行手段）
- **Hermes Agent ハイブリッド連携の追加**:
  - `app/cli.py`（Hermes Agent や Cron から呼び出し可能なサブコマンド群：`process-queue`, `list-tasks`, `update-task`, `list-consultations`, `copy-reply` のJSON/テキスト出力対応CLI）
  - `.hermes/skills/teams-workflow/SKILL.md`（および `.agents/skills/teams-workflow/SKILL.md`：Hermes Agent からTeamsキュー処理・タスク管理・相談返信ドラフト調整を対話実行・Cron定期実行するためのSkill定義）
- **モックテストとドキュメントの整備 (Step 6 & Step 7)**:
  - `tests/`（サンプルJSON投入からDB登録・通知・クリップボード連携までの検証テスト）
  - `docs/power_automate_setup.md`（自分自身のメッセージ除外条件やテナント設定を含むPower Automate設定手順書）
  - `README.md` への仕様統合および解決済みとなった `docs/TODO.md` の削除

## Capabilities

### New Capabilities
- `queue-ingestion`: OneDrive同期フォルダ（`TeamsQueue/incoming/`）のパス解決、未処理JSONの検知・読み込み、SQLiteへの永続化・重複排除、および `processed/`・`failed/` へのファイル移動管理
- `decision-engine`: ユーザープロファイルとLM Studio（OpenAI互換ローカルLLM）を用いた関与度・意図分類（`consultation` / `task` / `info` / `ignore`）、ヒアリング質問生成、タスク構造化抽出、およびJSONパースリトライ制御
- `desktop-actions`: 判定結果に応じたWindowsデスクトップ通知（トースト）、相談返信案のクリップボード自動コピー、タスクのSQLite `tasks` テーブル登録、Hermes Agent連携用CLI・Skillインターフェース、およびPower Automate連携セットアップ手順

### Modified Capabilities
<!-- 既存のCapabilityはなし -->

## Impact

- 新規追加モジュール: `app/` 配下一式（`config.py`, `schemas.py`, `main.py`, `cli.py`, `storage/`, `watcher/`, `ai/`, `actions/`）
- Hermes Agent スキル定義: `.hermes/skills/teams-workflow/SKILL.md`, `.agents/skills/teams-workflow/SKILL.md`
- 設定・スクリプト: `config/settings.yaml.example`, `config/user_profile.yaml.example`, `requirements.txt`, `run.bat`
- テスト・ドキュメント: `tests/`, `docs/power_automate_setup.md`, `docs/TODO.md`
- 依存パッケージ: `pydantic`, `pyyaml`, `httpx` (または `openai`), `pyperclip`, `windows-toasts` (または通知ライブラリ), `pytest`

