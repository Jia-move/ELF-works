<template>
  <div class="qa-records-page">
    <h2 class="page-title">智能问答记录</h2>

    <div class="filter-bar">
      <el-select v-model="filterDevice" placeholder="选择设备" clearable style="width: 200px" @change="fetchData">
        <el-option label="elf2-01" value="elf2-01" />
      </el-select>
      <el-button type="primary" @click="fetchData">查询</el-button>
    </div>

    <el-table :data="tableData" stripe v-loading="loading" style="width: 100%" max-height="520">
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="scenic_name" label="关联目标" width="120" />
      <el-table-column prop="question" label="用户问题" min-width="220" show-overflow-tooltip />
      <el-table-column prop="answer" label="回复内容" min-width="280" show-overflow-tooltip />
      <el-table-column prop="provider" label="来源" width="80">
        <template #default="{ row }">
          <el-tag size="small">{{ row.provider }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="device_id" label="设备" width="100" />
      <el-table-column label="时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
    </el-table>

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
import { ref, onMounted, onBeforeUnmount } from 'vue'
import { getQARecords } from '@/common/request/api/qaRecords.js'

const AUTO_REFRESH_INTERVAL = 5000 // 5 秒自动刷新

const tableData = ref([])
const loading = ref(false)
const currentPage = ref(1)
const pageSize = ref(20)
const total = ref(0)
const filterDevice = ref('')
let refreshTimer = null

async function fetchData() {
  loading.value = true
  try {
    const params = { page: currentPage.value, page_size: pageSize.value }
    if (filterDevice.value) params.device_id = filterDevice.value
    const res = await getQARecords(params)
    if (res.status === 'success') {
      tableData.value = res.data.list || []
      total.value = res.data.total || 0
    }
  } catch (e) {
    console.error('获取问答记录失败:', e)
  } finally {
    loading.value = false
  }
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  fetchData()
  refreshTimer = setInterval(fetchData, AUTO_REFRESH_INTERVAL)
})

onBeforeUnmount(() => {
  if (refreshTimer) {
    clearInterval(refreshTimer)
    refreshTimer = null
  }
})
</script>

<style scoped>
.qa-records-page {
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
  .qa-records-page {
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
  .qa-records-page :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }

  .pagination-bar {
    justify-content: center;
  }
}
</style>
