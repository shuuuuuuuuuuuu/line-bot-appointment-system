<template>
  <div class="booking-wrapper">
    <el-card class="booking-card">
      <template #header>
        <div class="card-header">
          <h2>預約服務</h2>
        </div>
      </template>

      <el-form :model="form" label-position="top">
        <!-- 法定姓名 -->
        <el-form-item label="法定姓名">
          <el-row :gutter="10">
            <el-col :span="8">
              <el-input
                v-model="form.lastName"
                placeholder="姓氏"
                @keyup.enter="$event.target.blur()"
              />
            </el-col>
            <el-col :span="14">
              <el-input
                v-model="form.firstName"
                placeholder="名稱"
                @keyup.enter="$event.target.blur()"
              />
            </el-col>
          </el-row>
        </el-form-item>

        <!-- 服務類別（下拉選單） -->
        <el-form-item label="服務類別">
          <el-select
            v-model="selectedCategoryId"
            placeholder="請選擇類別"
            @change="handleCategoryChange"
            style="width: 100%"
          >
            <el-option
              v-for="cat in categories"
              :key="cat.id"
              :label="cat.category_name"
              :value="cat.id"
            />
          </el-select>
        </el-form-item>

        <!-- 服務時長描述 (淺灰色字體) -->
        <div class="description-text" v-if="servicesList.length > 0">
          服務時長約 {{ serviceDuration }} 分鐘
        </div>

        <!-- 服務項目（根據類別動態顯示）（多選） -->
        <el-form-item label="服務項目" v-if="servicesList.length > 0">
          <el-checkbox-group v-model="form.services" class="service-grid">
            <el-checkbox
              v-for="service in servicesList"
              :key="service.id"
              :label="service.service_name"
              :value="service.service_name"
            >
              {{ service.service_name }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>

        <!-- 問題簡述（阿卡西必填） -->
        <el-form-item
          label="問題簡述"
          required
          v-if="needsUserMessage"
        >
          <el-input
            v-model="form.user_message"
            type="textarea"
            :rows="3"
            placeholder="請簡述您想詢問的問題（必填）"
            maxlength="500"
            show-word-limit
          />
        </el-form-item>

        <!-- 日期選擇 -->
        <el-form-item label="預約日期">
          <el-date-picker
            v-model="form.date"
            type="date"
            :editable="false"
            placeholder="請選擇日期"
            format="YYYY-MM-DD"
            value-format="YYYY-MM-DD"
            :disabled-date="disabledDateLogic"
            @change="handleDateChange"
            style="width: 100%"
          />
        </el-form-item>

        <!-- 時間選擇 -->
        <el-form-item v-if="availableSlots.length > 0" label="預約時段">
          <div class="slots-grid">
            <el-check-tag
              v-for="slot in availableSlots"
              :key="slot"
              :checked="form.time === slot"
              @change="handleSlotClick(slot)"
              class="slot-tag"
            >
              {{ slot }}
            </el-check-tag>
          </div>
        </el-form-item>
        <p v-else-if="form.date && !loading" class="no-slot-text">
          此日期目前無可用時段或為公休日。
        </p>

        <!-- 優惠碼（預約日期區塊下、提交上） -->
        <el-form-item label="優惠碼">
          <div class="coupon-row">
            <el-input
              v-model="couponInput"
              placeholder="例：20260802_soundhealing_50"
              :disabled="!!appliedCoupon"
              @input="onCouponInputChange"
              @keyup.enter="applyCoupon"
            />
            <el-button
              v-if="!appliedCoupon"
              type="primary"
              plain
              :loading="couponValidating"
              :disabled="!couponInput.trim()"
              @click="applyCoupon"
            >
              套用
            </el-button>
            <el-button v-else @click="clearCoupon">取消</el-button>
          </div>
          <div v-if="appliedCoupon" class="coupon-success">
            {{ appliedCoupon.message }}
          </div>
          <div v-else-if="couponError" class="coupon-error">
            {{ couponError }}
          </div>
        </el-form-item>

        <!-- 置中提交按鈕 -->
        <div class="submit-area">
          <el-button
            type="primary"
            size="large"
            @click="submitForm"
            :loading="submitting"
            :disabled="!canSubmit"
          >
            提交預約
          </el-button>
        </div>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, watch } from "vue";
import liff from "@line/liff";
import axios from "axios";
import { ElMessage, ElMessageBox } from "element-plus";

const API_BASE = import.meta.env.VITE_API_URL;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "ngrok-skip-browser-warning": "any-value",
  },
});

const form = reactive({
  lastName: "",
  firstName: "",
  services: [],
  user_message: "",
  date: "",
  time: "",
});

const lineUserId = ref("");
const categories = ref([]);
const servicesList = ref([]);
const selectedCategoryId = ref(null);
const availableSlots = ref([]);
const loading = ref(false);
const submitting = ref(false);
const couponInput = ref("");
const couponValidating = ref(false);
const couponError = ref("");
const appliedCoupon = ref(null);
const businessSettings = ref({
  off_weekdays: [4, 5, 6],
  max_advance_days: 30,
  holidays: [],
});

function pyWeekdayToJs(pyDay) {
  return (pyDay + 1) % 7;
}

function toDateStr(date) {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  const d = String(date.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
}

// --- 取得所有類別 ---
const fetchCategories = async () => {
  try {
    const response = await api.get("/categories");
    categories.value = response.data;
  } catch (error) {
    console.error("獲取類別失敗:", error);
  }
};

const fetchBusinessSettings = async () => {
  try {
    const response = await api.get("/business-settings");
    businessSettings.value = {
      off_weekdays: response.data.off_weekdays ?? [4, 5, 6],
      max_advance_days: response.data.max_advance_days ?? 30,
      holidays: response.data.holidays ?? [],
    };
  } catch (error) {
    console.error("獲取營業設定失敗:", error);
  }
};

// --- 當類別切換時，取得對應服務 ---
const handleCategoryChange = async (catId) => {
  form.services = []; // 清空已選服務
  form.user_message = "";
  servicesList.value = [];
  clearCoupon();

  const currentCategory = categories.value.find((c) => c.id === catId);
  if (currentCategory?.category_name?.includes("頌缽")) {
    ElMessageBox.alert(
      `<strong>不適合做頌缽療癒的對象：</strong><br>
🚨 懷孕<br>
🚨 裝有心律調節器<br>
🚨 對聲音或震動特別敏感<br>
🚨 目前有嚴重身心疾病`,
      "注意事項",
      {
        confirmButtonText: "我知道了",
        dangerouslyUseHTMLString: true,
        customClass: "singing-bowl-warning",
      }
    );
  }

  try {
    const response = await api.get(`/services/filter?category_id=${catId}`);
    servicesList.value = response.data;
  } catch (error) {
    console.error("過濾服務項目失敗:", error);
    ElMessage.error("無法取得該類別的服務項目");
  }
};

onMounted(async () => {
  await Promise.all([fetchCategories(), fetchBusinessSettings()]);

  try {
    await liff.init({ liffId: "2009928780-6PHEbZpr" });
    if (liff.isLoggedIn()) {
      const context = liff.getContext();
      if (context) lineUserId.value = context.userId;
    } else {
      liff.login();
    }
  } catch (error) {
    console.error("LIFF 初始化失敗:", error);
  }
});

const disabledDateLogic = (time) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const maxDate = new Date(today);
  maxDate.setDate(
    maxDate.getDate() + (businessSettings.value.max_advance_days || 30),
  );
  const dateStr = toDateStr(time);
  const offJsDays = (businessSettings.value.off_weekdays || []).map(pyWeekdayToJs);
  const holidaySet = new Set(
    (businessSettings.value.holidays || []).map((h) => h.holiday_date),
  );
  const isPast = time.getTime() < today.getTime();
  const isTooFar = time.getTime() > maxDate.getTime();
  const isOffDay = offJsDays.includes(time.getDay());
  const isHoliday = holidaySet.has(dateStr);
  return isPast || isTooFar || isOffDay || isHoliday;
};

const handleDateChange = async (val) => {
  if (form.date && form.time) {
    api.post("/api/slot/action", {
      date: form.date,
      time: form.time,
      action: "reject",
    });
  }
  if (!val) {
    availableSlots.value = [];
    return;
  }
  loading.value = true;
  form.time = "";
  try {
    const response = await api.get(`/available-slots?date=${val}`);
    availableSlots.value = response.data.available_slots;
  } catch (error) {
    ElMessage.error("無法取得時段");
  } finally {
    loading.value = false;
  }
};

const handleSlotClick = async (slot) => {
  if (form.time === slot) return;
  form.time = slot;
  try {
    const res = await api.post("/api/slot/lock", {
      date: form.date,
      time: slot,
      userId: lineUserId.value,
    });
    if (!res.data.success) {
      ElMessage.warning("該時段剛被選走");
      form.time = "";
      handleDateChange(form.date);
    } else {
      ElMessage.success({ message: "時段已保留 10 分鐘", duration: 2000 });
    }
  } catch (error) {
    ElMessage.error("鎖定失敗");
    form.time = "";
  }
};

const selectedCategory = computed(() =>
  categories.value.find((c) => c.id === selectedCategoryId.value)
);

const needsUserMessage = computed(() => {
  const name = selectedCategory.value?.category_name || "";
  return name.includes("阿卡西");
});

const canSubmit = computed(() => {
  return (
    form.lastName.trim() !== "" &&
    form.firstName.trim() !== "" &&
    selectedCategoryId.value !== null &&
    form.services.length > 0 &&
    form.date !== "" &&
    form.time !== "" &&
    (!needsUserMessage.value || form.user_message.trim() !== "")
  );
});

const serviceDuration = computed(() => {
  if (!servicesList.value.length || !form.services.length) {
    return 60;
  }
  const selected = servicesList.value.filter((service) =>
    form.services.includes(service.service_name),
  );
  if (!selected.length) return 60;
  return Math.max(...selected.map((service) => service.duration_minutes || 60));
});

const servicePrice = computed(() => {
  if (!servicesList.value.length || !form.services.length) {
    return 0;
  }
  const selected = servicesList.value.filter((service) =>
    form.services.includes(service.service_name),
  );
  if (!selected.length) return 0;
  // 同類多選（如阿卡西題目）沿用單次療程價；取選取項目中最高價
  return Math.max(...selected.map((service) => service.price || 0));
});

const payablePrice = computed(() => {
  if (appliedCoupon.value) {
    return appliedCoupon.value.discounted_price;
  }
  return servicePrice.value;
});

watch(
  () => [servicePrice.value, selectedCategoryId.value],
  (next, prev) => {
    if (!appliedCoupon.value) {
      return;
    }
    // 價格或類別變更後需重新套用，避免顯示過期折扣金額
    if (!prev || next[0] !== prev[0] || next[1] !== prev[1]) {
      appliedCoupon.value = null;
      couponError.value = "服務或價格已變更，請重新套用優惠碼";
    }
  },
);

function clearCoupon() {
  couponInput.value = "";
  couponError.value = "";
  appliedCoupon.value = null;
}

function onCouponInputChange() {
  couponError.value = "";
  if (appliedCoupon.value) {
    appliedCoupon.value = null;
  }
}

const applyCoupon = async () => {
  couponError.value = "";
  const code = couponInput.value.trim();
  if (!code) {
    couponError.value = "請輸入優惠碼";
    return;
  }
  if (!lineUserId.value) {
    couponError.value = "請先完成 LINE 登入後再套用優惠碼";
    return;
  }
  if (!selectedCategory.value) {
    couponError.value = "請先選擇服務類別";
    return;
  }
  if (!servicePrice.value) {
    couponError.value = "請先選擇服務項目";
    return;
  }

  couponValidating.value = true;
  try {
    const { data } = await api.post("/coupons/validate", {
      code,
      line_user_id: lineUserId.value,
      category: selectedCategory.value.category_name,
      base_price: servicePrice.value,
    });
    appliedCoupon.value = data;
    couponInput.value = data.code;
    ElMessage.success(data.message);
  } catch (error) {
    appliedCoupon.value = null;
    const detail = error.response?.data?.detail;
    couponError.value = detail || "無法辨識或無法使用此優惠碼";
  } finally {
    couponValidating.value = false;
  }
};

const submitForm = async () => {
  submitting.value = true;

  // 取得目前選中的類別名稱
  const currentCategory = selectedCategory.value;

  const payload = {
    line_user_id: lineUserId.value,
    last_name: form.lastName,
    first_name: form.firstName,
    category: currentCategory ? currentCategory.category_name : "",
    service_items: form.services,
    user_message: form.user_message,
    total_price: payablePrice.value,
    total_duration: serviceDuration.value,
    service_dateTime: `${form.date}T${form.time}:00`,
    coupon_code: appliedCoupon.value ? appliedCoupon.value.code : null,
  };

  try {
    await api.post("/appointments/", payload);
    ElMessage.success("已提交預約");
    setTimeout(() => {
      if (liff.isInClient()) liff.closeWindow();
    }, 1000);
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "提交失敗");
  } finally {
    submitting.value = false;
  }
};
</script>

<style scoped>
/* 讓 Checkbox 群組變成兩欄網格 */
.service-grid {
  display: grid;
  grid-template-columns: 1fr 1fr; /* 分成兩等份 */
  gap: 2px 20px; /* 垂直間距 10px，水平間距 20px */
  width: 100%;
  margin-top: 5px;
}

/* 修正 Element Plus 預設 Checkbox 的間距，確保置左對齊 */
:deep(.el-checkbox) {
  margin-right: 0; /* 移除預設的右邊距 */
  display: flex;
  align-items: center;
  justify-content: flex-start; /* 強制置左 */
}

/* 如果文字太長，可以限制寬度並換行 */
:deep(.el-checkbox__label) {
  white-space: normal;
  word-break: break-all;
  line-height: 1.4;
}

.booking-wrapper {
  display: flex;
  justify-content: center;
  padding: 20px;
  background-color: #f5f7fa;
  min-height: 100vh;
}

.booking-card {
  width: 100%;
  max-width: 450px;
}

.card-header h2 {
  margin: 0;
  text-align: center;
  color: #409eff;
}

.slots-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  width: 100%;
}

.slot-tag {
  padding: 8px;
  text-align: center;
  cursor: pointer;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
}

.no-slot-text {
  color: #909399;
  font-size: 14px;
  text-align: center;
}

.submit-area {
  margin-top: 30px;
  display: flex;
  justify-content: center;
}

.coupon-row {
  display: flex;
  gap: 8px;
  width: 100%;
}

.coupon-row .el-input {
  flex: 1;
}

.coupon-success {
  margin-top: 6px;
  color: #67c23a;
  font-size: 13px;
}

.coupon-error {
  margin-top: 6px;
  color: #f56c6c;
  font-size: 13px;
}

.description-text {
  font-size: 13px;
  color: #909399;
  margin-top: -10px;
  margin-bottom: 10px;
  text-align: left;
}

:global(.singing-bowl-warning .el-message-box__title) {
  color: #f56c6c;
  font-weight: 700;
}
</style>
