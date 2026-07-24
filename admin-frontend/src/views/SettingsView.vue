<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  createBusinessHoliday,
  deleteBusinessHoliday,
  fetchBusinessSettings,
  updateBusinessSettings,
} from "../api";

const WEEKDAY_OPTIONS = [
  { label: "週一", value: 0 },
  { label: "週二", value: 1 },
  { label: "週三", value: 2 },
  { label: "週四", value: 3 },
  { label: "週五", value: 4 },
  { label: "週六", value: 5 },
  { label: "週日", value: 6 },
];

const loading = ref(false);
const saving = ref(false);
const holidaySaving = ref(false);
const holidays = ref([]);

const form = reactive({
  open_hour: 9,
  close_hour: 21,
  slot_interval_minutes: 60,
  buffer_minutes: 60,
  off_weekdays: [4, 5, 6],
  max_advance_days: 30,
  slot_lock_minutes: 10,
});

const holidayForm = reactive({
  holiday_date: "",
  name: "",
});

const hourOptions = computed(() =>
  Array.from({ length: 25 }, (_, hour) => ({
    label: `${String(hour).padStart(2, "0")}:00`,
    value: hour,
  })),
);

function applySettings(data) {
  form.open_hour = data.open_hour;
  form.close_hour = data.close_hour;
  form.slot_interval_minutes = data.slot_interval_minutes;
  form.buffer_minutes = data.buffer_minutes;
  form.off_weekdays = [...(data.off_weekdays || [])];
  form.max_advance_days = data.max_advance_days;
  form.slot_lock_minutes = data.slot_lock_minutes;
  holidays.value = data.holidays || [];
}

async function loadSettings() {
  loading.value = true;
  try {
    applySettings(await fetchBusinessSettings());
  } catch (error) {
    ElMessage.error("無法載入營業設定");
  } finally {
    loading.value = false;
  }
}

async function saveSettings() {
  if (form.open_hour >= form.close_hour) {
    ElMessage.warning("開始營業時間須早於結束時間");
    return;
  }
  saving.value = true;
  try {
    applySettings(
      await updateBusinessSettings({
        open_hour: form.open_hour,
        close_hour: form.close_hour,
        slot_interval_minutes: form.slot_interval_minutes,
        buffer_minutes: form.buffer_minutes,
        off_weekdays: form.off_weekdays,
        max_advance_days: form.max_advance_days,
        slot_lock_minutes: form.slot_lock_minutes,
      }),
    );
    ElMessage.success("營業設定已儲存");
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存失敗");
  } finally {
    saving.value = false;
  }
}

async function addHoliday() {
  if (!holidayForm.holiday_date) {
    ElMessage.warning("請選擇休假日期");
    return;
  }
  holidaySaving.value = true;
  try {
    await createBusinessHoliday({
      holiday_date: holidayForm.holiday_date,
      name: holidayForm.name.trim() || null,
    });
    holidayForm.holiday_date = "";
    holidayForm.name = "";
    ElMessage.success("已新增休假日");
    await loadSettings();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "新增休假日失敗");
  } finally {
    holidaySaving.value = false;
  }
}

async function removeHoliday(row) {
  try {
    await ElMessageBox.confirm(
      `確定刪除休假日 ${row.holiday_date}${row.name ? `（${row.name}）` : ""}？`,
      "刪除休假日",
      { type: "warning", confirmButtonText: "刪除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  try {
    await deleteBusinessHoliday(row.id);
    ElMessage.success("已刪除休假日");
    await loadSettings();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "刪除失敗");
  }
}

onMounted(loadSettings);
</script>

<template>
  <div v-loading="loading">
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Settings</p>
        <h1>營業設定</h1>
        <p>管理營業時段、每週休假、預約間隔與特定休假日。</p>
      </div>
      <el-button type="primary" :loading="saving" @click="saveSettings">
        儲存設定
      </el-button>
    </div>

    <el-form label-position="top" class="settings-form">
      <el-row :gutter="20">
        <el-col :xs="24" :md="12">
          <el-form-item label="開始營業">
            <el-select v-model="form.open_hour" style="width: 100%">
              <el-option
                v-for="opt in hourOptions.filter((h) => h.value < 24)"
                :key="`open-${opt.value}`"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-form-item label="結束營業">
            <el-select v-model="form.close_hour" style="width: 100%">
              <el-option
                v-for="opt in hourOptions.filter((h) => h.value > 0)"
                :key="`close-${opt.value}`"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-form-item label="時段間隔（分鐘）">
            <el-input-number
              v-model="form.slot_interval_minutes"
              :min="15"
              :max="240"
              :step="15"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-form-item label="緩衝時間（分鐘）">
            <el-input-number
              v-model="form.buffer_minutes"
              :min="0"
              :max="240"
              :step="15"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="8">
          <el-form-item label="時段鎖定（分鐘）">
            <el-input-number
              v-model="form.slot_lock_minutes"
              :min="1"
              :max="120"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :xs="24" :md="12">
          <el-form-item label="最遠可預約天數">
            <el-input-number
              v-model="form.max_advance_days"
              :min="1"
              :max="365"
              style="width: 100%"
            />
          </el-form-item>
        </el-col>
        <el-col :span="24">
          <el-form-item label="每週休假日">
            <el-checkbox-group v-model="form.off_weekdays">
              <el-checkbox
                v-for="day in WEEKDAY_OPTIONS"
                :key="day.value"
                :label="day.value"
                :value="day.value"
              >
                {{ day.label }}
              </el-checkbox>
            </el-checkbox-group>
          </el-form-item>
        </el-col>
      </el-row>
    </el-form>

    <div class="holiday-section">
      <h2>特定休假日</h2>
      <p class="holiday-hint">額外關閉的日期（例如國定假日），不受每週休假影響。</p>

      <el-form inline class="holiday-form" @submit.prevent>
        <el-form-item label="日期">
          <el-date-picker
            v-model="holidayForm.holiday_date"
            type="date"
            value-format="YYYY-MM-DD"
            format="YYYY-MM-DD"
            placeholder="選擇日期"
          />
        </el-form-item>
        <el-form-item label="名稱（選填）">
          <el-input
            v-model="holidayForm.name"
            placeholder="例如：春節"
            maxlength="100"
            style="width: 180px"
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="holidaySaving" @click="addHoliday">
            新增
          </el-button>
        </el-form-item>
      </el-form>

      <el-table :data="holidays" stripe empty-text="尚無特定休假日">
        <el-table-column prop="holiday_date" label="日期" width="140" />
        <el-table-column prop="name" label="名稱" min-width="180">
          <template #default="{ row }">
            {{ row.name || "—" }}
          </template>
        </el-table-column>
        <el-table-column label="操作" width="100" fixed="right">
          <template #default="{ row }">
            <el-button text type="danger" @click="removeHoliday(row)">刪除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.settings-form {
  margin-bottom: 32px;
}

.holiday-section h2 {
  margin: 0 0 6px;
  font-size: 1.15rem;
}

.holiday-hint {
  margin: 0 0 16px;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}

.holiday-form {
  margin-bottom: 12px;
}
</style>
