<template>
  <div 
    class="virtual-scroll-container"
    :style="{ height: containerHeight }"
    @scroll="handleScroll"
    ref="containerRef"
  >
    <div 
      class="virtual-scroll-content"
      :style="{ height: totalHeight }"
    >
      <div 
        class="virtual-scroll-items"
        :style="{ transform: `translateY(${offsetY}px)` }"
      >
        <div
          v-for="item in visibleItems"
          :key="getItemKey(item)"
          class="virtual-scroll-item"
          :style="{ height: itemHeight + 'px' }"
        >
          <slot :item="item" :index="item.index"></slot>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'

const props = defineProps({
  // 数据列表
  items: {
    type: Array,
    required: true
  },
  // 每个item的高度
  itemHeight: {
    type: Number,
    default: 50
  },
  // 容器高度
  containerHeight: {
    type: String,
    default: '400px'
  },
  // 缓冲区大小（额外渲染的item数量）
  bufferSize: {
    type: Number,
    default: 5
  },
  // 获取item key的函数
  keyField: {
    type: String,
    default: 'id'
  }
})

const emit = defineEmits(['scroll'])

const containerRef = ref(null)
const scrollTop = ref(0)

// 计算总高度
const totalHeight = computed(() => {
  return props.items.length * props.itemHeight + 'px'
})

// 计算可见区域的起始索引
const startIndex = computed(() => {
  return Math.max(0, Math.floor(scrollTop.value / props.itemHeight) - props.bufferSize)
})

// 计算可见区域的结束索引
const endIndex = computed(() => {
  const containerHeight = containerRef.value?.clientHeight || 0
  const visibleCount = Math.ceil(containerHeight / props.itemHeight)
  return Math.min(
    props.items.length - 1,
    startIndex.value + visibleCount + props.bufferSize * 2
  )
})

// 计算可见的items
const visibleItems = computed(() => {
  const items = []
  for (let i = startIndex.value; i <= endIndex.value; i++) {
    if (props.items[i]) {
      items.push({
        ...props.items[i],
        index: i
      })
    }
  }
  return items
})

// 计算偏移量
const offsetY = computed(() => {
  return startIndex.value * props.itemHeight
})

// 获取item的key
const getItemKey = (item) => {
  return item[props.keyField] || item.index
}

// 处理滚动事件
const handleScroll = (e) => {
  scrollTop.value = e.target.scrollTop
  emit('scroll', {
    scrollTop: e.target.scrollTop,
    startIndex: startIndex.value,
    endIndex: endIndex.value
  })
}

// 滚动到指定位置
const scrollTo = (index) => {
  if (containerRef.value) {
    const targetScrollTop = index * props.itemHeight
    containerRef.value.scrollTop = targetScrollTop
  }
}

// 暴露方法给父组件
defineExpose({
  scrollTo
})

// 监听items变化，重置滚动位置
watch(() => props.items.length, () => {
  scrollTop.value = 0
})
</script>

<style scoped>
.virtual-scroll-container {
  overflow-y: auto;
  overflow-x: hidden;
  position: relative;
}

.virtual-scroll-content {
  position: relative;
  width: 100%;
}

.virtual-scroll-items {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
}

.virtual-scroll-item {
  width: 100%;
  box-sizing: border-box;
}
</style>
