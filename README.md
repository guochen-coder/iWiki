# iWiki v1.0.1 — 个人知识库构建工具

![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

iWiki 是一个面向普通用户的知识管理工具。持续"投喂"文档，AI 自动帮你整理、提取关键信息，构建可视化知识图谱。

<img width="2874" height="1356" alt="图谱全览" src="https://github.com/user-attachments/assets/4f2f4fbf-409d-42a5-88f1-664661b51614" />

## 准备工作

### 1. 下载项目

```bash
//github
git clone https://github.com/guochen-coder/iWiki.git
//国内下载地址 git clone https://gitcode.com/Kwok_Chen/iWiki.git
cd iWiki
```

> 没有 Git？去 [git-scm.com](https://git-scm.com/downloads) 下载安装。

### 2. 安装 Python 3.10+

去 [python.org](https://www.python.org/downloads/) 下载安装，完成后验证：

```bash
python3 --version
# 应显示 Python 3.10.x 或更高版本
```

### 3. 运行安装脚本

```bash
bash setup.sh
```

脚本会自动检测 Python、创建虚拟环境、安装依赖、启动服务、打开浏览器。

> 关闭终端或按 `Ctrl+C` 停止服务。

## 使用

1. 打开浏览器访问 `http://localhost:8765`
2. 点击左侧 **⚙️ 设置**，选择提供商、填写 API Key、测试连接、保存

<img width="972" height="942" alt="大模型配置" src="https://github.com/user-attachments/assets/6b73b4dd-a695-4134-ad52-7ff6864f6820" />

3. **摄入文档** — 选择文件导入知识库

<img width="936" height="946" alt="注入的文件" src="https://github.com/user-attachments/assets/432fe745-108e-4e72-a0df-79890e633e9f" />

4. **提问** — 顶部搜索栏向知识库提问

<img width="1642" height="180" alt="提问" src="https://github.com/user-attachments/assets/c6841114-5c4b-4a23-8d23-03aa32474408" />

<img width="1096" height="1378" alt="提问结果" src="https://github.com/user-attachments/assets/187a3039-db21-4b86-ba16-45e96d1d48e5" />

5. **浏览图谱** — 点击节点查看详情，发现知识关联

## 常见问题

### AI 操作报错"API Key 未配置"

点击侧边栏 **⚙️ 设置** → 选择提供商 → 填写 API Key → 保存。支持 Anthropic、DeepSeek 等服务。

> 获取 Anthropic Key：[console.anthropic.com](https://console.anthropic.com)
> 获取 DeepSeek Key：[platform.deepseek.com](https://platform.deepseek.com)

### Python 版本太低

macOS 自带的 Python 版本过低，需手动安装：

```bash
brew install python@3.12
```

### 端口被占用

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
