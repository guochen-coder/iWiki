# iWiki — 个人知识库构建工具

iWiki 是一个面向普通用户的知识管理工具。你只需要持续"投喂"文档，AI 就会自动帮你整理、提取关键信息，构建成一个可视化的知识图谱。

## 准备工作

### 1. 安装 Python 3.10+

去 [python.org](https://www.python.org/downloads/) 下载安装。

安装完成后，打开终端验证：

```bash
python3 --version
# 应显示 Python 3.10.x 或更高版本
```

### 2. 配置 API Key

AI 功能的运转需要一个 LLM API Key。支持 Anthropic、DeepSeek 等兼容 OpenAI 接口的服务。

在项目根目录的 `.claude/settings.json` 中配置：

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "你的密钥",
    "LLM_MODEL": "anthropic/claude-sonnet-4-6"
  }
}
```

`LLM_MODEL` 可省略，默认使用 Claude Sonnet。如果使用其他服务（如 DeepSeek），需同时修改 `LLM_MODEL`，例如：

```json
{
  "env": {
    "ANTHROPIC_API_KEY": "sk-你的deepseek密钥",
    "LLM_MODEL": "deepseek/deepseek-chat"
  }
}
```

> 获取 Anthropic API Key：[console.anthropic.com](https://console.anthropic.com)
> 获取 DeepSeek API Key：[platform.deepseek.com](https://platform.deepseek.com)

## 快速开始

### 1. 克隆并安装

打开终端，执行：

```bash
git clone <仓库地址>
cd iwiki

# 运行安装脚本
bash setup.sh
```

安装脚本会自动检测 Python、创建虚拟环境、安装依赖。

### 2. 启动

安装脚本运行后会自动启动 Web 服务并打开浏览器。在浏览器中访问 `http://localhost:8765` 即可使用。

关闭终端或按 `Ctrl+C` 会停止服务。重新启动：

```bash
source venv/bin/activate
python server/server.py
```

## 使用

- **左侧四个操作按钮** — 摄入文档、内容检查、重建图谱、健康检查
- **顶部搜索栏** — 向知识库提问，AI 检索并综合答案
- **中间图谱** — 点击节点查看详情，发现知识关联

## 常见问题

### AI 操作报错"API Key 未配置"

请确认 `.claude/settings.json` 中已正确配置 `ANTHROPIC_API_KEY`。详见[准备工作 - 配置 API Key](#2-配置-api-key)。

### Python 版本太低

本项目需要 Python 3.10 或更高版本。macOS 自带的 Python 通常是 3.9，需要手动安装新版：

```bash
brew install python@3.12
```

### 端口被占用

如果 8765 端口被占用，可以指定其他端口：

```bash
PORT=8766 python server/server.py
```

## 项目结构

```
iwiki/
├── setup.sh           # 一键安装脚本
├── server/server.py   # Web 后端
├── web/index.html     # Web 前端
├── tools/             # 命令行工具（可独立使用）
├── wiki/              # 知识库数据
├── graph/             # 图谱数据
└── raw/               # 源文档
```

## 致谢

本项目基于 Andrej Karpathy 的 llm-wiki 方法论构建。
