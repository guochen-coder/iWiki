# iWiki 第四阶段功能开发计划

> 给 coder agent 执行 · 基于 AI 工程师分析生成 · 2026-05-22
> 10 项功能 · 预估 21h · 优先级分三档

## 总览

| 优先级 | 功能 | 估时 | 前置依赖 |
|--------|------|------|----------|
| 🔴 P0 | SHA256 增量缓存 | 1.5h | - |
| 🔴 P0 | 保证资料摘要生成 | 0.5h | - |
| 🔴 P0 | 自动 Embedding 闭环 | 1h | - |
| 🔴 P0 | 持久化摄入队列 | 4h | - |
| 🟡 P1 | 来源可追溯 | 1h | - |
| 🟡 P1 | 语言感知生成 | 1h | - |
| 🟡 P1 | 文件夹导入 | 3h | - |
| 🟡 P1 | 队列可视化 | 4h | P0 队列 |
| 🟡 P1 | Source 文件夹自动监听 | 3h | P0 队列 |
| 🟢 P2 | 资料源渐进渲染 | 2h | - |

**执行顺序**：P0 全部可并行 → P1 在 P0 队列完成后开始 → P2 最后

---

## 功能 1：SHA256 增量缓存

**文件**：`tools/ingest.py`（修改 ~30 行）

**目标**：摄入前检查源文件内容哈希，已摄入且未变更则跳过 LLM 调用。

### 实施

在 `tools/ingest.py` 的 `ingest()` 函数中，`source_hash` 计算后（line 264）增加缓存检查：

**1.1 新增常量**（放在文件顶部常量区，约 line 44 附近）：

```python
INGEST_CACHE_FILE = REPO_ROOT / "wiki" / ".ingest_cache.json"
```

**1.2 新增两个函数**（放在 `sha256()` 函数后面）：

```python
def _load_ingest_cache() -> dict:
    if INGEST_CACHE_FILE.exists():
        try:
            return json.loads(INGEST_CACHE_FILE.read_text())
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def _save_ingest_cache(cache: dict):
    INGEST_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    INGEST_CACHE_FILE.write_text(json.dumps(cache, indent=2, ensure_ascii=False))
```

**1.3 在 `ingest()` 函数中插入缓存检查**（在 `print(f"\nIngesting: {source.name}...")` 之前，约 line 266）：

```python
    # Check ingest cache — skip if source unchanged and all pages still exist
    ingest_cache = _load_ingest_cache()
    cached = ingest_cache.get(source_hash)
    if cached:
        all_pages_exist = all((WIKI_DIR / p).exists() for p in cached.get("pages", []))
        if all_pages_exist:
            print(f"  ⏭  Skipped (unchanged, {len(cached.get('pages', []))} pages intact)")
            return {"slug": cached["slug"], "created_pages": cached["pages"], "cached": True}
        else:
            # Stale cache — some pages deleted, re-ingest
            ingest_cache.pop(source_hash)
            _save_ingest_cache(ingest_cache)
```

**1.4 在 `ingest()` 返回前保存缓存**（在 `return {"slug": slug, ...}` 之前，约 line 370）：

```python
    # Save to ingest cache
    ingest_cache[source_hash] = {
        "slug": slug,
        "pages": created_pages,
        "ts": today,
    }
    _save_ingest_cache(ingest_cache)
```

### 验收标准

- [ ] 相同文件第二次摄入输出 "Skipped (unchanged)"，无 LLM 调用
- [ ] 删除 wiki 产出页后重新摄入同一源文件 → 重新调用 LLM
- [ ] 缓存持久化在 `wiki/.ingest_cache.json`

---

## 功能 2：保证资料摘要生成

**文件**：`tools/ingest.py`（修改 ~10 行）

**目标**：LLM 遗漏 `source_page` 字段时自动生成兜底摘要页。

### 实施

在 `ingest()` 函数中 `data = parse_json_from_response(raw)` 之后（约 line 282），增加兜底逻辑：

```python
    # ── 兜底：确保 source_page 始终存在 ──
    if not data.get("source_page"):
        print("  [warn] LLM did not return source_page, generating fallback...")
        source_ref = str(source.relative_to(REPO_ROOT) if source.is_relative_to(REPO_ROOT) else source.name)
        data["source_page"] = (
            f"title: {data.get('title', source.stem)}\n"
            f"type: source\n"
            f"sources:\n  - {source_ref}\n\n"
            f"# {data.get('title', source.stem)}\n\n"
            f"> 原始文档：`{source_ref}`\n"
            f"> 摄入日期：{today}\n"
        )

    if not data.get("title"):
        data["title"] = source.stem

    if not data.get("slug"):
        data["slug"] = source.stem
```

### 验收标准

- [ ] LLM 不返回 `source_page` 时，自动生成基础摘要页
- [ ] 兜底页面包含正确的 YAML frontmatter 和原始文档引用
- [ ] 正常情况的 LLM 输出不受影响

---

## 功能 3：自动 Embedding 闭环

**文件**：`tools/ingest.py`（检查现有代码）、`server/server.py`（微小修改）

**目标**：确认 embedding 自动触发生效，补上遗漏的场景。

### 现状检查

`ingest.py:357-368` 已有自动 embedding 逻辑：

```python
try:
    from tools.embeddings import get_store
    store = get_store()
    for page in created_pages:
        ...
        n = store.index_page(page, content)
except Exception as e:
    print(f"  [warn] embedding index failed: {e}")
```

### 需要做的

**3.1 删除页面时同步清除 embedding**（修改 `server/server.py` 的 `_remove_source_map` 函数）：

```python
def _remove_source_map(slug: str):
    mapping = _load_source_map()
    entry = mapping.pop(slug, None)
    if entry and isinstance(entry, dict):
        for page_path in entry.get("created_pages", []):
            p = PROJECT_ROOT / "wiki" / page_path
            if p.exists():
                p.unlink()
            # 同步清除 embedding
            try:
                from tools.embeddings import get_store
                get_store().remove_page(page_path)
            except Exception:
                pass
    SOURCE_MAP_FILE.write_text(json.dumps(mapping, indent=2, ensure_ascii=False))
```

**3.2 确认 `POST /api/graph` 不触发 embedding**（无需改动，当前行为正确）。

**3.3 在 server 启动时初始化 EmbeddingStore**（修改 `server/server.py`，在 `init_client()` 之后）：

```python
from tools.embeddings import init_store
init_store()
```

### 验收标准

- [ ] 摄入后自动生成 embedding（已有，确认无回归）
- [ ] 删除文档同步清除 embedding
- [ ] server 启动时 EmbeddingStore 初始化完成

---

## 功能 4：持久化摄入队列

**文件**：新建 `server/ingest_queue.py`，修改 `server/server.py`

**目标**：串行处理摄入任务，队列持久化到磁盘，重启恢复，失败自动重试最多 3 次。

### 4.1 新建 `server/ingest_queue.py`

```python
"""
Persistent ingest queue with retry logic.

- Serial processing: one ingest at a time
- Disk-persisted JSON: survives server restart
- Auto-retry: up to 3 attempts on failure
"""

import json
import asyncio
import uuid
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass, field, asdict
from typing import Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QUEUE_FILE = PROJECT_ROOT / ".ingest_queue.json"


@dataclass
class QueuedIngest:
    task_id: str
    file_path: str
    raw_name: str
    status: str = "queued"        # queued | processing | done | failed
    retries: int = 0
    max_retries: int = 3
    created_at: str = ""
    error: str | None = None
    result: dict | None = None
    progress: list[dict] = field(default_factory=list)


class IngestQueue:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._tasks: dict[str, QueuedIngest] = {}
        self._processing = False
        self._restore()

    def _restore(self):
        if QUEUE_FILE.exists():
            try:
                data = json.loads(QUEUE_FILE.read_text())
                for t in data:
                    task = QueuedIngest(**t)
                    # Reset 'processing' tasks — process died/crashed
                    if task.status == "processing":
                        task.status = "queued"
                    self._tasks[task.task_id] = task
            except (json.JSONDecodeError, TypeError):
                pass

    def _persist(self):
        try:
            data = [asdict(t) for t in self._tasks.values()]
            # Atomic write
            tmp = QUEUE_FILE.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False))
            tmp.replace(QUEUE_FILE)
        except Exception:
            pass

    async def enqueue(self, file_path: str, raw_name: str) -> str:
        async with self._lock:
            tid = uuid.uuid4().hex[:12]
            task = QueuedIngest(
                task_id=tid,
                file_path=file_path,
                raw_name=raw_name,
                created_at=datetime.now().isoformat(),
            )
            self._tasks[tid] = task
            self._persist()

        # Kick off worker
        asyncio.create_task(self._worker())
        return tid

    async def _worker(self):
        if self._processing:
            return

        async with self._lock:
            self._processing = True
            pending = [t for t in self._tasks.values() if t.status == "queued"]
            if not pending:
                self._processing = False
                return
            task = pending[0]  # FIFO
            task.status = "processing"
            self._persist()

        try:
            from tools import ingest
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, ingest.ingest, task.file_path, True)
            async with self._lock:
                task.status = "done"
                task.result = result
                self._persist()
        except Exception as e:
            async with self._lock:
                task.retries += 1
                task.error = str(e)[:500]
                if task.retries < task.max_retries:
                    task.status = "queued"
                else:
                    task.status = "failed"
                self._persist()
        finally:
            async with self._lock:
                self._processing = False
            # Schedule next
            asyncio.create_task(self._worker())

    async def cancel(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "queued":
                task.status = "failed"
                task.error = "Cancelled by user"
                self._persist()
                return True
            return False

    async def retry(self, task_id: str) -> bool:
        async with self._lock:
            task = self._tasks.get(task_id)
            if task and task.status == "failed":
                task.status = "queued"
                task.retries = 0
                task.error = None
                self._persist()
                asyncio.create_task(self._worker())
                return True
            return False

    def get_all(self) -> list[dict]:
        tasks = sorted(self._tasks.values(), key=lambda t: t.created_at, reverse=True)
        return [asdict(t) for t in tasks]
```

### 4.2 修改 `server/server.py`

**4.2.1** 初始化队列（在 `server.py` 的 `_load_claude_env()` 之后）：

```python
from server.ingest_queue import IngestQueue
ingest_queue = IngestQueue()
```

**4.2.2** 修改 `POST /api/ingest`（约 line 164）：

将原来的 `asyncio.create_task(run())` 替换为队列入队：

```python
@app.post("/api/ingest")
async def api_ingest(file: UploadFile = File(...), rebuild: bool = Query(True)):
    if _write_lock.locked():
        return JSONResponse({"error": "另一个操作正在进行，请等待"}, status_code=423)

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        return JSONResponse({"error": "文件过大（>50MB），请压缩或拆分后再试"}, status_code=413)

    safe_name = "".join(c for c in file.filename if c.isalnum() or c in "._- " or '一' <= c <= '鿿')
    if not safe_name.strip():
        return JSONResponse({"error": "文件名无效"}, status_code=400)

    # Save to raw/
    dest = PROJECT_ROOT / "raw" / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)

    # Enqueue instead of immediate execution
    tid = await ingest_queue.enqueue(str(dest), safe_name)
    return JSONResponse({"task_id": tid, "status": "queued", "message": "已加入摄入队列"})
```

**4.2.3** 新增队列管理端点：

```python
@app.get("/api/queue")
async def api_queue():
    return JSONResponse(ingest_queue.get_all())

@app.post("/api/queue/{task_id}/cancel")
async def api_queue_cancel(task_id: str):
    ok = await ingest_queue.cancel(task_id)
    return JSONResponse({"ok": ok})

@app.post("/api/queue/{task_id}/retry")
async def api_queue_retry(task_id: str):
    ok = await ingest_queue.retry(task_id)
    return JSONResponse({"ok": ok})
```

### 验收标准

- [ ] 同时上传 3 个文件 → 串行依次摄入，不会并发
- [ ] 摄入进行中时重启 server → 队列恢复，queued 任务继续
- [ ] 摄入失败 → 自动重试 3 次，3 次后标记 failed
- [ ] `GET /api/queue` 返回所有任务状态
- [ ] `POST /api/queue/{id}/cancel` 取消排队中的任务
- [ ] `POST /api/queue/{id}/retry` 重试失败任务
- [ ] 队列文件 `.ingest_queue.json` 持久化

---

## 功能 5：来源可追溯

**文件**：`prompts/ingest_user.md`、`tools/ingest.py`

**目标**：每个 wiki 页面的 YAML frontmatter 包含 `sources: []` 字段，链接回原始文件。

### 5.1 修改 prompt 模板

**文件**：`prompts/ingest_user.md`，在 JSON schema 中为每个页面类型增加 `sources` 字段：

```json
{
  "source_page": "...",
  "source_page_sources": ["raw/my-article.md"],
  "entity_pages": [
    {"path": "entities/X.md", "content": "...", "sources": ["raw/my-article.md"]}
  ],
  "concept_pages": [
    {"path": "concepts/Y.md", "content": "...", "sources": ["raw/my-article.md"]}
  ]
}
```

### 5.2 修改 `tools/ingest.py` 的兜底逻辑

在写入每个页面之前，确保 sources 字段存在：

```python
def _ensure_sources_in_frontmatter(content: str, source_ref: str) -> str:
    """Ensure the YAML frontmatter includes a sources field referencing the raw document."""
    if "sources:" in content.split("---")[1] if "---" in content else True:
        return content
    # No sources field — insert after 'type:' or after first frontmatter line
    lines = content.split("\n")
    inserted = False
    result = []
    in_frontmatter = False
    fm_start_count = 0
    for line in lines:
        result.append(line)
        if line.strip() == "---":
            fm_start_count += 1
            if fm_start_count == 1:
                in_frontmatter = True
            else:
                in_frontmatter = False
        elif in_frontmatter and not inserted and line.strip().startswith("type:"):
            result.append(f"sources:\n  - {source_ref}")
            inserted = True
    if not inserted:
        # Insert right after opening ---
        result.insert(1, f"sources:\n  - {source_ref}")
    return "\n".join(result)


# 在 ingest() 中，写入每个页面前调用：
source_ref = "raw/" + source.name
data["source_page"] = _ensure_sources_in_frontmatter(data["source_page"], source_ref)
for page in data.get("entity_pages", []):
    page["content"] = _ensure_sources_in_frontmatter(page["content"], source_ref)
for page in data.get("concept_pages", []):
    page["content"] = _ensure_sources_in_frontmatter(page["content"], source_ref)
```

### 验收标准

- [ ] 每个生成的 wiki 页面 YAML frontmatter 包含 `sources:` 字段
- [ ] `sources:` 值正确指向 `raw/` 下的原始文件
- [ ] LLM 未返回 sources 时，兜底逻辑自动补充

---

## 功能 6：语言感知生成

**文件**：`prompts/ingest_system.md`、`prompts/query_synthesis.md`、`prompts/lint_semantic.md`、`server/server.py`、`web/index.html`

**目标**：用户在设置中选择语言（中文/英文），LLM 按该语言生成所有内容。

### 6.1 设置面板增加语言选项

**文件**：`web/index.html`

在设置面板中增加语言选择器：

```html
<div class="setting-row">
    <label>界面语言 / Output Language</label>
    <select id="setting-language">
        <option value="zh">中文</option>
        <option value="en">English</option>
    </select>
</div>
```

### 6.2 后端存储语言设置

**文件**：`server/server.py`

`POST /api/settings` 新增 `language` 字段处理：

```python
if "language" in body:
    os.environ["IWIKI_LANGUAGE"] = body["language"]
```

`GET /api/settings` 返回当前语言：

```python
"language": os.environ.get("IWIKI_LANGUAGE", "zh"),
```

### 6.3 Prompt 模板增加语言指令

**文件**：`prompts/ingest_system.md`

在模板开头增加：

```markdown
Language: **MUST respond in ${language}**.
- If 'zh': All titles, summaries, and content must be written in Chinese.
- If 'en': All output must be written in English.
```

**文件**：`prompts/query_synthesis.md`

同样增加语言指令。

### 6.4 传递 language 参数

**文件**：`tools/ingest.py` 的 `ingest()` 函数：

```python
import os
language = os.environ.get("IWIKI_LANGUAGE", "zh")
system_msg = load_prompt("ingest_system", schema=schema, wiki_context=wiki_context_str, today=today, language=language)
```

### 验收标准

- [ ] 选择"中文" → 摄入生成中文标题和内容
- [ ] 选择"English" → 摄入生成英文标题和内容
- [ ] 查询回答语言与设置一致

---

## 功能 7：文件夹导入

**文件**：`tools/ingest.py`（修改 `__main__` 部分和 `ingest()` 函数签名）

**目标**：递归导入目录，保留目录结构作为分类上下文传给 LLM。

### 7.1 修改 `ingest()` 函数签名

```python
def ingest(source_path: str, auto_convert: bool = True, category_hint: str | None = None):
```

### 7.2 将 category_hint 传入 prompt

在 prompt 构建中（约 line 275）增加分类上下文：

```python
category_line = f"\nFile category/context: This file is from the '{category_hint}' directory group." if category_hint else ""
user_msg = load_prompt("ingest_user", source_name=str(source_name), source_content=source_content, today=today, category_context=category_line)
```

### 7.3 修改目录导入逻辑

替换 `__main__` 中的目录处理部分（约 line 425-428）：

```python
elif p.is_dir():
    # 递归导入，保留子目录结构作为分类
    for f in sorted(p.rglob("*")):
        if f.is_file() and f.suffix.lower() in ALL_SUPPORTED_EXTENSIONS:
            rel_dir = f.parent.relative_to(p).as_posix()
            category = f"{p.name}/{rel_dir}" if rel_dir and rel_dir != "." else p.name
            paths_to_process.append((f, category))
```

同时修改处理循环（约 line 453）：

```python
for item in unique_paths:
    if isinstance(item, tuple):
        p, category = item
        ingest(str(p), auto_convert=not no_convert, category_hint=category)
    else:
        ingest(str(item), auto_convert=not no_convert)
```

### 验收标准

- [ ] `python tools/ingest.py raw/papers/` 递归摄入所有子目录文件
- [ ] 文件来自 `papers/energy` 时，LLM prompt 收到分类上下文
- [ ] 单文件摄入行为不变

---

## 功能 8：队列可视化

**文件**：`web/index.html`

**目标**：前端展示摄入队列状态，支持取消和重试。

### 8.1 新增队列面板 HTML

在侧边栏日志区域上方增加：

```html
<div id="queue-panel" style="display:none">
    <h3>摄入队列</h3>
    <div id="queue-list"></div>
</div>
```

### 8.2 队列渲染逻辑

```javascript
// 每 3 秒轮询队列状态
setInterval(async () => {
    const resp = await fetch('/api/queue');
    const tasks = await resp.json();
    renderQueue(tasks);
}, 3000);

function renderQueue(tasks) {
    if (!tasks || tasks.length === 0) {
        document.getElementById('queue-panel').style.display = 'none';
        return;
    }
    const panel = document.getElementById('queue-panel');
    panel.style.display = 'block';

    const list = document.getElementById('queue-list');
    list.innerHTML = tasks.map(t => {
        const statusIcon = {
            'queued': '⏳',
            'processing': '🔄',
            'done': '✅',
            'failed': '❌',
        }[t.status] || '❓';

        const actions = [];
        if (t.status === 'queued') {
            actions.push(`<button onclick="cancelTask('${t.task_id}')">取消</button>`);
        }
        if (t.status === 'failed') {
            actions.push(`<button onclick="retryTask('${t.task_id}')">重试</button>`);
        }

        const error = t.error ? `<div class="queue-error">${escapeHtml(t.error)}</div>` : '';

        return `<div class="queue-item queue-${t.status}">
            <span>${statusIcon}</span>
            <span>${escapeHtml(t.raw_name)}</span>
            <span class="queue-status">${t.status}</span>
            ${actions.join('')}
            ${error}
        </div>`;
    }).join('');
}

async function cancelTask(taskId) {
    await fetch(`/api/queue/${taskId}/cancel`, { method: 'POST' });
}

async function retryTask(taskId) {
    await fetch(`/api/queue/${taskId}/retry`, { method: 'POST' });
}
```

### 8.3 队列样式

```css
.queue-item { padding: 8px; border-bottom: 1px solid var(--border); display: flex; align-items: center; gap: 8px; font-size: 13px; }
.queue-processing { background: rgba(255, 152, 0, 0.1); }
.queue-failed { background: rgba(244, 67, 54, 0.1); }
.queue-done { background: rgba(76, 175, 80, 0.1); }
.queue-error { font-size: 11px; color: var(--error); margin-top: 4px; }
```

### 验收标准

- [ ] 上传文件后侧边栏显示队列列表
- [ ] 显示状态图标（⏳排队 / 🔄处理中 / ✅完成 / ❌失败）
- [ ] 排队任务可取消，失败任务可重试
- [ ] 完成的任务 10 秒后自动从列表消失
- [ ] 空队列时面板隐藏

---

## 功能 9：Source 文件夹自动监听

**文件**：新建 `server/file_watcher.py`，修改 `server/server.py`、`requirements.txt`

**目标**：`raw/` 目录下的文件增删改自动触发摄入/删除，无需手动上传。

### 9.1 安装依赖

**文件**：`requirements.txt`，新增：

```
watchdog>=4.0.0
```

### 9.2 新建 `server/file_watcher.py`

```python
"""Watch raw/ directory for file changes, auto-ingest or delete."""

import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "raw"

# Supported extensions
SUPPORTED = {".md", ".pdf", ".docx", ".pptx", ".xlsx", ".html", ".txt",
             ".csv", ".json", ".xml", ".yaml", ".yml", ".tsv"}


class RawFolderHandler(FileSystemEventHandler):
    def __init__(self, enqueue_fn, delete_fn):
        self._enqueue = enqueue_fn
        self._delete = delete_fn
        self._pending: dict[str, float] = {}  # path → first_seen_time
        self._debounce_sec = 1.0

    def _should_process(self, path: str) -> bool:
        ext = Path(path).suffix.lower()
        if ext not in SUPPORTED:
            return False
        if Path(path).name.startswith("."):
            return False
        return True

    def on_created(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        # Wait for file to stabilize (avoid partial writes)
        self._pending[event.src_path] = time.time()

    def on_modified(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._pending[event.src_path] = time.time()

    def on_deleted(self, event):
        if event.is_directory or not self._should_process(event.src_path):
            return
        self._delete(Path(event.src_path).name)

    def tick(self):
        """Call periodically to process debounced events."""
        now = time.time()
        ready = []
        for path, first_seen in list(self._pending.items()):
            if now - first_seen >= self._debounce_sec:
                ready.append(path)
                del self._pending[path]
        for path in ready:
            if Path(path).exists():
                self._enqueue(path, Path(path).name)


def start_watcher(enqueue_fn, delete_fn):
    """Start file watcher in a daemon thread. Returns the observer."""
    handler = RawFolderHandler(enqueue_fn, delete_fn)
    observer = Observer()
    observer.schedule(handler, str(RAW_DIR), recursive=True)
    observer.daemon = True
    observer.start()
    return observer, handler
```

### 9.3 集成到 server.py

在 `server.py` 的 main 函数或 startup 事件中：

```python
from server.file_watcher import start_watcher

# After server starts:
async def _auto_enqueue(file_path: str, raw_name: str):
    await ingest_queue.enqueue(file_path, raw_name)

async def _auto_delete(raw_name: str):
    # Reuse existing delete logic
    slug = Path(raw_name).stem
    _remove_source_map(slug)
    source_page = PROJECT_ROOT / "wiki" / "sources" / f"{slug}.md"
    if source_page.exists():
        source_page.unlink()

observer, watcher_handler = start_watcher(_auto_enqueue, _auto_delete)

# Periodically process debounced events
async def _watcher_tick():
    while True:
        watcher_handler.tick()
        await asyncio.sleep(1)

asyncio.create_task(_watcher_tick())
```

### 验收标准

- [ ] 往 `raw/` 目录拖入文件 → 自动入队摄入
- [ ] 修改 `raw/` 下已有文件 → 自动重新摄入
- [ ] 删除 `raw/` 下文件 → 自动清理对应 wiki 页面
- [ ] 大文件（如 100MB PDF）不会在写入一半时触发摄入（debounce 保护）

---

## 功能 10：资料源渐进渲染

**文件**：`web/index.html`

**目标**：大型知识库的 Sources 列表分批渲染，避免页面卡顿。

### 实施

找到 Sources 列表渲染函数，改造为分批加载：

```javascript
const SOURCES_BATCH = 20;
let sourcesRendered = 0;
let allSources = [];

function renderSourcesBatch(sources) {
    allSources = sources;
    sourcesRendered = 0;
    const container = document.getElementById('sources-list');
    container.innerHTML = '';
    loadNextBatch();
}

function loadNextBatch() {
    const container = document.getElementById('sources-list');
    const batch = allSources.slice(sourcesRendered, sourcesRendered + SOURCES_BATCH);

    batch.forEach(src => {
        const item = document.createElement('div');
        item.className = 'source-item';
        item.innerHTML = `
            <span class="source-name">${escapeHtml(src.name)}</span>
            <span class="source-date">${src.created_at?.slice(0, 10) || ''}</span>
        `;
        container.appendChild(item);
    });

    sourcesRendered += batch.length;

    if (sourcesRendered >= allSources.length) {
        // 全部渲染完成
        return;
    }

    // 用 IntersectionObserver 检测是否需要加载更多
    const sentinel = document.createElement('div');
    sentinel.id = 'sources-sentinel';
    sentinel.style.height = '1px';
    container.appendChild(sentinel);

    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            observer.disconnect();
            sentinel.remove();
            // 用 requestAnimationFrame 避免 jank
            requestAnimationFrame(() => loadNextBatch());
        }
    });
    observer.observe(sentinel);
}
```

### 验收标准

- [ ] 100+ sources 时页面首次渲染 < 500ms
- [ ] 滚动到底部自动加载下一批
- [ ] 无滚动时仅渲染前 20 条

---

## 附录 A：文件变更清单

| 文件 | 操作 | 涉及功能 |
|------|------|----------|
| `tools/ingest.py` | 修改 | 1(缓存), 2(兜底), 5(来源), 7(文件夹) |
| `server/ingest_queue.py` | **新建** | 4(队列) |
| `server/file_watcher.py` | **新建** | 9(监听) |
| `server/server.py` | 修改 | 3(embedding), 4(队列), 6(语言), 9(监听) |
| `web/index.html` | 修改 | 6(语言), 8(队列UI), 10(渐进渲染) |
| `prompts/ingest_system.md` | 修改 | 6(语言) |
| `prompts/ingest_user.md` | 修改 | 5(来源), 7(分类上下文) |
| `prompts/query_synthesis.md` | 修改 | 6(语言) |
| `requirements.txt` | 修改 | 9(watchdog) |

## 附录 B：验收总清单

- [ ] SHA256 缓存：相同文件跳过 LLM
- [ ] 摘要兜底：LLM 遗漏时自动生成 source page
- [ ] Embedding 闭环：删除文档同步清理向量
- [ ] 摄入队列：串行处理、持久化、重试 3 次
- [ ] 来源追溯：每个页面 YAML 含 sources 字段
- [ ] 语言感知：设置中切换中文/英文
- [ ] 文件夹导入：递归处理 + 目录作为分类上下文
- [ ] 队列可视化：侧边栏展示队列，可取消/重试
- [ ] 文件监听：raw/ 增删改自动触发摄入/清理
- [ ] 渐进渲染：Sources 列表分批加载
