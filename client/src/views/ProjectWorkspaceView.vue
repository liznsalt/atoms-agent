<script setup lang="ts">
import { computed, nextTick, onMounted, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import MessageCard from '../components/MessageCard.vue'
import PreviewPanel from '../components/PreviewPanel.vue'
import { useWorkspaceStore, type RunMessage } from '../stores/workspace'
import { useThemeStore } from '../stores/theme'

const route = useRoute()
const store = useWorkspaceStore()
const theme = useThemeStore()

const draft = ref('')
const scrollRef = ref<HTMLElement | null>(null)

const projectId = computed(() => Number(route.params.id))
const totalSteps = computed(() =>
  store.messages.reduce((sum, message) => sum + (message.steps?.length ?? 0), 0),
)

function scrollToBottom(behavior: ScrollBehavior = 'auto'): void {
  void nextTick(() => {
    const el = scrollRef.value
    if (el) el.scrollTo({ top: el.scrollHeight, behavior })
  })
}

/** 新消息 / 新步骤到达时自动滚动到底部。 */
watch([() => store.messages.length, totalSteps], () => scrollToBottom('smooth'))

/** iframe 上报的运行时错误 → Issue 列表（PreviewPanel 经全局事件转发）。 */
function onIssueEvent(event: Event): void {
  const detail = (event as CustomEvent<{ message: string; source: string }>).detail
  if (detail?.message) {
    store.pushIssue(detail.message, detail.source)
    scrollToBottom('smooth')
  }
}

onMounted(() => {
  window.addEventListener('atoms-issue', onIssueEvent)
})
onBeforeUnmount(() => {
  window.removeEventListener('atoms-issue', onIssueEvent)
  store.closeWatch() // 断开项目事件长连接（多设备同步）
})

onMounted(async () => {
  await store.loadProject(projectId.value)
  scrollToBottom()
  // R1：首页创建项目跳转而来 → 自动作为首条消息开始首次生成
  const pending = store.pendingPrompt
  if (pending) {
    store.pendingPrompt = ''
    // 防御：仅空项目自动发首条（正常时序创建的新项目必无消息；
    // 经任何异常途径带着 pendingPrompt 打开已有消息的项目时不重复生成）
    if (!store.loadError && !store.messages.length) void store.sendPrompt(pending)
  }
})

/** Design Mode 点选元素 → 回填需求输入框并聚焦（用户补充描述后发送）。 */
function onPick(description: string): void {
  draft.value = `${description}${draft.value.trim() ? draft.value.trim() : '请把它改得更好看'}`
  void nextTick(() => {
    const ta = document.querySelector('textarea')
    if (ta instanceof HTMLTextAreaElement) {
      ta.focus()
      const pos = Math.max(0, draft.value.length - 6)
      ta.setSelectionRange(pos, pos)
    }
  })
}

/** 分享弹层：复制链接（关闭即隐藏 toast 场景下链接仍可随时再复制）。 */
async function copyShareLink(): Promise<void> {
  await navigator.clipboard.writeText(store.shareUrl).catch(() => {})
  store.notify('链接已复制')
}

/** R4：follow-up 增量迭代；生成中自动入队（Task 14）。 */
function send(): void {
  const text = draft.value
  if (!text.trim()) return
  draft.value = ''
  store.submit(text)
}

function onKeydown(event: KeyboardEvent): void {
  if (event.key === 'Enter' && !event.shiftKey && !event.isComposing) {
    event.preventDefault()
    send()
  }
}

/** R6：重试 = 重发错误卡片之前最近的一条用户消息。 */
function onRetry(message: RunMessage): void {
  const list = store.messages
  const index = list.indexOf(message)
  for (let i = index - 1; i >= 0; i--) {
    if (list[i].role === 'user') {
      void store.sendPrompt(list[i].content)
      return
    }
  }
}
</script>

<template>
  <div class="flex h-dvh flex-col bg-base text-ink">
    <!-- 顶部：项目标题 + 返回列表 -->
    <header class="flex h-14 shrink-0 items-center gap-3 border-b border-line px-3 sm:px-4">
      <RouterLink
        to="/projects"
        title="返回项目列表"
        class="flex shrink-0 items-center gap-1.5 rounded-lg px-2 py-1.5 text-sm text-ink-soft transition hover:bg-line/70 hover:text-ink"
      >
        <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path stroke-linecap="round" stroke-linejoin="round" d="M10 19l-7-7m0 0l7-7m-7 7h18" />
        </svg>
        <span class="hidden sm:inline">返回列表</span>
      </RouterLink>
      <div class="hidden h-4 w-px bg-line sm:block"></div>
      <h1 class="min-w-0 flex-1 truncate text-sm font-medium text-ink" :title="store.project?.title ?? ''">
        {{ store.project?.title ?? '项目工作台' }}
      </h1>
      <span
        v-if="store.generating && store.queuePosition > 0"
        class="flex shrink-0 items-center gap-1.5 rounded-full border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-xs text-amber-500"
      >
        <span class="size-1.5 animate-pulse rounded-full bg-amber-400"></span>
        排队中 · 第 {{ store.queuePosition }} 位
      </span>
      <span
        v-else-if="store.generating"
        class="flex shrink-0 items-center gap-1.5 rounded-full border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-xs text-emerald-400"
      >
        <span class="size-1.5 animate-pulse rounded-full bg-emerald-400"></span>
        生成中…
      </span>
      <!-- 主题切换：深/浅 -->
      <button
        type="button"
        :title="theme.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
        class="shrink-0 rounded-lg p-2 text-ink-soft transition hover:bg-line/70 hover:text-ink"
        @click="theme.toggle()"
      >
        <svg v-if="theme.theme === 'dark'" class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z"
          />
        </svg>
        <svg v-else class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z"
          />
        </svg>
      </button>
    </header>

    <!-- 项目加载失败 -->
    <main v-if="store.loadError" class="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center">
      <p class="text-sm text-red-400">项目加载失败：{{ store.loadError }}</p>
      <RouterLink
        to="/projects"
        class="rounded-xl border border-line-strong px-4 py-2 text-sm text-ink-soft transition hover:border-ink-mute hover:text-ink"
      >
        返回项目列表
      </RouterLink>
    </main>
    <div v-else-if="store.loading" class="flex flex-1 items-center justify-center">
      <p class="animate-pulse text-sm text-ink-mute">加载中…</p>
    </div>

    <!-- 主体：左 Chat 右 Preview，移动端纵向堆叠 -->
    <main
      v-else
      class="grid min-h-0 flex-1 grid-cols-1 grid-rows-[minmax(0,1.1fr)_minmax(0,1fr)] lg:grid-cols-[minmax(400px,2fr)_minmax(0,3fr)] lg:grid-rows-1"
    >
      <!-- 左：对话面板 -->
      <section class="flex min-h-0 flex-col border-b border-line lg:border-b-0 lg:border-r">
        <div ref="scrollRef" class="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4">
          <div
            v-if="!store.messages.length && !store.generating"
            class="flex h-full flex-col items-center justify-center gap-2 text-center"
          >
            <svg
              class="size-8 text-line-strong"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              stroke-width="1.5"
            >
              <path
                stroke-linecap="round"
                stroke-linejoin="round"
                d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
              />
            </svg>
            <p class="text-sm text-ink-mute">在下方输入需求，Engineer 智能体将开始生成你的应用</p>
          </div>

          <!-- Issue 卡（预览运行时错误，一键自动修复） -->
          <div
            v-for="(issue, index) in store.issues"
            :key="issue.message"
            class="w-full rounded-xl border border-amber-500/30 bg-amber-500/10 p-4"
          >
            <p class="flex items-center gap-2 text-sm font-medium text-amber-500">
              <svg class="size-4 shrink-0" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z" />
              </svg>
              检测到应用运行错误
            </p>
            <p class="mt-1.5 break-words text-xs leading-relaxed text-amber-600">
              {{ issue.message }}
              <span class="text-amber-500/70">（{{ issue.source }}）</span>
            </p>
            <div class="mt-3 flex items-center gap-2">
              <button
                type="button"
                :disabled="store.generating"
                class="inline-flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-50"
                @click="store.resolveIssue(index)"
              >
                <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.456 2.456L21.75 6l-1.035.259a3.375 3.375 0 00-2.456 2.456z" />
                </svg>
                自动修复
              </button>
              <button
                type="button"
                class="rounded-lg border border-line px-3 py-1.5 text-xs text-ink-soft transition hover:text-ink"
                @click="store.dismissIssue(index)"
              >
                忽略
              </button>
            </div>
          </div>

          <MessageCard
            v-for="message in store.messages"
            :key="message.id"
            :message="message"
            :generating="store.generating"
            @retry="onRetry(message)"
          />
        </div>

        <!-- 输入区：生成中可入队（Task 14）+ Stop -->
        <footer class="shrink-0 border-t border-line bg-base/60 p-3">
          <!-- 排队消息（可删） -->
          <div v-if="store.queue.length" class="mb-2 space-y-1.5">
            <p class="px-1 text-[11px] text-ink-mute">
              队列（{{ store.queue.length }} 条，本轮完成后自动发送）
            </p>
            <div
              v-for="(item, index) in store.queue"
              :key="`${index}-${item}`"
              class="flex items-center gap-2 rounded-lg border border-line bg-surface/70 px-2.5 py-1.5"
            >
              <span class="size-1.5 shrink-0 rounded-full bg-amber-400"></span>
              <span class="min-w-0 flex-1 truncate text-xs text-ink-soft" :title="item">{{ item }}</span>
              <button
                type="button"
                title="移除排队消息"
                class="shrink-0 rounded p-0.5 text-ink-mute transition hover:text-red-400"
                @click="store.removeQueued(index)"
              >
                <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
          </div>

          <div
            class="flex items-end gap-2 rounded-xl border border-line bg-surface/70 p-2 transition focus-within:border-emerald-500/40"
          >
            <textarea
              v-model="draft"
              rows="2"
              :placeholder="store.generating ? '生成中…发送将加入队列，完成后自动执行' : '继续描述你想要的改动，例如：主题色改成绿色…'"
              class="max-h-32 min-h-11 flex-1 resize-none bg-transparent px-2 py-2 text-sm text-ink placeholder:text-ink-mute outline-none"
              @keydown="onKeydown"
            />
            <!-- Stop（Task 14）：协作式中断，保留已写文件；排队中 = 取消排队 -->
            <button
              v-if="store.generating"
              type="button"
              :disabled="store.stopping"
              :title="store.queuePosition > 0 ? '取消排队（不会产生任何改动）' : '停止生成（已完成的修改会保留）'"
              class="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-500/10 px-3 py-2 text-sm font-medium text-red-400 transition hover:bg-red-500/20 disabled:cursor-not-allowed disabled:opacity-50"
              @click="store.stop()"
            >
              <svg class="size-3.5" viewBox="0 0 24 24" fill="currentColor">
                <rect x="6" y="6" width="12" height="12" rx="2" />
              </svg>
              {{ store.stopping ? '停止中…' : store.queuePosition > 0 ? '取消排队' : '停止' }}
            </button>
            <button
              type="button"
              :disabled="!draft.trim()"
              class="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-emerald-600 px-3.5 py-2 text-sm font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-line-strong disabled:text-ink-soft"
              @click="send"
            >
              <svg
                v-if="store.generating"
                class="size-4 animate-spin"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
              >
                <path stroke-linecap="round" d="M12 3a9 9 0 109 9" />
              </svg>
              <svg v-else class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 12L3 21l18-9L3 3l3 9zm0 0h6" />
              </svg>
              {{ store.generating ? '加入队列' : '发送' }}
            </button>
          </div>
          <p class="mt-1.5 px-1 text-[11px] text-line-strong">Enter 发送 · Shift + Enter 换行</p>
        </footer>
      </section>

      <!-- 右：实时预览（R3）+ P1（视口/版本/分享/代码） -->
      <section class="min-h-0">
        <PreviewPanel
          :project-id="projectId"
          :preview-key="store.previewKey"
          :files="store.files"
          :versions="store.versions"
          :share-enabled="store.project?.is_shared ?? false"
          :generating="store.generating"
          @refresh="store.bumpPreview()"
          @rollback="store.rollbackTo"
          @toggle-share="store.toggleShare"
          @pick="onPick"
        />
      </section>
    </main>

    <!-- 操作提示（分享/回滚结果），自动消失 -->
    <Teleport to="body">
      <div
        v-if="store.toast"
        class="pointer-events-none fixed top-4 left-1/2 z-50 max-w-[92vw] -translate-x-1/2 truncate rounded-xl border border-line-strong bg-surface/95 px-4 py-2 text-sm text-ink shadow-2xl shadow-black/50"
      >
        {{ store.toast }}
      </div>
    </Teleport>

    <!-- 分享弹层：二维码扫码 / 链接直开（无需登录即可查看） -->
    <Teleport to="body">
      <Transition name="pop">
        <div
          v-if="store.showShare"
          class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4"
          @click.self="store.closeShare()"
        >
        <div class="w-full max-w-xs rounded-2xl border border-line bg-surface p-5 shadow-2xl">
          <div class="mb-4 flex items-center justify-between">
            <h3 class="text-sm font-semibold text-ink">分享项目</h3>
            <button
              type="button"
              title="关闭"
              class="rounded-lg p-1.5 text-ink-mute transition hover:bg-line/70 hover:text-ink"
              @click="store.closeShare()"
            >
              <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
          <!-- 二维码固定白底保证扫码对比度（深色主题同样可扫） -->
          <div class="flex justify-center rounded-xl bg-white p-3">
            <img v-if="store.shareQr" :src="store.shareQr" alt="分享二维码" class="size-52" />
            <div v-else class="flex size-52 items-center justify-center text-xs text-gray-400">
              二维码生成失败，请使用下方链接
            </div>
          </div>
          <p class="mt-3 break-all text-center text-xs leading-relaxed text-ink-mute" :title="store.shareUrl">
            {{ store.shareUrl }}
          </p>
          <button
            type="button"
            class="mt-4 w-full rounded-lg bg-emerald-600 px-3 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
            @click="copyShareLink"
          >
            复制链接
          </button>
          <p class="mt-2.5 text-center text-[11px] text-ink-mute">扫码或打开链接即可查看项目，无需登录</p>
        </div>
        </div>
      </Transition>
    </Teleport>
  </div>
</template>
