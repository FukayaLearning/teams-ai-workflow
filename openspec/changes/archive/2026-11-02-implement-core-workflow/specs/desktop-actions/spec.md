
# desktop-actions 要求仕様書


## ＜デスクトップ通知・ローカルDB連携＞


### 相談通知, クリップボード連携: 上位要求 R01

**要求**: 相談（`consultation`）と判定されたメッセージについて、相談履歴をDBに保存し、返信質問案をクリップボードへ自動コピーした上でデスクトップ通知を表示したい。
**理由**: ユーザーが通知を確認した直後にTeamsウィンドウで `Ctrl + V` を押すだけでヒアリング返信を完了できるようにするため。
**説明**: SQLiteの `consultations` テーブルへの保存、OSクリップボード更新、Windowsトースト通知を連携して実行する。


###### ＜相談アクション実行仕様＞

- ■■■ **S01-01**: 判定結果が `action_type: "consultation"` の場合、`consultations` テーブルに `message_id`, `missing_points`, `suggested_reply`, `is_copied` を保存する。
- ■■■ **S01-02**: 生成された `suggested_reply` をOSクリップボードへ自動コピーし、`【相談受信】<送信者名>さんからの相談に対する質問案を作成しました` というデスクトップ通知を表示する。


### タスク登録, 通知: 上位要求 R02

  **要求**: タスク（`task`）と判定されたメッセージについて、SQLiteデータベースへ未完了タスクとして自動登録し、デスクトップ通知を表示したい。
  **理由**: Teamsで受けた作業依頼の登録漏れを防ぎ、ユーザーにタスク追加を即時把握させるため。
  **説明**: SQLiteの `tasks` テーブルへ初期ステータス `todo` で登録する。

###### ＜タスク登録アクション仕様＞

- ■■■ **S02-01**: 判定結果が `action_type: "task"` の場合、`tasks` テーブルに `title`, `description`, `due_date`, `priority` および `status: "todo"` でレコードを作成し、`【タスク登録】「<タスク件名>」をToDoに登録しました` というデスクトップ通知を表示する。

### 静音処理, 非Windows環境フォールバック: 上位要求 R03

**要求**: 無関係なメッセージは通知せず静かに記録し、またGUIやクリップボードが利用できない非Windows・ヘッドレス環境でもエラー停止せず動作するようにしたい。
**理由**: 不要な通知による集中阻害を防ぎつつ、WSL/Linux開発環境やCIテスト環境でも同一コードベースで安全にパイプラインを実行できるようにするため。
**説明**: `ignore` 判定時のスキップ制御と、OS依存機能（トースト通知・クリップボード）失敗時のログフォールバックを行う。

###### ＜静音処理・環境フォールバック仕様＞

- ■■■ **S03-01**: 判定結果が `action_type: "ignore"` の場合、デスクトップ通知やクリップボード更新は実行せず、`messages` テーブルへの履歴保存のみを行う。
- ■■■ **S03-02**: Windows通知ライブラリやクリップボード機構が利用できない環境でアクションが呼び出された場合、例外で停止せず標準ログまたは警告ログへ出力してフォールバックし、DB保存およびファイル移動処理を正常に完了させる。

## ＜外部システム・エージェント連携＞


### Power Automate, クラウドフロー手順: 上位要求 R04

**要求**: クラウド側のPower AutomateでTeamsメッセージを受信してOneDriveキューへJSON出力するための構築手順書を提供したい。
**理由**: 管理者権限やAzure Bot登録が不要な標準コネクタのみで、自己送信ループを防ぎつつ1on1・グループ・チャネル・外部テナントのメッセージを収集できるようにするため。
**説明**: `docs/power_automate_setup.md` にトリガー・条件式・JSONテンプレート・運用上の注意点を記載する。


###### ＜Power Automate構築ドキュメント仕様＞

- ■■■ **S04-01**: `docs/power_automate_setup.md` に、Teamsトリガー設定、自己送信メッセージの除外条件、OneDrive `/TeamsQueue/incoming/{message_id}.json` 作成アクションのJSONテンプレート、および1on1/グループチャット/チャネル/別テナント参加時の留意事項を記載する。


### Hermes Agent, CLI・Skill連携: 上位要求 R05

  **要求**: Hermes Agent（対話セッションおよびCronジョブ）からキュー処理・タスク管理・相談返信案のブラッシュアップと再コピーを実行できるCLIおよびSkillを提供したい。
  **理由**: バックグラウンドの定期ポーリングをゼロトークンで効率化しつつ、対話時にはHermes Agentの記憶や文脈を活かしてタスク確認や返信案の推敲を行えるようにするため。
  **説明**: `python -m app.cli` のJSON出力対応サブコマンド群と、Skill定義ファイル（`.hermes/skills/teams-workflow/SKILL.md` および `.agents/skills/teams-workflow/SKILL.md`）を提供する。

###### ＜CLIサブコマンド・Skill提供仕様＞

- ■■■ **S05-01**: `python -m app.cli process-queue --json` 実行時、`incoming/` 内の未処理JSONファイルを一括処理し、スキャン件数・相談件数・タスク登録件数のサマリをJSON形式で標準出力へ返却する（未処理ファイルが0件の場合はLLMを呼び出さず即座に終了する）。
- ■■■ **S05-02**: `python -m app.cli list-tasks [--status <status>] --json` および `python -m app.cli update-task <id> --status <status> --json` により、SQLite `tasks` テーブルの一覧取得とステータス更新をJSON出力で行う。
- ■■■ **S05-03**: `python -m app.cli list-consultations --json` および `python -m app.cli copy-reply <message_id> [--text "<修正文案>"] --json` により、相談履歴のJSON照会と、指定した返信案（または修正文案）のDB更新およびクリップボードへのコピーを行う。
- ■■■ **S05-04**: Hermes Agentが上記CLIコマンド群を利用して定期キュー処理や対話的タスク・相談管理を行うための手順を定義したSkillファイル（`SKILL.md`）を提供する。
