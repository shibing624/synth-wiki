# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations

from dataclasses import dataclass, field

from synth_wiki.llm.client import Usage

# Tokens per byte estimate (rough average for English text)
_TOKENS_PER_BYTE = 0.25


@dataclass
class ModelPrice:
    input: float        # $ per 1M input tokens
    output: float       # $ per 1M output tokens
    cached_input: float = 0.0
    batch_input: float = 0.0
    batch_output: float = 0.0


PRICES: dict[str, dict[str, ModelPrice]] = {
    "anthropic": {
        "claude-sonnet-4-20250514": ModelPrice(3.0, 15.0, 0.3, 1.5, 7.5),
        "claude-haiku-4-5-20251001": ModelPrice(0.8, 4.0, 0.08, 0.4, 2.0),
        "claude-opus-4-6": ModelPrice(15.0, 75.0, 1.5, 7.5, 37.5),
    },
    "openai": {
        "gpt-4o": ModelPrice(2.5, 10.0, 1.25, 1.25, 5.0),
        "gpt-4o-mini": ModelPrice(0.15, 0.60, 0.075, 0.075, 0.3),
        "o3-mini": ModelPrice(1.10, 4.40, 0.55, 0.55, 2.2),
    },
    "gemini": {
        "gemini-2.5-flash": ModelPrice(0.15, 0.60, 0.0375),
        "gemini-2.5-pro": ModelPrice(1.25, 10.0, 0.3125),
        "gemini-2.0-flash": ModelPrice(0.10, 0.40, 0.025),
        "gemini-3-flash-preview": ModelPrice(0.15, 0.60, 0.0375),
        "gemini-3.1-flash-lite": ModelPrice(0.02, 0.05, 0.005),
    },
}

# Fallback pricing when model not found
_DEFAULT_PRICE = ModelPrice(1.0, 3.0, 0.1)


def _get_price(provider: str, model: str) -> ModelPrice:
    provider_prices = PRICES.get(provider, {})
    return provider_prices.get(model, _DEFAULT_PRICE)


@dataclass
class PassStats:
    model: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    estimated_cost: float = 0.0
    cache_savings: float = 0.0


@dataclass
class CostReport:
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_cached_tokens: int = 0
    total_tokens: int = 0
    estimated_cost: float = 0.0
    cache_savings: float = 0.0
    per_pass: dict[str, PassStats] = field(default_factory=dict)


class CostTracker:
    def __init__(self, provider: str, price_override: float = 0.0):
        self._provider = provider
        self._price_override = price_override
        self._entries: list[tuple[str, str, Usage, bool]] = []

    def track(self, pass_name: str, model: str, usage: Usage, batch: bool = False) -> None:
        self._entries.append((pass_name, model, usage, batch))

    def report(self) -> CostReport:
        report = CostReport()
        pass_map: dict[str, PassStats] = {}

        for pass_name, model, usage, batch in self._entries:
            price = _get_price(self._provider, model)

            if self._price_override > 0:
                input_rate = self._price_override
                output_rate = self._price_override
                cached_rate = 0.0
            elif batch:
                input_rate = price.batch_input if price.batch_input > 0 else price.input
                output_rate = price.batch_output if price.batch_output > 0 else price.output
                cached_rate = price.cached_input
            else:
                input_rate = price.input
                output_rate = price.output
                cached_rate = price.cached_input

            billable_input = usage.input_tokens - usage.cached_tokens
            call_cost = (
                (billable_input * input_rate / 1_000_000)
                + (usage.cached_tokens * cached_rate / 1_000_000)
                + (usage.output_tokens * output_rate / 1_000_000)
            )
            # cache savings = what cached tokens would have cost at full rate vs cached rate
            savings = usage.cached_tokens * (input_rate - cached_rate) / 1_000_000

            report.total_input_tokens += usage.input_tokens
            report.total_output_tokens += usage.output_tokens
            report.total_cached_tokens += usage.cached_tokens
            report.estimated_cost += call_cost
            report.cache_savings += savings

            if pass_name not in pass_map:
                pass_map[pass_name] = PassStats(model=model)
            ps = pass_map[pass_name]
            ps.input_tokens += usage.input_tokens
            ps.output_tokens += usage.output_tokens
            ps.cached_tokens += usage.cached_tokens
            ps.estimated_cost += call_cost
            ps.cache_savings += savings

        report.total_tokens = report.total_input_tokens + report.total_output_tokens
        report.per_pass = pass_map
        return report


def estimate_from_bytes(
    content_bytes: int,
    provider: str,
    model: str,
    price_override: float = 0.0,
) -> tuple[int, float]:
    tokens = int(content_bytes * _TOKENS_PER_BYTE)
    price = _get_price(provider, model)
    rate = price_override if price_override > 0 else price.input
    cost = tokens * rate / 1_000_000
    return tokens, cost


def format_report(report: CostReport) -> str:
    lines = [
        "Cost Report",
        "-----------",
        f"Total input tokens:  {report.total_input_tokens:,}",
        f"Total output tokens: {report.total_output_tokens:,}",
        f"Total cached tokens: {report.total_cached_tokens:,}",
        f"Total tokens:        {report.total_tokens:,}",
        f"Estimated cost:      ${report.estimated_cost:.4f}",
        f"Cache savings:       ${report.cache_savings:.4f}",
    ]
    if report.per_pass:
        lines.append("")
        lines.append("Per-pass breakdown:")
        for pass_name, ps in report.per_pass.items():
            lines.append(
                f"  {pass_name}: in={ps.input_tokens:,} out={ps.output_tokens:,}"
                f" cached={ps.cached_tokens:,} cost=${ps.estimated_cost:.4f}"
            )
    return "\n".join(lines)
