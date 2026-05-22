import json
from pathlib import Path

import pytest

from tools.build_graph import (
    extract_wikilinks,
    extract_frontmatter_type,
    page_id,
    edge_id,
    deduplicate_edges,
    build_extracted_edges,
    sha256,
    load_cache,
    save_cache,
)


class TestSha256:
    def test_full_length(self):
        h = sha256("hello")
        assert len(h) == 64

    def test_deterministic(self):
        assert sha256("hello") == sha256("hello")


class TestExtractWikilinks:
    def test_basic(self):
        assert extract_wikilinks("[[Hello]]") == ["Hello"]

    def test_deduplicates(self):
        assert extract_wikilinks("[[A]] and [[A]]") == ["A"]

    def test_no_links(self):
        assert extract_wikilinks("plain") == []

    def test_multiple_unique(self):
        links = extract_wikilinks("[[A]] and [[B]] and [[C]]")
        assert sorted(links) == ["A", "B", "C"]


class TestExtractFrontmatterType:
    def test_basic_type(self):
        content = "---\ntype: source\n---\n\nBody"
        assert extract_frontmatter_type(content) == "source"

    def test_entity_type(self):
        content = "---\ntype: entity\n---\n\nBody"
        assert extract_frontmatter_type(content) == "entity"

    def test_no_frontmatter(self):
        assert extract_frontmatter_type("Just body") == "unknown"

    def test_quoted_type(self):
        content = '---\ntype: "concept"\n---\n\nBody'
        assert extract_frontmatter_type(content) == "concept"

    def test_empty(self):
        assert extract_frontmatter_type("") == "unknown"


class TestPageId:
    def test_contains_page_stem(self):
        """page_id includes the page stem in its result."""
        from tools.build_graph import WIKI_DIR
        p = WIKI_DIR / "sources" / "_test_page_id_.md"
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("")
            result = page_id(p)
            assert "sources" in result
            assert "_test_page_id_" in result
        finally:
            if p.exists():
                p.unlink()

    def test_removes_dot_md(self):
        from tools.build_graph import WIKI_DIR
        p = WIKI_DIR / "_test_ext_.md"
        try:
            p.write_text("")
            result = page_id(p)
            assert not result.endswith(".md")
        finally:
            if p.exists():
                p.unlink()


class TestEdgeId:
    def test_format(self):
        eid = edge_id("src", "target", "EXTRACTED")
        assert eid == "src->target:EXTRACTED"

    def test_inferred_type(self):
        eid = edge_id("a", "b", "INFERRED")
        assert eid == "a->b:INFERRED"


class TestDeduplicateEdges:
    def test_deduplicates_bidirectional(self):
        edges = [
            {"from": "a", "to": "b", "type": "EXTRACTED", "confidence": 1.0},
            {"from": "b", "to": "a", "type": "INFERRED", "confidence": 0.8},
        ]
        result = deduplicate_edges(edges)
        assert len(result) == 1

    def test_keeps_highest_confidence(self):
        edges = [
            {"from": "a", "to": "b", "type": "INFERRED", "confidence": 0.5},
            {"from": "a", "to": "b", "type": "INFERRED", "confidence": 0.9},
        ]
        result = deduplicate_edges(edges)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.9

    def test_empty_list(self):
        assert deduplicate_edges([]) == []

    def test_single_edge(self):
        e = [{"from": "a", "to": "b", "type": "EXTRACTED", "confidence": 1.0}]
        assert len(deduplicate_edges(e)) == 1

    def test_different_pairs(self):
        edges = [
            {"from": "a", "to": "b", "type": "EXTRACTED", "confidence": 1.0},
            {"from": "a", "to": "c", "type": "EXTRACTED", "confidence": 1.0},
        ]
        assert len(deduplicate_edges(edges)) == 2


class TestBuildExtractedEdges:
    def test_basic_wikilink(self, monkeypatch, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        p = wiki / "source.md"
        p.write_text("Link to [[target]]")
        pt = wiki / "target.md"
        pt.write_text("# Target")
        import tools.build_graph as bg
        monkeypatch.setattr(bg, "WIKI_DIR", wiki)
        pages = [p, pt]
        edges = build_extracted_edges(pages)
        assert len(edges) >= 1
        assert "source" in edges[0]["from"]
        assert "target" in edges[0]["to"]

    def test_no_links(self, monkeypatch, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        p = wiki / "source.md"
        p.write_text("No links here")
        import tools.build_graph as bg
        monkeypatch.setattr(bg, "WIKI_DIR", wiki)
        edges = build_extracted_edges([p])
        assert edges == []

    def test_self_link_ignored(self, monkeypatch, tmp_path):
        wiki = tmp_path / "wiki"
        wiki.mkdir(parents=True)
        p = wiki / "source.md"
        p.write_text("Link to [[source]]")
        import tools.build_graph as bg
        monkeypatch.setattr(bg, "WIKI_DIR", wiki)
        edges = build_extracted_edges([p])
        assert edges == []


class TestCache:
    def test_load_cache_missing_file(self):
        assert load_cache() == {}

    def test_cache_save_and_load(self, tmp_path):
        import tools.build_graph as bg
        bg.CACHE_FILE = tmp_path / ".cache.json"
        cache = {"key": {"hash": "abc"}}
        save_cache(cache)
        assert load_cache() == cache

    def test_load_cache_corrupted(self, tmp_path):
        import tools.build_graph as bg
        bg.CACHE_FILE = tmp_path / ".cache.json"
        bg.CACHE_FILE.write_text("invalid json")
        assert load_cache() == {}
