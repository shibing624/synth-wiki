# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: Batch API support for bulk LLM calls.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum


class BatchStatus(Enum):
    IN_PROGRESS = "in_progress"
    ENDED = "ended"
    FAILED = "failed"
    EXPIRED = "expired"


@dataclass
class BatchRequest:
    custom_id: str
    messages: list
    opts: object


@dataclass
class BatchResult:
    custom_id: str
    response: object = None
    error: str = ""


@dataclass
class BatchPollResult:
    status: BatchStatus
    results_url: str = ""
