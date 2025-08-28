import axios from 'axios'

// 创建axios实例
const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json'
  }
})

// 请求拦截器
api.interceptors.request.use(
  config => {
    // 在发送请求之前做些什么
    return config
  },
  error => {
    return Promise.reject(error)
  }
)

// 响应拦截器
api.interceptors.response.use(
  response => {
    return response.data
  },
  error => {
    console.error('API错误:', error)
    return Promise.reject(error)
  }
)

// 配置相关API
export const configAPI = {
  // 获取所有配置
  getConfigs: () => api.get('/configs'),
  
  // 获取当前配置
  getCurrentConfig: () => api.get('/configs/current'),
  
  // 选择配置
  selectConfig: (configName) => api.post('/configs/select', { config_name: configName }),
  
  // 保存配置
  saveConfig: (configName, configData) => api.post('/configs/save', { 
    config_name: configName, 
    config_data: configData 
  }),
  
  // 创建新配置
  createConfig: (configName, modName, modPath, description, temperature, maxTokens) => api.post('/configs/create', {
    config_name: configName,
    mod_name: modName,
    mod_path: modPath,
    description,
    temperature,
    max_tokens: maxTokens
  }),
  
  // 删除配置
  deleteConfig: (configName) => api.post('/configs/delete', { config_name: configName }),
  
  // 自动检测文件并配置
  autoDetectFiles: (configName) => api.post('/configs/auto-detect', { config_name: configName }),
  
  // 获取配置模板
  getTemplates: () => api.get('/config/templates'),
  
  // 验证配置
  validateConfig: (configData) => api.post('/config/validate', configData),
  
  // 修复配置
  fixConfig: (configData) => api.post('/config/fix', configData),
  
  // 导出配置
  exportConfig: (configName) => api.get(`/config/export/${configName}`, { responseType: 'blob' }),
  
  // 导入配置
  importConfig: (formData) => api.post('/config/import', formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),
  
  // 获取全局配置
  getGlobalConfig: () => api.get('/configs/global'),
  
  // 保存全局配置
  saveGlobalConfig: (configData) => api.post('/configs/global', configData),
  
  // 检查API配置状态
  checkApiConfig: () => api.get('/configs/global/api-status')
}

// 翻译相关API
export const translationAPI = {
  // 获取翻译文件列表
  getTranslations: () => api.get('/translations'),
  
  // 应用翻译
  applyTranslations: (filePath, applyAll = false) => api.post('/apply-translations', {
    file_path: filePath,
    apply_all: applyAll
  }),
  
  // 获取翻译审核数据
  getTranslationReview: (filePath) => api.get(`/translation-review/${filePath}`),
  
  // 保存翻译审核数据
  saveTranslationReview: (filePath, translations) => api.post(`/translation-review/${filePath}`, {
    translations
  }),
  
  // 开始翻译
  startTranslation: (filePath) => api.post('/translate/start', { file_path: filePath }),
  
  // 停止翻译
  stopTranslation: () => api.post('/translate/stop'),
  
  // 获取翻译状态
  getTranslationStatus: () => api.get('/translate/status'),
  
  // 获取提取函数
  getExtractFunctions: () => api.get('/extract-functions'),
  
  // 重置进度
  resetProgress: (filePath = null) => api.post('/progress/reset', { file_path: filePath })
}

// 专有名词相关API
export const terminologyAPI = {
  // 获取专有名词
  getTerminology: () => api.get('/terminology'),
  
  // 获取专有名词列表
  getTerminologyList: () => api.get('/terminology/list'),
  
  // 添加专有名词
  addTerminology: (term, translation, domain = 'general', notes = '') => api.post('/terminology/add', {
    term, translation, domain, notes
  }),
  
  // 删除专有名词
  deleteTerminology: (term) => api.post('/terminology/delete', { term }),
  
  // 获取高频词建议
  getHighFrequencyWords: () => api.get('/terminology/high-frequency'),
  
  // 替换专有名词
  replaceTerminology: (filePath) => api.post('/terminology/replace', { file_path: filePath }),
  
  // 导出专有名词
  exportTerminology: () => {
    // 直接触发下载，不经过axios拦截器
    window.location.href = '/api/terminology/export'
  },
  
  // 导入专有名词
  importTerminology: (file) => {
    const formData = new FormData()
    formData.append('file', file)
    return api.post('/terminology/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })
  }
}

// 翻译记忆库相关API
export const memoryAPI = {
  // 获取翻译记忆列表（分页）
  getTranslations: (page = 1, pageSize = 20, searchParams = {}) => {
    const params = { page, page_size: pageSize }
    
    // 添加搜索参数
    if (searchParams.file_name) params.search_file_name = searchParams.file_name
    if (searchParams.original_text) params.search_original_text = searchParams.original_text
    if (searchParams.approved_text) params.search_approved_text = searchParams.approved_text
    if (searchParams.context) params.search_context = searchParams.context
    
    return api.get('/memory/translations', { params })
  },
  
  // 获取统计信息
  getStats: () => api.get('/memory/translations/stats'),
  
  // 删除翻译记录
  deleteTranslation: (id) => api.delete(`/memory/translations/${id}`),
  
  // 批量删除翻译记录
  batchDeleteTranslations: (ids) => api.delete('/memory/translations/batch', { data: { ids } })
}

// 进度管理相关API
export const progressAPI = {
  // 获取翻译进度概览
  getProgressOverview: () => api.get('/progress/overview'),
  
  // 获取指定文件的翻译进度
  getFileProgress: (filePath) => api.get(`/progress/file/${filePath}`),
  
  // 刷新翻译进度
  refreshProgress: () => api.post('/progress/refresh'),
  
  // 重置翻译进度
  resetProgress: (filePath = null) => api.post('/progress/reset', { file_path: filePath }),
  
  // 获取文件列表
  getFiles: () => api.get('/files')
}

export default api
