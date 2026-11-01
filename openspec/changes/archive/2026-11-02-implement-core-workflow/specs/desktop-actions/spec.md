## Purpose

Decision Engineの判定結果に応じて、ローカルSQLiteデータベースへのタスク・相談履歴の記録、Windowsデスクトップ通知（トースト）の表示、およびクリップボードへの返信案自動コピーを実行し、ユーザーが最小の手間でTeams返信やタスク管理を行えるようにする。

## ADDED Requirements

### Requirement: 相談判定時の履歴保存・クリップボード自動コピー・デスクトップ通知
システムは、判定結果が `consultation` の場合、`consultations` テーブルに不足情報と返信案を保存し、返信案（`suggested_reply`）をクリップボードに自動コピーした上で、デスクトップ通知を表示しなければならない（SHALL）。

#### Scenario: 相談メッセージ受信時のアクション実行
- **WHEN** メッセージが `action_type: "consultation"` と判定された
- **THEN** `consultations` テーブルにレコードが保存され、`suggested_reply` がOSクリップボードにコピー（および `is_copied` フラグが記録）され、`【相談受信】<送信者名>さんからの相談に対する質問案を作成しました` という通知が表示される

### Requirement: タスク判定時のSQLite登録とデスクトップ通知
システムは、判定結果が `task` の場合、`tasks` テーブルにステータス `todo` でタスクを登録し、タスク登録完了のデスクトップ通知を表示しなければならない（SHALL）。

#### Scenario: タスク依頼メッセージ受信時のアクション実行
- **WHEN** メッセージが `action_type: "task"` と判定された
- **THEN** `tasks` テーブルに `status: "todo"` でレコードが作成され、`【タスク登録】「<タスク件名>」をToDoに登録しました` という通知が表示される

### Requirement: 無関係・情報共有メッセージの静音処理
システムは、判定結果が `ignore` の場合は通知やクリップボード操作を行わず、`messages` テーブルへのログ保存のみを行わなければならない（SHALL）。

#### Scenario: 無関係なメッセージのスキップ
- **WHEN** メッセージが `action_type: "ignore"` と判定された
- **THEN** デスクトップ通知やクリップボード更新は実行されず、`messages` テーブルに履歴のみが保存される

### Requirement: 非Windows・ヘッドレス環境での安全なフォールバック
システムは、Windows通知ライブラリやクリップボード機構が利用できない環境（テスト実行環境やLinux開発環境など）でも例外で停止せず、ログ出力およびモック可能なインターフェースへ安全にフォールバックしなければならない（SHALL）。

#### Scenario: GUI・クリップボード非対応環境での実行
- **WHEN** トースト通知またはクリップボード操作がOS環境制約により利用できない状態でアクションが呼び出された
- **THEN** システムは警告または標準ログへ通知内容を出力し、データベース保存およびファイル移動処理を正常に完了させる

### Requirement: Power Automate フロー構築手順の提供
システムは、クラウド側のPower AutomateでTeamsメッセージを受信してOneDriveの `/TeamsQueue/incoming/{message_id}.json` を作成するための設定手順（自分自身が送信したメッセージの除外条件、1on1/グループチャット/チャネル/別テナントの考慮事項を含む）をドキュメントとして提供しなければならない（SHALL）。

#### Scenario: Power Automate手順書の参照
- **WHEN** ユーザーが `docs/power_automate_setup.md` を参照する
- **THEN** トリガー設定、自己送信メッセージの除外条件式、OneDriveファイル作成アクションのJSONテンプレート、および別テナント参加時の留意事項が確認できる

### Requirement: Hermes Agent 連携用 CLI と Skill インターフェースの提供
システムは、Hermes Agent（対話セッションおよびCronジョブ）から呼び出し可能なCLIサブコマンド（`process-queue`, `list-tasks`, `update-task`, `list-consultations`, `copy-reply`）をJSON出力対応で提供し、Hermes AgentがそのCLIを用いてTeamsの未処理キュー処理・タスク管理・相談返信案の操作を行えるSkill定義（`.hermes/skills/teams-workflow/SKILL.md`）を備えなければならない（SHALL）。

#### Scenario: Hermes Agent または Cron からのワンショットキュー処理
- **WHEN** `python -m app.cli process-queue --json` が実行される
- **THEN** `incoming/` 内の未処理JSONファイルがすべて処理され、処理件数・相談件数・タスク登録件数のサマリがJSON形式で標準出力へ返却される

#### Scenario: Hermes Agent からのタスク一覧照会とステータス更新
- **WHEN** `python -m app.cli list-tasks --status todo --json` および `python -m app.cli update-task <id> --status done --json` が実行される
- **THEN** SQLite `tasks` テーブルから該当タスク一覧がJSON出力され、指定タスクのステータスが更新される

#### Scenario: Hermes Agent からの相談履歴照会と返信案の再コピー
- **WHEN** `python -m app.cli list-consultations --json` または `python -m app.cli copy-reply <message_id> [--text "<修正文案>"]` が実行される
- **THEN** 相談履歴がJSON出力され、指定された返信案（またはHermes上でブラッシュアップされた返信文）がクリップボードにコピーされる

