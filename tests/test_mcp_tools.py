"""MCP 工具单元测试 — 不依赖真实 LLM 调用。"""
import json
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from mcp_server import (
    search_wiki_impl,
    read_wiki_page_impl,
    list_wiki_pages_impl,
    get_graph_neighbors_impl,
    get_graph_stats_impl,
    check_wiki_health_impl,
    read_wiki_overview_impl,
    query_wiki_impl,
    _validate_page_id,
    _all_wiki_pages,
    WIKI_DIR,
    GRAPH_JSON,
)


# ==========================================================
# search_wiki 工具测试
# ==========================================================

class TestSearchWiki:
    def test_chinese_keyword_match(self):
        """中文关键词能匹配中文页面标题和正文。"""
        result = json.loads(search_wiki_impl("雨影效应"))
        assert result["total"] >= 1
        ids = [r["id"] for r in result["results"]]
        assert "concepts/雨影效应" in ids

    def test_english_keyword_match(self):
        """英文关键词能匹配英文页面。"""
        result = json.loads(search_wiki_impl("Machine Learning"))
        assert result["total"] >= 1

    def test_type_filter_concept(self):
        """page_type='entity' 过滤出 entity 类型页面。"""
        result = json.loads(search_wiki_impl("微信", page_type="entity"))
        # 如果搜索结果不为空，确保类型都是 entity
        for r in result["results"]:
            assert r["type"] == "entity"

    def test_max_results_limit(self):
        """max_results 限制返回数量。"""
        result = json.loads(search_wiki_impl("微信", max_results=3))
        assert len(result["results"]) <= 3

    def test_no_match(self):
        """无匹配结果返回 total 0。"""
        result = json.loads(search_wiki_impl("xyznotexist99999"))
        assert result["total"] == 0

    def test_empty_wiki(self, monkeypatch):
        """空知识库返回 total 0 + 提示消息。"""
        import pathlib
        fake_dir = pathlib.Path("/tmp/iwiki_test_nonexistent")
        monkeypatch.setattr("mcp_server.WIKI_DIR", fake_dir)
        result = json.loads(search_wiki_impl("test"))
        assert result["total"] == 0
        assert "hint" in result


# ==========================================================
# read_wiki_page 工具测试
# ==========================================================

class TestReadWikiPage:
    def test_normal_read(self):
        """正常读取页面返回完整内容。"""
        result = json.loads(read_wiki_page_impl("concepts/雨影效应"))
        assert result["page_id"] == "concepts/雨影效应"
        assert result["title"] == "雨影效应"
        assert "markdown" in result
        assert isinstance(result["outgoing_links"], list)
        assert isinstance(result["incoming_links"], list)
        assert isinstance(result["graph_neighbors"], list)

    def test_path_traversal_rejected(self):
        """路径穿越（..）被拒绝。"""
        result = json.loads(read_wiki_page_impl("../../../etc/passwd"))
        assert "error" in result
        assert "hint" in result

    def test_absolute_path_rejected(self):
        """绝对路径被拒绝。"""
        result = json.loads(read_wiki_page_impl("/etc/passwd"))
        assert "error" in result

    def test_non_existent_page(self):
        """不存在的页面返回错误。"""
        result = json.loads(read_wiki_page_impl("concepts/不存在的页面"))
        assert "error" in result
        assert "hint" in result

    def test_outgoing_links_extracted(self):
        """正确提取出站 wikilinks。"""
        result = json.loads(read_wiki_page_impl("concepts/雨影效应"))
        assert len(result["outgoing_links"]) > 0
        assert "安第斯山脉" in result["outgoing_links"]


# ==========================================================
# list_wiki_pages 工具测试
# ==========================================================

class TestListWikiPages:
    def test_pagination(self):
        """offset 和 limit 正确分页。"""
        page1 = json.loads(list_wiki_pages_impl(limit=3, offset=0))
        page2 = json.loads(list_wiki_pages_impl(limit=3, offset=3))
        assert len(page1["pages"]) == 3
        assert len(page2["pages"]) == 3
        # 确保两页内容不同
        ids1 = [p["id"] for p in page1["pages"]]
        ids2 = [p["id"] for p in page2["pages"]]
        assert ids1 != ids2

    def test_has_more(self):
        """has_more 正确指示。"""
        result = json.loads(list_wiki_pages_impl(limit=200))
        if result["total"] <= 200:
            assert result["has_more"] is False
        else:
            assert result["has_more"] is True

    def test_type_counts_included(self):
        """type_counts 统计所有类型。"""
        result = json.loads(list_wiki_pages_impl())
        assert "type_counts" in result
        assert isinstance(result["type_counts"], dict)
        assert result["type_counts"]["unknown"] >= 1

    def test_each_page_has_required_fields(self):
        """每页都包含必要字段。"""
        result = json.loads(list_wiki_pages_impl(limit=5))
        for p in result["pages"]:
            assert "id" in p
            assert "title" in p
            assert "type" in p
            assert "path" in p
            assert "size_bytes" in p
            assert "outbound_link_count" in p


# ==========================================================
# get_graph_neighbors 工具测试
# ==========================================================

class TestGetGraphNeighbors:
    def test_normal_query(self):
        """正常查询返回邻居。"""
        result = json.loads(get_graph_neighbors_impl("concepts/雨影效应"))
        assert "neighbors" in result
        assert result["total"] >= 1

    def test_min_confidence_filter(self):
        """最小置信度过滤。"""
        result_high = json.loads(get_graph_neighbors_impl("concepts/雨影效应", min_confidence=0.9))
        assert result_high["total"] >= 1  # 所有边都是 1.0，应该能通过

    def test_nonexistent_node(self):
        """不存在的节点返回 0 结果 + 提示。"""
        result = json.loads(get_graph_neighbors_impl("xxx/不存在的节点"))
        assert result["total"] == 0
        assert "hint" in result

    def test_neighbor_has_required_fields(self):
        """每个邻居都有必要字段。"""
        result = json.loads(get_graph_neighbors_impl("concepts/雨影效应"))
        for n in result["neighbors"]:
            assert "id" in n
            assert "label" in n
            assert "edge_type" in n
            assert "confidence" in n

    def test_max_results(self):
        """max_results 限制返回数量。"""
        result = json.loads(get_graph_neighbors_impl("concepts/雨影效应", max_results=1))
        assert len(result["neighbors"]) <= 1


# ==========================================================
# get_graph_stats 工具测试
# ==========================================================

class TestGetGraphStats:
    def test_contains_key_stats(self):
        """返回必要的统计数据。"""
        result = json.loads(get_graph_stats_impl())
        assert result["total_nodes"] >= 1
        assert result["total_edges"] >= 1
        assert "type_distribution" in result
        assert "edge_type_distribution" in result
        assert "degree" in result
        assert "health_rating" in result
        assert "orphans" in result

    def test_degree_top_10(self):
        """度数 top 10 列表存在。"""
        result = json.loads(get_graph_stats_impl())
        assert len(result["degree"]["top_10"]) <= 10

    def test_orphans_list(self):
        """orphans 列表存在。"""
        result = json.loads(get_graph_stats_impl())
        assert isinstance(result["orphans"], list)


# ==========================================================
# check_wiki_health 工具测试
# ==========================================================

class TestCheckWikiHealth:
    def test_returns_status(self):
        """返回状态信息。"""
        result = json.loads(check_wiki_health_impl())
        assert result["status"] in ("healthy", "needs_attention", "error")
        assert "issues" in result
        assert "summary" in result

    def test_summary_has_counts(self):
        """summary 包含各类计数。"""
        result = json.loads(check_wiki_health_impl())
        assert "total" in result["summary"]
        assert "errors" in result["summary"]
        assert "warnings" in result["summary"]

    def test_info_has_basic_info(self):
        """info 包含基本知识库信息。"""
        result = json.loads(check_wiki_health_impl())
        assert "total_pages" in result["info"]
        assert "has_index" in result["info"]
        assert "graph_exists" in result["info"]


# ==========================================================
# read_wiki_overview 工具测试
# ==========================================================

class TestReadWikiOverview:
    def test_overview_exists(self):
        """overview.md 存在时正确返回。"""
        result = json.loads(read_wiki_overview_impl())
        assert result["overview"]["exists"] is True
        assert "markdown" in result["overview"]

    def test_index_exists(self):
        """index.md 存在时正确返回。"""
        result = json.loads(read_wiki_overview_impl())
        assert result["index"]["exists"] is True
        assert "markdown" in result["index"]

    def test_section_counts(self):
        """section_counts 统计各 section 条目数。"""
        result = json.loads(read_wiki_overview_impl())
        assert isinstance(result["index"]["section_counts"], dict)
        assert len(result["index"]["section_counts"]) >= 1


# ==========================================================
# query_wiki 工具测试（无 API key 路径）
# ==========================================================

class TestQueryWiki:
    def test_no_api_key(self, monkeypatch):
        """无 API key 时返回明确错误 + 配置指引。"""
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
        monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
        result = json.loads(query_wiki_impl("测试问题"))
        assert "error" in result
        assert "hint" in result
        # 不应该调用 LLM，所以不应该有 answer
        assert "answer" not in result


# ==========================================================
# _validate_page_id 安全测试
# ==========================================================

class TestValidatePageId:
    def test_valid_page_id(self):
        """合法的 page_id 返回 Path。"""
        path = _validate_page_id("concepts/雨影效应")
        assert path.exists()

    def test_path_traversal_dots(self):
        """.. 路径穿越被拒绝。"""
        with pytest.raises(ValueError, match="无效页面 ID"):
            _validate_page_id("../../../etc/passwd")

    def test_absolute_path(self):
        """绝对路径被拒绝。"""
        with pytest.raises(ValueError, match="无效页面 ID"):
            _validate_page_id("/etc/passwd")
