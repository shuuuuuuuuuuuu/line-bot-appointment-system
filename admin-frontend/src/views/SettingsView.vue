<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  deleteDateOverride,
  fetchBusinessSettings,
  updateBusinessSettings,
  updateWeeklyHours,
  upsertDateOverride,
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

const STATUS_LABELS = {
  defaultOpen: "預設營業",
  defaultClosed: "預設休",
  specialOpen: "特別營業",
  specialClosed: "特別休",
};

const loading = ref(false);
const saving = ref(false);
const weeklySaving = ref(false);
const dayDialogVisible = ref(false);
const daySaving = ref(false);
const calendarValue = ref(new Date());
const weeklyHours = ref([]);
const dateOverrides = ref([]);

const form = reactive({
  slot_interval_minutes: 60,
  buffer_minutes: 60,
  max_advance_days: 30,
  slot_lock_minutes: 10,
});

const weeklyForm = reactive({
  items: WEEKDAY_OPTIONS.map((day) => ({
    weekday: day.value,
    is_open: day.value < 4,
    open_hour: 9,
    close_hour: 21,
    time_slots: [{ open_hour: 9, close_hour: 21 }],
  })),
});

const dayForm = reactive({
  target_date: "",
  mode: "default",
  open_hour: 9,
  close_hour: 21,
  time_slots: [{ open_hour: 9, close_hour: 21 }],
  note: "",
  override_id: null,
});

const hourOptions = computed(() =>
  Array.from({ length: 25 }, (_, hour) => ({
    label: `${String(hour).padStart(2, "0")}:00`,
    value: hour,
  })),
);

const overrideMap = computed(() => {
  const map = new Map();
  for (const item of dateOverrides.value) {
    map.set(item.target_date, item);
  }
  return map;
});

const weeklyMap = computed(() => {
  const map = new Map();
  for (const item of weeklyHours.value) {
    map.set(item.weekday, item);
  }
  return map;
});


function normalizeSlots(slots, fallbackOpen = 9, fallbackClose = 21) {
  const normalized = (slots || [])
    .map((item) => ({
      open_hour: Number(item?.open_hour),
      close_hour: Number(item?.close_hour),
    }))
    .filter((item) => Number.isInteger(item.open_hour) && Number.isInteger(item.close_hour));
  if (!normalized.length) {
    return [{ open_hour: fallbackOpen, close_hour: fallbackClose }];
  }
  return normalized.sort((a, b) => a.open_hour - b.open_hour);
}

function canAddAnotherSlot(slots) {
  if (!slots?.length) return false;
  const last = slots[slots.length - 1];
  return Number.isInteger(last.open_hour) && Number.isInteger(last.close_hour) && last.open_hour < last.close_hour;
}

function addSlot(slots) {
  if (!canAddAnotherSlot(slots)) return;
  slots.push({ open_hour: null, close_hour: null });
}

function removeSlot(slots, index) {
  if (!slots || slots.length <= 1) return;
  slots.splice(index, 1);
}

function slotsToBounds(slots, fallbackOpen = 9, fallbackClose = 21) {
  const normalized = normalizeSlots(slots, fallbackOpen, fallbackClose);
  return {
    open_hour: normalized[0].open_hour,
    close_hour: normalized[normalized.length - 1].close_hour,
    time_slots: normalized,
  };
}

function validateSlots(slots, label) {
  for (const slot of slots || []) {
    if (!Number.isInteger(slot?.open_hour) || !Number.isInteger(slot?.close_hour)) {
      ElMessage.warning(`${label} 的每段都要選開始與結束時間`);
      return false;
    }
  }
  const normalized = normalizeSlots(slots);
  for (const slot of normalized) {
    if (slot.open_hour >= slot.close_hour) {
      ElMessage.warning(`${label} 的開始時間須早於結束時間`);
      return false;
    }
  }
  for (let i = 1; i < normalized.length; i += 1) {
    if (normalized[i - 1].close_hour > normalized[i].open_hour) {
      ElMessage.warning(`${label} 的多時段不可重疊`);
      return false;
    }
  }
  return true;
}

function toDateStr(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function jsDateToPyWeekday(date) {
  return (date.getDay() + 6) % 7;
}

function formatHourRange(openHour, closeHour) {
  return `${String(openHour).padStart(2, "0")}:00–${String(closeHour).padStart(2, "0")}:00`;
}

function formatSlotsDisplay(slots, fallbackOpen = 9, fallbackClose = 21) {
  const normalized = normalizeSlots(slots, fallbackOpen, fallbackClose);
  return normalized.map((slot) => formatHourRange(slot.open_hour, slot.close_hour)).join(" / ");
}

function resolveDayStatus(date) {
  const dateStr = toDateStr(date);
  const override = overrideMap.value.get(dateStr);
  if (override) {
    if (!override.is_open) {
      return {
        key: "specialClosed",
        label: STATUS_LABELS.specialClosed,
        isOpen: false,
        hours: null,
        note: override.note,
        override,
      };
    }
    return {
      key: "specialOpen",
      label: STATUS_LABELS.specialOpen,
      isOpen: true,
      hours: formatSlotsDisplay(override.time_slots, override.open_hour, override.close_hour),
      note: override.note,
      override,
    };
  }

  const weekly = weeklyMap.value.get(jsDateToPyWeekday(date));
  if (!weekly || !weekly.is_open) {
    return {
      key: "defaultClosed",
      label: STATUS_LABELS.defaultClosed,
      isOpen: false,
      hours: null,
      override: null,
    };
  }
  return {
    key: "defaultOpen",
    label: STATUS_LABELS.defaultOpen,
    isOpen: true,
    hours: formatSlotsDisplay(weekly.time_slots, weekly.open_hour, weekly.close_hour),
    override: null,
  };
}

function applySettings(data) {
  form.slot_interval_minutes = data.slot_interval_minutes;
  form.buffer_minutes = data.buffer_minutes;
  form.max_advance_days = data.max_advance_days;
  form.slot_lock_minutes = data.slot_lock_minutes;
  weeklyHours.value = data.weekly_hours || [];
  dateOverrides.value = data.date_overrides || [];

  weeklyForm.items = WEEKDAY_OPTIONS.map((day) => {
    const existing = (data.weekly_hours || []).find((item) => item.weekday === day.value);
    const timeSlots = (existing?.time_slots?.length
      ? normalizeSlots(existing.time_slots)
      : normalizeSlots([], existing?.open_hour ?? 9, existing?.close_hour ?? 21));
    const bounds = slotsToBounds(timeSlots, existing?.open_hour ?? 9, existing?.close_hour ?? 21);
    return {
      weekday: day.value,
      is_open: existing?.is_open ?? day.value < 4,
      open_hour: bounds.open_hour,
      close_hour: bounds.close_hour,
      time_slots: bounds.time_slots,
    };
  });
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

async function saveBookingParams() {
  saving.value = true;
  try {
    applySettings(
      await updateBusinessSettings({
        slot_interval_minutes: form.slot_interval_minutes,
        buffer_minutes: form.buffer_minutes,
        max_advance_days: form.max_advance_days,
        slot_lock_minutes: form.slot_lock_minutes,
      }),
    );
    ElMessage.success("預約參數已儲存");
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存失敗");
  } finally {
    saving.value = false;
  }
}

async function saveWeeklyTemplate() {
  for (const item of weeklyForm.items) {
    if (item.is_open && !validateSlots(item.time_slots, WEEKDAY_OPTIONS[item.weekday].label)) {
      return;
    }
  }

  weeklySaving.value = true;
  try {
    const payloadItems = weeklyForm.items.map((item) => {
      if (!item.is_open) {
        return { ...item, time_slots: [], open_hour: 9, close_hour: 21 };
      }
      const bounds = slotsToBounds(item.time_slots, item.open_hour, item.close_hour);
      return {
        weekday: item.weekday,
        is_open: true,
        open_hour: bounds.open_hour,
        close_hour: bounds.close_hour,
        time_slots: bounds.time_slots,
      };
    });
    applySettings(await updateWeeklyHours({ items: payloadItems }));
    ElMessage.success("每週範本已儲存");
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存每週範本失敗");
  } finally {
    weeklySaving.value = false;
  }
}

function openDayDialog(date) {
  const dateStr = toDateStr(date);
  const status = resolveDayStatus(date);
  const weekly = weeklyMap.value.get(jsDateToPyWeekday(date));

  dayForm.target_date = dateStr;
  dayForm.note = status.override?.note || "";
  dayForm.override_id = status.override?.id || null;

  if (status.override) {
    dayForm.mode = status.override.is_open ? "specialOpen" : "specialClosed";
    dayForm.open_hour = status.override.open_hour ?? weekly?.open_hour ?? 9;
    dayForm.close_hour = status.override.close_hour ?? weekly?.close_hour ?? 21;
    dayForm.time_slots = normalizeSlots(status.override.time_slots, dayForm.open_hour, dayForm.close_hour);
  } else {
    dayForm.mode = "default";
    dayForm.open_hour = weekly?.open_hour ?? 9;
    dayForm.close_hour = weekly?.close_hour ?? 21;
    dayForm.time_slots = normalizeSlots(weekly?.time_slots, dayForm.open_hour, dayForm.close_hour);
  }

  dayDialogVisible.value = true;
}

async function saveDayOverride() {
  if (dayForm.mode === "default") {
    if (!dayForm.override_id) {
      dayDialogVisible.value = false;
      return;
    }
    daySaving.value = true;
    try {
      await deleteDateOverride(dayForm.override_id);
      await loadSettings();
      ElMessage.success("已恢復為每週範本");
      dayDialogVisible.value = false;
    } catch (error) {
      const detail = error.response?.data?.detail;
      ElMessage.error(detail || "清除覆寫失敗");
    } finally {
      daySaving.value = false;
    }
    return;
  }

  if (dayForm.mode === "specialOpen" && !validateSlots(dayForm.time_slots, "特別營業時段")) {
    return;
  }

  daySaving.value = true;
  try {
    const payload = {
      target_date: dayForm.target_date,
      is_open: dayForm.mode === "specialOpen",
      note: dayForm.note.trim() || null,
    };
    if (payload.is_open) {
      const bounds = slotsToBounds(dayForm.time_slots, dayForm.open_hour, dayForm.close_hour);
      payload.open_hour = bounds.open_hour;
      payload.close_hour = bounds.close_hour;
      payload.time_slots = bounds.time_slots;
    }
    await upsertDateOverride(payload);
    await loadSettings();
    ElMessage.success("日期設定已儲存");
    dayDialogVisible.value = false;
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存日期設定失敗");
  } finally {
    daySaving.value = false;
  }
}

async function clearDayOverride() {
  if (!dayForm.override_id) {
    dayForm.mode = "default";
    return;
  }
  try {
    await ElMessageBox.confirm(
      `確定清除 ${dayForm.target_date} 的特別設定，恢復為每週範本？`,
      "清除覆寫",
      { type: "warning", confirmButtonText: "清除", cancelButtonText: "取消" },
    );
  } catch {
    return;
  }

  daySaving.value = true;
  try {
    await deleteDateOverride(dayForm.override_id);
    await loadSettings();
    ElMessage.success("已恢復為每週範本");
    dayDialogVisible.value = false;
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "清除覆寫失敗");
  } finally {
    daySaving.value = false;
  }
}

onMounted(loadSettings);
</script>

<template>
  <div v-loading="loading" class="settings-page">
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Settings</p>
        <h1>營業設定</h1>
        <p>以月曆管理每週範本與特定日期營業／休假調整。</p>
      </div>
    </div>

    <el-row :gutter="20">
      <el-col :xs="24" :lg="8">
        <section class="panel">
          <div class="panel-header">
            <h2>預約參數</h2>
            <el-button
              type="primary"
              size="small"
              :loading="saving"
              @click="saveBookingParams"
            >
              儲存預約參數
            </el-button>
          </div>
          <el-form label-position="top">
            <el-form-item label="時段間隔（分鐘）">
              <el-input-number
                v-model="form.slot_interval_minutes"
                :min="15"
                :max="240"
                :step="15"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="緩衝時間（分鐘）">
              <el-input-number
                v-model="form.buffer_minutes"
                :min="0"
                :max="240"
                :step="15"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="時段鎖定（分鐘）">
              <el-input-number
                v-model="form.slot_lock_minutes"
                :min="1"
                :max="120"
                style="width: 100%"
              />
            </el-form-item>
            <el-form-item label="最遠可預約天數">
              <el-input-number
                v-model="form.max_advance_days"
                :min="1"
                :max="365"
                style="width: 100%"
              />
            </el-form-item>
          </el-form>
        </section>

        <section class="panel">
          <div class="panel-header">
            <h2>每週範本</h2>
            <el-button
              type="primary"
              size="small"
              :loading="weeklySaving"
              @click="saveWeeklyTemplate"
            >
              儲存範本
            </el-button>
          </div>
          <div class="weekly-list">
            <div
              v-for="item in weeklyForm.items"
              :key="item.weekday"
              class="weekly-row"
            >
              <div class="weekly-row-title">
                <span>{{ WEEKDAY_OPTIONS[item.weekday].label }}</span>
                <el-switch v-model="item.is_open" />
              </div>
              <div v-if="item.is_open" class="weekly-slot-list">
                <div
                  v-for="(slot, slotIndex) in item.time_slots"
                  :key="`weekly-slot-${item.weekday}-${slotIndex}`"
                  class="weekly-row-hours"
                >
                  <el-select v-model="slot.open_hour" style="width: 100%">
                    <el-option
                      v-for="opt in hourOptions.filter((h) => h.value < 24)"
                      :key="`weekly-open-${item.weekday}-${slotIndex}-${opt.value}`"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <span class="weekly-separator">至</span>
                  <el-select v-model="slot.close_hour" style="width: 100%">
                    <el-option
                      v-for="opt in hourOptions.filter((h) => h.value > 0)"
                      :key="`weekly-close-${item.weekday}-${slotIndex}-${opt.value}`"
                      :label="opt.label"
                      :value="opt.value"
                    />
                  </el-select>
                  <el-button
                    v-if="slotIndex > 0"
                    text
                    type="danger"
                    @click="removeSlot(item.time_slots, slotIndex)"
                  >
                    移除
                  </el-button>
                  <el-button
                    v-if="slotIndex === item.time_slots.length - 1 && canAddAnotherSlot(item.time_slots)"
                    text
                    type="primary"
                    @click="addSlot(item.time_slots)"
                  >
                    ＋
                  </el-button>
                </div>
              </div>
              <p v-else class="weekly-closed">固定休假</p>
            </div>
          </div>
        </section>
      </el-col>

      <el-col :xs="24" :lg="16">
        <section class="panel calendar-panel">
          <div class="panel-header">
            <h2>營業月曆</h2>
            <div class="legend">
              <span class="legend-item legend-default-open">預設營業</span>
              <span class="legend-item legend-default-closed">預設休</span>
              <span class="legend-item legend-special-open">特別營業</span>
              <span class="legend-item legend-special-closed">特別休</span>
            </div>
          </div>
          <el-calendar v-model="calendarValue">
            <template #date-cell="{ data }">
              <button
                type="button"
                class="calendar-day"
                :class="`calendar-day--${resolveDayStatus(data.date).key}`"
                @click="openDayDialog(data.date)"
              >
                <span class="calendar-day-number">{{ data.day.split("-")[2] }}</span>
                <span class="calendar-day-label">{{ resolveDayStatus(data.date).label }}</span>
                <span
                  v-if="resolveDayStatus(data.date).hours"
                  class="calendar-day-hours"
                >
                  {{ resolveDayStatus(data.date).hours }}
                </span>
              </button>
            </template>
          </el-calendar>
        </section>
      </el-col>
    </el-row>

    <el-dialog
      v-model="dayDialogVisible"
      :title="`編輯 ${dayForm.target_date}`"
      width="520px"
    >
      <el-form label-position="top">
        <el-form-item label="日期設定">
          <el-radio-group v-model="dayForm.mode">
            <el-radio value="default">套用每週範本</el-radio>
            <el-radio value="specialOpen">特別營業</el-radio>
            <el-radio value="specialClosed">特別休</el-radio>
          </el-radio-group>
        </el-form-item>

        <template v-if="dayForm.mode === 'specialOpen'">
          <div class="weekly-slot-list">
            <div
              v-for="(slot, slotIndex) in dayForm.time_slots"
              :key="`day-slot-${slotIndex}`"
              class="weekly-row-hours"
            >
              <el-select v-model="slot.open_hour" style="width: 100%">
                <el-option
                  v-for="opt in hourOptions.filter((h) => h.value < 24)"
                  :key="`day-open-${slotIndex}-${opt.value}`"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <span class="weekly-separator">至</span>
              <el-select v-model="slot.close_hour" style="width: 100%">
                <el-option
                  v-for="opt in hourOptions.filter((h) => h.value > 0)"
                  :key="`day-close-${slotIndex}-${opt.value}`"
                  :label="opt.label"
                  :value="opt.value"
                />
              </el-select>
              <el-button
                v-if="slotIndex > 0"
                text
                type="danger"
                @click="removeSlot(dayForm.time_slots, slotIndex)"
              >
                移除
              </el-button>
              <el-button
                v-if="slotIndex === dayForm.time_slots.length - 1 && canAddAnotherSlot(dayForm.time_slots)"
                text
                type="primary"
                @click="addSlot(dayForm.time_slots)"
              >
                ＋
              </el-button>
            </div>
          </div>
        </template>

        <el-form-item v-if="dayForm.mode !== 'default'" label="備註（選填）">
          <el-input
            v-model="dayForm.note"
            maxlength="100"
            placeholder="例如：國定假日、臨時加班"
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button
          v-if="dayForm.override_id"
          type="danger"
          plain
          :loading="daySaving"
          @click="clearDayOverride"
        >
          清除覆寫
        </el-button>
        <el-button @click="dayDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="daySaving" @click="saveDayOverride">
          儲存
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.settings-page {
  padding-bottom: 24px;
}

.panel {
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 0;
  font-size: 1.1rem;
}

.weekly-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.weekly-row {
  padding: 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 10px;
}

.weekly-row-title {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
  font-weight: 600;
}

.weekly-slot-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.weekly-row-hours {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  gap: 8px;
  align-items: center;
}

.weekly-separator {
  color: var(--el-text-color-secondary);
}

.weekly-closed {
  margin: 0;
  color: var(--el-text-color-secondary);
  font-size: 0.9rem;
}

.legend {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.legend-item {
  font-size: 0.8rem;
  padding: 4px 8px;
  border-radius: 999px;
}

.legend-default-open {
  background: #e8f5e9;
  color: #2e7d32;
}

.legend-default-closed {
  background: #f5f5f5;
  color: #757575;
}

.legend-special-open {
  background: #e3f2fd;
  color: #1565c0;
}

.legend-special-closed {
  background: #ffebee;
  color: #c62828;
}

.calendar-panel :deep(.el-calendar-day) {
  padding: 4px;
  height: 100%;
}

.calendar-day {
  width: 100%;
  min-height: 88px;
  border: 1px solid transparent;
  border-radius: 10px;
  background: transparent;
  text-align: left;
  padding: 8px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.calendar-day:hover {
  border-color: var(--el-color-primary-light-5);
}

.calendar-day-number {
  font-weight: 700;
}

.calendar-day-label,
.calendar-day-hours {
  font-size: 0.75rem;
  line-height: 1.2;
}

.calendar-day--defaultOpen {
  background: #f1f8f4;
}

.calendar-day--defaultClosed {
  background: #fafafa;
  color: #888;
}

.calendar-day--specialOpen {
  background: #eef6ff;
}

.calendar-day--specialClosed {
  background: #fff1f1;
}
</style>
