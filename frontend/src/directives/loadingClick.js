import { requestManager } from '../composables/useRequest.js'

/**
 * 防重复点击指令
 * 用法：v-loading-click="handler"
 */
export const vLoadingClick = {
  mounted(el, binding) {
    const { value: handler, arg: key } = binding
    const requestKey = key || `btn_${Math.random().toString(36).substr(2, 9)}`
    
    // 保存原始处理函数和请求key
    el._loadingClickHandler = handler
    el._loadingClickKey = requestKey
    
    // 创建新的点击处理函数
    const clickHandler = async (event) => {
      // 如果正在请求中，阻止执行
      if (requestManager.isLoading(requestKey)) {
        event.preventDefault()
        event.stopPropagation()
        return
      }
      
      try {
        // 开始请求状态
        requestManager.start(requestKey)
        updateButtonState(el, true)
        
        // 执行原始处理函数
        await handler(event)
      } catch (error) {
        console.error('Request error:', error)
        throw error
      } finally {
        // 结束请求状态
        requestManager.end(requestKey)
        updateButtonState(el, false)
      }
    }
    
    // 移除原有的点击监听器，添加新的
    el.removeEventListener('click', handler)
    el.addEventListener('click', clickHandler)
    el._loadingClickListener = clickHandler
  },
  
  updated(el, binding) {
    const { value: newHandler } = binding
    
    // 如果处理函数改变了，重新绑定
    if (newHandler !== el._loadingClickHandler) {
      el.removeEventListener('click', el._loadingClickListener)
      
      el._loadingClickHandler = newHandler
      const clickHandler = async (event) => {
        if (requestManager.isLoading(el._loadingClickKey)) {
          event.preventDefault()
          event.stopPropagation()
          return
        }
        
        try {
          requestManager.start(el._loadingClickKey)
          updateButtonState(el, true)
          await newHandler(event)
        } catch (error) {
          console.error('Request error:', error)
          throw error
        } finally {
          requestManager.end(el._loadingClickKey)
          updateButtonState(el, false)
        }
      }
      
      el.addEventListener('click', clickHandler)
      el._loadingClickListener = clickHandler
    }
  },
  
  unmounted(el) {
    // 清理事件监听器
    if (el._loadingClickListener) {
      el.removeEventListener('click', el._loadingClickListener)
    }
    
    // 清理请求状态
    if (el._loadingClickKey) {
      requestManager.end(el._loadingClickKey)
    }
  }
}

/**
 * 更新按钮状态
 * @param {HTMLElement} el - 按钮元素
 * @param {boolean} loading - 是否加载中
 */
function updateButtonState(el, loading) {
  // 如果是Element Plus的按钮，使用其loading属性
  if (el.classList.contains('el-button')) {
    const buttonInstance = el.__vueParentComponent
    if (buttonInstance && buttonInstance.props) {
      // 通过Vue实例更新loading状态
      const vnode = buttonInstance.vnode
      if (vnode && vnode.props) {
        vnode.props.loading = loading
      }
    }
    
    // 同时设置disabled状态作为备用
    el.disabled = loading
    
    // 添加视觉反馈
    if (loading) {
      el.classList.add('is-loading')
      if (!el.querySelector('.loading-icon')) {
        const loadingIcon = document.createElement('i')
        loadingIcon.className = 'loading-icon el-icon-loading'
        loadingIcon.style.marginRight = '4px'
        el.insertBefore(loadingIcon, el.firstChild)
      }
    } else {
      el.classList.remove('is-loading')
      const loadingIcon = el.querySelector('.loading-icon')
      if (loadingIcon) {
        loadingIcon.remove()
      }
    }
  } else {
    // 普通按钮，直接设置disabled
    el.disabled = loading
    
    if (loading) {
      el.classList.add('loading')
      el.style.opacity = '0.6'
      el.style.cursor = 'not-allowed'
    } else {
      el.classList.remove('loading')
      el.style.opacity = ''
      el.style.cursor = ''
    }
  }
}
