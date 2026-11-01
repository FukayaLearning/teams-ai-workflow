## Context

`README.md` および `docs/TODO.md` で定義された「代替案A（OneDriveファイル自動同期 ＋ ローカルSQLite ＋ LM Studio Decisionモデル）」のアーキテクチャを実装する。背景・動機については `proposal.md` を参照。
特に `docs/TODO.md` の「2. 次回セッションに向けた残存検討事項 (Open Issues)」で挙げられている4つの技術的論点（①LM Studioのモデル選定とJSON出力安定性、②OneDriveフォルダのパス自動解決、③Power Automateの自己メッセージ除外・テナント設定、④Windows通知・クリップボードのライブラリ選定とクロスプラットフォーム検証性）を設計レベルで解決する。

## Goals / Non-Goals

**Goals:**
- `docs/TODO.md` の Step 1〜7 に定義された全モジュール・設定・テスト・ドキュメントを実装可能にする。
- Windows実機（OneDrive + LM Studio + トースト通知）でそのまま動作し、かつ開発・CI環境（Linux等）でもモックテスト・単体テストが100%動作する疎結合な設計とする。
- DeepSeek-R1蒸留モデルやQwen2.5等のローカルLLMが出力する `<think>...</think>` タグやMarkdownコードブロック付きJSONを堅牢にパース・リトライできる機構を備える。

**Non-Goals:**
- Microsoft Graph APIの直接呼び出しやWebhookサーバー（インバウンド通信）の構築（社内イントラ制約に反するため対象外）。
- Teamsへの自動メッセージ送信（誤送信リスクを避け、クリップボードへの自動コピー＋ユーザーの `Ctrl+V` 貼り付けまでをスコープとする）。

## Decisions

### 1. LM Studio クライアントと JSON 出力の安定化設計（残存検討事項①の解決）
- **決定**: 標準ライブラリまたは軽量な `httpx` を用いて OpenAI 互換エンドポイント（`POST /v1/chat/completions`）を呼び出す。モデルのレスポンスから以下の手順でJSONを抽出・検証する：
  1. `<think>...</think>` ブロックが含まれる場合は正規表現で除去する（DeepSeek-R1系モデル対策）。
  2. ````json ... ```` または最初の `{` から最後の `}` までを抽出して `json.loads()` および Pydantic の `DecisionResult.model_validate()` にかける。
  3. パースまたはバリデーション失敗時は、設定された `max_retries`（デフォルト2回）までエラーフィードバック付きでリトライする。
- **代替案との比較**: OpenAI公式SDKの `response_format={"type": "json_schema"}` のみに依存する案は、LM Studioのバージョンやローカルモデルによって未サポート・エラーになるケースがあるため、プロンプトでのJSON指示＋クライアント側での柔軟な抽出・リトライを併用する方式を採用した。

### 2. OneDrive ローカルフォルダパスの自動解決（残存検討事項②の解決）
- **決定**: `app/config.py` にて以下の優先順位でベースディレクトリを解決する：
  1. `config/settings.yaml` の `queue.base_dir` に明示的なパスが指定されていればそれを使用。
  2. `auto` または未指定の場合、環境変数 `OneDriveCommercial` → `OneDriveConsumer` → `OneDrive` の順で確認。
  3. 上記環境変数がない場合、`%USERPROFILE%`（または `Path.home()`）直下の `OneDrive - *` ディレクトリをグロブ検索し、見つからなければローカルの `./data/TeamsQueue` にフォールバックする。
- **理由**: 企業貸与PC（`OneDrive for Business`）では `%OneDriveCommercial%` が設定されるのが標準であり、ローカル開発・テスト時には相対パスへシームレスにフォールバックできるため。

### 3. Power Automate フローでの自己送信除外とテナント設計（残存検討事項③の解決）
- **決定**: 二重の安全策を採る。
  1. **クラウド側（Power Automate）**: トリガー条件または「条件」アクションにて、送信者のメールアドレス（またはユーザーID）が自分自身と一致する場合はOneDriveへのファイル作成をスキップする手順を `docs/power_automate_setup.md` に明記する。また、ゲスト参加している別テナントについてはTeamsコネクタの仕様上「テナントごとにフローを作成し同じOneDriveフォルダ（または共有フォルダ）へ出力する」運用手順を記載する。
  2. **ローカル側（`teams-ai-workflow`）**: `config/user_profile.yaml` に自分の氏名・メールアドレス（`self_emails`, `self_names`）を設定可能とし、万一自己送信メッセージが `incoming/` に届いた場合でも、LLM推論前に `ignore` として即時スキップできるようにする。

### 4. Windows通知・クリップボードのライブラリ選定（残存検討事項④の解決）
- **決定**:
  - **クリップボード**: 軽量で依存の少ない `pyperclip` を採用し、OSにクリップボード機構がない環境（ヘッドレスLinux等）で `PyperclipException` が発生した場合はメモリ内バッファ＋ログ出力にフォールバックする。
  - **デスクトップ通知**: Windows 10/11 ネイティブのトースト通知に対応した `windows-toasts`（またはWindows標準PowerShell/WinRT呼び出し・`plyer`）を利用可能としつつ、非Windows環境やインポート失敗時には標準ログ出力へ安全にフォールバックするアダプタ構造（`DesktopNotifier`）とする。

### 5. SQLite データベース管理
- **決定**: Python標準の `sqlite3` を使用し、`app/storage/database.py` で起動時に `CREATE TABLE IF NOT EXISTS` により `messages`, `tasks`, `consultations` の3テーブルを初期化する。外部ライブラリ（SQLAlchemy等）への依存を省き、ポータビリティと起動速度を高める。

### 6. Hermes Agent ハイブリッド統合設計（Python CLI + Hermes Skill）
- **決定**: 常駐監視ループ（`app/main.py`）だけでなく、Hermes Agent のツール実行および Cron ジョブからワンショット呼び出しできる CLI エントリポイント（`app/cli.py`）と Hermes Skill（`.hermes/skills/teams-workflow/SKILL.md` および `.agents/skills/teams-workflow/SKILL.md`）を提供する。
  - **CLIサブコマンド**:
    - `process-queue [--json]`: `incoming/` を1パス走査し、未処理ファイルのみ Decision Engine へかけて結果サマリを返す（未処理0件ならLLM呼び出しゼロで即終了）。
    - `list-tasks [--status todo|in_progress|done] [--json]` / `update-task <id> --status <status> [--json]`: タスクの参照・状態変更。
    - `list-consultations [--limit N] [--json]` / `copy-reply <message_id> [--text "..."]`: 相談履歴の参照、およびHermesとの対話で推敲した返信文のクリップボード反映。
- **代替案との比較**: ファイル監視やJSON抽出まで全てHermesのマルチターンTool Callingに委譲する案は、Cron起動のたびにLLMコンテキストを消費し、7B〜8BクラスのローカルLLMではツール呼び出しループが不安定になりやすい。コア処理をPython CLIにカプセル化し、HermesからはSkill経由でCLIを叩くハイブリッド方式により、省リソース・高安定性と対話的な拡張性を両立する。

## Risks / Trade-offs

- **[Risk] OneDrive同期中の不完全なJSONファイルの読み取り** → **Mitigation**: ファイル検知時、ファイルサイズが0バイトの場合やJSONパースが一時的に失敗した場合に備え、短い待機またはリトライ後に読み込みを行い、それでも不正な場合のみ `failed/` へ移動する。
- **[Risk] LM Studio が起動していない状態でのキュー処理** → **Mitigation**: LM Studio への接続エラー（`ConnectError`）時はファイルを `failed/` に即移動してロストさせるか、設定に応じて `incoming/` に残して次回ポーリングで再試行するかを選択可能にする（デフォルトはエラー詳細をログ出力し、明示的な処理失敗時は `failed/` へ移動してループ詰まりを防ぐ）。

