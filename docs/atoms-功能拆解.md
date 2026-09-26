# Atoms（atoms.dev）产品功能拆解

> 调研来源：atoms.dev 官网首页体验 + 帮助中心 help.atoms.dev/en 全量文档 + 浏览器实际探索（首页/登录/定价/Discover/Templates）
> 调研日期：2026-09-26
> 用途：笔试需求"实现类 Atoms 的 AI Agent 应用生成 Demo"的产品参考

---

## 1. 产品定位

**一句话**：一个多智能体（Agent Team）驱动的全栈应用构建平台——用户用自然语言描述想要的结果，AI 团队完成调研、规划、构建、测试与增长，最终产出可发布上线的网站/Web 应用。

- 核心工作流（官方 Quick Start 总结）：**Describe → Check → Change → Test → Publish → Verify → Update**
- 目标用户：无需编程经验的创作者（建站、Landing Page、仪表盘、内部工具、原型）
- 官网 Hero 定位："AI 团队，帮助你更快构建并赢得客户"（A full AI team that helps you launch faster at a lower cost）

## 2. 多智能体团队（产品最大特色）

8 个具名 agent 角色，各司其职：

| Agent | 角色 | 职责 |
|---|---|---|
| **Mike** | Team Leader | 读取用户请求 → 拆成具体 brief → @分派给专家 → 协调全程 → 向用户请求批准 |
| **Alex** | Engineer | 构建生产级全栈应用：前端、后端、集成、部署 |
| **Emma** | Product Manager | 把想法变成清晰的 spec 与 scope |
| **Bob** | Architect | 设计系统蓝图与技术选型，保证可扩展、可靠 |
| **Iris** | Deep Researcher | 深度调研，发现真实需求与细分市场机会 |
| **David** | Data Analyst | 数据分析，发现增长机会与洞察 |
| **Sarah** | SEO Specialist | 快速生成 SEO 页面并自动化优化 |
| **Adrian** | Ads Specialist | 自动创建/追踪/优化 Google Ads 广告 |

**协作机制（关键体验点）**：
- 用户发需求 → Mike 发布 activity card（"Processed N steps"，可展开看逐步叙述）→ Mike 写出详细 brief（章节、约束、质量规则）→ @mention 分派专家 → 专家接受 handoff → 干活
- 每条 agent 消息带 **身份标签**（Mike | Team Leader、Alex | Engineer），多智能体工作一目了然
- **工具卡片（Tool Cards）**：读文件、写代码、跑终端命令、生成图片、审查渲染页面等具体动作可视化
- 完成时消息末尾附 **Version 卡片**（如 "Version 1: Launch publishing hero"），每个里程碑可追溯

## 3. 功能模块逐一拆解

### 3.1 首页 / 仪表盘（Dashboard）

- **中央大 prompt 输入框**：最快的开工方式；`+` 附加文件/文件夹/图片/设计稿；Web / App 项目类型切换
- 左侧栏：Workspace 切换、Home、Resources、My Projects、**Discover**、**Templates**、Connect tools
- 右上角：**Credits 余额**展示
- 项目归属 workspace，支持多工作区（每个工作区有独立项目与共享资源）
- 底部：社区入口、免费 credits 卡片、账号/设置/通知

### 3.2 对话式构建（Project Chat）★ 核心中的核心

- **自然语言启动任务**：只描述结果，不写技术规格（例："Create me a landing page to promote my medical equipment"）
- **多 agent 协作可视化**：brief 全文可见、handoff 全程在用户眼前
- **追加式修改**：follow-up 消息在现有基础上迭代（例："I need the theme to be green" → 产出 Version 2，其他保持不变）
- **消息队列**：agent 工作中发消息不中断，排队执行；排队中可编辑 / 删除 / 调整顺序
- **中断与续跑**：Stop 后已完成部分保留；补充遗漏信息重新提交，从当前状态继续而非从零重建
- **消息级操作**：
  - Revert（回滚到该消息改动前的状态，先确认目标版本）
  - Copy、Helpful/Not helpful 反馈、Feedback（直通支持团队）
  - Activity card 展开收起、Version card
- **云端后台运行**：关浏览器任务可继续，回来查状态
- **Issue Report（自修复）**：出错时左下角弹出通知 → 描述错误 + **Resolve** 按钮（AI 自行分析修复）+ 展开看完整错误日志/stack trace/系统信息
- **知识问答**：chat 里可直接问"为什么这样实现"、"刚改了什么"

### 3.3 预览与可视化编辑（App Viewer + Design Mode）

- **App Viewer**：编辑器内实时预览当前项目状态，无需离开 Atoms
- **PC / 移动双端预览切换**（平板尺寸：新标签页打开拉窗口）
- **Reload App Viewer** / 新标签页打开
- **Design Mode**：直接**点选 UI 元素**做可视化修改，agent 只改该元素（解决"改不准"问题）
- **Console / Terminal 错误面板**
- 支持上传截图/设计稿/文件作为修改参考（期望 vs 实际对比图）

### 3.4 发布与部署（Publish）

- **Publish** → 生成 `[name].pub.atoms.world` 公网 URL（名称 6–30 字符，小写字母/数字/连字符，可改名）
- 发布前官方建议：App Viewer 以访客身份走查主流程、双端布局、移除密码/API key/测试数据
- **Security scan**：发布前自动安全扫描 → Security checked / 发现问题可 **Resolve All** 或理解风险后 **Publish Anyway**
- **Update**：编辑后手动推送线上版本（编辑器里的 App Viewer ≠ 线上版本）
- **自定义域名**：首次发布后开放（Add your domain）
- **Atoms Cloud 项目专属**：
  - Migrate existing data（数据迁移开关）+ View database
  - App Status：Live / Paused（暂停可访问，计费继续）/ Unpublished
- **Unpublish** 下线（可再次发布）
- **Remove Atoms™ Badge**（Pro 权益）
- Cloud Balance 不足时提示 Top up（**Cloud 钱包与订阅 credits 是两套钱**：前者付托管/部署，后者付 agent 对话）

### 3.5 分享 / Remix / 导出（Collaborate）

- **Share 面板**：
  - **Public**：可通过链接访问 + 出现在 Discover
  - **Private**：仅自己可见（改 Private 需 Pro）
  - Copy link（官方建议无痕窗口验证）
- **App Card**：封面、名称、描述、版本（Discover 里的展示卡）
- **Remix a project**：把别人（或自己历史版本）的项目 fork 一份继续改
- **Export**：下载 ZIP（代码 + 资产，Pro 权益）
- **权限体系**：owner / editor 角色，Workspace settings 管理协作权限

### 3.6 集成连接器（Connectors）

- 入口：Settings → Connectors，或 Dashboard 的 "Connect your tools to Atoms"
- **三类用途**：
  1. 构建时给 agent 提供上下文（读文件、总结任务、引用项目数据）
  2. 让 agent 在外部服务执行动作（建任务、改记录、写表格、建日程）
  3. 给已发布应用增加能力（数据存储、认证、支付）
- **连接器目录**（按用途分类）：
  - 开发：GitHub、Linear
  - 后端与数据：Supabase
  - 支付：Stripe
  - 工作管理：Asana、Todoist
  - 文件与内容：Box、Dropbox
  - 分析与营销：GA4、Google Search Console、Google Ads
- OAuth 授权流、权限范围审查、**写外部数据前需 Confirm 确认**、断开/重连管理
- 在 Chat 中通过 **connector picker** 按会话启用

### 3.7 增长与优化（Grow & Optimize，Pro 权益）

- 项目内 **Marketing 模块**：
  - **Analytics**（默认 tab）：GA4 数据报表——Active Users & Sessions 柱状图、Top Referrers、Top Regions、Top Browsers、Device Categories、Top Pages 六大块；7/30 天切换
  - **SEO**：Performance、Operations 两个 tab；SEO Agent 自动化
  - **Ads**：Google Ads 管理；Ads Agent
- **AI Fix**：自动修复 GA4 tracking code 问题（agent 改项目 → 需重新发布生效）
- Check Status 手动重查
- 限制：移动端项目无 Marketing；Free 只能连不能看报表

### 3.8 账号、工作区与计费

- **登录方式**：Google 登录 / 邮箱
- **定价体系**（官网 + 帮助中心）：

| 档位 | 价格 | 积分 | 存储 | 差异化权益 |
|---|---|---|---|---|
| Free | $0 | 每日免费额度（账户而异） | 2GB | 2 个后端项目 |
| Pro 100 | $20/月 | 100/月 | 10GB | 私有项目、代码编辑/下载、去徽标 |
| Pro 250/350 | $50/$70 | 250/350 | 10GB | 同上 |
| Max 500+ | $100–$2000/月 | 500–10000/月 | 100GB | 扩展算力、**Race Mode**（竞赛模式） |

- **credits 消耗顺序**：每日免费 → plan credits → bonus credits
- 月度升级 credits 可 rollover 一次（下月有效）；降级清零；bonus 不过期
- **Settings 结构**：账号、Workspace（成员/权限/Connectors）、Plans & credits（Plan/Payment）、Cloud & AI（用量/交易/余额/告警/消费限额）
- 存储/额度不足会阻塞发布

### 3.9 社区与模板（Discover / Templates / App World）

- **Discover**：公开项目流；卡片含标题、作者、使用次数；分类筛选（全部、Claude Fable 5、E-commerce 等）+ 排序；可直接打开项目预览
- **Templates**：模板分类导航 + 模板卡片（封面图/标题/描述），从既有结构起步而非空白 prompt
- **App World**：找接近需求的项目 Remix
- 社区支持：Discord、Help Center（Ask AI assistant）、付费用户 Support 工单

### 3.10 移动端项目

- 移动项目走**独立的构建与分发流程**（区别于 web 项目）
- 不支持 Marketing 模块

## 4. 关键用户旅程（端到端）

```
注册登录（Google/邮箱）
   ↓
Dashboard 中央 prompt 输入需求（可附图/文件，选 Web/App）
   ↓
Mike 解析 → 生成 brief → 分派 Alex → activity/tool 卡片直播过程
   ↓
Version 1 交付（附总结与验证说明）
   ↓
App Viewer 预览（PC/移动）→ Design Mode 点选微调 / chat 追加修改
   ↓
迭代循环：消息队列 / 中断续跑 / Revert 回滚
   ↓
出错 → Issue Report → Resolve 自修复
   ↓
Publish（安全扫描）→ [name].pub.atoms.world 上线
   ↓
Share（Public/Private）/ Remix / Export ZIP / 自定义域名
   ↓
增长：连 GA4 / SEO / Ads → Marketing 模块看数据 → Update 持续迭代
```

## 5. 对笔试 Demo 的借鉴映射（优先级建议）

### 必做（对齐"核心主流程"要求）
| Atoms 功能 | Demo 对应实现 |
|---|---|
| 中央 prompt 输入 | 首页大输入框 + 附件入口（可简化） |
| Project Chat 多轮生成 | 对话式构建 + 流式输出 |
| Activity card / Tool cards | 生成过程可视化（"规划→写代码→修复"步骤直播）——此类产品体验的灵魂 |
| App Viewer 双端预览 | iframe sandbox 实时预览 + PC/移动切换 |
| follow-up 迭代修改 | 在已有代码上增量改，而非重生成 |
| Version card + Revert | 版本快照与回滚 |
| Issue Report + Resolve | 生成失败的自修复提示 |
| 注册/登录 + 项目持久化 | 账号体系 + 项目/会话/代码存储 |

### 加分项（对齐"延展能力 + 创新性"）
- 多 agent 角色分工展示（Team Leader / Engineer 分工，贴合 Atoms 主题）
- Design Mode 式点选元素修改
- Discover / Templates 画廊 + Remix fork
- 一键 Publish 分享链接
- Export ZIP 代码下载

### 可砍（复杂度高、非评分重点）
- 外部 Connectors（GitHub/Supabase/Stripe）
- GA4/SEO/Ads 增长模块
- 完整计费/credits 体系、自定义域名、Atoms Cloud 数据迁移

---

## 附：信息来源

- 官网首页：https://atoms.dev/ （agent 团队介绍、Hero 文案）
- 帮助中心：https://help.atoms.dev/en
  - Welcome to Atoms / Quick Start / Dashboard Overview
  - Project Chat（消息操作、队列、中断续跑、Issue Report）
  - Integrations（连接器目录与授权流）
  - Share a project / Remix / Publish your project（发布、安全扫描、域名、App Status）
  - Analytics Overview / Plans and credits（定价与 credits 机制）
- 浏览器实测：首页、登录页（Google/邮箱）、定价页、Discover、Templates
