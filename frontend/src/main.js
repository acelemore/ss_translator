import { createApp } from 'vue'
import ElementPlus from 'element-plus'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'
import 'element-plus/dist/index.css'
import 'element-plus/theme-chalk/dark/css-vars.css'

import App from './App.vue'
import router from './router'
import { createPinia } from 'pinia'

// 导入自定义指令
import { vLoadingClick } from './directives/loadingClick.js'

const app = createApp(App)
const pinia = createPinia()

// 注册所有 Element Plus 图标
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component)
}

// 注册自定义指令
app.directive('loading-click', vLoadingClick)

app.use(pinia)
app.use(router)
app.use(ElementPlus)
app.mount('#app')
