# queue-ingestion Specification

## Purpose

Power AutomateによってOneDrive同期フォルダ（`TeamsQueue/incoming/`）に配置されたTeamsメッセージのJSONファイルを検知・検証・永続化し、重複処理を防止しつつ処理ステータス（`processed/` または `failed/`）に応じたファイルライフサイクルを管理する。

## Requirements

### Requirement: OneDrive キューフォルダパスの自動解決と初期化
システムは、設定ファイルの明示的なパス指定またはWindows環境変数（`OneDriveCommercial`, `OneDriveConsumer`, `OneDrive`, `USERPROFILE`）から `TeamsQueue/incoming`, `TeamsQueue/processed`, `TeamsQueue/failed` の各ディレクトリパスを解決し、存在しない場合は自動生成しなければならない（SHALL）。

#### Scenario: 環境変数からOneDriveパスを自動解決する
- **WHEN** 設定ファイルでキューパスが未指定または自動解決モードであり、環境変数 `OneDriveCommercial` が設定されている
- **THEN** `%OneDriveCommercial%/TeamsQueue/incoming`（および `processed`, `failed`）が監視対象ディレクトリとして解決・作成される

#### Scenario: 明示的なローカルパスを使用する
- **WHEN** 設定ファイルに明示的なディレクトリパスが設定されている
- **THEN** 指定されたパス配下の `incoming`, `processed`, `failed` ディレクトリが作成・使用される

### Requirement: キューJSONファイルの読み込みとスキーマ検証
システムは、`incoming/` ディレクトリ内の `.json` ファイルを検出し、必須フィールド（`message_id`, `sender_name`, `chat_type`, `content`, `received_at`）およびオプションフィールド（`sender_email`, `chat_name`, `is_mentioned`）を持つメッセージモデルとして検証しなければならない（SHALL）。

#### Scenario: 正常なメッセージJSONの読み込み
- **WHEN** `incoming/` に仕様通りの必須フィールドを含むJSONファイルが配置される
- **THEN** システムはJSONをパースして構造化データとして読み込み、後続の判定パイプラインへ渡す

#### Scenario: 不正なJSONフォーマットまたはスキーマ違反ファイルの退避
- **WHEN** `incoming/` に破損したJSONファイルまたは必須フィールドが欠落したJSONファイルが配置される
- **THEN** システムはエラーログを記録し、該当ファイルを `failed/` ディレクトリへ移動して監視ループを継続する

### Requirement: メッセージのSQLite永続化と重複排除
システムは、処理対象のメッセージをSQLiteデータベース（`teams_workflow.db` の `messages` テーブル）に記録し、同一 `message_id` のメッセージが既に処理済みの場合はAI推論や通知を再実行せずに重複排除しなければならない（SHALL）。

#### Scenario: 新規メッセージの処理完了と移動
- **WHEN** 未処理の `message_id` を持つJSONファイルが正常に判定・アクション実行された
- **THEN** `messages` テーブルに判定結果とともに保存され、元のJSONファイルは `processed/` ディレクトリへ移動される

#### Scenario: 処理済みmessage_idの重複検知
- **WHEN** 既に `messages` テーブルに存在する `message_id` を持つJSONファイルが `incoming/` に配置された
- **THEN** システムはAI判定および通知アクションをスキップし、該当ファイルを `processed/` ディレクトリへ移動する

