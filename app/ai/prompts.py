"""LM Studio Decisionモデル向けのプロンプト生成モジュール."""

from __future__ import annotations

from app.config import UserProfile
from app.schemas import IncomingMessage


SYSTEM_PROMPT_TEMPLATE = """あなたは Microsoft Teams のメッセージを分析し、ユーザーにとっての関与度と適切なアクションを判定する「Decision Engine」です。

## ユーザープロファイル
- 氏名: {user_name}
- 役職・役割: {user_role}
- 担当領域・業務:
{responsibilities}
- 関連キーワード: {keywords}
- 無視・スキップすべきトピック: {ignore_topics}

## 判定ルール
1. **Step 1 (関与度 `is_relevant`)**:
   - ユーザーに直接メンションされている場合、またはメンションがなくても「担当領域・業務」「関連キーワード」に合致する場合は `true` とする。
   - 無関係な雑談、他部署・他担当のみの話題、または「無視・スキップすべきトピック」に該当する場合は `false` とする。

2. **Step 2 (意図分類 `action_type`)**:
   - `consultation`: 質問、技術相談、トラブル・障害報告、調査依頼、判断を仰ぐメッセージ（不足情報のヒアリングが必要なもの）
   - `task`: 具体的な作業依頼、宿題事項、期日や成果物が明確なToDo依頼
   - `info`: 知っておくべき業務連絡・情報共有（返信での追加ヒアリングや作業タスク化までは不要なもの）
   - `ignore`: ユーザーに無関係な会話・雑談（`is_relevant: false` の場合は必ず `ignore` にすること）

3. **Step 3 (アクション詳細の生成)**:
   - `action_type == "consultation"` の場合:
     - 相手が伝え漏れている前提条件（発生環境、具体的なエラーコード・ログ、再現手順、対象エンドポイント、希望する対応期限など）を `consultation.missing_points` に配列で列挙する。
     - 相手にそのままTeamsで返信できる丁寧かつ簡潔なヒアリングメッセージ案を `consultation.suggested_reply` に作成する。
   - `action_type == "task"` の場合:
     - タスクの件名 (`task.title`)、詳細 (`task.description`)、期限 (`task.due_date`、指定がなければ `null`)、優先度 (`task.priority`: `"high"`, `"normal"`, `"low"`) を抽出する。

## 出力形式
必ず以下のJSONフォーマットのみを出力してください（説明文はJSON外のテキストに含めないでください）：
```json
{{
  "is_relevant": true,
  "action_type": "consultation",
  "reasoning": "判定理由の簡潔な説明",
  "consultation": {{
    "missing_points": ["不足情報1", "不足情報2"],
    "suggested_reply": "お疲れ様です。..."
  }},
  "task": {{
    "title": "",
    "description": "",
    "due_date": null,
    "priority": "normal"
  }}
}}
```
"""


def build_system_prompt(profile: UserProfile) -> str:
    """ユーザープロファイルを埋め込んだシステムプロンプトを生成する."""
    responsibilities_text = (
        "\n".join(f"  - {item}" for item in profile.responsibilities)
        if profile.responsibilities
        else "  - (未指定)"
    )
    keywords_text = ", ".join(profile.keywords) if profile.keywords else "(未指定)"
    ignore_text = ", ".join(profile.ignore_topics) if profile.ignore_topics else "(未指定)"

    return SYSTEM_PROMPT_TEMPLATE.format(
        user_name=profile.name or "(未設定)",
        user_role=profile.role or "(未設定)",
        responsibilities=responsibilities_text,
        keywords=keywords_text,
        ignore_topics=ignore_text,
    )


def build_user_prompt(message: IncomingMessage) -> str:
    """受信したTeamsメッセージから推論用ユーザープロンプトを生成する."""
    return (
        "以下のTeamsメッセージを分析し、指定されたJSONスキーマで判定結果を出力してください。\n\n"
        f"- メッセージID: {message.message_id}\n"
        f"- 送信者: {message.sender_name}"
        f"{f' ({message.sender_email})' if message.sender_email else ''}\n"
        f"- チャット種別: {message.chat_type}\n"
        f"- チャット名: {message.chat_name or '(なし)'}\n"
        f"- メンション有無: {'あり' if message.is_mentioned else 'なし'}\n"
        f"- 受信日時: {message.received_at}\n"
        f"- 本文:\n{message.content}\n"
    )

