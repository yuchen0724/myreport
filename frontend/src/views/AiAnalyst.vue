<template>
  <div class="ai-analyst">
    <div class="analyst-header">
      <h2>AI 数据分析师</h2>
      <p class="subtitle">自然语言查询，智能分析数据</p>
    </div>

    <div class="chat-container">
      <!-- 消息列表 -->
      <div class="messages" ref="messagesContainer">
        <div
          v-for="(msg, index) in messages"
          :key="index"
          :class="['message', msg.role]"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'" :size="20"><User /></el-icon>
            <el-icon v-else :size="20"><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <div class="message-text" v-html="formatMessage(msg.content)"></div>
            <!-- SQL 结果表格 -->
            <div v-if="msg.type === 'query_result'" class="result-table">
              <el-table
                :data="msg.data"
                stripe
                border
                size="small"
                max-height="300"
                style="width: 100%"
              >
                <el-table-column
                  v-for="col in msg.columns"
                  :key="col.key"
                  :prop="col.key"
                  :label="col.label"
                  :min-width="120"
                />
              </el-table>
            </div>
            <!-- 图表 -->
            <div v-if="msg.type === 'chart'" class="result-chart">
              <div ref="chartContainer" class="chart-box"></div>
            </div>
          </div>
        </div>

        <!-- 加载中 -->
        <div v-if="loading" class="message assistant">
          <div class="message-avatar">
            <el-icon :size="20"><Monitor /></el-icon>
          </div>
          <div class="message-content">
            <div class="typing-indicator">
              <span></span><span></span><span></span>
            </div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          v-model="inputText"
          type="textarea"
          :rows="2"
          placeholder="输入您的数据问题，例如：查询本月销售额最高的10个门店"
          @keydown.enter.exact="sendMessage"
          :disabled="loading"
        />
        <el-button
          type="primary"
          @click="sendMessage"
          :loading="loading"
          :disabled="!inputText.trim()"
        >
          发送
        </el-button>
      </div>
    </div>

    <!-- 快捷问题 -->
    <div class="quick-questions">
      <p>快捷问题：</p>
      <div class="question-tags">
        <el-tag
          v-for="q in quickQuestions"
          :key="q"
          @click="askQuestion(q)"
          class="question-tag"
        >
          {{ q }}
        </el-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'
import { User, Monitor } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { sanitizeHtml } from '@/utils/sanitizeHtml'

const messages = ref([])
const inputText = ref('')
const loading = ref(false)
const messagesContainer = ref(null)

const quickQuestions = [
  '查询本月销售总额',
  '统计各区域门店数量',
  '分析最近7天的销售趋势',
  '找出销售额最低的门店',
  '对比本月和上月的销售数据'
]

const formatMessage = (content) => {
  // 简单的 Markdown 格式化
  return sanitizeHtml(content
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>'))
}

const scrollToBottom = async () => {
  await nextTick()
  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight
  }
}

const sendMessage = async () => {
  if (!inputText.value.trim() || loading.value) return

  const userMessage = inputText.value.trim()
  messages.value.push({ role: 'user', content: userMessage })
  inputText.value = ''
  loading.value = true

  await scrollToBottom()

  try {
    const response = await axios.post('/api/ai-analyst/chat', {
      message: userMessage,
      context: {}
    })

    const result = response.data

    if (result.type === 'text') {
      messages.value.push({
        role: 'assistant',
        content: result.content
      })
    } else if (result.type === 'query_result') {
      messages.value.push({
        role: 'assistant',
        content: `查询完成，共 ${result.data.length} 条结果：`,
        type: 'query_result',
        data: result.data,
        columns: result.columns
      })
    } else if (result.type === 'chart') {
      messages.value.push({
        role: 'assistant',
        content: '为您生成了图表：',
        type: 'chart',
        chartConfig: result.config
      })
    }
  } catch (error) {
    console.error('AI 分析师请求失败:', error)
    ElMessage.error('请求失败，请稍后重试')
    messages.value.push({
      role: 'assistant',
      content: '抱歉，处理您的请求时出现了错误，请稍后重试。'
    })
  } finally {
    loading.value = false
    await scrollToBottom()
  }
}

const askQuestion = (question) => {
  inputText.value = question
  sendMessage()
}

onMounted(() => {
  messages.value.push({
    role: 'assistant',
    content: '您好！我是 AI 数据分析师。您可以向我提问关于数据的问题，我会帮您查询和分析。例如：\n\n- **查询类**：查询本月销售总额、统计各区域门店数量\n- **分析类**：分析销售趋势、找出异常数据\n- **对比类**：对比本月和上月的数据\n\n请问您想了解什么？'
  })
})
</script>

<style scoped>
.ai-analyst {
  height: 100%;
  display: flex;
  flex-direction: column;
  padding: 20px;
}

.analyst-header {
  text-align: center;
  margin-bottom: 20px;
}

.analyst-header h2 {
  margin: 0;
  color: #303133;
}

.analyst-header .subtitle {
  margin: 5px 0 0;
  color: #909399;
  font-size: 14px;
}

.chat-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  overflow: hidden;
}

.messages {
  flex: 1;
  overflow-y: auto;
  padding: 20px;
  background: #f5f7fa;
}

.message {
  display: flex;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #409eff;
  color: white;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #67c23a;
}

.message-content {
  max-width: 70%;
  margin: 0 12px;
}

.message.user .message-content {
  text-align: right;
}

.message-text {
  background: white;
  padding: 12px 16px;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  line-height: 1.6;
}

.message.user .message-text {
  background: #409eff;
  color: white;
}

.result-table {
  margin-top: 12px;
  background: white;
  border-radius: 8px;
  overflow: hidden;
}

.result-chart {
  margin-top: 12px;
}

.chart-box {
  width: 100%;
  height: 300px;
  background: white;
  border-radius: 8px;
}

.typing-indicator {
  display: flex;
  padding: 12px 16px;
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  background: #909399;
  border-radius: 50%;
  margin: 0 2px;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) {
  animation-delay: 0.2s;
}

.typing-indicator span:nth-child(3) {
  animation-delay: 0.4s;
}

@keyframes typing {
  0%, 80%, 100% { transform: scale(0.6); opacity: 0.6; }
  40% { transform: scale(1); opacity: 1; }
}

.input-area {
  display: flex;
  gap: 12px;
  padding: 16px;
  background: white;
  border-top: 1px solid #dcdfe6;
}

.input-area :deep(.el-textarea__inner) {
  resize: none;
}

.quick-questions {
  margin-top: 16px;
}

.quick-questions p {
  margin: 0 0 8px;
  color: #606266;
  font-size: 14px;
}

.question-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.question-tag {
  cursor: pointer;
  transition: all 0.3s;
}

.question-tag:hover {
  color: #409eff;
  border-color: #409eff;
}
</style>
