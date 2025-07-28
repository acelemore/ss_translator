<template>
  <div class="terminology-view">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>📚 专有名词管理</span>
          <p>管理翻译中的专业术语和固定译名</p>
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
        <!-- 操作栏 -->
        <div class="operations-bar">
          <div class="search-section">
            <el-input
              v-model="searchText"
              placeholder="搜索术语或译名..."
              style="width: 300px;"
              clearable
            >
              <template #prefix>
                <el-icon><Search /></el-icon>
              </template>
            </el-input>
            <el-select v-model="categoryFilter" style="width: 150px; margin-left: 12px;">
              <el-option label="全部分类" value="" />
              <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
            </el-select>
          </div>
          <div class="action-buttons">
            <el-button type="primary" @click="showAddDialog = true">
              <el-icon><Plus /></el-icon>
              添加术语
            </el-button>
            <el-button @click="importTerms">
              <el-icon><Upload /></el-icon>
              导入
            </el-button>
            <el-button @click="exportTerms">
              <el-icon><Download /></el-icon>
              导出
            </el-button>
          </div>
        </div>

        <!-- 术语列表 -->
        <el-table 
          :data="filteredTerms" 
          style="width: 100%" 
          v-loading="loading"
          stripe
        >
          <el-table-column prop="term" label="原术语" min-width="150">
            <template #default="scope">
              <el-text type="primary">{{ scope.row.term }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="translation" label="译名" min-width="150">
            <template #default="scope">
              <el-text v-if="scope.row.translation" type="primary">
                {{ scope.row.translation }}
              </el-text>
              <el-text v-else type="info">未翻译</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="domain" label="分类" width="120">
            <template #default="scope">
              <el-tag v-if="scope.row.domain" size="small">
                {{ scope.row.domain }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="notes" label="说明" min-width="200" show-overflow-tooltip />
          <el-table-column prop="frequency" label="使用频率" width="100" sortable>
            <template #default="scope">
              <el-text>{{ scope.row.frequency || 0 }}</el-text>
            </template>
          </el-table-column>
          <el-table-column prop="lastUsed" label="最后使用" width="120">
            <template #default="scope">
              <el-text type="info" size="small">
                {{ formatDate(scope.row.lastUsed) }}
              </el-text>
            </template>
          </el-table-column>
          <el-table-column label="操作" width="150" fixed="right">
            <template #default="scope">
              <el-button type="primary" size="small" @click="editTerm(scope.row)">
                编辑
              </el-button>
              <el-button type="danger" size="small" @click="deleteTerm(scope.row)">
                删除
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <!-- 分页 -->
        <div class="pagination-container">
          <el-pagination
            v-model="currentPage"
            :page-size="pageSize"
            :total="filteredTerms.length"
            layout="prev, pager, next, jumper, total"
          />
        </div>

        <!-- 添加/编辑对话框 -->
        <el-dialog
          v-model="showAddDialog"
          :title="editingTerm ? '编辑术语' : '添加术语'"
          width="600px"
        >
          <el-form :model="termForm" label-width="80px" ref="termFormRef">
            <el-form-item label="原术语" prop="term" :rules="[{ required: true, message: '请输入原术语' }]">
              <el-input v-model="termForm.term" placeholder="请输入原术语" />
            </el-form-item>
            <el-form-item label="译名" prop="translation">
              <el-input v-model="termForm.translation" placeholder="请输入译名" />
            </el-form-item>
            <el-form-item label="分类" prop="domain">
              <el-select v-model="termForm.domain" placeholder="选择或输入分类" filterable allow-create>
                <el-option v-for="cat in categories" :key="cat" :label="cat" :value="cat" />
              </el-select>
            </el-form-item>
            <el-form-item label="说明" prop="notes">
              <el-input 
                v-model="termForm.notes" 
                type="textarea" 
                :rows="3" 
                placeholder="术语说明或使用场景" 
              />
            </el-form-item>
          </el-form>
          
          <template #footer>
            <el-button @click="showAddDialog = false">取消</el-button>
            <el-button type="primary" @click="saveTerm" :loading="saving">确定</el-button>
          </template>
        </el-dialog>

        <!-- 导入对话框 -->
        <el-dialog v-model="showImportDialog" title="导入术语" width="500px">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :on-change="handleFileChange"
            :show-file-list="false"
            accept=".json"
            drag
          >
            <el-icon class="el-icon--upload"><upload-filled /></el-icon>
            <div class="el-upload__text">
              将文件拖到此处，或<em>点击上传</em>
            </div>
            <template #tip>
              <div class="el-upload__tip">
                只支持 JSON 格式文件
              </div>
            </template>
          </el-upload>
          
          <div v-if="selectedFile" class="selected-file-info">
            <el-alert
              :title="`已选择文件: ${selectedFile.name}`"
              type="success"
              :closable="false"
              show-icon
            />
          </div>
          
          <template #footer>
            <el-button @click="showImportDialog = false; selectedFile = null">取消</el-button>
            <el-button 
              type="primary" 
              @click="confirmImport" 
              :loading="importing"
              :disabled="!selectedFile"
            >
              导入
            </el-button>
          </template>
        </el-dialog>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAppStore } from '../stores/app'
import { terminologyAPI } from '../utils/api'

const appStore = useAppStore()

// 数据
const terms = ref([])
const searchText = ref('')
const categoryFilter = ref('')
const currentPage = ref(1)
const pageSize = ref(20)
const loading = ref(false)
const saving = ref(false)
const importing = ref(false)
const selectedFile = ref(null)

// 对话框状态
const showAddDialog = ref(false)
const showImportDialog = ref(false)
const editingTerm = ref(null)
const termForm = ref({
  term: '',
  translation: '',
  domain: '',
  notes: ''
})
const termFormRef = ref()

// 计算属性
const filteredTerms = computed(() => {
  let filtered = terms.value

  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    filtered = filtered.filter(term =>
      term.term.toLowerCase().includes(search) ||
      (term.translation && term.translation.toLowerCase().includes(search)) ||
      (term.notes && term.notes.toLowerCase().includes(search))
    )
  }

  if (categoryFilter.value) {
    filtered = filtered.filter(term => term.domain === categoryFilter.value)
  }

  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filtered.slice(start, end)
})

const categories = computed(() => {
  const cats = new Set()
  terms.value.forEach(term => {
    if (term.domain) {
      cats.add(term.domain)
    }
  })
  return Array.from(cats).sort()
})

// 方法
const loadTerms = async () => {
  loading.value = true
  try {
    const data = await terminologyAPI.getTerminologyList()
    if (data.success) {
      terms.value = data.terms || []
    } else {
      ElMessage.error(data.message || '加载术语列表失败')
    }
  } catch (error) {
    console.error('加载术语列表失败:', error)
    ElMessage.error('加载术语列表失败')
  } finally {
    loading.value = false
  }
}

const editTerm = (term) => {
  editingTerm.value = term
  termForm.value = { ...term }
  showAddDialog.value = true
}

const saveTerm = async () => {
  try {
    await termFormRef.value.validate()
    saving.value = true
    
    if (editingTerm.value) {
      // 更新现有术语 - 需要先删除再添加，因为后端API没有更新接口
      await terminologyAPI.deleteTerminology(editingTerm.value.term)
      await terminologyAPI.addTerminology(
        termForm.value.term,
        termForm.value.translation,
        termForm.value.domain || 'general',
        termForm.value.notes || ''
      )
      ElMessage.success('术语更新成功')
    } else {
      // 添加新术语
      const result = await terminologyAPI.addTerminology(
        termForm.value.term,
        termForm.value.translation,
        termForm.value.domain || 'general',
        termForm.value.notes || ''
      )
      if (result.success) {
        ElMessage.success('术语添加成功')
      } else {
        ElMessage.error(result.message || '术语添加失败')
      }
    }
    
    showAddDialog.value = false
    resetForm()
    await loadTerms() // 重新加载列表
  } catch (error) {
    console.error('保存术语失败:', error)
    ElMessage.error('保存失败')
  } finally {
    saving.value = false
  }
}

const deleteTerm = async (term) => {
  try {
    await ElMessageBox.confirm('确定要删除这个术语吗？', '删除确认', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning'
    })
    
    const result = await terminologyAPI.deleteTerminology(term.term)
    if (result.success) {
      ElMessage.success('术语删除成功')
      await loadTerms() // 重新加载列表
    } else {
      ElMessage.error(result.message || '删除失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('删除术语失败:', error)
      ElMessage.error('删除失败')
    }
  }
}

const resetForm = () => {
  termForm.value = {
    term: '',
    translation: '',
    domain: '',
    notes: ''
  }
  editingTerm.value = null
}

const importTerms = () => {
  showImportDialog.value = true
}

const exportTerms = async () => {
  try {
    await terminologyAPI.exportTerminology()
    ElMessage.success('导出完成')
  } catch (error) {
    console.error('导出失败:', error)
    ElMessage.error('导出失败')
  }
}

const handleFileChange = (file) => {
  selectedFile.value = file.raw
  ElMessage.success(`已选择文件: ${file.name}`)
}

const confirmImport = async () => {
  if (!selectedFile.value) {
    ElMessage.warning('请先选择文件')
    return
  }
  
  try {
    importing.value = true
    const result = await terminologyAPI.importTerminology(selectedFile.value)
    
    if (result.success) {
      ElMessage.success(result.message)
      showImportDialog.value = false
      selectedFile.value = null
      await loadTerms() // 重新加载数据
    } else {
      ElMessage.error(result.message || '导入失败')
    }
  } catch (error) {
    console.error('导入失败:', error)
    ElMessage.error('导入失败')
  } finally {
    importing.value = false
  }
}

const formatDate = (date) => {
  if (!date) return '-'
  return new Date(date).toLocaleDateString()
}

// 监听配置状态变化
watch(() => appStore.isConfigSelected, (newVal) => {
  if (newVal && terms.value.length === 0) {
    loadTerms()
  }
})

// 生命周期
onMounted(() => {
  if (appStore.isConfigSelected) {
    loadTerms()
  }
})
</script>

<style scoped>
.terminology-view {
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

.operations-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.search-section {
  display: flex;
  align-items: center;
}

.action-buttons {
  display: flex;
  gap: 12px;
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

.selected-file-info {
  margin-top: 16px;
}

@media (max-width: 768px) {
  .operations-bar {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-section {
    flex-direction: column;
    gap: 12px;
  }
  
  .action-buttons {
    justify-content: center;
  }
}
</style>
