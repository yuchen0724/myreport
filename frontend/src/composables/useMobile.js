import { ref, computed, onMounted, onUnmounted } from 'vue'

/**
 * 移动端检测与响应式 composable
 * 提供设备类型检测、屏幕尺寸响应、以及便捷的断点工具
 */
export function useMobile(options = {}) {
  const {
    mobileBreakpoint = 768,
    tabletBreakpoint = 1024,
    mobileMenuBreakpoint = 768,
  } = options

  // 屏幕宽度响应式
  const windowWidth = ref(typeof window !== 'undefined' ? window.innerWidth : 1024)
  const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 768)

  // 计算属性
  const isMobile = computed(() => windowWidth.value < mobileBreakpoint)
  const isTablet = computed(() => windowWidth.value >= mobileBreakpoint && windowWidth.value < tabletBreakpoint)
  const isDesktop = computed(() => windowWidth.value >= tabletBreakpoint)
  const isMobileOrTablet = computed(() => windowWidth.value < tabletBreakpoint)

  // 移动端菜单状态
  const mobileMenuVisible = ref(false)

  const toggleMobileMenu = () => {
    mobileMenuVisible.value = !mobileMenuVisible.value
  }

  const closeMobileMenu = () => {
    mobileMenuVisible.value = false
  }

  // 设备方向
  const isPortrait = computed(() => windowHeight.value > windowWidth.value)
  const isLandscape = computed(() => windowWidth.value > windowHeight.value)

  // 响应式类名
  const responsiveClass = computed(() => {
    if (isMobile.value) return 'is-mobile'
    if (isTablet.value) return 'is-tablet'
    return 'is-desktop'
  })

  // 触摸设备检测
  const isTouchDevice = computed(() => {
    if (typeof window === 'undefined') return false
    return 'ontouchstart' in window || navigator.maxTouchPoints > 0
  })

  // 屏幕尺寸等级（用于 CSS 类）
  const screenSize = computed(() => {
    const w = windowWidth.value
    if (w < 480) return 'xs'
    if (w < 768) return 'sm'
    if (w < 1024) return 'md'
    if (w < 1200) return 'lg'
    return 'xl'
  })

  // 监听窗口大小变化
  let resizeTimer = null
  const handleResize = () => {
    // 防抖处理
    clearTimeout(resizeTimer)
    resizeTimer = setTimeout(() => {
      windowWidth.value = window.innerWidth
      windowHeight.value = window.innerHeight
    }, 100)
  }

  onMounted(() => {
    if (typeof window !== 'undefined') {
      window.addEventListener('resize', handleResize, { passive: true })
      // 初始值
      windowWidth.value = window.innerWidth
      windowHeight.value = window.innerHeight
    }
  })

  onUnmounted(() => {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', handleResize)
      clearTimeout(resizeTimer)
    }
  })

  return {
    windowWidth,
    windowHeight,
    isMobile,
    isTablet,
    isDesktop,
    isMobileOrTablet,
    isPortrait,
    isLandscape,
    isTouchDevice,
    screenSize,
    responsiveClass,
    mobileMenuVisible,
    toggleMobileMenu,
    closeMobileMenu,
  }
}
