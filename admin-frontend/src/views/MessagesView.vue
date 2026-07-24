<script setup>
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";

import {
  fetchMessageTemplates,
  updateMessageTemplate,
} from "../api";

const TRIGGER_LABELS = {
  payment_instruction: "預約送出／匯款說明",
  payment_reminder: "匯款提醒",
  payment_expired: "匯款逾期取消",
  approval_success: "審核通過",
  approval_reject: "審核拒絕／取消",
};

const loading = ref(false);
const saving = ref(false);
const templates = ref([]);
const dialogVisible = ref(false);
const editing = ref(null);

const form = reactive({
  name: "",
  body: "",
  description: "",
  is_active: true,
});

function triggerLabel(key) {
  return TRIGGER_LABELS[key] || key;
}

async function loadTemplates() {
  loading.value = true;
  try {
    templates.value = await fetchMessageTemplates();
  } catch (error) {
    ElMessage.error("無法載入訊息範本");
  } finally {
    loading.value = false;
  }
}

function openEdit(row) {
  editing.value = row;
  form.name = row.name;
  form.body = row.body;
  form.description = row.description || "";
  form.is_active = row.is_active;
  dialogVisible.value = true;
}

async function submitForm() {
  if (!form.name.trim() || !form.body.trim()) {
    ElMessage.warning("名稱與內容不可空白");
    return;
  }

  saving.value = true;
  try {
    await updateMessageTemplate(editing.value.id, {
      name: form.name.trim(),
      body: form.body,
      description: form.description.trim() || null,
      is_active: form.is_active,
    });
    ElMessage.success("已更新訊息範本");
    dialogVisible.value = false;
    await loadTemplates();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存失敗");
  } finally {
    saving.value = false;
  }
}

onMounted(loadTemplates);
</script>

<template>
  <div>
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Messages</p>
        <h1>訊息範本</h1>
        <p>編輯預約、匯款提醒與審核結果的 LINE 回覆內容。</p>
      </div>
    </div>

    <el-table v-loading="loading" :data="templates" stripe>
      <el-table-column prop="name" label="名稱" min-width="160" />
      <el-table-column label="觸發時機" min-width="160">
        <template #default="{ row }">
          {{ triggerLabel(row.key) }}
        </template>
      </el-table-column>
      <el-table-column label="分類" width="120">
        <template #default="{ row }">
          {{ row.category_name || "通用" }}
        </template>
      </el-table-column>
      <el-table-column label="內容預覽" min-width="260">
        <template #default="{ row }">
          <span class="template-preview">{{ row.body }}</span>
        </template>
      </el-table-column>
      <el-table-column label="狀態" width="90">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? "啟用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="100" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">編輯</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="editing ? `編輯：${editing.name}` : '編輯訊息範本'"
      width="720px"
    >
      <el-form label-position="top">
        <el-form-item label="名稱">
          <el-input v-model="form.name" maxlength="100" />
        </el-form-item>
        <el-form-item v-if="editing" label="觸發時機">
          <el-input :model-value="triggerLabel(editing.key)" disabled />
        </el-form-item>
        <el-form-item v-if="editing?.category_name" label="分類">
          <el-input :model-value="editing.category_name" disabled />
        </el-form-item>
        <el-form-item v-if="editing?.description" label="可用變數">
          <el-alert
            :title="editing.description"
            type="info"
            :closable="false"
            show-icon
          />
        </el-form-item>
        <el-form-item label="訊息內容">
          <el-input
            v-model="form.body"
            type="textarea"
            :rows="14"
            maxlength="4000"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="說明（選填）">
          <el-input v-model="form.description" maxlength="500" />
        </el-form-item>
        <el-form-item label="啟用">
          <el-switch v-model="form.is_active" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="saving" @click="submitForm">
          儲存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>
