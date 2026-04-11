# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Embedding providers with cascade auto-detection. | Text embedding generation using various providers.
"""
from __future__ import annotations
import json
from dataclasses import dataclass
from typing import Optional, Protocol
import httpx


class Embedder(Protocol):
    def embed(self, text: str) -> list[float]: ...
    def dimensions(self) -> int: ...
    def name(self) -> str: ...


DEFAULT_MODELS = {
    "openai": "text-embedding-3-small",
    "gemini": "gemini-embedding-2-preview",
    "voyage": "voyage-3-lite",
    "mistral": "mistral-embed",
}

DEFAULT_DIMENSIONS = {
    "text-embedding-3-small": 1536,
    "gemini-embedding-2-preview": 768,
    "voyage-3-lite": 1024,
    "mistral-embed": 1024,
    "nomic-embed-text": 768,
}


class APIEmbedder:
    def __init__(self, provider: str, model: str, api_key: str, base_url: str = "", dims: int = 0):
        self._provider = provider
        self._model = model
        self._api_key = api_key
        self._base_url = base_url
        self._dims = dims
        self._client = httpx.Client(timeout=30.0)

    def name(self) -> str:
        return f"{self._provider}/{self._model}"

    def dimensions(self) -> int:
        return self._dims

    def embed(self, text: str) -> list[float]:
        if self._provider == "gemini":
            return self._embed_gemini(text)
        return self._embed_openai(text)

    def _embed_openai(self, text: str) -> list[float]:
        url = self._embedding_url()
        resp = self._client.post(
            url,
            json={"model": self._model, "input": text},
            headers={"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"},
        )
        resp.raise_for_status()
        data = resp.json()
        embedding = data["data"][0]["embedding"]
        if self._dims == 0:
            self._dims = len(embedding)
        return embedding

    def _embed_gemini(self, text: str) -> list[float]:
        base = self._base_url or "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{self._model}:embedContent?key={self._api_key}"
        body = {"model": f"models/{self._model}", "content": {"parts": [{"text": text}]}}
        resp = self._client.post(url, json=body, headers={"Content-Type": "application/json"})
        resp.raise_for_status()
        values = resp.json()["embedding"]["values"]
        self._dims = len(values)
        return values

    def _embedding_url(self) -> str:
        base = self._base_url
        if not base:
            urls = {
                "openai": "https://api.openai.com/v1",
                "voyage": "https://api.voyageai.com/v1",
                "mistral": "https://api.mistral.ai/v1",
            }
            base = urls.get(self._provider, "https://api.openai.com/v1")
        return f"{base}/embeddings"


class OllamaEmbedder:
    def __init__(self, model: str = "nomic-embed-text", dims: int = 768):
        self._model = model
        self._dims = dims
        self._client = httpx.Client(timeout=30.0)

    def name(self) -> str:
        return f"ollama/{self._model}"

    def dimensions(self) -> int:
        return self._dims

    def embed(self, text: str) -> list[float]:
        resp = self._client.post(
            "http://localhost:11434/api/embeddings",
            json={"model": self._model, "prompt": text},
        )
        resp.raise_for_status()
        embedding = resp.json()["embedding"]
        self._dims = len(embedding)
        return embedding


def ollama_available() -> bool:
    try:
        resp = httpx.get("http://localhost:11434/api/tags", timeout=2.0)
        return resp.status_code == 200
    except Exception:
        return False


def new_from_config(cfg) -> Optional[APIEmbedder | OllamaEmbedder]:
    """Create embedder from project config with cascade detection."""
    override = None
    if cfg.embed:
        override = {
            "provider": cfg.embed.provider,
            "model": cfg.embed.model,
            "dimensions": cfg.embed.dimensions,
            "api_key": cfg.embed.api_key,
            "base_url": cfg.embed.base_url,
        }
    return new_cascade(cfg.api.provider, cfg.api.api_key, cfg.api.base_url, override)


def new_cascade(provider: str, api_key: str, base_url: str = "", override: dict | None = None):
    """Cascade: explicit override > provider API > Ollama local > None."""
    # Tier 0: explicit override
    if override and override.get("model"):
        p = override.get("provider") or provider
        key = override.get("api_key") or api_key
        url = override.get("base_url") or base_url
        if key:
            dims = override.get("dimensions") or DEFAULT_DIMENSIONS.get(override["model"], 0)
            return APIEmbedder(p, override["model"], key, url, dims)

    # Tier 1: provider default
    if provider in DEFAULT_MODELS and api_key:
        model = DEFAULT_MODELS[provider]
        dims = DEFAULT_DIMENSIONS.get(model, 0)
        return APIEmbedder(provider, model, api_key, base_url, dims)

    # Tier 2: Ollama
    if ollama_available():
        return OllamaEmbedder()

    return None
