/** 
 * 性能监控工具
 * 用于监控前端性能指标
 */

class PerformanceMonitor {
  constructor() {
    this.metrics = {}
    this.observers = []
    this.init()
  }

  init() {
    // 监听页面加载性能
    if ('PerformanceObserver' in window) {
      this.observeNavigationTiming()
      this.observeResourceTiming()
      this.observePaintTiming()
    }
    
    // 监听用户交互
    this.observeUserInteractions()
  }

  /**
   * 监听导航时间
   */
  observeNavigationTiming() {
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      entries.forEach(entry => {
        this.metrics.navigation = {
          domContentLoaded: entry.domContentLoadedEventEnd - entry.domContentLoadedEventStart,
          loadComplete: entry.loadEventEnd - entry.loadEventStart,
          firstPaint: entry.responseStart - entry.requestStart
        }
      })
    })
    observer.observe({ entryTypes: ['navigation'] })
    this.observers.push(observer)
  }

  /**
   * 监听资源加载时间
   */
  observeResourceTiming() {
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const resources = {}
      
      entries.forEach(entry => {
        const type = this.getResourceType(entry.name)
        if (!resources[type]) {
          resources[type] = []
        }
        resources[type].push({
          name: entry.name,
          duration: entry.duration,
          size: entry.transferSize
        })
      })
      
      this.metrics.resources = resources
    })
    observer.observe({ entryTypes: ['resource'] })
    this.observers.push(observer)
  }

  /**
   * 监听绘制时间
   */
  observePaintTiming() {
    const observer = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      entries.forEach(entry => {
        if (entry.name === 'first-paint') {
          this.metrics.firstPaint = entry.startTime
        } else if (entry.name === 'first-contentful-paint') {
          this.metrics.firstContentfulPaint = entry.startTime
        }
      })
    })
    observer.observe({ entryTypes: ['paint'] })
    this.observers.push(observer)
  }

  /**
   * 监听用户交互
   */
  observeUserInteractions() {
    let interactionStart = null
    
    document.addEventListener('click', (e) => {
      interactionStart = performance.now()
    }, { passive: true })
    
    document.addEventListener('scroll', () => {
      if (interactionStart) {
        const interactionDelay = performance.now() - interactionStart
        this.metrics.interactionDelay = interactionDelay
        interactionStart = null
      }
    }, { passive: true })
  }

  /**
   * 获取资源类型
   */
  getResourceType(url) {
    if (url.endsWith('.js')) return 'script'
    if (url.endsWith('.css')) return 'stylesheet'
    if (url.match(/\.(png|jpg|jpeg|gif|svg|webp)$/)) return 'image'
    if (url.startsWith('http')) return 'fetch'
    return 'other'
  }

  /**
   * 获取性能指标
   */
  getMetrics() {
    return {
      ...this.metrics,
      timestamp: Date.now()
    }
  }

  /**
   * 记录自定义性能指标
   */
  mark(name) {
    if ('performance' in window) {
      performance.mark(name)
    }
  }

  /**
   * 测量两个标记之间的时间
   */
  measure(name, startMark, endMark) {
    if ('performance' in window) {
      try {
        performance.measure(name, startMark, endMark)
        const measure = performance.getEntriesByName(name)[0]
        return measure ? measure.duration : null
      } catch (e) {
        console.error('Performance measure error:', e)
        return null
      }
    }
    return null
  }

  /**
   * 发送性能数据到服务器
   */
  async sendMetrics(url) {
    const metrics = this.getMetrics()
    try {
      await fetch(url, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(metrics)
      })
    } catch (e) {
      console.error('Failed to send performance metrics:', e)
    }
  }

  /**
   * 清理观察者
   */
  disconnect() {
    this.observers.forEach(observer => observer.disconnect())
    this.observers = []
  }
}

// 创建全局实例
const performanceMonitor = new PerformanceMonitor()

// 页面卸载时发送性能数据
window.addEventListener('beforeunload', () => {
  // 可以在这里发送性能数据到服务器
  // performanceMonitor.sendMetrics('/api/performance/metrics')
})

export default performanceMonitor
