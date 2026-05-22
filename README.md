# iWiki — AI 驱动的个人知识库

<p align="center">
  <img src="https://img.shields.io/badge/python-3.10+-blue" alt="Python">
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License">
  <img src="https://img.shields.io/badge/tests-143%20passed-brightgreen" alt="Tests">
  <img src="https://img.shields.io/badge/version-1.2.0-blue" alt="Version">
  <img src="https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20WSL-lightgrey" alt="Platform">
</p>

**投喂文档，AI 自动整理成你会提问、能浏览、可探索的知识图谱。**

你只管丢文件进去（PDF、Word、PPT、Markdown 都行），剩下的事交给 AI：阅读、提取关键信息、发现隐藏关联、织成一张你可以自由探索的知识网络。

<img width="2874" height="1356" alt="图谱全览" src="https://github.com/user-attachments/assets/4f2f4fbf-409d-42a5-88f1-664661b51614" />

---

## 目录

- [它能做什么](#它能做什么)
- [30 秒快速开始](#30-秒快速开始)
- [详细安装指南](#详细安装指南)
- [使用手册](#使用手册)
- [常见问题](#常见问题)
- [开发者指南](#开发者指南)
- [致谢与许可证](#致谢与许可证)

---

## 它能做什么

### 核心流程（3 步）

```
丢文件进去           AI 自动整理            随时提问
   │                    │                    │
   ▼                    ▼                    ▼
 PDF/Word/MD     →   提取实体+概念    →   "这两个概念
 PPT/网页/文本       织成知识图谱          什么关系？"
```

### 具体功能

| 功能 | 说明 | 需要 API Key？ |
|------|------|:---:|
| **多格式摄入** | 支持 PDF、Word、PPT、Excel、Markdown 等 15+ 格式，拖进去就能用 | ✅ |
| **智能问答** | 用自然语言向知识库提问，AI 综合多篇文档给出带来源引用的答案 | ✅ |
| **知识图谱** | 自动生成交互式图谱，节点=知识，连线=关系，点击即看详情 | 可选 |
| **健康检查** | 一键检测空白页面、断链、索引不同步等问题 | ❌ 免费 |
| **内容审查** | AI 帮你发现知识库中的矛盾、过时内容、覆盖盲区 | ✅ |

### 和笔记软件的区别

笔记软件帮你**存**信息。iWiki 帮你**理解**信息之间的关联。

比如你分别投喂了《机器学习入门》和《Python 性能优化》两篇文章——iWiki 不仅各自整理摘要，还会自动推断"机器学习模型的推理速度 → Python 的向量化计算"这种你没写出来但实际存在的关联。

---

## 30 秒快速开始

### 前提条件

- **Python 3.10 或更高版本**（[下载 python.org](https://www.python.org/downloads/)）
- **一个 LLM API Key**（任选其一）：
  - [Anthropic Claude](https://console.anthropic.com) — 推荐，效果好
  - [DeepSeek](https://platform.deepseek.com) — 国内友好，性价比高
  - 其他 litellm 兼容的服务商（OpenAI、Groq 等）

### 三步启动

```bash
# 1. 下载
git clone https://github.com/guochen-coder/iWiki.git
cd iWiki

# 2. 一键安装 + 启动
bash setup.sh

# 3. 打开浏览器 → http://localhost:8765 → 设置 API Key → 开始使用
```

> **macOS / Linux 用户**：setup.sh 自动处理 Python 检测、虚拟环境创建、依赖安装和服务启动。
>
> **Windows 用户**：推荐使用 WSL2（Windows Subsystem for Linux），在上面运行和 Linux 完全一样。或参考[手动安装](#windows-手动安装)。

---

## 详细安装指南

### macOS

```bash
# 如果系统自带 Python 版本过低
brew install python@3.12

# 克隆并启动
git clone https://github.com/guochen-coder/iWiki.git
cd iWiki
bash setup.sh
```

### Linux (Ubuntu/Debian)

```bash
# 确保 Python 3.10+
sudo apt update && sudo apt install python3 python3-venv python3-pip -y

git clone https://github.com/guochen-coder/iWiki.git
cd iWiki
bash setup.sh
```

### Windows 手动安装

如果不使用 WSL，手动步骤：

```powershell
# 1. 从 python.org 安装 Python 3.10+，勾选 "Add Python to PATH"

# 2. 克隆项目
git clone https://github.com/guochen-coder/iWiki.git
cd iWiki

# 3. 创建虚拟环境
python -m venv venv
venv\Scripts\activate

# 4. 安装依赖
pip install -r requirements.txt

# 5. 启动服务
python server\server.py

# 6. 浏览器打开 http://localhost:8765
```

### 手动安装（所有平台通用，不用 setup.sh）

```bash
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
python server/server.py        # 访问 http://localhost:8765
```

### 配置 AI 服务

1. 打开 `http://localhost:8765`
2. 点击左侧 **⚙️ 设置**
3. 填写 API Key、选择模型、点击"测试连接"

<img width="972" height="942" alt="大模型配置" src="https://github.com/user-attachments/assets/6b73b4dd-a695-4134-ad52-7ff6864f6820" />

支持的配置项：

| 配置 | 说明 | 示例值 |
|------|------|--------|
| API Key | 服务商的 API 密钥 | `sk-ant-...` 或 `sk-...` |
| Base URL | API 端点地址（自定义服务商时填写） | `https://api.deepseek.com/anthropic` |
| 主模型 | ingest/query/lint 等核心任务 | `anthropic/claude-sonnet-4-6` |
| 快速模型 | 页面选择/图谱推断等轻量任务 | `anthropic/claude-haiku-4-5` |

> **国内用户提示**：DeepSeek 支付方便（支持支付宝），兼容 Anthropic API 格式。在 Base URL 填入 `https://api.deepseek.com/anthropic`，模型填 `deepseek-chat` 即可。

---

## 使用手册

### 1. 摄入第一篇文档

点击侧边栏 📄 按钮上传文件，或直接拖拽文件到页面。

<img width="936" height="946" alt="注入的文件" src="https://github.com/user-attachments/assets/432fe745-108e-4e72-a0df-79890e633e9f" />

支持的格式：`.md` `.pdf` `.docx` `.pptx` `.xlsx` `.html` `.txt` `.csv` `.json` `.xml` `.yaml` 等

AI 会自动：
- 创建源文档摘要页（`wiki/sources/`）
- 提取人物/公司/项目页（`wiki/entities/`）
- 提取概念/框架/方法页（`wiki/concepts/`）
- 更新全局综述（`wiki/overview.md`）
- 发现有矛盾的声明

### 2. 向知识库提问

顶部搜索栏输入问题，回车。

<img width="1642" height="180" alt="提问" src="https://github.com/user-attachments/assets/c6841114-5c4b-4a23-8d23-03aa32474408" />

<img width="1096" height="1378" alt="提问结果" src="https://github.com/user-attachments/assets/187a3039-db21-4b86-ba16-45e96d1d48e5" />

AI 会检索相关知识、综合答案，并列出引用的页面来源。

### 3. 探索知识图谱

中间画布展示知识网络。可以：
- **拖拽**移动节点
- **滚轮**缩放
- **点击**节点查看完整内容
- **搜索**定位特定节点
- **过滤**边类型（显式链接 / AI 推断 / 低置信度）

### 4. 定期巡检

| 操作 | 按钮 | 什么时候做 |
|------|------|------------|
| 健康检查 | ❤️ | 每次使用前，零 API 成本 |
| 内容审查 | 🔍 | 每摄入 10-15 篇文档后 |
| 重建图谱 | 🔄 | 图谱显示不全时 |

---

## 常见问题

### 启动报错 / 打不开页面

**症状**：`bash setup.sh` 后浏览器没打开，或访问 `localhost:8765` 无响应。

**排查步骤**：

```bash
# 1. 检查 Python 版本
python3 --version  # 需要 ≥ 3.10

# 2. 手动启动看报错信息
source venv/bin/activate
python server/server.py
# 看终端输出，通常会有明确错误提示

# 3. 端口被占用
PORT=8766 python server/server.py
# 访问 http://localhost:8766
```

### AI 操作报错"API Key 未配置"

确认设置面板中已保存 API Key。测试连接按钮可验证。

不同服务商获取 Key 的地址：
- Anthropic：[console.anthropic.com/settings/keys](https://console.anthropic.com)
- DeepSeek：[platform.deepseek.com/api_keys](https://platform.deepseek.com)

### 摄入 PDF 报错

PDF 需要文字层。扫描版 PDF（图片转 PDF）需先 OCR 处理。

```bash
# 测试 markitdown 是否正常安装
python3 -c "from markitdown import MarkItDown; print('ok')"
```

### 文档太大摄入失败

单文件限制 50 MB。大文档建议拆分为小文件分批摄入。

### 数据存储在哪里

所有数据在本地文件系统：

```
wiki/     ← 知识页面（Markdown，可用任何编辑器查看修改）
graph/    ← 图谱数据
raw/      ← 你上传的原始文档
```

不依赖任何云服务或数据库。用 Git 就能备份和版本控制。

### 如何升级到新版本

```bash
cd iWiki
git pull origin main                    # 拉取最新代码
source venv/bin/activate
pip install -r requirements.txt         # 更新依赖
python server/server.py                 # 重启服务
```

- `wiki/` 和 `raw/` 中的数据完全兼容，不会丢失
- 如果升级后启动报错，试试重建虚拟环境：`rm -rf venv && python3 -m venv venv`
- 完整变更记录见 [CHANGELOG.md](CHANGELOG.md)

### 如何切换到稳定版本

```bash
git checkout v1.1.0   # 切换到指定版本
```

可用版本：`v1.0.1`（初始版）、`v1.1.0`（工程化加固）、`v1.2.0`（当前稳定版）。

### 如何停止服务

关闭终端窗口，或按 `Ctrl+C`。

---

## 开发者指南

### 命令行工具

除了 Web UI，所有功能都有对应的命令行工具：

```bash
source venv/bin/activate

# 摄入文档
python tools/ingest.py raw/my-doc.md

# 查询知识库
python tools/query.py "什么是雨影效应"

# 构建图谱（不调用 LLM）
python tools/build_graph.py --no-infer --open

# 健康检查
python tools/health.py --json

# 内容检查
python tools/lint.py --save
```

### 项目结构

```
iwiki/
├── setup.sh               # 一键安装脚本
├── server/server.py       # FastAPI 后端（API + WebSocket）
├── web/index.html         # 单文件前端
├── tools/                 # 可独立使用的命令行工具
│   ├── ingest.py          #   文档摄入
│   ├── query.py           #   知识库查询
│   ├── build_graph.py     #   知识图谱构建
│   ├── lint.py            #   内容质量检查
│   ├── health.py          #   结构健康检查（零 API 成本）
│   └── llm_client.py      #   统一 LLM 客户端（重试+追踪）
├── prompts/               # Prompt 模板（可审计修改）
├── tests/                 # 143 个单元测试
├── wiki/                  # 知识库数据
├── graph/                 # 图谱数据
└── raw/                   # 用户上传的源文档
```

### 技术栈

| 层 | 技术 |
|------|------|
| Web 框架 | FastAPI + uvicorn |
| LLM 调用 | litellm（支持 100+ 服务商） |
| 图谱算法 | NetworkX（Louvain 社区检测） |
| 前端可视化 | vis.js + marked.js |
| 文档转换 | markitdown（Microsoft） |
| 实时通信 | WebSocket |
| 数据存储 | 文件系统（Markdown + JSON） |

### MCP 服务

iWiki 提供了 MCP (Model Context Protocol) 接口，让 Claude Code 等 AI 编程助手直接查询你的知识库。

```json
// 在 .claude/settings.json 中添加
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

配置后，Claude Code 可以自动搜索你的知识库、查看页面、分析图谱——在你编码时获取相关知识。

详见 [MCP Server 实施计划](docs/mcp-server-plan.md)。

### 工程化改造

项目经过三阶段工程化改造（评分 4.0 → 7.6），详见 [实施计划文档](docs/implementation-plan.md)。

### 参与贡献

欢迎提 Issue 和 PR。大的改动建议先开 Issue 讨论。

### 运行测试

```bash
pip install pytest pytest-asyncio
pytest tests/ -v
```

---

## 致谢与许可证

本项目受 Andrej Karpathy 的 [llm-wiki](https://github.com/karpathy/llm-wiki) 方法论启发。

[MIT License](LICENSE) © 2025 guochen-coder
