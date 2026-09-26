# Atoms-Demo（类 Atoms 的 AI Agent 应用生成平台）Spec

> 依据：`docs/atoms-功能拆解.md` + 笔试要求（真实交互、数据持久化、核心主流程、至少一个延展能力）
> **P0 = 最小核心闭环（再收敛版，必须全部实现）**；P1 = 延展能力（尽量做 1 个）；P2 = 时间富余的亮点

## Why

在 6-8 小时内交付可运行、可体验的 "Atoms Demo"：智能体驱动生成应用并以可视化网页展示。P0 聚焦最小闭环，把前后端交互、核心功能、部署方案一次想清楚。

## What Changes

- 新建全栈应用：**Vue 3 前端 + Python(FastAPI) 后端 + deepagents 智能体 + SQLite**
- 核心闭环：输入需求 → deepagents 流式生成（todo/工具调用过程可视）→ 沙箱预览 → follow-up 增量迭代 → 持久化
- 数据层经 SQLAlchemy，连接串可切换 PostgreSQL；LLM 走环境变量可换模型

## Impact

- Affected specs: 无（首个 spec）
- Affected code: 全新项目 `d:\项目\atoms-agent`（当前仅有 `docs/`）

---

## 一、技术选型

| 层 | 选型（P0 起步） | 可扩展路径 |
|---|---|---|
| 前端 | **Vue 3 + Vite + Pinia + Vue Router + TailwindCSS** | 标准组合，可平移 |
| 后端 | **Python 3.12 + FastAPI + uvicorn** | SSE 用 sse-starlette |
| Agent | **deepagents**（内置规划 todo + 子代理 + 工具调用，天然贴合 Atoms"过程直播"） | 换模型/加子代理不影响结构 |
| LLM | LangChain OpenAI-compatible（`LLM_BASE_URL / LLM_API_KEY / LLM_MODEL` 环境变量） | GLM/DeepSeek/OpenAI 一键切换 |
| 存储 | **SQLite + SQLAlchemy**，`DATABASE_URL` 环境变量 | 换 PostgreSQL 只改连接串，ORM 层不动 |
| 预览 | 后端组装文件为自包含 HTML，经 `/preview/{id}` 供 iframe `sandbox` 加载 | 后续可升级多文件构建 |
| 部署 | **单 Docker 镜像**（多阶段：Node 构建 Vue → Python 服务静态文件+API），Railway/Render + 持久卷挂 `/data` 存 SQLite | 换平台/换库不影响业务代码 |

## 二、前后端交互契约（P0 核心设计）

**REST**（JSON）：
- `POST /api/projects` `{prompt}` → `201 {id, title}`（创建并立即开始首次生成）
- `GET /api/projects` → `[{id, title, created_at}]`
- `GET /api/projects/{id}` → `{messages: [...], files: {"index.html": "...", ...}}`（刷新恢复）
- `DELETE /api/projects/{id}` → `204`
- `GET /preview/{id}` → `text/html`（文件组装后的应用页，供 iframe `src`）

**SSE**（`POST /api/projects/{id}/chat` `{message}`，fetch ReadableStream 消费，sse-starlette 推送）：
- `event: step` `{kind: todo|tool|message, agent, content}`（生成过程步骤，deepagents 的 todo 更新与工具调用映射为此事件）
- `event: files` `{files}`（save_file 工具落库后推送，可多次）
- `event: queue` `{position, max}`（并发池排队位次：position>0 排队第 N 位；position=0 已获槽位开始生成）
- `event: done` `{summary}`（本次任务完成总结）
- `event: stopped` `{message}` / `event: error` `{message}`（Stop 收尾 / 失败，前端展示重试）

**项目事件长连接**（`GET /api/projects/{id}/events`，多设备实时同步的数据通道）：
- 有活跃生成 → 原子快照重放（queue 位次 + 已发生 steps + 最新 files）+ 继续直播直到本轮结束
- 空闲 → 挂入项目 hub 等待，项目变更时推 `event: sync` `{reason: chat_start|gen_end|rollback|share, running}`；
  前端收到 `sync(chat_start)` 拉取新消息后断开重连进入直播，收到其他 sync 拉详情合并
- sse-starlette 周期 ping 保活；前端断线退避重连（重放为全量快照，幂等）

**关键机制**：deepagents 不做脆弱的"整包 JSON 输出"，而是给 Engineer Agent 注册 `save_file(filename, content)` 工具——每个文件由工具调用落库并即时推 `files` 事件，天然结构化 + 增量流式。

## 三、P0 —— 最小核心闭环（必须全部实现）

### R1: 需求输入与项目创建
- **WHEN** 用户在首页输入框填需求并提交
- **THEN** 创建项目、跳转工作台、自动开始首次生成

### R2: 流式生成与过程可视化
系统 SHALL 用 deepagents 执行生成（内置规划 todo → 工具调用写文件），过程 SHALL 经 SSE `step` 事件在聊天面板实时展示步骤卡片，文件经 `save_file` 工具结构化落库。
- **WHEN** 生成进行中 **THEN** 聊天面板流式出现"规划/正在写 index.html"等步骤卡片
- **WHEN** 生成完成 **THEN** 展示变更总结，文件集完整

### R3: 沙箱实时预览
系统 SHALL 经 `/preview/{id}` 组装自包含 HTML（相对路径内联、Tailwind CDN 可用），iframe `sandbox` 隔离加载；`files` 事件到达后自动刷新预览，应用内交互真实可用。

### R4: 对话式增量迭代
- **WHEN** 用户发送 follow-up（如"主题色改绿色"）
- **THEN** Agent 携带当前文件上下文增量修改，未提及文件不变，预览自动刷新

### R5: 持久化与项目列表
系统 SHALL 持久化项目/消息/文件（SQLite），刷新或从列表重开完整恢复；项目列表支持打开、删除。存储经 SQLAlchemy，`DATABASE_URL` 可切换。
- **WHEN** 刷新浏览器重开项目 **THEN** 对话历史与代码状态完整恢复

### R6: 错误处理与重试
- **WHEN** LLM 失败/超时
- **THEN** 聊天流显示错误卡片，一键重试成功，无脏数据（不产生半成品文件状态）

### R7: 注册/登录与多用户隔离（用户追加的 P0）
系统 SHALL 提供邮箱密码注册/登录（Cookie 会话，HttpOnly），项目归属 owner；未登录访问受保护页面跳转登录页；项目列表/工作台仅可见自己的项目；分享链接与预览访客免登录。
- **WHEN** 未登录打开任意受保护页 **THEN** 跳转 /login
- **WHEN** 用户 A 登录 **THEN** 项目列表只见自己的项目；直接访问他人项目 API 返回 404
- **WHEN** 退出 **THEN** 会话失效，需重新登录

### R8: 消息队列与 Stop（用户追加的 P0）
生成进行中，新消息 SHALL 入队（可删除）而非被禁言；队列在本轮结束后自动依序执行；Stop SHALL 协作式中断当前生成——engineer 流循环逐 chunk 检查取消标志（延迟≈一个 token），已完成写入的文件保留落库（保留进度），聊天落「已停止」消息，队列清空。
- **WHEN** 生成中发送 follow-up **THEN** 进入队列展示（可删），本轮完成自动发送下一条
- **WHEN** 点击 Stop **THEN** 当前生成近乎立即停止，已保存文件落库并刷新预览，聊天出现「⏹ 已停止」卡片

## 四、P1 —— 延展能力（已完成）

- **R9 版本快照与回滚**：每次生成完成存快照，历史版本一键回滚（文件+预览恢复）
- **R10 PC/移动视口切换**：预览宽度切换
- **R11 一键分享**：公开只读链接，访客免登录可交互；关闭即失效
- **R12 代码查看与导出**：文件树 + 语法高亮 + ZIP 下载

## 五、P2 —— 亮点加分（Design Mode / Issue 自修复已完成）

- **R13 画廊与 Remix**（公开画廊卡片 + 一键复制为新项目）：未做
- **R14 Design Mode 点选修改**（预览点选元素回填输入框）：已完成
- **R15 Issue 自修复**（预览错误捕获 → Resolve 自动修复）：已完成

## 六、平台增强（第二轮迭代，已全部完成并上线）

- **R16 同用户多设备实时同步**：`GET /events` 项目事件长连接——活跃生成重放+直播，空闲挂 hub 等 `sync` 通知；
  另一设备发起生成时，本设备自动拉取新消息并重连进入直播，全过程无需刷新
- **R17 生成并发池**：`BoundedSemaphore(MAX_CONCURRENT_GENERATIONS=3)` 控制全局并发生成数，超出的排队等待；
  `queue` 事件实时广播排队位次（页面顶部显示"排队中 · 第 N 位"），排队中可取消（Stop 立即退出，不产生改动）；15 分钟排队超时兜底
- **R18 project_id 雪花算法**：53 位（42 位毫秒时间戳 + 5 位机器 + 6 位序列），JS Number 精度安全（<2^53），
  API JSON 直传 int 无需字符串化；`MACHINE_ID` 环境变量多实例错开；SQLite INTEGER 亲和性天然兼容存量小 id，无需数据迁移
- **R19 分享二维码**：开启分享后弹层展示二维码（`qrcode` 包前端生成 dataURL，白底保证扫码对比度）+ 链接 + 复制按钮；扫码免登录查看
- **R20 Stop 提速**：取消检查点下沉到 engineer 流循环 chunk 级（此前在 on_step/on_files 回调，消息流密集处延迟≈一个 token）
- **R21 LLM 请求优化（前缀缓存 + 上下文压缩）**（第三轮迭代）：
  - *前缀缓存*：Anthropic 端点给请求尾块打缓存断点——system prompt + 工具定义 + 已累积对话整体进入服务端前缀缓存（KV Cache）；deepagents 工具循环每步重传全量历史，命中缓存降低 input token 与首 token 延迟（`LLM_PROMPT_CACHE=0` 可关，实测智谱兼容端点接受该标记）；OpenAI 兼容端点由服务端自动命中前缀缓存。
    实现注意：不能直接 `model.bind(cache_control=…)` 交给 deepagents——其 `resolve_model` 只认 `BaseChatModel`，bind 产物会被误当 `"provider:model"` 字符串解析（`partition` AttributeError，第二轮上线即此坑）。正确做法是子类化 `ChatAnthropic` 覆写 `bind_tools`，在工具绑定产物上链式附加 `cache_control`（kwargs 随调用透传到请求组装层，机制与官方 bind 用法一致，且对 deepagents 仍是真正的 `BaseChatModel`）
  - *上下文压缩*：对话历史以 KB 级摘要注入（首条原始需求 + 最近两轮，单条截断）；文件集总量超 `MAX_CONTEXT_CHARS`（默认 60k 字符）时自动压缩——入口 index.html 全量保留、其余文件保留头部并标注省略（明确告知截断文件无需重写）
- **R22 UI 打磨与帮助**（第三轮迭代）：首页「三步上手」引导卡 + 「真实生成案例」展示区（引用 `client/public/screenshots/` 真实运行截图，README 同源引用）；全局入场动画（消息卡/首页 stagger/分享弹层 pop 过渡），`prefers-reduced-motion` 豁免
- **R23 多端/多项目运行态隔离**（第四轮迭代，修复多端同步引入的状态串扰）：运行态（generating/stopping/queuePosition）属项目级而非页面级全局态，六个隔离点：
  1. `loadProject` 切项目即重置运行态（旧项目的生成/停止/排队标志不带进新项目）
  2. `chatSSE` 支持 `AbortSignal`；`closeWatch` 切项目时中断本地 chat 消费（后端生成继续，切回经 `/events` 重连直播）
  3. `sendPrompt` 全回调链绑定发起时的 `pid` 与 `AbortController`：切项目/中断后旧流事件不再写入新项目状态（跨项目泄漏）
  4. 直播中 `pullDetail` 全量拉取被拒（不覆盖 pending run 本地卡）；`sync(chat_start)` 观看端拉消息后重连进直播，但发起端豁免（本端 chat 流就是数据源，重连会渲染第二张 run 卡并重复步骤）
  5. 队列续跑只在发起端（chat 流所在页面）进行；观看端收尾不续跑（多端各自续跑会双发）
  6. `stop()` 加 10s 超时兜底（stopped 事件丢失时解除"停止中"卡死，提示后自动恢复）
- **R24 首页平台能力功能区**（第五轮迭代）：首页底部新增「平台能力」区块——十二项核心功能点卡片（3 列网格、同行 stretch 等高），每项含 emoji 图标 + 标题 + 一句话实现方案（智能体生成 / 流式直播 / 增量迭代 / 队列与 Stop / 多设备同步 / 多端运行态隔离 / 快照回滚 / Issue 自修复 / Design Mode / 分享二维码 / 代码导出 / 主题切换），内容与 README 完成度清单同源；首页结构变为 Hero → 三步上手 → 真实生成案例 → 平台能力，入场沿用 stagger 动画

## 七、部署方案（P0 交付的一部分）

1. **Dockerfile（多阶段）**：`node:20` 构建 `client/dist` → `python:3.12-slim` 安装依赖、复制 dist，FastAPI `StaticFiles` 托管前端 + API 同端口
2. **Railway（首选）/Render**：挂持久卷 `/data`，env：`DATABASE_URL=sqlite:////data/app.db`、`LLM_*`
3. **本地开发**：`uvicorn --reload` + `vite dev`（proxy `/api`→8000）
4. 交付：在线链接（笔试硬性）+ GitHub public 仓库 + README（思路/取舍/完成度/扩展规划）

## 非目标

外部 Connectors、增长模块、计费体系、自定义域名、多文件工程构建、移动 App 分发、登录体系（P2）

## 验收基线

| 验收基线（笔试要求） | 对应 |
|---|---|
| 真实交互 | R1-R4、R8、R16-R20、R23 |
| 数据持久化 | R5、R7 |
| 基本使用流程 | R1、R5、R7 |
| 至少一个延展能力 | P1 R9-R12（四项全做）+ P2 R14/R15 + 平台增强 R16-R20 |
