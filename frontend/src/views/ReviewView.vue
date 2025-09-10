<template>
  <div class="review-view">
    <el-card class="header-card">
      <template #header>
        <div class="card-header">
          <span>📝 翻译审核</span>
          <p>审核和编辑翻译内容</p>
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
        <!-- 翻译文件列表 -->
                  <div v-if="!selectedFile" class="files-section">
            <div class="files-header">
              <h3>选择要审核的翻译文件</h3>
              <div class="header-actions">
                <el-button
                  type="success"
                  :loading="exportingPackage"
                  @click="exportTranslationPackage"
                  icon="Download"
                >
                  导出汉化包
                </el-button>
                <el-button
                  type="primary"
                  :disabled="!canApplyAllTranslations"
                  :loading="applyingAllTranslations"
                  @click="applyAllTranslations"
                  :title="canApplyAllTranslations ? '应用所有文件的翻译' : '请先完成所有文件的审核'"
                >
                  全部应用翻译
                </el-button>
              </div>
            </div>
            
            <!-- 文件搜索框 -->
            <div class="file-search-container">
              <el-input
                v-model="fileSearchText"
                placeholder="搜索文件名或路径..."
                clearable
                style="max-width: 400px;"
              >
                <template #prefix>
                  <el-icon><Search /></el-icon>
                </template>
              </el-input>
              <div class="search-stats" v-if="fileSearchText">
                找到 {{ filteredTranslationFiles.length }} / {{ translationFiles.length }} 个文件
              </div>
            </div>
            
          <div v-if="filteredTranslationFiles.length === 0 && translationFiles.length > 0" class="empty-state">
            <el-empty description="没有找到匹配的文件">
              <el-button @click="fileSearchText = ''">清除搜索</el-button>
            </el-empty>
          </div>
          <div v-else-if="translationFiles.length === 0" class="empty-state">
            <el-empty description="暂无翻译文件">
              <el-button @click="loadTranslationFiles">刷新</el-button>
            </el-empty>
          </div>
          <div v-else class="translation-files">
            <div
              v-for="file in filteredTranslationFiles"
              :key="file.path"
              class="file-card"
            >
              <el-card shadow="hover" class="clickable" @click="selectFile(file)">
                <div class="file-info">
                  <h4>{{ file.path }}</h4>
                  <p>{{ file.type }} - {{ file.total_count }} 条翻译 (已审核: {{ file.approved_count }})</p>
                  <el-progress
                    :percentage="getApprovalRate(file)"
                    :color="getProgressColor(file)"
                  />
                </div>
                <div class="file-actions">
                  <el-button
                    size="small"
                    type="success"
                    :disabled="!isFileFullyReviewed(file)"
                    :loading="applyingTranslations[file.path]"
                    @click.stop="applyFileTranslation(file)"
                    :title="isFileEmpty(file) ? '该文件没有翻译内容' : (isFileFullyReviewed(file) ? '应用此文件的翻译' : '请先完成此文件的审核')"
                  >
                    应用翻译
                  </el-button>
                </div>
              </el-card>
            </div>
          </div>
        </div>

        <!-- 翻译内容审核 -->
        <div v-if="selectedFile" class="review-section">
          <div class="review-header">
            <el-button @click="backToFileList" icon="ArrowLeft" :loading="saving">
              返回文件列表
            </el-button>
            <h3>{{ selectedFile.path }}</h3>
            <div class="review-stats">
              <el-tag type="info">总计: {{ translations.length }}</el-tag>
              <el-tag type="success">已审核: {{ getTotalApprovedCount() }}</el-tag>
              <el-tag type="warning">待审核: {{ getTotalPendingCount() }}</el-tag>
              <el-tag type="danger">引号不匹配: {{ getQuoteMismatchCount() }}</el-tag>
            </div>
          </div>

          <!-- 过滤和操作栏 -->
          <div class="filter-actions">
            <div class="filter-row">
              <div class="search-container">
                <el-dropdown trigger="click" placement="bottom-start">
                  <el-button 
                    :type="selectedFieldsCount === 0 ? 'warning' : 'primary'"
                    size="small" 
                    style="border-top-right-radius: 0; border-bottom-right-radius: 0; border-right: none;"
                    :title="`搜索字段: ${selectedFieldsText}`"
                  >
                    {{ selectedFieldsCount }}/4 字段
                    <el-icon class="el-icon--right"><arrow-down /></el-icon>
                  </el-button>
                  <template #dropdown>
                    <el-dropdown-menu>
                      <div class="search-fields-selector">
                        <div class="field-option">
                          <el-checkbox v-model="searchFields.original" @change="resetPagination">
                            原文
                          </el-checkbox>
                        </div>
                        <div class="field-option">
                          <el-checkbox v-model="searchFields.translation" @change="resetPagination">
                            LLM翻译
                          </el-checkbox>
                        </div>
                        <div class="field-option">
                          <el-checkbox v-model="searchFields.approved" @change="resetPagination">
                            审核结果
                          </el-checkbox>
                        </div>
                        <div class="field-option">
                          <el-checkbox v-model="searchFields.context" @change="resetPagination">
                            上下文
                          </el-checkbox>
                        </div>
                        <el-divider style="margin: 8px 0;" />
                        <div class="field-actions">
                          <el-button type="primary" size="small" @click="selectAllFields">全选</el-button>
                          <el-button size="small" @click="clearAllFields">清空</el-button>
                        </div>
                      </div>
                    </el-dropdown-menu>
                  </template>
                </el-dropdown>
                <el-input
                  v-model="searchText"
                  placeholder="在选定字段中搜索...（支持 \u0001 格式搜索控制字符）"
                  style="width: 300px; border-top-left-radius: 0; border-bottom-left-radius: 0;"
                  clearable
                  @input="resetPagination"
                >
                  <template #prefix>
                    <el-icon><Search /></el-icon>
                  </template>
                </el-input>
              </div>
              
              <el-select v-model="filterStatus" style="width: 150px; margin-right: 12px;" @change="resetPagination">
                <el-option label="全部" value="all" />
                <el-option label="已审核" value="approved" />
                <el-option label="未审核" value="unapproved" />
                <el-option label="已翻译" value="translated" />
                <el-option label="未翻译" value="empty" />
              </el-select>

              <el-select v-model="filterLlmSuggestion" style="width: 180px; margin-right: 12px;" @change="resetPagination">
                <el-option label="全部建议" value="all" />
                <el-option label="LLM建议翻译" value="suggested" />
                <el-option label="LLM不建议翻译" value="not_suggested" />
              </el-select>

              <el-select v-model="customFilter" style="width: 180px; margin-right: 12px;" @change="resetPagination">
                <el-option label="全部条目" value="all" />
                <el-option label="单词原文" value="word_only" />
                <el-option label="引号不匹配" value="quote_mismatch" />
              </el-select>

              <el-select v-model="pageSize" style="width: 120px; margin-right: 12px;" @change="resetPagination">
                <el-option label="50条/页" :value="50" />
                <el-option label="10条/页" :value="10" />
                <el-option label="100条/页" :value="100" />
              </el-select>
            </div>

            <div class="action-row">
              <div class="action-group">
                <el-button type="primary" @click="saveReview" :loading="saving">
                  保存审核进度
                </el-button>
              </div>
              <div class="action-group">
                <el-button type="success" @click="approveAllFiltered" :loading="approvingAll">
                  全部应用LLM翻译 ({{ filteredTranslations.length }}条)
                </el-button>
                <el-button type="info" @click="keepAllOriginal" :loading="keepingAllOriginal">
                  全部保留原文 ({{ filteredTranslations.length }}条)
                </el-button>
                <el-button type="danger" @click="resetAllFiltered" :loading="resettingAll">
                  全部重置审核状态 ({{ filteredTranslations.length }}条)
                </el-button>
              </div>
            </div>
          </div>

          <!-- 翻译列表 -->
          <div class="translations-container">
            <transition-group name="translation-item" tag="div">
              <div
                v-for="item in paginatedTranslations"
                :key="item.translation_key || `${item.file_name}-${item.original_text}`"
                class="translation-item"
                :class="{ 
                  'approved': item.approved,
                  'quote-mismatch': hasTranslationQuoteMismatch(item)
                }"
              >
                <el-card>
                  <div class="translation-header">
                    <div class="item-status">
                      <el-tag 
                        :type="item.approved ? 'success' : 'warning'" 
                        size="small"
                      >
                        {{ item.approved ? '已审核' : '待审核' }}
                      </el-tag>
                      <el-tag 
                        v-if="item.is_suggested_to_translate" 
                        type="primary" 
                        size="small"
                      >
                        LLM建议翻译
                      </el-tag>
                      <el-tag 
                        v-else
                        type="info" 
                        size="small"
                      >
                        LLM不建议翻译
                      </el-tag>
                      <el-tag 
                        v-if="hasTranslationQuoteMismatch(item)"
                        type="danger" 
                        size="small"
                      >
                        引号不匹配
                      </el-tag>
                    </div>
                    <div class="item-number">#{{ getOriginalIndex(item) + 1 }}</div>
                  </div>

                  <div class="translation-content">
                    <div class="content-row">
                      <div class="content-section">
                        <label>原文:</label>
                        <div class="original-text" v-html="formatTextForHtml(item.original_text)"></div>
                      </div>
                    </div>

                    <div class="content-row">
                      <div class="content-section">
                        <label>LLM翻译结果:</label>
                        <div class="machine-translation" :class="{ 'empty': !item.translation }">
                          <span v-if="item.translation" v-html="formatTextForHtml(item.translation)"></span>
                          <span v-else>未翻译</span>
                        </div>
                      </div>
                    </div>

                    <div class="content-row">
                      <div class="content-section">
                        <label>审核结果:</label>
                        <el-input
                          v-model="item.approved_text"
                          type="textarea"
                          :rows="3"
                          placeholder="请输入审核后的翻译结果...（支持 \u0001 格式的转义字符）"
                          @change="handleApprovedTextChange(item)"
                        />
                        <div v-if="item.approved_text" class="preview-text">
                          <div class="preview-label">预览效果:</div>
                          <div v-html="formatTextForHtml(item.approved_text)"></div>
                        </div>
                      </div>
                    </div>

                    <div v-if="item.context" class="context-info">
                      <el-tag size="small" type="info">上下文: {{ item.context }}</el-tag>
                    </div>

                    <div v-if="item.llm_reason" class="llm-reason">
                      <el-alert
                        :title="item.is_suggested_to_translate ? 'LLM建议翻译:' : 'LLM不建议翻译:'"
                        :type="item.is_suggested_to_translate ? 'success' : 'warning'"
                        :description="item.llm_reason"
                        show-icon
                        :closable="false"
                      />
                    </div>

                    <div class="translation-actions">
                      <el-button
                        size="small"
                        @click="copyOriginalToApproved(item)"
                      >
                        应用LLM翻译
                      </el-button>
                      <el-button
                        size="small"
                        type="info"
                        @click="keepOriginalText(item)"
                      >
                        保留原文
                      </el-button>
                      <el-button
                        size="small"
                        type="warning"
                        @click="resetApprovedText(item)"
                      >
                        重置
                      </el-button>
                    </div>

                    <!-- 翻译建议 -->
                    <div v-if="item.suggestions && item.suggestions.length > 0" class="suggestions">
                      <p>翻译建议:</p>
                      <div class="suggestion-list">
                        <el-tag
                          v-for="(suggestion, sIndex) in item.suggestions"
                          :key="sIndex"
                          @click="applySuggestion(item, suggestion)"
                          class="clickable-tag"
                        >
                          {{ suggestion }}
                        </el-tag>
                      </div>
                    </div>
                  </div>
                </el-card>
              </div>
            </transition-group>
          </div>

          <!-- 分页 -->
          <div class="pagination-container">
            <el-pagination
              :current-page="currentPage"
              :page-size="pageSize"
              :total="filteredTranslations.length"
              layout="prev, pager, next, jumper, total"
              @current-change="handlePageChange"
            />
          </div>
        </div>
      </div>
    </el-card>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch, nextTick } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, ArrowDown } from '@element-plus/icons-vue'
import { useAppStore } from '../stores/app'
import { translationAPI, memoryAPI } from '../utils/api'

const appStore = useAppStore()

// 数据
const translationFiles = ref([])
const selectedFile = ref(null)
const translations = ref([])
const searchText = ref('')
const fileSearchText = ref('') // 文件搜索文本
const searchFields = ref({
  original: true,     // 原文
  translation: true,  // LLM翻译
  approved: true,     // 审核结果
  context: true       // 上下文
})
const filterStatus = ref('all')
const filterLlmSuggestion = ref('all')
const customFilter = ref('all')
const currentPage = ref(1)
const pageSize = ref(50)
const saving = ref(false)
const approvingAll = ref(false)
const keepingAllOriginal = ref(false)
const resettingAll = ref(false)
const applyingAllTranslations = ref(false)
const applyingTranslations = ref({})
const exportingPackage = ref(false)
const modifiedIndices = ref(new Set())
const autoSaveCounter = ref(0)

// 监听搜索和过滤变化，重置分页
const resetPagination = () => {
  currentPage.value = 1
}

// 字段选择器控制方法
const selectAllFields = () => {
  searchFields.value = {
    original: true,
    translation: true,
    approved: true,
    context: true
  }
  resetPagination()
}

const clearAllFields = () => {
  searchFields.value = {
    original: false,
    translation: false,
    approved: false,
    context: false
  }
  resetPagination()
}

// 处理翻页并滚动到顶部
const handlePageChange = (page) => {
  currentPage.value = page
  // 滚动到翻译列表容器的顶部
  const container = document.querySelector('.translations-container')
  if (container) {
    container.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }
}

// 自动保存逻辑
watch(modifiedIndices, (newVal) => {
  if (newVal.size > 0 && newVal.size % 5 === 0) {
    autoSaveReview()
  }
}, { deep: true })

// 计算属性
const filteredTranslationFiles = computed(() => {
  if (!fileSearchText.value) {
    return translationFiles.value
  }
  
  const search = fileSearchText.value.toLowerCase()
  return translationFiles.value.filter(file => {
    return file.path.toLowerCase().includes(search)
  })
})

// 计算选中的搜索字段数量
const selectedFieldsCount = computed(() => {
  return Object.values(searchFields.value).filter(Boolean).length
})

// 获取选中的字段名称列表
const selectedFieldsText = computed(() => {
  const fields = []
  if (searchFields.value.original) fields.push('原文')
  if (searchFields.value.translation) fields.push('翻译')
  if (searchFields.value.approved) fields.push('审核')
  if (searchFields.value.context) fields.push('上下文')
  
  if (fields.length === 0) return '无字段'
  if (fields.length === 4) return '全部字段'
  return fields.join('、')
})

const filteredTranslations = computed(() => {
  let filtered = translations.value

  // 搜索过滤
  if (searchText.value) {
    const search = searchText.value.toLowerCase()
    
    // 将用户输入的转义序列转换为实际字符（用于搜索控制字符）
    const searchAsControlChar = convertEscapeSequences(search)
    
    filtered = filtered.filter(item => {
      const results = []
      
      // 根据选择的字段进行搜索
      if (searchFields.value.original) {
        // 搜索原文
        const originalAsEscape = formatTextForDisplay(item.original_text).toLowerCase()
        results.push(
          item.original_text.toLowerCase().includes(search) ||
          item.original_text.toLowerCase().includes(searchAsControlChar) ||
          originalAsEscape.includes(search)
        )
      }
      
      if (searchFields.value.translation && item.translation) {
        // 搜索LLM翻译
        const translationAsEscape = formatTextForDisplay(item.translation).toLowerCase()
        results.push(
          item.translation.toLowerCase().includes(search) ||
          item.translation.toLowerCase().includes(searchAsControlChar) ||
          translationAsEscape.includes(search)
        )
      }
      
      if (searchFields.value.approved && item.approved_text) {
        // 搜索审核结果
        const approvedAsEscape = formatTextForDisplay(item.approved_text).toLowerCase()
        results.push(
          item.approved_text.toLowerCase().includes(search) ||
          item.approved_text.toLowerCase().includes(searchAsControlChar) ||
          approvedAsEscape.includes(search)
        )
      }
      
      if (searchFields.value.context && item.context) {
        // 搜索上下文
        results.push(item.context.toLowerCase().includes(search))
      }
      
      // 只要有一个字段匹配就返回true（如果没有选择任何字段，则不显示任何结果）
      return results.length > 0 && results.some(result => result === true)
    })
  }

  // 状态过滤
  if (filterStatus.value !== 'all') {
    filtered = filtered.filter(item => {
      if (filterStatus.value === 'approved') {
        return item.approved === true
      } else if (filterStatus.value === 'unapproved') {
        return item.approved !== true
      } else if (filterStatus.value === 'translated') {
        return item.translation && item.translation.trim() !== ''
      } else if (filterStatus.value === 'empty') {
        return !item.translation || item.translation.trim() === ''
      }
      return true
    })
  }

  // LLM建议过滤
  if (filterLlmSuggestion.value !== 'all') {
    filtered = filtered.filter(item => {
      if (filterLlmSuggestion.value === 'suggested') {
        return item.is_suggested_to_translate === true
      } else if (filterLlmSuggestion.value === 'not_suggested') {
        return item.is_suggested_to_translate === false
      }
      return true
    })
  }

  // 定制化过滤
  if (customFilter.value !== 'all') {
    filtered = filtered.filter(item => {
      if (customFilter.value === 'word_only') {
        // 过滤出不包含空格的原文条目（单词）
        return item.original_text && !item.original_text.includes(' ')
      } else if (customFilter.value === 'quote_mismatch') {
        // 过滤出LLM翻译结果或审核文本中引号不匹配的条目
        return hasTranslationQuoteMismatch(item)
      }
      return true
    })
  }

  return filtered
})

// 分页数据
const paginatedTranslations = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  const end = start + pageSize.value
  return filteredTranslations.value.slice(start, end)
})

// 统计方法 - 基于过滤结果
const getApprovedCount = () => {
  return filteredTranslations.value.filter(item => item.approved === true).length
}

const getPendingCount = () => {
  return filteredTranslations.value.filter(item => item.approved !== true).length
}

const getQuoteMismatchCount = () => {
  return translations.value.filter(item => hasTranslationQuoteMismatch(item)).length
}

// 统计方法 - 基于全部翻译
const getTotalApprovedCount = () => {
  return translations.value.filter(item => item.approved === true).length
}

const getTotalPendingCount = () => {
  return translations.value.filter(item => item.approved !== true).length
}

// 方法
const loadTranslationFiles = async () => {
  try {
    const data = await translationAPI.getTranslations()
    if (data.error) {
      ElMessage.error(data.error)
    } else {
      translationFiles.value = data
    }
  } catch (error) {
    ElMessage.error('加载翻译文件失败')
  }
}

const selectFile = async (file) => {
  try {
    selectedFile.value = file
    const data = await translationAPI.getTranslationReview(file.path)
    if (data.error) {
      ElMessage.error(data.error)
    } else {
      translations.value = data.translations.map(item => ({
        ...item,
        suggestions: []
      }))
      currentPage.value = 1
      // 默认选择未审核过滤项
      filterStatus.value = 'unapproved'
    }
  } catch (error) {
    ElMessage.error('加载翻译内容失败')
  }
}

// 刷新当前文件数据 - 用于批量操作后强制更新界面
const refreshCurrentFileData = async () => {
  if (!selectedFile.value) return
  
  try {
    const data = await translationAPI.getTranslationReview(selectedFile.value.path)
    if (data.error) {
      ElMessage.error(data.error)
    } else {
      // 保存当前的筛选条件和页码
      const currentFilterStatus = filterStatus.value
      const currentFilterLlmSuggestion = filterLlmSuggestion.value
      const currentCustomFilter = customFilter.value
      const currentSearchText = searchText.value
      const currentPageNum = currentPage.value
      
      // 更新翻译数据
      translations.value = data.translations.map(item => ({
        ...item,
        suggestions: []
      }))
      
      // 强制触发Vue的响应性更新
      await nextTick()
      
      // 恢复筛选条件和页码
      filterStatus.value = currentFilterStatus
      filterLlmSuggestion.value = currentFilterLlmSuggestion
      customFilter.value = currentCustomFilter
      searchText.value = currentSearchText
      currentPage.value = currentPageNum
      
      // 再次等待DOM更新
      await nextTick()
      
      // 清空修改标记
      modifiedIndices.value.clear()
      
      // 刷新文件列表以更新统计信息
      loadTranslationFiles()
    }
  } catch (error) {
    console.error('刷新当前文件数据失败:', error)
  }
}

const backToFileList = async () => {
  // 如果有未保存的修改，先进行保存
  if (modifiedIndices.value.size > 0) {
    try {
      await saveReview()
      ElMessage.success('返回时自动保存成功')
    } catch (error) {
      ElMessage.error('自动保存失败，但仍然返回文件列表')
      console.error('返回时自动保存失败:', error)
    }
  }
  
  selectedFile.value = null
  translations.value = []
  modifiedIndices.value.clear()
  // 重置过滤状态为默认值
  filterStatus.value = 'all'
  filterLlmSuggestion.value = 'all'
  customFilter.value = 'all'
  searchText.value = ''
  fileSearchText.value = '' // 清空文件搜索
  // 返回文件列表时刷新数据以更新审核状态
  loadTranslationFiles()
}

const markAsModified = (item) => {
  const index = translations.value.findIndex(t => t === item)
  if (index !== -1) {
    modifiedIndices.value.add(index)
    // 如果修改了approved_text，自动设置为已审核
    if (item.approved_text && item.approved_text.trim() !== '') {
      item.approved = true
    }
  }
}

// 新的审核相关方法
const copyOriginalToApproved = (item) => {
  item.approved_text = item.translation || ''
  markAsModified(item)
}

const resetApprovedText = (item) => {
  item.approved_text = ''
  item.approved = false
  markAsModified(item)
}

// 保留原文方法
const keepOriginalText = (item) => {
  item.approved_text = item.original_text || ''
  item.approved = true
  markAsModified(item)
}

// 获取原始索引的方法
const getOriginalIndex = (item) => {
  return translations.value.findIndex(t => t === item)
}

// 处理特殊字符显示的方法
const formatTextForDisplay = (text) => {
  if (!text) return text
  
  // 将不可见的Unicode控制字符转换为可视化的转义序列
  return text.replace(/[\u0000-\u001f\u007f-\u009f]/g, (char) => {
    const code = char.charCodeAt(0).toString(16).padStart(4, '0')
    return `\\u${code}`
  })
}

// 处理特殊字符显示的方法（用于HTML显示）
const formatTextForHtml = (text) => {
  if (!text) return text
  
  // 将不可见的Unicode控制字符转换为带高亮的转义序列
  return text.replace(/[\u0000-\u001f\u007f-\u009f]/g, (char) => {
    const code = char.charCodeAt(0).toString(16).padStart(4, '0')
    return `<span class="unicode-escape">\\u${code}</span>`
  })
}

// 将用户输入的转义序列转换为实际的Unicode字符
const convertEscapeSequences = (text) => {
  if (!text) return text
  
  // 将 \u0001 这样的转义序列转换为实际的Unicode字符
  return text.replace(/\\u([0-9a-fA-F]{4})/g, (match, hex) => {
    return String.fromCharCode(parseInt(hex, 16))
  })
}

// 检测文本中引号是否匹配
const hasQuoteMismatch = (text) => {
  if (!text) return false
  
  // 计算各种引号的数量，排除单引号和撇号
  const doubleQuoteCount = (text.match(/"/g) || []).length  // 英文双引号
  const leftDoubleQuoteCount = (text.match(/"/g) || []).length  // 左双引号
  const rightDoubleQuoteCount = (text.match(/"/g) || []).length  // 右双引号
  const japaneseLeftQuoteCount = (text.match(/「/g) || []).length // 日文左引号
  const japaneseRightQuoteCount = (text.match(/」/g) || []).length // 日文右引号
  const japaneseLeftDoubleQuoteCount = (text.match(/『/g) || []).length // 日文左双引号
  const japaneseRightDoubleQuoteCount = (text.match(/』/g) || []).length  // 日文右双引号
  
  // 检查是否有任何引号数量为奇数
  const quoteCounts = [
    doubleQuoteCount,
    leftDoubleQuoteCount,
    rightDoubleQuoteCount,
    japaneseLeftQuoteCount,
    japaneseRightQuoteCount,
    japaneseLeftDoubleQuoteCount,
    japaneseRightDoubleQuoteCount
  ]
  
  return quoteCounts.some(count => count % 2 !== 0)
}

// 检测翻译项是否有引号不匹配问题
const hasTranslationQuoteMismatch = (item) => {
  // 优先检查审核结果，如果有审核结果就只检查审核结果
  if (item.approved_text && item.approved_text.trim() !== '') {
    return hasQuoteMismatch(item.approved_text)
  }
  
  // 如果没有审核结果，再检查LLM翻译结果
  if (item.translation && item.translation.trim() !== '') {
    return hasQuoteMismatch(item.translation)
  }
  
  // 如果都没有，则认为没有引号不匹配
  return false
}

// 处理审核文本变化，支持转义序列输入
const handleApprovedTextChange = (item) => {
  // 转换转义序列为实际字符
  const convertedText = convertEscapeSequences(item.approved_text)
  if (convertedText !== item.approved_text) {
    item.approved_text = convertedText
  }
  markAsModified(item)
}

const approveAllFiltered = async () => {
  try {
    const itemsToProcess = filteredTranslations.value.length // 在操作前记住数量
    await ElMessageBox.confirm(
      `确定要将当前过滤的 ${itemsToProcess} 条翻译全部应用LLM翻译结果吗？这将覆盖已有的审核结果。`,
      '批量应用LLM翻译确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    approvingAll.value = true
    
    // 遍历所有过滤后的翻译，强制设置为LLM翻译结果
    filteredTranslations.value.forEach(item => {
      const index = translations.value.findIndex(t => t === item)
      if (index !== -1) {
        // 强制使用LLM翻译结果，覆盖已有的审核结果
        translations.value[index].approved_text = item.translation || ''
        translations.value[index].approved = true
        markAsModified(item)
      }
    })

    // 自动保存修改
    await saveReview()
    
    // 批量操作后强制刷新当前文件数据
    await refreshCurrentFileData()
    
    ElMessage.success(`已将 ${itemsToProcess} 条翻译应用LLM翻译结果并保存`)
  } catch (error) {
    // 用户取消
  } finally {
    approvingAll.value = false
  }
}

const keepAllOriginal = async () => {
  try {
    const itemsToProcess = filteredTranslations.value.length // 在操作前记住数量
    await ElMessageBox.confirm(
      `确定要将当前过滤的 ${itemsToProcess} 条翻译全部保留原文吗？`,
      '批量保留原文确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    keepingAllOriginal.value = true
    
    // 遍历所有过滤后的翻译，设置为保留原文
    filteredTranslations.value.forEach(item => {
      const index = translations.value.findIndex(t => t === item)
      if (index !== -1) {
        translations.value[index].approved_text = item.original_text || ''
        translations.value[index].approved = true
        markAsModified(item)
      }
    })

    // 自动保存修改
    await saveReview()
    
    // 批量操作后强制刷新当前文件数据
    await refreshCurrentFileData()
    
    ElMessage.success(`已将 ${itemsToProcess} 条翻译标记为保留原文并保存`)
  } catch (error) {
    // 用户取消
  } finally {
    keepingAllOriginal.value = false
  }
}

const resetAllFiltered = async () => {
  try {
    const itemsToProcess = filteredTranslations.value.length // 在操作前记住数量
    await ElMessageBox.confirm(
      `确定要重置当前过滤的 ${itemsToProcess} 条翻译的审核状态吗？这将清空所有审核结果并将状态设置为未审核。`,
      '重置审核状态确认',
      {
        confirmButtonText: '确定重置',
        cancelButtonText: '取消',
        type: 'warning',
        dangerouslyUseHTMLString: true,
        message: `<div>
          <p>此操作将：</p>
          <ul style="text-align: left; margin: 10px 0;">
            <li>清空所有已审核的翻译结果</li>
            <li>将审核状态设置为"未审核"</li>
            <li>自动保存修改</li>
          </ul>
          <p><strong>注意：此操作不可撤销！</strong></p>
        </div>`
      }
    )

    resettingAll.value = true
    
    // 遍历所有过滤后的翻译，重置审核状态
    filteredTranslations.value.forEach(item => {
      const index = translations.value.findIndex(t => t === item)
      if (index !== -1) {
        translations.value[index].approved_text = ''
        translations.value[index].approved = false
        markAsModified(item)
      }
    })

    // 自动保存修改
    await saveReview()
    
    // 批量操作后强制刷新当前文件数据
    await refreshCurrentFileData()
    
    ElMessage.success(`已重置 ${itemsToProcess} 条翻译的审核状态并保存`)
  } catch (error) {
    // 用户取消
  } finally {
    resettingAll.value = false
  }
}

const applySuggestion = (item, suggestion) => {
  item.approved_text = suggestion
  markAsModified(item)
}

// 保存审核结果
const saveReview = async () => {
  try {
    saving.value = true
    const result = await translationAPI.saveTranslationReview(
      selectedFile.value.path,
      translations.value
    )
    
    if (result.success) {
      ElMessage.success('审核结果保存成功')
      modifiedIndices.value.clear()
      // 保存成功后刷新文件列表以更新审核状态
      loadTranslationFiles()
    } else {
      ElMessage.error(result.message)
    }
  } catch (error) {
    ElMessage.error('保存审核结果失败')
  } finally {
    saving.value = false
  }
}

// 自动保存
const autoSaveReview = async () => {
  if (modifiedIndices.value.size === 0) return
  
  try {
    const modificationCount = modifiedIndices.value.size // 在清空前记住修改数量
    await saveReview()
    ElMessage.success(`自动保存成功 (${modificationCount} 条修改)`)
  } catch (error) {
    console.error('自动保存失败:', error)
  }
}

const getApprovalRate = (file) => {
  if (file.total_count === 0) return 100  // 没有翻译内容的文件显示100%
  return Math.round((file.approved_count / file.total_count) * 100)
}

const getProgressColor = (file) => {
  const rate = getApprovalRate(file)
  if (rate === 100) return '#67c23a'
  if (rate >= 70) return '#e6a23c'
  return '#f56c6c'
}

// 应用翻译相关方法
const isFileFullyReviewed = (file) => {
  // 没有翻译内容的文件不能应用翻译
  if (file.total_count === 0) return false
  return file.total_count > 0 && file.approved_count === file.total_count
}

// 检查文件是否可以被忽略（没有翻译内容）
const isFileEmpty = (file) => {
  return file.total_count === 0
}

const canApplyAllTranslations = computed(() => {
  // 过滤掉空文件，只检查有内容的文件（基于过滤后的文件列表）
  const filesWithContent = filteredTranslationFiles.value.filter(file => !isFileEmpty(file))
  return filesWithContent.length > 0 && 
         filesWithContent.every(file => isFileFullyReviewed(file))
})

// 应用单个文件翻译
const applyFileTranslation = async (file) => {
  if (isFileEmpty(file)) {
    ElMessage.info('该文件没有翻译内容，无需应用翻译')
    return
  }
  
  if (!isFileFullyReviewed(file)) {
    ElMessage.warning('请先完成此文件的审核')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要应用文件 "${file.path}" 的翻译吗？`,
      '应用翻译确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    applyingTranslations.value[file.path] = true
    
    const response = await fetch('/api/apply-translations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        file_path: file.path,
        apply_all: false
      })
    })
    
    const result = await response.json()
    
    if (result.success) {
      ElMessage.success(`文件 "${file.path}" 翻译应用成功`)
    } else {
      ElMessage.error(result.message || '应用翻译失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('应用翻译失败')
    }
  } finally {
    applyingTranslations.value[file.path] = false
  }
}

// 应用所有翻译
const applyAllTranslations = async () => {
  if (!canApplyAllTranslations.value) {
    ElMessage.warning('请先完成所有文件的审核')
    return
  }

  try {
    await ElMessageBox.confirm(
      `确定要应用所有文件的翻译吗？共 ${translationFiles.value.length} 个文件。`,
      '批量应用翻译确认',
      {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }
    )

    applyingAllTranslations.value = true
    
    const response = await fetch('/api/apply-translations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        apply_all: true
      })
    })
    
    const result = await response.json()
    
    if (result.success) {
      ElMessage.success('所有文件翻译应用成功')
    } else {
      ElMessage.error(result.message || '应用翻译失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('应用翻译失败')
    }
  } finally {
    applyingAllTranslations.value = false
  }
}

// 导出翻译包
const exportTranslationPackage = async () => {
  try {
    await ElMessageBox.confirm(
      '确定要导出翻译包吗？这将打包所有已翻译的文件。',
      '导出翻译包确认',
      {
        confirmButtonText: '确定导出',
        cancelButtonText: '取消',
        type: 'info',
      }
    )

    exportingPackage.value = true
    
    const response = await fetch('/api/export_translation_package', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      }
    })
    
    if (response.ok) {
      // 如果响应是文件，则下载它
      const contentType = response.headers.get('content-type')
      if (contentType && contentType.includes('application/zip')) {
        const blob = await response.blob()
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.style.display = 'none'
        a.href = url
        
        // 从响应头获取文件名，如果没有则使用默认名称
        const contentDisposition = response.headers.get('content-disposition')
        let filename = 'translation_package.zip'
        if (contentDisposition) {
          const filenameMatch = contentDisposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/)
          if (filenameMatch && filenameMatch[1]) {
            filename = filenameMatch[1].replace(/['"]/g, '')
          }
        }
        
        a.download = filename
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
        
        ElMessage.success('翻译包导出成功')
      } else {
        // 如果不是文件，则处理为JSON响应
        const result = await response.json()
        if (result.success) {
          ElMessage.success('翻译包导出成功')
        } else {
          ElMessage.error(result.message || '导出翻译包失败')
        }
      }
    } else {
      const result = await response.json()
      ElMessage.error(result.message || '导出翻译包失败')
    }
  } catch (error) {
    if (error !== 'cancel') {
      console.error('导出翻译包失败:', error)
      ElMessage.error('导出翻译包失败')
    }
  } finally {
    exportingPackage.value = false
  }
}

// 监听配置状态变化
watch(() => appStore.isConfigSelected, (newVal) => {
  if (newVal && translationFiles.value.length === 0) {
    loadTranslationFiles()
  }
})

// 生命周期
onMounted(() => {
  if (appStore.isConfigSelected) {
    loadTranslationFiles()
  }
})
</script>

<style scoped>
.review-view {
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

.translation-files {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
  margin-top: 16px;
}

.files-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.files-header h3 {
  margin: 0;
}

.file-search-container {
  margin: 16px 0;
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
}

.search-stats {
  color: var(--el-text-color-secondary);
  font-size: 14px;
}

.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.file-card {
  cursor: pointer;
}

.file-card .el-card {
  position: relative;
  transition: transform 0.2s;
}

.file-card .el-card:hover {
  transform: translateY(-2px);
}

.file-actions {
  margin-top: 12px;
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}

.file-info h4 {
  margin: 0 0 8px 0;
  color: var(--el-color-primary);
}

.file-info p {
  margin: 0 0 12px 0;
  color: var(--el-text-color-regular);
  font-size: 14px;
}

.review-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
  gap: 16px;
}

.review-header h3 {
  margin: 0;
  flex: 1;
  color: var(--el-color-primary);
}

.review-stats {
  display: flex;
  gap: 8px;
  align-items: center;
}

.filter-actions {
  margin-bottom: 20px;
  padding: 16px;
  background: var(--el-bg-color-page);
  border-radius: 8px;
}

.filter-row, .action-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.search-container {
  display: flex;
  align-items: center;
  margin-right: 12px;
}

.search-fields-selector {
  padding: 12px;
  min-width: 150px;
}

.field-option {
  padding: 4px 0;
  display: flex;
  align-items: center;
}

.field-actions {
  display: flex;
  gap: 8px;
  justify-content: space-between;
}

.action-row {
  margin-bottom: 0;
  justify-content: space-between;
  align-items: flex-start;
}

.action-group {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.translations-container {
  margin-bottom: 20px;
}

.translation-item {
  margin-bottom: 16px;
  border-radius: 8px;
  overflow: hidden;
}

.translation-item.approved {
  border-left: 4px solid var(--el-color-success);
}

.translation-item.quote-mismatch {
  border-left: 4px solid var(--el-color-danger);
}

.translation-item.quote-mismatch .el-card {
  border: 1px solid var(--el-color-danger);
  background-color: rgba(245, 108, 108, 0.05);
}

/* 过渡动画 */
.translation-item-enter-active,
.translation-item-leave-active {
  transition: all 0.5s ease;
}

.translation-item-enter-from {
  opacity: 0;
  transform: translateY(-20px);
}

.translation-item-leave-to {
  opacity: 0;
  transform: translateX(100px);
}

.translation-item-move {
  transition: transform 0.5s ease;
}

.translation-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.item-status {
  display: flex;
  gap: 8px;
  align-items: center;
}

.item-number {
  font-size: 14px;
  color: var(--el-text-color-secondary);
  font-weight: 500;
}

.translation-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.content-row {
  display: flex;
  flex-direction: column;
}

.content-section {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.content-section label {
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-size: 14px;
}

.original-text {
  background: var(--el-bg-color-page);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  min-height: 60px;
  line-height: 1.5;
  font-size: 14px;
  font-family: 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  word-break: break-all;
}

.machine-translation {
  background: var(--el-fill-color-light);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  min-height: 60px;
  line-height: 1.5;
  font-size: 14px;
  font-family: 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  word-break: break-all;
}

.machine-translation.empty {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

.preview-text {
  margin-top: 8px;
  padding: 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color-light);
  border-radius: 4px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-family: 'Microsoft YaHei', '微软雅黑', Arial, sans-serif;
  word-break: break-all;
}

.preview-label {
  font-weight: bold;
  margin-bottom: 4px;
  font-size: 11px;
  color: var(--el-text-color-regular);
}

.unicode-escape {
  background: #fff3cd;
  color: #856404;
  padding: 2px 4px;
  border-radius: 3px;
  font-weight: bold;
  border: 1px solid #ffeaa7;
  font-family: 'Courier New', 'Consolas', monospace;
}

.context-info {
  margin-top: 8px;
}

.llm-reason {
  margin-top: 12px;
}

.translation-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

.suggestions {
  margin-top: 12px;
}

.suggestions p {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.clickable-tag:hover {
  transform: scale(1.05);
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .filter-row, .action-row {
    flex-direction: column;
    align-items: stretch;
  }
  
  .search-container {
    margin-right: 0;
    margin-bottom: 12px;
  }
  
  .search-container .el-input {
    width: 100% !important;
  }
  
  .action-group {
    justify-content: center;
    width: 100%;
  }
  
  .review-header {
    flex-direction: column;
    align-items: stretch;
  }
  
  .translation-actions {
    justify-content: center;
  }
}
</style>
}

.original-section label,
.translation-section label {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.original-text {
  background: var(--el-bg-color-page);
  padding: 12px;
  border-radius: 4px;
  border: 1px solid var(--el-border-color);
  min-height: 60px;
  line-height: 1.5;
}

.context-info {
  margin-top: 4px;
}

.translation-actions {
  display: flex;
  gap: 8px;
  margin-top: 8px;
}

.suggestions {
  margin-top: 12px;
}

.suggestions p {
  margin: 0 0 8px 0;
  font-size: 14px;
  color: var(--el-text-color-regular);
}

.suggestion-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.clickable-tag {
  cursor: pointer;
  transition: all 0.2s;
}

.clickable-tag:hover {
  transform: scale(1.05);
}

.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: 20px;

