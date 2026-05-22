#!/usr/bin/env python3
"""iWiki FastAPI server — MVP phase."""

import sys
import os
import json
import time
import uuid
import asyncio
import threading
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path so 'from tools import ...' works
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tools.llm_client import init_client, get_total_usage

# ── Load env from .claude/settings.json on startup ────────────
def _load_claude_env():
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                settings = json.load(f)
            env = settings.get("env", {})
            for key, value in env.items():
                if value and key not in os.environ:
                    os.environ[key] = value

            # Bridge: if ANTHROPIC_AUTH_TOKEN is set but ANTHROPIC_API_KEY is not,
            # copy it so litellm can find it
            if os.environ.get("ANTHROPIC_AUTH_TOKEN") and not os.environ.get("ANTHROPIC_API_KEY"):
                os.environ["ANTHROPIC_API_KEY"] = os.environ["ANTHROPIC_AUTH_TOKEN"]

            # Bridge: ANTHROPIC_API_KEY -> DEEPSEEK_API_KEY, so user only
            # needs to configure one key regardless of provider
            if os.environ.get("ANTHROPIC_API_KEY") and not os.environ.get("DEEPSEEK_API_KEY"):
                os.environ["DEEPSEEK_API_KEY"] = os.environ["ANTHROPIC_API_KEY"]
        except Exception:
            pass

    # Set sane default model names with provider prefix for litellm
    if not os.environ.get("LLM_MODEL"):
        os.environ["LLM_MODEL"] = "anthropic/claude-sonnet-4-6"
    if not os.environ.get("LLM_MODEL_FAST"):
        os.environ["LLM_MODEL_FAST"] = "anthropic/claude-sonnet-4-6"

_load_claude_env()

init_client(
    model=os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-6"),
    fast_model=os.environ.get("LLM_MODEL_FAST"),
)

# Ensure required directories exist
for _d in ["raw", "wiki", "graph"]:
    (PROJECT_ROOT / _d).mkdir(parents=True, exist_ok=True)

from fastapi import FastAPI, UploadFile, File, Form, Query, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from tools import ingest, query, health, lint as lint_tool, build_graph
from tools.embeddings import get_store as get_embedding_store
from server.ingest_queue import IngestQueue

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(title="iWiki", docs_url=None, redoc_url=None)

# ── State ────────────────────────────────────────────────────────
_read_sem = asyncio.Semaphore(3)
_write_lock = asyncio.Lock()
tasks: dict[str, dict] = {}
usage_stats = {
    "total_requests": 0,
    "by_operation": {},
}
# Per-task progress queues: task_id -> asyncio.Queue
progress_queues: dict[str, asyncio.Queue] = {}
# Per-task cancel events: task_id -> threading.Event
active_tasks: dict[str, threading.Event] = {}
# Ingest queue (initialized lazily after all helpers are defined)
ingest_queue = None

# ── Helpers ──────────────────────────────────────────────────────
def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sanitize_error(e: Exception) -> str:
    """Convert technical auth errors into user-friendly Chinese messages."""
    msg = str(e)
    auth_errors = (
        "AuthenticationError" in msg or
        "no key is set" in msg.lower() or
        ("missing" in msg.lower() and "api" in msg.lower() and "key" in msg.lower())
    )
    if auth_errors:
        return "Claude Code 可能未登录或 API Key 未配置。请在终端运行 claude login，或在 .claude/settings.json 中配置 ANTHROPIC_API_KEY。"
    return msg

SOURCE_MAP_FILE = PROJECT_ROOT / "wiki" / ".source_map.json"

def _load_source_map() -> dict:
    try:
        if SOURCE_MAP_FILE.exists():
            return json.loads(SOURCE_MAP_FILE.read_text())
    except Exception:
        pass
    return {}

def _save_source_map(slug: str, raw_name: str, created_pages: list | None = None):
    mapping = _load_source_map()
    mapping[slug] = {"raw_name": raw_name, "created_pages": created_pages or []}
    SOURCE_MAP_FILE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE_MAP_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))

def _remove_source_map(slug: str):
    mapping = _load_source_map()
    entry = mapping.pop(slug, None)
    # Also remove the entity/concept pages created during ingest
    if entry and isinstance(entry, dict):
        for page_path in entry.get("created_pages", []):
            p = PROJECT_ROOT / "wiki" / page_path
            if p.exists():
                p.unlink()
            # Sync remove embedding
            try:
                from tools.embeddings import get_store
                get_store().remove_page(page_path)
            except Exception:
                pass
    SOURCE_MAP_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))


def make_task(status: str = "pending") -> dict:
    tid = uuid.uuid4().hex[:12]
    tasks[tid] = {"task_id": tid, "status": status, "progress": [], "result": None, "error": None}
    progress_queues[tid] = asyncio.Queue()
    active_tasks[tid] = threading.Event()
    return tasks[tid]


def cleanup_task(task_id: str):
    tasks.pop(task_id, None)
    progress_queues.pop(task_id, None)
    active_tasks.pop(task_id, None)

async def push_progress(task_id: str, msg_type: str, **kwargs):
    """Push a progress message to the task's WebSocket queue."""
    msg = {"type": msg_type, "timestamp": now_ts(), **kwargs}
    tasks[task_id]["progress"].append(msg)
    if task_id in progress_queues:
        await progress_queues[task_id].put(msg)

async def track_usage(operation: str = "unknown"):
    usage_stats["total_requests"] += 1
    if operation not in usage_stats["by_operation"]:
        usage_stats["by_operation"][operation] = {"count": 0}
    usage_stats["by_operation"][operation]["count"] += 1


async def _on_ingest_complete(task):
    """Post-processing after a queued ingest completes."""
    slug = task.result.get("slug", "") if task.result else ""
    created_pages = task.result.get("created_pages", []) if task.result else []
    if slug:
        _save_source_map(slug, task.raw_name, created_pages)
    for cp in created_pages:
        cp_path = PROJECT_ROOT / "wiki" / cp
        if cp_path.exists():
            try:
                loop = asyncio.get_event_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda path=cp, content=cp_path.read_text(encoding="utf-8"):
                            build_graph.build_graph_incremental(path, content, infer=False)
                    ),
                    timeout=30
                )
            except Exception:
                pass
    await track_usage("ingest")


# Initialize ingest queue
ingest_queue = IngestQueue(on_complete=_on_ingest_complete)

# ── Static files ─────────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse(str(PROJECT_ROOT / "web" / "index.html"))

# ── REST Endpoints ───────────────────────────────────────────────

@app.post("/api/ingest")
async def api_ingest(file: UploadFile = File(...), rebuild: bool = Query(True)):
    """Upload a document for ingestion. Uses persistent queue for serial processing."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "文件过大（>50MB），请压缩或拆分后再试"}, status_code=413)

    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._- " or '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    if not safe_name.strip():
        return JSONResponse({"error": "文件名无效"}, status_code=400)

    dest = PROJECT_ROOT / "raw" / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    tid = await ingest_queue.enqueue(str(dest), safe_name)
    return JSONResponse({"task_id": tid, "status": "queued", "message": "已加入摄入队列"})


@app.post("/api/query")
async def api_query(body: dict):
    """Ask a question against the wiki."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _read_sem:
            try:
                await push_progress(tid, "log", level="info", message=f"查询: {question}")
                await push_progress(tid, "progress", step="search", message="正在检索相关页面...")
                await push_progress(tid, "progress", step="answer", message="AI 正在综合答案...")

                loop = asyncio.get_event_loop()
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, query.query, question),
                        timeout=120
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "error", message="操作超时（2分钟），请检查网络或模型响应速度")
                    return

                await push_progress(tid, "log", level="success", message="查询完成")
                result_data = {"answer": result.answer, "sources": result.sources, "tokens_used": result.tokens_used, "pages_matched": result.pages_matched}
                await push_progress(tid, "complete", result=result_data)
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = result_data
                await track_usage("query")
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"查询失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/health")
async def api_health_check():
    """Run health check (zero API cost)."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _read_sem:
            try:
                await push_progress(tid, "log", level="info", message="执行健康检查...")
                loop = asyncio.get_event_loop()
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, health.run_health),
                        timeout=30
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "error", message="操作超时（30秒）")
                    return
                await push_progress(tid, "log", level="success", message="健康检查完成")
                await push_progress(tid, "complete", result=result)
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = result
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"健康检查失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/lint")
async def api_lint():
    """Run content quality check."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _write_lock:
            try:
                await push_progress(tid, "log", level="info", message="执行内容检查...")
                await push_progress(tid, "progress", step="lint", message="AI 正在分析内容质量...")
                loop = asyncio.get_event_loop()
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(None, lint_tool.run_lint),
                        timeout=180
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "error", message="操作超时（3分钟），请检查网络或模型响应速度")
                    return
                await push_progress(tid, "log", level="success", message="内容检查完成")
                await push_progress(tid, "complete", result=result if isinstance(result, dict) else {"report": str(result)})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = result if isinstance(result, dict) else {"report": str(result)}
                await track_usage("lint")
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"检查失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/graph")
async def api_graph(body: dict):
    """Rebuild knowledge graph."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _write_lock:
            try:
                await push_progress(tid, "log", level="info", message="开始重建图谱...")
                await push_progress(tid, "progress", step="scan", message="扫描 wiki 页面...")
                await push_progress(tid, "progress", step="extract", message="提取显式链接（第 1 阶段）...")

                loop = asyncio.get_event_loop()
                # Build graph without opening browser, with inference
                try:
                    result = await asyncio.wait_for(
                        loop.run_in_executor(
                            None, lambda: build_graph.build_graph(infer=True, open_browser=False, clean=False)
                        ),
                        timeout=600
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "error", message="图谱构建超时（10分钟），请检查网络或模型响应速度")
                    return

                await push_progress(tid, "progress", step="community", message="计算社区结构...")
                await push_progress(tid, "log", level="success", message="图谱构建完成")
                await push_progress(tid, "complete", result={"status": "ok"})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"status": "ok"}
                await track_usage("graph")
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"图谱构建失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/sources/batch-delete")
async def api_batch_delete(body: dict):
    """Delete multiple documents at once, rebuild graph once at the end."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    names = body.get("names", [])
    if not names:
        return JSONResponse({"error": "请提供要删除的文档名列表"}, status_code=400)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _write_lock:
            try:
                deleted = []
                source_map = _load_source_map()
                for source_name in names:
                    source_page = PROJECT_ROOT / "wiki" / "sources" / f"{source_name}.md"
                    entry = source_map.get(source_name, source_name)
                    raw_name = entry["raw_name"] if isinstance(entry, dict) else entry
                    raw_file = PROJECT_ROOT / "raw" / raw_name
                    if source_page.exists():
                        source_page.unlink()
                    if raw_file.exists():
                        raw_file.unlink()
                    # Also remove entity/concept pages created during ingest
                    if isinstance(entry, dict):
                        for page_path in entry.get("created_pages", []):
                            p = PROJECT_ROOT / "wiki" / page_path
                            if p.exists():
                                p.unlink()
                    source_map.pop(source_name, None)
                    deleted.append(raw_name)
                # Persist cleaned source map
                SOURCE_MAP_FILE.write_text(json.dumps(source_map, indent=2, ensure_ascii=False))

                await push_progress(tid, "log", level="success", message=f"已删除 {len(deleted)} 个文档")

                # Rebuild graph once
                await push_progress(tid, "log", level="info", message="开始重建图谱...")
                await push_progress(tid, "progress", step="graph", message="提取 wikilinks 中...")
                loop = asyncio.get_event_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            None, lambda: build_graph.build_graph(infer=False, open_browser=False, clean=False)
                        ),
                        timeout=60
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "log", level="warn", message="图谱重建超时")
                graph_json = PROJECT_ROOT / "graph" / "graph.json"
                if graph_json.exists():
                    with open(graph_json) as gf:
                        gd = json.load(gf)
                    n_nodes = len(gd.get("nodes", []))
                    n_edges = len(gd.get("edges", []))
                    await push_progress(tid, "log", level="success", message=f"图谱已更新: {n_nodes} 节点, {n_edges} 边")

                await push_progress(tid, "complete", result={"deleted": deleted})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"deleted": deleted}
            except Exception as e:
                await push_progress(tid, "log", level="error", message=f"批量删除失败: {str(e)}")
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = str(e)
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.delete("/api/sources/{source_name}")
async def api_delete_source(source_name: str):
    """Delete an ingested document."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _write_lock:
            try:
                # Remove the source page
                source_page = PROJECT_ROOT / "wiki" / "sources" / f"{source_name}.md"
                if source_page.exists():
                    source_page.unlink()

                # Remove raw file using source map (slug → original filename)
                source_map = _load_source_map()
                entry = source_map.get(source_name, source_name)
                raw_name = entry["raw_name"] if isinstance(entry, dict) else entry
                raw_file = PROJECT_ROOT / "raw" / raw_name
                if raw_file.exists():
                    raw_file.unlink()
                _remove_source_map(source_name)

                await push_progress(tid, "log", level="success", message=f"已删除: {raw_name}")

                # Auto-rebuild graph to remove deleted node
                await push_progress(tid, "log", level="info", message="开始重建图谱...")
                await push_progress(tid, "progress", step="graph", message="提取 wikilinks 中...")
                loop = asyncio.get_event_loop()
                try:
                    await asyncio.wait_for(
                        loop.run_in_executor(
                            None, lambda: build_graph.build_graph(infer=False, open_browser=False, clean=False)
                        ),
                        timeout=60
                    )
                except asyncio.TimeoutError:
                    await push_progress(tid, "log", level="warn", message="图谱重建超时")
                graph_json = PROJECT_ROOT / "graph" / "graph.json"
                if graph_json.exists():
                    with open(graph_json) as gf:
                        gd = json.load(gf)
                    n_nodes = len(gd.get("nodes", []))
                    n_edges = len(gd.get("edges", []))
                    await push_progress(tid, "log", level="success", message=f"图谱已更新: {n_nodes} 节点, {n_edges} 边")

                await push_progress(tid, "complete", result={"deleted": source_name})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"deleted": source_name}
            except Exception as e:
                await push_progress(tid, "log", level="error", message=f"删除失败: {str(e)}")
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = str(e)
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.get("/api/task/{task_id}")
async def api_task_status(task_id: str):
    """Poll task status (fallback if WebSocket unavailable)."""
    if task_id not in tasks:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(tasks[task_id])


@app.post("/api/cancel/{task_id}")
async def api_cancel_task(task_id: str):
    """Cancel a running task."""
    if task_id in active_tasks:
        active_tasks[task_id].set()
        if task_id in tasks:
            tasks[task_id]["status"] = "cancelled"
            tasks[task_id]["error"] = "用户取消"
        return JSONResponse({"status": "cancelling"})
    return JSONResponse({"status": "not_found"})


@app.get("/api/queue")
async def api_queue():
    """Return all ingest queue tasks."""
    return JSONResponse(ingest_queue.get_all())


@app.post("/api/queue/{task_id}/cancel")
async def api_queue_cancel(task_id: str):
    """Cancel a queued ingest task."""
    ok = await ingest_queue.cancel(task_id)
    return JSONResponse({"ok": ok})


@app.post("/api/queue/{task_id}/retry")
async def api_queue_retry(task_id: str):
    """Retry a failed ingest task."""
    ok = await ingest_queue.retry(task_id)
    return JSONResponse({"ok": ok})


@app.post("/api/reindex")
async def api_reindex():
    """Re-index all wiki pages into the embedding store."""
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)
    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with _write_lock:
            try:
                await push_progress(tid, "log", level="info", message="开始重索引所有页面到向量库...")
                store = get_embedding_store()
                wiki_root = PROJECT_ROOT / "wiki"
                total = 0
                pages_to_index = list(wiki_root.rglob("*.md"))
                for i, page in enumerate(pages_to_index):
                    if active_tasks.get(tid, threading.Event()).is_set():
                        await push_progress(tid, "log", level="warning", message="重索引已取消")
                        return
                    rel = str(page.relative_to(wiki_root))
                    content = page.read_text(encoding="utf-8")
                    n = store.index_page(rel, content)
                    total += n
                    if (i + 1) % 10 == 0:
                        await push_progress(tid, "progress", step="reindex", message=f"已处理 {i + 1}/{len(pages_to_index)} 页面")
                await push_progress(tid, "log", level="success", message=f"重索引完成: {len(pages_to_index)} 页面, {total} 块")
                await push_progress(tid, "complete", result={"pages": len(pages_to_index), "chunks": total})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"pages": len(pages_to_index), "chunks": total}
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"重索引失败: {err_msg}")
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg
            finally:
                cleanup_task(tid)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.get("/api/sources")
async def api_sources():
    """List all ingested documents."""
    sources_dir = PROJECT_ROOT / "wiki" / "sources"
    if not sources_dir.exists():
        return JSONResponse([])
    source_map = _load_source_map()
    files = []
    for f in sorted(sources_dir.glob("*.md")):
        slug = f.stem
        entry = source_map.get(slug, slug)
        raw_name = entry["raw_name"] if isinstance(entry, dict) else entry
        files.append({
            "name": slug,
            "raw_name": raw_name,
            "path": str(f.relative_to(PROJECT_ROOT)),
            "created_at": datetime.fromtimestamp(f.stat().st_ctime).isoformat()
        })
    return JSONResponse(files)


@app.get("/api/model")
async def api_model():
    """Return current model configuration."""
    return JSONResponse({
        "model_name": os.environ.get("LLM_MODEL", "claude-sonnet-4-6-20250514"),
        "model_fast_name": os.environ.get("LLM_MODEL_FAST", "claude-haiku-4-5-20251001"),
    })


@app.get("/api/usage")
async def api_usage():
    """Return session usage stats (requests + LLM token counts)."""
    llm_usage = get_total_usage()
    return JSONResponse({
        **usage_stats,
        "llm_usage": llm_usage,
    })


@app.get("/api/graph-data")
async def api_graph_data():
    """Return graph data for frontend visualization."""
    graph_json = PROJECT_ROOT / "graph" / "graph.json"
    if graph_json.exists():
        with open(graph_json) as f:
            return JSONResponse(json.load(f))
    return JSONResponse({"nodes": [], "edges": []})


# ── Settings (API key + model config via web UI) ─────────────────

def _read_settings_file() -> dict:
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    if settings_path.exists():
        try:
            with open(settings_path) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _write_settings_file(data: dict):
    settings_path = PROJECT_ROOT / ".claude" / "settings.json"
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    with open(settings_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


@app.get("/api/settings")
async def api_settings_get():
    """Return current settings (API key masked, model)."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    masked = ""
    if key:
        if len(key) > 10:
            masked = key[:4] + "****" + key[-4:]
        else:
            masked = "****"
    return JSONResponse({
        "api_key_masked": masked,
        "has_key": bool(key),
        "model": os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-6"),
        "model_fast": os.environ.get("LLM_MODEL_FAST", "anthropic/claude-sonnet-4-6"),
        "base_url": os.environ.get("ANTHROPIC_BASE_URL", ""),
        "language": os.environ.get("IWIKI_LANGUAGE", "zh"),
    })


@app.post("/api/settings")
async def api_settings_save(body: dict):
    """Save API key and/or model. Updates runtime + persists to file."""
    api_key = body.get("api_key", "").strip()
    model = body.get("model", "").strip()
    base_url = body.get("base_url", "").strip()

    changed = []

    # Update API key
    if api_key:
        os.environ["ANTHROPIC_API_KEY"] = api_key
        os.environ["ANTHROPIC_AUTH_TOKEN"] = api_key
        os.environ["DEEPSEEK_API_KEY"] = api_key
        changed.append("api_key")

    # Update model
    if model:
        os.environ["LLM_MODEL"] = model
        changed.append("model")

    # Update language
    if "language" in body:
        lang = body["language"]
        if lang in ("zh", "en"):
            os.environ["IWIKI_LANGUAGE"] = lang
            changed.append("language")

    # Update base URL (always update, empty string clears it)
    if "base_url" in body:
        if base_url:
            os.environ["ANTHROPIC_BASE_URL"] = base_url
        else:
            os.environ.pop("ANTHROPIC_BASE_URL", None)
        changed.append("base_url")

    # Persist to settings.json
    if changed:
        settings = _read_settings_file()
        if "env" not in settings:
            settings["env"] = {}
        if "api_key" in changed:
            settings["env"]["ANTHROPIC_AUTH_TOKEN"] = api_key
        if "model" in changed:
            settings["env"]["LLM_MODEL"] = model
        if "base_url" in changed:
            if base_url:
                settings["env"]["ANTHROPIC_BASE_URL"] = base_url
            else:
                settings["env"].pop("ANTHROPIC_BASE_URL", None)
                settings["env"].pop("ANTHROPIC_BASE_URL", None)
        if "language" in changed:
            settings["env"]["IWIKI_LANGUAGE"] = os.environ.get("IWIKI_LANGUAGE", "zh")
        _write_settings_file(settings)

    return JSONResponse({"ok": True, "changed": changed})


@app.post("/api/settings/test")
async def api_settings_test(body: dict):
    """Test current or provided API key by making a small API call."""
    test_key = body.get("api_key", "").strip()
    key_to_test = test_key or os.environ.get("ANTHROPIC_API_KEY", "")

    if not key_to_test:
        return JSONResponse({"ok": False, "error": "未提供 API Key"}, status_code=400)

    test_model = body.get("model", "").strip()
    model = test_model or os.environ.get("LLM_MODEL", "anthropic/claude-sonnet-4-6")
    test_base_url = body.get("base_url", "").strip()

    # Temporarily override env vars so litellm picks them up for all providers
    old_anthropic = os.environ.get("ANTHROPIC_API_KEY")
    old_deepseek = os.environ.get("DEEPSEEK_API_KEY")
    old_base_url = os.environ.get("ANTHROPIC_BASE_URL")
    os.environ["ANTHROPIC_API_KEY"] = key_to_test
    os.environ["ANTHROPIC_AUTH_TOKEN"] = key_to_test
    os.environ["DEEPSEEK_API_KEY"] = key_to_test
    if test_base_url:
        os.environ["ANTHROPIC_BASE_URL"] = test_base_url
    try:
        from litellm import completion
        loop = asyncio.get_event_loop()
        resp = await loop.run_in_executor(
            None,
            lambda: completion(
                model=model,
                messages=[{"role": "user", "content": "Say 'ok'"}],
                max_tokens=16,
            )
        )
        return JSONResponse({"ok": True, "model": model})
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=400)
    finally:
        if old_anthropic is not None:
            os.environ["ANTHROPIC_API_KEY"] = old_anthropic
        else:
            os.environ.pop("ANTHROPIC_API_KEY", None)
        if old_deepseek is not None:
            os.environ["DEEPSEEK_API_KEY"] = old_deepseek
        else:
            os.environ.pop("DEEPSEEK_API_KEY", None)
        if old_base_url is not None:
            os.environ["ANTHROPIC_BASE_URL"] = old_base_url
        else:
            os.environ.pop("ANTHROPIC_BASE_URL", None)


# ── WebSocket ────────────────────────────────────────────────────
@app.websocket("/ws/progress/{task_id}")
async def ws_progress(websocket: WebSocket, task_id: str):
    await websocket.accept()
    try:
        if task_id not in progress_queues:
            progress_queues[task_id] = asyncio.Queue()

        queue = progress_queues[task_id]

        # Send already-recorded history (only if WS connected after task started)
        if task_id in tasks:
            history = list(tasks[task_id]["progress"])
            for msg in history:
                await websocket.send_json(msg)

            # Drain already-sent messages from queue to avoid duplicates
            drained = 0
            while not queue.empty() and drained < len(history):
                try:
                    queue.get_nowait()
                    drained += 1
                except asyncio.QueueEmpty:
                    break

        # Stream new messages
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=30)
                await websocket.send_json(msg)
                if msg["type"] in ("complete", "error"):
                    break
            except asyncio.TimeoutError:
                await websocket.send_json({"type": "ping"})
    except WebSocketDisconnect:
        pass
    except Exception:
        pass


# ── Startup ──────────────────────────────────────────────────────
def main():
    from tools.embeddings import init_store as _init_embeddings
    try:
        _init_embeddings()
    except Exception as e:
        print(f"[iWiki] Embedding store init skipped: {e}")

    # Start file watcher (optional, graceful fallback if watchdog not installed)
    try:
        from server.file_watcher import start_watcher
        async def _auto_enqueue(fp: str, rn: str):
            await ingest_queue.enqueue(fp, rn)
        async def _auto_delete(rn: str):
            slug = Path(rn).stem
            _remove_source_map(slug)
            sp = PROJECT_ROOT / "wiki" / "sources" / f"{slug}.md"
            if sp.exists():
                sp.unlink()
        observer, watcher_handler = start_watcher(
            lambda fp, rn: asyncio.create_task(_auto_enqueue(fp, rn)),
            lambda rn: asyncio.create_task(_auto_delete(rn)),
        )
        print(f"[iWiki] File watcher started on raw/")

        async def _watcher_tick():
            while True:
                watcher_handler.tick()
                await asyncio.sleep(1)
        asyncio.create_task(_watcher_tick())
    except ImportError:
        print("[iWiki] watchdog not installed — file watcher disabled. pip install watchdog")
    except Exception as e:
        print(f"[iWiki] File watcher init failed: {e}")

    port = int(os.environ.get("PORT", 8765))
    print(f"[iWiki] Starting server on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
