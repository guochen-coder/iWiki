# Changelog

iWiki 所有值得关注的变更记录。

格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)，版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## [1.2.0] — 2026-05-22

### 新增

- **SHA256 增量缓存**：摄入前检查源文件哈希，未变更自动跳过 LLM 调用，直接省钱
- **持久化摄入队列**：串行处理 + JSON 磁盘持久化 + 服务重启恢复 + 失败自动重试 3 次
- **文件夹导入**：递归处理子目录，目录名作为分类上下文传给 LLM（如 `papers/energy`）
- **文件自动监听**：`raw/` 目录增删改自动触发摄入/删除（watchdog 库）
- **Queue API**：`GET /api/queue` + `POST /api/queue/{id}/cancel` + `POST /api/queue/{id}/retry`
- **队列可视化**：侧边栏展示排队/处理中/完成/失败任务，支持取消和重试
- **来源可追溯**：每个 wiki 页面的 YAML frontmatter 自动包含 `sources: []` 字段
- **语言感知生成**：设置中选择中文/英文，LLM 输出语言一致
- **资料源渐进渲染**：大型 Sources 列表用 IntersectionObserver 分批加载，避免卡顿
- **Embedding 清理闭环**：删除文档同步清除对应向量，保持检索结果干净
- **资料摘要兜底**：LLM 遗漏 source_page 时自动生成基础摘要页

### 改进

- 队列状态 3 秒轮询 + WS 实时推送双重保障
- 文件监听 debounce 1 秒，防止大文件写入一半触发摄入
- 队列文件原子写入（tmp → rename），防止崩溃损坏

---

## [1.1.0] — 2026-05-22

### 新增

- **MCP Server**：通过 Model Context Protocol 对外暴露知识库，Claude Code/OpenCode 等 AI 编程助手可直接查询（`mcp_server.py`，8 个工具）
- **Embedding 语义检索**：基于本地向量存储的语义搜索，替代纯关键词匹配
- **Docker 部署**：`Dockerfile` + `docker-compose.yml` 一键容器化
- **Prompt 模板化**：所有 LLM 提示词独立为 `prompts/*.md` 文件，可审计可修改
- **Token 用量追踪**：全局累计 prompt/completion token 统计，前端展示
- **前端用量面板**：设置面板可视化 token 消耗
- **前端来源引用展示**：查询结果下方显示引用的 wiki 页面
- **请求级取消机制**：长时间操作可中途取消
- **查询答案缓存**：相同问题 + 相同 index.md → 复用结果，零 LLM 调用
- **单元测试**：143 个用例覆盖 ingest/query/build_graph/health/embeddings/mcp_tools

### 改进

- **统一 LLM 客户端**（`tools/llm_client.py`）：消除 4 个文件中的重复 `call_llm` 实现，统一重试、超时、用量追踪
- **LLM 重试机制**：指数退避重试（1s→2s→4s），自动恢复 RateLimit/Connection/Server 错误
- **读写锁分离**：查询/健康检查可并发运行，写操作互斥
- **超时控制**：所有操作有 `asyncio.wait_for` 超时保护，防止 LLM 卡死系统
- **图谱推断并行化**：`ThreadPoolExecutor(max_workers=5)`，50 页从 ~100s 降到 ~25s
- **ingest prompt 用量控制**：wiki_context token 估算上限 4000，自动截断
- **lint 智能采样**：优先检查最近修改页面 + 随机老页面抽检
- **前端 WS 重连指数退避**：2s→4s→8s→16s→30s 上限
- **HTTP 轮询递增间隔**：3s→4.5s→…→15s 上限，减少空请求
- **多格式文档支持**：启用 markitdown，支持 PDF/Word/PPT/Excel 等 15+ 格式
- **_sanitize_error 括号修正**：消除 and/or 混用歧义
- **query.py 结构化返回**：`QueryResult` dataclass 替代 stdout 重定向

### 修复

- 摄入长文档失败：max_tokens 从 8192 翻倍到 16384
- 图谱加载为空：edges 数据 JSON 语法错误修复

---

## [1.0.1] — 2026-05-18

### 新增

- 项目官网 README + MIT 许可证
- 演示数据（32 节点/72 边知识图谱）
- 可视化 Web 界面（vis.js 图谱 + marked.js 渲染）
- 一键安装脚本 `setup.sh`

### 核心功能

- **文档摄入**：上传 Markdown → LLM 分析 → 自动生成 wiki 页面
- **智能查询**：自然语言提问 → 检索相关页面 → LLM 综合答案
- **知识图谱**：vis.js 交互式可视化、社区着色、边类型过滤
- **健康检查**：零 API 成本的确定性结构检查
- **内容审查**：LLM 驱动的孤立页面/断链/矛盾检测
- 批量摄入/删除、WebSocket 实时进度推送

---

## [1.0.0] — 2026-05-14

初始版本。基于 Andrej Karpathy llm-wiki 方法论的首次实现。

---

## 升级指南

### 从 v1.0.1 升级到 v1.1.0

```bash
# 1. 进入项目目录
cd iWiki

# 2. 拉取最新代码
git pull origin main

# 3. 更新依赖（新增 markitdown、mcp、numpy 等）
source venv/bin/activate
pip install -r requirements.txt

# 4. 重启服务
python server/server.py
```

**兼容性说明**：
- `wiki/` 和 `raw/` 目录中的数据完全兼容，无需迁移
- 新增的 `prompts/` 目录随 git 拉取自动获得
- 首次启动会自动初始化 Embedding 存储（`wiki/.embeddings.pkl`）
- 如使用 MCP Server，需在 `.claude/settings.json` 中添加配置（见 README）

### 从 v1.1.0 升级到 v1.2.0

```bash
git pull origin main
source venv/bin/activate
pip install -r requirements.txt  # 新增 watchdog 依赖
python server/server.py
```

**新增文件**：首次摄入后自动生成 `wiki/.ingest_cache.json`、`.ingest_queue.json`。
**不兼容变更**：无。所有 v1.1.0 数据原样可用。

### 全新安装

见 [README.md](README.md#30-秒快速开始)。

### 故障排查

**升级后服务起不来**：
```bash
# 重建虚拟环境（最彻底）
rm -rf venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python server/server.py
```

**依赖冲突**：某些包（如 markitdown）可能与旧版 Python 不兼容。确保 Python ≥ 3.10。
