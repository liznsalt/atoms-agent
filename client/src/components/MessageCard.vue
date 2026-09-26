<script setup lang="ts">
import { computed, ref } from 'vue'
import { ERROR_PREFIX, type RunMessage } from '../stores/workspace'

const props = defineProps<{ message: RunMessage; generating?: boolean }>()
const emit = defineEmits<{ retry: [] }>()

const isUser = computed(() => props.message.role === 'user')
const isPending = computed(() => !isUser.value && (props.message.pending ?? false))
/** 以 ERROR_PREFIX 开头的 agent 消息（含历史落库的错误消息）按错误卡渲染。 */
const isError = computed(() => !isUser.value && props.message.content.startsWith(ERROR_PREFIX))
const errorDetail = computed(
  () =>
    props.message.content.replace(`${ERROR_PREFIX}：`, '').replace(`${ERROR_PREFIX}:`, '') ||
    props.message.content,
)
const steps = computed(() => props.message.steps ?? [])
/** 执行动作步骤（tool/todo）；message 类逐 token 步骤合并为流式文本预览。 */
const actionSteps = computed(() => steps.value.filter((s) => s.kind !== 'message'))
const streamText = computed(() =>
  steps.value
    .filter((s) => s.kind === 'message')
    .map((s) => s.content)
    .join(''),
)
/** 运行中的卡片步骤默认展开，历史消息默认折叠。 */
const expanded = ref(isPending.value)

const KIND_META: Record<string, { label: string; cls: string }> = {
  todo: { label: '规划', cls: 'border-indigo-400/30 bg-indigo-400/10 text-indigo-300' },
  tool: { label: '工具', cls: 'border-emerald-400/30 bg-emerald-400/10 text-emerald-300' },
  message: { label: '消息', cls: 'border-ink-mute/30 bg-ink-mute/10 text-ink-soft' },
}

function kindMeta(kind: string): { label: string; cls: string } {
  return KIND_META[kind] ?? KIND_META.message
}
</script>

<template>
  <!-- 用户消息：右侧气泡 -->
  <div v-if="isUser" class="animate-rise flex justify-end">
    <div
      class="max-w-[85%] rounded-2xl rounded-br-md bg-line px-4 py-2.5 text-sm leading-relaxed whitespace-pre-wrap break-words text-ink"
    >
      {{ message.content }}
    </div>
  </div>

  <!-- Agent 消息：左侧，带 Engineer 标签 -->
  <div v-else class="animate-rise flex flex-col items-start gap-2">
    <div class="flex items-center gap-2">
      <span
        class="flex size-6 items-center justify-center rounded-md bg-gradient-to-br from-emerald-400 to-teal-500 text-[11px] font-bold text-zinc-950"
      >
        E
      </span>
      <span class="text-xs font-medium text-emerald-400">Engineer</span>
      <span v-if="isPending" class="flex items-center gap-1.5 text-xs text-ink-mute">
        <span class="thinking-dot"></span>
        <span class="thinking-dot thinking-dot-2"></span>
        <span class="thinking-dot thinking-dot-3"></span>
        <span>生成中</span>
      </span>
    </div>

    <!-- 错误卡片（R6：红色错误卡 + 重试按钮） -->
    <div v-if="isError" class="w-full max-w-[92%] rounded-xl border border-red-500/25 bg-red-500/10 p-4">
      <p class="flex items-center gap-2 text-sm font-medium text-red-400">
        <svg class="size-4 shrink-0" viewBox="0 0 20 20" fill="currentColor">
          <path
            fill-rule="evenodd"
            d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-5a1 1 0 112 0 1 1 0 01-2 0zm1-8a.75.75 0 01.75.75v4.5a.75.75 0 11-1.5 0v-4.5A.75.75 0 0110 5z"
            clip-rule="evenodd"
          />
        </svg>
        生成失败
      </p>
      <p class="mt-1.5 text-sm leading-relaxed whitespace-pre-wrap break-words text-red-300/90">
        {{ errorDetail }}
      </p>
      <button
        type="button"
        :disabled="generating"
        class="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:opacity-50"
        @click="emit('retry')"
      >
        <svg class="size-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path
            stroke-linecap="round"
            stroke-linejoin="round"
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
        重试
      </button>
    </div>

    <!-- 本次总结（done 的 summary） -->
    <div
      v-else-if="message.content"
      class="max-w-[92%] rounded-2xl rounded-tl-md border border-line bg-surface/70 px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words text-ink"
    >
      {{ message.content }}
    </div>

    <!-- 运行中的流式输出预览（打字机效果） -->
    <div
      v-if="isPending && streamText"
      class="max-w-[92%] rounded-2xl rounded-tl-md border border-emerald-500/20 bg-surface/70 px-4 py-3 text-sm leading-relaxed whitespace-pre-wrap break-words text-ink"
    >
      {{ streamText }}<span class="thinking-caret"></span>
    </div>

    <!-- 执行过程（可折叠步骤卡片，R2；实时 step 也累积在此） -->
    <div
      v-if="actionSteps.length"
      class="w-full max-w-[92%] overflow-hidden rounded-xl border border-line bg-surface/40"
    >
      <button
        type="button"
        class="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-ink-soft transition hover:text-ink"
        @click="expanded = !expanded"
      >
        <svg
          class="size-3.5 shrink-0 transition-transform"
          :class="expanded ? 'rotate-90' : ''"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
        >
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 5l7 7-7 7" />
        </svg>
        执行过程
        <span class="text-ink-mute">（{{ actionSteps.length }} 步）</span>
      </button>
      <ol v-show="expanded" class="space-y-2 border-t border-line/70 px-3 py-2.5">
        <li v-for="(step, i) in actionSteps" :key="i" class="flex items-start gap-2">
          <span
            class="mt-px shrink-0 rounded border px-1.5 py-0.5 font-mono text-[10px] leading-none"
            :class="kindMeta(step.kind).cls"
          >
            {{ kindMeta(step.kind).label }}
          </span>
          <span class="min-w-0 flex-1 break-words whitespace-pre-wrap text-xs leading-relaxed text-ink-soft">
            {{ step.content }}
          </span>
        </li>
      </ol>
    </div>
  </div>
</template>
