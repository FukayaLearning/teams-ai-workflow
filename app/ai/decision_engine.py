"""Decision Engine: メッセージの関与度判定・自己送信除外・LLM推論実行モジュール."""

from __future__ import annotations

import logging

from app.ai.lm_studio_client import LMStudioClient
from app.ai.prompts import build_system_prompt, build_user_prompt
from app.config import UserProfile
from app.schemas import DecisionResult, IncomingMessage

logger = logging.getLogger(__name__)


class DecisionEngine:
    """ユーザープロファイルとLM Studioクライアントを用いてメッセージを判定するエンジン."""

    def __init__(self, client: LMStudioClient, user_profile: UserProfile) -> None:
        self.client = client
        self.user_profile = user_profile

    def evaluate(self, message: IncomingMessage) -> DecisionResult:
        """受信メッセージを評価し、DecisionResult を返す."""
        if self.user_profile.is_self_sender(message.sender_name, message.sender_email):
            logger.info("Skipping self-sent message: %s", message.message_id)
            return DecisionResult(
                is_relevant=False,
                action_type="ignore",
                reasoning="ユーザー自身が送信したメッセージのため自動スキップ",
            )

        system_prompt = build_system_prompt(self.user_profile)
        user_prompt = build_user_prompt(message)
        result = self.client.request_decision(system_prompt=system_prompt, user_prompt=user_prompt)

        if not result.is_relevant and result.action_type != "ignore":
            result.action_type = "ignore"

        return result

