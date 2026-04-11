# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations

import json
from typing import Protocol

import httpx

from synth_wiki.llm.client import CallOpts, Message, Response, Usage


class Provider(Protocol):
    def name(self) -> str: ...
    def format_request(self, messages: list[Message], opts: CallOpts) -> httpx.Request: ...
    def parse_response(self, body: bytes) -> Response: ...
    def supports_vision(self) -> bool: ...


class OpenAIProvider:
    def __init__(self, api_key: str, base_url: str = "", extra_body: dict = None):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else "https://api.openai.com/v1"
        self._extra_body = extra_body or {}

    def name(self) -> str:
        return "openai"

    def supports_vision(self) -> bool:
        return True

    def format_request(self, messages: list[Message], opts: CallOpts) -> httpx.Request:
        formatted: list[dict] = []
        for msg in messages:
            if msg.image_base64:
                formatted.append({
                    "role": msg.role,
                    "content": [
                        {"type": "text", "text": msg.content},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{msg.image_mime};base64,{msg.image_base64}"
                            },
                        },
                    ],
                })
            else:
                formatted.append({"role": msg.role, "content": msg.content})

        payload: dict = {
            "model": opts.model,
            "messages": formatted,
            "max_tokens": opts.max_tokens,
            "temperature": opts.temperature,
        }
        if self._extra_body:
            payload.update(self._extra_body)

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        return httpx.Request(
            "POST",
            f"{self._base_url}/chat/completions",
            headers=headers,
            content=json.dumps(payload).encode(),
        )

    def parse_response(self, body: bytes) -> Response:
        data = json.loads(body)
        choice = data["choices"][0]
        content = choice["message"]["content"] or ""
        model = data.get("model", "")
        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("prompt_tokens", 0),
            output_tokens=usage_data.get("completion_tokens", 0),
            cached_tokens=usage_data.get("prompt_tokens_details", {}).get("cached_tokens", 0),
        )
        return Response(
            content=content,
            model=model,
            tokens_used=usage.input_tokens + usage.output_tokens,
            usage=usage,
        )


class AnthropicProvider:
    def __init__(self, api_key: str, base_url: str = ""):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else "https://api.anthropic.com"

    def name(self) -> str:
        return "anthropic"

    def supports_vision(self) -> bool:
        return True

    def format_request(self, messages: list[Message], opts: CallOpts) -> httpx.Request:
        system_text = ""
        chat_messages: list[dict] = []

        for msg in messages:
            if msg.role == "system":
                system_text = msg.content
                continue
            if msg.image_base64:
                chat_messages.append({
                    "role": msg.role,
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": msg.image_mime,
                                "data": msg.image_base64,
                            },
                        },
                        {"type": "text", "text": msg.content},
                    ],
                })
            else:
                chat_messages.append({"role": msg.role, "content": msg.content})

        payload: dict = {
            "model": opts.model,
            "max_tokens": opts.max_tokens,
            "temperature": opts.temperature,
            "messages": chat_messages,
        }
        if system_text:
            payload["system"] = system_text

        headers = {
            "Content-Type": "application/json",
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
        }

        return httpx.Request(
            "POST",
            f"{self._base_url}/v1/messages",
            headers=headers,
            content=json.dumps(payload).encode(),
        )

    def parse_response(self, body: bytes) -> Response:
        data = json.loads(body)
        content = ""
        for block in data.get("content", []):
            if block.get("type") == "text":
                content = block.get("text", "")
                break
        model = data.get("model", "")
        usage_data = data.get("usage", {})
        usage = Usage(
            input_tokens=usage_data.get("input_tokens", 0),
            output_tokens=usage_data.get("output_tokens", 0),
            cached_tokens=usage_data.get("cache_read_input_tokens", 0),
        )
        return Response(
            content=content,
            model=model,
            tokens_used=usage.input_tokens + usage.output_tokens,
            usage=usage,
        )


class GeminiProvider:
    def __init__(self, api_key: str, base_url: str = ""):
        self._api_key = api_key
        self._base_url = base_url.rstrip("/") if base_url else "https://generativelanguage.googleapis.com/v1beta"

    def name(self) -> str:
        return "gemini"

    def supports_vision(self) -> bool:
        return True

    def format_request(self, messages: list[Message], opts: CallOpts) -> httpx.Request:
        contents: list[dict] = []
        system_text = ""

        for msg in messages:
            if msg.role == "system":
                system_text = msg.content
                continue

            role = "user" if msg.role == "user" else "model"
            if msg.image_base64:
                parts = [
                    {"text": msg.content},
                    {
                        "inline_data": {
                            "mime_type": msg.image_mime,
                            "data": msg.image_base64,
                        }
                    },
                ]
            else:
                parts = [{"text": msg.content}]

            contents.append({"role": role, "parts": parts})

        payload: dict = {
            "contents": contents,
            "generationConfig": {
                "maxOutputTokens": opts.max_tokens,
                "temperature": opts.temperature,
            },
        }
        if system_text:
            payload["systemInstruction"] = {"parts": [{"text": system_text}]}

        url = f"{self._base_url}/models/{opts.model}:generateContent?key={self._api_key}"

        return httpx.Request(
            "POST",
            url,
            headers={"Content-Type": "application/json"},
            content=json.dumps(payload).encode(),
        )

    def parse_response(self, body: bytes) -> Response:
        data = json.loads(body)
        content = ""
        candidates = data.get("candidates", [])
        if candidates:
            for part in candidates[0].get("content", {}).get("parts", []):
                if "text" in part:
                    content = part["text"]
                    break

        usage_data = data.get("usageMetadata", {})
        usage = Usage(
            input_tokens=usage_data.get("promptTokenCount", 0),
            output_tokens=usage_data.get("candidatesTokenCount", 0),
            cached_tokens=usage_data.get("cachedContentTokenCount", 0),
        )
        return Response(
            content=content,
            model="",
            tokens_used=usage.input_tokens + usage.output_tokens,
            usage=usage,
        )


def build_provider(provider_name: str, api_key: str, base_url: str = "", extra_body: dict = None) -> Provider:
    name = provider_name.lower()
    if name == "openai":
        return OpenAIProvider(api_key, base_url, extra_body)
    if name == "openai-compatible":
        return OpenAIProvider(api_key, base_url, extra_body)
    if name == "anthropic":
        return AnthropicProvider(api_key, base_url)
    if name == "gemini":
        return GeminiProvider(api_key, base_url)
    if name == "ollama":
        return OpenAIProvider(api_key, base_url or "http://localhost:11434/v1", extra_body)
    raise ValueError(f"Unknown provider: {provider_name!r}")
