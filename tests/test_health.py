import shutil
from pathlib import Path

import pytest

import tools.health as health
from tools.health import (
    STUB_THRESHOLD_CHARS,
    _parse_index_links,
    _parse_log_entries,
    check_empty_files,
    check_index_sync,
    check_log_coverage,
    strip_frontmatter,
)


# ── Pure function tests (no mocking / fs needed) ────────────────────


class TestStripFrontmatter:
    def test_removes_frontmatter(self):
        assert strip_frontmatter("---\ntitle: T\n---\n\nBody") == "Body"

    def test_no_frontmatter(self):
        assert strip_frontmatter("Just body") == "Just body"

    def test_empty(self):
        assert strip_frontmatter("") == ""

    def test_only_frontmatter(self):
        assert strip_frontmatter("---\ntitle: X\n---") == ""

    def test_unclosed_frontmatter_unchanged(self):
        content = "---\ntitle: X\n\nBody"
        assert strip_frontmatter(content) == content


class TestParseIndexLinks:
    def test_extracts_md_links(self):
        assert _parse_index_links("[A](sources/a.md)") == {"sources/a.md"}

    def test_multiple_links(self):
        content = "[A](a.md) text [B](b.md)"
        assert _parse_index_links(content) == {"a.md", "b.md"}

    def test_ignores_non_md_hrefs(self):
        content = "[Web](http://x.com) [Doc](doc.md)"
        assert _parse_index_links(content) == {"doc.md"}

    def test_empty(self):
        assert _parse_index_links("") == set()

    def test_no_links(self):
        assert _parse_index_links("plain") == set()


class TestParseLogEntries:
    def test_extracts_ingest_title(self):
        assert _parse_log_entries("## [2024-01-01] ingest | My Doc") == {"my doc"}

    def test_multiple_entries(self):
        c = "## [2024-01-01] ingest | One\n## [2024-01-02] ingest | Two"
        assert _parse_log_entries(c) == {"one", "two"}

    def test_ignores_non_ingest_lines(self):
        c = "## [2024-01-01] ingest | Doc\n## [2024-01-02] lint | Report"
        assert _parse_log_entries(c) == {"doc"}

    def test_lowercases(self):
        assert _parse_log_entries("## [2024-01-01] ingest | MY Doc") == {"my doc"}

    def test_empty(self):
        assert _parse_log_entries("") == set()


# ── Fixture: ephemeral wiki directory ───────────────────────────────


@pytest.fixture
def wiki_env(monkeypatch, tmp_path):
    """Patch health module constants to point at a temp directory."""
    wiki_dir = tmp_path / "wiki"
    sources_dir = wiki_dir / "sources"
    sources_dir.mkdir(parents=True)
    index_file = wiki_dir / "index.md"
    log_file = wiki_dir / "log.md"

    monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(health, "WIKI_DIR", wiki_dir)
    monkeypatch.setattr(health, "INDEX_FILE", index_file)
    monkeypatch.setattr(health, "LOG_FILE", log_file)

    return wiki_dir, sources_dir, index_file, log_file


# ── check_empty_files ───────────────────────────────────────────────


class TestCheckEmptyFiles:
    def test_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p = tmp_path / "empty.md"
        monkeypatch.setattr(health, "read_file", lambda _: "---\ntitle: E\n---")
        result = check_empty_files([p])
        assert len(result) == 1
        assert result[0]["status"] == "empty"
        assert result[0]["body_bytes"] == 0

    def test_stub(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p = tmp_path / "stub.md"
        monkeypatch.setattr(health, "read_file", lambda _: "---\ntitle: S\n---\n\nShort")
        result = check_empty_files([p])
        assert len(result) == 1
        assert result[0]["status"] == "stub"

    def test_healthy(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p = tmp_path / "ok.md"
        content = "x" * (STUB_THRESHOLD_CHARS + 10)
        monkeypatch.setattr(health, "read_file", lambda _: content)
        result = check_empty_files([p])
        assert len(result) == 0

    def test_custom_threshold(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p = tmp_path / "t.md"
        monkeypatch.setattr(health, "read_file", lambda _: "---\n---\n\nHi")
        result = check_empty_files([p], threshold=5)
        assert len(result) == 1

    def test_results_sorted_by_body_bytes(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p1 = tmp_path / "a.md"
        p2 = tmp_path / "b.md"
        contents = {
            p1: "---\n---",
            p2: "---\n---\n\n" + "x" * 50,
        }
        monkeypatch.setattr(health, "read_file", lambda p: contents[p])
        result = check_empty_files([p1, p2])
        assert result[0]["body_bytes"] == 0
        assert result[1]["body_bytes"] == 50

    def test_non_existent_reported_as_empty(self, monkeypatch, tmp_path):
        monkeypatch.setattr(health, "REPO_ROOT", tmp_path)
        p = tmp_path / "noexist.md"
        result = check_empty_files([p])
        assert len(result) == 1
        assert result[0]["status"] == "empty"


# ── check_index_sync ────────────────────────────────────────────────


class TestCheckIndexSync:
    def test_in_sync(self, wiki_env):
        _, sources_dir, index_file, _ = wiki_env
        index_file.write_text("[A](sources/a.md)\n[B](sources/b.md)")
        (sources_dir / "a.md").write_text("a")
        (sources_dir / "b.md").write_text("b")
        pages = sorted(sources_dir.rglob("*.md"))
        result = check_index_sync(pages)
        assert result == {"in_index_not_on_disk": [], "on_disk_not_in_index": []}

    def test_stale_index_entry(self, wiki_env):
        _, sources_dir, index_file, _ = wiki_env
        index_file.write_text("[A](sources/a.md)\n[B](sources/b.md)")
        (sources_dir / "a.md").write_text("a")
        pages = sorted(sources_dir.rglob("*.md"))
        result = check_index_sync(pages)
        assert "wiki/sources/b.md" in result["in_index_not_on_disk"]

    def test_missing_from_index(self, wiki_env):
        _, sources_dir, index_file, _ = wiki_env
        index_file.write_text("[A](sources/a.md)")
        (sources_dir / "a.md").write_text("a")
        (sources_dir / "c.md").write_text("c")
        pages = sorted(sources_dir.rglob("*.md"))
        result = check_index_sync(pages)
        assert "wiki/sources/c.md" in result["on_disk_not_in_index"]

    def test_ignores_overview_md(self, wiki_env):
        wiki_dir, _, index_file, _ = wiki_env
        index_file.write_text("[Overview](overview.md)")
        (wiki_dir / "overview.md").write_text("overview")
        result = check_index_sync([])
        assert result == {"in_index_not_on_disk": [], "on_disk_not_in_index": []}

    def test_empty_index(self, wiki_env):
        _, sources_dir, _, index_file = wiki_env
        (sources_dir / "a.md").write_text("a")
        pages = sorted(sources_dir.rglob("*.md"))
        result = check_index_sync(pages)
        assert "wiki/sources/a.md" in result["on_disk_not_in_index"]

    def test_no_pages_on_disk(self, wiki_env):
        _, _, index_file, _ = wiki_env
        index_file.write_text("[A](sources/a.md)")
        result = check_index_sync([])
        assert "wiki/sources/a.md" in result["in_index_not_on_disk"]


# ── check_log_coverage ──────────────────────────────────────────────


class TestCheckLogCoverage:
    def test_all_covered_by_slug(self, wiki_env):
        _, sources_dir, _, log_file = wiki_env
        log_file.write_text("## [2024-01-01] ingest | My Source")
        (sources_dir / "my-source.md").write_text("---\ntitle: My Source\n---\n\nC")
        result = check_log_coverage([])
        assert result == []

    def test_all_covered_by_title(self, wiki_env):
        _, sources_dir, _, log_file = wiki_env
        log_file.write_text("## [2024-01-01] ingest | Cool Article")
        (sources_dir / "cool-article.md").write_text("---\ntitle: Cool Article\n---\n\nC")
        result = check_log_coverage([])
        assert result == []

    def test_missing_log_entry(self, wiki_env):
        _, sources_dir, _, log_file = wiki_env
        log_file.write_text("## [2024-01-01] ingest | Other Doc")
        (sources_dir / "unlogged.md").write_text("---\ntitle: Unlogged Doc\n---\n\nC")
        result = check_log_coverage([])
        assert len(result) == 1
        assert result[0]["slug"] == "unlogged"

    def test_no_sources_dir(self, wiki_env):
        _, sources_dir, _, _ = wiki_env
        shutil.rmtree(str(sources_dir))
        result = check_log_coverage([])
        assert result == []

    def test_empty_log(self, wiki_env):
        _, sources_dir, _, _ = wiki_env
        (sources_dir / "doc.md").write_text("---\ntitle: Doc\n---\n\nC")
        result = check_log_coverage([])
        assert len(result) == 1
