import { ref } from 'vue'

/**
 * Element Plus 按钮防重复点击Hook
 * 专门为Element Plus按钮设计，自动管理loading状态
 */
export function useButtonLoading() {
  // 存储多个按钮的loading状态
  const loadingStates = ref(new Map())
  
  /**
   * 创建一个带loading状态的按钮处理函数
   * @param {Function} asyncFn - 异步函数
   * @param {string} key - 按钮的唯一标识，默认为'default'
   * @returns {Object} { handler: 处理函数, loading: 响应式loading状态 }
   */
  const createLoadingHandler = (asyncFn, key = 'default') => {
    // 初始化该key的loading状态
    if (!loadingStates.value.has(key)) {
      loadingStates.value.set(key, false)
    }
    
    // 创建响应式的loading状态
    const loading = ref(false)
    
    // 同步loading状态
    const syncLoading = (value) => {
      loading.value = value
      loadingStates.value.set(key, value)
    }
    
    // 创建处理函数
    const handler = async (...args) => {
      // 如果正在loading，直接返回
      if (loadingStates.value.get(key)) {
        return
      }
      
      try {
        syncLoading(true)
        const result = await asyncFn(...args)
        return result
      } catch (error) {
        throw error
      } finally {
        syncLoading(false)
      }
    }
    
    return {
      handler,
      loading,
      isLoading: () => loadingStates.value.get(key) || false
    }
  }
  
  /**
   * 获取指定按钮的loading状态
   * @param {string} key - 按钮标识
   */
  const getLoadingState = (key = 'default') => {
    return loadingStates.value.get(key) || false
  }
  
  /**
   * 清除指定按钮的loading状态
   * @param {string} key - 按钮标识
   */
  const clearLoading = (key = 'default') => {
    loadingStates.value.set(key, false)
  }
  
  /**
   * 清除所有按钮的loading状态
   */
  const clearAllLoading = () => {
    for (const [key] of loadingStates.value) {
      loadingStates.value.set(key, false)
    }
  }
  
  return {
    createLoadingHandler,
    getLoadingState,
    clearLoading,
    clearAllLoading,
    loadingStates
  }
}

// 全局实例，可以在整个应用中共享
export const globalButtonLoading = useButtonLoading()
