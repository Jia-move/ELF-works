<template>
  <div class="dashboard-page">
    <h2 class="page-title">系统总览</h2>

    <!-- 统计卡片 -->
    <div class="stats-row">
      <div class="stat-card device-card">
        <div class="stat-icon">🖥️</div>
        <div class="stat-info">
          <div class="stat-value">{{ summary.online_devices }} / {{ summary.total_devices }}</div>
          <div class="stat-label">设备在线</div>
        </div>
      </div>
      <div class="stat-card recog-card">
        <div class="stat-icon">📷</div>
        <div class="stat-info">
          <div class="stat-value">{{ summary.total_recognitions }}</div>
          <div class="stat-label">识别记录</div>
        </div>
      </div>
      <div class="stat-card qa-card">
        <div class="stat-icon">💬</div>
        <div class="stat-info">
          <div class="stat-value">{{ summary.total_qa_records }}</div>
          <div class="stat-label">问答记录</div>
        </div>
      </div>
      <div class="stat-card spot-card">
        <div class="stat-icon">📍</div>
        <div class="stat-info">
          <div class="stat-value">{{ summary.current_scenic_spot ? summary.current_scenic_spot.display_name : '—' }}</div>
          <div class="stat-label">当前目标</div>
        </div>
      </div>
    </div>

    <!-- 当前景点详情 -->
    <div class="section-row">
      <div class="section current-spot">
        <h3 class="section-title">当前导览目标</h3>
        <div v-if="summary.current_scenic_spot" class="spot-detail">
          <div class="spot-name">{{ summary.current_scenic_spot.display_name }}</div>
          <div class="spot-meta">
            <el-tag type="warning" size="large">{{ (summary.current_scenic_spot.confidence * 100).toFixed(1) }}% 置信度</el-tag>
            <el-tag size="large">{{ summary.current_scenic_spot.class_name }}</el-tag>
            <el-tag v-if="summary.current_scenic_spot.domain" size="large" type="success">{{ domainLabel(summary.current_scenic_spot.domain) }}</el-tag>
          </div>
          <div class="spot-time">
            识别时间：{{ formatTime(summary.current_scenic_spot.timestamp) }}
          </div>
          <div class="spot-device">
            设备：{{ summary.current_scenic_spot.device_id }}
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="empty-icon">📭</div>
          <div>暂无识别数据</div>
        </div>
      </div>

      <!-- 设备状态 -->
      <div class="section device-status">
        <h3 class="section-title">设备状态</h3>
        <div v-if="primaryDevice" class="device-status-content">
          <div class="feature-list">
            <div class="feature-item">
              <span class="feature-label">设备 ID：</span>
              <span class="feature-value">{{ primaryDevice.name }}</span>
            </div>
            <div class="feature-item">
              <span class="feature-label">在线状态：</span>
              <el-tag :type="primaryDevice.online_status === 'online' ? 'success' : 'info'" size="small">
                {{ primaryDevice.online_status === 'online' ? '在线' : '离线' }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">运行模式：</span>
              <el-tag size="small">{{ primaryDevice.mode || '—' }}</el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">摄像头：</span>
              <el-tag :type="primaryDevice.camera_status === 'ok' ? 'success' : 'warning'" size="small">
                {{ statusLabel(primaryDevice.camera_status) }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">RKNN NPU：</span>
              <el-tag :type="primaryDevice.npu_status === 'running' ? 'success' : 'warning'" size="small">
                {{ statusLabel(primaryDevice.npu_status) }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">Qt 界面：</span>
              <el-tag :type="statusTagType(primaryDevice.qt_status)" size="small">
                {{ statusLabel(primaryDevice.qt_status) }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">文字问答：</span>
              <el-tag :type="primaryDevice.qa_status === 'available' ? 'success' : 'info'" size="small">
                {{ statusLabel(primaryDevice.qa_status) }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">语音问答：</span>
              <el-tag :type="primaryDevice.asr_status === 'available' ? 'success' : 'info'" size="small">
                {{ statusLabel(primaryDevice.asr_status) }}
              </el-tag>
            </div>
            <div class="feature-item">
              <span class="feature-label">最后心跳：</span>
              <span class="feature-value">{{ formatTime(primaryDevice.last_seen) }}</span>
            </div>
          </div>
          <div class="demo-badge" v-if="primaryDevice.is_demo">
            <el-tag type="warning" size="small">⚠ 演示设备（非真实 RK3588）</el-tag>
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="empty-icon">🖥️</div>
          <div>暂无设备数据</div>
          <div class="hint">等待 RK3588 发送心跳…</div>
        </div>
      </div>
    </div>

    <!-- 最近识别记录 -->
    <div class="section">
      <h3 class="section-title">最近识别记录
        <span class="ws-hint" v-if="wsConnected">🟢 实时连接中</span>
        <span class="ws-hint" v-else>⚫ 未连接实时推送</span>
      </h3>
      <el-table :data="recentRecognitions" stripe style="width: 100%" max-height="360">
        <el-table-column prop="display_name" label="目标名称" min-width="140" />
        <el-table-column prop="class_name" label="类别名" min-width="160" />
        <el-table-column label="置信度" width="110">
          <template #default="{ row }">
            <el-progress
              :percentage="+(row.confidence * 100).toFixed(1)"
              :color="confidenceColor(row.confidence)"
              :stroke-width="16"
            />
          </template>
        </el-table-column>
        <el-table-column label="讲解触发" width="100">
          <template #default="{ row }">
            <el-tag :type="row.narration_triggered ? 'success' : 'info'" size="small">
              {{ row.narration_triggered ? '已触发' : '未触发' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="来源" width="80">
          <template #default="{ row }">
            <el-tag size="small">{{ row.source }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="时间" min-width="170">
          <template #default="{ row }">
            {{ formatTime(row.timestamp) }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getDashboardSummary } from '@/common/request/api/dashboard.js'
import { getDevices } from '@/common/request/api/devices.js'
import { createWebSocket } from '@/common/ws/ws.js'

const summary = ref({
  total_devices: 0,
  online_devices: 0,
  total_recognitions: 0,
  total_qa_records: 0,
  current_scenic_spot: null,
})

const recentRecognitions = ref([])
const wsConnected = ref(false)
const primaryDevice = ref(null)
let ws = null

async function fetchSummary() {
  try {
    const res = await getDashboardSummary()
    if (res.status === 'success') {
      summary.value = res.data
      recentRecognitions.value = res.data.recent_recognitions || []
    }
  } catch (e) {
    console.error('获取 Dashboard 数据失败:', e)
  }
}

async function fetchDevices() {
  try {
    const res = await getDevices()
    if (res.status === 'success' && res.data.list && res.data.list.length > 0) {
      const devices = res.data.list.filter(isRealDevice)
      // 优先取非演示设备，fallback 到第一个
      primaryDevice.value = devices.find(d => !d.is_demo) || devices[0] || null
      // 用过滤后的设备数覆盖 summary 中的设备统计
      if (devices.length > 0) {
        const onlineCount = devices.filter(d => d.online_status === 'online').length
        summary.value.total_devices = devices.length
        summary.value.online_devices = onlineCount
      }
    } else {
      primaryDevice.value = null
    }
  } catch (e) {
    console.error('获取设备列表失败:', e)
  }
}

function connectWebSocket() {
  ws = createWebSocket({
    path: '/ws/events',
    onJsonMessage: (msg) => {
      if (msg.type === 'recognition_event' && msg.data) {
        const event = msg.data
        recentRecognitions.value.unshift(event)
        if (recentRecognitions.value.length > 20) {
          recentRecognitions.value = recentRecognitions.value.slice(0, 20)
        }
        summary.value.current_scenic_spot = {
          class_name: event.class_name,
          display_name: event.display_name,
          confidence: event.confidence,
          timestamp: event.timestamp,
          device_id: event.device_id,
        }
        summary.value.total_recognitions++
      }
    },
    onOpen: () => {
      wsConnected.value = true
    },
    onClose: () => {
      wsConnected.value = false
    },
    onError: () => {
      wsConnected.value = false
    },
    onStatusMessage: (s) => {
      if (s.kind === 'reconnecting') {
        wsConnected.value = false
      }
    },
    reconnect: { enabled: true, maxDelay: 15000 },
  })
}

function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleString('zh-CN', { hour12: false })
}

function confidenceColor(val) {
  if (val >= 0.95) return '#67C23A'
  if (val >= 0.85) return '#E6A23C'
  return '#F56C6C'
}

function statusLabel(val) {
  if (!val || val === 'unknown') return '未知'
  if (val === 'ok' || val === 'running' || val === 'available') return '正常'
  if (val === 'unsupported') return '预留 / 待驱动启用'
  return val
}

function domainLabel(domain) {
  const map = {
    landmark: '景点 / 建筑',
    scenic: '景点 / 建筑',
    animal: '动物 / 生物',
    marine: '海洋生物',
    exhibit: '展品',
  }
  return map[domain] || '导览目标'
}

function isRealDevice(d) {
  const name = (d.name || '').toLowerCase()
  const exclude = ['test', 'mock', 'review', 'demo-device']
  return !exclude.some(k => name.includes(k))
}

function statusTagType(val) {
  if (!val || val === 'unknown') return 'info'
  if (val === 'ok' || val === 'running' || val === 'available') return 'success'
  if (val === 'unsupported') return 'info'
  return 'warning'
}

onMounted(() => {
  fetchSummary()
  fetchDevices()
  connectWebSocket()
})

onBeforeUnmount(() => {
  if (ws) {
    ws.close()
  }
})
</script>

<style scoped>
.dashboard-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #5D3A2A;
  margin-bottom: 24px;
}

.stats-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.stat-card {
  background: white;
  border-radius: 12px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  border-left: 4px solid #F0D5C0;
}

.stat-icon {
  font-size: 32px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #5D3A2A;
}

.stat-label {
  font-size: 13px;
  color: #8B6B5A;
  margin-top: 4px;
}

.section-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 24px;
}

.section {
  background: white;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  margin-bottom: 24px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  color: #5D3A2A;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #F0D5C0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ws-hint {
  font-size: 12px;
  font-weight: 400;
}

.spot-detail {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.spot-name {
  font-size: 24px;
  font-weight: 700;
  color: #B8653A;
}

.spot-meta {
  display: flex;
  gap: 8px;
}

.spot-time, .spot-device {
  font-size: 14px;
  color: #8B6B5A;
}

.empty-state {
  text-align: center;
  padding: 40px 0;
  color: #BBB;
}

.empty-icon {
  font-size: 48px;
  margin-bottom: 12px;
}

.asr-status {
  margin-bottom: 16px;
}

.hint {
  font-size: 12px;
  color: #909399;
  margin-top: 4px;
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.feature-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 14px;
}

.feature-label {
  color: #606266;
}

.feature-value {
  color: #333;
  font-weight: 500;
}

.demo-badge {
  margin-top: 16px;
  text-align: center;
}

.device-status-content {
  min-height: 100px;
}

/* ===== 移动端响应式 ===== */
@media (max-width: 767px) {
  .dashboard-page {
    padding: 16px;
  }

  .page-title {
    font-size: 18px;
    margin-bottom: 16px;
  }

  .stats-row {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .stat-card {
    padding: 14px;
    gap: 10px;
  }

  .stat-icon {
    font-size: 24px;
  }

  .stat-value {
    font-size: 18px;
  }

  .section-row {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .section {
    padding: 14px;
  }

  .spot-name {
    font-size: 18px;
  }

  /* 表格横向滚动 */
  .section :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }
}

@media (max-width: 400px) {
  .stats-row {
    grid-template-columns: 1fr;
  }
}
</style>
