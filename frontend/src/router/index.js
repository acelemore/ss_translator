import { createRouter, createWebHistory } from 'vue-router'

// 路由懒加载
const ConfigView = () => import('../views/ConfigView.vue')
const FilesView = () => import('../views/FilesView.vue')
const ReviewView = () => import('../views/ReviewView.vue')
const TerminologyView = () => import('../views/TerminologyView.vue')
const MemoryView = () => import('../views/MemoryView.vue')

const routes = [
  {
    path: '/',
    name: 'Config',
    component: ConfigView,
    meta: { title: '配置管理' }
  },
  {
    path: '/files',
    name: 'Files',
    component: FilesView,
    meta: { title: '文件列表' }
  },
  {
    path: '/review',
    name: 'Review', 
    component: ReviewView,
    meta: { title: '翻译审核' }
  },
  {
    path: '/terminology',
    name: 'Terminology',
    component: TerminologyView,
    meta: { title: '专有名词管理' }
  },
  {
    path: '/memory',
    name: 'Memory',
    component: MemoryView,
    meta: { title: '翻译记忆库' }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// 路由守卫 - 设置页面标题
router.beforeEach((to, from, next) => {
  if (to.meta.title) {
    document.title = `${to.meta.title} - SS Translator`
  }
  next()
})

export default router
