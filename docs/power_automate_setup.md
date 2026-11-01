# Power Automate クラウドフロー設定手順書

本書では、Microsoft Teams に届いたメッセージを検知し、OneDrive for Business の `/TeamsQueue/incoming/{message_id}.json` に1件1ファイルのJSONとして自動保存する **Power Automate クラウドフロー** の作成手順を解説します。

---

## 1. 事前準備（OneDrive フォルダの作成）

1. **OneDrive for Business** を開き、ルート直下に以下のフォルダを作成します：
   - `/TeamsQueue`
   - `/TeamsQueue/incoming`
   - `/TeamsQueue/processed`
   - `/TeamsQueue/failed`
2. Windows PC 側の OneDrive デスクトップ同期クライアントが稼働しており、`%OneDriveCommercial%\TeamsQueue\incoming` がローカルに同期されていることを確認します。
   - ※ `teams-ai-workflow` 起動時にも、ローカル側の `incoming/`, `processed/`, `failed/` は自動作成されます。

---

## 2. クラウドフローの作成手順

### Step 1: トリガーの選択
1. [Power Automate ポータル](https://make.powerautomate.com/) にサインインします。
2. **「＋ 作成」** → **「自動化したクラウド フロー」** を選択します。
3. フロー名に `Teams to OneDrive Queue` と入力します。
4. トリガーとして Microsoft Teams コネクタの **「チャットまたはチャネルで新しいメッセージが追加されたとき」**（または **「チャットに新しいメッセージが追加されたとき (V3)」**）を選択し、「作成」をクリックします。
   - **対象**:
     - 1on1チャット・グループチャットを監視する場合は「グループ チャット」または「すべてのチャット」を選択します。
     - 特定チームのチャネル投稿も監視したい場合は、チャネル用のフローを別途複製して作成すると管理しやすくなります。

---

### Step 2: 自分自身が送信したメッセージの除外設定（重要）

自分が送信したメッセージまでキューに入れてAI判定するのを防ぐため、**トリガーの条件**（または直後の「条件」アクション）で除外します。

#### 方法A: トリガーの設定（推奨・フロー実行回数の節約）
1. トリガー右上の **「…」**（または設定アイコン）→ **「設定」** を開きます。
2. 一番下の **「トリガーの条件」** で「＋ 追加」をクリックし、以下の式を入力します（`<自分のメールアドレス>` または `<自分のAzure AD Object ID>` に置き換えてください）：

```text
@not(equals(toLower(triggerOutputs()?['body/from/user/email']), 'kenta.sato@example.com'))
```
※ テナント環境によって `from/user/email` が空になる場合は、`from/user/id`（自分のユーザーID）または `from/user/displayName` を使用してください：
```text
@not(equals(triggerOutputs()?['body/from/user/id'], '<自分のUser-Object-ID>'))
```

#### 方法B: 「条件」コントロールを使う場合
1. トリガーの次に **「コントロール」→「条件」** アクションを追加します。
2. 左辺に動的コンテンツの **「送信者 (From User Email または Display Name)」**、条件に **「次の値に等しくない」**、右辺に **自分のメールアドレス（または表示名）** を設定します。
3. **「はい (True)」** の分岐内にのみ、次の Step 3（OneDrive ファイル作成）を配置します。

> **補足（ローカル側の二重防御）**:
> 万一 Power Automate 側をすり抜けて自分のメッセージが `incoming/` に保存された場合でも、`config/user_profile.yaml` の `self_names` / `self_emails` に自分の名前とメールアドレスを登録しておけば、ローカルの `DecisionEngine` が LLM を呼ばずに即座に `ignore` としてスキップします。

---

### Step 3: HTMLタグのプレーンテキスト変換（任意・推奨）
Teams のメッセージ本文（`body/content`）には `<p>...</p>` などの HTML タグが含まれる場合があります。
1. **「Content Conversion」→「HTML からテキスト」** アクションを追加します。
2. 「コンテンツ」にトリガーの **「メッセージ本文 (Body Content)」** を指定します。

---

### Step 4: OneDrive for Business に JSON ファイルを作成

1. **「OneDrive for Business」→「ファイルの作成 (Create file)」** アクションを追加します。
2. 各項目を以下のように設定します：
   - **フォルダーのパス**: `/TeamsQueue/incoming`
   - **ファイル名**: `@{triggerOutputs()?['body/id']}.json`
   - **ファイル コンテンツ**: 以下の JSON テンプレートを設定します（「HTMLからテキスト」の出力や動的コンテンツを埋め込みます）

```json
{
  "message_id": "@{triggerOutputs()?['body/id']}",
  "sender_name": "@{coalesce(triggerOutputs()?['body/from/user/displayName'], 'Unknown')}",
  "sender_email": "@{coalesce(triggerOutputs()?['body/from/user/email'], '')}",
  "chat_type": "@{coalesce(triggerOutputs()?['body/chatType'], 'group')}",
  "chat_name": "@{coalesce(triggerOutputs()?['body/topic'], '')}",
  "is_mentioned": false,
  "content": @{string(body('HTML_からテキスト'))},
  "received_at": "@{triggerOutputs()?['body/createdDateTime']}"
}
```

> **JSONエスケープのポイント**:
> `content` に改行やダブルクォーテーションが含まれていてもJSONが壊れないよう、Power Automate の式 `@{string(body('HTML_からテキスト'))}`（または動的コンテンツ全体を JSON オブジェクト構築関数 `json(...)` で組む方式）を使用すると、自動的に文字列エスケープ（`"..."` 付き）されて出力されます。

---

## 3. 別テナント（ゲスト参加）のメッセージを扱う場合

Power Automate の Teams コネクタは、原則として **フローを作成したアカウントが所属する現在のテナント** のチャット・チャネルを監視します。

- **ケース1: 外部ユーザーが自テナントのチャットにゲスト参加している場合**
  - 上記の標準フロー1つでそのまま全てのメッセージを検知できます。
- **ケース2: 自分が顧客・パートナー企業の別テナントにゲスト切り替えして参加している場合**
  - 別テナント側の Power Automate 環境（または該当テナントで許可されたコネクタ）で同様のフローを作成し、出力先として自テナント側の OneDrive（または共有フォルダ）を指定するか、ローカルの監視パスに追加することで一元処理が可能です。

---

## 4. 動作確認手順

1. フローを保存し、テスト用の Teams チャットで他メンバー（またはテスト用アカウント）からメッセージを送信します。
2. 数秒〜数十秒以内に OneDrive の `/TeamsQueue/incoming/` に `{message_id}.json` が生成され、Windows PC のローカルフォルダへ同期されることを確認します。
3. ローカルで `run.bat`（常駐モード）または Hermes Agent / CLI から `python -m app.cli process-queue --json` を実行し、SQLite（`teams_workflow.db`）への登録・Windows通知・`processed/` への移動が行われることを確認します。

