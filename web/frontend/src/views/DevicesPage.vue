<template>
  <div class="devices-page">
    <h2 class="page-title">设备管理</h2>

    <div class="devices-grid">
      <div v-for="device in filteredDevices" :key="device.id" class="device-card">
        <div class="card-header">
          <div class="device-name">{{ device.name }}</div>
          <el-tag :type="device.status === 'online' ? 'success' : 'info'" size="small">
            {{ device.status === 'online' ? '在线' : '离线' }}
          </el-tag>
        </div>
        <div class="card-body">
          <div class="info-row">
            <span class="info-label">平台：</span>
            <span class="info-value">{{ device.platform }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">模型：</span>
            <span class="info-value">{{ device.model_display_name || device.model_name || '—' }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">版本：</span>
            <span class="info-value">{{ device.software_version }}</span>
          </div>
          <div class="info-row">
            <span class="info-label">摄像头：</span>
            <el-tag :type="device.camera_status === 'normal' ? 'success' : 'warning'" size="small">
              {{ device.camera_status === 'normal' ? '正常' : device.camera_status }}
            </el-tag>
          </div>
          <div class="info-row">
            <span class="info-label">Qt 界面：</span>
            <el-tag :type="device.qt_status === 'running' ? 'success' : 'warning'" size="small">
              {{ device.qt_status === 'running' ? '运行中' : device.qt_status }}
            </el-tag>
          </div>
          <div class="info-row">
            <span class="info-label">最后在线：</span>
            <span class="info-value">{{ formatTime(device.last_seen) }}</span>
          </div>
        </div>
        <div class="card-footer">
          <div class="feature-badges">
            <el-tooltip content="麦克风：预留 / 待驱动启用" placement="top">
              <el-tag type="info" size="small">🎤 麦克风：待驱动启用</el-tag>
            </el-tooltip>
            <el-tooltip content="ASR：预留 / 待接入" placement="top">
              <el-tag type="info" size="small">🔊 ASR：待接入</el-tag>
            </el-tooltip>
            <el-tooltip content="USB Audio：待内核驱动验证" placement="top">
              <el-tag type="warning" size="small">🔌 USB Audio：待驱动验证</el-tag>
            </el-tooltip>
          </div>
        </div>
      </div>

      <div v-if="filteredDevices.length === 0" class="empty-devices">
        <div class="empty-icon">🖥️</div>
        <div>暂无设备数据</div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getDevices } from '@/common/request/api/devices.js'

const devices = ref([])

function isRealDevice(d) {
  const name = (d.name || '').toLowerCase()
  const exclude = ['test', 'mock', 'review', 'demo-device']
  return !exclude.some(k => name.includes(k))
}

const filteredDevices = computed(() => {
  return devices.value.filter(isRealDevice)
})

async function fetchDevices() {
  try {
    const res = await getDevices()
    if (res.status === 'success') {
      devices.value = res.data.list || []
    }
  } catch (e) {
    console.error('获取设备列表失败:', e)
  }
}

function formatTime(ts) {
  if (!ts) return '—'
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  fetchDevices()
})
</script>

<style scoped>
.devices-page {
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

.devices-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(360px, 1fr));
  gap: 20px;
}

.device-card {
  background: white;
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  overflow: hidden;
  transition: box-shadow 0.2s;
}

.device-card:hover {
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.1);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, #FDE8D5, #F5D5C7);
}

.device-name {
  font-size: 18px;
  font-weight: 700;
  color: #5D3A2A;
}

.card-body {
  padding: 16px 20px;
}

.info-row {
  display: flex;
  align-items: center;
  padding: 6px 0;
  font-size: 14px;
}

.info-label {
  color: #8B6B5A;
  width: 90px;
  flex-shrink: 0;
}

.info-value {
  color: #333;
}

.card-footer {
  padding: 12px 20px;
  border-top: 1px solid #F5F0EB;
}

.feature-badges {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.empty-devices {
  text-align: center;
  padding: 80px 0;
  color: #BBB;
  grid-column: 1 / -1;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: 16px;
}

/* ===== 移动端响应式 ===== */
@media (max-width: 767px) {
  .devices-page {
    padding: 16px;
  }

  .page-title {
    font-size: 18px;
    margin-bottom: 16px;
  }

  .devices-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .device-card {
    border-radius: 10px;
  }

  .card-header {
    padding: 12px 16px;
  }

  .device-name {
    font-size: 16px;
  }

  .card-body {
    padding: 12px 16px;
  }

  .info-row {
    font-size: 13px;
  }

  .info-label {
    width: 70px;
  }

  .card-footer {
    padding: 10px 16px;
  }
}
</style>
