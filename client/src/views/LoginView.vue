<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = useRouter()
const auth = useAuthStore()

type Mode = 'login' | 'register'

const mode = ref<Mode>(router.currentRoute.value.query.mode === 'register' ? 'register' : 'login')
const email = ref('')
const password = ref('')
const showPassword = ref(false)
const submitting = ref(false)
const error = ref('')

/** 密码框类型随可见性切换；隐藏时 type=password 才能触发浏览器密码管理器保存。 */
const passwordType = computed(() => (showPassword.value ? 'text' : 'password'))

/** 登录/注册切换：清密码与错误，保留邮箱（常见习惯：同一邮箱试两种流程）。 */
function switchMode(next: Mode): void {
  if (mode.value === next) return
  mode.value = next
  password.value = ''
  showPassword.value = false
  error.value = ''
}

/** 登录/注册成功 → 回首页（若带 redirect 查询参数则回跳）。 */
async function submit(): Promise<void> {
  if (submitting.value) return
  submitting.value = true
  error.value = ''
  try {
    // 浏览器密码管理器自动填充不触发 v-model 的 input 事件，
    // 提交前直接从 DOM 读值兜底（@change 已同步大部分场景）
    const domEmail = document.querySelector<HTMLInputElement>('input[type=email]')?.value.trim()
    const domPassword =
      document.querySelector<HTMLInputElement>('#password-input')?.value ?? password.value
    const finalEmail = domEmail || email.value.trim()
    const finalPassword = domPassword || password.value
    if (!finalEmail) {
      error.value = '请输入邮箱'
      return
    }
    if (!finalPassword) {
      error.value = '请输入密码'
      return
    }
    if (mode.value === 'login') {
      await auth.login(finalEmail, finalPassword)
    } else {
      await auth.register(finalEmail, finalPassword)
    }
    // 回跳 redirect；未登录发起生成携带的 prompt 一并透传（首页会自动继续生成）
    const { redirect, prompt: carried } = router.currentRoute.value.query
    if (typeof redirect === 'string' && redirect.startsWith('/')) {
      await router.push(
        typeof carried === 'string' && carried.trim()
          ? { path: redirect, query: { prompt: carried } }
          : redirect,
      )
    } else {
      await router.push('/')
    }
  } catch (err) {
    error.value = err instanceof Error ? err.message : String(err)
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="flex min-h-dvh flex-col items-center justify-center gap-8 bg-base px-4 text-ink">
    <RouterLink to="/login" class="flex items-center gap-2.5" @click.prevent>
      <span class="flex size-8 items-center justify-center rounded-lg bg-gradient-to-br from-emerald-400 to-indigo-500 text-zinc-950">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" class="size-5">
          <circle cx="12" cy="12" r="1.6" fill="currentColor" stroke="none" />
          <ellipse cx="12" cy="12" rx="9" ry="3.6" />
          <ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(60 12 12)" />
          <ellipse cx="12" cy="12" rx="9" ry="3.6" transform="rotate(120 12 12)" />
        </svg>
      </span>
      <span class="text-lg font-semibold tracking-tight">
        Atoms<span class="text-emerald-400"> Agent</span>
      </span>
    </RouterLink>

    <div class="w-full max-w-sm rounded-2xl border border-line bg-surface/70 p-6 shadow-2xl shadow-black/40">
      <!-- 登录 / 注册切换 -->
      <div class="mb-5 flex rounded-lg border border-line bg-base/60 p-0.5">
        <button
          v-for="item in (['login', 'register'] as Mode[])"
          :key="item"
          type="button"
          class="flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition"
          :class="mode === item ? 'bg-line-strong/80 text-ink' : 'text-ink-soft hover:text-ink'"
          @click="switchMode(item)"
        >
          {{ item === 'login' ? '登录' : '注册' }}
        </button>
      </div>

      <form class="space-y-4" novalidate @submit.prevent="submit">
        <label class="block">
          <span class="mb-1.5 block text-xs text-ink-soft">邮箱</span>
          <input
            v-model="email"
            type="email"
            name="email"
            autocomplete="email"
            placeholder="you@example.com"
            class="w-full rounded-xl border border-line bg-base/70 px-3.5 py-2.5 text-sm text-ink placeholder:text-line-strong outline-none transition focus:border-emerald-500/40"
            @change="email = ($event.target as HTMLInputElement).value"
          />
        </label>
        <label class="block">
          <span class="mb-1.5 block text-xs text-ink-soft">
            密码{{ mode === 'register' ? '（至少 6 位）' : '' }}
          </span>
          <div class="relative">
            <input
              id="password-input"
              v-model="password"
              :type="passwordType"
              name="password"
              :autocomplete="mode === 'login' ? 'current-password' : 'new-password'"
              placeholder="••••••••"
              class="w-full rounded-xl border border-line bg-base/70 px-3.5 py-2.5 pr-11 text-sm text-ink placeholder:text-line-strong outline-none transition focus:border-emerald-500/40"
              @change="password = ($event.target as HTMLInputElement).value"
            />
            <button
              type="button"
              :title="showPassword ? '隐藏密码' : '显示密码'"
              class="absolute inset-y-0 right-0 flex w-10 items-center justify-center rounded-r-xl text-ink-soft transition hover:text-ink"
              @click="showPassword = !showPassword"
            >
              <svg v-if="showPassword" class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  d="M3.98 8.223A10.477 10.477 0 001.934 12C3.226 16.338 7.244 19.5 12 19.5c.993 0 1.953-.138 2.863-.395M6.228 6.228A10.45 10.45 0 0112 4.5c4.756 0 8.773 3.162 10.065 7.498a10.523 10.523 0 01-4.293 5.774M6.228 6.228L3 3m3.228 3.228l3.65 3.65m7.894 7.894L21 21m-3.228-3.228l-3.65-3.65m0 0a3 3 0 10-4.243-4.243"
                />
              </svg>
              <svg v-else class="size-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
                <path stroke-linecap="round" stroke-linejoin="round" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z" />
                <path stroke-linecap="round" stroke-linejoin="round" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
              </svg>
            </button>
          </div>
        </label>

        <!-- 错误提示：红色圆点 + 文案，语义明确 -->
        <p
          v-if="error"
          class="flex items-start gap-1.5 rounded-lg border border-red-500/25 bg-red-500/10 px-3 py-2 text-xs leading-relaxed text-red-400"
        >
          <svg class="mt-px size-3.5 shrink-0" viewBox="0 0 20 20" fill="currentColor">
            <path
              fill-rule="evenodd"
              d="M10 18a8 8 0 100-16 8 8 0 000 16zm-1-5a1 1 0 112 0 1 1 0 01-2 0zm1-8a.75.75 0 01.75.75v4.5a.75.75 0 11-1.5 0v-4.5A.75.75 0 0110 5z"
              clip-rule="evenodd"
            />
          </svg>
          {{ error }}
        </p>

        <button
          type="submit"
          :disabled="submitting"
          class="w-full rounded-xl bg-emerald-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-emerald-500 disabled:cursor-not-allowed disabled:bg-line-strong disabled:text-ink-soft"
        >
          {{ submitting
            ? (mode === 'login' ? '登录中…' : '注册中…')
            : mode === 'login' ? '登录' : '注册并登录' }}
        </button>
      </form>

      <p class="mt-4 text-center text-[11px] text-line-strong">
        {{ mode === 'login' ? '没有账号？切换到注册一键创建' : '已有账号？切换到登录' }}
      </p>
    </div>
  </div>
</template>
