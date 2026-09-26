import { defineStore } from 'pinia'
import { ref } from 'vue'

export type Theme = 'dark' | 'light'

const STORAGE_KEY = 'atoms-theme'

/** 主题状态：深/浅切换，localStorage 持久化，默认亮色。 */
export const useThemeStore = defineStore('theme', () => {
  const saved = localStorage.getItem(STORAGE_KEY)
  const theme = ref<Theme>(saved === 'dark' ? 'dark' : 'light')

  function apply(): void {
    document.documentElement.classList.toggle('dark', theme.value === 'dark')
  }

  function toggle(): void {
    theme.value = theme.value === 'dark' ? 'light' : 'dark'
    localStorage.setItem(STORAGE_KEY, theme.value)
    apply()
  }

  return { theme, apply, toggle }
})
