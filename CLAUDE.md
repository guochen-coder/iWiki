# CLAUDE.md

此文件为 Claude Code（claude.ai/code）在本仓库中工作时提供指导。

## 项目概述

iWiki 是一个个人知识库构建工具。用户运行 `setup.sh` 启动 Web 服务，通过可视化网页摄入文档、提问、浏览知识图谱。AI 功能通过 litellm 调用 LLM API 实现。

**当前状态：** server 已与 Claude Code 解耦。Claude Code 是可选的交互式 AI 辅助工具，不影响 iWiki Web 功能。

## 技术参考库

`vendor/llm-wiki-agent-main/` 是技术参考库。**只读参考，不在其内部进行开发。** 开发工作在根项目层级进行，从参考库中提取需要的模块和模式。

### 参考库结构（只读）

```
vendor/llm-wiki-agent-main/
├── tools/
│   ├── ingest.py             # 源文档摄入（LLM 驱动）
│   ├── query.py              # wiki 查询
│   ├── build_graph.py        # 知识图谱生成（NetworkX + vis.js）
│   ├── lint.py               # 内容质量检查（LLM 驱动）
│   ├── health.py             # 结构完整性检查（无 LLM 调用，快速）
│   ├── heal.py               # 自动修复工具
│   ├── refresh.py            # 重新索引/处理 wiki 页面
│   ├── pdf2md.py             # 高质量 arXiv PDF 转换
│   └── file_to_md.py         # 批量文件格式转换
├── wiki/                     # 智能体维护的知识层结构参考
│   ├── index.md              # 所有页面的目录
│   ├── log.md                # 追加式操作日志
│   ├── overview.md           # 跨源文档的持续综述
│   ├── sources/              # 源文档摘要页
│   ├── entities/             # 人物/公司/项目页
│   ├── concepts/             # 概念/框架/方法页
│   └── syntheses/            # 已保存的查询答案
├── graph/                    # 图谱数据与可视化
└── raw/                      # 不可变源文档
```

## 根项目架构

### 启动流程

```
用户运行 bash setup.sh
  → 检测 Python 3.10+
  → 创建/激活 venv
  → pip install -r requirements.txt
  → python server/server.py &    # 后台启动，nohup/terminal 控制生命周期
  → 打开浏览器 http://localhost:8765
```

### Server 端口与设置

| 端点 | 功能 |
|------|------|
| `GET /api/settings` | 返回当前 API key（脱敏）、模型、base_url |
| `POST /api/settings` | 保存 key / model / base_url，更新 os.environ + settings.json |
| `POST /api/settings/test` | 用当前配置测试 LLM 连接 |
| `POST /api/ingest` | 摄入文档 |
| `POST /api/query` | 智能查询 |
| `POST /api/lint` | 内容检查 |
| `POST /api/graph` | 重建图谱 |
| `POST /api/health` | 健康检查 |
| `GET /api/graph-data` | 返回 graph.json |
| `WS /ws/progress/{task_id}` | 实时进度推送 |

### 配置存储

用户通过 Web UI 设置面板配置 API Key、模型、端点 URL。保存后写入 `.claude/settings.json` 的 `env` 字段：

```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "LLM_MODEL": "anthropic/claude-sonnet-4-6",
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"
  }
}
```

Server 启动时从 settings.json 加载 env，运行时保存即时更新 `os.environ`，无需重启。

### 前端

单文件 `web/index.html`，自包含 HTML/CSS/JS：
- 左侧边栏：操作按钮（ingest / lint / graph / health）+ 设置按钮 + 暗色切换 + 日志
- 中间：vis.js 知识图谱画布 + 节点抽屉
- 顶部：常驻查询栏

依赖：vis.js + marked.js（CDN 引入）

## 根项目开发命令

### Python 环境

```bash
pip install -r requirements.txt
```

### 启动服务

```bash
source venv/bin/activate
python server/server.py
```

### 从参考库中运行工具（参考用）

```bash
# 摄入源文档（LLM 驱动）
python tools/ingest.py raw/my-article.md

# 健康检查（确定性，无 LLM 调用，快速）
python tools/health.py
python tools/health.py --json

# 内容检查（LLM 驱动，定期运行）
python tools/lint.py
python tools/lint.py --save

# 构建知识图谱
python tools/build_graph.py                  # 完整构建
python tools/build_graph.py --no-infer       # 跳过语义推理
python tools/build_graph.py --open           # 构建后自动打开浏览器
python tools/build_graph.py --clean          # 强制完全重新推理
```

## 参考库关键架构知识

从参考库中提取的架构要点（用于指导根项目开发）：

- **两阶段图谱构建：** 第一阶段提取显式 `[[wikilinks]]`（确定性，标记为 `EXTRACTED`）。第二阶段使用 LLM 推断隐式关系（标记为 `INFERRED` 或 `AMBIGUOUS`，带置信度分数）。SHA256 缓存避免重复处理。JSONL 检查点文件支持中断后恢复。

- **Health 与 Lint 的边界：** `health.py` 仅做结构检查（空文件、索引同步、日志覆盖）—— 零 API 成本，每次会话都可运行。`lint.py` 做语义分析（孤立页面、矛盾、过时内容、数据缺口）—— 使用 LLM，定期运行。始终先 health 再 lint。

- **多格式摄入：** 非 markdown 文件（PDF、DOCX、PPTX、XLSX、HTML 等）通过 [markitdown](https://github.com/microsoft/markitdown) 自动转换为 markdown。`--no-convert` 跳过转换。

- **图谱可视化：** 自包含的 vis.js 单页（`graph.html`），支持按边类型和置信度过滤、节点搜索、Louvain 社区着色、侧滑抽屉展示完整 markdown 内容。

- **API 依赖：** LLM 驱动操作使用 litellm 调用模型。`health.py` 是唯一无需 API key 的工具。支持 Anthropic、DeepSeek 及任何 litellm 兼容的提供商。

## 对话限制规则

**Claude Code 对话中禁止直接修改知识库数据。** 以下目录的内容只能通过 Web UI（`http://localhost:8765`）或 `tools/*.py` CLI 工具来操作，不得在对话中直接读写：

- `wiki/` — 知识页面、索引、日志
- `raw/` — 用户放入的源文档
- `graph/` — 图谱数据（`graph.json` 等）

可以做的：启动/停止 `server/server.py` 服务、回答项目架构问题、修改 `server/`、`web/`、`tools/` 等开发代码。

原因：防止对话中误操作破坏知识库数据，保持 Web UI 和 CLI 工具作为唯一的数据操作入口。
