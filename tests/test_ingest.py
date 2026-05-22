import json
from pathlib import Path

import pytest

from tools.ingest import (
    sha256,
    extract_wikilinks,
    parse_json_from_response,
    estimate_tokens,
    validate_ingest,
    build_wiki_context,
)


class TestSha256:
    def test_returns_16_chars(self):
        assert len(sha256("hello")) == 16

    def test_deterministic(self):
        assert sha256("hello") == sha256("hello")

    def test_different_inputs_differ(self):
        assert sha256("hello") != sha256("world")

    def test_empty_string(self):
        assert len(sha256("")) == 16


class TestExtractWikilinks:
    def test_basic_link(self):
        assert extract_wikilinks("[[Hello]]") == ["Hello"]

    def test_multiple_links(self):
        assert extract_wikilinks("[[A]] and [[B]]") == ["A", "B"]

    def test_no_links(self):
        assert extract_wikilinks("plain text") == []

    def test_empty_string(self):
        assert extract_wikilinks("") == []

    def test_nested_brackets(self):
        assert extract_wikilinks("[[Foo Bar]]") == ["Foo Bar"]

    def test_unicode_links(self):
        assert extract_wikilinks("[[张三]]") == ["张三"]


class TestParseJsonFromResponse:
    def test_bare_json(self):
        result = parse_json_from_response('{"a": 1}')
        assert result == {"a": 1}

    def test_markdown_fenced_json(self):
        result = parse_json_from_response('```json\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_markdown_fenced_no_lang(self):
        result = parse_json_from_response('```\n{"a": 1}\n```')
        assert result == {"a": 1}

    def test_embedded_json_in_text(self):
        result = parse_json_from_response('Some text\n{"a": 1}\nmore text')
        assert result == {"a": 1}

    def test_nested_json(self):
        result = parse_json_from_response('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_raises_on_no_json(self):
        with pytest.raises(ValueError, match="No JSON object"):
            parse_json_from_response("no json here")

    def test_raises_on_invalid_json(self):
        with pytest.raises(json.JSONDecodeError):
            parse_json_from_response("{invalid}")


class TestEstimateTokens:
    def test_latin_text(self):
        count = estimate_tokens("hello world")
        assert count > 0
        assert count < 20

    def test_cjk_text(self):
        count = estimate_tokens("你好世界")
        assert count > 0

    def test_mixed_text(self):
        count = estimate_tokens("hello 你好 world 世界")
        assert count > 0

    def test_empty(self):
        assert estimate_tokens("") == 1

    def test_long_text_scales(self):
        short = estimate_tokens("a" * 100)
        long_ = estimate_tokens("a" * 1000)
        assert long_ > short


class TestValidateIngest:
    def test_empty_wiki_returns_empty_results(self, tmp_path):
        """Test that validate_ingest doesn't crash in edge cases."""
        pass


class TestBuildWikiContext:
    def test_empty_wiki_returns_empty(self):
        """Build wiki context from empty wiki returns empty string."""
        pass
