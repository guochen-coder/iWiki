#!/usr/bin/env python3
"""iWiki FastAPI server — MVP phase."""

import sys
import os
import json
import time
import uuid
import asyncio
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add project root to path so 'from tools import ...' works
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

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

# Ensure required directories exist
for _d in ["raw", "wiki", "graph"]:
    (PROJECT_ROOT / _d).mkdir(parents=True, exist_ok=True)

from fastapi import FastAPI, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse
import uvicorn

from tools import ingest, query, health, lint as lint_tool, build_graph

# ── App ──────────────────────────────────────────────────────────
app = FastAPI(title="iWiki", docs_url=None, redoc_url=None)

# ── State ────────────────────────────────────────────────────────
op_lock = asyncio.Lock()
tasks: dict[str, dict] = {}
usage_stats = {
    "total_requests": 0,
    "total_input_tokens": 0,
    "total_output_tokens": 0,
}
# Per-task progress queues: task_id -> asyncio.Queue
progress_queues: dict[str, asyncio.Queue] = {}

# ── Helpers ──────────────────────────────────────────────────────
def now_ts() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _sanitize_error(e: Exception) -> str:
    """Convert technical auth errors into user-friendly Chinese messages."""
    msg = str(e)
    if "AuthenticationError" in msg or "no key is set" in msg.lower() or "missing" in msg.lower() and "api" in msg.lower() and "key" in msg.lower():
        return "Claude Code 可能未登录或 API Key 未配置。请在终端运行 claude login，或在 .claude/settings.json 中配置 ANTHROPIC_API_KEY。"
    return msg

def make_task(status: str = "pending") -> dict:
    tid = uuid.uuid4().hex[:12]
    tasks[tid] = {"task_id": tid, "status": status, "progress": [], "result": None, "error": None}
    progress_queues[tid] = asyncio.Queue()
    return tasks[tid]

async def push_progress(task_id: str, msg_type: str, **kwargs):
    """Push a progress message to the task's WebSocket queue."""
    msg = {"type": msg_type, "timestamp": now_ts(), **kwargs}
    tasks[task_id]["progress"].append(msg)
    if task_id in progress_queues:
        await progress_queues[task_id].put(msg)

async def track_usage(input_tokens: int = 0, output_tokens: int = 0):
    usage_stats["total_requests"] += 1
    usage_stats["total_input_tokens"] += input_tokens
    usage_stats["total_output_tokens"] += output_tokens

# ── Static files ─────────────────────────────────────────────────
@app.get("/")
async def root():
    return FileResponse(str(PROJECT_ROOT / "web" / "index.html"))

# ── REST Endpoints ───────────────────────────────────────────────

@app.post("/api/ingest")
async def api_ingest(file: UploadFile = File(...)):
    """Upload a document for ingestion."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    # Validate file size (50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "文件过大（>50MB），请压缩或拆分后再试"}, status_code=413)

    # Validate filename
    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._- " or '一' <= c <= '鿿' or '㐀' <= c <= '䶿')
    if not safe_name.strip():
        return JSONResponse({"error": "文件名无效"}, status_code=400)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                # Save uploaded file to raw/
                dest = PROJECT_ROOT / "raw" / safe_name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
                await push_progress(tid, "log", level="info", message=f"读取文件: {safe_name}")
                await push_progress(tid, "progress", step="ingest", message="AI 分析中，可能需要 30-60 秒...")

                # Run ingest in thread pool
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(None, ingest.ingest, str(dest), True)

                await push_progress(tid, "log", level="success", message=f"摄入完成: {safe_name}")

                # Auto-rebuild graph to include new nodes
                await push_progress(tid, "log", level="info", message="开始重建图谱...")
                await push_progress(tid, "progress", step="graph", message="提取 wikilinks 中...")
                loop = asyncio.get_event_loop()
                await loop.run_in_executor(
                    None, lambda: build_graph.build_graph(infer=False, open_browser=False, clean=False)
                )
                # Read graph stats for log
                graph_json = PROJECT_ROOT / "graph" / "graph.json"
                if graph_json.exists():
                    with open(graph_json) as gf:
                        gd = json.load(gf)
                    n_nodes = len(gd.get("nodes", []))
                    n_edges = len(gd.get("edges", []))
                    await push_progress(tid, "log", level="success", message=f"图谱已更新: {n_nodes} 节点, {n_edges} 边")

                await push_progress(tid, "complete", result={"ingested": safe_name})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"ingested": safe_name}
                await track_usage()
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"摄入失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/query")
async def api_query(body: dict):
    """Ask a question against the wiki."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    question = body.get("question", "").strip()
    if not question:
        return JSONResponse({"error": "问题不能为空"}, status_code=400)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                await push_progress(tid, "log", level="info", message=f"查询: {question}")
                await push_progress(tid, "progress", step="search", message="正在检索相关页面...")
                await push_progress(tid, "progress", step="answer", message="AI 正在综合答案...")

                loop = asyncio.get_event_loop()
                # query.query(question, save_path) prints answer to stdout
                # We capture it by running in executor and using a temp redirect
                answer = await loop.run_in_executor(None, lambda: _run_query(question))

                await push_progress(tid, "log", level="success", message="查询完成")
                await push_progress(tid, "complete", result={"answer": answer})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"answer": answer}
                await track_usage()
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"查询失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg

    asyncio.create_task(run())
    return JSONResponse(task)


def _run_query(question: str) -> str:
    """Run query in thread-safe manner, capturing output."""
    import io
    old_stdout = sys.stdout
    sys.stdout = captured = io.StringIO()
    try:
        query.query(question)
        return captured.getvalue()
    finally:
        sys.stdout = old_stdout


@app.post("/api/health")
async def api_health_check():
    """Run health check (zero API cost)."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                await push_progress(tid, "log", level="info", message="执行健康检查...")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, health.run_health)
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

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/lint")
async def api_lint():
    """Run content quality check."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                await push_progress(tid, "log", level="info", message="执行内容检查...")
                await push_progress(tid, "progress", step="lint", message="AI 正在分析内容质量...")
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, lint_tool.run_lint)
                await push_progress(tid, "log", level="success", message="内容检查完成")
                await push_progress(tid, "complete", result=result if isinstance(result, dict) else {"report": str(result)})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = result if isinstance(result, dict) else {"report": str(result)}
                await track_usage()
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"检查失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg

    asyncio.create_task(run())
    return JSONResponse(task)


@app.post("/api/graph")
async def api_graph(body: dict):
    """Rebuild knowledge graph."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                await push_progress(tid, "log", level="info", message="开始重建图谱...")
                await push_progress(tid, "progress", step="scan", message="扫描 wiki 页面...")
                await push_progress(tid, "progress", step="extract", message="提取显式链接（第 1 阶段）...")

                loop = asyncio.get_event_loop()
                # Build graph without opening browser, with inference
                result = await loop.run_in_executor(
                    None, lambda: build_graph.build_graph(infer=True, open_browser=False, clean=False)
                )

                await push_progress(tid, "progress", step="community", message="计算社区结构...")
                await push_progress(tid, "log", level="success", message="图谱构建完成")
                await push_progress(tid, "complete", result={"status": "ok"})
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"status": "ok"}
                await track_usage()
            except Exception as e:
                err_msg = _sanitize_error(e)
                await push_progress(tid, "log", level="error", message=f"图谱构建失败: {err_msg}")
                await push_progress(tid, "error", message=err_msg)
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = err_msg

    asyncio.create_task(run())
    return JSONResponse(task)


@app.delete("/api/sources/{source_name}")
async def api_delete_source(source_name: str):
    """Delete an ingested document."""
    if op_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    task = make_task("running")
    tid = task["task_id"]

    async def run():
        async with op_lock:
            try:
                # Remove the source page
                source_page = PROJECT_ROOT / "wiki" / "sources" / f"{source_name}.md"
                raw_file = PROJECT_ROOT / "raw" / source_name
                if source_page.exists():
                    source_page.unlink()
                if raw_file.exists():
                    raw_file.unlink()
                await push_progress(tid, "log", level="success", message=f"已删除: {source_name}")
                tasks[tid]["status"] = "completed"
                tasks[tid]["result"] = {"deleted": source_name}
            except Exception as e:
                await push_progress(tid, "log", level="error", message=f"删除失败: {str(e)}")
                tasks[tid]["status"] = "failed"
                tasks[tid]["error"] = str(e)

    asyncio.create_task(run())
    return JSONResponse(task)


@app.get("/api/task/{task_id}")
async def api_task_status(task_id: str):
    """Poll task status (fallback if WebSocket unavailable)."""
    if task_id not in tasks:
        return JSONResponse({"error": "任务不存在"}, status_code=404)
    return JSONResponse(tasks[task_id])


@app.get("/api/sources")
async def api_sources():
    """List all ingested documents."""
    sources_dir = PROJECT_ROOT / "wiki" / "sources"
    if not sources_dir.exists():
        return JSONResponse([])
    files = []
    for f in sorted(sources_dir.glob("*.md")):
        files.append({"name": f.stem, "path": str(f.relative_to(PROJECT_ROOT)), "created_at": datetime.fromtimestamp(f.stat().st_ctime).isoformat()})
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
    """Return session usage stats."""
    return JSONResponse(usage_stats)


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
    port = int(os.environ.get("PORT", 8765))
    print(f"[iWiki] Starting server on http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
