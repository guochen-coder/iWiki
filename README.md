# iWiki — AI 驱动的个人知识库

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Version](https://img.shields.io/badge/version-1.1.0-blue)

iWiki 不是笔记软件，不是文档管理器，而是一个**会思考的知识助手**。

你负责投喂文档，AI 负责阅读、提取关键信息、发现隐藏关联，最终构建出一张你可以浏览、提问、探索的可视化知识图谱。

<img width="2874" height="1356" alt="图谱全览" src="https://github.com/user-attachments/assets/4f2f4fbf-409d-42a5-88f1-664661b51614" />

---

## 核心理念

### 不是"存文档"，而是"织知识"

传统笔记软件解决的问题是"放在哪"。iWiki 解决的问题是"和什么有关"。

每当你摄入一篇文档，AI 会做三件事：

1. **提取** — 识别文档中的人物、概念、项目、事件，自动创建独立页面
2. **链接** — 在页面间建立显式引用（`[[wikilink]]`），让相关知识自然编织成网
3. **推断** — 用 LLM 发现文档中未明确写出、但语义上存在的隐含关系

### 知识处理流水线

```
源文档 (.md / .pdf / .docx / .pptx ...)
   │
   ▼
格式转换 (markitdown)      ← 多格式统一入口
   │
   ▼
AI 摄入分析                 ← LLM 阅读、提取、结构化
   │
   ├──→ wiki/sources/      ← 源文档摘要页
   ├──→ wiki/entities/     ← 人物/公司/项目页
   ├──→ wiki/concepts/     ← 概念/框架/方法页
   ├──→ wiki/overview.md   ← 跨源文档持续综述
   └──→ wiki/index.md      ← 全局目录索引
   │
   ▼
知识图谱构建
   ├── 阶段 1: 显式边（[[wikilink]] 提取）
   └── 阶段 2: 隐式边（LLM 语义推断 + 置信度评分）
   │
   ▼
可视化浏览 + 自然语言查询
```

### 两阶段图谱：显式 + 隐式

iWiki 的知识图谱区别于简单的思维导图：

| 边类型 | 来源 | 置信度 | 示例 |
|--------|------|--------|------|
| **EXTRACTED** | 文档中的 `[[wikilink]]` | 1.0 | `[[LangGraph]]` |
| **INFERRED** | LLM 推断的语义关系 | ≥0.7 | "雨影效应 → 制度经济学（环境基础影响制度形成）" |
| **AMBIGUOUS** | 低置信度推断 | <0.7 | 仅供参考，用户自行判断 |

这种双层结构意味着：**显式链接是你知道的知识，推断链接是你可能错过的知识**。

---

## 功能特性

### 核心功能

- **多格式摄入** — 支持 Markdown、PDF、DOCX、PPTX、XLSX、HTML 等 15+ 格式，自动转换后分析
- **AI 驱动提取** — LLM 阅读文档，自动识别实体、概念，生成结构化 wiki 页面
- **智能问答** — 自然语言提问，AI 检索相关页面并综合答案，引用来源
- **知识图谱** — 自动构建交互式图谱，支持按边类型/置信度过滤、社区着色、节点搜索
- **内容质量检查** — 检测孤立页面、断链、矛盾声明、数据缺口、stale content
- **结构健康检查** — 零 API 成本的确定性检查（空文件/索引同步/日志覆盖）

### 工程可靠性

- **统一 LLM 客户端** — 单一 `LLMClient` 封装所有 LLM 调用，指数退避重试
- **读写锁分离** — 查询/健康检查可并发执行，写操作（摄入/图谱重建）互斥
- **超时控制** — 所有操作有 `asyncio.wait_for` 超时保护，防止 LLM 卡死系统
- **Token 用量追踪** — 累计统计 prompt/completion tokens，按操作类型分组
- **Prompt 模板化** — 所有提示词独立为 `prompts/*.md` 文件，可审计、可 A/B 测试
- **WebSocket 实时进度** — 前端实时接收操作进度，断线指数退避重连
- **增量图谱缓存** — SHA256 内容哈希 + JSONL 检查点，中断后可恢复，避免重复推理

### MCP 服务（规划中）

通过 Model Context Protocol 对外暴露知识库，让 Claude Code、OpenCode 等 AI 智能体直接查询。详见 [MCP Server 实施计划](docs/mcp-server-plan.md)。

---

## 技术栈

| 层次 | 技术 | 用途 |
|------|------|------|
| **后端框架** | FastAPI + uvicorn | Web 服务，端口 8765 |
| **LLM 调用** | litellm | 统一接口，支持 Anthropic/DeepSeek/OpenAI 等 100+ 提供商 |
| **LLM 客户端** | 自研 `LLMClient` | 重试逻辑、用量追踪、快速/完整模型切换 |
| **图谱算法** | NetworkX | Louvain 社区检测、度分析、孤点检测 |
| **图谱可视化** | vis.js | 交互式 canvas 图谱，暗色主题 |
| **前端** | 原生 HTML/CSS/JS | 单文件 SPA，零构建步骤 |
| **Markdown 渲染** | marked.js (CDN) | 图谱抽屉中的内容渲染 |
| **文档转换** | markitdown (Microsoft) | PDF/DOCX/PPTX/XLSX → Markdown |
| **实时通信** | WebSocket | 操作进度推送 |
| **配置存储** | `.claude/settings.json` | API Key、模型、端点 URL |
| **数据存储** | 文件系统 | wiki/ 目录树 + graph/graph.json |

---

## 快速开始

### 1. 环境要求

- Python 3.10+
- Git（可选，用于克隆仓库）

### 2. 下载项目

```bash
git clone https://github.com/guochen-coder/iWiki.git
cd iWiki
```

### 3. 一键启动

```bash
bash setup.sh
```

脚本会自动：
1. 检测 Python 版本
2. 创建虚拟环境
3. 安装依赖
4. 启动 Web 服务
5. 打开浏览器 → `http://localhost:8765`

### 4. 配置 AI 服务

1. 打开 `http://localhost:8765`
2. 点击左侧 **⚙️ 设置**
3. 选择服务商（Anthropic / DeepSeek / 自定义）
4. 填写 API Key，测试连接，保存

<img width="972" height="942" alt="大模型配置" src="https://github.com/user-attachments/assets/6b73b4dd-a695-4134-ad52-7ff6864f6820" />

支持所有 litellm 兼容的服务商（Anthropic、DeepSeek、OpenAI、Groq 等）。支持的模型配置：

- **LLM_MODEL** — 主模型（ingest/query/lint/graph 核心任务，推荐 claude-sonnet-4-6 或 deepseek-chat）
- **LLM_MODEL_FAST** — 快速模型（页面选择/图谱推断等轻量任务，推荐 claude-haiku 或 deepseek-v4-flash）

### 5. 开始使用

| 操作 | 说明 |
|------|------|
| **摄入文档** | 点击右侧 📄 按钮，选择文件导入 |
| **提问** | 顶部搜索栏输入问题，AI 检索并综合答案 |
| **浏览图谱** | 中间画布拖拽缩放，点击节点查看详情 |
| **健康检查** | 点击左侧 ❤️ 检查知识库结构完整性 |
| **内容审查** | 点击左侧 🔍 运行 LLM 内容质量分析 |

---

## 项目结构

```
iwiki/
├── setup.sh               # 一键安装启动脚本
├── requirements.txt        # Python 依赖
├── README.md               # 本文件
├── LICENSE                 # MIT 许可证
│
├── server/
│   └── server.py           # FastAPI Web 后端（API + WebSocket）
│
├── web/
│   └── index.html          # 单文件 SPA 前端（vis.js + marked.js）
│
├── tools/                  # 命令行工具（可脱离 Web UI 独立使用）
│   ├── llm_client.py       # 统一 LLM 客户端（重试 + 用量追踪）
│   ├── ingest.py           # 文档摄入（LLM 驱动）
│   ├── query.py            # 知识库查询
│   ├── build_graph.py      # 知识图谱构建（两阶段：提取 + 推断）
│   ├── lint.py             # 内容质量检查（LLM 驱动）
│   ├── health.py           # 结构健康检查（确定性，零 API 成本）
│   ├── pdf2md.py           # 高质量 arXiv PDF 转换
│   ├── file_to_md.py       # 批量文件格式转换
│   ├── refresh.py          # 重新索引 wiki 页面
│   ├── heal.py             # 自动修复工具
│   └── prompt_loader.py    # Prompt 模板加载器
│
├── prompts/                # LLM 提示词模板（独立于代码，可审计）
│   ├── ingest_system.md    # 摄入系统指令 + schema
│   ├── ingest_user.md      # 摄入用户消息模板
│   ├── query_select_pages.md
│   ├── query_synthesis.md
│   ├── graph_infer.md
│   └── lint_semantic.md
│
├── wiki/                   # 知识库数据（AI 维护的知识层）
│   ├── index.md            # 全局目录索引
│   ├── overview.md         # 跨源文档持续综述
│   ├── log.md              # 追加式操作日志
│   ├── sources/            # 源文档摘要页
│   ├── entities/           # 人物/公司/项目页
│   ├── concepts/           # 概念/框架/方法页
│   └── syntheses/          # 已保存的查询答案
│
├── graph/                  # 图谱数据
│   ├── graph.json          # 节点/边数据
│   ├── graph.html          # 独立可用的 vis.js 可视化页面
│   └── .cache.json         # SHA256 缓存（避免重复推理）
│
├── raw/                    # 用户放入的源文档（不可变）
│
└── docs/                   # 开发文档
    ├── implementation-plan.md  # 工程化改造实施计划
    └── mcp-server-plan.md      # MCP Server 实施计划
```

---

## 常见问题

### AI 操作报错"API Key 未配置"

点击侧边栏 **⚙️ 设置** → 选择服务商 → 填写 API Key → 保存。

- 获取 Anthropic Key：[console.anthropic.com](https://console.anthropic.com)
- 获取 DeepSeek Key：[platform.deepseek.com](https://platform.deepseek.com)

### 摄入时间过长或超时

大文档或复杂推理可能超时。建议：
- 拆分大文件为多个小文件分批摄入
- 使用更快的模型（如 deepseek-chat）作为 `LLM_MODEL`
- PDF 文件确保文字层可读取（扫描版 PDF 需先 OCR）

### Python 版本太低

macOS 自带 Python 版本过低：

```bash
brew install python@3.12
```

### 端口被占用

```bash
PORT=8766 bash setup.sh
# 或
PORT=8766 python server/server.py
```

### 图谱显示为空

先确认有 wiki 页面，然后点击 **🔄 重建图谱**，或运行：

```bash
python tools/build_graph.py --open
```

### 如何只用命令行，不启动 Web UI

```bash
source venv/bin/activate
export ANTHROPIC_API_KEY=sk-...

# 摄入文档
python tools/ingest.py raw/my-doc.md

# 查询知识库
python tools/query.py "什么是雨影效应"

# 构建图谱
python tools/build_graph.py --no-infer --open

# 健康检查
python tools/health.py

# 内容检查
python tools/lint.py --save
```

---

## CLI 工具速查

| 工具 | 命令 | 零 API 成本 |
|------|------|:---:|
| 摄入文档 | `python tools/ingest.py <文件路径>` | |
| 查询知识库 | `python tools/query.py "问题"` | |
| 构建图谱 | `python tools/build_graph.py [--no-infer] [--open]` | ✅ (--no-infer 时) |
| 健康检查 | `python tools/health.py [--json] [--save]` | ✅ |
| 内容检查 | `python tools/lint.py [--save]` | |
| 格式转换 | `python tools/pdf2md.py <PDF文件>` | ✅ |
| 批量转换 | `python tools/file_to_md.py <目录>` | ✅ |
| 重新索引 | `python tools/refresh.py` | |
| 自动修复 | `python tools/heal.py` | |

---

## 设计原则

1. **用户掌控数据** — 所有数据存储在本地文件系统（`wiki/`、`graph/`、`raw/`），不依赖数据库或云服务
2. **AI 是助手，不是主人** — AI 的建议（推断边、lint 报告）可审查、可修正；显式链接高于隐式推断
3. **零成本也能工作** — `health.py` 和 graph 基础构建不需要 API Key；仅 LLM 驱动功能需要
4. **文件即数据库** — 知识以 Markdown 文件存储，可用任何编辑器修改，Git 版本控制友好
5. **渐进式复杂度** — 从简单的文档摄入到高级的图谱分析，用户按需深入

---

## 路线图

当前版本 **v1.1.0** 已完成工程化加固。规划中的方向：

- [x] 统一 LLM 客户端 + 重试逻辑
- [x] Prompt 模板文件化
- [x] Token 用量追踪
- [x] 读写锁并发控制
- [x] 多格式文档支持（markitdown）
- [ ] Embedding 语义检索（ChromaDB）
- [ ] MCP Server（让其他 AI Agent 查询知识库）
- [ ] 增量图谱更新
- [ ] Docker 一键部署

详见 [工程化改造实施计划](docs/implementation-plan.md)。

---

## 致谢

本项目受 Andrej Karpathy 的 [llm-wiki](https://github.com/karpathy/llm-wiki) 方法论启发。

## 许可证

MIT License — 详见 [LICENSE](LICENSE)
