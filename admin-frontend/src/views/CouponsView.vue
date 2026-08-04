<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";

import {
  addCouponEligibilities,
  createCoupon,
  deleteCoupon,
  fetchAdminCategories,
  fetchAdminClients,
  fetchAdminCoupons,
  fetchCouponEligibilities,
  removeCouponEligibility,
  updateCoupon,
} from "../api";

const loading = ref(false);
const saving = ref(false);
const coupons = ref([]);
const categories = ref([]);
const dialogVisible = ref(false);
const editingId = ref(null);

const eligibilityVisible = ref(false);
const eligibilityLoading = ref(false);
const eligibilitySaving = ref(false);
const eligibilityCoupon = ref(null);
const eligibilities = ref([]);
const clientOptions = ref([]);
const selectedClientIds = ref([]);
const clientSearchLoading = ref(false);

const form = reactive({
  name: "",
  code: "",
  category_id: null,
  valid_range: [],
  is_active: true,
  max_uses: 100,
});

const dialogTitle = computed(() =>
  editingId.value ? "編輯折扣碼" : "新增折扣碼",
);

function resetForm() {
  form.name = "";
  form.code = "";
  form.category_id = categories.value[0]?.id || null;
  form.valid_range = [];
  form.is_active = true;
  form.max_uses = 100;
  editingId.value = null;
}

async function loadCategories() {
  categories.value = await fetchAdminCategories();
}

async function loadCoupons() {
  loading.value = true;
  try {
    coupons.value = await fetchAdminCoupons();
  } catch (error) {
    ElMessage.error("無法載入折扣碼");
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  form.name = row.name;
  form.code = row.code;
  form.category_id = row.category_id;
  form.valid_range = [row.valid_from, row.valid_to];
  form.is_active = row.is_active;
  form.max_uses = row.max_uses;
  dialogVisible.value = true;
}

async function submitForm() {
  if (!form.name.trim()) {
    ElMessage.warning("請輸入活動名稱");
    return;
  }
  if (!form.code.trim()) {
    ElMessage.warning("請輸入折扣碼");
    return;
  }
  if (!form.category_id) {
    ElMessage.warning("請選擇折扣項目");
    return;
  }
  if (!form.valid_range || form.valid_range.length !== 2) {
    ElMessage.warning("請選擇有效期限");
    return;
  }

  saving.value = true;
  const payload = {
    name: form.name.trim(),
    code: form.code.trim(),
    category_id: form.category_id,
    valid_from: form.valid_range[0],
    valid_to: form.valid_range[1],
    is_active: form.is_active,
    max_uses: Number(form.max_uses) || 1,
  };

  try {
    if (editingId.value) {
      await updateCoupon(editingId.value, payload);
      ElMessage.success("已更新折扣碼");
    } else {
      await createCoupon(payload);
      ElMessage.success("已新增折扣碼，請接著設定發放名單");
    }
    dialogVisible.value = false;
    await loadCoupons();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "儲存失敗");
  } finally {
    saving.value = false;
  }
}

async function onDelete(row) {
  try {
    await ElMessageBox.confirm(
      `確定刪除「${row.code}」？若已有使用紀錄會改為停用。`,
      "刪除確認",
      {
        type: "warning",
        confirmButtonText: "確定",
        cancelButtonText: "取消",
      },
    );
  } catch {
    return;
  }

  try {
    const result = await deleteCoupon(row.id);
    ElMessage.success(result.detail || "已處理");
    await loadCoupons();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "刪除失敗");
  }
}

function todayStr() {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

function isExpired(row) {
  return Boolean(row.valid_to && row.valid_to < todayStr());
}

function formatStatus(row) {
  if (!row.is_active) return "已停用";
  if (isExpired(row)) return "過期";
  if (row.redemption_count >= row.max_uses) return "已用完";
  return "可用";
}

function statusTagType(row) {
  const status = formatStatus(row);
  if (status === "可用") return "success";
  if (status === "過期") return "warning";
  return "info";
}

async function openEligibility(row) {
  eligibilityCoupon.value = row;
  selectedClientIds.value = [];
  eligibilityVisible.value = true;
  eligibilityLoading.value = true;
  try {
    eligibilities.value = await fetchCouponEligibilities(row.id);
    clientOptions.value = await fetchAdminClients();
  } catch (error) {
    ElMessage.error("無法載入發放名單");
  } finally {
    eligibilityLoading.value = false;
  }
}

async function searchClients(query) {
  clientSearchLoading.value = true;
  try {
    clientOptions.value = await fetchAdminClients(query || undefined);
  } catch (error) {
    // ignore search errors
  } finally {
    clientSearchLoading.value = false;
  }
}

function clientLabel(client) {
  return `${client.last_name || ""}${client.first_name || ""}`.trim() || "未命名客戶";
}

async function submitEligibilities() {
  const merged = [...new Set(selectedClientIds.value || [])];
  if (!merged.length) {
    ElMessage.warning("請從既有客戶選取");
    return;
  }

  eligibilitySaving.value = true;
  try {
    eligibilities.value = await addCouponEligibilities(
      eligibilityCoupon.value.id,
      merged,
    );
    selectedClientIds.value = [];
    ElMessage.success("已加入發放名單");
    await loadCoupons();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "加入失敗");
  } finally {
    eligibilitySaving.value = false;
  }
}

async function onRemoveEligibility(row) {
  try {
    await removeCouponEligibility(eligibilityCoupon.value.id, row.id);
    eligibilities.value = eligibilities.value.filter((item) => item.id !== row.id);
    ElMessage.success("已移除");
    await loadCoupons();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "移除失敗");
  }
}

onMounted(async () => {
  try {
    await loadCategories();
    await loadCoupons();
  } catch (error) {
    ElMessage.error("初始化折扣碼頁失敗");
  }
});
</script>

<template>
  <div>
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Coupons</p>
        <h1>折扣碼</h1>
        <p>
          同一活動共用一個 code。業主用 LINE 發完後，請把符合資格的客人加入「發放名單」；未在名單內的帳號套用會顯示「優惠碼無效」。
        </p>
      </div>
      <el-button type="primary" @click="openCreate">新增折扣碼</el-button>
    </div>

    <el-table v-loading="loading" :data="coupons" stripe>
      <el-table-column prop="name" label="活動名稱" min-width="160" />
      <el-table-column prop="code" label="折扣碼" min-width="200" />
      <el-table-column label="折扣項目" width="120">
        <template #default="{ row }">
          {{ row.category_name || "—" }}
        </template>
      </el-table-column>
      <el-table-column label="應付比例" width="100" align="center">
        <template #default="{ row }">{{ row.discount_percent }}%</template>
      </el-table-column>
      <el-table-column label="有效期限" min-width="200">
        <template #default="{ row }">
          {{ row.valid_from }} ～ {{ row.valid_to }}
        </template>
      </el-table-column>
      <el-table-column label="發放人數" width="90" align="center">
        <template #default="{ row }">{{ row.eligibility_count }}</template>
      </el-table-column>
      <el-table-column label="已用 / 名額" width="110" align="center">
        <template #default="{ row }">
          {{ row.redemption_count }} / {{ row.max_uses }}
        </template>
      </el-table-column>
      <el-table-column label="狀態" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="statusTagType(row)" size="small">
            {{ formatStatus(row) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="220" fixed="right">
        <template #default="{ row }">
          <el-button link type="primary" @click="openEligibility(row)">
            發放名單
          </el-button>
          <el-button link type="primary" @click="openEdit(row)">編輯</el-button>
          <el-button link type="danger" @click="onDelete(row)">刪除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog
      v-model="dialogVisible"
      :title="dialogTitle"
      width="520px"
      destroy-on-close
    >
      <el-form label-position="top">
        <el-form-item label="活動名稱" required>
          <el-input
            v-model="form.name"
            placeholder="例：頌缽療癒體驗活動"
            maxlength="100"
          />
        </el-form-item>
        <el-form-item label="折扣碼" required>
          <el-input
            v-model="form.code"
            placeholder="例：20260802_soundhealing_50"
            maxlength="100"
          />
          <div class="field-hint">
            系統會從 code 自動解析折扣趴數（50 = 應付原價 50%）
          </div>
        </el-form-item>
        <el-form-item label="折扣項目" required>
          <el-select
            v-model="form.category_id"
            placeholder="請選擇適用的服務類別"
            style="width: 100%"
          >
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.category_name"
              :value="cat.id"
            />
          </el-select>
          <div class="field-hint">
            僅該服務類別可套用此折扣碼，例如選「頌缽」時選「阿卡西」不可用
          </div>
        </el-form-item>
        <el-form-item label="有效期限" required>
          <el-date-picker
            v-model="form.valid_range"
            type="daterange"
            range-separator="至"
            start-placeholder="開始日"
            end-placeholder="結束日"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            style="width: 100%"
          />
        </el-form-item>
        <el-form-item label="活動總名額">
          <el-input-number v-model="form.max_uses" :min="1" :max="10000" />
          <div class="field-hint">
            同一活動共用此 code；此為總使用上限。每位 LINE 帳號仍只能套用一次。
          </div>
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

    <el-dialog
      v-model="eligibilityVisible"
      :title="eligibilityCoupon ? `發放名單｜${eligibilityCoupon.code}` : '發放名單'"
      width="640px"
      destroy-on-close
    >
      <div v-loading="eligibilityLoading">
        <p class="eligibility-intro">
          手動用 LINE 把折扣碼傳給符合資格的客人後，請從既有客戶加入發放名單。未在名單內的帳號即使知道 code 也無法套用。
        </p>

        <el-form label-position="top">
          <el-form-item label="從既有客戶選取">
            <el-select
              v-model="selectedClientIds"
              multiple
              filterable
              remote
              clearable
              reserve-keyword
              placeholder="搜尋客戶名稱"
              :remote-method="searchClients"
              :loading="clientSearchLoading"
              style="width: 100%"
            >
              <el-option
                v-for="client in clientOptions"
                :key="client.line_user_id"
                :label="clientLabel(client)"
                :value="client.line_user_id"
              />
            </el-select>
          </el-form-item>
        </el-form>

        <div class="eligibility-actions">
          <el-button
            type="primary"
            :loading="eligibilitySaving"
            @click="submitEligibilities"
          >
            加入名單
          </el-button>
        </div>

        <el-table :data="eligibilities" stripe max-height="320">
          <el-table-column prop="client_name" label="姓名" min-width="160">
            <template #default="{ row }">
              {{ row.client_name || "—" }}
            </template>
          </el-table-column>
          <el-table-column label="操作" width="80" fixed="right">
            <template #default="{ row }">
              <el-button link type="danger" @click="onRemoveEligibility(row)">
                移除
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<style scoped>
.field-hint {
  margin-top: 6px;
  color: var(--el-text-color-secondary);
  font-size: 12px;
  line-height: 1.4;
}

.eligibility-intro {
  margin: 0 0 16px;
  color: var(--el-text-color-regular);
  font-size: 13px;
  line-height: 1.5;
}

.eligibility-actions {
  margin-bottom: 16px;
}
</style>
