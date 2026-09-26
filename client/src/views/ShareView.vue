<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { getShare, type ShareInfo } from '../api'

const route = useRoute()
const state = ref<'loading' | 'ready' | 'invalid'>('loading')
const data = ref<ShareInfo | null>(null)

onMounted(async () => {
  try {
    data.value = await getShare(String(route.params.shareId))
    state.value = 'ready'
  } catch {
    state.value = 'invalid'
  }
})
</script>

<template>
  <div class="flex h-dvh flex-col bg-base text-ink">
    <!-- 加载 / 失效态 -->
    <main
      v-if="state !== 'ready'"
      class="flex flex-1 flex-col items-center justify-center gap-4 px-4 text-center"
    >
      <template v-if="state === 'loading'">
        <p class="animate-pulse text-sm text-ink-mute">正在打开分享…</p>
      </template>
      <template v-else>
        <svg class="size-10 text-line-strong" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
        </svg>
        <p class="text-sm text-ink-soft">分享链接无效或已被作者关闭</p>
        <p class="text-xs text-line-strong">请向项目作者确认分享状态</p>
      </template>
    </main>

    <!-- 只读预览：访客免登录，应用内可真实交互 -->
    <template v-else-if="data">
      <header class="flex h-14 shrink-0 items-center gap-3 border-b border-line px-4">
        <span class="flex items-center gap-1.5 text-sm font-medium text-emerald-400">
          <svg class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
          </svg>
          Atoms Agent
        </span>
        <div class="h-4 w-px bg-line"></div>
        <h1 class="min-w-0 flex-1 truncate text-sm font-medium text-ink" :title="data.title">
          {{ data.title }}
        </h1>
        <span class="shrink-0 rounded-full border border-line-strong bg-surface px-2.5 py-1 text-xs text-ink-soft">
          只读分享
        </span>
      </header>
      <main class="min-h-0 flex-1 p-3 lg:p-4">
        <iframe
          :src="`/preview/${data.project_id}`"
          sandbox="allow-scripts allow-forms allow-popups allow-modals allow-same-origin"
          class="h-full w-full rounded-xl border border-line bg-white"
        />
      </main>
    </template>
  </div>
</template>
