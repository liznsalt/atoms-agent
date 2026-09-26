# Tasks — implement-atoms-demo

> P0（最小闭环+部署）→ P1（延展，至少 1 个）→ P2。选型与交互契约见 spec.md。

## P0 任务

- [x] **Task 1: 脚手架**
  - [x] 1.1 `client/`：Vue 3 + Vite + TS + Pinia + Vue Router + TailwindCSS；`server/`：FastAPI + uvicorn（Python 3.13）；`.env.example`（DATABASE_URL / LLM_BASE_URL / LLM_API_KEY / LLM_MODEL）
  - [x] 1.2 开发约定：vite proxy `/api` 与 `/preview` → 8000；目录骨架（server/app: api/ agents/ db/ preview/）
- [x] **Task 2: 数据库与模型**
  - [x] 2.1 SQLAlchemy 模型：Project / Message（含步骤 JSON）/ FileState（当前文件 JSON），`DATABASE_URL` 驱动连接，`create_all` 起步
  - [x] 2.2 薄查询层（get/create/update/delete），单测验证切换 PostgreSQL 仅改连接串（跑 typecheck/import）
- [x] **Task 3: deepagents 智能体**
  - [x] 3.1 Engineer Agent（deepagents）：system prompt（生成自包含 Web 应用：HTML/CSS/JS，Tailwind CDN 可用）+ `save_file(filename, content)` 工具（落库 + 记录步骤）
  - [x] 3.2 LangChain OpenAI-compatible 模型封装（env 驱动），失败分类（超时/限流/内容异常）
  - [x] 3.3 follow-up 上下文注入：当前文件集 + 历史摘要拼入 prompt（增量修改）
  - [x] 3.4 流事件映射：deepagents stream（todo 更新/工具调用/消息）→ `step`/`files`/`done` 事件
- [x] **Task 4: REST API + 预览组装**
  - [x] 4.1 路由：`POST/GET/DELETE /api/projects`、`GET /api/projects/{id}`（消息+文件，刷新恢复）
  - [x] 4.2 `POST /api/projects/{id}/chat`：sse-starlette 流式（step/files/done/error），完成落库总结消息
  - [x] 4.3 `GET /preview/{id}`：文件 → 自包含 HTML 组装（相对路径内联），iframe 可加载
- [x] **Task 5: 前端首页 + 项目列表**
  - [x] 5.1 首页：Hero + 大输入框 → `POST /api/projects` → 跳转 `/project/:id`
  - [x] 5.2 项目列表：卡片（标题/时间）、打开、删除
- [x] **Task 6: 工作台（Chat + Preview）**
  - [x] 6.1 Chat 面板：历史消息恢复；fetch ReadableStream 消费 SSE；步骤卡片流式渲染；错误卡片 + 重试按钮
  - [x] 6.2 Preview 面板：iframe sandbox 加载 `/preview/{id}`；`files` 事件自动刷新；手动刷新按钮
- [ ] **Task 7: 部署交付**（方案已改火山引擎 veFaaS）
  - [x] 7.0 本地部署：uvicorn 同端口托管 Vue dist（SPA history fallback 修复），本地浏览器全流程验证通过
  - [x] 7.1 veFaaS 部署：App atoms-agent + 网关 atoms-demo，env 注入（LLM anthropic + DATABASE_URL=/tmp/app.db + AUTH_SECRET）；在线 health/注册/登录/SSE 流式生成实测全通（注意：实例内 SQLite，实例回收后数据重置）；第二轮五项增强（R16-R20）重新部署上线，线上 health + 新前端 hash 验证通过
  - [ ] 7.2 GitHub public 仓库 + README（README 已就绪含在线链接，仓库待推送）
- [x] **Task 8: P0 E2E 验证**
  - [x] 8.1 手动全流程：创建 → 生成（过程可视）→ 预览交互 → 迭代 → 刷新恢复 → 重试路径（真实 LLM 实测全过）
  - [x] 8.2 换 2 个不同类型需求验证 prompt 健壮性（番茄钟计时工具 + 贪吃蛇游戏，Chrome DevTools 实测交互真实可用）；线上链接复验待部署后补

- [x] **Task 13: 注册/登录与多用户隔离（用户提级 P0）**
  - [x] 13.1 User 模型（email 唯一 + pbkdf2 密码哈希，stdlib 零新依赖）+ projects.owner_id 迁移
  - [x] 13.2 HMAC 签名 Cookie 会话（HttpOnly）+ /api/auth/register|login|logout|me
  - [x] 13.3 全部项目 API 鉴权过滤（owner 或 NULL 演示项目可读写；跨用户 404）；preview/share 访客免登录
  - [x] 13.4 前端 /login 页（登录/注册切换）+ 路由守卫 + 顶栏用户态/退出（C7.1-C7.6 全过；修复自动填充 422 bug）
- [x] **Task 14: 消息队列与 Stop（用户提级 P0）**
  - [x] 14.1 后端协作式取消：每项目 cancel 标志，step/files 回调检测抛中断；已写文件落库保留进度 + 「⏹ 已停止」消息 + stopped 事件
  - [x] 14.2 POST /api/projects/{id}/stop
  - [x] 14.3 前端队列：生成中发送入队（可删）、done/error/stopped 后自动发下一条、Stop 按钮
  - [x] 14.4 浏览器 E2E：双用户隔离 + 队列连发 + Stop 保留进度（C8.1-C8.5 全过：入队/自动接续/停止保留进度/队列继续）

## P1 任务（延展，按序做，至少 1 个）

- [x] **Task 9: 版本快照与回滚**：生成完成自动存 Version；版本时间线 UI + 一键回滚（文件+预览恢复）（实测：迭代自动快照 v1/v2 → UI 回滚 v1 → 文件/预览恢复 + 系统消息 + 回滚动作落新快照 v3）
- [x] **Task 10: PC/移动视口切换**：预览容器宽度切换（375px 手机视口居中带描边）
- [x] **Task 11: 一键分享**：shareId + 开关；访客只读预览页（免登录可交互）；关闭后失效（share_id 复用；访客页 404 失效提示）
- [x] **Task 12: 代码查看与导出**：预览/代码视图切换（文件树 + 行号代码视图，纯 CSS 高亮路线）；ZIP 导出（内存打包 + 防路径穿越）

## P2 任务（亮点，仅画廊未做）

- [x] **Task 13: 注册/登录**：见上方 P0 Task 13（用户提级）
- [ ] **Task 14: 画廊与 Remix**：公开画廊卡片 + 一键复制为新项目（未做）
- [x] **Task 15: Design Mode 点选**：预览内点选元素回填修改输入框（C11.2 实测通过）
- [x] **Task 16: 消息队列与 Stop**：见上方 P0 Task 14（用户提级）
- [x] **Task 17: Issue 自修复**：预览错误捕获 → Issue 卡片 → Resolve 自动修复（C11.1 实测通过）

## 第二轮平台增强（用户反馈驱动，R16-R20，已全部完成并上线）

- [x] **Task 18: 多设备实时同步 + 并发池 + 雪花 ID + 分享二维码 + Stop 提速**
  - [x] 18.1 后端事件总线重构：`_runs` 活跃生成 ctx + `_hubs` 空闲订阅 hub；`_notify_project` 广播 sync(chat_start/gen_end/rollback/share)；GET /events 长连接生命周期（直播→空闲挂 hub，sse-starlette ping 保活）
  - [x] 18.2 生成并发池：`BoundedSemaphore(MAX_CONCURRENT_GENERATIONS=3)` + 排队位次 queue 事件广播 + 排队可取消（5s 轮询检查 cancel）+ 15min 超时兜底
  - [x] 18.3 engineer.py：GenerationStopped 移入 + `should_cancel` 参数，stream 循环逐 chunk 检查（Stop 延迟≈一个 token）
  - [x] 18.4 雪花 ID：`app/utils/snowflake.py`（42ms+5 机器+6 序列 = 53 位，threading.Lock，同毫秒耗尽自旋）；models.py Project.id → BigInteger + default（存量小 id 兼容）
  - [x] 18.5 前端 watchProject 常驻长连接循环：sync(chat_start)→拉消息+断开重连进直播；sync(其他)→拉详情合并；断线退避重连；closeWatch（切项目/unmount 断连）
  - [x] 18.6 排队 UI：顶部"排队中 · 第 N 位"徽章 + Stop 按钮变"取消排队"
  - [x] 18.7 分享二维码：`qrcode` 包生成 dataURL + 弹层（白底二维码/链接/复制按钮），扫码免登录查看
  - [x] 18.8 构建部署 + 浏览器实测（C12.1-C12.5 全过）+ vefaas 上线验证

## 第三轮迭代（LLM 优化 + UI 打磨，R21-R22，已上线）

- [x] **Task 19: LLM 请求优化 + UI 打磨**
  - [x] 19.1 前缀缓存：ChatAnthropic 前缀缓存断点（请求尾块缓存全前缀）；`LLM_PROMPT_CACHE` 开关；实测智谱 Anthropic 兼容端点接受标记、请求正常
    （第四轮修正：直接 `bind(cache_control)` 的产物会被 deepagents `resolve_model` 当字符串 spec 解析而崩溃（`partition` AttributeError）——改子类化覆写 `bind_tools` 链式附加，见 Task 20.7）
  - [x] 19.2 上下文压缩：`_recent_history`（首条需求 + 最近两轮，user 200/agent 400 字符截断）+ `_render_files` 超限裁剪（`MAX_CONTEXT_CHARS=60000`，index.html 全量、其余头部 1500 字符 + 省略标注）；函数级验证 200k 字符文件集 → 1.8k 渲染
  - [x] 19.3 首页「三步上手」引导 + 「真实生成案例」区（截图存 client/public/screenshots，构建进 dist，README 同源引用）
  - [x] 19.4 全局动画基建：`animate-rise` 入场 / `pop` 弹层过渡 / `prefers-reduced-motion` 豁免；首页 hero stagger、消息卡入场、分享弹层过渡
  - [x] 19.5 系统截图入仓（home/workspace/code/share 四张真实运行截图）+ README 截图区 + 部署上线验证（线上 /screenshots/workspace.png 200）

## 第四轮迭代（多端运行态隔离 + 前缀缓存链路修复，R23）

- [x] **Task 20: 运行态独立（多端/多项目互不干扰）+ partition 崩溃修复**
  - [x] 20.1 `chatSSE` 增加 `AbortSignal` 参数（中断本地消费，后端生成不受影响）
  - [x] 20.2 `loadProject` 切项目重置运行态（generating/stopping/queuePosition 不跨项目残留）
  - [x] 20.3 `closeWatch` 同时中断本地 chat 消费（`activeChat.abort()`）
  - [x] 20.4 `sendPrompt` 回调链绑定发起时 pid + AbortController（跨项目事件泄漏防护）；主动中断静默退出
  - [x] 20.5 直播中 `pullDetail` 拒绝全量覆盖（保 pending run 卡）；观看端收尾不续跑队列；发起端 `sync(chat_start)` 豁免重连（防双 run 卡/步骤重复）
  - [x] 20.6 `stop()` 10s 超时兜底（stopped 丢失自动解除"停止中"）
  - [x] 20.7 前缀缓存链路修复：`bind(cache_control)` 产物使 deepagents `resolve_model` 崩溃（'ChatAnthropic' object has no attribute 'partition'）→ 改子类化 `ChatAnthropic` 覆写 `bind_tools` 链式附加 cache_control；冒烟验证构造/流式/请求发出 OK（端点 429 限流为额度问题，非代码问题）
  - [ ] 20.8 构建部署 + 多端实测（C14）+ spec/README 同步

# Task Dependencies

- Task 2/3 依赖 Task 1；Task 4 依赖 2/3；Task 5/6 依赖 4；Task 7 可与 5/6 并行（先出镜像骨架）
- Task 8 是 P0 验收闸门，依赖 1-7
- Task 9-12（P1）相互独立，依赖 Task 8 通过；优先级 9 > 10 > 11 > 12
- Task 13-17（P2）独立，按剩余时间挑亮点
