# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: LLM API client wrapper supporting multiple providers (OpenAI, Anthropic, Gemini, etc.).
"""
from __future__ import annotations

import random
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import httpx


@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str
    image_base64: str = ""
    image_mime: str = ""


@dataclass
class CallOpts:
    model: str = ""
    max_tokens: int = 4096
    temperature: float = 0.0


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0


@dataclass
class Response:
    content: str = ""
    model: str = ""
    tokens_used: int = 0
    usage: Usage = field(default_factory=Usage)


DEFAULT_RATE_LIMITS: dict[str, int] = {
    "anthropic": 50,
    "openai": 60,
    "gemini": 60,
}
_DEFAULT_RATE_LIMIT = 30

_MAX_RETRIES = 4
_MAX_BACKOFF = 60.0


class RateLimiter:
    def __init__(self, requests_per_minute: int):
        self._interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0.0
        self._last_request: float = 0.0
        self._lock = threading.Lock()

    def acquire(self) -> None:
        if self._interval <= 0:
            return
        with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._interval:
                time.sleep(self._interval - elapsed)
            self._last_request = time.monotonic()


class Client:
    def __init__(
        self,
        provider_name: str,
        api_key: str,
        base_url: str = "",
        rate_limit: int = 0,
        extra_body: dict = None,
    ):
        from synth_wiki.llm.providers import build_provider

        self._provider = build_provider(provider_name, api_key, base_url, extra_body)
        self._provider_name = provider_name

        rpm = rate_limit if rate_limit > 0 else DEFAULT_RATE_LIMITS.get(provider_name, _DEFAULT_RATE_LIMIT)
        self._rate_limiter = RateLimiter(rpm)

        self._http = httpx.Client(timeout=120.0)
        self._tracker = None
        self._pass_name: str = ""

    def set_tracker(self, tracker) -> None:
        self._tracker = tracker

    def set_pass(self, pass_name: str) -> None:
        self._pass_name = pass_name

    def supports_vision(self) -> bool:
        return self._provider.supports_vision()

    def provider_name(self) -> str:
        return self._provider_name

    def chat_completion(self, messages: list[Message], opts: CallOpts) -> Response:
        for attempt in range(_MAX_RETRIES):
            self._rate_limiter.acquire()

            req = self._provider.format_request(messages, opts)
            http_resp = self._http.send(req)

            if http_resp.status_code == 429:
                if attempt < _MAX_RETRIES - 1:
                    base = 2 ** attempt
                    delay = min(base + random.random() * base, _MAX_BACKOFF)
                    time.sleep(delay)
                    continue
                raise RuntimeError(f"Rate limited after {_MAX_RETRIES} attempts")

            if http_resp.status_code != 200:
                # Truncate response body to avoid leaking sensitive info in stack traces
                error_text = http_resp.text[:500] if http_resp.text else ""
                raise RuntimeError(
                    f"Provider {self._provider_name} returned {http_resp.status_code}: {error_text}"
                )

            response = self._provider.parse_response(http_resp.content)

            if self._tracker is not None and response.usage is not None:
                self._tracker.track(self._pass_name, opts.model or response.model, response.usage)

            return response

        raise RuntimeError("chat_completion exhausted retries")

    def chat_completion_with_image(
        self,
        messages: list[Message],
        prompt: str,
        image_base64: str,
        mime_type: str,
        opts: CallOpts,
    ) -> Response:
        vision_msg = Message(
            role="user",
            content=prompt,
            image_base64=image_base64,
            image_mime=mime_type,
        )
        return self.chat_completion(messages + [vision_msg], opts)
