import { ref, watch, onUnmounted } from "vue"

/**
 * 数字滚动动画 composable
 * @param targetValue - ref 类型的目标数字
 * @param duration - 动画持续时间（毫秒），默认 1200
 * @param immediate - 是否立即开始，默认 true
 */
export function useCountUp(targetValue, duration = 1200, immediate = true) {
  const displayValue = ref(0)
  let animationId = null
  let startTime = null
  let startValue = 0

  const animate = (target, isNew) => {
    if (animationId) cancelAnimationFrame(animationId)

    if (isNew && displayValue.value === 0) {
      // 第一次加载时从 0 开始
    }

    startValue = displayValue.value
    startTime = null

    const tick = (timestamp) => {
      if (!startTime) startTime = timestamp
      const elapsed = timestamp - startTime
      const progress = Math.min(elapsed / duration, 1)

      // easeOutQuart 缓动
      const eased = 1 - Math.pow(1 - progress, 4)
      displayValue.value = Math.round(startValue + (target - startValue) * eased)

      if (progress < 1) {
        animationId = requestAnimationFrame(tick)
      } else {
        displayValue.value = target
        animationId = null
      }
    }

    animationId = requestAnimationFrame(tick)
  }

  watch(
    targetValue,
    (newVal) => {
      const target = typeof newVal === "number" ? newVal : parseInt(newVal, 10) || 0
      animate(target, true)
    },
    { immediate }
  )

  onUnmounted(() => {
    if (animationId) cancelAnimationFrame(animationId)
  })

  return { displayValue }
}
