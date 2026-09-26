<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import SiteNav from '../components/SiteNav.vue'
import type { ProjectSummary } from '../api'
import { useProjectsStore } from '../stores/projects'

const router = useRouter()
const store = useProjectsStore()
const deleteError = ref('')

onMounted(() => {
  void store.fetchList()
})

function open(id: number): void {
  void router.push(`/project/${id}`)
}

async function remove(project: ProjectSummary): Promise<void> {
  if (!confirm(`确定删除项目「${project.title}」？删除后不可恢复。`)) return
  deleteError.value = ''
  try {
    await store.remove(project.id)
  } catch (err) {
    deleteError.value = err instanceof Error ? err.message : String(err)
  }
}

/** 服务端存 UTC naive ISO，补 Z 后按本地时区展示。 */
function formatTime(iso: string): string {
  const normalized = /[zZ]$|[+-]\d{2}:?\d{2}$/.test(iso) ? iso : `${iso}Z`
  const date = new Date(normalized)
  if (Number.isNaN(date.getTime())) return iso
  return new Intl.DateTimeFormat('zh-CN', { dateStyle: 'medium', timeStyle: 'short' }).format(date)
}
</script>

<template>
  <div class="flex min-h-dvh flex-col bg-base text-ink">
    <SiteNav />
    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-10 sm:px-6">
      <div class="flex items-center gap-3">
        <h1 class="text-xl font-semibold tracking-tight">我的项目</h1>
        <span
          v-if="store.projects.length"
          class="rounded-md border border-line bg-surface px-1.5 py-0.5 text-xs text-ink-soft"
        >
          {{ store.projects.length }}
        </span>
      </div>

      <p v-if="deleteError" class="mt-4 text-sm text-red-400">删除失败：{{ deleteError }}</p>
      <p v-if="store.loading" class="mt-10 animate-pulse text-sm text-ink-mute">加载中…</p>
      <p v-else-if="store.error" class="mt-10 text-sm text-red-400">加载失败：{{ store.error }}</p>

      <div v-else class="mt-6">
        <div v-if="store.projects.length" class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <article
            v-for="project in store.projects"
            :key="project.id"
            class="flex flex-col gap-4 rounded-xl border border-line bg-surface/50 p-5 transition hover:border-line-strong hover:bg-surface/80"
          >
            <div class="min-w-0">
              <h3 class="truncate text-sm font-medium text-ink" :title="project.title">
                {{ project.title }}
              </h3>
              <p class="mt-1 text-xs text-ink-mute">{{ formatTime(project.created_at) }}</p>
            </div>
            <div class="mt-auto flex items-center gap-2">
              <button
                type="button"
                class="flex-1 rounded-lg bg-emerald-600/90 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500"
                @click="open(project.id)"
              >
                打开
              </button>
              <button
                type="button"
                class="flex-1 rounded-lg border border-line-strong px-3 py-1.5 text-xs font-medium text-ink-soft transition hover:border-red-500/40 hover:text-red-400"
                @click="remove(project)"
              >
                删除
              </button>
            </div>
          </article>
        </div>

        <div
          v-else
          class="flex flex-col items-center gap-4 rounded-xl border border-dashed border-line py-20 text-center"
        >
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
          <p class="text-sm text-ink-mute">还没有项目，从一句话需求开始生成你的第一个应用</p>
          <RouterLink
            to="/"
            class="rounded-xl bg-emerald-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-emerald-500"
          >
            去创建应用
          </RouterLink>
        </div>
      </div>
    </main>
  </div>
</template>
