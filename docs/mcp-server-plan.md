# iWiki MCP Server 实施计划

> 给 coder agent 执行 · 基于 MCP 构建器设计方案生成 · 2026-05-22
> **状态：✅ 已完成** · 实施分支 `feat/mcp-server` · 产出 `mcp_server.py`（841 行）

## 总览

让 iWiki 知识库通过 MCP（Model Context Protocol）对外暴露，Claude Code、OpenCode 等 AI 智能体可以直接查询知识库、浏览图谱、检查健康状态。

| 阶段 | 任务数 | 预估工时 | 状态 |
|------|--------|----------|------|
| 安装依赖 | 1 | 0.5h | ✅ |
| 核心只读工具 | 7 | 4h | ✅ |
| LLM 驱动查询 | 1 | 1.5h | ✅ |
| 测试验证 | 1 | 1h | ✅ |
| **合计** | **10** | **7h** | **全部完成** |

## 架构决策

- **语言**：Python（复用 `tools/` 下现有模块）
- **传输**：stdio（本地进程，按需启动，零网络暴露）
- **进程模型**：独立 `mcp_server.py`，不嵌入 `server/server.py`
- **配置来源**：`.claude/settings.json` 的 `env` 字段加载 LLM 密钥
- **安全边界**：所有工具只读；文件访问限定在 `wiki/` + `graph/` 目录内

## 文件产出清单

```
mcp_server.py              # MCP stdio 入口（~300 行）
requirements.txt           # 新增 mcp 依赖
tests/test_mcp_tools.py    # MCP 工具单元测试（~150 行）
```

---

## 第一步：安装 MCP SDK 依赖

**文件**：`requirements.txt`

在文件末尾新增一行：

```
mcp>=1.0.0
```

然后执行安装：

```bash
source venv/bin/activate
pip install mcp>=1.0.0
```

**验收**：`python3 -c "from mcp.server import Server; print('ok')"` 无报错。

**备选方案**：如果 `mcp>=1.0.0` 安装失败（依赖冲突），降级为：

```
# 备选：旧的 Python MCP SDK
mcp[cli]>=0.9.0
```

并改用旧版 API（`mcp.server.lowlevel.Server` + `mcp.types`），但优先尝试新版。

---

## 第二步：创建 mcp_server.py

**文件**：`/Users/guochen/Documents/iWiki/mcp_server.py`（项目根目录，新建）

### 2.1 整体结构

```python
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
from pathlib import Path

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

# ── 工具实现（内联，不依赖 server.py）─────────────
# ... 见下文各工具实现 ...

# ── MCP Server 注册与启动 ─────────────────────────
def main():
    # 使用新版 FastMCP API
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("iWiki")

    # 注册工具（见下文）
    # mcp.tool("search_wiki", ...)(search_wiki_impl)
    # ...

    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### 2.2 工具实现规范

每个工具遵循此模式：

```python
def tool_impl(params: ToolParams) -> str:
    """工具简短描述。"""
    try:
        # 1. 输入校验
        _validate_input(params)

        # 2. 执行业务逻辑
        result = _do_work(params)

        # 3. 返回结构化 JSON
        return json.dumps(result, ensure_ascii=False, indent=2)

    except ValueError as e:
        # 可预期的用户错误 → isError + 建议
        return json.dumps({
            "error": str(e),
            "hint": "..."  # 明确的下一步操作建议
        }, ensure_ascii=False)
    except Exception as e:
        # 不可预期的错误 → isError + 详细信息
        return json.dumps({
            "error": f"内部错误：{e}",
            "hint": "如持续出现，请在 http://localhost:8765 的 Web UI 中检查知识库状态"
        }, ensure_ascii=False)
```

**返回格式准则**：
- 数据结果返回 JSON 字符串（智能体可程序化解析）
- 仅 `read_wiki_page` 和 `read_wiki_overview` 例外：返回原始 markdown
- 错误消息必须包含 `hint` 字段给出明确的下一步建议

---

## 第三步：实现 7 个只读工具

### 工具 1：`search_wiki`

**用途**：关键词搜索 wiki 页面（标题 + 正文），零 LLM 成本，永远可用。

**Pydantic 参数定义**：

```python
from pydantic import BaseModel, Field

class SearchWikiInput(BaseModel):
    query: str = Field(description="搜索关键词。匹配页面标题、正文内容。支持中文和英文。")
    page_type: str | None = Field(
        default=None,
        description="按类型过滤：'source'（源文档摘要）、'entity'（人物/公司/项目）、'concept'（概念/框架/方法）、'synthesis'（已保存查询）。省略则搜索全部。"
    )
    max_results: int = Field(default=10, ge=1, le=30, description="返回结果数量，1-30，默认 10。")
```

**实现逻辑**：

```python
import re
from pathlib import Path

def _all_wiki_pages() -> list[Path]:
    exclude = {"index.md", "log.md", "lint-report.md", "health-report.md"}
    return [p for p in WIKI_DIR.rglob("*.md") if p.name not in exclude]

def _extract_type(content: str) -> str:
    m = re.search(r'^type:\s*(\S+)', content, re.MULTILINE)
    return m.group(1).strip('"\'') if m else "unknown"

def _extract_title(content: str) -> str:
    m = re.search(r'^title:\s*"?([^"\n]+)"?', content, re.MULTILINE)
    return m.group(1).strip() if m else ""

def _page_id(p: Path) -> str:
    return p.relative_to(WIKI_DIR).as_posix().replace(".md", "")

def search_wiki_impl(query: str, page_type: str | None = None, max_results: int = 10) -> str:
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
            ptype = _extract_type(content)
            # 类型过滤
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
        return json.dumps({"error": str(e), "hint": "搜索出错，请检查 wiki/ 目录是否存在且可读"}, ensure_ascii=False)
```

**验收标准**：
- [ ] 中文关键词能匹配中文页面标题和正文
- [ ] `page_type="entity"` 正确过滤出 entity 类型页面
- [ ] 空知识库返回 `total: 0` + 提示消息
- [ ] 不依赖 LLM API key

### 工具 2：`read_wiki_page`

**用途**：读取指定页面的完整 markdown 内容 + 图谱邻居信息。

**Pydantic 参数**：

```python
class ReadWikiPageInput(BaseModel):
    page_id: str = Field(
        description="页面标识符。格式为 wiki/ 目录下的相对路径（不含 .md）。示例：'sources/my-doc'、'concepts/雨影效应'、'entities/LangGraph'。从 search_wiki 或 list_wiki_pages 返回的 'id' 字段获取。"
    )
```

**实现逻辑**：

```python
def _validate_page_id(page_id: str) -> Path:
    """安全校验：防止路径穿越。"""
    if ".." in page_id or page_id.startswith("/") or page_id.startswith("~"):
        raise ValueError(f"无效页面 ID '{page_id}'。ID 是 wiki/ 下的相对路径，不含扩展名。")
    page_path = (WIKI_DIR / f"{page_id}.md").resolve()
    wiki_root = WIKI_DIR.resolve()
    if not str(page_path).startswith(str(wiki_root)):
        raise ValueError(f"安全违规：'{page_id}' 解析到 wiki/ 目录外部。")
    return page_path

def read_wiki_page_impl(page_id: str) -> str:
    try:
        page_path = _validate_page_id(page_id)
        if not page_path.exists():
            return json.dumps({
                "error": f"页面 '{page_id}' 不存在",
                "hint": "使用 search_wiki 或 list_wiki_pages 查找正确的页面 ID。"
            }, ensure_ascii=False)

        content = page_path.read_text(encoding="utf-8")
        title = _extract_title(content) or page_path.stem
        ptype = _extract_type(content)

        # 提取出站 wikilinks
        outgoing = list(set(re.findall(r'\[\[([^\]]+)\]\]', content)))

        # 计算入站链接
        incoming = []
        for p in _all_wiki_pages():
            if p == page_path:
                continue
            pc = p.read_text(encoding="utf-8")
            if f"[[{page_path.stem}]]" in pc:
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
        return json.dumps({"error": str(e), "hint": "使用 search_wiki 或 list_wiki_pages 查找正确的页面 ID。"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "hint": "读取页面失败，请检查文件权限。"}, ensure_ascii=False)

def _get_graph_neighbors_for_page(node_id: str) -> list[dict]:
    """从 graph.json 获取某节点的邻居。"""
    if not GRAPH_JSON.exists():
        return []
    try:
        gd = json.loads(GRAPH_JSON.read_text())
        neighbors = []
        for edge in gd.get("edges", []):
            other = None
            if edge["from"] == node_id:
                other = edge["to"]
            elif edge["to"] == node_id:
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
    except Exception:
        return []
```

**验收标准**：
- [ ] 返回完整 markdown + 出站链接 + 入站链接 + 图谱邻居
- [ ] `page_id` 含 `..` 或绝对路径时返回安全错误
- [ ] 不存在的页面返回明确的错误 + 建议

### 工具 3：`list_wiki_pages`

**用途**：分页列出知识库所有页面，支持按类型过滤。

**Pydantic 参数**：

```python
class ListWikiPagesInput(BaseModel):
    page_type: str | None = Field(default=None, description="按类型过滤：'source'、'entity'、'concept'、'synthesis'。")
    offset: int = Field(default=0, ge=0, description="分页偏移量。")
    limit: int = Field(default=50, ge=1, le=200, description="每页数量，1-200。")
```

**实现逻辑**：

```python
def list_wiki_pages_impl(page_type: str | None = None, offset: int = 0, limit: int = 50) -> str:
    try:
        pages = _all_wiki_pages()
        if not pages:
            return json.dumps({
                "total": 0, "offset": 0, "limit": limit,
                "has_more": False, "pages": [],
                "hint": "知识库为空。请先在 http://localhost:8765 摄入文档。"
            }, ensure_ascii=False)

        # 收集页面信息
        all_pages = []
        type_counts: dict[str, int] = {}
        for p in pages:
            content = p.read_text(encoding="utf-8")
            ptype = _extract_type(content)
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
        return json.dumps({"error": str(e), "hint": "列出页面失败，请检查 wiki/ 目录。"}, ensure_ascii=False)
```

**验收标准**：
- [ ] `page_type="concept"` 仅返回 concept 页面
- [ ] `offset=10&limit=5` 正确分页
- [ ] `has_more` 字段正确指示是否有更多页
- [ ] `type_counts` 统计所有类型（不受过滤影响）

### 工具 4：`get_graph_neighbors`

**用途**：查询某节点的图谱邻居及边关系。

**Pydantic 参数**：

```python
class GetGraphNeighborsInput(BaseModel):
    node_id: str = Field(description="节点 ID（与页面 ID 相同）。示例：'concepts/雨影效应'。")
    edge_types: list[str] | None = Field(
        default=None,
        description="边类型过滤：'EXTRACTED'（显式 [[wikilink]]）、'INFERRED'（LLM 推断）、'AMBIGUOUS'（低置信度）。省略则返回全部。"
    )
    min_confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="边的最小置信度阈值。0.7 仅返回高置信度边。")
    max_neighbors: int = Field(default=20, ge=1, le=50, description="返回邻居数量上限。")
```

**实现逻辑**：

```python
def get_graph_neighbors_impl(
    node_id: str,
    edge_types: list[str] | None = None,
    min_confidence: float = 0.0,
    max_neighbors: int = 20,
) -> str:
    try:
        if not GRAPH_JSON.exists():
            return json.dumps({
                "error": "知识图谱尚未构建",
                "hint": "请在 http://localhost:8765 运行 'Build Graph'，或执行 python tools/build_graph.py。"
            }, ensure_ascii=False)

        gd = json.loads(GRAPH_JSON.read_text())

        # 查找节点
        node_info = None
        for n in gd.get("nodes", []):
            if n["id"] == node_id:
                node_info = n
                break

        if not node_info:
            all_ids = [n["id"] for n in gd.get("nodes", [])][:20]
            return json.dumps({
                "error": f"节点 '{node_id}' 不存在于图谱中",
                "hint": "使用 search_graph_nodes 或 get_graph_stats 浏览可用节点。",
                "available_nodes_sample": all_ids,
            }, ensure_ascii=False)

        # 收集邻居
        neighbors = []
        edge_type_counts: dict[str, int] = {}
        for edge in gd.get("edges", []):
            etype = edge.get("type", "UNKNOWN")
            confidence = float(edge.get("confidence", 1.0))
            # 过滤
            if edge_types and etype not in edge_types:
                continue
            if confidence < min_confidence:
                continue

            other = None
            if edge["from"] == node_id:
                other = edge["to"]
            elif edge["to"] == node_id:
                other = edge["from"]
            if not other:
                continue

            # 找到邻居 label
            other_label = other
            other_type = "unknown"
            for n in gd.get("nodes", []):
                if n["id"] == other:
                    other_label = n.get("label", other)
                    other_type = n.get("type", "unknown")
                    break

            edge_type_counts[etype] = edge_type_counts.get(etype, 0) + 1
            neighbors.append({
                "id": other,
                "label": other_label,
                "type": other_type,
                "edge_id": edge.get("id", f"{node_id}->{other}:{etype}"),
                "edge_type": etype,
                "confidence": confidence,
                "title": edge.get("title", ""),
            })

        # 按置信度降序排列，截断
        neighbors.sort(key=lambda x: x["confidence"], reverse=True)
        neighbors = neighbors[:max_neighbors]

        # 节点度数
        degree = sum(1 for e in gd.get("edges", []) if e["from"] == node_id or e["to"] == node_id)

        return json.dumps({
            "node": {
                "id": node_id,
                "label": node_info.get("label", node_id),
                "type": node_info.get("type", "unknown"),
                "community": node_info.get("group", -1),
                "degree": degree,
            },
            "neighbors": neighbors,
            "neighbor_count": len(neighbors),
            "edge_count_by_type": edge_type_counts,
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "hint": "图谱查询失败，请检查 graph/graph.json。"}, ensure_ascii=False)
```

**验收标准**：
- [ ] `min_confidence=0.7` 过滤掉 AMBIGUOUS 边
- [ ] `edge_types=["EXTRACTED"]` 仅返回显式链接
- [ ] 不存在的节点返回错误 + 可用节点列表样本
- [ ] graph.json 不存在时返回明确提示

### 工具 5：`get_graph_stats`

**用途**：返回知识图谱全局统计信息（节点数、边数、社区、孤点、god nodes 等）。

**Pydantic 参数**：

```python
class GetGraphStatsInput(BaseModel):
    include_orphans: bool = Field(default=True, description="是否列出孤立节点（度数为 0 的节点）。")
```

**实现逻辑**：

```python
def get_graph_stats_impl(include_orphans: bool = True) -> str:
    try:
        if not GRAPH_JSON.exists():
            return json.dumps({
                "error": "知识图谱尚未构建",
                "hint": "请先在 http://localhost:8765 运行 'Build Graph'。"
            }, ensure_ascii=False)

        gd = json.loads(GRAPH_JSON.read_text())
        nodes = gd.get("nodes", [])
        edges = gd.get("edges", [])

        if not nodes:
            return json.dumps({
                "node_count": 0, "edge_count": 0,
                "hint": "图谱存在但为空。请摄入文档并构建图谱。"
            }, ensure_ascii=False)

        # 度数计算
        degrees: dict[str, int] = {n["id"]: 0 for n in nodes}
        edge_type_breakdown: dict[str, int] = {}
        for e in edges:
            etype = e.get("type", "UNKNOWN")
            edge_type_breakdown[etype] = edge_type_breakdown.get(etype, 0) + 1
            degrees[e["from"]] = degrees.get(e["from"], 0) + 1
            degrees[e["to"]] = degrees.get(e["to"], 0) + 1

        n_nodes = len(nodes)
        n_edges = len(edges)
        edges_per_node = n_edges / n_nodes if n_nodes else 0

        # 健康评级
        if edges_per_node >= 2.0:
            health = "healthy"
        elif edges_per_node >= 1.0:
            health = "warning"
        else:
            health = "critical"

        # 社区
        communities: dict[int, list[str]] = {}
        for n in nodes:
            cid = n.get("group", -1)
            communities.setdefault(cid, []).append(n["id"])

        # 孤点
        orphans = [n["id"] for n in nodes if degrees.get(n["id"], 0) == 0] if include_orphans else []

        # God nodes (> mean + 2*std)
        deg_values = list(degrees.values())
        mean_deg = sum(deg_values) / len(deg_values) if deg_values else 0
        variance = sum((d - mean_deg) ** 2 for d in deg_values) / len(deg_values) if deg_values else 0
        std_deg = variance ** 0.5
        threshold = mean_deg + 2 * std_deg
        god_nodes = [
            {"id": nid, "degree": deg}
            for nid, deg in sorted(degrees.items(), key=lambda x: x[1], reverse=True)
            if deg > threshold
        ][:5]

        return json.dumps({
            "node_count": n_nodes,
            "edge_count": n_edges,
            "edges_per_node": round(edges_per_node, 2),
            "health_rating": health,
            "edge_type_breakdown": edge_type_breakdown,
            "communities": {
                "count": len(communities),
                "sizes": {str(k): len(v) for k, v in sorted(communities.items(), key=lambda x: len(x[1]), reverse=True)},
            },
            "orphans": orphans[:30],
            "orphan_count": len(orphans),
            "god_nodes": god_nodes,
            "graph_built_at": gd.get("built", "unknown"),
        }, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "hint": "图谱统计失败，请检查 graph/graph.json 格式。"}, ensure_ascii=False)
```

**验收标准**：
- [ ] 返回节点数、边数、健康评级
- [ ] `orphans` 列出所有度数为 0 的节点
- [ ] `god_nodes` 列出高度数异常节点
- [ ] 图谱为空时返回 0 计数 + 提示

### 工具 6：`check_wiki_health`

**用途**：运行结构性健康检查（零 API 成本，确定性检查）。

**Pydantic 参数**：

```python
class CheckWikiHealthInput(BaseModel):
    # 无参数
    pass
```

**实现逻辑**：直接调用 `tools/health.py` 的 `run_health()` 函数。

```python
def check_wiki_health_impl() -> str:
    try:
        from tools.health import run_health
        results = run_health()

        # 转化为更友好的输出格式
        empty_count = len(results["empty_files"])
        sync_issues = len(results["index_sync"]["in_index_not_on_disk"]) + \
                      len(results["index_sync"]["on_disk_not_in_index"])
        log_issues = len(results["log_coverage"])

        all_clean = empty_count == 0 and sync_issues == 0 and log_issues == 0
        total_issues = empty_count + sync_issues + log_issues

        return json.dumps({
            "date": results["date"],
            "total_pages": results["total_pages"],
            "issues_found": total_issues,
            "all_clean": all_clean,
            "empty_or_stub_files": results["empty_files"],
            "index_sync": results["index_sync"],
            "log_coverage_missing": results["log_coverage"],
            "summary": f"在 {results['total_pages']} 个页面中发现 {total_issues} 个问题。" if not all_clean
                       else f"✅ 所有 {results['total_pages']} 个页面检查通过。",
        }, ensure_ascii=False, indent=2)

    except ImportError:
        return json.dumps({"error": "无法导入 health 模块", "hint": "请检查 tools/health.py 是否存在。"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e), "hint": "健康检查失败。"}, ensure_ascii=False)
```

**验收标准**：
- [ ] 返回空文件、索引同步、日志覆盖三项检查结果
- [ ] `all_clean: true` 时 summary 显示通过
- [ ] 零 LLM 调用

### 工具 7：`read_wiki_overview`

**用途**：读取知识库全局概览（overview.md + index.md）。

**Pydantic 参数**：

```python
class ReadWikiOverviewInput(BaseModel):
    include_index: bool = Field(default=True, description="是否同时返回 index.md（完整目录）。")
```

**实现逻辑**：

```python
def read_wiki_overview_impl(include_index: bool = True) -> str:
    try:
        overview_path = WIKI_DIR / "overview.md"
        index_path = WIKI_DIR / "index.md"

        overview_exists = overview_path.exists()
        index_exists = index_path.exists()

        if not overview_exists and not index_exists:
            return json.dumps({
                "error": "overview.md 和 index.md 均不存在",
                "hint": "知识库可能为空。请先在 http://localhost:8765 摄入文档。"
            }, ensure_ascii=False)

        result = {
            "overview": {
                "exists": overview_exists,
                "markdown": overview_path.read_text(encoding="utf-8") if overview_exists else "",
            },
        }

        if include_index:
            index_content = index_path.read_text(encoding="utf-8") if index_exists else ""
            # 简单统计各 section 的条目数
            section_counts: dict[str, int] = {}
            current_section = None
            for line in index_content.splitlines():
                if line.startswith("## "):
                    current_section = line[3:].strip()
                    section_counts[current_section] = 0
                elif line.startswith("- [") and current_section:
                    section_counts[current_section] += 1

            result["index"] = {
                "exists": index_exists,
                "markdown": index_content,
                "section_counts": section_counts,
            }

        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return json.dumps({"error": str(e), "hint": "读取概览失败，请检查 wiki/ 目录权限。"}, ensure_ascii=False)
```

**验收标准**：
- [ ] 返回 overview.md + index.md 完整内容
- [ ] `section_counts` 统计 index 各 section 条目数
- [ ] 文件不存在时不报错，`exists: false`

---

## 第四步：LLM 驱动查询（第二阶段）

### 工具 8：`query_wiki`

**用途**：使用 LLM 对知识库进行语义问答。

**依赖**：需要 `settings.json` 中有有效的 LLM API key。

**Pydantic 参数**：

```python
class QueryWikiInput(BaseModel):
    question: str = Field(description="关于知识库的自然语言问题。")
    save_to_wiki: bool = Field(default=False, description="是否将答案保存到 wiki/syntheses/。需要写入权限。")
```

**实现逻辑**：

```python
def query_wiki_impl(question: str, save_to_wiki: bool = False) -> str:
    try:
        # 检查 API key
        if not os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
            return json.dumps({
                "error": "query_wiki 需要 LLM API Key",
                "hint": "请在 http://localhost:8765 的设置面板中配置 API Key，或在 .claude/settings.json 中设置 ANTHROPIC_AUTH_TOKEN。"
            }, ensure_ascii=False)

        # 初始化 LLMClient
        from tools.llm_client import get_client, init_client
        try:
            get_client()
        except RuntimeError:
            init_client()

        # 复用 query.py 的检索逻辑
        from tools.query import find_relevant_pages
        index_content = (WIKI_DIR / "index.md").read_text(encoding="utf-8")
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
            # 用问题前 50 字符做 slug
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
```

**验收标准**：
- [ ] 无 API key 时返回明确错误 + 配置指引
- [ ] 返回答案 + 引用来源列表 + token 用量
- [ ] `save_to_wiki=True` 将答案持久化到 syntheses/

---

## 第五步：MCP 配置

### Claude Code 配置

在 `.claude/settings.json` 中添加：

```json
{
  "mcpServers": {
    "iwiki": {
      "command": "python3",
      "args": ["mcp_server.py"],
      "cwd": "/Users/guochen/Documents/iWiki"
    }
  }
}
```

### Claude Desktop 配置

在 `claude_desktop_config.json` 中添加相同配置。

---

## 验收测试

### 单元测试

**文件**：`tests/test_mcp_tools.py`

```python
"""MCP 工具单元测试 — 不依赖真实 LLM 调用。"""
import json
import sys
from pathlib import Path

# 添加项目根目录
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

# 直接导入 mcp_server 中的工具函数
# (实际测试时需要调整导入方式)
```

测试用例清单：

| 工具 | 测试用例 |
|------|----------|
| `search_wiki` | 中文关键词匹配、类型过滤、空知识库、无匹配结果 |
| `read_wiki_page` | 正常读取、路径穿越拒绝、不存在的页面 |
| `list_wiki_pages` | 分页、类型过滤、空知识库 |
| `get_graph_neighbors` | 正常查询、最小置信度过滤、边类型过滤、不存在的节点 |
| `get_graph_stats` | 正常统计、空图谱、orphans 列表 |
| `check_wiki_health` | 正常检查、空知识库 |
| `read_wiki_overview` | overview+index 读取、文件缺失、section 统计 |
| `query_wiki` | 无 API key 报错（不测 LLM 调用本身） |

### 端到端测试

1. 启动 MCP server：
```bash
cd /Users/guochen/Documents/iWiki
echo '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}' | python3 mcp_server.py
```

2. 测试 search_wiki：
```bash
echo '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"search_wiki","arguments":{"query":"测试"}}}' | python3 mcp_server.py
```

3. 在 Claude Code 中验证：
```bash
# 配置 mcpServers 后，在 Claude Code 中直接问：
"搜索 iWiki 知识库中关于知识图谱的内容"
"iWiki 知识库的健康状态如何？"
```

**验收标准**：
- [ ] 7 个只读工具全部可在 Claude Code 中正常调用
- [ ] `pytest tests/test_mcp_tools.py` 全部通过
- [ ] 所有工具的 `hint` 字段在错误时都有明确的下一步建议

---

## 附录 A：依赖清单

```
# requirements.txt 新增
mcp>=1.0.0
pydantic>=2.0.0
```

## 附录 B：文件清单

| 文件 | 操作 | 估时 |
|------|------|------|
| `requirements.txt` | 修改（新增 mcp 依赖） | 5m |
| `mcp_server.py` | 新建（~350 行） | 4h |
| `tests/test_mcp_tools.py` | 新建（~200 行） | 1.5h |
| `.claude/settings.json` | 修改（新增 mcpServers） | 5m |

## 附录 C：关键设计约束

1. **所有工具只读** — 第一阶段不提供 ingest/delete 工具
2. **工具返回 JSON 字符串** — 智能体可程序化解析；仅 read_wiki_page 和 read_wiki_overview 返回原始 markdown
3. **错误必须含 hint** — 每个错误响应都要有明确的下一步操作建议
4. **页面 ID 格式** — `"sources/my-doc"` / `"concepts/雨影效应"`，即 wiki/ 下的相对路径去 .md
5. **零 LLM 成本基础工具** — search_wiki、list_wiki_pages、check_wiki_health 等不调 LLM，永远可用
