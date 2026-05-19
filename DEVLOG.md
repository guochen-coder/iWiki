# iWiki MVP 开发修复记录

> 2026-05-18

## 环境适配

| # | 问题 | 修复 |
|---|------|------|
| 1 | Python 3.9 不支持 `X \| None` 联合类型语法 | 为 `tools/ingest.py`、`tools/query.py`、`tools/refresh.py`、`tools/heal.py`、`tools/pdf2md.py` 添加 `from __future__ import annotations` |
| 2 | litellm 1.83.x 不识别裸模型名 `claude-3-5-sonnet-latest` | `server.py` 启动时设置默认 `LLM_MODEL=anthropic/claude-3-5-sonnet-20241022`（加 provider 前缀） |
| 3 | `ANTHROPIC_AUTH_TOKEN` 不被 litellm 识别 | `server.py` 添加 `_load_claude_env()`：从 `.claude/settings.json` 读取 env 并桥接 `ANTHROPIC_AUTH_TOKEN` → `ANTHROPIC_API_KEY` |
| 4 | `markitdown[all]` 在 PyPI 不可用 | `requirements.txt` 中注释掉，标记为二期验证 |

## 后端修复

| # | 问题 | 修复 |
|---|------|------|
| 5 | 摄入完成后 `complete` 消息未发送，前端永远不解锁 | ingest 任务末尾添加 `push_progress(tid, "complete", ...)` |
| 6 | WebSocket 重放历史 + 队列推送导致日志重复打印 | WS 连接后回放历史，然后清空队列中已发送的消息 |
| 7 | 摄入成功后图谱不更新（`graph.json` 还是旧的） | 摄入完成后自动调用 `build_graph.build_graph(infer=False)` 重建图谱 |
| 8 | 图谱重建过程无日志 | 重建前后添加日志：开始重建 → 提取 wikilinks → 完成（N 节点 M 边） |

## 前端修复

| # | 问题 | 修复 |
|---|------|------|
| 9 | WebSocket 漏消息时 UI 永久卡死 | 添加每 3 秒轮询 `GET /api/task/{id}` 作为兜底，检测到 completed/failed 自动解锁 |
| 10 | 操作中无等待反馈，用户以为死机 | 日志区上方添加蓝色呼吸灯 + "处理中" 文字 |
| 11 | `graph.json` 边字段用 `from`/`to`，前端用 `e.source`/`e.target` | `renderGraph` 兼容两种字段名：`e.from \|\| e.source` |
| 12 | 节点大小字段 `n.value`，前端用 `n.degree` | 改为 `n.value` |
| 13 | 发送按钮初始 disabled，加载后未启用 | `init` 中根据图谱是否有数据决定启用/禁用 |
| 14 | `onOperationDone` 先 `setButtonsEnabled(true)` 再移除 `executing` 类 → executing 按钮被跳过 | 调换顺序：先移除类再启用按钮 |
| 15 | 节点抽屉无内容：`graph.json` 中用 `markdown`，前端查 `content` | 改为 `node.markdown \|\| node.content` |
| 16 | 节点标签色不跟随主题 | 亮色 `#333`，暗色 `#E6EDF3`，主题切换时 `network.setOptions` 即时更新 |
| 17 | 侧边栏无法折叠/展开 | 添加折叠按钮，折叠后留在边缘可唤出 |
| 18 | 右侧结果面板布局 | 日志/结果区移入左侧边栏底部，右侧图谱独占空间 |

## 项目结构调整

| # | 变更 |
|---|------|
| 19 | 参考项目从 `wiki/llm-wiki-agent-main` 移至 `vendor/llm-wiki-agent-main`，避免污染 `wiki/` 数据目录 |
| 20 | CLAUDE.md 中所有路径引用同步更新 |
| 21 | SessionStart hook 去掉自动打开浏览器，服务改为纯后台运行；setup.sh 同样不再自动打开浏览器，改为提示用户手动打开 |
| 22 | CLAUDE.md 新增对话限制规则：禁止直接修改 wiki/raw/graph 目录，所有知识库操作必须通过 Web UI 或 CLI 工具 |
| 23 | setup.sh 恢复安装完成后自动打开浏览器（一次性配置场景，与 SessionStart 每次不跳转的设计不同） |
| 24 | 后端新增 `_sanitize_error()` 统一替换 auth 错误为中文提示；所有 except 块改用 sanitized 错误消息 |
| 25 | 前端新增 API key 错误检测与友好提示页：操作报错时显示 "Claude Code 服务异常" 并提示运行 `claude login`；支持关闭恢复 |

## 2026-05-19 — 架构解耦与 UX 改进

### Server 独立化（方案 1）

| # | 变更 |
|---|------|
| 26 | `.claude/settings.json` 中移除 SessionStart/SessionEnd hooks，server 不再随 Claude Code 启停 |
| 27 | `setup.sh` 不再检查 Claude Code（改为可选），精简为 4 步 [1/4]~[4/4] |
| 28 | server 生命周期由 `setup.sh` 终端控制：trap EXIT 杀 server，关终端即停 |
| 29 | README 重写：准备工作改为 Python + API Key 两项，删除 Claude Code 安装章节 |

### Web 设置面板（方案 B）

| # | 变更 |
|---|------|
| 30 | 后端新增 `GET /api/settings`、`POST /api/settings`、`POST /api/settings/test` 三个接口 |
| 31 | 前端新增设置模态框：提供商选择（Anthropic/DeepSeek/自定义）、模型下拉、端点 URL、API Key 输入 |
| 32 | 保存即时生效：更新 `os.environ` + 写入 `.claude/settings.json`，无需重启 server |
| 33 | 测试连接：用当前配置发最小 LLM 请求，即时反馈成功/失败 |
| 34 | 后端 key 桥接：`ANTHROPIC_AUTH_TOKEN` → `ANTHROPIC_API_KEY` → `DEEPSEEK_API_KEY` 全链覆盖 |
| 35 | 支持 `ANTHROPIC_BASE_URL` 配置自定义端点（如 DeepSeek 的 `https://api.deepseek.com/anthropic`） |
| 36 | 提供商切换时模型下拉动态更新，DeepSeek 时显示 DeepSeek V4 Flash/Pro 等友好标签 |
| 37 | 原 API Key 缺失提示页改为"去设置"按钮，引导用户到设置面板而非展示命令行 |
| 38 | 删除 `web/guide.html`（Claude Code 安装引导页），已无引用 |

### 文档对齐

| # | 变更 |
|---|------|
| 39 | CLAUDE.md 重写：移除 Claude Code hooks 相关内容，更新架构说明、API 端点表、配置存储方式 |
| 40 | PRD.md 同步更新：F0/F1/F11/F17/5.5 等章节 |
| 41 | 项目需求.md 更新为当前实现方式
