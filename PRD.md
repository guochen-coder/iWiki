# iWiki 产品需求文档 (PRD)

> 面向 AI 编码智能体实现。目标读者：Claude Code / AI Agent。

## 1. 产品概述

### 1.1 项目愿景

iWiki 是一个面向小白用户的个人知识库构建工具。用户只需克隆仓库、运行 `setup.sh` 配置环境，即可通过可视化 Web 界面完成文档摄入、智能问答、知识图谱浏览等操作。API Key、模型选择等配置均可在 Web 设置面板中完成，无需接触终端和 JSON 文件。

核心价值：**把 AI 驱动的知识管理工具从"面向开发者的 CLI 工具"变为"面向普通用户的可视化应用"。**

### 1.2 开源策略

- 基于 Andrej Karpathy 的 llm-wiki 方法论，知识库采用 `wiki/` 目录 + `graph/graph.json` 的存储格式
- 通用性改进（如 `build_graph.py` 增量更新、错误重试机制）考虑以 PR 形式回馈上游
- README 中添加"Web GUI 版"介绍章节，引导 CLI 用户迁移

### 1.3 迭代规划

**第一阶段：MVP（核心闭环）**

> 目标：小白用户能摄入 Markdown 笔记、提问、看到图谱。

| 模块 | 范围 |
|------|------|
| F0 安装配置 | 完整实现（setup 脚本 + README + API Key 引导） |
| F1 自动启动 | 完整实现（`.claude/settings.json` hooks + 自动打开浏览器） |
| F2 图谱可视化 | 仅 F2.1 基础画布（节点拖拽、缩放、节点大小按度数） |
| F3 操作面板 | 完整布局 + 按钮，不含操作队列（仅执行中/空闲两种状态） |
| F4 摄入文档 | 仅支持 `.md` `.txt`，不含文件类型校验弹窗 |
| F5 智能查询 | 常驻查询栏 + 基本答案展示 |
| F9 结果面板 | 基本日志展示，无可拖拽宽度 |
| F11 错误处理 | 完整实现（API Key 缺失 + 空状态 + 错误提示） |

**第二阶段：核心增强**

> 目标：完整的功能覆盖 + 小白友好的交互细节。

| 模块 | 范围 |
|------|------|
| F2 图谱 | F2.2 节点着色 + F2.3 节点抽屉 + F2.4 边过滤 + F2.5 搜索 |
| F4 摄入 | 完整文件类型校验（P1/P2/P3/不建议/不支持五级弹窗） + PDF/Office 格式 |
| F6 lint | 内容检查完整实现 |
| F7 graph | 图谱重建完整实现 |
| F8 health | 健康检查完整实现 |
| F10 操作队列 | 完整排队机制（FIFO，最多 5 个） |
| F13 删除文档 | 完整实现（二次确认 + 删除后重建衔接） |
| F5.3.1 答案 | Markdown 渲染 + `[[wikilinks]]` 可点击交互 |
| F11.5 欢迎引导 | 首次使用模态框 |

**第三阶段：性能与体验优化**

> 目标：大规模知识库下的流畅体验 + 个性化。

| 模块 | 范围 |
|------|------|
| F14 图谱聚合 | 节点 > 50 自动聚合 + 降级策略 |
| F15 暗色模式 | 完整实现 + localStorage 持久化 |
| F5.4 查询历史 | 会话内历史记录 |
| F4 摄入增强 | 多文件/文件夹批量摄入、URL 链接摄入 |
| F2.2 社区着色 | 按 Louvain 社区着色切换 |
| F9.1 面板拖拽 | 可拖拽调整宽度 |
| F17 多模型支持 | ✅ 已实现：模型配置 + 前端显示当前模型 + Web 设置面板 |
| F18 API 用量 | 会话用量统计 + 单次消耗 + 成本估算 |
| 国际化 | 中/英文界面切换（`i18n`） |

## 2. 用户画像与场景

### 2.1 目标用户

**主要画像：知识工作者「小张」**
- 日常用 Markdown/Word 记笔记、写文档，积累了大量本地文件
- 想从自己的笔记中快速找到答案，而非逐篇翻阅
- 没有编程背景，不会用命令行，不理解"API Key"是什么
- 愿意花 10 分钟按图文教程完成一次性配置
- 日常操作：拖入文档 → 提问 → 看图谱

**次要画像：学生/研究者「小李」**
- 收集大量 PDF 论文、课程笔记（Markdown）、数据集（CSV）
- 需要跨文档发现概念关联，找出研究空白
- 略微了解技术概念（知道"API"大概是什么），但不想写代码
- 日常操作：摄入 PDF → 查询跨文档主题 → 检查内容质量

**辅助画像：开发者「老王」**
- 认同 iWiki 理念，但有自己的定制需求
- 通过 CLI 直接调用 `tools/*.py` 脚本，集成到自己的工作流
- 可能通过修改环境变量切换模型、调整参数
- 不是主要目标用户，但 CLI 保留确保他不流失

### 2.2 核心场景

**场景 1：首次配置与第一次摄入**

> 小张刚 clone 了 iWiki 仓库。她打开 README.md，按步骤运行 `setup.sh`。脚本自动检测 Python、安装依赖、启动服务、打开浏览器。浏览器自动打开了图谱页，弹出欢迎引导："摄入文档 → 提问 → 浏览图谱"。她注意到侧边栏有"设置"按钮，点进去选择了 DeepSeek，粘贴了自己的 API Key，点"测试连接"验证通过，然后保存。
>
> 她点击「摄入文档」，选了桌面上的 `学习笔记.md`。文件上传后，结果面板显示"读取文件... → AI 分析中... → 摄入完成"。图谱中出现了第一个节点。她点击节点，侧栏抽屉展示了 AI 提取的摘要和关键词。

**场景 2：日常知识问答**

> 小张已经摄入了 15 篇笔记。她想回顾"之前关于时间管理的观点"。她在顶部查询栏输入"我关于时间管理有哪些观点和总结？"，按回车。结果面板显示"检索中... → AI 综合中... → 完成"，然后展示带引用链接的答案："你的笔记中共有 3 处关于时间管理的观点：[[番茄工作法实测]]认为... [[GTD 实践记录]]提到..."。她点击 `[[番茄工作法实测]]`，图谱自动定位到该节点，抽屉展开显示完整笔记摘要。

**场景 3：定期知识库维护**

> 小李摄入了 40 多篇 PDF 论文。她想检查知识库是否有问题。她点击「内容检查」，结果面板列出了 5 个问题：2 个孤立页面（没有入站链接）、1 处内容矛盾、2 个缺失的实体页面。她点击矛盾项，图谱中两个相关节点同时高亮。她决定重建图谱以反映最新状态，点击「重建图谱」，弹出预估："当前共 52 个页面，预计最多消耗约 60k tokens（约 $0.18 USD）。是否继续？"，她确认后等待构建完成。

**场景 4：探索知识图谱**

> 老王（虽会用 CLI，但偶尔也用 GUI）想在图谱中发现意想不到的关联。他缩放到远视角，节点自动聚合为社区圆。他看到一个聚合圆很大，放大后发现是一个核心概念节点连接了十几篇文档。他点击该节点，抽屉显示所有相关文档列表，逐个点击浏览。他发现了一篇忘记的旧笔记与当前项目密切相关。

**场景 5：删除旧文档**

> 小张有一篇过时笔记想从知识库中移除。她点击侧边栏底部「删除文档」，在弹出的文档列表中搜索到那篇笔记，点击删除。弹窗确认"确定要删除「过时笔记.md」吗？"，她确认。删除完成后弹窗问"是否重建知识图谱？"，她点"重建图谱"，系统自动开始重建，完成后图谱刷新。

## 3. 功能需求

### F0. 项目初始化

**F0.1 一键配置脚本**
- 提供 `setup.sh`（macOS/Linux）脚本
- 脚本自动完成：检测 Python >= 3.10 → 创建 venv → `pip install -r requirements.txt` → 后台启动 server → 打开浏览器
- 不依赖 Claude Code，不检查 `ANTHROPIC_API_KEY`（API Key 通过 Web 设置面板配置，见 F17）
- 关闭终端或 Ctrl+C 自动停止服务

**F0.2 README.md 小白指南**
- 每一步配文字说明，避免纯代码块
- 分 Windows / macOS / Linux 三列并行说明
- 包含常见报错及解决方法（如 Python 版本过低、pip 权限问题）
- 语言：中文为主，关键术语保留英文

**F0.3 API Key 缺失处理**
- AI 操作需要 API Key。用户可在侧边栏点击"设置"按钮，在弹出的设置面板中配置：
  - 提供商选择（Anthropic / DeepSeek / 自定义端点）
  - API Key 输入
  - 模型选择
  - "测试连接"按钮即时验证 key 是否有效
  - "保存"按钮写入 `.claude/settings.json`，即时生效，无需重启
- 若 AI 操作时无 key，页面显示友好提示页："未检测到 API Key，请在设置中配置"，并提供"去设置"按钮
- 设置面板通过 `GET/POST /api/settings` + `POST /api/settings/test` 实现

---

### F1. 启动

**F1.1 setup.sh 一键启动**
- 用户运行 `bash setup.sh` 后，脚本自动完成安装并后台启动 FastAPI 服务（端口 8765）
- 服务启动后自动在默认浏览器中打开 `http://localhost:8765`
- 关闭终端或 Ctrl+C 自动停止服务
- 若 `graph/graph.json` 不存在（首次启动），页面显示 F11.4 定义的空状态引导页

**F1.2 手动启动**
- 用户也可手动启动：`source venv/bin/activate && python server/server.py`
- Server 独立运行，不依赖 Claude Code 或任何外部进程

---

### F2. 图谱可视化（中间主区域）

**F2.1 画布**
- 使用 vis.js（CDN 方式引入 `vis-network`），渲染在页面中央主区域
- 支持节点拖拽、缩放（滚轮）、画布平移（拖拽空白区域）
- 节点大小按度数（连接数）等比缩放
- 双击节点以该节点为中心重新布局

**F2.2 节点着色与图例**
- 节点按类型着色：来源=绿色，实体=蓝色，概念=橙色，综合=紫色
- 提供切换：按类型着色 / 按 Louvain 社区着色
- 右上角固定图例
- 右下角显示统计信息：可见节点数 / 总边数

**F2.3 节点交互**
- 单击节点：高亮该节点及其直接邻居，其他节点半透明
- 单击节点：从图谱区域右侧滑入抽屉，展示该节点的详细信息
- 抽屉内容：标题、类型标签、社区 ID、markdown 正文（完整渲染）、相关节点标签列表（可点击跳转）

**F2.4 边过滤**
- 控制条：按边类型过滤（提取/推断/模糊），三个复选框，默认"模糊"不勾选
- 置信度滑块：0.0 ~ 1.0，默认 0.0，仅显示置信度 >= 滑块值的边

**F2.5 节点搜索**
- 图谱上方搜索框，输入关键词实时过滤高亮匹配节点
- 支持中文和英文搜索

---

### F3. 操作面板（左侧边栏）

**F3.1 布局**
- 页面左侧固定宽度侧边栏（约 280px），可折叠
- 4 个操作按钮纵向排列，间距统一（query 不在此处，见 F5 独立查询栏）
- 每个按钮左侧图标 + 中文名（大号字体）+ 英文名（小号灰色辅助文字）
- 每个按钮右侧 `?` 图标，鼠标悬停（hover）弹出 tooltip 解释该操作的用途、耗时和 API 消耗

**F3.2 按钮定义**

| 顺序 | 中文名 | 英文辅助 | ? 解释 |
|------|--------|----------|--------|
| 1 | 摄入文档 | ingest | "将本地文档导入知识库。支持 Markdown、TXT、HTML、CSV、JSON、PDF、Office 文档等格式。预估消耗：短文约 2k tokens，长文约 5-10k tokens。" |
| 2 | 内容检查 | lint | "检查知识库的内容质量：是否存在矛盾、过时内容、孤立页面。消耗 API 调用，建议定期运行。预估消耗：约 3-8k tokens（视知识库大小）。" |
| 3 | 重建图谱 | graph | "重新扫描所有 wiki 页面，构建最新的知识关系图谱。消耗较多 API 调用。预估消耗：每页面约 1-2k tokens。" |
| 4 | 健康检查 | health | "快速检查知识库的结构完整性（空文件、索引同步、日志覆盖）。完全免费，零 API 消耗。" |

**F3.3 附加操作**
- 侧边栏底部添加"删除文档"按钮（中文 + 英文 delete 辅助），样式弱于 4 个主按钮（灰色/小号），`?` 解释："从知识库中移除已摄入的文档。"
- 侧边栏底部添加"暗色模式"切换开关（见 F15）

**F3.4 按钮状态**
- 默认：所有按钮可点击（亮色）
- 执行中（MVP 即实现）：当前操作按钮显示 CSS 动画旋转图标（`@keyframes spin`，非 GIF），其余按钮置灰 + `cursor: not-allowed` + 降低透明度 + `title` 属性显示"当前有操作正在进行"
- 排队中（第二阶段实现）：排队操作按钮显示排队序号角标（如"第 2"），前端维护全局任务队列状态，实时更新角标数字
- 某任务失败或完成时，立即从队列中移除，后续任务序号前移

---

### F4. 摄入文档（ingest）

**F4.1 触发**
- 点击"摄入文档"按钮 → 弹出操作系统原生文件选择对话框
- 接受参数：单个文件
- MVP 阶段：文件选择框设置 `accept=".md,.txt"`，由操作系统过滤可选文件（无需自定义校验弹窗）
- 第二阶段：扩展 accept 属性覆盖全部支持格式，并增加 F4.2 自定义校验弹窗
- 后续迭代考虑：多文件、整个文件夹

**F4.2 文件类型校验**
- 选择文件后，前端根据扩展名分类处理：

| 优先级 | 扩展名 | 行为 |
|--------|--------|------|
| P1（直接通过） | `.txt` `.md` `.html` `.csv` `.tsv` `.json` | 直接进入摄入流程 |
| P2（二次确认） | `.pdf` | 弹窗警告"PDF 转换可能丢失排版格式，是否继续？"，用户确认后继续 |
| P3（二次确认） | `.docx` `.pptx` `.xlsx` | 弹窗警告"Office 文档需要额外转换步骤，处理时间可能较长，是否继续？"，用户确认后继续 |
| 不建议 | `.png` `.jpg` `.jpeg` `.webp` `.gif` `.svg` `.wav` `.mp3` `.mp4` `.mov` 等图片/音视频格式 | 弹窗警告"不推荐摄入图片/音视频文件，AI 无法有效提取其中的知识。确定要继续吗？" |
| 不支持 | URL 链接（纯文本粘贴） | 提示"暂不支持 URL 链接摄入，请先下载到本地再导入。" |

**F4.2.1 文件大小限制**
- 单个文件最大 50MB，前端选择文件后立即校验，超过时提示"文件过大（>50MB），请压缩或拆分后再试"
- 后端同样校验文件大小，双重防护（防止前端绕过）
- 见 R2 文件摄入安全

**F4.3 摄入进度**
- 文件确认后，结果展示区（F9）显示分步进度：
  1. ⏳ 读取文件...
  2. ⏳ 格式转换...（仅非 md 文件出现此步骤）
  3. ⏳ AI 分析中...（显示"正在调用 AI，可能需要 30-60 秒"）
  4. ⏳ 写入知识库...
  5. ✅ 摄入完成：[文件名]
- 每步完成后图标更新为 ✅，当前步骤为 🔄

**F4.4 摄入结果与自动图谱更新**
- 摄入完成后，自动触发图谱重建（`build_graph(infer=False)`，仅提取显式 wikilinks，避免额外 LLM 成本）
- 日志显示重建步骤：开始重建图谱 → 提取 wikilinks → 图谱已更新（N 节点 M 边）
- 完成后结果面板显示：生成的 wiki 页面路径、发现的实体/概念数量、是否检测到矛盾
- 前端接收到 complete 后自动刷新图谱画布
- 若需要推断隐式关系（`infer=True`），用户可手动点击「重建图谱」按钮

---

### F5. 智能查询（query）—— **主交互功能**

**F5.1 查询栏（常驻页面顶部）**
- 页面顶部居中放置醒目的查询输入栏，不隐藏在侧边栏中，始终可见
- 样式参考搜索引擎首页：宽输入框 + 右侧"发送"按钮
- placeholder："向你的知识库提问... 例如：这些文档主要讲了什么？"
- 多行输入（textarea），最多 500 字符，按 Enter 发送，Shift+Enter 换行
- 查询栏宽度约 600px ~ 800px（响应式），居中放置，位于图谱画布上方
- 视觉融合：使用 `backdrop-filter: blur(8px)` 毛玻璃效果 + 半透明背景，`z-index` 高于图谱画布但不遮挡节点交互区域（仅占用顶部约 80px 条带）
- 输入框高度自适应：使用 JS 监听 `input` 事件自动调整 textarea 行高（或使用 CSS `field-sizing: content`，降级为 JS 方案）

**F5.2 空状态提示**
- 若知识库为空（无摄入文档），查询栏仍显示但 placeholder 变为"请先摄入文档后再提问"
- 输入框禁用（灰色），发送按钮不可点击

**F5.3 查询执行**
- 点击发送 → 结果展示区（右侧面板，F9）显示进度：
  1. 🔄 正在检索相关页面...
  2. 🔄 AI 正在综合答案...
  3. ✅ 查询完成
- 发送按钮在查询期间显示加载动画，完成后恢复

**F5.3.1 答案展示**
- 结果区完整渲染 Markdown（标题、列表、代码块、引用、加粗、斜体等）
- 答案中的 `[[页面名]]` 引用链接由前端解析为可点击元素（蓝色链接样式）
- 点击 `[[页面名]]` 链接：
  1. 图谱中对应节点高亮 + 脉冲动画
  2. 视图平移到该节点位置（`network.moveTo({position, scale})`）
  3. 自动打开该节点的抽屉，展示完整 wiki 页面内容
- 如引用的页面不存在（幽灵节点），链接显示为灰色虚线样式 + tooltip "此页面尚未创建"

**F5.4 查询历史**
- 当前会话内保留查询历史（内存中，不持久化）
- 结果面板顶部有"历史"下拉，可回看之前的问答
- 点击历史问题 → 直接显示该次查询的答案（不重新请求 API）

---

### F6. 内容检查（lint）

**F6.1 触发**
- 点击"内容检查"按钮 → 结果展示区显示检查进度

**F6.2 检查类型**
- 结构问题：孤立页面（零入站链接）、断开的 `[[wikilinks]]`、缺失的实体页面
- 语义问题：内容矛盾、过时信息、数据缺口
- 图谱问题：枢纽存根、脆弱桥梁、孤立社区

**F6.3 结果展示**
- 结果面板分类列出所有问题，每项可展开查看详情
- 点击某条问题 → 对应图谱节点高亮（如孤立节点直接定位到图中位置）
- 报告末尾附统计摘要："共发现 X 个问题：结构问题 Y 个，语义问题 Z 个..."

---

### F7. 重建图谱（graph）

**F7.1 触发**
- 点击"重建图谱"按钮 → 先检测当前 wiki 页面总数 → 弹窗显示预估消耗：
  > "当前共 N 个页面，预计最多消耗约 XX tokens（约 $X.XX USD）。是否继续？"
  > 两个按钮："取消" / "继续构建"
- 用户确认后，执行完整图谱重建（等同于 `build_graph.py --clean`）
- 若用户取消，不执行任何操作
- 相关缓存机制见 R3 图谱构建 API 成本爆炸
- 结果面板显示构建进度：
  1. 🔄 扫描 wiki 页面...
  2. 🔄 提取显式链接（第 1 阶段）...
  3. 🔄 推断语义关系（第 2 阶段）... `[3/15]`
  4. 🔄 计算社区结构...
  5. ✅ 图谱构建完成：N 个节点，M 条边

**F7.2 完成**
- 图谱画布自动刷新，新节点平滑出现
- 如构建失败，错误信息显示在结果面板，画布保持上一次成功状态

---

### F8. 健康检查（health）

**F8.1 按钮样式**
- 侧边栏中体积最小、颜色最淡的按钮
- 中文名"健康检查"，英文辅助"health"
- `?` 悬浮提示："快速检查知识库的结构完整性。零 API 消耗，随时可放心使用。"

**F8.2 执行**
- 点击后静默执行（无进度条，仅状态图标变化）
- 检查三项：空/存根文件、索引同步状态、日志覆盖完整性
- 结果展示区显示三项的通过/失败状态（✅ / ⚠️）

---

### F9. 结果展示区（右侧面板）

**F9.1 布局**
- 页面右侧独立面板，默认宽度约 400px
- 宽度可拖拽调整：面板左侧边缘添加拖拽手柄（`cursor: col-resize`），拖拽时实时调整宽度（最小 280px，最大 800px）；或使用 CSS `resize: horizontal` + `overflow: auto` 搭配少量 JS 实现
- 可折叠（折叠后面板隐藏，图谱区域扩展）

**F9.2 内容（日志区）**
- 终端风格日志区域：黑色背景 + 等宽字体
- 每条日志带时间戳前缀 `[14:30:05]`
- 日志按级别分色：
  - `[INFO]` — 白色/浅灰，常规进度信息
  - `[SUCCESS]` — 绿色，操作成功完成
  - `[WARNING]` — 黄色/橙色，警告（如文件类型不建议）
  - `[ERROR]` — 红色，操作失败
- 新日志从底部追加，自动滚动到最新
- 操作完成后，日志区上方显示结构化结果摘要（如 lint 报告、查询答案），日志区可折叠以腾出更多空间查看结果

**F9.3 操作队列可视化（第二阶段实现）**
- 结果面板顶部显示操作队列进度条：
  - 左侧：🔄 当前操作名 + 进度百分比（可估计时）或旋转图标（不可估计时）
  - 右侧：⏳ "队列中：N 个任务"
- 悬停队列进度条时弹出详情 tooltip，列出所有等待中的任务名称
- 当前任务完成 → 进度条平滑过渡到下一个任务
- 若队列为空，进度条区域隐藏

---

### F10. 操作队列（第二阶段实现）

> MVP 阶段不实现操作队列。MVP 仅支持执行中/空闲两种状态，执行期间其他按钮直接置灰不可点击。

**F10.1 排他性**
- 全局操作锁：任一时刻最多 1 个操作在执行
- 执行期间其他按钮置灰（opacity: 0.4 + `cursor: not-allowed` + pointer-events: none）

**F10.2 排队机制**
- 若用户在执行期间点击其他按钮 → 操作加入 FIFO 队列
- 队列最多容纳 5 个待执行操作，超出时提示"操作队列已满，请等待"
- 队列显示在 F9.3 中

**F10.3 异常处理**
- 某操作失败时，队列继续执行下一个（不阻塞）
- 失败操作在日志中红色标记，用户可点击"重试"按钮重新加入队列

---

### F11. 错误处理

**F11.1 API Key 缺失**
- 不显示技术堆栈，显示中文引导："未检测到 API Key。请在设置中配置。"
- 提供"去设置"按钮，点击后打开设置面板，用户可直接填写 key 和选择模型
- AI 操作报错时自动弹出 API Key 提示页

**F11.2 API 调用失败**
- 网络错误、超时、速率限制：显示"AI 服务暂时不可用（原因：xxx），请稍后重试。"
- 提供"重试"按钮（重新执行当前操作）

**F11.3 前端错误**
- JS 异常不暴露给用户，捕获后在结果面板显示："操作过程中出现意外错误，请刷新页面。如问题持续，请提交 Issue。"

**F11.4 空状态**
- 当 `graph/graph.json` 不存在或 `wiki/index.md` 中无任何来源条目时，判定为"知识库为空"
- 空状态时，查询/lint/graph 按钮点击后提示"知识库为空，请先摄入至少一篇文档。"
- 图谱区域显示居中的引导插图 + 文字："点击左侧「摄入文档」开始构建你的知识库"
- MVP 无删除功能，知识库只会从空变为非空；第二阶段需额外处理"删除全部文档后回到空状态"的场景

**F11.5 首次使用欢迎引导**
- 首次启动（知识库为空 + 首次访问标记 `localStorage` 中不存在 `iwiki_welcome_dismissed`）时，显示一次性欢迎模态框
- 模态框内容：3 步简述核心流程：
  1. 📄 摄入文档 — "点击左侧「摄入文档」按钮，将你的文档导入知识库"
  2. 💬 提问 — "在顶部搜索栏输入问题，AI 会从你的知识库中综合答案"
  3. 🗺️ 浏览图谱 — "知识图谱自动构建，点击节点查看详情，发现知识关联"
- 模态框底部："不再显示"复选框 + "开始使用"按钮
- 若勾选"不再显示"，写入 `localStorage.iwiki_welcome_dismissed = true`，后续启动不再弹出

---

### F12. CLI 保留

- `tools/` 目录下所有 Python 脚本保持独立可运行，功能不受 UI 影响
- 用户可在终端直接执行 `python tools/ingest.py raw/xxx.md` 等命令
- CLI 输出保持原样（英文日志），不做修改
- 新增的 Python 包装脚本（如 `server.py`）也支持 CLI 参数启动

---

### F13. 删除文档

**F13.1 触发**
- 点击侧边栏底部"删除文档"按钮 → 弹出文档选择列表（显示所有已摄入文档名称）
- 支持搜索/过滤已摄入文档

**F13.2 二次确认**
- 选中文档 → 弹窗确认："确定要删除「xxx」吗？删除后将移除该文档的所有知识条目。此操作不可撤销。"
- 两个按钮："取消" / "确认删除"

**F13.3 删除后**
- 删除完成后弹窗："已删除「xxx」。是否重建知识图谱以反映最新状态？"
- 两个按钮："不了" / "重建图谱"
- 若选择"重建图谱"：弹窗关闭，自动触发 F7 图谱重建流程，结果面板显示构建进度，流程无缝衔接无需用户额外操作

---

### F14. 图谱性能（节点聚合）

**F14.1 缩放任**
- 当可见节点 > 50 时，小缩放级别（远视角）下自动启用节点聚合
- 聚合方式：按 Louvain 社区分组，每个社区显示为一个聚合圆
- 聚合圆大小反映包含节点数，颜色使用社区色
- 放大到一定阈值后自动展开为独立节点

**F14.2 降级策略**
- 节点 > 200 时，默认隐藏"模糊"边（仅显示 EXTRACTED + INFERRED）
- 节点 > 500 时，物理引擎自动降低迭代次数，优先渲染响应性

---

### F15. 暗色模式

**F15.1 切换**
- 侧边栏底部提供切换开关（月亮/太阳图标 + 中文"暗色模式"）
- 切换即时生效，无需刷新
- 偏好存储在 `localStorage`，下次打开页面自动应用

**F15.2 适配范围**
- 页面整体背景、侧边栏、结果面板、图谱画布背景均适配暗色
- 图谱节点颜色保持不变，边颜色在暗色背景下提高亮度
- 结果面板日志区：暗色模式下背景更深，亮色模式下背景浅灰

---

### F16. 移动端（二期）

- 本期（V1）仅适配桌面端（最小宽度 1024px）
- 布局为固定三栏：左侧边栏 | 图谱 | 右侧结果面板
- 移动端适配列入二期规划，不在本 PRD 范围内

---

### F17. 多模型支持（已实现）

**F17.1 模型配置**
- Web 设置面板中提供提供商选择器：Anthropic / DeepSeek / 自定义端点
- 选择 DeepSeek 时自动填入端点 URL `https://api.deepseek.com/anthropic`，模型下拉显示 DeepSeek V4 Flash / V4 Pro
- 自定义端点时可手动输入 Base URL
- 保存后写入 `.claude/settings.json` 的 `env` 字段，即时更新 `os.environ`，无需重启
- 支持任何 litellm 兼容的模型提供商

**F17.2 前端模型显示**
- 侧边栏底部显示当前使用的主模型友好名称（如 "DeepSeek V4 Pro"、"Claude Sonnet 4"）
- 通过 `getModelLabel()` 函数将原始模型名映射为用户可见的标签

---

### F18. API 用量概览

**F18.1 会话用量统计**
- 侧边栏底部或设置区域显示"API 用量概览"折叠面板
- 本次会话累计：总请求次数、总 token 消耗（输入/输出分别统计）
- 数据来源：后端每个 API 响应中的 `usage` 字段，由前端累加

**F18.2 单次操作用量**
- 每次操作完成后，结果面板日志末尾显示该次操作的 token 消耗明细
- 示例："✅ 摄入完成。本次消耗：输入 1,200 tokens，输出 800 tokens"

**F18.3 成本估算**
- 侧边栏用量概览中，基于当前模型的市场价格显示预估费用（如"约 $0.05 USD"）
- 费用仅为估算，标注"实际费用以 API 提供商账单为准"
- 用户可在设置中填入自定义模型的价格（per 1M tokens）以提高估算精度

## 4. UI 设计规格

### 4.1 页面布局（桌面端 1024px+）

```
┌──────────────────────────────────────────────────────────────┐
│  [查询栏]  向你的知识库提问...                     [发送]     │  ← 顶部常驻
├─────────────┬────────────────────────────────────────────────┤
│ 摄入文档 ?   │                                                │
│ 内容检查 ?   │                                                │
│ 重建图谱 ?   │              知识图谱画布 (vis.js)              │
│ 健康检查 ?   │                                                │
│ ────────── │                                                │
│ 删除文档     │                                                │
│ ☀ 暗色      │                                                │
│ 模型: xxx   │                                                │
│ ────────── │                                                │
│ 📋 操作日志  │                                                │
│ ────────── │                                                │
│ [14:30:01] │                                                │
│ 读取文件... │                                                │
│ [14:30:35] │                                                │
│ 摄入完成    │                                                │
├─────────────┴────────────────────────────────────────────────┤
│  [图例: ● 来源  ● 实体  ● 概念  ● 综合]  节点:42  边:108     │
└──────────────────────────────────────────────────────────────┘
│←─ 320px ─→│←────────────── flex:1 ─────────────────────────→│
```

**两栏布局（V1 实际实现）：**
- 左侧边栏（320px，可折叠）：上方操作按钮 + 底部信息，下方日志区 + 结果展示
- 右侧图谱（`flex: 1`）：独占剩余空间
- 原 PRD 设计的三栏布局（右侧独立结果面板）简化为两栏，日志和结果内嵌在侧边栏底部

### 4.2 色彩系统

**亮色模式：**
```css
:root {
  --bg-primary: #FAFAFA;        /* 页面背景 */
  --bg-sidebar: #FFFFFF;        /* 侧边栏背景 */
  --bg-panel: #F5F5F5;          /* 结果面板背景 */
  --bg-query: rgba(255,255,255,0.85); /* 查询栏毛玻璃 */
  --bg-log: #1E1E1E;            /* 日志区域（终端黑） */
  --text-primary: #1A1A1A;      /* 主文字 */
  --text-secondary: #666666;    /* 辅助文字（英文名） */
  --text-log: #D4D4D4;          /* 日志文字 */
  --border: #E0E0E0;            /* 边框/分割线 */
  --accent: #2563EB;            /* 主色调（蓝） */
  --accent-hover: #1D4ED8;      /* hover 加深 */
  --success: #16A34A;           /* 成功绿 */
  --warning: #F59E0B;           /* 警告黄 */
  --error: #DC2626;             /* 错误红 */
  --btn-disabled: #D4D4D4;      /* 按钮禁用 */
}
```

**暗色模式：**
```css
[data-theme="dark"] {
  --bg-primary: #0D1117;
  --bg-sidebar: #161B22;
  --bg-panel: #161B22;
  --bg-query: rgba(22,27,34,0.9);
  --bg-log: #0D1117;
  --text-primary: #E6EDF3;
  --text-secondary: #8B949E;
  --text-log: #C9D1D9;
  --border: #30363D;
  /* accent/success/warning/error 保持不变 */
}
```

### 4.3 排版

- 全局字体：`system-ui, -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif`
- 等宽字体（日志/代码）：`"JetBrains Mono", "Fira Code", "Consolas", monospace`
- 侧边栏按钮中文：`font-size: 16px; font-weight: 600`
- 侧边栏按钮英文辅助：`font-size: 12px; color: var(--text-secondary)`
- 查询栏 placeholder：`font-size: 15px`
- 日志文字：`font-size: 13px; font-family: monospace`

### 4.4 组件样式规范

**侧边栏按钮：**
- 高度 48px，圆角 8px，左右内边距 16px
- 默认：背景透明，hover 时背景 `var(--bg-panel)`
- 执行中：当前按钮背景 `var(--accent)` + 白色文字 + CSS 旋转动画
- 禁用：`opacity: 0.4; cursor: not-allowed; pointer-events: none`
- 图标使用 SVG inline（24x24），颜色继承文字色
- `?` 图标：16x16，`opacity: 0.5`，hover 时 `opacity: 1`

**Tooltip（`?` 悬浮解释）：**
- 绝对定位，出现在 `?` 图标右侧或上方
- 背景 `#333`（亮色）/ `#666`（暗色），白色文字
- 圆角 6px，内边距 8px 12px，`font-size: 12px`
- `max-width: 260px`，自动换行
- 动画：`opacity 0.15s` 淡入

**查询栏：**
- 高度自适应（最小 48px，最大 150px）
- 圆角 12px，`border: 1px solid var(--border)`
- `backdrop-filter: blur(8px); -webkit-backdrop-filter: blur(8px)`
- `z-index: 100`（高于图谱画布）
- `box-shadow: 0 2px 12px rgba(0,0,0,0.08)`
- textarea 无边框、无轮廓、`resize: none`、`width: 100%`
- "发送"按钮：40px 高度，圆角 8px，背景 `var(--accent)`，白色文字

**图谱画布：**
- 背景：亮色 `#FAFAFA`，暗色 `#0D1117`
- vis.js 节点默认样式在 CSS 中覆盖
- 加载状态：画布中央显示旋转加载图标 + "加载图谱数据..."

**节点抽屉（侧滑面板）：**
- 从图谱区域右侧滑入，宽度 360px
- 背景 `var(--bg-sidebar)`，`box-shadow: -4px 0 16px rgba(0,0,0,0.1)`
- 顶部：节点标题（18px 加粗）+ 类型标签（彩色 pill）+ 关闭按钮
- 内容区：Markdown 渲染正文，`[[wikilinks]]` 渲染为蓝色可点击链接
- 底部：相关节点标签列表（横向排列，每个可点击）

**结果面板日志区：**
- 终端风格：`background: var(--bg-log)`，`border-radius: 8px`
- 内边距 12px，`overflow-y: auto`
- 每条日志一行，`line-height: 1.6`
- 时间戳用 `var(--text-secondary)` 色

**模态框：**
- 居中定位，`z-index: 1000`
- 背景遮罩：`rgba(0,0,0,0.5)`
- 内容区：白色/暗色背景，圆角 12px，padding 24px
- 标题 18px 加粗，正文 14px
- 按钮组右对齐，主按钮使用 `var(--accent)`

**进度条（操作队列）：**
- 高度 4px，背景 `var(--border)`，填充色 `var(--accent)`
- 不确定进度时使用 CSS 动画条纹（`@keyframes indeterminate`）
- 下方伴随文字：当前操作名

### 4.5 图标

- 使用 SVG inline，不依赖图标字体库
- 摄入文档：📄 文档图标（或 SVG 等价物）
- 智能查询：💬 对话气泡
- 内容检查：🔍 放大镜
- 重建图谱：🔄 刷新/循环
- 健康检查：❤ 心形（小号，低饱和度）
- 发送：→ 箭头
- 暗色模式：☀/🌙 太阳/月亮

### 4.6 响应式行为

**V1 桌面端（≥1024px）：** 三栏完整显示

**窄屏降级（768px–1023px，二期考虑）：**
- 右侧结果面板默认折叠，按钮触发展开
- 侧边栏缩窄为图标模式（仅图标，无文字）

**移动端（<768px，二期）：**
- 不在 V1 范围，但 CSS 变量和布局使用 flexbox 为后续适配留空间

### 4.7 动画规范

| 元素 | 动画 | 时长 | 缓动 |
|------|------|------|------|
| 按钮 hover | background-color 过渡 | 150ms | ease |
| 按钮执行中旋转 | `@keyframes spin` 360deg 循环 | 1s/圈 | linear |
| 模态框出现 | opacity + scale(0.95→1) | 200ms | ease-out |
| 抽屉滑入 | transform translateX(100%→0) | 250ms | ease-out |
| 日志追加 | opacity 0→1 | 150ms | ease |
| 图谱节点新增 | 节点从中心缩放入场 | 300ms | ease-out |
| Tooltip | opacity 0→1 | 150ms | ease |
| 进度条条纹 | `background-position` 移动 | 1.5s/循环 | linear |
| 暗色模式切换 | `transition: background-color, color` | 300ms | ease |

### 4.8 空状态与错误状态设计

**空知识库状态：**
- 图谱画布中央：大号插图（简约线条风格）+ "你的知识库还是空的" 标题
- 下方文字："点击左侧「摄入文档」导入你的第一篇文档"
- 箭头动画指向侧边栏的摄入按钮

**API Key 缺失状态：**
- 全页面居中卡片，取代正常 UI
- 红色警示图标 + "未检测到 API Key"
- 复制命令按钮 + 测试密钥按钮 + 配置教程链接
- 配置成功后页面自动刷新

**操作失败状态：**
- 结果面板中失败步骤标记为红色 ❌
- 下方显示"重试"按钮
- 日志区错误消息使用 `var(--error)` 色

**加载状态：**
- 图谱加载中：画布中央旋转图标 + "加载中..."
- 操作执行中：按钮内置旋转图标，结果面板显示进度

## 5. 技术架构

### 5.1 整体架构

```
┌─────────────────────────────────────────────────────────┐
│                    用户浏览器                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────────────────┐   │
│  │ 左侧边栏  │  │ 图谱画布  │  │ 右侧结果面板          │   │
│  │ (操作按钮) │  │ (vis.js) │  │ (日志 + 结果展示)     │   │
│  └──────────┘  └──────────┘  └──────────────────────┘   │
│        │              │                │                 │
│        └──────────────┼────────────────┘                 │
│                       │ REST + WebSocket                  │
└───────────────────────┼─────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────┐
│               Python 后端 (FastAPI)                       │
│                       │                                   │
│  ┌────────────────────┼──────────────────────────────┐   │
│  │ server.py           │                              │   │
│  │  /api/ingest       /api/query                      │   │
│  │  /api/lint         /api/graph                      │   │
│  │  /api/health       /api/delete                     │   │
│  │  /ws/progress      (WebSocket)                     │   │
│  └────────────────────┼──────────────────────────────┘   │
│                       │                                   │
│  ┌────────────────────┼──────────────────────────────┐   │
│  │ 工具层（直接 import，非 subprocess）                 │   │
│  │  tools/ingest.py    tools/query.py                  │   │
│  │  tools/lint.py      tools/build_graph.py            │   │
│  │  tools/health.py                                     │   │
│  └───────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
                        │
┌───────────────────────┼─────────────────────────────────┐
│                  数据层（文件系统）                        │
│  raw/         wiki/         graph/                       │
│  (源文档)     (知识页面)    (graph.json + graph.html)     │
└─────────────────────────────────────────────────────────┘
```

**架构原则：**
- 前后端分离：纯 HTML/JS 前端 ↔ FastAPI 后端 ↔ 工具层（import 调用）
- 工具层基于 llm-wiki 方法论实现，**不使用 subprocess**，通过直接 import 函数获取进度回调
- setup.sh 负责：检测环境 + 安装依赖 + 启动后端服务 + 打开浏览器
- 单用户本地运行（desktop app 模式），无需认证、无需多租户

### 5.2 项目目录结构

```
iwiki/
├── setup.sh / setup.bat        # 一键配置脚本
├── requirements.txt            # Python 依赖
├── README.md                   # 小白向安装指南
├── .claude/
│   └── settings.json           # 用户配置（API Key、模型等，由 Web 设置面板写入）
├── server/
│   └── server.py               # FastAPI 后端入口（含 REST + WebSocket）
├── tools/                      # 从参考库复制的工具（直接使用，尽量不改）
│   ├── ingest.py
│   ├── query.py
│   ├── build_graph.py
│   ├── lint.py
│   ├── health.py
│   ├── heal.py
│   ├── refresh.py
│   ├── file_to_md.py
│   └── pdf2md.py
├── web/
│   └── index.html              # 前端单页应用（含 CSS + JS）
├── wiki/                       # 知识层（由工具创建和维护）
│   ├── index.md
│   ├── log.md
│   ├── overview.md
│   ├── sources/
│   ├── entities/
│   ├── concepts/
│   └── syntheses/
├── graph/                      # 图谱数据（由 build_graph.py 生成）
│   ├── graph.json
│   └── graph.html              # 保留参考库的原版图谱页（独立可用）
└── raw/                        # 用户放入的源文档（不可变）
```

**目录职责：**
- `server/` 仅一个 `server.py`，所有后端逻辑集中在此
- `tools/` 为独立可运行的 Python 模块，可被 server 直接 import，也可 CLI 独立使用
- `web/` 仅一个 `index.html`，自包含所有 CSS 和 JS，无构建工具

### 5.3 后端设计

**框架选型：FastAPI**
- 原生 async 支持，适配长时间 LLM 调用
- 内置 WebSocket 支持
- 自动生成 OpenAPI 文档（`/docs`），方便调试
- 选择理由：Flask 的 WebSocket 需要额外插件（flask-socketio），FastAPI 开箱即用

**API 端点设计：**

| 方法 | 路径 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `POST` | `/api/ingest` | 摄入文档 | `multipart/form-data` (file) | `{task_id, status}` |
| `POST` | `/api/query` | 智能查询 | `{question: string}` | `{task_id, status}` |
| `POST` | `/api/lint` | 内容检查 | 无 | `{task_id, status}` |
| `POST` | `/api/graph` | 重建图谱 | `{infer_depth: "basic"|"standard"|"deep"}` | `{task_id, status}` |
| `POST` | `/api/health` | 健康检查 | 无 | `{task_id, status}` |
| `POST` | `/api/delete` | 删除文档 | `{source_name: string}` | `{task_id, status}` |
| `GET` | `/api/task/{task_id}` | 查询任务状态 | 无 | `{status, progress, result, error}` |
| `GET` | `/api/usage` | 获取会话用量统计 | 无 | `{total_requests, total_input_tokens, total_output_tokens, estimated_cost}` |
| `GET` | `/api/sources` | 列出已摄入文档 | 无 | `[{name, slug, created_at}]` |
| `GET` | `/api/model` | 获取当前模型配置 | 无 | `{model_name, model_fast_name}` |
| `WS` | `/ws/progress/{task_id}` | 任务进度推送 | — | 实时 JSON 消息流 |

**WebSocket 消息格式（服务端 → 客户端）：**
```json
{"type": "progress", "step": "ai_analysis", "message": "AI 分析中...", "timestamp": "14:30:05"}
{"type": "log", "level": "info", "message": "正在读取文件...", "timestamp": "14:30:05"}
{"type": "log", "level": "success", "message": "摄入完成: 我的笔记.md", "timestamp": "14:30:35"}
{"type": "complete", "result": {"pages_created": 3, "entities_found": 5}, "usage": {"input": 1200, "output": 800}}
{"type": "error", "message": "API 调用失败: 网络超时"}
```

**工具调用方式：直接 import（非 subprocess）**

```python
# server/server.py 中的调用模式示例
from tools.ingest import ingest_file
from tools.query import query_wiki

# 通过回调函数接收进度
async def run_ingest(file_path: str, progress_callback):
    await progress_callback("reading", "读取文件...")
    result = ingest_file(file_path)  # 同步调用，在线程池中运行
    await progress_callback("done", "摄入完成")
    return result
```

- 所有 LLM 调用通过 `litellm` + 环境变量配置，与参考库一致
- 长时间工具调用在 `asyncio.to_thread()` 或 `run_in_executor()` 中执行，避免阻塞事件循环
- 进度信息通过 WebSocket 推送到前端

**进度回调机制：**
- 修改工具函数签名，添加可选的 `progress_callback: Callable[[str, str], None]` 参数
- 若 callback 为 None（CLI 模式），行为不变，保持向后兼容
- 后端在调用工具时传入 `asyncio.Queue` 作为回调，WebSocket 协程从队列消费消息

### 5.4 前端设计

**技术选型：**
- 纯 HTML/CSS/JS，零构建工具，单文件 `web/index.html`
- vis.js 通过 CDN 引入：`<script src="https://unpkg.com/vis-network@9.1.6/dist/vis-network.min.js">`
- marked.js 通过 CDN 引入用于 Markdown 渲染：`<script src="https://unpkg.com/marked@12.0.0/marked.min.js">`
- 无其他第三方依赖

**模块划分（JS 模块模式 - IIFE）：**

```
App
├── StateManager      # 全局状态管理（单例）
│   ├── queue: []           # 操作队列
│   ├── isExecuting: bool   # 是否正在执行
│   ├── sessionUsage: {}    # 会话用量累计
│   └── darkMode: bool      # 暗色模式
├── APIClient          # HTTP + WebSocket 通信
│   ├── fetchAPI(method, path, body)  # REST 调用
│   ├── connectWS(taskId)             # WebSocket 连接
│   └── onMessage(handler)            # 消息回调
├── GraphView          # 图谱画布（vis.js Network）
│   ├── init(data)
│   ├── highlightNode(id)
│   ├── panToNode(id)
│   └── refresh(data)
├── SidebarPanel       # 左侧操作面板
│   ├── renderButtons()
│   ├── updateButtonStates(state)
│   └── onButtonClick(operation)
├── QueryBar           # 顶部常驻查询栏
│   ├── submit(question)
│   └── setDisabled(bool)
├── ResultPanel        # 右侧结果面板
│   ├── appendLog(level, message, timestamp)
│   ├── renderMarkdown(md)
│   ├── showProgress(taskName, step)
│   └── showQueueStatus(current, pending[])
├── Drawer             # 节点详情抽屉
│   ├── open(nodeData)
│   └── renderWikiContent(markdown)
├── ModalManager       # 模态框管理
│   ├── welcome()      # 首次引导
│   ├── confirm(msg)   # 通用确认
│   └── fileWarning()  # 文件类型警告
└── ThemeManager       # 暗色模式切换
    ├── toggle()
    └── apply()
```

**状态管理（StateManager 全局对象）：**
```javascript
const AppState = {
  isExecuting: false,       // 当前是否有操作在执行
  queue: [],                // [{id, name, operation, params}]
  currentTaskId: null,      // 当前执行中的 task_id
  sessionUsage: {
    totalRequests: 0,
    totalInputTokens: 0,
    totalOutputTokens: 0,
    estimatedCost: 0
  },
  darkMode: localStorage.getItem('iwiki_dark_mode') === 'true',
  welcomeDismissed: localStorage.getItem('iwiki_welcome_dismissed') === 'true',
  modelName: '',            // 从 /api/model 获取
};
```

**WebSocket 客户端实现要点：**
```javascript
function connectWS(taskId) {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
  const ws = new WebSocket(`${protocol}//${location.host}/ws/progress/${taskId}`);
  ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    switch (msg.type) {
      case 'progress': ResultPanel.showProgress(msg.step, msg.message); break;
      case 'log': ResultPanel.appendLog(msg.level, msg.message, msg.timestamp); break;
      case 'complete': handleComplete(msg); break;
      case 'error': handleError(msg); break;
    }
  };
  ws.onclose = (event) => {
    if (!event.wasClean) reconnect(taskId);
  };
}
```

**暗色模式 CSS 方案：**
- `:root` 定义 CSS 变量（`--bg`, `--text`, `--sidebar-bg`, `--panel-bg` 等）
- `[data-theme="dark"]` 覆盖变量值
- JS 切换 `document.documentElement.dataset.theme`

### 5.5 配置管理

**`.claude/settings.json` 配置（由 Web 设置面板自动写入）：**
```json
{
  "env": {
    "ANTHROPIC_AUTH_TOKEN": "sk-...",
    "LLM_MODEL": "anthropic/claude-sonnet-4-6",
    "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic"
  }
}
```

**配置流程：**
1. 用户运行 `bash setup.sh`，启动 FastAPI 服务
2. 浏览器打开 `http://localhost:8765`，打开侧边栏"设置"面板
3. 选择提供商（Anthropic/DeepSeek/自定义）→ 填 API Key → 选模型 → 点"测试连接" → 点"保存"
4. 后端更新 `os.environ` + 写入 `.claude/settings.json`，即时生效无需重启
5. 前端通过 `GET /api/settings` 加载当前配置，侧边栏显示当前模型名

**启动流程：**
- Server 通过 `setup.sh` 或手动 `python server/server.py` 启动
- 不依赖 Claude Code，server 独立运行
- `_load_claude_env()` 在启动时从 `.claude/settings.json` 加载 env 配置

### 5.6 多模型配置

**环境变量（`.env` 或 shell export）：**
```bash
LLM_MODEL=claude-sonnet-4-6-20250514    # 主模型（ingest/query/lint 综合）
LLM_MODEL_FAST=claude-haiku-4-5-20251001 # 快速模型（图谱推断、查询页面选择）
ANTHROPIC_API_KEY=sk-ant-xxx             # 或 OPENAI_API_KEY 等
```

- 完全兼容 litellm 模型名称，用户可切换为 `gpt-4o`、`gemini-2.0-flash` 等
- 后端启动时读取环境变量，通过 `/api/model` 告知前端当前模型名
- 不提供 LLM 提供商切换（用户自行通过环境变量配置）

### 5.7 依赖清单

**Python（requirements.txt）：**
```
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
python-multipart>=0.0.18       # 文件上传支持
litellm~=1.83.10               # LLM API 抽象（锁定版本，参考库同版本）
networkx~=3.6.1                # 图谱算法
markitdown[all]>=0.1.5,<0.2.0 # 多格式文件转换
websockets>=13.0               # WebSocket 支持（uvicorn 内置，显式声明）
```

- `tools/` 中原有依赖保持不变（`tqdm` 等）
- 新增依赖仅 `fastapi`、`uvicorn`、`python-multipart`
- `websockets` 为 uvicorn 内置依赖，显式声明确保版本

### 5.8 关键实现注意事项

1. **工具导入路径：** `server/server.py` 需将项目根目录加入 `sys.path`，以便 `from tools.ingest import ...`
2. **线程安全：** 全局操作锁在 `server.py` 中用 `asyncio.Lock` 实现，确保同一时间仅一个工具函数在执行
3. **同步→异步桥接：** 工具函数为同步调用，需在 `await asyncio.to_thread()` 中执行。进度回调通过 `loop.call_soon_threadsafe(queue.put_nowait, msg)` 实现跨线程推送，WebSocket 协程从 `queue` 消费
4. **WebSocket 断线重连：** 前端实现指数退避重连（1s → 2s → 4s → 8s → 16s，最多 5 次）
5. **端口冲突处理：** 服务器启动时检测 8765 端口是否被占用，若被占用则提示用户手动终止占用进程或修改 `PORT` 环境变量
6. **服务器健康确认：** hook 中的 `sleep 2` 后增加 `curl -s http://localhost:8765/api/model` 检查，失败时输出错误提示
7. **CORS：** 若前后端同源（同一 `localhost:8765`），无需 CORS 配置；否则需 `fastapi.middleware.cors`
8. **CLI 兼容：** 所有 `tools/*.py` 修改仅限于添加可选 `progress_callback` 参数，默认值 `None` 保持 CLI 行为不变

## 6. 验收标准

> 以下验收标准面向 AI 编码智能体，每条均可自动化验证。按迭代阶段组织。

### 第一阶段 MVP 验收

**AC-0：一键安装**
- [ ] `setup.sh` 在 macOS/Linux 干净环境执行后，Python 环境就绪，`pip install` 成功
- [ ] 未设置 `ANTHROPIC_API_KEY` 时，脚本输出包含"获取地址"和配置提示
- [ ] 安装完成后脚本询问"是否现在启动 Web 服务？(y/n)"

**AC-1：自动启动**
- [ ] 执行 `python server/server.py` 后，访问 `http://localhost:8765` 返回 `web/index.html`
- [ ] 若 `graph/graph.json` 存在，图谱渲染在页面中央
- [ ] 若 `graph/graph.json` 不存在，页面显示空状态引导而非报错

**AC-2：图谱基础交互**
- [ ] 节点可拖拽移动位置
- [ ] 滚轮缩放，拖拽空白区域平移画布
- [ ] 节点大小与度数正相关（度数越高节点越大）

**AC-3：摄入文档（仅 .md/.txt）**
- [ ] 点击「摄入文档」→ 弹出系统文件选择框，仅显示 `.md` `.txt` 文件（通过 `<input accept=".md,.txt">` 实现）
- [ ] 选择 `.md` 文件后，结果面板显示进度日志（读取→AI 分析→写入→完成）
- [ ] 摄入完成后图谱新增对应节点
- [ ] 浏览器原生文件选择器自动过滤不支持的格式，用户无法选中其他扩展名文件

**AC-4：智能查询**
- [ ] 顶部查询栏始终可见，输入问题后回车发送
- [ ] 结果面板显示 AI 答案，包含 `[[页面名]]` 引用
- [ ] 知识库为空时，查询栏禁用并提示"请先摄入文档"

**AC-5：错误处理**
- [ ] API Key 缺失时，页面显示配置引导（含复制按钮 + 测试密钥按钮）
- [ ] API 调用失败时，显示"AI 服务暂时不可用" + 重试按钮
- [ ] JS 异常不暴露技术堆栈给用户

**AC-6：侧边栏按钮状态**
- [ ] 某操作执行中，其余 3 个按钮置灰不可点击
- [ ] 操作完成后，所有按钮恢复可点击

### 第二阶段验收

**AC-7：文件类型五级校验**
- [ ] `.md` `.txt` → 直接摄入（P1）
- [ ] `.pdf` → 弹窗二次确认（P2）
- [ ] `.docx` → 弹窗二次确认（P3）
- [ ] `.png` → 警告不建议，确认后可继续（不建议）
- [ ] 粘贴 URL → 提示不支持

**AC-8：图谱完整功能**
- [ ] 节点按类型着色（来源/实体/概念/综合），图例正确显示
- [ ] 单击节点：抽屉滑入显示 markdown 正文 + 相关节点列表
- [ ] 边过滤：三个复选框切换边类型，默认隐藏"模糊"边
- [ ] 置信度滑块有效（拖动后不符合条件的边消失）
- [ ] 搜索框输入关键词，匹配节点高亮

**AC-9：lint 检查**
- [ ] 点击后结果面板列出所有问题（分类：结构/语义/图谱）
- [ ] 点击某条问题 → 对应图谱节点高亮定位

**AC-10：graph 重建**
- [ ] 点击「重建图谱」→ 弹出成本预估弹窗
- [ ] 确认后，结果面板显示 5 步进度
- [ ] 完成后图谱自动刷新

**AC-11：health 检查**
- [ ] 点击后快速返回三项检查结果（✅/⚠️）
- [ ] 无 API 调用消耗

**AC-12：操作队列**
- [ ] 执行中点击其他按钮 → 操作进入排队
- [ ] 当前操作完成 → 自动执行队列中的下一个
- [ ] 队列最多 5 个，超出时提示
- [ ] 失败操作不阻塞后续队列

**AC-13：删除文档**
- [ ] 选中文档 → 二次确认弹窗
- [ ] 删除后弹窗"是否重建图谱？"
- [ ] 确认后自动触发图谱重建

**AC-14：查询 Markdown 渲染**
- [ ] 答案中的 Markdown 正确渲染（标题、列表、代码块、加粗等）
- [ ] 点击 `[[页面名]]` → 图谱节点高亮 + 平移 + 抽屉打开

**AC-15：首次引导**
- [ ] 首次访问时弹出欢迎模态框（3 步引导）
- [ ] 勾选"不再显示"后，刷新页面不再弹出

### 第三阶段验收

**AC-16：图谱聚合**
- [ ] 节点 > 50 时，缩小后节点自动聚合为社区圆
- [ ] 放大后聚合圆展开恢复独立节点

**AC-17：暗色模式**
- [ ] 切换开关即时生效、无刷新
- [ ] 刷新页面后保持选择（localStorage）

**AC-18：API 用量**
- [ ] 侧边栏显示会话 token 累计 + 估算费用
- [ ] 每次操作完成后展示该次消耗

**AC-19：查询历史**
- [ ] 结果面板可查看本次会话的历史问答
- [ ] 点击历史问题直接展示之前答案（不重新请求）

**AC-20：面板拖拽**
- [ ] 拖拽结果面板左侧边缘可调整宽度
- [ ] 最小 280px，最大 800px

## 7. 非功能需求

### 7.1 性能

| 指标 | 目标 | 测量方式 |
|------|------|----------|
| 页面首次加载 | < 3 秒（含图谱数据加载） | Chrome DevTools Lighthouse |
| 图谱渲染（100 节点） | < 2 秒 | vis.js stabilization 完成时间 |
| 操作 API 响应（启动任务） | < 500ms | 后端返回 task_id 的时间 |
| 日志追加延迟 | < 100ms | WebSocket 消息到达 → DOM 更新 |

### 7.2 兼容性

| 维度 | 要求 |
|------|------|
| 浏览器 | Chrome 100+, Firefox 100+, Edge 100+, Safari 16+ |
| 操作系统 | macOS 12+, Windows 10+, Ubuntu 22.04+ |
| Python | 3.10, 3.11, 3.12, 3.13 |
| vis.js CDN | 固定版本 `vis-network@9.1.6`，避免跨版本不兼容 |
| marked.js CDN | 固定版本 `marked@12.0.0` |

### 7.3 安全性

- 文件上传限制 50MB，前后端双重校验
- 文件名过滤防路径遍历（仅允许中英文、数字、`_` `-` `.`）
- 不执行用户上传文件中的任何代码（宏、JS、VBA）
- 后端仅监听 `127.0.0.1`（localhost），不接受外部连接
- 无用户认证系统（单用户本地运行）

### 7.4 可维护性

- `tools/` 目录下的代码修改仅限于添加 `progress_callback` 可选参数
- 其他参考库代码保持原样，方便跟踪上游更新
- `server/server.py` 为所有新增逻辑的唯一入口
- `web/index.html` 为所有前端逻辑的唯一文件
- 前端 JS 使用 IIFE + 模块对象模式，避免全局变量污染

### 7.5 可用性（小白友好）

- 所有面向用户的文案使用中文
- 技术术语附带白话解释（如 "token ≈ 一个字或一个词"）
- 每个操作按钮有 `?` 悬浮解释
- 错误消息不包含技术堆栈，给出可操作的下一步
- 读取和写入文件的操作均有进度反馈

## 8. 风险与应对

### R1. 长任务超时

**风险：** 摄入大文件或重建图谱可能耗时数分钟，HTTP 请求可能超时断开，前端看不到结果。

**应对：**
- 优先采用 **WebSocket** 长连接：后端执行过程中主动推送进度日志到前端，前端实时渲染在结果面板
- **轮询兜底（V1 已实现）**：前端同时启动每 3 秒轮询 `GET /api/task/{task_id}`，若检测到任务 completed/failed 而 WebSocket 未推送，自动解锁 UI。解决 WebSocket 消息丢失导致的 UI 卡死问题
- 操作进行中显示呼吸灯 + "处理中" 动画指示器，防止用户误以为死机
- WebSocket 连接断开时自动重连（指数退避，最多 5 次）

### R2. 文件摄入安全

**风险：** 用户可能上传恶意文件（超大 PDF 耗尽内存、包含宏病毒的 Office 文档、路径遍历文件名）。

**应对：**
- **文件大小限制：** 前端 + 后端双重校验，单个文件最大 50MB，超过时提示"文件过大，请压缩或拆分后再试"
- **文件名安全：** 过滤 `../` `..\` 等路径遍历字符，仅保留文件名部分；文件名仅允许字母、数字、中文、下划线、连字符、点号，其他字符替换为 `_`
- **Office 文档：** 使用安全库解析（如 `python-docx`、`openpyxl`、`python-pptx`），禁用宏执行
- **PDF 解析：** 使用安全库（如 `PyMuPDF`、`pdfplumber`），默认不执行内嵌 JavaScript
- **临时文件清理：** 摄入完成后立即删除临时转换文件，异常时在 `finally` 块中清理

### R3. 图谱构建 API 成本爆炸

**风险：** 用户摄入大量文档后重建图谱，`build_graph.py` 对每对页面调用 LLM 推断关系，N 个页面约 N×(N-1)/2 次调用，成本极高。

**应对：**
- **执行前预估弹窗：** 点击"重建图谱"后，先检测当前 wiki 页面总数，弹窗显示预估消耗并让用户确认：
  > "当前共 N 个页面，预计最多消耗约 XX tokens（约 $X.XX USD）。是否继续？"
  > 两个按钮："取消" / "继续构建"
- **增量缓存：** 对内容未变更的页面（SHA256 比对），复用上一次的推断结果，仅对新页面/修改页面进行语义推断
- **关系推断深度配置：** 允许用户在设置中选择推断范围："仅直接引用"（默认，成本最低）/ "标准推断" / "深度推断"（全对全，成本最高）
- 缓存文件（`.inferred_edges.jsonl`）不得随意删除，`--clean` 操作同样需执行前弹窗确认

### R4. 节点命名冲突

**风险：** 不同来源文档中出现同名实体（如两个"张三"），若仅用名称作为图谱节点 ID，会导致错误的合并。

**应对：**
- 后端提取实体时生成唯一 ID：`hash(source_file + entity_name)`，而非仅使用名称
- 前端图谱以唯一 ID 区分节点，显示标签仍用实体名称
- 若多个节点同名，前端在抽屉中显示"同名实体"列表，标注各自来源文档
- vis.js 原生支持 UTF-8，中文节点标签无需特殊处理
