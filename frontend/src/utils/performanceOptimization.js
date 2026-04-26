/**
 * 防抖和节流工具
 * 用于优化频繁触发的事件
 */

/**
 * 防抖函数
 * 在事件被触发n秒后再执行回调，如果在这n秒内又被触发，则重新计时
 * 
 * @param {Function} func - 需要防抖的函数
 * @param {number} wait - 等待时间（毫秒）
 * @param {boolean} immediate - 是否立即执行
 * @returns {Function} 防抖后的函数
 */
export function debounce(func, wait = 300, immediate = false) {
  let timeout
  
  return function executedFunction(...args) {
    const context = this
    
    const later = () => {
      timeout = null
      if (!immediate) func.apply(context, args)
    }
    
    const callNow = immediate && !timeout
    
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
    
    if (callNow) func.apply(context, args)
  }
}

/**
 * 节流函数
 * 规定在一个单位时间内，只能触发一次函数。如果这个单位时间内触发多次函数，只有一次生效
 * 
 * @param {Function} func - 需要节流的函数
 * @param {number} wait - 等待时间（毫秒）
 * @param {Object} options - 配置选项
 * @param {boolean} options.leading - 是否在开始时执行
 * @param {boolean} options.trailing - 是否在结束时执行
 * @returns {Function} 节流后的函数
 */
export function throttle(func, wait = 300, options = {}) {
  let timeout, context, args, result
  let previous = 0
  
  const { leading = true, trailing = true } = options
  
  const later = () => {
    previous = leading === false ? 0 : Date.now()
    timeout = null
    result = func.apply(context, args)
    if (!timeout) context = args = null
  }
  
  const throttled = function(...params) {
    const now = Date.now()
    if (!previous && leading === false) previous = now
    
    const remaining = wait - (now - previous)
    context = this
    args = params
    
    if (remaining <= 0 || remaining > wait) {
      if (timeout) {
        clearTimeout(timeout)
        timeout = null
      }
      previous = now
      result = func.apply(context, args)
      if (!timeout) context = args = null
    } else if (!timeout && trailing !== false) {
      timeout = setTimeout(later, remaining)
    }
    
    return result
  }
  
  throttled.cancel = () => {
    clearTimeout(timeout)
    previous = 0
    timeout = context = args = null
  }
  
  return throttled
}

/**
 * 请求动画帧节流
 * 使用requestAnimationFrame实现节流，适合动画场景
 * 
 * @param {Function} func - 需要节流的函数
 * @returns {Function} 节流后的函数
 */
export function rafThrottle(func) {
  let ticking = false
  
  return function(...args) {
    if (!ticking) {
      requestAnimationFrame(() => {
        func.apply(this, args)
        ticking = false
      })
      ticking = true
    }
  }
}

/**
 * 创建防抖指令
 * 用于Vue指令
 */
export const debounceDirective = {
  mounted(el, binding) {
    const { value, modifiers } = binding
    const [func, wait = 300] = value
    
    el._debounceHandler = debounce(func, wait, modifiers.immediate)
    
    // 根据事件类型绑定
    const eventType = modifiers.scroll ? 'scroll' : 
                    modifiers.resize ? 'resize' : 'input'
    
    el.addEventListener(eventType, el._debounceHandler)
  },
  
  unmounted(el) {
    if (el._debounceHandler) {
      el.removeEventListener('input', el._debounceHandler)
      el.removeEventListener('scroll', el._debounceHandler)
      el.removeEventListener('resize', el._debounceHandler)
      delete el._debounceHandler
    }
  }
}

/**
 * 创建节流指令
 * 用于Vue指令
 */
export const throttleDirective = {
  mounted(el, binding) {
    const { value, modifiers } = binding
    const [func, wait = 300] = value
    
    el._throttleHandler = throttle(func, wait, {
      leading: !modifiers.trailing,
      trailing: !modifiers.leading
    })
    
    // 根据事件类型绑定
    const eventType = modifiers.scroll ? 'scroll' : 
                    modifiers.resize ? 'resize' : 'click'
    
    el.addEventListener(eventType, el._throttleHandler)
  },
  
  unmounted(el) {
    if (el._throttleHandler) {
      el.removeEventListener('click', el._throttleHandler)
      el.removeEventListener('scroll', el._throttleHandler)
      el.removeEventListener('resize', el._throttleHandler)
      delete el._throttleHandler
    }
  }
}
