"""データスキーマ定義モジュール (Pydantic)."""

from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, field_validator


ActionType = Literal["consultation", "task", "info", "ignore"]
PriorityType = Literal["high", "normal", "low"]
TaskStatusType = Literal["todo", "in_progress", "done"]


class IncomingMessage(BaseModel):
    """Power Automate が incoming/ に出力するキューJSONのスキーマ."""

    message_id: str = Field(..., min_length=1)
    sender_name: str = Field(..., min_length=1)
    sender_email: str | None = None
    chat_type: str = Field(..., min_length=1)
    chat_name: str | None = None
    is_mentioned: bool = False
    content: str = Field(..., min_length=1)
    received_at: str = Field(..., min_length=1)

    @field_validator("message_id", "sender_name", "chat_type", "content", "received_at")
    @classmethod
    def validate_non_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Field must not be empty or whitespace only")
        return stripped


class ConsultationDetail(BaseModel):
    """相談判定時の不足情報・返信案スキーマ."""

    missing_points: list[str] = Field(default_factory=list)
    suggested_reply: str = ""


class TaskDetail(BaseModel):
    """タスク判定時の抽出データスキーマ."""

    title: str = ""
    description: str = ""
    due_date: str | None = None
    priority: PriorityType = "normal"

    @field_validator("priority", mode="before")
    @classmethod
    def normalize_priority(cls, value: object) -> str:
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in ("high", "normal", "low"):
                return lowered
        return "normal"


class DecisionResult(BaseModel):
    """LM Studio Decisionモデルからの構造化出力スキーマ."""

    is_relevant: bool
    action_type: ActionType
    reasoning: str = ""
    consultation: ConsultationDetail = Field(default_factory=ConsultationDetail)
    task: TaskDetail = Field(default_factory=TaskDetail)

