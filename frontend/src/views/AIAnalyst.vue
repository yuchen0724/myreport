<template>
  <div class="ai-analyst">
    <el-card class="ai-analyst-card">
      <template #header>
        <div class="card-header">
          <el-icon><MagicStick /></el-icon>
          <span>AI 数据分析师</span>
          <div class="header-controls">
            <el-select
              v-model="dataSourceId"
              placeholder="选择数据源"
              size="small"
              style="width: 200px"
              @change="onDataSourceChange"
            >
              <el-option
                v-for="ds in dataSources"
                :key="ds.id"
                :label="`${ds.name}（${ds.id}）`"
                :value="ds.id"
              />
            </el-select>
            <el-select
              v-if="showGroupSelect && dataSourceId"
              v-model="groupId"
              placeholder="选择集团（可选）"
              clearable
              filterable
              size="small"
              style="width: 200px; margin-left: 8px"
              :loading="groupLoading"
            >
              <el-option
                v-for="g in groups"
                :key="g.group_id"
                :label="`${g.group_name}（${g.group_id}）`"
                :value="g.group_id"
              />
            </el-select>
            <el-button
              size="small"
              type="danger"
              plain
              style="margin-left: 8px"
              @click="clearChat"
            >
              新对话
            </el-button>
          </div>
        </div>
      </template>

      <!-- 消息区域 -->
      <div
        ref="chatContainer"
        class="chat-container"
      >
        <div v-if="messages.length === 0" class="empty-state">
          <el-icon :size="64" color="#c0c4cc"><MagicStick /></el-icon>
          <h3>AI 数据分析师</h3>
          <p>我可以帮你查询数据、生成图表、分析数据洞察</p>
          <div class="quick-actions">
            <el-button
              v-for="(q, idx) in quickQuestions"
              :key="idx"
              size="small"
              @click="sendQuickQuestion(q)"
            >
              {{ q }}
            </el-button>
          </div>
        </div>

        <div
          v-for="(msg, idx) in messages"
          :key="idx"
          class="message"
          :class="[msg.role]"
        >
          <div class="message-avatar">
            <el-icon v-if="msg.role === 'user'" :size="20"><User /></el-icon>
            <el-icon v-else :size="20"><MagicStick /></el-icon>
          </div>
          <div class="message-body">
            <div class="message-role">{{ msg.role === 'user' ? '我' : 'AI 助手' }}<span class="msg-time">{{ msg.time || '' }}</span></div>

            <!-- 工具调用记录 -->
            <div v-if="msg.tool_calls && msg.tool_calls.length > 0" class="tool-calls">
              <div
                v-for="(tc, tIdx) in msg.tool_calls"
                :key="tIdx"
                class="tool-call-item"
              >
                <el-tag size="small" type="info" effect="dark">
                  <el-icon><SetUp /></el-icon>
                  {{ tc.tool_name }}
                </el-tag>
                <el-collapse>
                  <el-collapse-item :title="'查看详情'">
                    <div class="tool-detail">
                      <div class="tool-detail-label">输入:</div>
                      <pre class="code-block">{{ formatJson(tc.tool_input) }}</pre>
                      <div class="tool-detail-label">输出:</div>
                      <pre class="code-block">{{ tc.tool_output }}</pre>
                    </div>
                  </el-collapse-item>
                </el-collapse>
              </div>
            </div>

            <!-- 反馈按钮 -->
            <div v-if="msg.role === 'assistant' && !isStreaming" class="feedback-btns">
              <el-button size="small" text circle :type="msg._liked === true ? 'primary' : ''" @click="likeMessage(idx)">
                <el-icon><Promotion /></el-icon>
              </el-button>
              <el-button size="small" text circle :type="msg._liked === false ? 'danger' : ''" @click="showFeedback(idx)">
                <el-icon><Close /></el-icon>
              </el-button>
            </div>

            <!-- 反馈对话框 -->
            <el-dialog v-model="msg._showFeedback" title="反馈问题" width="500px" :close-on-click-modal="false">
              <el-form label-position="top">
                <el-form-item label="原始 SQL">
                  <pre class="code-block">{{ getToolSql(msg.tool_calls) }}</pre>
                </el-form-item>
                <el-form-item label="修正后的 SQL">
                  <el-input v-model="msg._correctedSql" type="textarea" :rows="4" placeholder="请输入修正后的 SQL"></el-input>
                </el-form-item>
                <el-form-item label="补充说明（可选）">
                  <el-input v-model="msg._userFeedback" type="textarea" :rows="2" placeholder="还有什么需要补充的？"></el-input>
                </el-form-item>
              </el-form>
              <template #footer>
                <el-button @click="msg._showFeedback = false">取消</el-button>
                <el-button type="primary" @click="submitFeedback(idx)" :loading="msg._submitting">提交反馈</el-button>
              </template>
            </el-dialog>

            <!-- 图表展示 -->
            <div v-if="msg.chart_config" class="chart-container">
              <div :id="'chart-' + idx" class="chart"></div>
            </div>

            <!-- 文本内容 -->
            <div
              v-if="msg.content"
              class="message-content"
              v-html="renderMarkdown(msg.content)"
            ></div>

            <!-- 流式输出中 -->
            <div v-if="msg.streaming" class="streaming-indicator">
              <span class="dot"></span>
              <span class="dot"></span>
              <span class="dot"></span>
            </div>
          </div>
        </div>

        <!-- 流式消息占位 -->
        <div v-if="isStreaming && (streamingMessage || streamingChart)" class="message assistant">
          <div class="message-avatar">
            <el-icon :size="20"><MagicStick /></el-icon>
          </div>
          <div class="message-body">
            <div class="message-role">AI 助手</div>
            <div v-if="streamingToolCalls.length > 0" class="tool-calls">
              <div
                v-for="(tc, tIdx) in streamingToolCalls"
                :key="tIdx"
                class="tool-call-item"
              >
                <el-tag size="small" :type="tc.done ? 'success' : 'warning'" effect="dark">
                  <el-icon><SetUp /></el-icon>
                  {{ tc.tool_name }}
                  <span v-if="!tc.done" class="spinner"></span>
                </el-tag>
              </div>
            </div>
            <!-- 流式图表占位：chart 事件到达时直接渲染 -->
            <div v-if="streamingChart" class="chart-container">
              <div id="streaming-chart" class="chart"></div>
            </div>
            <div
              v-if="streamingMessage"
              class="message-content"
              v-html="renderMarkdown(streamingMessage)"
            ></div>
          </div>
        </div>
      </div>

      <!-- 输入区域 -->
      <div class="input-area">
        <el-input
          ref="inputRef"
          v-model="inputMessage"
          type="textarea"
          :rows="2"
          placeholder="输入你的数据分析问题，例如：查询最近一个月各门店的销售额趋势"
          :disabled="isStreaming"
          @keydown.enter.exact="sendMessage"
        />
        <el-button
          type="primary"
          :disabled="!inputMessage.trim() || isStreaming || !dataSourceId"
          :loading="isStreaming"
          @click="sendMessage"
        >
          <el-icon v-if="!isStreaming"><Promotion /></el-icon>
          {{ isStreaming ? '分析中...' : '发送' }}
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script>
import { ref, nextTick, onMounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { MagicStick, User, SetUp, Promotion } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import { chatStream } from '@/api/aiAnalyst'
import { getGroups } from '@/api/nl2sql'
import { sanitizeHtml } from '@/utils/sanitizeHtml'

// 简易 markdown 渲染
function renderMarkdown(text) {
  if (!text) return ''
  const html = text
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="code-block"><code>$2</code></pre>')
    .replace(/`([^`]+)`/g, '<code class="inline-code">$1</code>')
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\n/g, '<br>')
  return sanitizeHtml(html)
}

export default {
  name: 'AIAnalyst',
  components: { MagicStick, User, SetUp, Promotion },
  setup() {
    // 会话兜底：即使页面 full reload（例如调试器开关），也尽量保留 ai-analyst 对话内容
    const SESSION_KEY = 'ai_analyst_session_v1'
    const chatContainer = ref(null)
    const inputRef = ref(null)
    const inputMessage = ref('')
    const messages = ref([])
    const isStreaming = ref(false)
    const streamingMessage = ref('')
    const streamingToolCalls = ref([])
    const streamingChart = ref(null)

    const dataSourceId = ref(null)
    const groupId = ref(null)
    const conversationId = ref(null)
    const dataSources = ref([])
    const groups = ref([])
    const groupLoading = ref(false)

    const quickQuestions = [
      '查看所有可用的表',
      '最近的销售趋势如何？',
      '哪个门店销售额最高？',
      '帮我分析数据概况',
    ]

    const showGroupSelect = ref(false)

    // 页面初始化：从 sessionStorage 恢复会话
    function persistState() {
      try {
        sessionStorage.setItem(
          SESSION_KEY,
          JSON.stringify({
            conversationId: conversationId.value,
            dataSourceId: dataSourceId.value,
            groupId: groupId.value,
            messages: messages.value,
          })
        )
      } catch (_) {
        // ignore
      }
    }

    function restoreState() {
      try {
        const raw = sessionStorage.getItem(SESSION_KEY)
        if (!raw) return
        const state = JSON.parse(raw)
        conversationId.value = state.conversationId ?? null
        dataSourceId.value = state.dataSourceId ?? null
        groupId.value = state.groupId ?? null
        messages.value = Array.isArray(state.messages) ? state.messages : []
      } catch (_) {
        // ignore
      }
    }

    // 获取数据源列表
    async function loadDataSources() {
      try {
        const res = await fetch('/api/datasources', {
          headers: {
            Authorization: `Bearer ${sessionStorage.getItem('token')}`,
          },
        })
        const data = await res.json()
        dataSources.value = Array.isArray(data) ? data : data.data || []
      } catch (e) {
        console.error('获取数据源列表失败', e)
      }
    }

    // 数据源切换时加载集团列表
    async function onDataSourceChange(dsId) {
      if (!dsId) {
        groups.value = []
        groupId.value = null
        showGroupSelect.value = false
        return
      }

      // 检查数据源是否支持集团
      const ds = dataSources.value.find((d) => d.id === dsId)
      showGroupSelect.value = ds?.load_group || false

      if (showGroupSelect.value) {
        groupLoading.value = true
        try {
          groups.value = await getGroups(dsId)
        } catch (e) {
          groups.value = []
        } finally {
          groupLoading.value = false
        }
      }
    }

    // 滚动到底部
    function scrollToBottom() {
      nextTick(() => {
        if (chatContainer.value) {
          chatContainer.value.scrollTop = chatContainer.value.scrollHeight
        }
      })
    }

    // 恢复状态后确保滚动到底部
    restoreState()
    nextTick(() => scrollToBottom())


    // 发送消息
    function sendMessage(e) {
      if (e && e.preventDefault) e.preventDefault()
      if (!inputMessage.value.trim() || isStreaming.value || !dataSourceId.value) return

      const msg = inputMessage.value.trim()
      inputMessage.value = ''

      // 添加用户消息（含时间戳）
      messages.value.push({
        role: 'user',
        content: msg,
        time: new Date().toLocaleTimeString(),
      })
      persistState()
      scrollToBottom()

      // 流式请求
      isStreaming.value = true
      streamingMessage.value = ''
      streamingToolCalls.value = []
      streamingChart.value = null
      // 清理旧的流式图表实例
      if (window._streamingChart) {
        window._streamingChart.dispose()
        window._streamingChart = null
      }

      const streamRef = chatStream(
        {
          message: msg,
          data_source_id: dataSourceId.value,
          conversation_id: conversationId.value,
          group_id: groupId.value || undefined,
        },
        {
          onToken(content) {
            streamingMessage.value += content
            scrollToBottom()
          },
          onProgress(msg) {
            streamingMessage.value = '⏳ ' + msg
            scrollToBottom()
          },
          onToolCall(data) {
            // 将当前累积的文字作为一条独立消息输出（含时间戳）
            if (streamingMessage.value.trim()) {
              messages.value.push({
                role: 'assistant',
                content: streamingMessage.value,
                time: new Date().toLocaleTimeString(),
              })
              streamingMessage.value = ''
            }
            streamingToolCalls.value.push({
              tool_name: data.tool_name,
              tool_input: data.tool_input,
              done: false,
            })
            scrollToBottom()
          },
          onToolResult(data) {
            const lastTc = streamingToolCalls.value[streamingToolCalls.value.length - 1]
            if (lastTc) {
              lastTc.done = true
              lastTc.tool_output = data.tool_output
              // 每个工具调用完成后立即推送为独立消息
              messages.value.push({
                role: 'assistant',
                tool_calls: [{
                  tool_name: lastTc.tool_name,
                  tool_input: lastTc.tool_input,
                  tool_output: data.tool_output || '',
                }],
                time: new Date().toLocaleTimeString(),
              })
            }
            scrollToBottom()
          },
          onChart(config) {
            streamingChart.value = config
            // 图表事件到达时直接渲染到当前流式消息的占位区域
            nextTick(function() {
              var placeholder = document.getElementById('streaming-chart')
              if (!placeholder) return
              try {
                if (window._streamingChart) window._streamingChart.dispose()
                var chart = echarts.init(placeholder)
                chart.setOption(config)
                window._streamingChart = chart
              } catch (e) {
                console.error('[AI-Analyst] 流式图表渲染失败:', e)
              }
            })
            scrollToBottom()
          },
          onDone(data) {
            // 完成：将最终文字转为正式消息（工具调用已在上方独立推送）
            if (streamingMessage.value.trim()) {
              messages.value.push({
                role: 'assistant',
                content: streamingMessage.value,
                time: new Date().toLocaleTimeString(),
                chart_config: streamingChart.value,
              })
            }
            conversationId.value = data.conversation_id || conversationId.value
            // 先渲染图表到正式消息，再关流式区域（避免图表闪烁消失）
            renderCharts()
            setTimeout(function() {
              isStreaming.value = false
              streamingMessage.value = ''
              streamingToolCalls.value = []
              streamingChart.value = null
              persistState()
              scrollToBottom()
            }, 50)
          },
          onError(error) {
            messages.value.push({
              role: 'assistant',
              content: `⚠️ 错误: ${error}`,
              time: new Date().toLocaleTimeString(),
            })
            isStreaming.value = false
            streamingMessage.value = ''
            streamingToolCalls.value = []
            persistState()
            scrollToBottom()
          },
        }
      )

      // 保存 abort 引用以供取消
      streamRef._abort = streamRef.abort
    }

    function sendQuickQuestion(q) {
      inputMessage.value = q
      sendMessage()
    }

    function clearChat() {
      messages.value = []
      conversationId.value = null
      streamingMessage.value = ''
      streamingToolCalls.value = []
      streamingChart.value = null
      if (window._streamingChart) {
        window._streamingChart.dispose()
        window._streamingChart = null
      }
      persistState()
    }

    function formatJson(obj) {
      try {
        return JSON.stringify(obj, null, 2)
      } catch {
        return String(obj)
      }
    }

    function getToolSql(toolCalls) {
      if (!toolCalls || toolCalls.length === 0) return ''
      const sqlCall = toolCalls.find(tc => tc.tool_name === 'execute_sql')
      return sqlCall ? (sqlCall.tool_input?.sql || sqlCall.tool_output || '') : ''
    }

    function likeMessage(idx) {
      const msg = messages.value[idx]
      if (!msg) return
      if (msg._liked === true) {
        msg._liked = undefined
      } else {
        msg._liked = true
        msg._disliked = false
      }
    }

    function showFeedback(idx) {
      const msg = messages.value[idx]
      if (!msg) return
      msg._showFeedback = true
      msg._correctedSql = getToolSql(msg.tool_calls)
      msg._userFeedback = ''
      msg._liked = false
    }

    async function submitFeedback(idx) {
      const msg = messages.value[idx]
      if (!msg) return
      msg._submitting = true
      try {
        const body = JSON.stringify({
          data_source_id: dataSourceId.value,
          question: messages.value.filter(m => m.role === 'user').pop()?.content || '',
          original_sql: getToolSql(msg.tool_calls),
          corrected_sql: msg._correctedSql || getToolSql(msg.tool_calls),
          user_feedback: msg._userFeedback || '',
        })
        await fetch('/api/ai-analyst/feedback', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            Authorization: `Bearer ${sessionStorage.getItem('token')}`,
          },
          body,
        })
        ElMessage.success('感谢反馈！')
        msg._showFeedback = false
      } catch (e) {
        ElMessage.error('提交失败: ' + e.message)
      } finally {
        msg._submitting = false
      }
    }

    onMounted(() => {
      // 恢复会话状态
      restoreState()
      nextTick(() => {
        scrollToBottom()
        renderCharts()
        // 恢复数据源后，重新计算集团下拉状态
        if (dataSourceId.value) {
          loadDataSources().then(() => {
            onDataSourceChange(dataSourceId.value)
          })
        } else {
          loadDataSources()
        }
      })
    })

    // 渲染所有图表
    var chartInstances = {}
    function renderCharts() {
      nextTick(function() {
        var hasNewChart = false
        messages.value.forEach(function(msg, idx) {
          if (!msg.chart_config) return
          var key = 'chart-' + idx
          var chartEl = document.getElementById(key)
          if (!chartEl) return
          // 判断是否为最新消息的图表
          if (idx === messages.value.length - 1) hasNewChart = true
          if (chartInstances[key]) {
            chartInstances[key].setOption(msg.chart_config)
            return
          }
          try {
            var chart = echarts.init(chartEl)
            chart.setOption(msg.chart_config)
            chartInstances[key] = chart
            setTimeout(function() { chart.resize(); }, 200)
          } catch (e) {
            console.error('[AI-Analyst] 图表渲染失败:', e)
          }
        })
        // 仅当最新消息包含图表时才滚动到图表位置
        if (hasNewChart && chatContainer.value) {
          var lastMsg = messages.value[messages.value.length - 1]
          if (lastMsg && lastMsg.chart_config) {
            var key = 'chart-' + (messages.value.length - 1)
            var el = document.getElementById(key)
            if (el) el.scrollIntoView({ behavior: 'smooth', block: 'center' })
          }
        }
      })
    }

    // 监听消息变化，自动渲染图表
    watch(messages, () => {
      renderCharts()
    }, { deep: true })

    return {
      chatContainer,
      inputRef,
      inputMessage,
      messages,
      isStreaming,
      streamingMessage,
      streamingToolCalls,
      dataSourceId,
      groupId,
      dataSources,
      groups,
      groupLoading,
      showGroupSelect,
      quickQuestions,
      onDataSourceChange,
      sendMessage,
      sendQuickQuestion,
      clearChat,
      renderMarkdown,
      formatJson,
    }
  },
}
</script>

<style scoped>
.ai-analyst {
  height: 100%;
  padding: 16px;
}

.ai-analyst-card {
  height: calc(100vh - 120px);
  display: flex;
  flex-direction: column;
}

.ai-analyst-card :deep(.el-card__body) {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
  padding: 0;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-controls {
  margin-left: auto;
  display: flex;
  align-items: center;
}

.chat-container {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
  color: #909399;
}

.empty-state h3 {
  margin: 16px 0 8px;
  color: #303133;
}

.quick-actions {
  margin-top: 16px;
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
  justify-content: center;
}

.message {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.message.user {
  flex-direction: row-reverse;
}

.message-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.message.user .message-avatar {
  background: #409eff;
  color: white;
}

.message.assistant .message-avatar {
  background: #67c23a;
  color: white;
}

.message-body {
  max-width: 80%;
}

.message-role {
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.msg-time {
  font-size: 11px;
  color: #c0c4cc;
  margin-left: 8px;
}

.message-content {
  background: #f4f4f5;
  padding: 12px 16px;
  border-radius: 12px;
  line-height: 1.6;
  word-break: break-word;
}

.message.user .message-content {
  background: #409eff;
  color: white;
}

.tool-calls {
  margin-bottom: 8px;
}

.tool-call-item {
  margin-bottom: 4px;
}

.tool-detail {
  font-size: 12px;
}

.tool-detail-label {
  font-weight: bold;
  color: #606266;
  margin-top: 4px;
}

.code-block {
  background: #1e1e1e;
  color: #d4d4d4;
  padding: 8px 12px;
  border-radius: 6px;
  overflow-x: auto;
  font-size: 12px;
  line-height: 1.4;
  margin: 4px 0;
}

.inline-code {
  background: #e6e8eb;
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 0.9em;
}

.chart-container {
  margin: 8px 0;
  background: #fff;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  padding: 12px;
}

.chart {
  width: 100%;
  height: 300px;
  border: 2px solid #409eff;
  border-radius: 4px;
  background: #fafafa;
}

.input-area {
  padding: 12px 16px;
  border-top: 1px solid #ebeef5;
  display: flex;
  gap: 8px;
  align-items: flex-end;
}

.input-area .el-input {
  flex: 1;
}

.feedback-btns {
  display: flex;
  gap: 4px;
  margin-top: 4px;
  opacity: 0.4;
  transition: opacity 0.2s;
}
.feedback-btns:hover { opacity: 1; }

.streaming-indicator {
  display: inline-flex;
  gap: 4px;
  padding: 8px 0;
}

.dot {
  width: 8px;
  height: 8px;
  background: #409eff;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.dot:nth-child(1) { animation-delay: -0.32s; }
.dot:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}

.spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
  margin-left: 4px;
  vertical-align: middle;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
