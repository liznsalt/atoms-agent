<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'
import { useThemeStore } from '../stores/theme'

const router = useRouter()
const auth = useAuthStore()
const theme = useThemeStore()

async function signOut(): Promise<void> {
  await auth.logout()
  await router.push({ name: 'login' })
}
</script>

<template>
  <header class="sticky top-0 z-20 border-b border-line/70 bg-base/85 backdrop-blur">
    <nav class="mx-auto flex h-14 w-full max-w-6xl items-center px-4 sm:px-6">
      <RouterLink to="/" class="flex shrink-0 items-center gap-2.5">
        <span
          class="flex size-7 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 to-indigo-500 text-zinc-950"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="size-5">
            <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
            <ellipse cx="12" cy="12" rx="9" ry="3.6" />
            <ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)" />
            <ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(120 12 12)" />
          </svg>
        </span>
        <span class="text-base font-semibold tracking-tight text-ink">
          Atoms<span class="text-emerald-400"> Agent</span>
        </span>
      </RouterLink>
      <div class="ml-auto flex items-center gap-1 text-sm">
        <RouterLink
          to="/"
          class="rounded-lg px-3 py-1.5 text-ink-soft transition hover:bg-line/60 hover:text-ink"
        >
          首页
        </RouterLink>
        <RouterLink
          to="/projects"
          class="rounded-lg px-3 py-1.5 text-ink-soft transition hover:bg-line/60 hover:text-ink"
        >
          我的项目
        </RouterLink>

        <!-- 主题切换：深/浅 -->
        <button
          type="button"
          :title="theme.theme === 'dark' ? '切换到浅色主题' : '切换到深色主题'"
          class="rounded-lg p-2 text-ink-soft transition hover:bg-line/60 hover:text-ink"
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

        <!-- 用户态：邮箱展示 + 退出；游客显示登录入口 -->
        <div v-if="auth.user" class="ml-2 flex items-center gap-2 border-l border-line pl-3">
          <span
            class="hidden max-w-40 truncate text-xs text-ink-soft sm:inline"
            :title="auth.user.email"
          >
            {{ auth.user.email }}
          </span>
          <button
            type="button"
            class="rounded-lg px-2.5 py-1.5 text-xs text-ink-soft transition hover:bg-line/60 hover:text-ink"
            @click="signOut"
          >
            退出
          </button>
        </div>
        <RouterLink
          v-else
          to="/login"
          class="ml-2 rounded-lg bg-emerald-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-emerald-500"
        >
          登录 / 注册
        </RouterLink>
      </div>
    </nav>
  </header>
</template>
