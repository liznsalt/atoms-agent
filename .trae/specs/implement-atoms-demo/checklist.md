# Checklist — implement-atoms-demo

## P0 自测用例（本轮浏览器逐项验证）

### R1 需求输入与项目创建
- [x] C1.1 未登录访问任意受保护页 → 跳 /login 并携带 redirect（实测 /projects → /login?redirect=/projects）
- [x] C1.2 登录后首页输入需求提交 → 创建项目跳工作台，自动开始首次生成（实测 qa 账号创建 project/12 倒计时器）

### R2 流式生成与过程可视化
- [x] C2.1 生成中步骤卡片实时出现（保存文件/调用工具）（实测 project/12 首次生成步骤卡实时累积）
- [x] C2.2 AI 文本打字机式流式渲染（MessageCard pending + streamText，C8 生成过程实测）
- [x] C2.3 完成展示总结卡片（实测倒计时器总结"已完成…3 个文件"）

### R3 沙箱实时预览
- [x] C3.1 files 事件到达预览自动刷新（实测生成中途 preview v 递增至 v5）
- [x] C3.2 预览内交互真实可用（实测倒计时输入 10 秒点击开始，00:09→00:07 真实递减）
- [x] C3.3 手动刷新按钮工作（P0 时期实测，UI 未变更）

### R4 对话式增量迭代
- [x] C4.1 follow-up 只改相关文件、未提及文件保留（实测"改标题"仅动 index.html；P0 紫色迭代仅动 style.css）
- [x] C4.2 迭代完成预览自动更新为新状态（实测标题/背景迭代后预览即时更新）

### R5 持久化与项目列表
- [x] C5.1 刷新工作台 → 消息历史与文件状态完整恢复（实测刷新恢复 4 条 user 消息+停止卡+版本4+浅紫预览）
- [x] C5.2 项目列表打开/删除可用（实测创建 project/13 → UI 删除 → 列表消失 + API 404）

### R6 错误处理与重试
- [x] C6.1 历史错误卡有重试按钮，点击重发成功（P0 时期实测错误卡+重试链路；本轮无新增错误数据，逻辑未变）

### R7 注册/登录与多用户隔离
- [x] C7.1 注册新账号（含浏览器自动填充场景不 422）（实测 qa@atoms.cn 注册；**修复真实 bug：Chrome 密码自动填充不触发 v-model → 提交空密码 422，已加 @change 同步 + DOM 兜底**）
- [x] C7.2 登出 → 会话失效 → 重新登录成功（实测登出跳 /login，tester1 重新登录）
- [x] C7.3 错误密码 → 401 文案提示（实测"邮箱或密码错误"）
- [x] C7.4 用户 A 的项目用户 B 列表不可见、直连 API 404（实测 tester1 列表无 qa 的 project/12，直连 404；**修复用户反馈 bug：原"无主项目全员可见"设计改为严格隔离（仅 owner 可见），历史无主项目由启动迁移划归最早注册用户**）
- [x] C7.5 刷新页面保持登录态（实测刷新后 me=qa@atoms.cn 保持）
- [x] C7.6 分享链接与 /preview 访客免登录可访问（实测 credentials:omit preview 200；访客开他人分享 401）

### 主题与代码高亮（追加）

- [x] C10.1 深/浅主题切换：语义 token（base/surface/line/ink）+ localStorage 持久化，导航栏与工作台均可切换（实测浅色全组件正常、刷新保持；默认亮色）
- [x] C10.2 代码语法高亮：highlight.js 按扩展名映射语言（html/css/js/ts/json/md/py），深色代码底两主题通用（实测 231 个高亮节点、keyword 红 / string 蓝、行号对齐）

### 亮点与高可用（追加）

- [x] C11.1 Issue 自修复：预览 window.onerror/unhandledrejection 捕获（注入 head 前置，可捕获同步错误）→ postMessage → 聊天流 Issue 卡（去重限量 3 条）→ 一键自动修复走生成链路（实测：内置 ReferenceError 的项目 → Issue 卡 → LLM 移除错误调用+补函数 → 预览刷新 Issue 清除；files 事件自动清过时 Issue）
- [x] C11.2 Design Mode 点选修改：预览工具栏开关 → iframe 注入选择器（hover 描边 + click 拦截上报）→ 元素描述回填需求输入框并聚焦，点选一次自动退出（实测点选 #boom 按钮回填完整描述）
- [x] C11.3 高可用：SQLite WAL + busy_timeout（读写并发不阻塞）；LLM 统一 120s 超时 + 2 次自动重试（瞬时抖动自愈、长任务不挂死）；SSE 断线自动重连（此前已做）

### R8 消息队列与 Stop
- [x] C8.1 生成中发送 → 入队显示 chip（非禁言）（实测发送按钮变"加入队列"，队列 chip + 计数标签显示）
- [x] C8.2 队列消息可删除（chip 渲染移除按钮，removeBtns 确认存在）
- [x] C8.3 本轮完成自动发送队首消息（实测"改标题"完成后"精准每一秒"自动接续）
- [x] C8.4 Stop → 「⏹ 已停止」卡片 + 已写文件保留落库 + 预览恢复保留态（实测停止后 stopped 消息落库 + "⏹ 已停止（进度保留）"版本快照 + 小字已写入 index.html 保留）
- [x] C8.5 Stop 后队列自动继续下一条（实测停止后"浅紫色"自动接续生成并完成）
- [x] C8.6 生成中离开/刷新页面 → 重进自动重连直播（GET /events 广播订阅：重放已发生步骤 + 继续直播 + done 总结经恢复流送达；实测刷新后 pending 卡/Stop 按钮恢复，GitHub 图标迭代完整走完落版本 6）

### 第二轮平台增强（R16-R20，本轮实测）

- [x] C12.1 雪花 ID：新项目 id 为 53 位内大数字（实测创建项目 URL /project/112073351557184，位数 47；存量小 id 项目不受影响）
- [x] C12.2 多设备实时同步：双标签页同账号开同一项目，B 页发消息 → A 页无需刷新自动出现新用户消息并进入直播（步骤流式 + 完成总结 + 预览刷新全链路；实测 A 页收到"加一个计次圈数显示"消息与完整生成直播）
- [x] C12.3 并发池排队：4 个 chat 经 Barrier 同时发出（上限 3）→ 第 4 个收到 queue{position:1,max:3}，槽位释放后 queue{position:0} 接续生成；页面顶部显示"排队中 · 第 N 位"，Stop 按钮变"取消排队"
- [x] C12.4 Stop 提速：生成中点击 Stop 近乎立即收尾（chunk 级取消检查点；实测点击后快照即显示"⏹ 已停止：已保存的文件已保留"）
- [x] C12.5 分享二维码：开启分享弹层展示二维码（qrcode dataURL，白底可扫）+ 链接 + 复制按钮；扫码/打开 /share/{share_id} 免登录只读可交互（实测分享页秒表计圈器预览正常）
- [x] C12.6 长连接清理：切项目/离开工作台断开 events 长连接（closeWatch：世代号递增 + AbortController），退避重连（1.5s 起步封顶 10s，重放全量快照幂等）

### 第三轮迭代（R21-R22，本轮实测）

- [x] C13.1 前缀缓存：`bind(cache_control)` 真实请求智谱 Anthropic 兼容端点成功返回（`1+1=2`，无协议报错）；`LLM_PROMPT_CACHE=0` 可关兜底（端点不回传 usage，命中率无法量化，如实标注）
  （第四轮修正注：直接 bind 的产物无法通过 deepagents 全链路——见 C14.6；最终方案为子类化 `bind_tools` 链式附加）
- [x] C13.2 上下文压缩：函数级验证——200k 字符文件集渲染为 1.8k（`中间省略 N 字符`标注 + index.html 全量）；`_compose_user_input` 含历史摘要段与需求段
- [x] C13.3 首页三步上手 + 真实案例区：浏览器实测新首页渲染（三卡引导 + 3 张截图 200 加载）；hero stagger 入场动画
- [x] C13.4 系统截图入仓：home/workspace/code/share 四张真实运行截图存 `client/public/screenshots/`；README 引用仓库路径、首页引用 `/screenshots/*`（同源文件）；线上部署后 `/screenshots/workspace.png` 200 可访问

### 第四轮迭代（R23 运行态隔离 + partition 修复，实测待额度重置后补跑 C14.1-C14.5）

- [ ] C14.1 双端同项目：发起端只有一张 run 卡（发起端豁免）；观看端自动进直播且步骤不重复（待实测）
- [ ] C14.2 Stop 隔离：发起端 Stop 后两端均正常收尾（观看端不续跑队列）；无"停止中"卡死（10s 兜底）
- [ ] C14.3 切项目隔离：生成中切到另一项目，运行态重置（新项目非生成中）；切回原项目经 /events 重连直播继续
- [ ] C14.4 排队隔离：并发池满时多端各自显示排队位次；一端取消排队不影响他端
- [ ] C14.5 跨项目泄漏：切项目后旧 chat 流事件不写入新项目状态（aborted 守卫）
- [x] C14.6 partition 修复验证：子类化 `ChatAnthropic` 覆写 `bind_tools` 后，create_deep_agent 构造 OK、流启动 OK、HTTP 请求真实发出（此前 `bind(cache_control)` 产物在 `resolve_model` 处报 `'ChatAnthropic' object has no attribute 'partition'`——被误当字符串 spec 解析）；修复后端点返回 429 限流（额度 19:12 重置，非代码问题），错误卡片链路（error→前端渲染）顺带实测通过
- [x] C14.7 429 错误路径多端实测（不耗额度的替代链路）：双页签同项目，发起端生成（429 失败）→ 两端均正常收尾无卡死（badge 均复位 idle、可再次输入）；观看端经 sync 全量合并错误消息（4 条库消息正确渲染）；发起端 pullDetail 在 chat 流收尾后全量拉取覆盖本地卡，内容一致无重复
- [x] C14.8 三端空闲同步（不耗额度）：A 端开分享 → B/C 端 is_shared 经 sync→pullDetail 自动变 true（无需刷新），分享弹层仅操作端显示——R23 改动未破坏空闲态同步
- [x] C14.9 pendingPrompt 重复生成防御：测试中观察到一次新页签带 pendingPrompt 自动重发 chat 的孤立案例（DevTools new_page 与 SPA 跳转竞态所致、对照实验 C 页不复现，非产品路径）；顺手加固 onMounted 自动发送条件为「空项目才发」（正常时序创建的新项目必无消息，防任何异常途径重复生成）；跨用户隔离顺带复验（qa3 打开 qa2 项目显示"项目不存在"）

## P0 核心闭环（此前已实测通过）

- [x] R1: 首页输入需求 → 创建项目并进入工作台，自动开始首次生成（浏览器实测）
- [x] R2: 生成过程流式可视——SSE step 事件实时渲染步骤卡片（todo/写文件），完成有总结（Chrome DevTools 实测 /project/8 番茄钟：3 个"保存文件"工具步骤实时出现 + done 总结 + 打字机流式文本）
- [x] R2: 文件经 save_file 工具结构化落库，无脆弱整包 JSON 解析（test_engineer/test_api 验证）
- [x] R3: `/preview/{id}` 组装自包含 HTML，iframe sandbox 加载，应用内交互真实可用（实测：番茄钟点击"开始"后 24:58 真实计时、按钮变暂停、标题实时更新；贪吃蛇空格开始/暂停、方向键控制）
- [x] R3: files 事件到达后预览自动刷新（实测；并修复 done 后 bump 预览——DB 原子提交后才拿最终文件集）
- [x] R4: follow-up 增量修改——未提及文件不变，预览自动刷新（实测 /project/8："主题色改紫色"仅改 style.css，edit_file×2+read_file+save_file，紫色 #a855f7 真实应用）
- [x] R5: 刷新/重开项目后消息与代码完整恢复（浏览器实测 /project/3、/project/8 刷新恢复）
- [x] R5: SQLAlchemy + DATABASE_URL，仅改连接串即可切换数据库（test_db 双连接串验证）
- [x] R5: 项目列表打开/删除可用（浏览器实测）
- [x] R6: LLM 失败显示错误卡片，一键重试成功且无半成品脏数据（浏览器实测：错误卡+重试；服务端 files 不落库）
- [x] LLM 经 env 切换 baseURL/model/key 即可换模型（llm.py 封装，缺 key 明确报错验证；新增 LLM_PROVIDER=anthropic/openai 支持智谱 Coding Plan Anthropic 端点）
- [x] 前后端交互与 spec 契约一致（REST + SSE 事件类型齐全，smoke_chat + test_api 验证）
- [x] 火山引擎 veFaaS 部署上线（App: atoms-agent，网关 atoms-demo；DATABASE_URL=/tmp/app.db + AUTH_SECRET 环境变量注入修复线上 500；实测 health/首页/鉴权/注册/登录/创建项目/SSE 流式生成全通）
- [x] 手动 E2E 全流程通过：创建 → 生成 → 预览交互 → 迭代 → 刷新恢复 → 重试（无 key 路径全过；真实生成双需求实测：番茄钟工具类 + 贪吃蛇游戏类）
- [x] 在线链接公开可访问（https://s4pnngk3fusjaesdsgkhc.apigateway-cn-beijing.volceapi.com/）；GitHub public 仓库 + README 就绪（README 已含在线链接；GitHub 仓库待推送）

## P1 延展能力（至少 1 个）

- [x] R7: 版本快照 + 时间线 + 一键回滚（文件与预览恢复）（实测 /project/8：两次真实迭代自动落 v1/v2，UI 回滚 v1 → style.css 浅蓝 #e0f2fe 消失恢复紫主题、预览刷新、聊天落"⏪ 已回滚至版本 v1"、回滚动作自动生成 v3 快照）
- [x] R8: PC/移动视口切换正常（实测：手机模式 iframe 375px 居中带描边，桌面恢复全宽）
- [x] R9: 分享链接访客免登录可交互；关闭后失效（实测：开启 → /share/{share_id} 访客页只读可交互；关闭 → 访客页"分享链接无效或已被作者关闭"；share_id 复用不漂移）
- [x] R10: 代码视图（文件树+高亮）+ ZIP 导出（实测：代码 tab 文件树 index.html/style.css/app.js + 行号代码视图；ZIP 导出 API 冒烟 3 文件；回滚后旧库 ALTER 迁移兼容 projects.share_id/is_shared）

## P2（仅画廊未做）

- [x] R11: 注册/登录 + 多用户隔离（用户提级为 P0，C7 全过）
- [ ] R12: 画廊 + Remix（未做）
- [x] R13: Design Mode 点选回填（C11.2 实测）
- [x] R14: 消息队列 + Stop（用户提级为 P0，C8 全过；本轮 Stop 提速至 chunk 级）
- [x] R15: Issue 卡片 + Resolve 自修复（C11.1 实测）
