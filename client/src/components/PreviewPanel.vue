<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import hljs from 'highlight.js/lib/common'
import { exportUrl, type VersionInfo } from '../api'

const props = defineProps<{
  projectId: number
  previewKey: number
  files: Record<string, string>
  versions: VersionInfo[]
  shareEnabled: boolean
  generating: boolean
}>()

const emit = defineEmits<{
  refresh: []
  rollback: [versionId: number]
  toggleShare: []
  /** Design Mode 点选了元素：回填需求输入框 */
  pick: [description: string]
}>()

type Tab = 'preview' | 'code'
type Viewport = 'desktop' | 'mobile'

const tab = ref<Tab>('preview')
const viewport = ref<Viewport>('desktop')
const showVersions = ref(false)
/** Design Mode：预览内点选元素回填需求（精准迭代）。 */
const designMode = ref(false)

const fileCount = computed(() => Object.keys(props.files).length)

/** previewKey 变化 → src 与 :key 同时更新，iframe 强制重载最新组装页；design 模式注入选择器。 */
const src = computed(
  () =>
    `/preview/${props.projectId}?v=${props.previewKey}${designMode.value ? '&design=1' : ''}`,
)

/* ---------- iframe → 父页面事件（Issue 自修复 + Design Mode 点选） ---------- */

function onMessage(event: MessageEvent): void {
  const frame = document.querySelector('iframe')
  if (!frame || event.source !== frame.contentWindow) return
  const data = event.data as { type?: string; message?: string; source?: string; description?: string; text?: string }
  if (data?.type === 'atoms-issue' && typeof data.message === 'string') {
    // 经全局自定义事件交给 workspace store（组件不直接依赖 store，保持纯展示）
    window.dispatchEvent(
      new CustomEvent('atoms-issue', { detail: { message: data.message, source: data.source ?? '' } }),
    )
  } else if (data?.type === 'atoms-pick' && typeof data.description === 'string') {
    const label = data.text ? `（内容：「${data.text}」）` : ''
    emit('pick', `修改页面中的这个元素：${data.description}${label}——`)
    designMode.value = false // 点选一次即退出，恢复交互
  }
}

onMounted(() => window.addEventListener('message', onMessage))
onBeforeUnmount(() => window.removeEventListener('message', onMessage))

/* ---------- 代码视图（Task 12 + 语法高亮）---------- */

const fileNames = computed(() => Object.keys(props.files).sort())
const activeFile = ref('')

/** 按扩展名映射 highlight.js 语言。 */
function languageOf(name: string): string {
  const ext = name.split('.').pop()?.toLowerCase() ?? ''
  if (ext === 'html' || ext === 'htm' || ext === 'vue' || ext === 'svg') return 'xml'
  if (ext === 'js' || ext === 'mjs') return 'javascript'
  if (ext === 'ts') return 'typescript'
  if (ext === 'jsx' || ext === 'tsx') return 'typescript'
  if (ext === 'json') return 'json'
  if (ext === 'md') return 'markdown'
  if (ext === 'py') return 'python'
  if (ext === 'css') return 'css'
  if (ext === 'scss') return 'scss'
  return 'plaintext'
}

/** 高亮后的 HTML（整块渲染 + 行号列对齐；失败退回纯文本转义）。 */
const highlightedLines = computed(() => {
  const code = props.files[activeFile.value] ?? ''
  const lang = languageOf(activeFile.value)
  const escape = (text: string): string =>
    text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  try {
    const html = hljs.highlight(code, { language: lang, ignoreIllegals: true }).value
    return { html, lines: code.split('\n').length, fallback: false }
  } catch {
    return { html: escape(code), lines: code.split('\n').length, fallback: true }
  }
})

watch(
  fileNames,
  (names) => {
    if (!names.includes(activeFile.value)) activeFile.value = names[0] ?? ''
  },
  { immediate: true },
)

/* ---------- 版本时间线（Task 9）---------- */

function formatTime(iso: string): string {
  const date = new Date(`${iso}Z`)
  return Number.isNaN(date.getTime())
    ? iso
    : date.toLocaleString('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
}
</script>

<template>
  <div class="flex h-full min-h-0 flex-col gap-2 p-3 lg:p-4">
    <!-- 工具栏：预览/代码 tab + 视口切换 + 分享 + 版本 + 刷新/导出 -->
    <div class="flex shrink-0 flex-wrap items-center gap-1.5">
      <div class="flex rounded-lg border border-line bg-surface/70 p-0.5">
        <button
          v-for="item in (['preview', 'code'] as Tab[])"
          :key="item"
          type="button"
          class="rounded-md px-2.5 py-1 text-xs font-medium transition"
          :class="tab === item ? 'bg-line-strong/80 text-ink' : 'text-ink-soft hover:text-ink'"
          @click="tab = item"
        >
          {{ item === 'preview' ? '预览' : '代码' }}
        </button>
      </div>
      <span
        v-if="fileCount > 0"
        class="rounded-md border border-line bg-surface/70 px-1.5 py-0.5 font-mono text-[11px] text-ink-soft"
      >
        {{ fileCount }} 个文件
      </span>
      <span v-if="generating" class="flex items-center gap-1 text-xs text-emerald-400">
        <span class="size-1.5 animate-pulse rounded-full bg-emerald-400"></span>
        更新中
      </span>

      <div class="ml-auto flex items-center gap-1.5">
        <!-- Task 10：视口切换（仅预览 tab） -->
        <div
          v-if="tab === 'preview'"
          class="flex rounded-lg border border-line bg-surface/70 p-0.5"
        >
          <button
            v-for="item in (['desktop', 'mobile'] as Viewport[])"
            :key="item"
            type="button"
            :title="item === 'desktop' ? '桌面视口' : '手机视口（375px）'"
            class="rounded-md p-1.5 transition"
            :class="viewport === item ? 'bg-line-strong/80 text-ink' : 'text-ink-mute hover:text-ink-soft'"
            @click="viewport = item"
          >
            <svg v-if="item === 'desktop'" class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <svg v-else class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 18h.01M7 21a2 2 0 01-2-2V5a2 2 0 012-2h10a2 2 0 012 2v14a2 2 0 01-2 2H7z" />
            </svg>
          </button>
        </div>

        <!-- Design Mode：点选元素回填需求（仅预览 tab） -->
        <button
          v-if="tab === 'preview' && fileCount > 0"
          type="button"
          :title="designMode ? '点选预览中的元素回填到输入框（点击后自动退出）' : '开启点选修改：在预览中点选元素'"
          class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition"
          :class="designMode
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
            : 'border-line text-ink-soft hover:border-line-strong hover:text-ink'"
          @click="designMode = !designMode"
        >
          <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.042 21.672L13.684 16.6m0 0l-2.51 2.225.569-9.47 5.227 7.917-3.286-.672zM12 2.25V4.5m5.834.166l-1.591 1.591M20.25 10.5H18M7.757 14.743l-1.59 1.59M6 10.5H3.75m4.007-4.243l-1.59-1.59" />
          </svg>
          {{ designMode ? '点选中…' : '点选修改' }}
        </button>

        <!-- Task 12：ZIP 导出（仅代码 tab） -->
        <a
          v-if="tab === 'code' && fileCount > 0"
          :href="exportUrl(projectId)"
          download
          title="下载 ZIP"
          class="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink-soft transition hover:border-line-strong hover:text-ink"
        >
          <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12m0 0l-4-4m4 4l4-4" />
          </svg>
          下载 ZIP
        </a>

        <!-- Task 11：一键分享 -->
        <button
          type="button"
          :disabled="generating"
          :title="shareEnabled ? '分享中，点击关闭（关闭后链接失效）' : '开启公开分享链接'"
          class="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs transition disabled:cursor-not-allowed disabled:opacity-50"
          :class="shareEnabled
            ? 'border-emerald-500/40 bg-emerald-500/10 text-emerald-400 hover:bg-emerald-500/20'
            : 'border-line text-ink-soft hover:border-line-strong hover:text-ink'"
          @click="emit('toggleShare')"
        >
          <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.684 13.342C8.886 13.211 9 13.03 9 12.839c0-.19-.114-.372-.316-.503L4 9.5m4.684 3.842c-.738.462-1.696.433-2.384-.193M8.684 13.342l8.838-5.524M5.3 13.149L15.32 6.86c.436-.273.436-.866 0-1.139l-2.03-1.271c-.872-.546-2.066-.4-2.667.325L4 12.03m1.3 1.119a2 2 0 00.676 2.647l2.03 1.271c.436.273.436.866 0 1.139l-2.03 1.271M18 16.5l-4 2m0 0l-1.854 1.36a1 1 0 01-1.446-.195l-1.7-2.4M14 18.5l-4-2m-3.5 4.5l4-2.5m5.5 3.5L12 20.5m6.75-10.75l-4.25-3m4.25 3a1.75 1.75 0 012.75 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h14a2 2 0 012 2v4.75z" />
          </svg>
          {{ shareEnabled ? '分享中' : '分享' }}
        </button>

        <!-- Task 9：版本时间线 -->
        <div class="relative">
          <button
            type="button"
            :disabled="generating"
            title="历史版本"
            class="inline-flex items-center gap-1.5 rounded-lg border border-line px-2.5 py-1.5 text-xs text-ink-soft transition hover:border-line-strong hover:text-ink disabled:cursor-not-allowed disabled:opacity-50"
            @click.stop="showVersions = !showVersions"
          >
            <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            版本
            <span v-if="versions.length" class="font-mono text-[10px] text-ink-mute">{{ versions.length }}</span>
          </button>

          <!-- 点击遮罩关闭下拉 -->
          <div v-if="showVersions" class="fixed inset-0 z-20" @click="showVersions = false"></div>
          <div
            v-if="showVersions"
            class="absolute right-0 top-full z-30 mt-2 max-h-96 w-80 overflow-y-auto rounded-xl border border-line bg-surface p-2 shadow-2xl shadow-black/50"
          >
            <p class="px-2 py-1.5 text-xs font-medium tracking-wider text-ink-mute uppercase">历史版本</p>
            <p v-if="!versions.length" class="px-2 py-4 text-center text-xs text-line-strong">
              暂无版本（每次生成成功会自动保存快照）
            </p>
            <div
              v-for="version in versions"
              :key="version.id"
              class="group flex items-start gap-2 rounded-lg px-2 py-2 transition hover:bg-line/60"
            >
              <div class="min-w-0 flex-1">
                <p class="truncate text-xs text-ink" :title="version.label">
                  <span class="font-mono text-ink-mute">v{{ version.id }}</span>
                  {{ version.label }}
                </p>
                <p class="mt-0.5 text-[10px] text-ink-mute">{{ formatTime(version.created_at) }}</p>
              </div>
              <button
                type="button"
                class="shrink-0 rounded-md border border-line-strong px-2 py-1 text-[11px] text-ink-soft transition hover:border-emerald-500/50 hover:text-emerald-400"
                @click="emit('rollback', version.id); showVersions = false"
              >
                回滚
              </button>
            </div>
          </div>
        </div>

        <!-- 手动刷新（仅预览 tab） -->
        <button
          v-if="tab === 'preview'"
          type="button"
          title="刷新预览"
          class="rounded-lg border border-line p-1.5 text-ink-soft transition hover:border-line-strong hover:text-ink"
          @click="emit('refresh')"
        >
          <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path
              stroke-linecap="round"
              stroke-linejoin="round"
              d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
            />
          </svg>
        </button>
      </div>
    </div>

    <!-- 预览 tab（R3 + Task 10 视口切换） -->
    <div
      v-if="tab === 'preview'"
      class="relative min-h-0 flex-1 overflow-hidden rounded-xl border border-line bg-surface/40"
      :class="viewport === 'mobile' ? 'flex items-center justify-center bg-base/60 p-3' : ''"
    >
      <iframe
        v-if="fileCount > 0"
        :key="previewKey"
        :src="src"
        sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"
        class="h-full border-0 bg-white"
        :class="viewport === 'mobile'
          ? 'w-full max-w-[375px] rounded-lg border border-line-strong shadow-2xl'
          : 'absolute inset-0 w-full'"
      />
      <!-- 占位态：首次尚无 files -->
      <div v-else class="absolute inset-0 flex flex-col items-center justify-center gap-3">
        <svg
          class="size-10 text-line-strong"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
        >
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M3 7a2 2 0 012-2h4l2 2h6a2 2 0 012 2v8a2 2 0 01-2 2H5a2 2 0 01-2-2V7z"
          />
        </svg>
        <p class="text-sm text-ink-mute">{{ generating ? '正在生成应用…' : '等待生成…' }}</p>
        <p v-if="generating" class="text-xs text-line-strong">Engineer 正在编写文件，预览稍后自动刷新</p>
      </div>
    </div>

    <!-- 代码 tab（Task 12：文件树 + 代码查看） -->
    <div v-else class="flex min-h-0 flex-1 gap-2">
      <!-- 文件列表 -->
      <div class="w-40 shrink-0 overflow-y-auto rounded-xl border border-line bg-surface/40 p-1.5 lg:w-52">
        <p v-if="!fileNames.length" class="px-2 py-4 text-center text-xs text-line-strong">暂无文件</p>
        <button
          v-for="name in fileNames"
          :key="name"
          type="button"
          class="block w-full truncate rounded-md px-2 py-1.5 text-left font-mono text-xs transition"
          :class="name === activeFile ? 'bg-line-strong/80 text-ink' : 'text-ink-soft hover:bg-line/60 hover:text-ink'"
          :title="name"
          @click="activeFile = name"
        >
          {{ name }}
        </button>
      </div>
      <!-- 代码内容（语法高亮，固定深色代码底，两主题通用） -->
      <div class="code-view min-h-0 min-w-0 flex-1 overflow-auto rounded-xl border border-line">
        <p v-if="!activeFile" class="flex h-full items-center justify-center text-xs text-[#8b949e]">
          选择左侧文件查看代码
        </p>
        <div v-else class="flex min-w-max py-3 font-mono text-xs leading-5">
          <div
            class="sticky left-0 shrink-0 bg-[#0d1117] pr-3 pl-4 text-right text-[#484f58] select-none"
          >
            <div v-for="n in highlightedLines.lines" :key="n">{{ n }}</div>
          </div>
          <pre
            class="min-w-0 flex-1 whitespace-pre pr-6 pl-3 text-[#c9d1d9]"
            v-html="highlightedLines.html"
          ></pre>
        </div>
      </div>
    </div>
  </div>
</template>
