# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: SSE streaming support for LLM responses.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Callable, Protocol
import httpx

StreamCallback = Callable[[str], None]


class StreamingProvider(Protocol):
    def format_stream_request(self, messages, opts) -> httpx.Request: ...
    def parse_stream_chunk(self, data: bytes) -> tuple[str, bool]: ...
