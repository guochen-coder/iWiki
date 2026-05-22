from pathlib import Path

import pytest

from tools.query import (
    QueryResult,
    WIKI_DIR as Q_WIKI_DIR,
    find_relevant_pages,
    read_file,
)
HAS_OVERVIEW = (Q_WIKI_DIR / "overview.md").exists()


class TestQueryResult:
    def test_default_values(self):
        r = QueryResult(answer="test")
        assert r.answer == "test"
        assert r.sources == []
        assert r.tokens_used == 0
        assert r.pages_matched == 0

    def test_all_fields(self):
        r = QueryResult(answer="A", sources=["a.md"], tokens_used=100, pages_matched=1)
        assert r.answer == "A"
        assert r.sources == ["a.md"]
        assert r.tokens_used == 100
        assert r.pages_matched == 1


class TestFindRelevantPages:
    def test_latin_keyword_match(self):
        from tools.query import WIKI_DIR as QD
        test_page = QD / "concepts" / "_test_ml_.md"
        try:
            test_page.parent.mkdir(parents=True, exist_ok=True)
            test_page.write_text("# ML")
            index = "- [Machine Learning](concepts/_test_ml_.md)"
            pages = find_relevant_pages("Tell me about machine learning", index)
            assert any(p.name == "_test_ml_.md" for p in pages)
        finally:
            if test_page.exists():
                test_page.unlink()

    def test_cjk_bigram_match(self):
        index = "- [机器学习](concepts/ml.md)"
        pages = find_relevant_pages("什么是机器学习", index)
        assert len(pages) >= 1

    def test_no_match_returns_empty(self):
        index = "- [Python](langs/python.md)"
        pages = find_relevant_pages("Quantum physics", index)
        if HAS_OVERVIEW:
            assert len(pages) <= 1  # only overview if it exists
        else:
            assert len(pages) == 0

    def test_empty_index(self):
        pages = find_relevant_pages("hello", "")
        if HAS_OVERVIEW:
            assert len(pages) <= 1  # only overview if it exists
        else:
            assert pages == []

    def test_multi_char_cjk_match(self):
        index = "- [深度学习框架](concepts/dl-framework.md)"
        pages = find_relevant_pages("深度 学习", index)
        assert len(pages) >= 1

    def test_case_insensitive_latin(self):
        index = "- [Machine Learning](concepts/ml.md)"
        pages = find_relevant_pages("MACHINE LEARNING", index)
        assert len(pages) >= 1

    def test_always_includes_overview(self, tmp_path):
        """When overview.md exists, it should be included in relevant pages."""
        from tools.query import WIKI_DIR
        overview = WIKI_DIR / "overview.md"
        if overview.exists():
            index = "- [ML](concepts/ml.md)"
            pages = find_relevant_pages("machine learning", index)
            overview_included = any(p.name == "overview.md" for p in pages)
            assert overview_included


class TestReadFile:
    def test_existing_file(self, tmp_path):
        f = tmp_path / "test.md"
        f.write_text("hello")
        assert read_file(f) == "hello"

    def test_missing_file(self):
        assert read_file(Path("/nonexistent/file.md")) == ""

    def test_empty_file(self, tmp_path):
        f = tmp_path / "empty.md"
        f.write_text("")
        assert read_file(f) == ""
