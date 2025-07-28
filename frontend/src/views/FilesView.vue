<template>
  <div class="files-view">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>📁 文件列表</span>
          <div class="header-actions">
            <el-button 
              type="primary" 
              @click="startAllTranslation"
              :disabled="!appStore.isConfigSelected || appStore.isTranslating || startingTranslation"
              :loading="startingTranslation"
            >
              开始翻译所有文件
            </el-button>
            <el-button 
              type="danger" 
              @click="stopTranslation"
              :disabled="!appStore.isTranslating || stoppingTranslation"
              :loading="stoppingTranslation"
              v-if="appStore.isTranslating"
            >
              <el-icon v-if="!stoppingTranslation"><CircleClose /></el-icon>
              {{ stoppingTranslation ? '停止中...' : '停止翻译' }}
            </el-button>
            <el-button @click="refreshFiles">
              <el-icon><Refresh /></el-icon>
              刷新
            </el-button>
          </div>
        </div>
      </template>
      
      <!-- 翻译状态显示 -->
      <div v-if="appStore.currentConfig" class="status-bar">
        <el-alert
          :title="statusText"
          :type="getStatusAlertType()"
          :closable="false"
          show-icon
        />
      </div>
      <div v-else class="status-bar">
        <el-alert
          title="请先选择配置"
          type="warning"
          :closable="false"
          show-icon
        />
      </div>
    </el-card>

    <!-- 文件列表 -->
    <el-card v-if="appStore.isConfigSelected">
      <template #header>
        <div class="files-header">
          <span>文件列表</span>
          <el-button 
            type="danger" 
            size="small"
            @click="resetAllProgress"
            :disabled="appStore.isTranslating || stoppingTranslation || resettingAll"
            :loading="resettingAll"
          >
            重置所有文件
          </el-button>
        </div>
      </template>
      
      <div v-if="files.length === 0" class="empty-state">
        <el-empty description="暂无文件数据">
          <el-button type="primary" @click="refreshFiles">刷新文件列表</el-button>
        </el-empty>
      </div>
      
      <div v-else class="files-list">
        <div v-for="file in files" :key="file.path" class="file-item">
          <el-card shadow="hover">
            <div class="file-content">
              <div class="file-info">
                <div class="file-header">
                  <h4 class="file-path">{{ file.path }}</h4>
                  <el-tag 
                    :type="getStatusType(file.status)"
                    :class="{'no-content-tag': file.status === '无可翻译内容'}"
                  >
                    {{ file.status }}
                  </el-tag>
                </div>
                <p class="file-description">{{ file.description }}</p>
                <div class="file-details">
                  <el-tag size="small">{{ file.type.toUpperCase() }}</el-tag>
                  <!-- <span class="field-count">{{ file.fields.length }} 个字段</span> -->
                  <span class="progress-text">{{ file.progress }}/{{ file.total_lines }}</span>
                </div>
              </div>
              
              <div class="file-progress">
                <el-progress
                  :percentage="getProgressPercentage(file)"
                  :status="file.completed ? 'success' : undefined"
                  :stroke-width="8"
                />
              </div>
              
              <div class="file-actions">
                <el-button-group>
                  <el-button 
                    size="small" 
                    @click="startTranslation(file.path)"
                    :disabled="appStore.isTranslating || startingTranslation"
                    :loading="startingTranslation"
                  >
                    开始翻译
                  </el-button>
                  <el-button 
                    size="small" 
                    type="warning"
                    @click="resetProgress(file.path)"
                    :disabled="appStore.isTranslating || stoppingTranslation"
                  >
                    重置进度
                  </el-button>
                </el-button-group>
              </div>
            </div>
          </el-card>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { CircleClose, Refresh } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app'
import { progressAPI, translationAPI } from '../utils/api'

const appStore = useAppStore()

// 数据
const files = ref([])
const loading = ref(false)
const startingTranslation = ref(false)
const stoppingTranslation = ref(false)  // 添加停止翻译状态
const resettingAll = ref(false)  // 添加重置所有文件状态
let statusTimer = null

// 计算属性
const statusText = computed(() => {
  const status = appStore.translationStatus
  if (status.running) {
    return `正在翻译: ${status.current_file} (进度: ${status.progress}%)`
  }
  
  // 检查是否是中断状态
  if (status.status === 'interrupted' || stoppingTranslation.value) {
    return '正在停止翻译，请稍候...'
  }
  
  return '翻译服务就绪'
})

// 获取状态警告框类型
const getStatusAlertType = () => {
  const status = appStore.translationStatus
  if (status.running) {
    return 'info'
  }
  if (status.status === 'interrupted' || stoppingTranslation.value) {
    return 'warning'
  }
  return 'success'
}

// 方法
const refreshFiles = async () => {
  if (!appStore.isConfigSelected) {
    ElMessage.warning('请先选择配置')
    return
  }
  
  try {
    loading.value = true
    const data = await progressAPI.getFiles()
    if (data.error) {
      ElMessage.error(data.error)
    } else {
      files.value = data
    }
  } catch (error) {
    ElMessage.error('加载文件列表失败')
  } finally {
    loading.value = false
  }
}

const startTranslation = async (filePath) => {
  if (startingTranslation.value) return
  
  try {
    startingTranslation.value = true
    const result = await translationAPI.startTranslation(filePath)
    if (result.success) {
      ElMessage.success(result.message)
      
      // 立即刷新状态和文件列表
      await appStore.updateTranslationStatus()
      await refreshFiles()
      
      // 启动状态轮询
      startStatusPolling()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    console.error('启动翻译失败:', error)
    ElMessage.error('启动翻译失败')
  } finally {
    startingTranslation.value = false
  }
}

const startAllTranslation = async () => {
  if (startingTranslation.value) return
  
  try {
    startingTranslation.value = true
    const result = await translationAPI.startTranslation(null)
    if (result.success) {
      ElMessage.success('开始翻译所有文件')
      
      // 立即刷新状态和文件列表
      await appStore.updateTranslationStatus()
      await refreshFiles()
      
      // 启动状态轮询
      startStatusPolling()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    console.error('启动翻译失败:', error)
    ElMessage.error('启动翻译失败')
  } finally {
    startingTranslation.value = false
  }
}

const stopTranslation = async () => {
  if (stoppingTranslation.value) return
  
  try {
    // 添加二次确认
    await ElMessageBox.confirm(
      '确定要停止当前的翻译任务吗？停止后当前正在翻译的进度将被保存。',
      '确认停止翻译',
      {
        type: 'warning',
        confirmButtonText: '确定停止',
        cancelButtonText: '取消'
      }
    )
    
    stoppingTranslation.value = true
    const result = await translationAPI.stopTranslation()
    if (result.success) {
      ElMessage.success(result.message)
      
      // 立即刷新状态
      await appStore.updateTranslationStatus()
      
      // 启动状态轮询以监控停止过程
      startStatusPolling()
    } else {
      ElMessage.error(result.message)
      stoppingTranslation.value = false
    }
  } catch (error) {
    if (error === 'cancel') {
      // 用户取消了操作，不显示错误信息
      return
    }
    console.error('停止翻译失败:', error)
    ElMessage.error('停止翻译失败')
    stoppingTranslation.value = false
  }
  // 注意：如果确认并成功发送停止请求，不立即设置为false
  // 我们需要等待翻译状态真正变为非运行状态
}

const resetProgress = async (filePath) => {
  // 检查是否可以重置进度
  if (appStore.isTranslating || stoppingTranslation.value) {
    ElMessage.warning('翻译进行中或正在停止时无法重置进度')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      '重置进度会删除已翻译的临时文件, 是否确认?',
      '确认重置',
      { 
        type: 'warning',
        confirmButtonText: '确定重置',
        cancelButtonText: '取消'
      }
    )
    
    const result = await translationAPI.resetProgress(filePath)
    if (result.success) {
      ElMessage.success(result.message)
      await refreshFiles()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置进度失败')
    }
  }
}

const resetAllProgress = async () => {
  // 检查是否可以重置进度
  if (appStore.isTranslating || stoppingTranslation.value) {
    ElMessage.warning('翻译进行中或正在停止时无法重置进度')
    return
  }
  
  if (resettingAll.value) return
  
  try {
    await ElMessageBox.confirm(
      '确定要重置所有文件的翻译进度吗？这将删除所有已翻译的临时文件，此操作不可撤销。',
      '确认重置所有文件',
      { 
        type: 'warning',
        confirmButtonText: '确定重置所有',
        cancelButtonText: '取消',
        dangerouslyUseHTMLString: true,
        message: `<div>
          <p><strong>警告：此操作将：</strong></p>
          <ul style="text-align: left; margin: 10px 0;">
            <li>清空所有文件的翻译进度</li>
            <li>删除所有已翻译的临时文件</li>
            <li>无法撤销此操作</li>
          </ul>
          <p>请确认您真的要重置所有文件的进度。</p>
        </div>`
      }
    )
    
    resettingAll.value = true
    const result = await translationAPI.resetProgress(null)  // 不传参数表示重置所有
    if (result.success) {
      ElMessage.success('所有文件进度已重置')
      await refreshFiles()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('重置所有文件进度失败')
    }
  } finally {
    resettingAll.value = false
  }
}

const getProgressPercentage = (file) => {
  if (file.total_lines === 0) return 0
  return Math.round((file.progress / file.total_lines) * 100)
}

const getStatusType = (status) => {
  switch (status) {
    case '已完成': return 'success'
    case '翻译中': return 'warning'
    case '无可翻译内容': return 'success'
    case '未开始': return 'info'
    case '正在停止': return 'warning'
    case '已中断': return 'info'
    default: return 'info'
  }
}

const startStatusPolling = () => {
  if (statusTimer) return
  
  statusTimer = setInterval(async () => {
    await appStore.updateTranslationStatus()
    await refreshFiles()
    
    // 如果翻译完成且不是中断状态，停止轮询
    if (!appStore.isTranslating) {
      stopStatusPolling()
      // 重置停止状态
      stoppingTranslation.value = false
    }
  }, 3000)
}

const stopStatusPolling = () => {
  if (statusTimer) {
    clearInterval(statusTimer)
    statusTimer = null
  }
  // 确保在停止轮询时重置状态
  stoppingTranslation.value = false
}

// 监听配置状态变化
watch(() => appStore.isConfigSelected, (newVal) => {
  if (newVal && files.value.length === 0) {
    refreshFiles()
  }
})

// 生命周期
onMounted(async () => {
  if (appStore.isConfigSelected) {
    await refreshFiles()
  }
  
  // 更新翻译状态
  await appStore.updateTranslationStatus()
  
  // 如果正在翻译，启动状态轮询
  if (appStore.isTranslating) {
    startStatusPolling()
    
    // 如果状态是interrupted，可能是从停止状态刷新页面，需要设置stopping状态
    if (appStore.translationStatus.status === 'interrupted') {
      stoppingTranslation.value = true
    }
  }
})

onUnmounted(() => {
  stopStatusPolling()
  // 重置所有状态
  stoppingTranslation.value = false
})
</script>

<style scoped>
.files-view {
  max-width: 1200px;
  margin: 0 auto;
  padding: 20px;
  min-height: 100%;
  box-sizing: border-box;
}

.header-card {
  margin-bottom: 20px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.card-header span {
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.status-bar {
  margin-top: 16px;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.empty-state {
  padding: 40px;
  text-align: center;
}

.files-list {
  display: grid;
  gap: 16px;
}

.file-item {
  border-radius: 8px;
  overflow: hidden;
}

.file-content {
  display: grid;
  grid-template-columns: 1fr auto auto;
  gap: 20px;
  align-items: center;
}

.file-info {
  flex: 1;
}

.file-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.file-path {
  margin: 0;
  font-size: 16px;
  font-weight: 500;
  color: var(--el-text-color-primary);
}

.file-description {
  margin: 0 0 8px 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.file-details {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 14px;
}

.field-count,
.progress-text {
  color: var(--el-text-color-secondary);
}

.file-progress {
  min-width: 200px;
}

.file-actions {
  min-width: 150px;
  text-align: right;
}

@media (max-width: 768px) {
  .file-content {
    grid-template-columns: 1fr;
    gap: 16px;
  }
  
  .file-progress,
  .file-actions {
    min-width: auto;
  }
  
  .file-actions {
    text-align: left;
  }
}

/* 自定义无可翻译内容状态的颜色 */
.no-content-tag.el-tag--success {
  --el-tag-bg-color: #f0f9a0;
  --el-tag-border-color: #b8d966;
  --el-tag-text-color: #5a7a2d;
}

.no-content-tag.el-tag--success:hover {
  background-color: #e6f47a;
  border-color: #a6cc52;
}
</style>
