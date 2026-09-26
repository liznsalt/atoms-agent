import { defineStore } from 'pinia'
import { ref } from 'vue'
import { getMe, login as apiLogin, logout as apiLogout, register as apiRegister, type AuthUser } from '../api'

/** 认证状态（Task 13）：user / ready（首屏 me 探测完成）/ login / register / logout。 */
export const useAuthStore = defineStore('auth', () => {
  const user = ref<AuthUser | null>(null)
  /** 首屏 /api/auth/me 探测完成前路由守卫需要等待，避免已登录用户被闪跳登录页。 */
  const ready = ref(false)

  async function init(): Promise<void> {
    try {
      user.value = await getMe()
    } catch {
      user.value = null
    } finally {
      ready.value = true
    }
  }

  async function login(email: string, password: string): Promise<void> {
    user.value = await apiLogin(email, password)
  }

  async function register(email: string, password: string): Promise<void> {
    user.value = await apiRegister(email, password)
  }

  async function logout(): Promise<void> {
    await apiLogout().catch(() => {})
    user.value = null
  }

  return { user, ready, init, login, register, logout }
})
