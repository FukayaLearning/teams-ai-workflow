# teams-ai-workflow

> **Microsoft Teams × Power Automate (OneDriveキュー) × LM Studio (ローカルDecisionモデル) 連携ワークフロー**

会社のイントラネット環境（社外からの通信不可・ポート開放不可）でも安全かつ確実に動作する、**OneDriveファイル同期を活用したローカル完結型**のAIワークフローシステムです。

PCがシャットダウンしている間や離席中に届いたTeamsメッセージも取りこぼさず、ローカルで稼働する LM Studio の **Decisionモデル（推論特化型LLM）** が「関与度」と「意図」を分析します。
- **相談事項**: 情報漏れ（前提条件、環境、エラー、期限等）を防ぐためのヒアリング質問案を自動生成
- **タスク依頼**: 要件・期限を構造化してローカルのSQLiteデータベースに自動登録

---

## 1. システムアーキテクチャ概要

```mermaid
flowchart TD
    subgraph Microsoft 365 クラウド (24時間稼働)
        Teams["Microsoft Teams\n(1on1 / グループ / チャネル / 別テナント)"] -->|メッセージ検知| PA["Power Automate (クラウドフロー)"]
        PA -->|1件1ファイルのJSONを作成| CloudFolder["OneDrive for Business (クラウド)\n/TeamsQueue/incoming/{id}.json"]
    end

    CloudFolder -.->|OneDriveデスクトップアプリが自動同期| LocalFolder["ローカルPCのOneDrive同期フォルダ\nC:\\Users\\...\\TeamsQueue\\incoming\\"]

    subgraph Windows PC (社内イントラネット内)
        subgraph teams-ai-workflow (本アプリ)
            Watcher["キューウォッチャー\n(フォルダ監視 / 未処理JSON読み取り)"]
            LocalDB[("ローカル SQLite DB\n(teams_workflow.db)")]
            DecisionEngine["Decision Engine\n(LM Studio連携)"]
            ActionExecutor["アクション実行モジュール"]
        end

        LocalFolder -->|未処理JSONを検知| Watcher
        Watcher -->|メッセージ保存 & 重複制御| LocalDB
        Watcher -->|処理済みに移動| ProcessedFolder["TeamsQueue/processed/"]
        
        Watcher --> DecisionEngine

        subgraph LM Studio (Local Server)
            LMDecision["Decision Model\n(例: DeepSeek-R1 / Qwen2.5等)"]
        end

        DecisionEngine <-->|OpenAI互換API\nhttp://127.0.0.1:1234/v1| LMDecision

        DecisionEngine -->|分岐| ActionExecutor
        
        ActionExecutor -->|相談の場合| ToastReply["Windows通知でサジェスト\n(質問案をクリップボードにコピー)"]
        ActionExecutor -->|タスクの場合| LocalDB
        ActionExecutor -->|無関係な会話| Skip["スキップ記録 (DB保存のみ)"]
    end
```

---

## 2. 本構成のメリット（なぜこの構成なのか）

1. **PC電源OFF・画面ロック中のメッセージを100%取りこぼさない**:
   - クラウド側のPower AutomateがメッセージをOneDriveに蓄積。PCを起動した瞬間にWindowsのOneDrive同期機能によってローカルへ自動ダウンロードされます。
2. **社内イントラネット・プロキシの制限を完全クリア**:
   - 外部からのインバウンド通信（Webhook受信やngrok等）は一切使いません。
   - 自作アプリは「PC内のローカルフォルダ」を読むだけなので、Graph APIのアプリ登録やAzure AD管理者権限も不要です。
3. **他テナント・1on1・グループチャットに全対応**:
   - Power AutomateのTeamsコネクタにより、メンションあり/なしを問わず柔軟にキューイング可能です。
4. **機密情報の保護**:
   - チャット解析はPC内のLM Studio（ローカルLLM）で行うため、社内データが外部のパブリックAIに送信されることはありません。

---

## 3. 仕様詳細

### 3.1. キューファイル仕様 (JSON)
Power Automate が OneDrive の `TeamsQueue/incoming/` に作成するJSONのフォーマット：

```json
{
  "message_id": "1730345678901",
  "sender_name": "山田 太郎",
  "sender_email": "yamada.taro@example.com",
  "chat_type": "group",
  "chat_name": "プロジェクトX 連絡用",
  "is_mentioned": false,
  "content": "昨日の夜からステージング環境でAPIエラーが多発しているようです。どなたか確認できますか？",
  "received_at": "2026-10-31T15:20:00Z"
}
```

### 3.2. 処理ステータス管理とOneDriveパス自動解決
- `TeamsQueue/incoming/`: 未処理のJSONが配置されるフォルダ。
- `TeamsQueue/processed/`: 処理完了後に移動されるフォルダ（履歴・バックアップ用）。
- `TeamsQueue/failed/`: エラー発生時に退避されるフォルダ。
- **ローカルパスの自動解決 (`app/config.py`)**:
  - `config/settings.yaml` の `queue.base_dir` が `"auto"` の場合、Windows環境変数 `%OneDriveCommercial%` → `%OneDriveConsumer%` → `%OneDrive%` → `%USERPROFILE%\OneDrive - *` → `./data/TeamsQueue` の優先順位でローカル同期フォルダを自動検出し、`incoming`, `processed`, `failed` ディレクトリを自動作成します。

### 3.3. LLM判定仕様 (Decision Engine)
LM Studio の OpenAI 互換エンドポイント (`http://127.0.0.1:1234/v1/chat/completions`) を使用。

1. **ユーザープロファイル参照と自己送信メッセージ除外**:
   - `config/user_profile.yaml` に定義されたユーザーの担当分野・キーワードを参照し、メンションなしのグループチャットでも関連性を判定。
   - 送信者が `self_names` または `self_emails` に一致する場合（自分自身の送信メッセージ）は、LLM推論を呼ばずに即座に `ignore` としてスキップします（Power Automate側のトリガー除外条件との二重防御）。
2. **推論ステップ (Chain-of-Thought / Structured Output)**:
   - **Step 1 (関与度)**: ユーザーに関係があるか？（`is_relevant`: true / false）
   - **Step 2 (意図分類)**:
     - `consultation`（相談・質問・トラブル報告）
     - `task`（作業依頼・タスク・宿題事項）
     - `info`（一般的な連絡・情報共有）
     - `ignore`（無関係な会話・雑談）
   - **Step 3 (アクション生成)**:
     - 相談の場合: 相手が伝え漏れている前提条件（発生環境、エラーログ、希望期限、再現性など）を洗い出し、丁寧なヒアリング質問文を生成。
     - タスクの場合: タイトル、詳細、期限（推定または指定）、優先度を抽出。
3. **JSON出力の安定化・リトライ機構 (`app/ai/lm_studio_client.py`)**:
   - DeepSeek-R1系モデルの `<think>...</think>` 思考タグや Markdown コードブロック（````json ... ````）を自動除去してJSONオブジェクトを抽出します。
   - JSONパースやPydanticスキーマ検証に失敗した場合は、`max_retries`（デフォルト2回）までエラーフィードバック付きで自動リトライします。

#### レスポンスデータスキーマ
```json
{
  "is_relevant": true,
  "action_type": "consultation",
  "reasoning": "ユーザーの担当領域（API・バックエンド）に関する障害の相談だが、具体的なエラーコードと発生時刻の詳細が不足しているため",
  "consultation": {
    "missing_points": [
      "発生している具体的なエラーコードやレスポンス内容",
      "再現する特定のエンドポイント",
      "希望する調査完了タイミング"
    ],
    "suggested_reply": "お疲れ様です。調査を進めたいと思いますので、可能であれば以下の点について教えていただけますでしょうか？\n1. 発生している具体的なHTTPステータスコードやエラーログ\n2. 特定のAPIエンドポイントで起きているか\n3. いつ頃までの対応をご希望ですか？"
  },
  "task": {
    "title": "",
    "description": "",
    "due_date": null,
    "priority": "normal"
  }
}
```

### 3.4. アクション仕様
1. **相談 (`consultation`) の場合**:
   - Windowsデスクトップ通知（トースト）を表示:
     - `【相談受信】山田 太郎さんからの相談に対する質問案を作成しました`
   - 生成された返信案をクリップボードに自動コピー（または通知クリックでコピー）。
   - Teamsのチャット画面で `Ctrl + V` を押すだけで、不足情報を的確にヒアリングするメッセージを即返信可能。
2. **タスク (`task`) の場合**:
   - ローカルの SQLite データベースの `tasks` テーブルに登録（ステータス: `todo`）。
   - Windows通知を表示: `【タスク登録】「ステージング環境のAPI調査」をToDoに登録しました`。
3. **無関係な会話 (`ignore`) の場合**:
   - 通知は出さず、SQLiteのメッセージ履歴ログにのみ「スキップ」として記録。

---

## 4. データベース設計 (SQLite: `teams_workflow.db`)

### テーブル: `messages`
- `id` (INTEGER, PK, AUTOINCREMENT)
- `message_id` (TEXT, UNIQUE): TeamsのメッセージID
- `sender_name` (TEXT)
- `chat_type` (TEXT)
- `content` (TEXT)
- `received_at` (DATETIME)
- `is_relevant` (BOOLEAN)
- `action_type` (TEXT): `consultation` / `task` / `info` / `ignore`
- `reasoning` (TEXT)
- `raw_json` (TEXT)
- `created_at` (DATETIME)

### テーブル: `tasks`
- `id` (INTEGER, PK, AUTOINCREMENT)
- `message_id` (TEXT, FK -> messages.message_id)
- `title` (TEXT)
- `description` (TEXT)
- `due_date` (DATETIME, NULLABLE)
- `priority` (TEXT): `high` / `normal` / `low`
- `status` (TEXT): `todo` / `in_progress` / `done`
- `created_at` (DATETIME)

### テーブル: `consultations`
- `id` (INTEGER, PK, AUTOINCREMENT)
- `message_id` (TEXT, FK -> messages.message_id)
- `missing_points` (TEXT): 不足情報リスト (JSON)
- `suggested_reply` (TEXT): 提案された返信文
- `is_copied` (BOOLEAN)
- `created_at` (DATETIME)

---

## 5. ディレクトリ構成

```text
teams-ai-workflow/
├── app/
│   ├── __init__.py
│   ├── main.py                  # メイン常駐ループ（監視・処理オーケストレーション）
│   ├── cli.py                   # Hermes Agent / Cron 連携用 CLI サブコマンド
│   ├── config.py                # 設定読み込み・OneDriveパス自動解決
│   ├── schemas.py               # Pydanticデータモデル (入力JSON, LLM出力)
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── database.py          # SQLite接続・テーブル初期化
│   │   └── repository.py        # CRUD操作（メッセージ・タスク・相談履歴の保存）
│   ├── watcher/
│   │   ├── __init__.py
│   │   └── queue_watcher.py     # OneDriveフォルダの監視・ファイル検出・ファイル移動
│   ├── ai/
│   │   ├── __init__.py
│   │   ├── lm_studio_client.py  # LM Studio API クライアント (<think>除去・リトライ対応)
│   │   ├── decision_engine.py   # Decisionモデルによる判定・自己送信除外
│   │   └── prompts.py           # 判定・ヒアリング質問生成プロンプト定義
│   └── actions/
│       ├── __init__.py
│       ├── desktop_notifier.py  # Windowsトースト通知表示 (windows-toasts / ログフォールバック)
│       └── clipboard_helper.py  # クリップボード自動コピー (pyperclip / メモリフォールバック)
├── .hermes/skills/teams-workflow/
│   └── SKILL.md                 # Hermes Agent 連携スキル定義
├── config/
│   ├── settings.yaml            # LM Studio接続設定、監視フォルダパス設定
│   ├── settings.yaml.example
│   ├── user_profile.yaml        # 自分の名前・担当業務・キーワード設定
│   └── user_profile.yaml.example
├── docs/
│   └── power_automate_setup.md  # Power Automate フロー作成手順書（自己送信除外・別テナント対応）
├── tests/
│   └── test_workflow.py         # 単体テスト・E2Eモックテスト
├── requirements.txt             # 依存ライブラリ
├── run.bat                      # Windows起動用ワンクリックバッチ
└── README.md                    # 本仕様書
```

---

## 6. セットアップ・実行要件

- **OS**: Windows 10 / Windows 11（開発・テストは Linux / macOS でも実行可能）
- **必須環境**:
  - Python 3.10 以上
  - OneDrive for Business デスクトップ同期クライアント（稼働中であること）
  - LM Studio（ローカルサーバー稼働中、デフォルト `http://127.0.0.1:1234/v1`）
  - 推奨LLM: 推論・判定精度の高いDecisionモデル（Qwen2.5-7B/14B/32B, DeepSeek-R1蒸留モデル, Llama-3.1等）
- **Power Automate 側の設定**:
  - クラウドフローの作成手順、自分自身が送信したメッセージの除外条件式、別テナント参加時の運用については [docs/power_automate_setup.md](file:///home/sweet/workspace/teams-ai-workflow/docs/power_automate_setup.md) を参照してください。

---

## 7. 使い方（常駐モード & Hermes Agent ハイブリッド連携）

### 7.1. スタンドアロン常駐モード
Windows 環境で `run.bat` をダブルクリックするか、以下を実行します：
```bash
python -m app.main
```

### 7.2. Hermes Agent / CLI 連携モード
[.hermes/skills/teams-workflow/SKILL.md](file:///home/sweet/workspace/teams-ai-workflow/.hermes/skills/teams-workflow/SKILL.md) により、Hermes Agent の対話セッションや Cron ジョブから以下の CLI サブコマンドを呼び出せます：

```bash
# 未処理キューのワンショット処理（未処理0件ならLLM呼び出しゼロで即終了）
python -m app.cli process-queue --json

# タスク一覧の照会・ステータス更新
python -m app.cli list-tasks --status todo --json
python -m app.cli update-task 1 --status done --json

# 相談履歴の照会・返信案のブラッシュアップとクリップボード再コピー
python -m app.cli list-consultations --json
python -m app.cli copy-reply "<message_id>" --text "<修正した返信文>" --json
```

