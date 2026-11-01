"""LM Studio OpenAI互換APIクライアントおよびJSON抽出・リトライ制御モジュール."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable

import httpx
from pydantic import ValidationError

from app.config import LMStudioConfig
from app.schemas import DecisionResult

logger = logging.getLogger(__name__)

THINK_TAG_PATTERN = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
CODE_FENCE_PATTERN = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL | re.IGNORECASE)


class LMStudioError(Exception):
    """LM Studio推論呼び出しまたはJSONパース失敗時の例外."""


def extract_json_object(raw_text: str) -> dict[str, Any]:
    """LLMのテキスト出力から <think> タグやコードブロックを除去し、JSONオブジェクトを抽出する."""
    cleaned = THINK_TAG_PATTERN.sub("", raw_text).strip()

    fence_match = CODE_FENCE_PATTERN.search(cleaned)
    if fence_match:
        candidate = fence_match.group(1).strip()
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    start_idx = cleaned.find("{")
    end_idx = cleaned.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        candidate = cleaned[start_idx : end_idx + 1]
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise LMStudioError(f"Failed to parse extracted JSON: {exc}") from exc

    raise LMStudioError("No valid JSON object found in model output")


class LMStudioClient:
    """LM Studio (OpenAI互換 /v1/chat/completions) クライアント."""

    def __init__(
        self,
        config: LMStudioConfig,
        transport_fn: Callable[[dict[str, Any]], str] | None = None,
    ) -> None:
        self.config = config
        self._transport_fn = transport_fn

    def request_decision(self, system_prompt: str, user_prompt: str) -> DecisionResult:
        """プロンプトを送信し、DecisionResult スキーマに合致する出力を取得する（失敗時リトライ付き）."""
        messages: list[dict[str, str]] = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        max_attempts = max(1, self.config.max_retries + 1)
        last_error: Exception | None = None

        for attempt in range(1, max_attempts + 1):
            payload: dict[str, Any] = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
            }

            try:
                raw_content = self._call_completion(payload)
                parsed_json = extract_json_object(raw_content)
                return DecisionResult.model_validate(parsed_json)
            except (LMStudioError, ValidationError, httpx.HTTPError) as exc:
                last_error = exc
                logger.warning(
                    "LM Studio decision attempt %d/%d failed: %s",
                    attempt,
                    max_attempts,
                    exc,
                )
                if attempt < max_attempts:
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"前回の出力がJSONスキーマとしてパースできませんでした（エラー: {exc}）。"
                                "余計な説明を省き、指定されたキー構造のJSONオブジェクトのみを再出力してください。"
                            ),
                        }
                    )

        raise LMStudioError(
            f"All {max_attempts} attempts to get valid DecisionResult from LM Studio failed: {last_error}"
        ) from last_error

    def _call_completion(self, payload: dict[str, Any]) -> str:
        """HTTP POST /chat/completions を実行してアシスタント応答文字列を返す."""
        if self._transport_fn is not None:
            return self._transport_fn(payload)

        url = f"{self.config.base_url.rstrip('/')}/chat/completions"
        with httpx.Client(timeout=self.config.timeout_seconds) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()

        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as exc:
            raise LMStudioError(f"Unexpected response structure from LM Studio: {data}") from exc

