import { ref } from 'vue'

/**
 * 请求状态管理组合式函数
 * 用于防止重复点击和管理按钮loading状态
 */
export function useRequest() {
  const loading = ref(false)
  const loadingStates = ref(new Map())

  /**
   * 执行异步请求并管理loading状态
   * @param {Function} requestFn - 异步请求函数
   * @param {string} key - 可选的唯一标识，用于多个按钮独立管理状态
   */
  const execute = async (requestFn, key = 'default') => {
    if (loadingStates.value.get(key)) {
      return // 如果正在请求中，直接返回
    }

    try {
      loadingStates.value.set(key, true)
      if (key === 'default') {
        loading.value = true
      }
      
      const result = await requestFn()
      return result
    } catch (error) {
      throw error
    } finally {
      loadingStates.value.set(key, false)
      if (key === 'default') {
        loading.value = false
      }
    }
  }

  /**
   * 获取指定key的loading状态
   * @param {string} key - 状态标识
   */
  const isLoading = (key = 'default') => {
    return key === 'default' ? loading.value : loadingStates.value.get(key) || false
  }

  /**
   * 创建一个带防重复点击的按钮处理函数
   * @param {Function} handler - 原始点击处理函数
   * @param {string} key - 可选的唯一标识
   */
  const createHandler = (handler, key = 'default') => {
    return async (...args) => {
      await execute(() => handler(...args), key)
    }
  }

  return {
    loading,
    loadingStates,
    execute,
    isLoading,
    createHandler
  }
}

/**
 * 全局请求状态管理
 */
class RequestManager {
  constructor() {
    this.requests = new Map()
  }

  /**
   * 开始请求
   * @param {string} key - 请求标识
   */
  start(key) {
    this.requests.set(key, true)
  }

  /**
   * 结束请求
   * @param {string} key - 请求标识
   */
  end(key) {
    this.requests.set(key, false)
  }

  /**
   * 检查是否正在请求
   * @param {string} key - 请求标识
   */
  isLoading(key) {
    return this.requests.get(key) || false
  }

  /**
   * 清除所有请求状态
   */
  clear() {
    this.requests.clear()
  }
}

export const requestManager = new RequestManager()
