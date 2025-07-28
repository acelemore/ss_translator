<template>
  <div id="app" class="translation-app">
    <!-- 顶部导航栏 -->
    <header class="app-header">
      <div class="header-content">
        <h1 class="app-title">
          <el-icon><DocumentCopy /></el-icon>
          StarSector模组翻译工具
        </h1>
        <div class="header-actions">
          <el-button @click="toggleTheme" circle>
            <el-icon><Moon v-if="!isDark" /><Sunny v-else /></el-icon>
          </el-button>
        </div>
      </div>
    </header>

    <!-- 侧边栏 -->
    <aside class="app-sidebar">
      <el-menu
        :default-active="activeMenu"
        router
        class="sidebar-menu"
      >
        <el-menu-item index="/">
          <el-icon><Setting /></el-icon>
          <span>配置管理</span>
        </el-menu-item>
        <el-menu-item index="/files">
          <el-icon><Folder /></el-icon>
          <span>文件列表</span>
        </el-menu-item>
        <el-menu-item index="/review">
          <el-icon><Edit /></el-icon>
          <span>翻译审核</span>
        </el-menu-item>
        <el-menu-item index="/terminology">
          <el-icon><Document /></el-icon>
          <span>专有名词</span>
        </el-menu-item>
        <el-menu-item index="/memory">
          <el-icon><DataAnalysis /></el-icon>
          <span>翻译记忆</span>
        </el-menu-item>
      </el-menu>
      
      <!-- 底部信息 -->
      <div class="sidebar-footer">
        <div class="app-info">
          <div class="version">v1.0.0</div>
          <div class="author">Developed by Acelemore</div>
        </div>
      </div>
    </aside>

    <!-- 主内容区域 -->
    <main class="app-main">
      <router-view />
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue'
import { useDark, useToggle } from '@vueuse/core'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from './stores/app'

const appStore = useAppStore()

// 主题切换配置
const isDark = useDark({
  selector: 'html',
  attribute: 'class',
  valueDark: 'dark',
  valueLight: '',
  // 默认使用系统主题
  initialValue: 'auto'
})

const toggleTheme = () => {
  isDark.value = !isDark.value
}

// 监听主题变化，确保正确应用到页面
watch(isDark, (dark) => {
  const html = document.documentElement
  if (dark) {
    html.classList.add('dark')
    html.setAttribute('data-theme', 'dark')
  } else {
    html.classList.remove('dark')
    html.setAttribute('data-theme', 'light')
  }
}, { immediate: true })

const router = useRouter()
const route = useRoute()
const activeMenu = ref('/')

onMounted(async () => {
  // 根据当前路由设置活跃菜单
  activeMenu.value = route.path
  
  // 监听路由变化
  router.afterEach((to) => {
    activeMenu.value = to.path
  })
  
  // 应用初始化：自动获取当前配置和基础数据
  try {
    await Promise.all([
      appStore.loadConfigs(),
      appStore.getCurrentConfig()
    ])
  } catch (error) {
    console.error('应用初始化失败:', error)
    // 不显示错误消息，因为用户可能还没有配置
  }
})
</script>

<style scoped>
.translation-app {
  height: 100vh;
  overflow: hidden;
}

.app-header {
  background: var(--el-color-primary);
  color: white;
  display: flex;
  align-items: center;
  padding: 0 20px;
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  height: 60px;
  z-index: 1000;
  box-shadow: 0 2px 4px rgba(0,0,0,0.1);
}

.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.app-title {
  margin: 0;
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 20px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.app-sidebar {
  background: var(--el-bg-color);
  border-right: 1px solid var(--el-border-color);
  display: flex;
  flex-direction: column;
  position: fixed;
  top: 60px;
  left: 0;
  width: 200px;
  height: calc(100vh - 60px);
  z-index: 999;
  overflow-y: auto;
}

.sidebar-menu {
  border: none;
  flex: 1;
}

.sidebar-footer {
  padding: 16px 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  margin-top: auto;
  background: var(--el-bg-color);
}

.app-info {
  text-align: center;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.version {
  font-weight: 600;
  color: var(--el-text-color-regular);
  margin-bottom: 4px;
  font-family: 'Monaco', 'Consolas', monospace;
}

.author {
  font-size: 11px;
  opacity: 0.8;
}

.app-main {
  background: var(--el-bg-color-page);
  position: fixed;
  top: 60px;
  left: 200px;
  right: 0;
  bottom: 0;
  overflow-y: auto;
  padding: 0;
}

:deep(.el-menu-item) {
  height: 50px;
  line-height: 50px;
}

:deep(.el-menu-item.is-active) {
  background-color: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
}

/* 响应式布局 */
@media (max-width: 768px) {
  .app-sidebar {
    transform: translateX(-100%);
    transition: transform 0.3s ease;
  }
  
  .app-main {
    left: 0;
  }
  
  /* 可以添加移动端侧边栏切换功能 */
}
</style>
