# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import pytest
from unittest.mock import patch, MagicMock
from synth_wiki.embed import (
    APIEmbedder,
    OllamaEmbedder,
    new_cascade,
    ollama_available,
    DEFAULT_MODELS,
    DEFAULT_DIMENSIONS,
)


class TestAPIEmbedder:
    def test_name(self):
        e = APIEmbedder("openai", "text-embedding-3-small", "fake_key")
        assert e.name() == "openai/text-embedding-3-small"

    def test_dimensions(self):
        e = APIEmbedder("openai", "text-embedding-3-small", "fake_key", dims=1536)
        assert e.dimensions() == 1536

    @patch("synth_wiki.embed.httpx.Client")
    def test_embed_openai(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"data": [{"embedding": [0.1, 0.2, 0.3]}]}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        e = APIEmbedder("openai", "text-embedding-3-small", "fake_key")
        result = e.embed("hello")
        assert result == [0.1, 0.2, 0.3]
        assert e.dimensions() == 3  # auto-detected

    @patch("synth_wiki.embed.httpx.Client")
    def test_embed_gemini(self, mock_client_cls):
        mock_client = MagicMock()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"embedding": {"values": [0.4, 0.5]}}
        mock_resp.raise_for_status = MagicMock()
        mock_client.post.return_value = mock_resp
        mock_client_cls.return_value = mock_client

        e = APIEmbedder("gemini", "gemini-embedding-2-preview", "fake_key")
        result = e.embed("hello")
        assert result == [0.4, 0.5]


class TestOllamaEmbedder:
    def test_name(self):
        e = OllamaEmbedder()
        assert e.name() == "ollama/nomic-embed-text"

    def test_dimensions_default(self):
        e = OllamaEmbedder()
        assert e.dimensions() == 768


class TestCascade:
    def test_tier0_explicit_override(self):
        result = new_cascade("openai", "fake_key", override={"model": "custom-model", "api_key": "custom_key"})
        assert result is not None
        assert "custom-model" in result.name()

    def test_tier1_provider_default(self):
        result = new_cascade("openai", "fake_key")
        assert result is not None
        assert "text-embedding-3-small" in result.name()

    def test_no_api_key_no_ollama_returns_none(self):
        with patch("synth_wiki.embed.ollama_available", return_value=False):
            result = new_cascade("unknown_provider", "")
            assert result is None

    @patch("synth_wiki.embed.ollama_available", return_value=True)
    def test_tier2_ollama_fallback(self, mock_ollama):
        result = new_cascade("unknown_provider", "")
        assert result is not None
        assert "ollama" in result.name()

    def test_auto_detect_dimensions(self):
        e = APIEmbedder("openai", "unknown-model", "fake_key", dims=0)
        assert e.dimensions() == 0  # not yet detected


class TestOllamaAvailable:
    @patch("synth_wiki.embed.httpx.get")
    def test_available(self, mock_get):
        mock_get.return_value = MagicMock(status_code=200)
        assert ollama_available() is True

    @patch("synth_wiki.embed.httpx.get", side_effect=Exception("connection refused"))
    def test_not_available(self, mock_get):
        assert ollama_available() is False
