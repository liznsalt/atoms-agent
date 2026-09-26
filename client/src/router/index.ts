import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: '/login',
      name: 'login',
      component: () => import('../views/LoginView.vue'),
    },
    {
      path: '/',
      name: 'home',
      component: () => import('../views/HomeView.vue'),
    },
    {
      path: '/projects',
      name: 'projects',
      component: () => import('../views/ProjectsView.vue'),
    },
    {
      path: '/project/:id',
      name: 'project',
      component: () => import('../views/ProjectWorkspaceView.vue'),
    },
    {
      path: '/share/:shareId',
      name: 'share',
      component: () => import('../views/ShareView.vue'),
    },
  ],
})

/** 路由守卫（Task 13）：游客可浏览首页与分享页；工作台/列表需登录，未登录跳登录并携带 redirect。 */
router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name === 'login' || to.name === 'share' || to.name === 'home') return true
  if (!auth.ready) return undefined // 首屏 me 探测未完成，放行由 App 初始化保证时序
  if (!auth.user) {
    return { name: 'login', query: { redirect: to.fullPath } }
  }
  return true
})

export default router
