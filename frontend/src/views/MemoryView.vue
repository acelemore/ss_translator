<template>
  <div class="memory-view">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>🧠 翻译记忆库</span>
          <p>查看和管理翻译历史记录</p>
        </div>
      </template>
      
      <div v-if="!appStore.isConfigSelected" class="empty-state">
        <el-empty description="请先选择配置">
          <el-button type="primary" @click="$router.push('/')">
            去配置管理
          </el-button>
        </el-empty>
      </div>
      
      <div v-else>
        <!-- 统计信息 -->
        <div class="stats-section">
          <el-card class="stat-card">
            <div class="stat-content">
              <div class="stat-number">{{ stats.total_count }}</div>
              <div class="stat-label">翻译记录总数</div>
            </div>
            <el-icon class="stat-icon"><Document /></el-icon>
          </el-card>
        </div>

        <!-- 搜索栏 -->
        <div class="search-section">
          <el-card class="search-card">
            <template #header>
              <div class="search-header">
                <span>🔍 搜索条件</span>
                <el-button 
                  type="text" 
                  @click="clearSearch"
                  :disabled="!hasSearchConditions"
                >
                  清空条件
                </el-button>
              </div>
            </template>
            
            <div class="search-fields">
              <div class="search-field">
                <label>文件名:</label>
                <el-input
                  v-model="searchParams.file_name"
                  placeholder="搜索文件名..."
                  clearable
                  @input="handleSearch"
                />
              </div>
              
              <div class="search-field">
                <label>原文:</label>
                <el-input
                  v-model="searchParams.original_text"
                  placeholder="搜索原文..."
                  clearable
                  @input="handleSearch"
                />
              </div>
              
              <div class="search-field">
                <label>审核文本:</label>
                <el-input
                  v-model="searchParams.approved_text"
                  placeholder="搜索审核文本..."
                  clearable
                  @input="handleSearch"
                />
              </div>
              
              <div class="search-field">
                <label>上下文:</label>
                <el-input
                  v-model="searchParams.context"
                  placeholder="搜索上下文..."
                  clearable
                  @input="handleSearch"
                />
              </div>
            </div>
            
            <div class="search-actions">
              <el-button @click="refreshData" :loading="loading">
                <el-icon><Refresh /></el-icon>
                刷新
              </el-button>
            </div>
          </el-card>
        </div>

        <!-- 批量操作栏 -->
        <div class="batch-actions" v-if="selectedRows.length > 0">
          <div class="selected-info">
            已选择 {{ selectedRows.length }} 条记录
          </div>
          <div class="action-buttons">
            <el-button 
              type="danger" 
              @click="batchDelete"
              :loading="batchDeleting"
            >
              <el-icon><Delete /></el-icon>
              批量删除
            </el-button>
            <el-button @click="clearSelection">
              取消选择
            </el-button>
          </div>
        </div>

        <!-- 翻译记录表格 -->
        <el-table 
          ref="tableRef"
          :data="translations" 
          v-loading="loading" 
          stripe
          style="width: 100%"
          @selection-change="handleSelectionChange"
        >
          <el-table-column 
            type="selection" 
            width="55"
          />
          <el-table-column prop="file_name" label="文件名" min-width="200" show-overflow-tooltip>
            <template #default="scope">
              <span v-if="scope.row.file_name" class="file-path">{{ scope.row.file_name }}</span>
              <span v-else class="empty-value">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="original_text" label="原文" min-width="300" show-overflow-tooltip />
          <el-table-column label="是否已审核" width="120" align="center">
            <template #default="scope">
              <el-tag :type="scope.row.approved ? 'success' : 'info'" size="small">
                {{ scope.row.approved ? '已审核' : '未审核' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="approved_text" label="审核后文本" min-width="300" show-overflow-tooltip>
            <template #default="scope">
              <span v-if="scope.row.approved_text" class="approved-text">{{ scope.row.approved_text }}</span>
              <span v-else class="empty-value">-</span>
            </template>
          </el-table-column>
          <el-table-column prop="context" label="上下文" min-width="200" show-overflow-tooltip>
            <template #default="scope">
              <span v-if="scope.row.context" class="context-text">{{ scope.row.context }}</span>
              <span v-else class="empty-value">-</span>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="100" fixed="right">
            <template #default="scope">
              <el-button 
                size="small" 
                type="danger" 
                @click="deleteTranslation(scope.row)"
                :loading="deleting === scope.row.id"
              >
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container">
          <div class="pagination-actions">
            <el-button 
              v-if="translations.length > 0"
              size="small" 
              @click="selectAll"
              :disabled="isAllSelected"
            >
              全选当前页
            </el-button>
            <el-button 
              v-if="selectedRows.length > 0"
              size="small" 
              @click="clearSelection"
            >
              取消选择
            </el-button>
          </div>
          <el-pagination
            :current-page="currentPage"
            :page-size="pageSize"
            :total="totalCount"
            :page-sizes="[10, 20, 50, 100]"
            layout="total, sizes, prev, pager, next, jumper"
            @current-change="handlePageChange"
            @size-change="handleSizeChange"
          />
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, computed, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '../stores/app'
import { memoryAPI } from '../utils/api'

const appStore = useAppStore()

// 数据
const loading = ref(false)
const deleting = ref(null)
const batchDeleting = ref(false)

// 翻译记录数据
const translations = ref([])
const searchParams = ref({
  file_name: '',
  original_text: '',
  approved_text: '',
  context: ''
})
const currentPage = ref(1)
const pageSize = ref(20)
const totalCount = ref(0)

// 统计数据
const stats = ref({
  total_count: 0
})

// 批量选择状态
const selectedRows = ref([])
const tableRef = ref(null)

// 搜索防抖
let searchTimeout = null

// 计算属性
const isAllSelected = computed(() => {
  return translations.value.length > 0 && selectedRows.value.length === translations.value.length
})

const hasSearchConditions = computed(() => {
  return Object.values(searchParams.value).some(value => value.trim())
})

// 方法
const loadData = async () => {
  loading.value = true
  try {
    // 获取翻译记录
    const result = await memoryAPI.getTranslations(
      currentPage.value, 
      pageSize.value, 
      searchParams.value
    )
    
    if (result.success) {
      translations.value = result.data.translations
      totalCount.value = result.data.total_count
    } else {
      ElMessage.error(result.message || '获取翻译记录失败')
    }
    
    // 获取统计信息
    const statsResult = await memoryAPI.getStats()
    if (statsResult.success) {
      stats.value = statsResult.stats
    }
    
  } catch (error) {
    console.error('加载翻译记忆数据失败:', error)
    ElMessage.error('加载翻译记忆数据失败')
  } finally {
    loading.value = false
  }
}

const refreshData = () => {
  loadData()
}

const clearSearch = () => {
  searchParams.value = {
    file_name: '',
    original_text: '',
    approved_text: '',
    context: ''
  }
  currentPage.value = 1
  loadData()
}

const handleSearch = () => {
  // 搜索防抖
  if (searchTimeout) {
    clearTimeout(searchTimeout)
  }
  searchTimeout = setTimeout(() => {
    currentPage.value = 1
    loadData()
  }, 500)
}

const handlePageChange = (page) => {
  currentPage.value = page
  clearSelection() // 清空当前选择
  loadData()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  clearSelection() // 清空当前选择
  loadData()
}

const deleteTranslation = async (row) => {
  try {
    await ElMessageBox.confirm('确定要删除这条翻译记录吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    deleting.value = row.id
    const result = await memoryAPI.deleteTranslation(row.id)
    
    if (result.success) {
      ElMessage.success('删除成功')
      // 重新加载数据
      loadData()
    } else {
      ElMessage.error(result.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除翻译失败:', error)
      ElMessage.error('删除翻译失败')
    }
  } finally {
    deleting.value = null
  }
}

// 批量操作方法
const handleSelectionChange = (selection) => {
  selectedRows.value = selection
}

const selectAll = () => {
  nextTick(() => {
    if (tableRef.value) {
      translations.value.forEach(row => {
        tableRef.value.toggleRowSelection(row, true)
      })
    }
  })
}

const clearSelection = () => {
  selectedRows.value = []
  if (tableRef.value) {
    tableRef.value.clearSelection()
  }
}

const batchDelete = async () => {
  if (selectedRows.value.length === 0) {
    ElMessage.warning('请先选择要删除的记录')
    return
  }
  
  try {
    await ElMessageBox.confirm(
      `确定要删除选中的 ${selectedRows.value.length} 条翻译记录吗？`, 
      '批量删除确认', 
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning'
      }
    )
    
    batchDeleting.value = true
    
    // 获取要删除的ID列表
    const idsToDelete = selectedRows.value.map(row => row.id)
    
    const result = await memoryAPI.batchDeleteTranslations(idsToDelete)
    
    if (result.success) {
      ElMessage.success(`成功删除 ${result.deleted_count} 条记录`)
      // 清空选择
      clearSelection()
      // 重新加载数据
      loadData()
    } else {
      ElMessage.error(result.message || '批量删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('批量删除翻译失败:', error)
      ElMessage.error('批量删除翻译失败')
    }
  } finally {
    batchDeleting.value = false
  }
}

// 监听配置变化
watch(() => appStore.isConfigSelected, (selected) => {
  if (selected) {
    loadData()
  }
})

// 监听配置状态变化
watch(() => appStore.isConfigSelected, (newVal) => {
  if (newVal && translations.value.length === 0) {
    loadData()
  }
})

// 生命周期
onMounted(() => {
  if (appStore.isConfigSelected) {
    loadData()
  }
})
</script>

<style scoped>
.memory-view {
  max-width: 1400px;
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

.card-header p {
  margin: 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.empty-state {
  padding: 40px;
  text-align: center;
}

.stats-section {
  margin-bottom: 20px;
}

.stat-card {
  position: relative;
  overflow: hidden;
  max-width: 300px;
}

.stat-content {
  text-align: center;
}

.stat-number {
  font-size: 32px;
  font-weight: bold;
  color: var(--el-color-primary);
  line-height: 1;
}

.stat-label {
  margin-top: 8px;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.stat-icon {
  position: absolute;
  top: 16px;
  right: 16px;
  font-size: 24px;
  color: var(--el-color-primary-light-5);
}

.search-section {
  margin-bottom: 20px;
}

.search-card .search-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.search-card .search-fields {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 16px;
  margin-bottom: 16px;
}

.search-field label {
  display: block;
  margin-bottom: 4px;
  font-size: 14px;
  color: var(--el-text-color-regular);
  font-weight: 500;
}

.search-card .search-actions {
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--el-border-color-lighter);
  padding-top: 16px;
}

.approved-text {
  color: var(--el-color-success);
  font-weight: 500;
}

.context-text {
  color: var(--el-color-info);
  font-style: italic;
}

.batch-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: var(--el-color-primary-light-9);
  border: 1px solid var(--el-color-primary-light-7);
  border-radius: 4px;
  padding: 12px 16px;
  margin-bottom: 16px;
}

.selected-info {
  color: var(--el-color-primary);
  font-weight: 500;
}

.action-buttons {
  display: flex;
  gap: 8px;
}

.file-path {
  color: var(--el-color-info);
  font-size: 12px;
  font-family: 'Courier New', monospace;
}

.empty-value {
  color: var(--el-color-info-light-5);
  font-style: italic;
}

.pagination-container {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 20px;
}

.pagination-actions {
  display: flex;
  gap: 8px;
}

@media (max-width: 768px) {
  .search-section {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-section el-input {
    width: 100% !important;
  }
  
  .batch-actions {
    flex-direction: column;
    gap: 12px;
  }
  
  .pagination-container {
    flex-direction: column;
    gap: 16px;
  }
  
  .pagination-actions {
    justify-content: center;
  }
}
</style>
