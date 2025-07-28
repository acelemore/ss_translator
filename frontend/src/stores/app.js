import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { configAPI, translationAPI } from '../utils/api'

export const useAppStore = defineStore('app', () => {
  // 状态
  const currentConfig = ref(null)
  const configs = ref([])
  const translationStatus = ref({
    running: false,
    current_file: '',
    progress: 0
  })
  const loading = ref(false)
  
  // 计算属性
  const isConfigSelected = computed(() => !!currentConfig.value)
  const isTranslating = computed(() => {
    return translationStatus.value.running || translationStatus.value.status === 'interrupted'
  })
  
  // 动作
  const loadConfigs = async () => {
    try {
      loading.value = true
      const data = await configAPI.getConfigs()
      configs.value = data
    } catch (error) {
      console.error('加载配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  const selectConfig = async (configName) => {
    try {
      loading.value = true
      await configAPI.selectConfig(configName)
      const data = await configAPI.getCurrentConfig()
      if (data.success) {
        currentConfig.value = data.config
        currentConfig.value.name = data.config_name
      }
      return data
    } catch (error) {
      console.error('选择配置失败:', error)
      throw error
    } finally {
      loading.value = false
    }
  }
  
  const getCurrentConfig = async () => {
    try {
      const data = await configAPI.getCurrentConfig()
      if (data.success) {
        currentConfig.value = data.config
        currentConfig.value.name = data.config_name
      }
      return data
    } catch (error) {
      console.error('获取当前配置失败:', error)
      throw error
    }
  }
  
  const updateTranslationStatus = async () => {
    try {
      const data = await translationAPI.getTranslationStatus()
      translationStatus.value = data
      return data
    } catch (error) {
      console.error('获取翻译状态失败:', error)
      throw error
    }
  }
  
  const clearCurrentConfig = () => {
    currentConfig.value = null
  }
  
  return {
    // 状态
    currentConfig,
    configs,
    translationStatus,
    loading,
    
    // 计算属性
    isConfigSelected,
    isTranslating,
    
    // 动作
    loadConfigs,
    selectConfig,
    getCurrentConfig,
    updateTranslationStatus,
    clearCurrentConfig
  }
})
