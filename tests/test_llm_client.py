# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations

import json
import time
from unittest.mock import MagicMock, patch

import httpx
import pytest

from synth_wiki.llm.client import CallOpts, Client, Message, Response, Usage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_openai_body(content: str = "hello", model: str = "gpt-4o") -> bytes:
    return json.dumps({
        "choices": [{"message": {"content": content}}],
        "model": model,
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 5,
            "prompt_tokens_details": {"cached_tokens": 0},
        },
    }).encode()


def _make_anthropic_body(content: str = "hello") -> bytes:
    return json.dumps({
        "content": [{"type": "text", "text": content}],
        "model": "claude-sonnet-4-20250514",
        "usage": {"input_tokens": 10, "output_tokens": 5, "cache_read_input_tokens": 0},
    }).encode()


def _make_gemini_body(content: str = "hello") -> bytes:
    return json.dumps({
        "candidates": [{"content": {"parts": [{"text": content}]}}],
        "modelVersion": "gemini-2.5-flash",
        "usageMetadata": {
            "promptTokenCount": 10,
            "candidatesTokenCount": 5,
            "cachedContentTokenCount": 0,
        },
    }).encode()


def _fake_response(status: int, body: bytes) -> httpx.Response:
    return httpx.Response(status_code=status, content=body)


# ---------------------------------------------------------------------------
# Provider creation tests
# ---------------------------------------------------------------------------

class TestClientCreation:
    def test_openai_provider(self):
        c = Client("openai", api_key="fake_openai_key")
        assert c.provider_name() == "openai"
        assert c.supports_vision() is True

    def test_anthropic_provider(self):
        c = Client("anthropic", api_key="fake_openai_key")
        assert c.provider_name() == "anthropic"
        assert c.supports_vision() is True

    def test_gemini_provider(self):
        c = Client("gemini", api_key="fake_openai_key")
        assert c.provider_name() == "gemini"
        assert c.supports_vision() is True

    def test_ollama_provider(self):
        c = Client("ollama", api_key="")
        assert c.provider_name() == "ollama"

    def test_unknown_provider_raises(self):
        with pytest.raises(ValueError, match="Unknown provider"):
            Client("bogus", api_key="x")


# ---------------------------------------------------------------------------
# chat_completion tests
# ---------------------------------------------------------------------------

class TestChatCompletion:
    def test_openai_success(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gpt-4o")

        with patch.object(c._http, "send", return_value=_fake_response(200, _make_openai_body("world"))):
            resp = c.chat_completion(msgs, opts)

        assert resp.content == "world"
        assert resp.model == "gpt-4o"
        assert resp.tokens_used == 15

    def test_anthropic_success(self):
        c = Client("anthropic", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="claude-sonnet-4-20250514")

        with patch.object(c._http, "send", return_value=_fake_response(200, _make_anthropic_body("pong"))):
            resp = c.chat_completion(msgs, opts)

        assert resp.content == "pong"

    def test_gemini_success(self):
        c = Client("gemini", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gemini-2.5-flash")

        with patch.object(c._http, "send", return_value=_fake_response(200, _make_gemini_body("flash"))):
            resp = c.chat_completion(msgs, opts)

        assert resp.content == "flash"

    def test_non_200_raises(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gpt-4o")

        with patch.object(c._http, "send", return_value=_fake_response(500, b"internal error")):
            with pytest.raises(RuntimeError, match="500"):
                c.chat_completion(msgs, opts)

    def test_429_retry_succeeds(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gpt-4o")

        responses = [
            _fake_response(429, b"rate limited"),
            _fake_response(200, _make_openai_body("ok after retry")),
        ]

        with patch.object(c._http, "send", side_effect=responses):
            with patch("time.sleep"):  # skip actual sleep
                resp = c.chat_completion(msgs, opts)

        assert resp.content == "ok after retry"

    def test_429_exhausted_raises(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gpt-4o")

        with patch.object(c._http, "send", return_value=_fake_response(429, b"rate limited")):
            with patch("time.sleep"):
                with pytest.raises(RuntimeError, match="Rate limited"):
                    c.chat_completion(msgs, opts)

    def test_tracker_called(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        c.set_pass("extract")
        tracker = MagicMock()
        c.set_tracker(tracker)

        msgs = [Message(role="user", content="hi")]
        opts = CallOpts(model="gpt-4o")

        with patch.object(c._http, "send", return_value=_fake_response(200, _make_openai_body())):
            c.chat_completion(msgs, opts)

        tracker.track.assert_called_once()
        call_args = tracker.track.call_args[0]
        assert call_args[0] == "extract"

    def test_set_tracker_and_pass(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        t = MagicMock()
        c.set_tracker(t)
        c.set_pass("my_pass")
        assert c._tracker is t
        assert c._pass_name == "my_pass"


# ---------------------------------------------------------------------------
# Vision tests
# ---------------------------------------------------------------------------

class TestVision:
    def test_chat_completion_with_image(self):
        c = Client("openai", api_key="fake_openai_key", rate_limit=10000)
        msgs = [Message(role="system", content="You are helpful")]
        opts = CallOpts(model="gpt-4o")

        captured_req = {}

        def fake_send(req):
            payload = json.loads(req.content)
            captured_req.update(payload)
            return _fake_response(200, _make_openai_body("image response"))

        with patch.object(c._http, "send", side_effect=fake_send):
            resp = c.chat_completion_with_image(
                msgs, "What is in this image?", "abc123", "image/png", opts
            )

        assert resp.content == "image response"
        user_msg = captured_req["messages"][-1]
        assert user_msg["role"] == "user"
        # content should be a list with image_url part
        assert isinstance(user_msg["content"], list)
        types = [p["type"] for p in user_msg["content"]]
        assert "image_url" in types

    def test_vision_message_format_openai(self):
        from synth_wiki.llm.providers import OpenAIProvider
        p = OpenAIProvider(api_key="fake_openai_key")
        msgs = [
            Message(role="user", content="describe this", image_base64="data123", image_mime="image/jpeg")
        ]
        req = p.format_request(msgs, CallOpts(model="gpt-4o"))
        body = json.loads(req.content)
        content = body["messages"][0]["content"]
        assert isinstance(content, list)
        image_part = next(x for x in content if x["type"] == "image_url")
        assert "data:image/jpeg;base64,data123" in image_part["image_url"]["url"]

    def test_vision_message_format_anthropic(self):
        from synth_wiki.llm.providers import AnthropicProvider
        p = AnthropicProvider(api_key="fake_openai_key")
        msgs = [
            Message(role="user", content="describe this", image_base64="data456", image_mime="image/png")
        ]
        req = p.format_request(msgs, CallOpts(model="claude-sonnet-4-20250514"))
        body = json.loads(req.content)
        content = body["messages"][0]["content"]
        assert isinstance(content, list)
        image_part = next(x for x in content if x["type"] == "image")
        assert image_part["source"]["data"] == "data456"
        assert image_part["source"]["media_type"] == "image/png"


# ---------------------------------------------------------------------------
# Rate limiter test
# ---------------------------------------------------------------------------

class TestRateLimiter:
    def test_rate_limiter_enforces_interval(self):
        from synth_wiki.llm.client import RateLimiter
        # 60 rpm -> 1s interval
        rl = RateLimiter(requests_per_minute=60)
        with patch("synth_wiki.llm.client.time") as mock_time:
            mock_time.monotonic.side_effect = [0.0, 0.0, 0.5, 1.0]
            mock_time.sleep = MagicMock()
            rl.acquire()  # first call: _last_request is 0.0, now=0.0, no wait needed since first call
            rl.acquire()  # second call: now=0.5, elapsed=0.5 < 1.0, should sleep 0.5s
            mock_time.sleep.assert_called()

    def test_rate_limiter_zero_no_wait(self):
        from synth_wiki.llm.client import RateLimiter
        rl = RateLimiter(requests_per_minute=0)
        t0 = time.monotonic()
        rl.acquire()
        rl.acquire()
        elapsed = time.monotonic() - t0
        assert elapsed < 0.1


# ---------------------------------------------------------------------------
# Provider URL / request format tests
# ---------------------------------------------------------------------------

class TestProviderRequestFormat:
    def test_openai_request_url(self):
        from synth_wiki.llm.providers import OpenAIProvider
        p = OpenAIProvider(api_key="fake_openai_key")
        req = p.format_request([Message("user", "hi")], CallOpts(model="gpt-4o"))
        assert "chat/completions" in str(req.url)

    def test_anthropic_request_url(self):
        from synth_wiki.llm.providers import AnthropicProvider
        p = AnthropicProvider(api_key="fake_openai_key")
        req = p.format_request([Message("user", "hi")], CallOpts(model="claude-sonnet-4-20250514"))
        assert "messages" in str(req.url)
        assert req.headers["x-api-key"] == "fake_openai_key"

    def test_gemini_request_url(self):
        from synth_wiki.llm.providers import GeminiProvider
        p = GeminiProvider(api_key="fake_openai_key")
        req = p.format_request([Message("user", "hi")], CallOpts(model="gemini-2.5-flash"))
        assert "generateContent" in str(req.url)
        assert "key=fake_openai_key" in str(req.url)

    def test_anthropic_system_message_extracted(self):
        from synth_wiki.llm.providers import AnthropicProvider
        p = AnthropicProvider(api_key="fake_openai_key")
        msgs = [
            Message(role="system", content="You are a bot"),
            Message(role="user", content="hello"),
        ]
        req = p.format_request(msgs, CallOpts(model="claude-sonnet-4-20250514"))
        body = json.loads(req.content)
        assert body["system"] == "You are a bot"
        assert all(m["role"] != "system" for m in body["messages"])

    def test_ollama_uses_openai_base_url(self):
        from synth_wiki.llm.providers import build_provider, OpenAIProvider
        p = build_provider("ollama", "", "")
        assert isinstance(p, OpenAIProvider)
        assert "11434" in p._base_url
