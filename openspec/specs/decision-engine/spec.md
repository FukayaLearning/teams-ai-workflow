# decision-engine Specification

## Purpose

ローカルで稼働するLM Studio（OpenAI互換API）とユーザープロファイル定義（`config/user_profile.yaml`）を用いて、受信したTeamsメッセージの関与度（`is_relevant`）と意図分類（`consultation` / `task` / `info` / `ignore`）を判定し、相談に対する不足情報のヒアリング質問案やタスク構造化データを生成する。

## Requirements

### Requirement: ユーザープロファイルに基づく関与度と意図分類の判定
システムは、`user_profile.yaml` に定義されたユーザーの氏名・役職・担当領域・キーワードおよび自分の送信除外条件を参照し、メンションの有無にかかわらずメッセージの関与度（`is_relevant`）とアクション種別（`consultation`, `task`, `info`, `ignore`）を判定しなければならない（SHALL）。

#### Scenario: メンションなしの担当領域に関する相談メッセージの検知
- **WHEN** グループチャットでメンションがないが、ユーザーの担当領域（例: API・バックエンド障害）に該当する相談メッセージを受信した
- **THEN** `is_relevant: true` かつ `action_type: "consultation"` と判定される

#### Scenario: 自分自身が送信したメッセージまたは無関係な雑談の除外
- **WHEN** 送信者がユーザー自身であるメッセージ、または担当業務・キーワードと無関係な雑談を受信した
- **THEN** `is_relevant: false` かつ `action_type: "ignore"` と判定される

### Requirement: 相談事項に対する不足情報抽出と返信質問案の生成
システムは、`action_type` が `consultation` と判定されたメッセージに対して、回答・調査に必要な不足情報（前提条件、発生環境、エラー内容、希望期限など）を `missing_points` としてリストアップし、相手にそのまま返信可能な丁寧なヒアリングメッセージ案 `suggested_reply` を生成しなければならない（SHALL）。

#### Scenario: 情報不足のトラブル相談に対する質問案生成
- **WHEN** 具体的なエラーログや期限が記載されていない障害相談メッセージが `consultation` と判定された
- **THEN** `consultation.missing_points` に不足項目の配列が設定され、`consultation.suggested_reply` に丁寧な確認メッセージ文字列が生成される

### Requirement: タスク依頼の構造化抽出
システムは、`action_type` が `task` と判定されたメッセージに対して、タスクの件名（`title`）、詳細説明（`description`）、期限（`due_date`、指定がない場合は `null`）、優先度（`priority`: `high` / `normal` / `low`）を構造化して抽出しなければならない（SHALL）。

#### Scenario: 期限付き作業依頼からのタスク抽出
- **WHEN** 「来週金曜までにステージング環境の証明書更新をお願いします」というメッセージが `task` と判定された
- **THEN** `task.title`, `task.description`, `task.due_date`, `task.priority` に構造化された値が抽出される

### Requirement: LLMのJSON出力パースとリトライ・フォールバック制御
システムは、LM Studio APIからのレスポンス（Markdownコードブロックや `<think>...</think>` タグが含まれる場合を含む）からJSONオブジェクトを抽出・検証し、パース失敗時には指定回数リトライを行った上で、最終的に失敗した場合はクラッシュせずエラーとして安全に処理しなければならない（SHALL）。

#### Scenario: DeepSeek-R1等の思考タグやコードブロック付きJSON出力の正常パース
- **WHEN** LM Studioが `<think>推論過程</think>` や ````json ... ```` ブロック付きでJSONを返却した
- **THEN** システムは不要なタグや装飾を除去してJSON部分を抽出し、スキーマ検証を通過させる

#### Scenario: JSONパース失敗時のリトライ
- **WHEN** 初回のLLM出力が不正なJSON形式であった
- **THEN** システムは設定された最大リトライ回数まで再要求を行い、回復を試みる

