/**
 * 图片懒加载指令
 * 使用Intersection Observer API实现图片懒加载
 */

import { createApp, nextTick } from 'vue'

const lazyLoad = {
  mounted(el, binding) {
    const imageUrl = binding.value
    
    // 如果图片已经在视口中，直接加载
    if (this.isInViewport(el)) {
      this.loadImage(el, imageUrl)
      return
    }
    
    // 创建Intersection Observer
    const observer = new IntersectionObserver((entries) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          this.loadImage(el, imageUrl)
          observer.unobserve(el)
        }
      })
    }, {
      rootMargin: '50px', // 提前50px开始加载
      threshold: 0.01
    })
    
    // 保存observer到元素上，方便后续清理
    el._lazyLoadObserver = observer
    observer.observe(el)
  },
  
  updated(el, binding) {
    // 如果图片URL变化，重新加载
    if (binding.value !== binding.oldValue) {
      this.loadImage(el, binding.value)
    }
  },
  
  unmounted(el) {
    // 清理observer
    if (el._lazyLoadObserver) {
      el._lazyLoadObserver.unobserve(el)
      delete el._lazyLoadObserver
    }
  },
  
  isInViewport(el) {
    const rect = el.getBoundingClientRect()
    return (
      rect.top >= 0 &&
      rect.left >= 0 &&
      rect.bottom <= (window.innerHeight || document.documentElement.clientHeight) &&
      rect.right <= (window.innerWidth || document.documentElement.clientWidth)
    )
  },
  
  loadImage(el, url) {
    // 创建临时图片对象预加载
    const img = new Image()
    
    img.onload = () => {
      el.src = url
      el.classList.add('loaded')
    }
    
    img.onerror = () => {
      el.classList.add('error')
      // 可以设置默认图片
      el.src = '/placeholder.png'
    }
    
    // 添加加载中状态
    el.classList.add('loading')
    img.src = url
  }
}

// 注册为全局指令
export default {
  install(app) {
    app.directive('lazy', lazyLoad)
  }
}
