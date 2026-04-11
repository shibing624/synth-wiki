# -*- coding: utf-8 -*-
"""
@author:XuMing(xuming624@qq.com)
@description: 
"""
import json
import pytest
from unittest.mock import MagicMock
from synth_wiki.compiler.concepts import (extract_concepts, parse_concepts_json, filter_noisy_concepts,
                                          deduplicate_concepts, ExtractedConcept)
from synth_wiki.compiler.summarize import SummaryResult
from synth_wiki.llm.client import Response, Usage


@pytest.fixture
def mock_client():
    client = MagicMock()
    client.chat_completion.return_value = Response(
        content='[{"name":"self-attention","aliases":["scaled dot-product"],"sources":["raw/paper.md"],"type":"technique"}]',
        model="test", usage=Usage()
    )
    return client


class TestExtractConcepts:
    def test_extracts_from_summaries(self, mock_client):
        summaries = [SummaryResult(source_path="raw/paper.md", summary="Paper about self-attention mechanisms")]
        result = extract_concepts(summaries, {}, mock_client, "test")
        assert len(result) >= 1
        assert result[0].name == "self-attention"

    def test_empty_summaries_returns_empty(self, mock_client):
        assert extract_concepts([], {}, mock_client, "test") == []

    def test_invalid_json_raises(self):
        client = MagicMock()
        client.chat_completion.return_value = Response(content="not json at all", model="test", usage=Usage())
        summaries = [SummaryResult(source_path="raw/doc.md", summary="content")]
        with pytest.raises(json.JSONDecodeError):
            extract_concepts(summaries, {}, client, "test")


class TestParseConceptsJSON:
    def test_valid_json(self):
        result = parse_concepts_json('[{"name":"test","aliases":[],"sources":[],"type":"concept"}]')
        assert len(result) == 1
        assert result[0].name == "test"

    def test_code_fenced_json(self):
        text = '```json\n[{"name":"fenced","aliases":[],"sources":[],"type":"concept"}]\n```'
        result = parse_concepts_json(text)
        assert result[0].name == "fenced"

    def test_json_with_surrounding_text(self):
        text = 'Here are concepts:\n[{"name":"embedded","aliases":[],"sources":[],"type":"concept"}]\nDone.'
        result = parse_concepts_json(text)
        assert result[0].name == "embedded"


class TestFilterNoisy:
    def test_filters_short_names(self):
        concepts = [ExtractedConcept(name="a"), ExtractedConcept(name="valid-concept")]
        result = filter_noisy_concepts(concepts)
        assert len(result) == 1
        assert result[0].name == "valid-concept"

    def test_filters_math_notation(self):
        concepts = [ExtractedConcept(name="$x^2"), ExtractedConcept(name="ok-name")]
        result = filter_noisy_concepts(concepts)
        assert len(result) == 1

    def test_filters_file_paths(self):
        concepts = [ExtractedConcept(name="src/main.md"), ExtractedConcept(name="real-concept")]
        result = filter_noisy_concepts(concepts)
        assert len(result) == 1


class TestDeduplicate:
    def test_merges_sources(self):
        c1 = ExtractedConcept(name="test", sources=["a.md"])
        c2 = ExtractedConcept(name="test", sources=["b.md"])
        result = deduplicate_concepts([c1, c2])
        assert len(result) == 1
        assert set(result[0].sources) == {"a.md", "b.md"}

    def test_merges_aliases(self):
        c1 = ExtractedConcept(name="test", aliases=["t1"])
        c2 = ExtractedConcept(name="test", aliases=["t2"])
        result = deduplicate_concepts([c1, c2])
        assert set(result[0].aliases) == {"t1", "t2"}
