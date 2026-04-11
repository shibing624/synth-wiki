# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
from __future__ import annotations

import pytest

from synth_wiki.llm.client import Usage
from synth_wiki.llm.cost import (
    CostReport,
    CostTracker,
    ModelPrice,
    PRICES,
    estimate_from_bytes,
    format_report,
)


# ---------------------------------------------------------------------------
# CostTracker accumulation tests
# ---------------------------------------------------------------------------

class TestCostTrackerAccumulation:
    def test_track_single_entry(self):
        tracker = CostTracker(provider="openai")
        tracker.track("extract", "gpt-4o", Usage(input_tokens=100, output_tokens=50))
        report = tracker.report()
        assert report.total_input_tokens == 100
        assert report.total_output_tokens == 50
        assert report.total_tokens == 150

    def test_track_multiple_entries(self):
        tracker = CostTracker(provider="openai")
        tracker.track("pass1", "gpt-4o", Usage(input_tokens=100, output_tokens=50))
        tracker.track("pass2", "gpt-4o", Usage(input_tokens=200, output_tokens=80))
        report = tracker.report()
        assert report.total_input_tokens == 300
        assert report.total_output_tokens == 130
        assert report.total_tokens == 430

    def test_per_pass_breakdown(self):
        tracker = CostTracker(provider="openai")
        tracker.track("extract", "gpt-4o", Usage(input_tokens=100, output_tokens=50))
        tracker.track("extract", "gpt-4o", Usage(input_tokens=100, output_tokens=50))
        tracker.track("summarize", "gpt-4o-mini", Usage(input_tokens=200, output_tokens=80))
        report = tracker.report()
        assert "extract" in report.per_pass
        assert "summarize" in report.per_pass
        assert report.per_pass["extract"].input_tokens == 200
        assert report.per_pass["summarize"].output_tokens == 80

    def test_empty_tracker(self):
        tracker = CostTracker(provider="openai")
        report = tracker.report()
        assert report.total_tokens == 0
        assert report.estimated_cost == 0.0
        assert report.cache_savings == 0.0


# ---------------------------------------------------------------------------
# Cost calculation tests
# ---------------------------------------------------------------------------

class TestCostCalculation:
    def test_openai_gpt4o_cost(self):
        tracker = CostTracker(provider="openai")
        # gpt-4o: $2.5/1M input, $10/1M output
        tracker.track("pass1", "gpt-4o", Usage(input_tokens=1_000_000, output_tokens=1_000_000))
        report = tracker.report()
        assert abs(report.estimated_cost - 12.5) < 0.01

    def test_anthropic_sonnet_cost(self):
        tracker = CostTracker(provider="anthropic")
        # claude-sonnet-4-20250514: $3.0/1M input, $15.0/1M output
        tracker.track("pass1", "claude-sonnet-4-20250514", Usage(input_tokens=1_000_000, output_tokens=1_000_000))
        report = tracker.report()
        assert abs(report.estimated_cost - 18.0) < 0.01

    def test_gemini_flash_cost(self):
        tracker = CostTracker(provider="gemini")
        # gemini-2.5-flash: $0.15/1M input, $0.60/1M output
        tracker.track("pass1", "gemini-2.5-flash", Usage(input_tokens=1_000_000, output_tokens=1_000_000))
        report = tracker.report()
        assert abs(report.estimated_cost - 0.75) < 0.001

    def test_price_override(self):
        tracker = CostTracker(provider="openai", price_override=5.0)
        # $5.0/1M for both input and output
        tracker.track("pass1", "gpt-4o", Usage(input_tokens=1_000_000, output_tokens=1_000_000))
        report = tracker.report()
        assert abs(report.estimated_cost - 10.0) < 0.01


# ---------------------------------------------------------------------------
# Cache savings tests
# ---------------------------------------------------------------------------

class TestCacheSavings:
    def test_cache_savings_anthropic(self):
        tracker = CostTracker(provider="anthropic")
        # claude-sonnet-4: $3.0 input, $0.3 cached -> saving $2.7/1M
        usage = Usage(input_tokens=1_000_000, output_tokens=0, cached_tokens=1_000_000)
        tracker.track("pass1", "claude-sonnet-4-20250514", usage)
        report = tracker.report()
        # billable = input - cached = 0, cached billed at $0.3/1M
        assert abs(report.cache_savings - 2.7) < 0.01

    def test_no_cache_no_savings(self):
        tracker = CostTracker(provider="openai")
        usage = Usage(input_tokens=100, output_tokens=50, cached_tokens=0)
        tracker.track("pass1", "gpt-4o", usage)
        report = tracker.report()
        assert report.cache_savings == 0.0

    def test_cached_tokens_tracked(self):
        tracker = CostTracker(provider="openai")
        usage = Usage(input_tokens=500, output_tokens=100, cached_tokens=200)
        tracker.track("pass1", "gpt-4o", usage)
        report = tracker.report()
        assert report.total_cached_tokens == 200


# ---------------------------------------------------------------------------
# Batch pricing tests
# ---------------------------------------------------------------------------

class TestBatchPricing:
    def test_batch_uses_batch_rates(self):
        tracker = CostTracker(provider="openai")
        # gpt-4o batch: $1.25/1M input, $5.0/1M output
        tracker.track("pass1", "gpt-4o", Usage(input_tokens=1_000_000, output_tokens=1_000_000), batch=True)
        report = tracker.report()
        assert abs(report.estimated_cost - 6.25) < 0.01

    def test_batch_cheaper_than_standard(self):
        tracker_standard = CostTracker(provider="openai")
        tracker_batch = CostTracker(provider="openai")
        usage = Usage(input_tokens=100_000, output_tokens=50_000)
        tracker_standard.track("p", "gpt-4o", usage, batch=False)
        tracker_batch.track("p", "gpt-4o", usage, batch=True)
        assert tracker_batch.report().estimated_cost < tracker_standard.report().estimated_cost


# ---------------------------------------------------------------------------
# Unknown model default pricing
# ---------------------------------------------------------------------------

class TestUnknownModel:
    def test_unknown_model_uses_default(self):
        tracker = CostTracker(provider="openai")
        tracker.track("pass1", "unknown-model-xyz", Usage(input_tokens=1000, output_tokens=500))
        report = tracker.report()
        # Should not raise; cost should be non-zero using default pricing
        assert report.estimated_cost > 0

    def test_unknown_provider_uses_default(self):
        tracker = CostTracker(provider="unknown-provider")
        tracker.track("pass1", "some-model", Usage(input_tokens=1000, output_tokens=500))
        report = tracker.report()
        assert report.estimated_cost > 0


# ---------------------------------------------------------------------------
# estimate_from_bytes tests
# ---------------------------------------------------------------------------

class TestEstimateFromBytes:
    def test_returns_reasonable_tokens(self):
        tokens, cost = estimate_from_bytes(4000, "openai", "gpt-4o")
        # 4000 bytes * 0.25 = 1000 tokens
        assert tokens == 1000
        assert cost > 0

    def test_cost_scales_with_bytes(self):
        _, cost_small = estimate_from_bytes(1000, "openai", "gpt-4o")
        _, cost_large = estimate_from_bytes(10000, "openai", "gpt-4o")
        assert cost_large > cost_small

    def test_price_override(self):
        _, cost_default = estimate_from_bytes(4000, "openai", "gpt-4o")
        _, cost_override = estimate_from_bytes(4000, "openai", "gpt-4o", price_override=100.0)
        assert cost_override > cost_default

    def test_zero_bytes(self):
        tokens, cost = estimate_from_bytes(0, "openai", "gpt-4o")
        assert tokens == 0
        assert cost == 0.0


# ---------------------------------------------------------------------------
# format_report tests
# ---------------------------------------------------------------------------

class TestFormatReport:
    def test_format_report_basic(self):
        report = CostReport(
            total_input_tokens=1000,
            total_output_tokens=500,
            total_cached_tokens=100,
            total_tokens=1500,
            estimated_cost=0.0042,
            cache_savings=0.0001,
        )
        output = format_report(report)
        assert "Cost Report" in output
        assert "1,000" in output
        assert "$0.0042" in output

    def test_format_report_includes_per_pass(self):
        tracker = CostTracker(provider="openai")
        tracker.track("extraction", "gpt-4o", Usage(input_tokens=100, output_tokens=50))
        tracker.track("summary", "gpt-4o-mini", Usage(input_tokens=200, output_tokens=80))
        report = tracker.report()
        output = format_report(report)
        assert "extraction" in output
        assert "summary" in output

    def test_format_report_readable_string(self):
        tracker = CostTracker(provider="anthropic")
        tracker.track("p1", "claude-sonnet-4-20250514", Usage(100, 50))
        output = format_report(tracker.report())
        assert isinstance(output, str)
        assert len(output) > 20


# ---------------------------------------------------------------------------
# PRICES table sanity tests
# ---------------------------------------------------------------------------

class TestPricesTable:
    def test_all_providers_present(self):
        assert "anthropic" in PRICES
        assert "openai" in PRICES
        assert "gemini" in PRICES

    def test_model_price_fields(self):
        p = PRICES["openai"]["gpt-4o"]
        assert isinstance(p, ModelPrice)
        assert p.input > 0
        assert p.output > 0

    def test_batch_prices_lower(self):
        p = PRICES["openai"]["gpt-4o"]
        assert p.batch_input < p.input
        assert p.batch_output < p.output
