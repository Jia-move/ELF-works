<template>
  <div class="scenic-spots-page">
    <h2 class="page-title">导览内容库管理</h2>

    <div class="toolbar">
      <el-button type="primary" @click="openCreateDialog">+ 新增导览内容</el-button>
    </div>

    <el-table :data="tableData" stripe v-loading="loading" style="width: 100%" max-height="520">
      <el-table-column type="index" label="#" width="60" />
      <el-table-column prop="display_name" label="目标名称" min-width="120" />
      <el-table-column prop="class_name" label="类别名（模型）" min-width="160" />
      <el-table-column label="类型" width="110">
        <template #default="{ row }">
          <el-tag size="small" :type="domainTagType(row.domain)">{{ domainLabel(row.domain) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="introduction" label="导览讲解" min-width="200" show-overflow-tooltip />
      <el-table-column prop="narration" label="讲解文本" min-width="200" show-overflow-tooltip />
      <el-table-column label="创建时间" width="170">
        <template #default="{ row }">{{ formatTime(row.created_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" size="small" @click="openEditDialog(row)">编辑</el-button>
          <el-button link type="danger" size="small" @click="handleDelete(row)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 新增/编辑弹窗 -->
    <el-dialog
      v-model="dialogVisible"
      :title="isEdit ? '编辑导览内容' : '新增导览内容'"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px" label-position="right">
        <el-form-item label="类别名" prop="class_name">
          <el-input v-model="form.class_name" placeholder="英文类别名，如 The Statue of Liberty" />
        </el-form-item>
        <el-form-item label="目标名称" prop="display_name">
          <el-input v-model="form.display_name" placeholder="中文展示名称" />
        </el-form-item>
        <el-form-item label="类型" prop="domain">
          <el-select v-model="form.domain" placeholder="选择导览内容类型" style="width: 100%">
            <el-option label="景点 / 建筑" value="scenic" />
            <el-option label="动物 / 生物" value="animal" />
            <el-option label="海洋生物" value="marine" />
            <el-option label="展品" value="exhibit" />
          </el-select>
        </el-form-item>
        <el-form-item label="导览讲解" prop="introduction">
          <el-input v-model="form.introduction" type="textarea" :rows="2" placeholder="导览讲解简介" />
        </el-form-item>
        <el-form-item label="历史背景" prop="history">
          <el-input v-model="form.history" type="textarea" :rows="2" placeholder="历史背景" />
        </el-form-item>
        <el-form-item label="特色说明" prop="features">
          <el-input v-model="form.features" type="textarea" :rows="2" placeholder="特色说明" />
        </el-form-item>
        <el-form-item label="讲解文本" prop="narration">
          <el-input v-model="form.narration" type="textarea" :rows="3" placeholder="语音讲解文本" />
        </el-form-item>
        <el-form-item label="图片URL" prop="image_url">
          <el-input v-model="form.image_url" placeholder="导览内容图片URL（可选）" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="handleSubmit" :loading="submitting">
          {{ isEdit ? '保存' : '创建' }}
        </el-button>
      </template>
    </el-dialog>

    <!-- 删除确认 -->
    <el-dialog v-model="deleteVisible" title="确认删除" width="400px">
      <p>确定要删除导览内容「{{ deleteTarget.display_name }}」吗？此操作不可恢复。</p>
      <template #footer>
        <el-button @click="deleteVisible = false">取消</el-button>
        <el-button type="danger" @click="confirmDelete" :loading="deleting">删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { getScenicSpots, createScenicSpot, updateScenicSpot, deleteScenicSpot } from '@/common/request/api/scenicSpots.js'
import * as I from '@/common/interactive.js'

const tableData = ref([])
const loading = ref(false)
const dialogVisible = ref(false)
const deleteVisible = ref(false)
const isEdit = ref(false)
const submitting = ref(false)
const deleting = ref(false)
const editId = ref(null)
const deleteTarget = ref({})
const formRef = ref(null)

const defaultForm = {
  class_name: '',
  display_name: '',
  domain: 'scenic',
  introduction: '',
  history: '',
  features: '',
  narration: '',
  image_url: '',
}

const form = ref({ ...defaultForm })

const rules = {
  class_name: [{ required: true, message: '请输入类别名', trigger: 'blur' }],
  display_name: [{ required: true, message: '请输入目标名称', trigger: 'blur' }],
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

function domainTagType(domain) {
  const map = { scenic: '', animal: 'success', marine: 'primary', exhibit: 'warning' }
  return map[domain] || 'info'
}

async function fetchData() {
  loading.value = true
  try {
    const res = await getScenicSpots()
    if (res.status === 'success') {
      tableData.value = res.data.list || []
    }
  } catch (e) {
    console.error('获取景点列表失败:', e)
  } finally {
    loading.value = false
  }
}

function openCreateDialog() {
  isEdit.value = false
  editId.value = null
  form.value = { ...defaultForm }
  dialogVisible.value = true
}

function openEditDialog(row) {
  isEdit.value = true
  editId.value = row.id
  form.value = {
    class_name: row.class_name,
    display_name: row.display_name,
    domain: row.domain || 'scenic',
    introduction: row.introduction || '',
    history: row.history || '',
    features: row.features || '',
    narration: row.narration || '',
    image_url: row.image_url || '',
  }
  dialogVisible.value = true
}

async function handleSubmit() {
  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  submitting.value = true
  try {
    if (isEdit.value) {
      const res = await updateScenicSpot(editId.value, form.value)
      if (res.status === 'success') I.showToast('更新成功', 'success')
    } else {
      const res = await createScenicSpot(form.value)
      if (res.status === 'success') I.showToast('创建成功', 'success')
    }
    dialogVisible.value = false
    fetchData()
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '操作失败'
    I.showToast(msg, 'error')
  } finally {
    submitting.value = false
  }
}

function handleDelete(row) {
  deleteTarget.value = row
  deleteVisible.value = true
}

async function confirmDelete() {
  deleting.value = true
  try {
    const res = await deleteScenicSpot(deleteTarget.value.id)
    if (res.status === 'success') {
      I.showToast('删除成功', 'success')
      deleteVisible.value = false
      fetchData()
    }
  } catch (e) {
    const msg = e?.response?.data?.detail || e?.message || '删除失败'
    I.showToast(msg, 'error')
  } finally {
    deleting.value = false
  }
}

function formatTime(ts) {
  if (!ts) return ''
  return new Date(ts).toLocaleString('zh-CN', { hour12: false })
}

onMounted(() => {
  fetchData()
})
</script>

<style scoped>
.scenic-spots-page {
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

.toolbar {
  margin-bottom: 16px;
}

/* ===== 移动端响应式 ===== */
@media (max-width: 767px) {
  .scenic-spots-page {
    padding: 16px;
  }

  .page-title {
    font-size: 18px;
    margin-bottom: 14px;
  }

  /* 表格横向滚动 */
  .scenic-spots-page :deep(.el-table) {
    display: block;
    overflow-x: auto;
  }

  /* 弹窗适配手机宽度 */
  .scenic-spots-page :deep(.el-dialog) {
    width: 92% !important;
    max-width: 92vw;
  }

  .scenic-spots-page :deep(.el-form-item__label) {
    width: 70px !important;
  }
}
</style>
