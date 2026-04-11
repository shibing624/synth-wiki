# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Prompt caching support.
"""
from __future__ import annotations
from typing import Protocol
import httpx


class CachingProvider(Protocol):
    def setup_cache(self, system_prompt: str, model: str) -> str: ...
    def format_cached_request(self, cache_id: str, messages, opts) -> httpx.Request: ...
    def teardown_cache(self, cache_id: str) -> None: ...
