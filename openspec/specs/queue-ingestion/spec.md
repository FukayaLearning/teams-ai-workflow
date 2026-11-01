
# queue-ingestion 要求仕様書

## ＜キューフォルダ管理＞

### OneDrive, ディレクトリ解決: 上位要求 R01


**要求**: OneDrive同期フォルダ配下のキューディレクトリ（`incoming`, `processed`, `failed`）を自動解決し、存在しない場合は自動生成できるようにしたい。
**理由**: 実行環境（法人用OneDrive、個人用OneDrive、ローカル検証環境）ごとに異なるパス設定の手間を省き、ディレクトリ未作成による実行時エラーを防ぐため。
**説明**: 設定ファイルの明示的パス指定を最優先し、未指定時はWindows環境変数から自動解決する。

###### ＜パス解決と初期化仕様＞

- ■■■ **S01-01**: 設定ファイルでキューパスが未指定または自動解決モードの場合、環境変数 `OneDriveCommercial`, `OneDriveConsumer`, `OneDrive`, `USERPROFILE` の優先順でベースパスを解決し、`TeamsQueue/incoming`, `TeamsQueue/processed`, `TeamsQueue/failed` の各パスを決定する。
- ■■■ **S01-02**: 設定ファイルに明示的なディレクトリパスが設定されている場合、その指定パスを `incoming`, `processed`, `failed` の各ディレクトリとして使用する。
- ■■■ **S01-03**: 解決された `incoming`, `processed`, `failed` ディレクトリが存在しない場合、初期化時にディレクトリを自動生成する。

## ＜メッセージ取り込み・永続化＞

### JSON検証, エラー退避: 上位要求 R02

**要求**: `incoming/` ディレクトリに配置されたTeamsメッセージのJSONファイルを読み込み、スキーマ検証と不正ファイルの退避を行えるようにしたい。
**理由**: Power Automateから連携されるJSONデータの欠損や破損によって監視プロセス全体が停止することを防ぐため。
**説明**: 必須フィールド（`message_id`, `sender_name`, `chat_type`, `content`, `received_at`）および任意フィールド（`sender_email`, `chat_name`, `is_mentioned`）を検証対象とする。

###### ＜JSON読み込み・スキーマ検証仕様＞

- ■■■ **S02-01**: `incoming/` ディレクトリ内の `.json` ファイルを検出し、必須フィールド（`message_id`, `sender_name`, `chat_type`, `content`, `received_at`）およびオプションフィールド（`sender_email`, `chat_name`, `is_mentioned`）を持つメッセージモデルとしてパース・検証し、後続の判定パイプラインへ渡す。
- ■■■ **S02-02**: 破損したJSONファイルまたは必須フィールドが欠落したJSONファイルを検出した場合、エラーログを記録した上で該当ファイルを `failed/` ディレクトリへ移動し、後続ファイルの処理を継続する。


### SQLite永続化, 重複排除: 上位要求 R03

**要求**: 処理対象のメッセージをローカルSQLiteデータベースに永続化し、同一メッセージの重複処理を防止できるようにしたい。
**理由**: OneDriveの同期タイミングや再実行時に、同じTeamsメッセージに対して複数回AI推論やデスクトップ通知が実行されるのを防ぐため。
**説明**: SQLiteデータベース（`teams_workflow.db`）の `messages` テーブルにおける `message_id` を一意キーとして管理する。

###### ＜永続化・重複排除・ファイル移動仕様＞

- ■■■ **S03-01**: 未処理の `message_id` を持つJSONファイルが正常に判定・アクション実行された場合、`messages` テーブルにメッセージ情報と判定結果を保存し、元のJSONファイルを `processed/` ディレクトリへ移動する。
- ■■■ **S03-02**: 既に `messages` テーブルに存在する `message_id` を持つJSONファイルが `incoming/` に配置された場合、AI判定および通知アクションをスキップし、該当ファイルを `processed/` ディレクトリへ移動する。
