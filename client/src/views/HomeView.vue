<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import SiteNav from '../components/SiteNav.vue'
import { useAuthStore } from '../stores/auth'
import { useProjectsStore } from '../stores/projects'
import { useWorkspaceStore } from '../stores/workspace'

/** 示例需求：chip 显示短标题，title/点击填充完整 prompt，保持一行三个的整齐布局。 */
const EXAMPLE_PROMPTS = [
  { label: '🍅 番茄钟计时器', prompt: '做一个番茄钟计时器：25 分钟专注 + 5 分钟休息自动循环，带开始/暂停与进度环' },
  { label: '📝 Markdown 编辑器', prompt: '生成一个 Markdown 编辑器：左侧输入、右侧实时预览，支持代码块与表格' },
  { label: '🐍 贪吃蛇小游戏', prompt: '做一个贪吃蛇小游戏：深色主题、方向键控制、实时计分与最高分记录' },
]

/** 使用帮助：三步上手引导（delay 为入场 stagger 的静态类名，Tailwind 可扫描）。 */
const STEPS = [
  {
    icon: '✍️',
    title: '① 描述需求',
    desc: '一句话说明你想要的应用（或点示例快速填入），Ctrl + Enter 即可开始',
    delay: 'delay-100',
  },
  {
    icon: '⚡',
    title: '② 实时观看生成',
    desc: 'Engineer 智能体规划并逐文件编写代码，步骤与沙箱预览实时刷新，可随时停止',
    delay: 'delay-200',
  },
  {
    icon: '🔁',
    title: '③ 对话迭代与分享',
    desc: '继续对话增量修改；自动版本快照可回滚，支持代码导出与扫码分享',
    delay: 'delay-300',
  },
]

/** 真实生成案例（截图存于 client/public/screenshots，README 引用同源文件）。 */
const DEMOS = [
  { image: '/screenshots/workspace.png', title: '秒表计圈器', desc: '一句话生成 · 对话迭代 · 实时预览', delay: 'delay-100' },
  { image: '/screenshots/code.png', title: '代码查看与导出', desc: '文件树 · 语法高亮 · ZIP 下载', delay: 'delay-200' },
  { image: '/screenshots/share.png', title: '扫码分享', desc: '二维码直开 · 访客免登录', delay: 'delay-300' },
]

/** 平台能力：核心功能点 + 一句话实现方案（与 README 完成度清单同源）。 */
const FEATURES = [
  { icon: '🤖', title: '智能体驱动生成', desc: 'deepagents 内置规划 todo，逐文件调用 save_file 工具结构化落库，天然支持流式' },
  { icon: '⚡', title: '实时流式直播', desc: 'SSE 逐步推送步骤与文件，沙箱预览中途即刷新，断开自动重连续看' },
  { icon: '💬', title: '对话增量迭代', desc: 'follow-up 携带当前文件上下文，只改提到的部分，未提及文件保持原样' },
  { icon: '🚦', title: '队列与极速 Stop', desc: '并发池满自动排队并实时显示位次；Stop 检查点下沉到 token 级，点击即停' },
  { icon: '👥', title: '多设备实时同步', desc: '项目事件长连接：活跃生成重放快照 + 直播，空闲挂起等通知，全程免刷新' },
  { icon: '🔀', title: '多端运行态隔离', desc: '生成/停止/排队状态归属项目级，发起端与观看端角色分离，互不干扰' },
  { icon: '📸', title: '版本快照回滚', desc: '每轮生成成功自动存快照，时间线一键回滚，回滚动作本身再落新快照' },
  { icon: '🛠️', title: 'Issue 自修复', desc: 'window.onerror 实时捕获预览报错，Issue 卡一键发起自动修复闭环' },
  { icon: '🎯', title: 'Design Mode', desc: '预览中点选元素，需求框自动回填元素描述，精准告诉 Agent 改哪里' },
  { icon: '📱', title: '分享二维码', desc: '前端生成二维码，扫码免登录只读可交互；关闭分享后链接即刻失效' },
  { icon: '⌨️', title: '代码高亮导出', desc: 'highlight.js 按扩展名高亮，文件树浏览当前文件集，一键 ZIP 打包下载' },
  { icon: '🌗', title: '深浅主题切换', desc: '语义色 token 驱动全组件自适应，localStorage 持久化，默认亮色' },
]

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const projectsStore = useProjectsStore()
const workspaceStore = useWorkspaceStore()

const prompt = ref('')
const creating = ref(false)
const error = ref('')

/** 登录回来带 prompt（/?prompt=...）→ 清 URL 并自动开始生成，衔接跳登录前的意图。 */
onMounted(() => {
  const carried = route.query.prompt
  if (typeof carried === 'string' && carried.trim()) {
    prompt.value = carried
    void router.replace({ query: {} })
    if (auth.user) void submit()
  }
})

/** R1：提交需求 → 创建项目 → pendingPrompt 存入 store → 跳工作台自动开始首次生成。
 *  未登录：携带 prompt 跳登录页，登录成功后回来自动继续。 */
async function submit(): Promise<void> {
  const text = prompt.value.trim()
  if (!text || creating.value) return
  if (!auth.user) {
    await router.push({ name: 'login', query: { redirect: '/', prompt: text } })
    return
  }
  creating.value = true
  error.value = ''
  try {
    const { id } = await projectsStore.create(text)
    workspaceStore.pendingPrompt = text
    prompt.value = ''
    await router.push(`/project/${id}`)
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    creating.value = false
  }
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && (event.ctrlKey || event.metaKey)) {
    event.preventDefault()
    void submit()
  }
}
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-base text-ink">
    <SiteNav />
    <main class="relative flex flex-1 flex-col items-center overflow-hidden px-4 py-20">
      <!-- 背景光晕装饰 -->
      <div aria-hidden="true" class="pointer-events-none absolute inset-0">
        <div
          class="absolute left-1/2 top-[-260px] h-[520px] w-[840px] -translate-x-1/2 rounded-full bg-emerald-500/10 blur-3xl"
        ></div>
        <div class="absolute right-[6%] top-1/4 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl"></div>
      </div>

      <div class="relative flex w-full max-w-3xl flex-col items-center gap-7 text-center">
        <span
          class="animate-rise inline-flex items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-medium text-emerald-300"
        >
          <svg class="size-3.5" viewBox="0 0 24 24" fill="currentColor">
            <path d="M12 2l2.4 7.6L22 12l-7.6 2.4L12 22l-2.4-7.6L2 12l7.6-2.4z" />
          </svg>
          智能体驱动 · 实时流式生成
        </span>

        <h1 class="animate-rise delay-75 text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          描述你的想法
          <span
            class="mt-1 block bg-gradient-to-r from-emerald-400 via-teal-300 to-indigo-400 bg-clip-text text-transparent"
          >
            生成你的应用
          </span>
        </h1>
        <p class="animate-rise delay-150 max-w-xl text-base leading-relaxed text-ink-soft sm:text-lg">
          输入一句话需求，Engineer 智能体实时规划、编写代码并保存文件，
          在沙箱预览中交付可交互的 Web 应用，还能对话式持续迭代。
        </p>

        <!-- 大输入框 -->
        <div
          class="animate-rise delay-200 w-full rounded-2xl border border-line bg-surface/70 p-2 shadow-2xl shadow-black/40 transition focus-within:border-emerald-500/40"
        >
          <textarea
            v-model="prompt"
            autofocus
            rows="4"
            placeholder="描述你想生成的应用，例如：做一个番茄钟计时器，支持专注与休息循环…"
            class="w-full resize-none bg-transparent px-4 py-3 text-base text-ink placeholder:text-ink-mute outline-none"
            @keydown="onKeydown"
          />
          <div class="flex items-center justify-between gap-3 px-4 pb-1 pt-0.5">
            <span class="text-xs text-line-strong">Ctrl + Enter 快速生成</span>
            <button
              type="button"
              :disabled="!prompt.trim() || creating"
              class="inline-flex shrink-0 items-center gap-2 rounded-xl bg-emerald-600 px-5 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-line-strong disabled:text-ink-soft"
              @click="submit"
            >
              {{ creating ? '创建中…' : '开始生成' }}
            </button>
          </div>
        </div>

        <p v-if="error" class="text-sm text-red-400">{{ error }}</p>

        <!-- 示例快捷填入：等高 chips 居中排布，点击填入完整需求 -->
        <div class="animate-rise delay-300 flex flex-wrap items-center justify-center gap-2.5">
          <button
            v-for="example in EXAMPLE_PROMPTS"
            :key="example.label"
            type="button"
            :title="example.prompt"
            class="rounded-full border border-line bg-surface/60 px-4 py-2 text-xs text-ink-soft transition hover:border-emerald-500/40 hover:text-emerald-300"
            @click="prompt = example.prompt"
          >
            {{ example.label }}
          </button>
        </div>
      </div>

      <!-- 使用帮助：三步上手 -->
      <section class="relative mt-20 w-full max-w-4xl">
        <h2 class="animate-rise text-center text-lg font-semibold text-ink">三步上手</h2>
        <div class="mt-6 grid gap-4 sm:grid-cols-3">
          <div
            v-for="step in STEPS"
            :key="step.title"
            class="animate-rise rounded-2xl border border-line bg-surface/60 p-5 text-left transition hover:-translate-y-0.5 hover:border-emerald-500/30"
            :class="step.delay"
          >
            <span class="text-2xl">{{ step.icon }}</span>
            <h3 class="mt-3 text-sm font-semibold text-ink">{{ step.title }}</h3>
            <p class="mt-1.5 text-xs leading-relaxed text-ink-soft">{{ step.desc }}</p>
          </div>
        </div>
      </section>

      <!-- 真实生成案例 -->
      <section class="relative mt-16 w-full max-w-4xl">
        <h2 class="animate-rise text-center text-lg font-semibold text-ink">真实生成案例</h2>
        <p class="animate-rise mt-1.5 text-center text-xs text-ink-mute">以下均为平台真实运行截图</p>
        <div class="mt-6 grid gap-5 sm:grid-cols-3">
          <figure
            v-for="demo in DEMOS"
            :key="demo.title"
            class="animate-rise group overflow-hidden rounded-2xl border border-line bg-surface/60 transition hover:-translate-y-1 hover:shadow-xl hover:shadow-black/10"
            :class="demo.delay"
          >
            <img
              :src="demo.image"
              :alt="demo.title"
              loading="lazy"
              class="aspect-[4/3] w-full border-b border-line object-cover object-top"
            />
            <figcaption class="p-4">
              <p class="text-sm font-medium text-ink">{{ demo.title }}</p>
              <p class="mt-1 text-xs text-ink-mute">{{ demo.desc }}</p>
            </figcaption>
          </figure>
        </div>
      </section>

      <!-- 平台能力：功能点罗列（含一句话实现方案） -->
      <section class="relative mt-16 w-full max-w-5xl pb-16">
        <h2 class="animate-rise text-center text-lg font-semibold text-ink">平台能力</h2>
        <p class="animate-rise mt-1.5 text-center text-xs text-ink-mute">十二项核心功能与实现方案一览</p>
        <div class="mt-6 grid gap-4 text-left sm:grid-cols-3">
          <div
            v-for="(feature, i) in FEATURES"
            :key="feature.title"
            class="animate-rise rounded-2xl border border-line bg-surface/60 p-5 transition hover:-translate-y-0.5 hover:border-emerald-500/30"
            :class="['delay-75', 'delay-150', 'delay-300'][i % 3]"
          >
            <span class="text-2xl">{{ feature.icon }}</span>
            <h3 class="mt-3 text-sm font-semibold text-ink">{{ feature.title }}</h3>
            <p class="mt-1.5 text-xs leading-relaxed text-ink-soft">{{ feature.desc }}</p>
          </div>
        </div>
      </section>
    </main>
  </div>
</template>
