<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import Sortable from "sortablejs";

import {
  createService,
  deleteService,
  fetchAdminCategories,
  fetchAdminServices,
  reorderServices,
  updateService,
} from "../api";

const loading = ref(false);
const saving = ref(false);
const reordering = ref(false);
const services = ref([]);
const categories = ref([]);
const filterCategoryId = ref(null);
const dialogVisible = ref(false);
const editingId = ref(null);
const tableRef = ref(null);

let sortable = null;

const form = reactive({
  service_name: "",
  category_id: null,
  price: 0,
  duration_minutes: 60,
  is_active: true,
  sort_order: 0,
});

const dialogTitle = computed(() =>
  editingId.value ? "編輯服務項目" : "新增服務項目",
);

const categoryOptions = computed(() =>
  categories.value.map((item) => ({
    label: item.category_name,
    value: item.id,
  })),
);

function resetForm() {
  form.service_name = "";
  form.category_id = filterCategoryId.value || categories.value[0]?.id || null;
  form.price = 0;
  form.duration_minutes = 60;
  form.is_active = true;
  // 表單排序為 1-based：現有列數 + 1
  form.sort_order = services.value.length + 1;
  editingId.value = null;
}

async function loadCategories() {
  categories.value = await fetchAdminCategories();
}

async function loadServices() {
  loading.value = true;
  try {
    services.value = await fetchAdminServices(filterCategoryId.value);
  } catch (error) {
    ElMessage.error("無法載入服務項目");
  } finally {
    loading.value = false;
  }
}

const canReorder = computed(() => filterCategoryId.value != null);

function destroySortable() {
  if (sortable) {
    sortable.destroy();
    sortable = null;
  }
}

function initSortable() {
  destroySortable();
  if (!canReorder.value || loading.value || !services.value.length) {
    return;
  }

  const tableEl = tableRef.value?.$el;
  const tbody = tableEl?.querySelector(".el-table__body-wrapper tbody");
  if (!tbody) {
    return;
  }

  sortable = Sortable.create(tbody, {
    handle: ".drag-handle",
    animation: 180,
    ghostClass: "drag-ghost",
    chosenClass: "drag-chosen",
    dragClass: "drag-dragging",
    onEnd: async (event) => {
      const { oldIndex, newIndex } = event;
      if (
        oldIndex == null ||
        newIndex == null ||
        oldIndex === newIndex ||
        reordering.value
      ) {
        return;
      }

      const next = [...services.value];
      const [moved] = next.splice(oldIndex, 1);
      next.splice(newIndex, 0, moved);
      const ordered = next.map((item, index) => ({
        ...item,
        sort_order: index,
      }));
      services.value = ordered;

      reordering.value = true;
      try {
        const updated = await reorderServices(
          ordered.map((item) => ({
            id: item.id,
            sort_order: item.sort_order,
          })),
        );
        // 只保留目前篩選類別的結果，避免全表回傳打亂畫面
        services.value = updated.filter(
          (item) => item.category_id === filterCategoryId.value,
        );
        ElMessage.success("排序已更新");
      } catch (error) {
        const detail = error.response?.data?.detail;
        ElMessage.error(detail || "排序更新失敗");
        await loadServices();
      } finally {
        reordering.value = false;
      }
    },
  });
}

function openCreate() {
  resetForm();
  dialogVisible.value = true;
}

function openEdit(row) {
  editingId.value = row.id;
  form.service_name = row.service_name;
  form.category_id = row.category_id;
  form.price = row.price;
  form.duration_minutes = row.duration_minutes;
  form.is_active = row.is_active;
  form.sort_order = row.sort_order + 1;
  dialogVisible.value = true;
}

async function submitForm() {
  if (!form.service_name.trim()) {
    ElMessage.warning("請輸入服務名稱");
    return;
  }
  if (!form.category_id) {
    ElMessage.warning("請選擇分類");
    return;
  }

  saving.value = true;
  const payload = {
    service_name: form.service_name.trim(),
    category_id: form.category_id,
    price: Number(form.price) || 0,
    duration_minutes: Number(form.duration_minutes) || 60,
    is_active: form.is_active,
    // 表單 1-based → API 0-based
    sort_order: Math.max(0, (Number(form.sort_order) || 1) - 1),
  };

  try {
    if (editingId.value) {
      await updateService(editingId.value, payload);
      ElMessage.success("已更新服務");
    } else {
      await createService(payload);
      ElMessage.success("已新增服務");
    }
    dialogVisible.value = false;
    await loadServices();
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
      `確定刪除「${row.service_name}」？若已有預約紀錄會改為停用。`,
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
    const result = await deleteService(row.id);
    ElMessage.success(result.detail || "已處理");
    await loadServices();
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "刪除失敗");
  }
}

watch(
  () => [services.value, loading.value, filterCategoryId.value],
  async () => {
    if (loading.value) {
      return;
    }
    await nextTick();
    initSortable();
  },
);

onMounted(async () => {
  try {
    await loadCategories();
    await loadServices();
  } catch (error) {
    ElMessage.error("初始化服務管理頁失敗");
  }
});

onBeforeUnmount(() => {
  destroySortable();
});
</script>

<template>
  <div>
    <div class="page-heading page-heading-row">
      <div>
        <p class="eyebrow">Services</p>
        <h1>服務項目</h1>
        <p>管理名稱、分類、價格、時長、排序與啟用狀態。</p>
      </div>
      <el-button type="primary" @click="openCreate">新增服務</el-button>
    </div>

    <div class="toolbar">
      <el-select
        v-model="filterCategoryId"
        clearable
        placeholder="全部類別"
        style="width: 220px"
        @change="loadServices"
      >
        <el-option
          v-for="cat in categories"
          :key="cat.id"
          :label="cat.category_name"
          :value="cat.id"
        />
      </el-select>
      <span class="toolbar-hint">
        {{
          canReorder
            ? "拖曳左側 ⋮⋮ 手柄可調整顯示順序"
            : "尚未篩選類別時顯示排序編號；選類別後可拖曳排序"
        }}
      </span>
    </div>

    <el-table
      ref="tableRef"
      v-loading="loading || reordering"
      :data="services"
      row-key="id"
      stripe
    >
      <el-table-column
        :label="canReorder ? '' : '排序'"
        width="56"
        align="center"
        class-name="drag-col"
        :resizable="false"
        :show-overflow-tooltip="false"
      >
        <template #default="{ $index }">
          <button
            v-if="canReorder"
            type="button"
            class="drag-handle"
            title="拖曳排序"
            aria-label="拖曳排序"
          >
            ⋮⋮
          </button>
          <span v-else class="sort-index">{{ $index + 1 }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="category_name" label="類別" min-width="120" />
      <el-table-column prop="service_name" label="服務名稱" min-width="180" />
      <el-table-column prop="price" label="價格" width="100" />
      <el-table-column prop="duration_minutes" label="時長(分)" width="100" />
      <el-table-column label="狀態" width="100">
        <template #default="{ row }">
          <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
            {{ row.is_active ? "啟用" : "停用" }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="160" fixed="right">
        <template #default="{ row }">
          <el-button text type="primary" @click="openEdit(row)">編輯</el-button>
          <el-button text type="danger" @click="onDelete(row)">刪除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="520px">
      <el-form label-position="top">
        <el-form-item label="服務名稱">
          <el-input v-model="form.service_name" maxlength="255" />
        </el-form-item>
        <el-form-item label="分類">
          <el-select v-model="form.category_id" style="width: 100%">
            <el-option
              v-for="opt in categoryOptions"
              :key="opt.value"
              :label="opt.label"
              :value="opt.value"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="價格">
          <el-input-number v-model="form.price" :min="0" :step="100" />
        </el-form-item>
        <el-form-item label="時長（分鐘）">
          <el-input-number
            v-model="form.duration_minutes"
            :min="1"
            :max="480"
            :step="5"
          />
        </el-form-item>
        <el-form-item label="排序">
          <el-input-number v-model="form.sort_order" :min="1" :step="1" />
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
