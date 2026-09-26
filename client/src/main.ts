import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'
import { useThemeStore } from './stores/theme'
import './style.css'

const app = createApp(App)
app.use(createPinia())

// 应用持久化主题（深/浅），再探测会话
useThemeStore().apply()

// 先探测会话（/api/auth/me）再装 router：router.install 会触发首次导航，
// 此时守卫的 ready 必为 true，已登录用户不会被闪跳登录页
await useAuthStore().init()

app.use(router)
app.mount('#app')
