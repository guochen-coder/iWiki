#!/usr/bin/env python3
"""
iWiki MCP Server — 向 AI 智能体暴露知识库的只读查询能力。

启动方式（由 MCP 客户端自动管理）：
    python3 mcp_server.py

传输协议：stdio（标准输入/输出）
"""

import sys
import json
import os
import re
from pathlib import Path
from typing import Any

# ── 项目路径初始化 ──────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

# ── 从 .claude/settings.json 加载 LLM 配置 ────────
def _load_config():
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    if not settings_path.exists():
        return
    try:
        with open(settings_path) as f:
            settings = json.load(f)
        for key, value in settings.get("env", {}).items():
            if value and key not in os.environ:
                os.environ[key] = value
        # 桥接：确保 litellm 能找到 key
        if os.environ.get("ANTHROPIC_AUTH_TOKEN") and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_AUTH_TOKEN"]
        if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
            os.environ["DEEPSEEK_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
    except Exception:
        pass


_load_config()

# ── 常量 ────────────────────────────────────────────
WIKI_DIR = PROJECT_ROOT / "wiki"
GRAPH_DIR = PROJECT_ROOT / "graph"
GRAPH_JSON = GRAPH_DIR / "graph.json"

_EXCLUDED_PAGES = {"index.md", "log.md", "lint-report.md", "health-report.md"}


# ── 工具辅助函数 ────────────────────────────────────

def _all_wiki_pages() -> list[Path]:
    """返回 wiki/ 下所有非排除的 .md 文件列表。"""
    if not WIKI_DIR.exists():
        return []
    return [p for p in sorted(WIKI_DIR.rglob("*.md")) if p.name not in _EXCLUDED_PAGES]


def _extract_type(content: str, page_path: Path | None = None) -> str:
    """从 frontmatter 中提取 type 字段，无 frontmatter 时从路径推断。"""
    m = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    if m:
        return m.group(1).strip('"\'')
    if page_path:
        return _page_type_from_path(page_path)
    return "unknown"


def _page_type_from_path(p: Path) -> str:
    """根据页面文件目录推断类型。"""
    try:
        rel = p.relative_to(WIKI_DIR).as_posix()
        if rel.startswith("concepts/"):
            return "concept"
        if rel.startswith("entities/"):
            return "entity"
        if rel.startswith("sources/"):
            return "source"
        if rel.startswith("syntheses/"):
            return "synthesis"
    except ValueError:
        pass
    return "unknown"


def _extract_title(content: str) -> str:
    """从 frontmatter 中提取 title 字段。"""
    m = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    return m.group(1).strip() if m else ""


def _page_id(p: Path) -> str:
    """将文件路径转换为页面 ID（wiki/ 下的相对路径，去 .md）。"""
    return p.relative_to(WIKI_DIR).as_posix().replace(".md", "")


def _validate_page_id(page_id: str) -> Path:
    """安全校验：防止路径穿越。"""
    if ".." in page_id or page_id.startswith("/") or page_id.startswith("~"):
        raise ValueError(
            f"无效页面 ID '{page_id}'。"
            f"ID 是 wiki/ 下的相对路径，不含扩展名。"
        )
    page_path = (WIKI_DIR / f"{page_id}.md").resolve()
    wiki_root = WIKI_DIR.resolve()
    if not str(page_path).startswith(str(wiki_root)):
        raise ValueError(f"安全违规：'{page_id}' 解析到 wiki/ 目录外部。")
    return page_path


def _load_graph() -> dict[str, Any]:
    """加载 graph.json，文件不存在时返回空结构。"""
    if not GRAPH_JSON.exists():
        return {"nodes": [], "edges": []}
    try:
        return json.loads(GRAPH_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"nodes": [], "edges": []}


def _get_graph_neighbors_for_page(node_id: str) -> list[dict]:
    """从 graph.json 获取某节点的邻居。"""
    gd = _load_graph()
    if not gd.get("edges"):
        return []
    node_id_lower = node_id.lower()
    neighbors: list[dict] = []
    for edge in gd["edges"]:
        other = None
        if isinstance(edge.get("from"), str) and edge["from"].lower() == node_id_lower:
            other = edge["to"]
        elif isinstance(edge.get("to"), str) and edge["to"].lower() == node_id_lower:
            other = edge["from"]
        if other:
            # 找到邻居的 label
            label = other
            for node in gd.get("nodes", []):
                if node["id"] == other:
                    label = node.get("label", other)
                    break
            neighbors.append({
                "id": other,
                "label": label,
                "edge_type": edge.get("type", "UNKNOWN"),
                "confidence": edge.get("confidence", 1.0),
                "title": edge.get("title", ""),
            })
    return neighbors[:20]


# ── 工具实现 ────────────────────────────────────────

# 工具 1：search_wiki
def search_wiki_impl(query: str, page_type: str | None = None, max_results: int = 10) -> str:
    """关键词搜索 wiki 页面（标题 + 正文）。"""
    try:
        if not WIKI_DIR.exists():
            return json.dumps({
                "total": 0, "query": query, "results": [],
                "hint": "知识库为空。请先在 http://localhost:8765 摄入文档。"
            }, ensure_ascii=False)

        query_lower = query.lower()
        results = []

        for p in _all_wiki_pages():
            content = p.read_text(encoding="utf-8")
            ptype = _extract_type(content, p)
            if page_type and ptype != page_type:
                continue

            title = _extract_title(content) or p.stem
            body = re.sub(r"^---\n.*?\n---\n?", "", content, flags=re.DOTALL)
            match_in = []
            if query_lower in title.lower():
                match_in.append("title")
            if query_lower in body.lower():
                match_in.append("content")

            if not match_in:
                continue

            preview = body.strip()[:200]
            results.append({
                "id": _page_id(p),
                "title": title,
                "type": ptype,
                "path": str(p.relative_to(PROJECT_ROOT)),
                "preview": preview,
                "match_in": match_in,
                "size_bytes": len(content),
            })

            if len(results) >= max_results:
                break

        return json.dumps({
            "total": len(results),
            "query": query,
            "results": results,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "搜索出错，请检查 wiki/ 目录是否存在且可读。"
        }, ensure_ascii=False)


# 工具 2：read_wiki_page
def read_wiki_page_impl(page_id: str) -> str:
    """读取指定页面的完整 markdown 内容 + 图谱邻居信息。"""
    try:
        page_path = _validate_page_id(page_id)
        if not page_path.exists():
            return json.dumps({
                "error": f"页面 '{page_id}' 不存在",
                "hint": "使用 search_wiki 或 list_wiki_pages 查找正确的页面 ID。"
            }, ensure_ascii=False)

        content = page_path.read_text(encoding="utf-8")
        title = _extract_title(content) or page_path.stem
        ptype = _extract_type(content, page_path)

        # 提取出站 wikilinks
        outgoing = list(set(re.findall(r'\[\[([^\]]+)\]\]', content)))

        # 计算入站链接
        incoming = []
        page_stem = page_path.stem
        for p in _all_wiki_pages():
            if p == page_path:
                continue
            pc = p.read_text(encoding="utf-8")
            if f"[[{page_stem}]]" in pc:
                incoming.append(_page_id(p))

        # 图谱邻居
        neighbors = _get_graph_neighbors_for_page(_page_id(page_path))

        return json.dumps({
            "page_id": page_id,
            "title": title,
            "type": ptype,
            "path": str(page_path.relative_to(PROJECT_ROOT)),
            "markdown": content,
            "outgoing_links": outgoing,
            "incoming_links": incoming,
            "graph_neighbors": neighbors,
        }, ensure_ascii=False, indent=2)

    except ValueError as e:
        return json.dumps({
            "error": str(e),
            "hint": "使用 search_wiki 或 list_wiki_pages 查找正确的页面 ID。"
        }, ensure_ascii=False)
    except Exception as e:
        return json.dumps({
            "error": f"读取页面失败：{e}",
            "hint": "请检查文件权限或 wiki/ 目录结构。"
        }, ensure_ascii=False)


# 工具 3：list_wiki_pages
def list_wiki_pages_impl(page_type: str | None = None, offset: int = 0, limit: int = 50) -> str:
    """分页列出知识库所有页面，支持按类型过滤。"""
    try:
        pages = _all_wiki_pages()
        if not pages:
            return json.dumps({
                "total": 0, "offset": 0, "limit": limit,
                "has_more": False, "pages": [],
                "hint": "知识库为空。请先在 http://localhost:8765 摄入文档。"
            }, ensure_ascii=False)

        all_pages = []
        type_counts: dict[str, int] = {}
        for p in pages:
            content = p.read_text(encoding="utf-8")
            ptype = _extract_type(content, p)
            type_counts[ptype] = type_counts.get(ptype, 0) + 1
            if page_type and ptype != page_type:
                continue
            title = _extract_title(content) or p.stem
            outgoing = len(re.findall(r'\[\[([^\]]+)\]\]', content))
            all_pages.append({
                "id": _page_id(p),
                "title": title,
                "type": ptype,
                "path": str(p.relative_to(PROJECT_ROOT)),
                "size_bytes": len(content),
                "outbound_link_count": outgoing,
            })

        total = len(all_pages)
        paged = all_pages[offset:offset + limit]

        return json.dumps({
            "total": total,
            "offset": offset,
            "limit": limit,
            "has_more": offset + limit < total,
            "type_counts": type_counts,
            "pages": paged,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "列出页面失败，请检查 wiki/ 目录。"
        }, ensure_ascii=False)


# 工具 4：get_graph_neighbors
def get_graph_neighbors_impl(node_id: str, edge_types: list[str] | None = None,
                              min_confidence: float = 0.0, max_results: int = 30) -> str:
    """查询某节点的图谱邻居及边关系。"""
    try:
        gd = _load_graph()
        if not gd.get("edges"):
            return json.dumps({
                "total": 0, "node_id": node_id, "neighbors": [],
                "hint": "图谱为空。请先在 http://localhost:8765 构建知识图谱。"
            }, ensure_ascii=False)

        # 查找节点是否存在
        node_exists = False
        for n in gd.get("nodes", []):
            if n["id"] == node_id:
                node_exists = True
                break

        if not node_exists:
            return json.dumps({
                "total": 0, "node_id": node_id, "neighbors": [],
                "hint": f"节点 '{node_id}' 不存在。使用 list_wiki_pages 查看所有可用页面 ID。"
            }, ensure_ascii=False)

        # 收集邻居
        node_id_lower = node_id.lower()
        all_neighbors = []
        for edge in gd["edges"]:
            other = None
            if isinstance(edge.get("from"), str) and edge["from"].lower() == node_id_lower:
                other = edge["to"]
            elif isinstance(edge.get("to"), str) and edge["to"].lower() == node_id_lower:
                other = edge["from"]
            if other is None:
                continue

            # 过滤
            et = edge.get("type", "UNKNOWN")
            conf = edge.get("confidence", 1.0)
            if edge_types and et not in edge_types:
                continue
            if conf < min_confidence:
                continue

            # 找到邻居 label
            label = other
            for node in gd.get("nodes", []):
                if node["id"] == other:
                    label = node.get("label", other)
                    break

            all_neighbors.append({
                "id": other,
                "label": label,
                "edge_type": et,
                "confidence": conf,
                "title": edge.get("title", ""),
            })

        # 按置信度降序排列，截断
        all_neighbors.sort(key=lambda x: x["confidence"], reverse=True)
        truncated = all_neighbors[:max_results]

        return json.dumps({
            "total": len(truncated),
            "total_all": len(all_neighbors),
            "node_id": node_id,
            "neighbors": truncated,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "查询邻居失败，请检查 graph/graph.json 是否有效。"
        }, ensure_ascii=False)


# 工具 5：get_graph_stats
def get_graph_stats_impl() -> str:
    """返回知识图谱的统计信息。"""
    try:
        gd = _load_graph()
        nodes = gd.get("nodes", [])
        edges = gd.get("edges", [])

        if not nodes:
            return json.dumps({
                "total_nodes": 0, "total_edges": 0,
                "hint": "图谱为空。请先在 http://localhost:8765 构建知识图谱。"
            }, ensure_ascii=False)

        # 度数计算
        degree: dict[str, int] = {}
        for edge in edges:
            f = edge.get("from")
            t = edge.get("to")
            if isinstance(f, str):
                degree[f] = degree.get(f, 0) + 1
            if isinstance(t, str):
                degree[t] = degree.get(t, 0) + 1

        # 类型统计
        type_dist = {}
        for node in nodes:
            nt = node.get("type", "unknown")
            type_dist[nt] = type_dist.get(nt, 0) + 1

        # 边类型统计
        edge_type_dist = {}
        for edge in edges:
            et = edge.get("type", "UNKNOWN")
            edge_type_dist[et] = edge_type_dist.get(et, 0) + 1

        # 度数统计
        all_degrees = list(degree.values()) if degree else [0]
        max_deg = max(all_degrees)
        mean_deg = sum(all_degrees) / len(all_degrees)
        sorted_deg = sorted(degree.items(), key=lambda x: x[1], reverse=True)

        import statistics
        std_deg = statistics.stdev(all_degrees) if len(all_degrees) > 1 else 0

        # 健康评级
        if not edges:
            health_rating = "empty"
        elif len(edges) < len(nodes) * 0.5:
            health_rating = "sparse"
        elif len(edges) < len(nodes) * 1.5:
            health_rating = "moderate"
        else:
            health_rating = "dense"

        # 社区（仅统计颜色分组数）
        colors = set()
        for node in nodes:
            if node.get("group") is not None:
                colors.add(node["group"])
        community_count = len(colors) if colors else 0

        # 孤点（度数为 0 的节点）
        orphans = [n["id"] for n in nodes if degree.get(n["id"], 0) == 0]

        # God nodes (> mean + 2*std)
        god_threshold = mean_deg + 2 * std_deg if std_deg > 0 else float('inf')
        god_nodes = [
            {"id": nid, "degree": d}
            for nid, d in sorted_deg if d > god_threshold
        ]

        return json.dumps({
            "total_nodes": len(nodes),
            "total_edges": len(edges),
            "type_distribution": type_dist,
            "edge_type_distribution": edge_type_dist,
            "degree": {
                "max": max_deg,
                "mean": round(mean_deg, 2),
                "std": round(std_deg, 2),
                "top_10": [{"id": nid, "degree": d} for nid, d in sorted_deg[:10]],
            },
            "health_rating": health_rating,
            "communities": community_count,
            "orphan_count": len(orphans),
            "orphans": orphans[:20],
            "god_nodes": god_nodes[:10],
            "graph_built_at": gd.get("built", "unknown"),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "统计失败，请检查 graph/graph.json。"
        }, ensure_ascii=False)


# 工具 6：check_wiki_health
def check_wiki_health_impl() -> str:
    """检查知识库结构完整性（零 LLM 成本）。"""
    try:
        issues = []
        info = {}

        # 检查目录
        info["wiki_dir_exists"] = WIKI_DIR.exists()
        if not WIKI_DIR.exists():
            issues.append({
                "severity": "error",
                "message": "wiki/ 目录不存在",
                "hint": "请先通过 http://localhost:8765 摄入文档。"
            })
            return json.dumps({
                "status": "error",
                "issues": issues,
                "summary": {"total": 1, "errors": 1, "warnings": 0},
            }, ensure_ascii=False, indent=2)

        pages = _all_wiki_pages()
        info["total_pages"] = len(pages)

        # 检查索引
        index_path = WIKI_DIR / "index.md"
        info["has_index"] = index_path.exists()
        if not index_path.exists():
            issues.append({
                "severity": "warning",
                "message": "wiki/index.md 不存在",
                "hint": "摄入文档后会自动创建 index.md。"
            })

        # 检查空文件
        empty_files = []
        for p in pages:
            content = p.read_text(encoding="utf-8")
            if len(content.strip()) < 20:
                empty_files.append(_page_id(p))
        if empty_files:
            issues.append({
                "severity": "warning",
                "message": f"发现 {len(empty_files)} 个空页面或内容过短的页面",
                "pages": empty_files[:10],
                "hint": "这些页面内容不足 20 字符，考虑补充或删除。"
            })

        # 检查孤立页面（无入站出站链接）
        orphaned_pages = []
        for p in pages:
            content = p.read_text(encoding="utf-8")
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            if not links:
                orphaned_pages.append(_page_id(p))
        if orphaned_pages:
            issues.append({
                "severity": "info",
                "message": f"发现 {len(orphaned_pages)} 个孤立页面（无 wikilinks）",
                "pages": orphaned_pages[:10],
                "hint": "考虑添加 [[wikilinks]] 连接到其他页面。"
            })

        # 检查断链（指向不存在的页面）
        all_page_ids = {_page_id(p) for p in pages}
        broken_links = []
        for p in pages:
            content = p.read_text(encoding="utf-8")
            links = re.findall(r'\[\[([^\]]+)\]\]', content)
            for link in links:
                if link not in all_page_ids:
                    broken_links.append({
                        "source": _page_id(p),
                        "target": link,
                    })
        if broken_links:
            issues.append({
                "severity": "warning",
                "message": f"发现 {len(broken_links)} 个断链",
                "samples": broken_links[:10],
                "hint": "这些 wikilink 指向不存在的页面。"
            })

        # 日志覆盖
        log_path = WIKI_DIR / "log.md"
        if log_path.exists():
            log_lines = log_path.read_text(encoding="utf-8").strip().split("\n")
            info["log_entries"] = len([l for l in log_lines if l.strip().startswith("-")])

        # 图谱状态
        info["graph_exists"] = GRAPH_JSON.exists()

        # 统计
        errors = [i for i in issues if i["severity"] == "error"]
        warnings = [i for i in issues if i["severity"] == "warning"]

        status = "healthy" if not errors else "needs_attention"

        return json.dumps({
            "status": status,
            "issues": issues,
            "info": info,
            "summary": {
                "total": len(issues),
                "errors": len(errors),
                "warnings": len(warnings),
                "infos": len([i for i in issues if i["severity"] == "info"]),
            },
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "健康检查失败，请检查文件系统权限。"
        }, ensure_ascii=False)


# 工具 7：read_wiki_overview
def read_wiki_overview_impl() -> str:
    """返回 wiki/overview.md 和 wiki/index.md 的摘要。"""
    try:
        result = {}

        overview_path = WIKI_DIR / "overview.md"
        if overview_path.exists():
            oc = overview_path.read_text(encoding="utf-8")
            result["overview"] = {
                "exists": True,
                "markdown": oc,
                "size_bytes": len(oc),
            }
        else:
            result["overview"] = {"exists": False}

        index_path = WIKI_DIR / "index.md"
        if index_path.exists():
            ic = index_path.read_text(encoding="utf-8")
            # 简单统计各 section 的条目数
            section_counts = {}
            current_section = "其他"
            for line in ic.split("\n"):
                if line.startswith("## "):
                    current_section = line[3:].strip()
                    section_counts[current_section] = 0
                elif line.startswith("- [") and current_section:
                    section_counts[current_section] += 1

            result["index"] = {
                "exists": True,
                "markdown": ic,
                "section_counts": section_counts,
            }
        else:
            result["index"] = {"exists": False}

        # 如果都不存在，给提示
        if not result.get("overview", {}).get("exists") and not result.get("index", {}).get("exists"):
            return json.dumps({
                "overview": {"exists": False},
                "index": {"exists": False},
                "hint": "知识库概览文件不存在。请先在 http://localhost:8765 摄入文档。"
            }, ensure_ascii=False, indent=2)

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": str(e),
            "hint": "读取概览失败，请检查 wiki/ 目录权限。"
        }, ensure_ascii=False)


# 工具 8：query_wiki（LLM 驱动查询，第二阶段）
def query_wiki_impl(question: str, save_to_wiki: bool = False) -> str:
    """使用 LLM 对知识库进行语义问答。"""
    # 检查 API key
    if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
        return json.dumps({
            "error": "query_wiki 需要 LLM API Key",
            "hint": "请在 http://localhost:8765 的设置面板中配置 API Key，"
                    "或在 .claude/settings.json 中设置 ANTHROPIC_AUTH_TOKEN。"
        }, ensure_ascii=False)

    try:
        # 初始化 LLMClient
        from tools.llm_client import get_client, init_client
        try:
            _ = get_client()
        except RuntimeError:
            init_client()

        # 复用 query.py 的检索逻辑
        from tools.query import find_relevant_pages
        index_path = WIKI_DIR / "index.md"
        if index_path.exists():
            index_content = index_path.read_text(encoding="utf-8")
        else:
            index_content = ""
        relevant_pages = find_relevant_pages(question, index_content)

        # 构建上下文
        pages_context = ""
        for p in relevant_pages:
            rel = p.relative_to(PROJECT_ROOT)
            pages_context += f"\n\n### {rel}\n{p.read_text(encoding='utf-8')}"

        if not pages_context:
            return json.dumps({
                "answer": "知识库中未找到与问题相关的页面。",
                "sources": [],
                "pages_matched": 0,
            }, ensure_ascii=False)

        # 调用 LLM 综合答案
        client = get_client()
        prompt = f"""You are querying an LLM Wiki. Answer the question using the wiki pages below. Cite sources using [[PageName]] wikilink syntax.

Wiki pages:
{pages_context}

Question: {question}

Write a thorough answer. At the end, add a ### Sources section listing the pages you drew from.
"""
        resp = client.complete(
            [{"role": "user", "content": prompt}],
            max_tokens=4096,
            use_fast=False,
        )

        sources = [str(p.relative_to(WIKI_DIR).as_posix().replace(".md", "")) for p in relevant_pages]

        # 可选保存
        saved_path = None
        if save_to_wiki:
            synth_dir = WIKI_DIR / "syntheses"
            synth_dir.mkdir(parents=True, exist_ok=True)
            slug = question[:50].replace(" ", "-").replace("/", "-")
            saved = synth_dir / f"{slug}.md"
            saved.write_text(f"# {question}\n\n{resp.text}", encoding="utf-8")
            saved_path = str(saved.relative_to(PROJECT_ROOT))

        return json.dumps({
            "question": question,
            "answer": resp.text,
            "sources": sources,
            "pages_matched": len(relevant_pages),
            "tokens_used": {
                "prompt": resp.usage.prompt_tokens,
                "completion": resp.usage.completion_tokens,
            },
            "saved_to": saved_path,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({
            "error": f"查询失败：{e}",
            "hint": "请检查 LLM API Key 是否有效，或尝试减少问题复杂度。"
        }, ensure_ascii=False)


# ── MCP Server 注册与启动 ─────────────────────────

def main():
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("iWiki")

    # ── 注册工具 1：search_wiki ──
    @mcp.tool()
    def search_wiki(query: str, page_type: str | None = None, max_results: int = 10) -> str:
        """搜索 iWiki 知识库页面。关键词匹配页面标题和正文内容。支持中文和英文。
        
        Args:
            query: 搜索关键词。匹配页面标题、正文内容。
            page_type: 按类型过滤：source（源文档）、entity（人物/公司/项目）、concept（概念/框架/方法）、synthesis（已保存查询）。省略则搜索全部。
            max_results: 返回结果数量，1-30，默认 10。
        """
        return search_wiki_impl(query, page_type, max_results)

    # ── 注册工具 2：read_wiki_page ──
    @mcp.tool()
    def read_wiki_page(page_id: str) -> str:
        """读取 iWiki 知识库中指定页面的完整 Markdown 内容、出站/入站 wikilinks 及图谱邻居信息。
        
        Args:
            page_id: 页面标识符，格式为 wiki/ 目录下的相对路径（不含 .md）。如 sources/my-doc、concepts/雨影效应、entities/LangGraph。
        """
        return read_wiki_page_impl(page_id)

    # ── 注册工具 3：list_wiki_pages ──
    @mcp.tool()
    def list_wiki_pages(page_type: str | None = None, offset: int = 0, limit: int = 50) -> str:
        """分页列出 iWiki 知识库所有页面，支持按类型过滤。返回页面 ID、标题、类型、大小、出站链接数。
        
        Args:
            page_type: 按类型过滤：source、entity、concept、synthesis。省略则列出全部。
            offset: 分页偏移量，从 0 开始。
            limit: 每页数量，1-200，默认 50。
        """
        return list_wiki_pages_impl(page_type, offset, limit)

    # ── 注册工具 4：get_graph_neighbors ──
    @mcp.tool()
    def get_graph_neighbors(node_id: str, edge_types: list[str] | None = None,
                             min_confidence: float = 0.0, max_results: int = 30) -> str:
        """查询 iWiki 知识图谱中某节点的邻居节点及边关系。
        
        Args:
            node_id: 节点 ID（与页面 ID 相同）。如 concepts/雨影效应。
            edge_types: 按边类型过滤，如 ["EXTRACTED", "INFERRED"]。省略则返回所有类型。
            min_confidence: 最小置信度阈值，0.0-1.0。默认 0.0 不过滤。
            max_results: 最大返回数量，1-100，默认 30。
        """
        return get_graph_neighbors_impl(node_id, edge_types, min_confidence, max_results)

    # ── 注册工具 5：get_graph_stats ──
    @mcp.tool()
    def get_graph_stats() -> str:
        """返回 iWiki 知识图谱的统计信息：节点/边数量、类型分布、度数统计、社区数量、孤点列表、God 节点等。"""
        return get_graph_stats_impl()

    # ── 注册工具 6：check_wiki_health ──
    @mcp.tool()
    def check_wiki_health() -> str:
        """检查 iWiki 知识库结构完整性。零 LLM 成本，检查目录存在性、空文件、孤立页面、断链等。"""
        return check_wiki_health_impl()

    # ── 注册工具 7：read_wiki_overview ──
    @mcp.tool()
    def read_wiki_overview() -> str:
        """读取 iWiki 知识库的 overview.md 和 index.md 摘要内容及目录结构统计。"""
        return read_wiki_overview_impl()

    # ── 注册工具 8：query_wiki（第二阶段，需要 LLM API Key） ──
    @mcp.tool()
    def query_wiki(question: str, save_to_wiki: bool = False) -> str:
        """使用 LLM 对 iWiki 知识库进行语义问答。需要有效 LLM API Key，否则返回错误提示。
        
        Args:
            question: 关于知识库的自然语言问题。
            save_to_wiki: 是否将答案保存到 wiki/syntheses/。
        """
        return query_wiki_impl(question, save_to_wiki)

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
