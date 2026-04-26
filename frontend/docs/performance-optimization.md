# 前端性能优化

## 概述

本文档描述了自定义报表查询系统的前端性能优化策略和实现方案。

## 优化策略

### 1. 代码分割和懒加载

#### Vite配置优化

在`vite.config.js`中配置了代码分割：

```javascript
build: {
  rollupOptions: {
    output: {
      manualChunks: {
        'element-plus': ['element-plus'],
        'echarts': ['echarts'],
        'vue-vendor': ['vue', 'vue-router', 'pinia']
      }
    }
  },
  cssCodeSplit: true,
  minify: 'terser',
  terserOptions: {
    compress: {
      drop_console: true,
      drop_debugger: true
    }
  }
}
```

#### 路由懒加载

使用动态导入实现路由懒加载：

```javascript
const Dashboard = () => import('@/views/Dashboard.vue')
const Templates = () => import('@/views/Templates.vue')
```

### 2. 资源优化

#### 图片懒加载

使用自定义的`v-lazy`指令实现图片懒加载：

```vue
<template>
  <img v-lazy="imageUrl" alt="懒加载图片">
</template>

<script setup>
import lazyLoad from '@/directives/lazyLoad'

const imageUrl = ref('/path/to/image.jpg')
</script>
```

#### 虚拟滚动

对于长列表使用虚拟滚动组件：

```vue
<template>
  <VirtualScroll
    :items="largeList"
    :item-height="50"
    :container-height="'400px'"
  >
    <template #default="{ item, index }">
      <div>{{ item.name }}</div>
    </template>
  </VirtualScroll>
</template>

<script setup>
import VirtualScroll from '@/components/VirtualScroll.vue'
</script>
```

### 3. 事件优化

#### 防抖和节流

使用防抖和节流优化频繁触发的事件：

```javascript
import { debounce, throttle } from '@/utils/performanceOptimization'

// 防抖：搜索输入
const handleSearch = debounce((value) => {
  // 执行搜索
}, 300)

// 节流：滚动事件
const handleScroll = throttle(() => {
  // 处理滚动
}, 100)
```

#### 使用指令

```vue
<template>
  <!-- 防抖输入 -->
  <input v-debounce="[handleInput, 300]" />
  
  <!-- 节流滚动 -->
  <div v-throttle.scroll="[handleScroll, 100]"></div>
</template>
```

### 4. 性能监控

#### 性能监控工具

使用性能监控工具收集性能指标：

```javascript
import performanceMonitor from '@/utils/performance'

// 获取性能指标
const metrics = performanceMonitor.getMetrics()

// 记录自定义标记
performanceMonitor.mark('feature-start')

// 测量性能
const duration = performanceMonitor.measure('feature-duration', 'feature-start', 'feature-end')
```

#### 监控指标

- **页面加载时间**：DOM加载时间、页面完全加载时间
- **资源加载时间**：脚本、样式、图片等资源加载时间
- **渲染性能**：首次绘制、首次内容绘制时间
- **用户交互**：交互延迟、响应时间

### 5. 组件优化

#### 组件懒加载

对于大型组件使用异步组件：

```javascript
const HeavyComponent = defineAsyncComponent(() => 
  import('@/components/HeavyComponent.vue')
)
```

#### 组件缓存

使用`<KeepAlive>`缓存组件状态：

```vue
<template>
  <KeepAlive>
    <component :is="currentComponent" />
  </KeepAlive>
</template>
```

### 6. 状态管理优化

#### 按需加载状态

使用Pinia的模块化状态管理：

```javascript
// stores/user.js
export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  
  const fetchUser = async () => {
    // 获取用户信息
  }
  
  return { user, fetchUser }
})
```

#### 状态持久化

使用持久化插件缓存状态：

```javascript
import { createPinia } from 'pinia'
import { createPersistedState } from 'pinia-plugin-persistedstate'

const pinia = createPinia()
pinia.use(createPersistedState())
```

## 性能优化工具

### 1. 性能监控工具

位置：`src/utils/performance.js`

功能：
- 监听页面加载性能
- 监听资源加载时间
- 监听绘制时间
- 监听用户交互
- 记录自定义性能指标

### 2. 懒加载指令

位置：`src/directives/lazyLoad.js`

功能：
- 图片懒加载
- 使用Intersection Observer API
- 支持加载状态和错误处理

### 3. 虚拟滚动组件

位置：`src/components/VirtualScroll.vue`

功能：
- 虚拟滚动长列表
- 只渲染可见区域的元素
- 支持缓冲区配置
- 支持滚动到指定位置

### 4. 防抖节流工具

位置：`src/utils/performanceOptimization.js`

功能：
- 防抖函数
- 节流函数
- RAF节流
- Vue指令支持

## 使用示例

### 1. 图片懒加载

```vue
<template>
  <div class="image-gallery">
    <img 
      v-for="image in images" 
      :key="image.id"
      v-lazy="image.url"
      :alt="image.name"
    />
  </div>
</template>

<script setup>
import { ref } from 'vue'
import lazyLoad from '@/directives/lazyLoad'

const images = ref([
  { id: 1, url: '/image1.jpg', name: '图片1' },
  { id: 2, url: '/image2.jpg', name: '图片2' }
])
</script>
```

### 2. 虚拟滚动

```vue
<template>
  <VirtualScroll
    :items="largeData"
    :item-height="60"
    :container-height="'500px'"
    key-field="id"
  >
    <template #default="{ item }">
      <div class="list-item">
        <span>{{ item.name }}</span>
        <span>{{ item.value }}</span>
      </div>
    </template>
  </VirtualScroll>
</template>

<script setup>
import { ref } from 'vue'
import VirtualScroll from '@/components/VirtualScroll.vue'

const largeData = ref(Array.from({ length: 10000 }, (_, i) => ({
  id: i,
  name: `项目 ${i}`,
  value: i * 10
})))
</script>
```

### 3. 防抖搜索

```vue
<template>
  <div class="search-container">
    <input 
      v-model="searchQuery"
      @input="handleSearch"
      placeholder="搜索..."
    />
    <div v-if="loading">搜索中...</div>
    <div v-else>
      <div v-for="result in searchResults" :key="result.id">
        {{ result.name }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { debounce } from '@/utils/performanceOptimization'

const searchQuery = ref('')
const searchResults = ref([])
const loading = ref(false)

const handleSearch = debounce(async (value) => {
  if (!value) {
    searchResults.value = []
    return
  }
  
  loading.value = true
  try {
    const results = await fetchSearchResults(value)
    searchResults.value = results
  } finally {
    loading.value = false
  }
}, 300)
</script>
```

### 4. 性能监控

```javascript
import performanceMonitor from '@/utils/performance'

// 记录功能开始
performanceMonitor.mark('data-fetch-start')

// 获取数据
const data = await fetchData()

// 记录功能结束
performanceMonitor.mark('data-fetch-end')

// 测量执行时间
const duration = performanceMonitor.measure(
  'data-fetch-duration',
  'data-fetch-start',
  'data-fetch-end'
)

console.log(`数据获取耗时: ${duration}ms`)

// 获取整体性能指标
const metrics = performanceMonitor.getMetrics()
console.log('性能指标:', metrics)
```

## 性能优化检查清单

### 构建优化

- [x] 启用代码分割
- [x] 启用CSS代码分割
- [x] 启用代码压缩
- [x] 移除console和debugger
- [x] 配置chunk大小警告

### 运行时优化

- [x] 实现路由懒加载
- [x] 实现图片懒加载
- [x] 实现虚拟滚动
- [x] 使用防抖和节流
- [x] 组件缓存
- [x] 按需加载状态

### 监控优化

- [x] 实现性能监控
- [x] 收集性能指标
- [x] 监控用户交互
- [x] 记录自定义指标

## 性能指标

### 目标指标

- **首次内容绘制（FCP）**：< 1.5s
- **最大内容绘制（LCP）**：< 2.5s
- **首次输入延迟（FID）**：< 100ms
- **累积布局偏移（CLS）**：< 0.1
- **首次字节时间（TTFB）**：< 600ms

### 监控方法

使用Chrome DevTools的Lighthouse工具进行性能测试：

```bash
# 在Chrome DevTools中运行Lighthouse
# 或者使用命令行工具
lighthouse http://localhost:3000 --view
```

## 最佳实践

1. **按需加载**：只加载当前需要的代码和资源
2. **缓存策略**：合理使用浏览器缓存和HTTP缓存
3. **资源压缩**：启用Gzip或Brotli压缩
4. **CDN加速**：使用CDN分发静态资源
5. **性能监控**：持续监控性能指标，及时发现问题
6. **渐进增强**：确保基本功能在低性能设备上也能使用

## 故障排查

### 性能问题排查

1. **使用Chrome DevTools**：
   - Performance面板分析运行时性能
   - Network面板分析网络请求
   - Coverage面板分析代码使用率

2. **使用Lighthouse**：
   - 运行Lighthouse获取性能评分
   - 查看优化建议

3. **分析打包结果**：
   - 使用`vite-bundle-visualizer`分析打包体积
   - 找出大文件并优化

### 常见问题

**问题：页面加载慢**
- 检查网络请求
- 优化图片大小
- 启用代码分割

**问题：交互响应慢**
- 检查事件处理
- 使用防抖节流
- 优化DOM操作

**问题：内存占用高**
- 检查内存泄漏
- 清理不再使用的对象
- 优化数据结构

## 参考资料

- [Vue.js性能优化](https://vuejs.org/guide/best-practices/performance.html)
- [Vite性能优化](https://vitejs.dev/guide/build.html)
- [Web性能优化](https://web.dev/performance/)
- [Intersection Observer API](https://developer.mozilla.org/en-US/docs/Web/API/Intersection_Observer_API)
