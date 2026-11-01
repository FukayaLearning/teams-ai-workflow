# 次回セッションへの引き継ぎメモ・残存検討事項 (HANDOVER & TODO)

本書は、次回セッション開始時にスムーズに実装・検証を進められるよう、**現在の合意状況**、**残された検討事項**、および**次回の実装手順（TODO）**をまとめたドキュメントです。

---

## 1. 確定した全体アーキテクチャのおさらい

- **方式**: **代替案A（OneDriveファイル自動同期 ＋ ローカルSQLite ＋ LM Studio Decisionモデル）**
- **処理の流れ**:
  1. **クラウド側 (24時間稼働)**:
     - Power Automate クラウドフローが Teams のメッセージ（1on1、メンション、グループチャット等）を受信。
     - OneDrive for Business のクラウドフォルダ `/TeamsQueue/incoming/{message_id}.json` に1件1ファイルで保存。
  2. **同期層 (Windows標準機能)**:
     - Windows PC 常駐の OneDrive デスクトップアプリが、クラウドのファイルをローカルフォルダ（`C:\Users\<user>\OneDrive - <社名>\TeamsQueue\incoming\`）へ自動ダウンロード。
     - **社内イントラ制限（外部ポート開放・Webhook不可）やPCスリープ時の取りこぼしを完全に解消**。
  3. **ローカルアプリ (`teams-ai-workflow`)**:
     - ローカルの `incoming/` を監視し、新しいJSONを検知。
     - ローカル SQLite DB（`teams_workflow.db`）にレコード保存。
     - 処理済みファイルを `TeamsQueue/processed/` に移動。
     - LM Studio（`http://127.0.0.1:1234/v1`）の **Decisionモデル** にプロンプト送信。
  4. **AI判定とアクション**:
     - `config/user_profile.yaml` のユーザー定義（担当領域・役職・キーワード）に基づき、メンションなしでも関与度を判定。
     - **相談 (`consultation`)**: 不足情報（前提、エラー、環境、期限等）を特定し、丁寧なヒアリング質問文を生成。Windows通知でサジェスト＆クリップボード自動コピー。
     - **タスク (`task`)**: 件名・詳細・期日を構造化抽出し、SQLite DB の `tasks` テーブルに自動登録。
     - **無関係 (`ignore`)**: DBにログのみ残して静かにスキップ。

---

## 2. 次回セッションに向けた残存検討事項 (Open Issues)

次回セッションで実際にコードを動かすにあたり、以下の点を確認・調整する必要があります。

### ① LM Studio のモデル選定とレスポンス形式
- **使用予定モデルの確認**:
  - 現在 LM Studio でダウンロード済み（または使用予定）のモデル名（例: `qwen2.5-7b-instruct`, `deepseek-r1-distill-qwen-8b`, `llama-3.1-8b-instruct` など）。
- **JSON出力の安定性**:
  - LM Studio のバージョンやモデルによって、Structured Outputs（JSON Schema）の挙動が異なる場合があります。JSONパース失敗時のリトライ・フォールバックロジックを実装するか検討。

### ② OneDrive フォルダの配置パス
- **ローカルパスの自動解決**:
  - Windows の環境変数 `%OneDriveConsumer%` または `%OneDriveCommercial%`、`%USERPROFILE%\OneDrive - <組織名>` から、`TeamsQueue/incoming` フォルダを自動検出できるようにする設計。

### ③ Power Automate フローの設計詳細
- **トリガーのスコープ**:
  - Teams コネクタの「チャットに追加された新しいメッセージ（V3）」トリガーを使う場合、自分が所属するすべてのチャットが対象になります。
  - **自分自身が送信したメッセージの除外**: 送信者ID（`User.Id`）が自分自身のメッセージは OneDrive に書き込まずスキップする条件（トリガーの条件設定）が必要。
- **別テナント（ゲスト参加）のメッセージ**:
  - Power Automate はログイン中の既定テナントのチャットを監視します。別テナントのチャットも同じフローで拾えるか、または別テナント側にもフローを作る必要があるかを実機で確認。

### ④ Windows通知・クリップボードのライブラリ選定
- **通知表示**: `windows-toasts` または `plyer`、`win10toast`（Windows 10/11 で通知アクション・ボタンを付けられるか）。
- **クリップボード**: `pyperclip`（軽量で依存が少ない）。

---

## 3. 次回セッションの実装ロードマップ (TODO)

次回セッションを開始する際は、以下のステップで進めることを推奨します。

- [ ] **Step 1: 設定ファイルとデータスキーマの作成**
  - `config/settings.yaml`（LM Studio接続先、フォルダパス設定）
  - `config/user_profile.yaml`（ユーザープロファイル定義）
  - `app/schemas.py`（Pydanticモデル定義）
- [ ] **Step 2: SQLiteデータベース層の実装**
  - `app/storage/database.py`（テーブル作成）
  - `app/storage/repository.py`（CRUD操作）
- [ ] **Step 3: キューウォッチャーの実装**
  - `app/watcher/queue_watcher.py`（ローカルフォルダのファイル検知・JSON読み込み・ファイル移動）
- [ ] **Step 4: LM Studio 連携 ＆ Decision Engine の実装**
  - `app/ai/lm_studio_client.py`（OpenAI互換クライアント）
  - `app/ai/prompts.py`（関与度・相談質問生成・タスク抽出プロンプト）
  - `app/ai/decision_engine.py`（推論実行エンジン）
- [ ] **Step 5: Windowsアクション層の実装**
  - `app/actions/desktop_notifier.py`（トースト通知）
  - `app/actions/clipboard_helper.py`（クリップボード操作）
- [ ] **Step 6: モックテストの実施**
  - サンプルのTeamsメッセージJSONを `incoming/` に投入し、LM Studioが意図通りに判定してDB登録＆通知が出るかをローカルで検証。
- [ ] **Step 7: Power Automate 設定手順書の作成**
  - `docs/power_automate_setup.md`（スクリーンショットや設定値を含む手順書）

---

## 4. 次回セッション開始用のプロンプト例

次のセッションを開始する際、以下のようにAIエージェントに指示するとスムーズです：

```text
/home/sweet/workspace/teams-ai-workflow/docs/TODO.md と README.md を読み込んでください。
前回のセッションで確定した仕様（OneDriveキュー + ローカルSQLite + LM Studio Decisionモデル）に基づき、
Step 1（設定・Pydanticスキーマ）から順に実装を進めてください。
```
