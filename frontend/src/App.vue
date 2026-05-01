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
          <el-input
            v-model="form.name"
            placeholder="請輸入您的法定姓名"
            autofocus
            @keyup.enter="$event.target.blur()"
          />
        </el-form-item>

        <!-- 服務項目（多選） -->
        <el-form-item label="服務項目">
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

        <!-- 日期選擇 (限制今天起一個月內) -->
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

        <!-- 服務時長 -->
        <el-form-item label="服務時長">
          <div style="min-height: 40px">
            <!-- 固定高度防止跳動 -->
            <transition name="el-zoom-in-center">
              <el-tag v-if="canSubmit" type="info" size="large">60 分鐘</el-tag>
            </transition>
          </div>
        </el-form-item>

        <!-- 服務金額 -->
        <el-form-item label="服務金額">
          <div style="min-height: 40px">
            <transition name="el-zoom-in-center">
              <el-tag
                v-if="canSubmit"
                type="primary"
                size="large"
                effect="plain"
                >$ 2,222</el-tag
              >
            </transition>
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
import { ref, reactive, computed, onMounted } from "vue";
import liff from "@line/liff";
import axios from "axios";
import { ElMessage } from "element-plus";

const API_BASE = import.meta.env.VITE_API_URL;

const api = axios.create({
  baseURL: API_BASE,
  headers: {
    "ngrok-skip-browser-warning": "any-value",
  },
});

// 1. 表單資料狀態
const form = reactive({
  name: "",
  services: [],
  date: "",
  time: "",
});

// 2. UI 狀態與資料列表
const lineUserId = ref("");
const servicesList = ref([]);
const availableSlots = ref([]); // 只保留這一個宣告
const loading = ref(false); // 只保留這一個宣告
const submitting = ref(false); // 只保留這一個宣告

// --- 從後端獲取服務項目 ---
const fetchServices = async () => {
  try {
    const response = await api.get("/services");
    servicesList.value = response.data;
  } catch (error) {
    console.error("獲取服務列表失敗:", error);
    ElMessage.error("無法載入服務項目，請檢查後端連線");
  }
};

// 頁面初始化時執行
onMounted(async () => {
  await fetchServices();

  try {
    // 這裡填入你在 LINE Developers Console 申請的 LIFF ID
    await liff.init({ liffId: "2009928780-6PHEbZpr" });

    if (liff.isLoggedIn()) {
      const context = liff.getContext();
      if (context) {
        lineUserId.value = context.userId;
        console.log("成功取得 UserId:", lineUserId.value);
      }
    } else {
      liff.login();
    }
  } catch (error) {
    console.error("LIFF 初始化失敗:", error);
  }
});

// --- 日期限制邏輯 ---
const disabledDateLogic = (time) => {
  const today = new Date();
  today.setHours(0, 0, 0, 0);

  const oneMonthLater = new Date();
  oneMonthLater.setMonth(today.getMonth() + 1);
  oneMonthLater.setHours(23, 59, 59, 999);

  const isPast = time.getTime() < today.getTime();
  const isTooFar = time.getTime() > oneMonthLater.getTime();
  const day = time.getDay();
  const isOffDay = [5, 6, 0].includes(day);

  return isPast || isTooFar || isOffDay;
};

// --- 抓取時段 ---
const handleDateChange = async (val) => {
  // 如果更換日期前已經有點選時段，釋放它
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
    console.error("抓取時段錯誤:", error);
    ElMessage.error("無法取得預約時段，請稍後再試");
  } finally {
    loading.value = false;
  }
};

// 修改時間選擇的點擊邏輯
const handleSlotClick = async (slot) => {
  // 如果點選的是已經選中的，不做事
  if (form.time === slot) return;

  const oldSlot = form.time; // 備份舊時段，用於失敗回退
  form.time = slot; // 先更新 UI

  try {
    const res = await api.post("/api/slot/lock", {
      date: form.date,
      time: slot,
      userId: lineUserId.value,
    });

    if (!res.data.success) {
      ElMessage.warning("該時段剛被選走，請選擇其他時段");
      form.time = ""; // 清除選取
      handleDateChange(form.date); // 刷新可用清單
    } else {
      // 鎖定成功
      ElMessage.success({ message: "時段已為您保留 10 分鐘", duration: 2000 });
    }
  } catch (error) {
    ElMessage.error("時段鎖定失敗");
    form.time = "";
  }
};

// --- 提交按鈕狀態 ---
const canSubmit = computed(() => {
  return (
    form.name.trim() !== "" &&
    form.services.length > 0 &&
    form.date !== "" &&
    form.time !== ""
  );
});

// --- 提交表單 ---
const submitForm = async () => {
  submitting.value = true;

  // 1. 轉換 service_items 格式
  // 比對 servicesList 中的所有項目，如果存在於 form.services 陣列中，則 selected 為 true
  const formattedServiceItems = servicesList.value.map((service) => ({
    name: service.service_name,
    selected: form.services.includes(service.service_name),
  }));

  // 2. 組合最終要送出的 Payload
  const payload = {
    line_user_id: lineUserId.value,
    name: form.name,
    service_items: formattedServiceItems,
    total_price: 2222, // 如果有計價邏輯可在此計算
    total_duration: 60,
    service_dateTime: `${form.date}T${form.time}:00`, // 格式化為 ISO 樣式
  };

  console.log("提交給後端的完整格式:", payload);

  try {
    const response = await api.post("/appointments/", payload);
    ElMessage.success("已提交預約");

    setTimeout(() => {
      if (liff.isInClient()) {
        liff.closeWindow();
      }
    }, 1000);
  } catch (error) {
    console.error("提交失敗:", error);
    ElMessage.error("提交失敗，請稍後再試");
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
</style>
