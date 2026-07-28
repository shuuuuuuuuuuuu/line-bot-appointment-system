<script setup>
import { computed, onMounted, reactive, ref, watch } from "vue";
import { ElMessage } from "element-plus";

import { fetchAdminStats, exportAdminAppointments } from "../api";
import TrendChart from "../components/TrendChart.vue";
import ServiceBarChart from "../components/ServiceBarChart.vue";
import ColumnFilterHeader from "../components/ColumnFilterHeader.vue";

const PERIOD_OPTIONS = [
  { label: "本週", value: "week" },
  { label: "本月", value: "month" },
  { label: "全部", value: "all" },
];

const loading = ref(false);
const exporting = ref(false);
const period = ref("month");
const stats = ref(null);
/** 預設收合圖表 */
const chartCollapse = ref([]);

const periodLabel = computed(() => {
  if (!stats.value) return "";
  if (stats.value.period === "all") return "全部期間（走勢近 12 個月）";
  if (stats.value.period_start && stats.value.period_end) {
    return `${stats.value.period_start} ～ ${stats.value.period_end}`;
  }
  return "";
});

const summaryCards = computed(() => {
  const s = stats.value;
  if (!s) return [];
  return [
    {
      key: "revenue",
      label: "已確認營收",
      value: formatMoney(s.revenue),
      hint: "依服務日期區間統計",
    },
    {
      key: "confirmed",
      label: "已確認預約",
      value: String(s.confirmed_count),
      hint: "已付款通過",
    },
    {
      key: "upcoming",
      label: "即將到來",
      value: String(s.upcoming_count),
      hint: "未來已確認場次",
    },
    {
      key: "pending",
      label: "待匯款",
      value: String(s.pending_payment_count),
      hint: "目前進行中",
    },
    {
      key: "review",
      label: "待審核",
      value: String(s.awaiting_review_count),
      hint: "已收到匯款資訊",
    },
    {
      key: "cancelled",
      label: "已取消",
      value: String(s.cancelled_count),
      hint: "區間內取消／逾期",
    },
  ];
});

const appointmentRows = computed(() => stats.value?.recent_appointments || []);

const tableFilters = reactive({
  client_name: [],
  category_name: [],
  service_names: [],
  payment_proof_received: [],
  status_label: [],
});

function uniqueFilterOptions(values) {
  return [...new Set(values.filter(Boolean))]
    .sort((a, b) => String(a).localeCompare(String(b), "zh-Hant"))
    .map((value) => ({ label: value, value }));
}

const clientFilters = computed(() =>
  uniqueFilterOptions(appointmentRows.value.map((row) => row.client_name)),
);

const categoryFilters = computed(() =>
  uniqueFilterOptions(
    appointmentRows.value.map((row) => row.category_name || "—"),
  ),
);

const serviceFilters = computed(() =>
  uniqueFilterOptions(
    appointmentRows.value.flatMap((row) =>
      row.service_names?.length ? row.service_names : ["—"],
    ),
  ),
);

const paymentFilters = [
  { label: "已收到", value: "received" },
  { label: "尚未", value: "pending" },
];

const statusFilters = computed(() =>
  uniqueFilterOptions(appointmentRows.value.map((row) => row.status_label)),
);

const filteredAppointmentRows = computed(() => {
  let rows = appointmentRows.value;

  if (tableFilters.client_name.length) {
    rows = rows.filter((row) =>
      tableFilters.client_name.includes(row.client_name),
    );
  }

  if (tableFilters.category_name.length) {
    rows = rows.filter((row) =>
      tableFilters.category_name.includes(row.category_name || "—"),
    );
  }

  if (tableFilters.service_names.length) {
    rows = rows.filter((row) => {
      const names = row.service_names?.length ? row.service_names : ["—"];
      return names.some((name) => tableFilters.service_names.includes(name));
    });
  }

  if (tableFilters.payment_proof_received.length) {
    rows = rows.filter((row) => {
      const key = row.payment_proof_received ? "received" : "pending";
      return tableFilters.payment_proof_received.includes(key);
    });
  }

  if (tableFilters.status_label.length) {
    rows = rows.filter((row) =>
      tableFilters.status_label.includes(row.status_label),
    );
  }

  return rows;
});

const hasActiveFilters = computed(() =>
  Object.values(tableFilters).some(
    (values) => Array.isArray(values) && values.length > 0,
  ),
);

function formatMoney(n) {
  return `$${Number(n || 0).toLocaleString("zh-TW")}`;
}

function formatDateTime(value) {
  if (!value) return "—";
  const d = new Date(value);
  if (Number.isNaN(d.getTime()))
    return String(value).replace("T", " ").slice(0, 16);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  const hh = String(d.getHours()).padStart(2, "0");
  const mm = String(d.getMinutes()).padStart(2, "0");
  return `${y}-${m}-${day} ${hh}:${mm}`;
}

function statusTagType(status) {
  if (status === "confirmed") return "success";
  if (status === "awaiting_review") return "warning";
  if (status === "pending_payment") return "info";
  return "danger";
}

async function loadStats() {
  loading.value = true;
  try {
    stats.value = await fetchAdminStats(period.value);
  } catch (error) {
    ElMessage.error("無法載入數據總覽");
  } finally {
    loading.value = false;
  }
}

async function exportExcel() {
  if (!filteredAppointmentRows.value.length) {
    ElMessage.warning("目前沒有可匯出的預約明細");
    return;
  }

  exporting.value = true;
  try {
    const ids = filteredAppointmentRows.value.map((row) => row.id);
    const response = await exportAdminAppointments(period.value, ids);
    const blob = new Blob([response.data], {
      type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    const stamp = new Date().toISOString().slice(0, 10);
    const filterTag = hasActiveFilters.value ? "_已篩選" : "";
    link.href = url;
    link.download = `預約明細_${period.value}${filterTag}_${stamp}.xlsx`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    ElMessage.success(
      hasActiveFilters.value
        ? `已匯出篩選後 ${ids.length} 筆`
        : `已匯出 ${ids.length} 筆`,
    );
  } catch (error) {
    ElMessage.error("匯出失敗");
  } finally {
    exporting.value = false;
  }
}

function resetAppointmentFilters() {
  tableFilters.client_name = [];
  tableFilters.category_name = [];
  tableFilters.service_names = [];
  tableFilters.payment_proof_received = [];
  tableFilters.status_label = [];
}

watch(period, () => {
  resetAppointmentFilters();
  loadStats();
});
onMounted(loadStats);
</script>

<template>
  <div v-loading="loading">
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Insights</p>
        <h1>數據總覽</h1>
        <p>查看預約量、營收與待處理狀態，方便掌握近期營運狀況。</p>
      </div>
      <div class="stats-toolbar">
        <el-radio-group v-model="period" size="default">
          <el-radio-button
            v-for="opt in PERIOD_OPTIONS"
            :key="opt.value"
            :value="opt.value"
            :label="opt.value"
          >
            {{ opt.label }}
          </el-radio-button>
        </el-radio-group>
        <span v-if="periodLabel" class="period-range">{{ periodLabel }}</span>
      </div>
    </div>

    <el-row :gutter="16" class="summary-row">
      <el-col
        v-for="card in summaryCards"
        :key="card.key"
        :xs="12"
        :sm="8"
        :md="4"
      >
        <div class="stat-card">
          <p class="stat-label">{{ card.label }}</p>
          <p class="stat-value">{{ card.value }}</p>
          <p class="stat-hint">{{ card.hint }}</p>
        </div>
      </el-col>
    </el-row>

    <el-collapse v-model="chartCollapse" class="trend-collapse section-row">
      <el-collapse-item name="trend">
        <template #title>
          <div class="trend-collapse-title">
            <span>營運走勢圖</span>
          </div>
        </template>
        <div class="trend-grid">
          <TrendChart :points="stats?.trend || []" />
        </div>
      </el-collapse-item>
      <el-collapse-item name="akashic">
        <template #title>
          <div class="trend-collapse-title">
            <span>阿卡西項目分析</span>
          </div>
        </template>
        <div class="trend-grid">
          <ServiceBarChart :items="stats?.by_akashic_service || []" />
        </div>
      </el-collapse-item>
    </el-collapse>

    <el-row :gutter="20" class="section-row">
      <el-col :xs="24" :md="10">
        <h2 class="section-title">分類營收</h2>
        <el-table
          :data="stats?.by_category || []"
          stripe
          empty-text="此期間尚無已確認預約"
        >
          <el-table-column prop="category_name" label="分類" min-width="120" />
          <el-table-column prop="appointment_count" label="場次" width="80" />
          <el-table-column label="營收" width="110">
            <template #default="{ row }">
              {{ formatMoney(row.revenue) }}
            </template>
          </el-table-column>
        </el-table>
      </el-col>

      <el-col :xs="24" :md="14">
        <h2 class="section-title">即將到來的預約</h2>
        <el-table
          :data="stats?.upcoming_appointments || []"
          stripe
          empty-text="目前沒有即將到來的已確認預約"
        >
          <el-table-column prop="client_name" label="客戶" width="100" />
          <el-table-column label="服務時間" min-width="150">
            <template #default="{ row }">
              {{ formatDateTime(row.service_date_time) }}
            </template>
          </el-table-column>
          <el-table-column prop="category_name" label="分類" width="110">
            <template #default="{ row }">
              {{ row.category_name || "—" }}
            </template>
          </el-table-column>
          <el-table-column label="金額" width="90">
            <template #default="{ row }">
              {{ formatMoney(row.total_price) }}
            </template>
          </el-table-column>
        </el-table>
      </el-col>
    </el-row>

    <div class="section-row">
      <div class="section-heading">
        <div>
          <h2 class="section-title">預約明細</h2>
          <p v-if="hasActiveFilters" class="filter-hint">
            目前篩選後 {{ filteredAppointmentRows.length }} /
            {{ appointmentRows.length }} 筆，匯出將依此結果
          </p>
        </div>
        <el-button
          type="primary"
          plain
          :loading="exporting"
          @click="exportExcel"
        >
          匯出 Excel
        </el-button>
      </div>
      <el-table
        :data="filteredAppointmentRows"
        stripe
        empty-text="尚無預約紀錄"
        row-key="id"
      >
        <el-table-column prop="id" label="#" width="70" />
        <el-table-column prop="client_name" label="客戶" width="110">
          <template #header>
            <ColumnFilterHeader
              v-model="tableFilters.client_name"
              label="客戶"
              :options="clientFilters"
            />
          </template>
        </el-table-column>
        <el-table-column label="服務時間" min-width="150">
          <template #default="{ row }">
            {{ formatDateTime(row.service_date_time) }}
          </template>
        </el-table-column>
        <el-table-column label="分類" width="120">
          <template #header>
            <ColumnFilterHeader
              v-model="tableFilters.category_name"
              label="分類"
              :options="categoryFilters"
            />
          </template>
          <template #default="{ row }">
            {{ row.category_name || "—" }}
          </template>
        </el-table-column>
        <el-table-column label="項目" min-width="160">
          <template #header>
            <ColumnFilterHeader
              v-model="tableFilters.service_names"
              label="項目"
              :options="serviceFilters"
            />
          </template>
          <template #default="{ row }">
            {{ (row.service_names || []).join("、") || "—" }}
          </template>
        </el-table-column>
        <el-table-column label="時長" width="90">
          <template #default="{ row }">
            {{ row.total_duration != null ? row.total_duration + " 分" : "—" }}
          </template>
        </el-table-column>
        <el-table-column label="備註" min-width="180">
          <template #default="{ row }">
            <span class="note-preview">{{ row.user_message || "—" }}</span>
          </template>
        </el-table-column>
        <el-table-column label="匯款" width="100">
          <template #header>
            <ColumnFilterHeader
              v-model="tableFilters.payment_proof_received"
              label="匯款"
              :options="paymentFilters"
            />
          </template>
          <template #default="{ row }">
            {{ row.payment_proof_received ? "已收到" : "尚未" }}
          </template>
        </el-table-column>
        <el-table-column label="金額" width="90">
          <template #default="{ row }">
            {{ formatMoney(row.total_price) }}
          </template>
        </el-table-column>
        <el-table-column label="狀態" width="110">
          <template #header>
            <ColumnFilterHeader
              v-model="tableFilters.status_label"
              label="狀態"
              :options="statusFilters"
            />
          </template>
          <template #default="{ row }">
            <el-tag :type="statusTagType(row.status)" size="small">
              {{ row.status_label }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="建立時間" min-width="150">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<style scoped>
.stats-toolbar {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 8px;
}

.period-range {
  color: #64748b;
  font-size: 13px;
}

.summary-row {
  margin-bottom: 28px;
}

.stat-card {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 16px 18px;
  margin-bottom: 16px;
  min-height: 110px;
}

.stat-label {
  margin: 0;
  color: #64748b;
  font-size: 13px;
}

.stat-value {
  margin: 8px 0 4px;
  font-size: 1.55rem;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.stat-hint {
  margin: 0;
  color: #94a3b8;
  font-size: 12px;
}

.section-row {
  margin-bottom: 28px;
}

.section-title {
  margin: 0 0 12px;
  font-size: 1.1rem;
}

.section-heading {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.section-heading .section-title {
  margin: 0;
}

.filter-hint {
  margin: 4px 0 0;
  color: #64748b;
  font-size: 13px;
}

.trend-collapse {
  border: none;
  --el-collapse-header-height: 52px;
}

.trend-collapse :deep(.el-collapse-item__header) {
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  padding: 0 16px;
  font-weight: 600;
  margin-bottom: 10px;
}

.trend-collapse :deep(.el-collapse-item__wrap) {
  border: none;
  background: transparent;
}

.trend-collapse :deep(.el-collapse-item__content) {
  padding: 14px 0 0;
}

.trend-collapse-title {
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.trend-collapse-hint {
  color: #94a3b8;
  font-size: 12px;
  font-weight: 400;
}

.trend-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 14px;
}

.note-preview {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: #475569;
  white-space: pre-wrap;
}
</style>
