<template>
  <div class="recognitions-page">
    <h2 class="page-title">导览识别记录</h2>

    <!-- 筛选 -->
    <div class="filter-bar">
      <el-select v-model="filterDevice" placeholder="选择设备" clearable style="width: 200px" @change="fetchData">
        <el-option label="elf2-01" value="elf2-01" />
      </el-select>
      <el-button type="primary" @click="fetchData" :icon="'Search'">查询</el-button>
    </div>

    <el-table :data="tableData" stripe v-loading="loading" style="width: 100%" max-height="520">
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="display_name" label="目标名称" min-width="140" />
      <el-table-column prop="class_name" label="类别名" min-width="150" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="domainTagType(row.domain)">{{ domainLabel(row.domain) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="置信度" width="130">
        <template #default="{ row }">
          <el-progress
            :percentage="+(row.confidence * 100).toFixed(1)"
            :color="confidenceColor(row.confidence)"
            :stroke-width="16"
          />
        </template>
      </el-table-column>
      <el-table-column prop="fps" label="FPS" width="80" />
      <el-table-column label="推理耗时" width="100">
        <template #default="{ row }">{{ row.inference_ms }}ms</template>
      </el-table-column>
      <el-table-column label="后处理" width="100">
        <template #default="{ row }">{{ row.postprocess_ms }}ms</template>
      </el-table-column>
      <el-table-column label="讲解触发" width="100">
        <template #default="{ row }">
          <el-tag :type="row.narration_triggered ? 'success' : 'info'" size="small">
            {{ row.narration_triggered ? '是' : '否' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="source" label="来源" width="80" />
      <el-table-column prop="device_id" label="设备" width="100" />
      <el-table-column label="时间" min-width="170">
        <template #default="{ row }">{{ formatTime(row.timestamp) }}</template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-bar">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        layout="total, prev, pager, next"
        @current-change="fetchData"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getRecognitions } from '@/common/request/api/recognitions.js'

const tableData = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filterDevice = ref('')

async function fetchData() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (filterDevice.value) params.device_id = filterDevice.value
    const res = await getRecognitions(params)
    if (res.status === 'success') {
      tableData.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('获取识别记录失败:', e)
  } finally {
    loading.value = false
  }
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

function domainLabel(domain) {
  const map = {
    landmark: '景点',
    scenic: '景点',
    animal: '动物',
    marine: '海洋生物',
    exhibit: '展品',
  }
  return map[domain] || '导览目标'
}

function domainTagType(domain) {
  const map = {
    landmark: '',
    scenic: '',
    animal: 'success',
    marine: 'primary',
    exhibit: 'warning',
  }
  return map[domain] || 'info'
}

function confidenceColor(val) {
  if (val >= 0.95) return '#67C23A'
  if (val >= 0.85) return '#E6A23C'
  return '#F56C6C'
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.recognitions-page {
  padding: 24px;
  height: 100%;
  overflow-y: auto;
}

.page-title {
  font-size: 22px;
  font-weight: 600;
  color: #5D3A2A;
  margin-bottom: 20px;
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  align-items: center;
}

.pagination-bar {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

/* ===== 移动端响应式 ===== */
@media (max-width: 767px) {
  .recognitions-page {
    padding: 16px;
  }

  .page-title {
    font-size: 18px;
    margin-bottom: 14px;
  }

  .filter-bar {
    flex-wrap: wrap;
    gap: 8px;
  }

  .filter-bar .el-select {
    width: 100% !important;
  }

  /* 表格横向滚动 */
  .recognitions-page :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }

  .pagination-bar {
    justify-content: center;
  }
}
</style>
