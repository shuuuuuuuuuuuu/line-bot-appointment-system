<script setup>
import { useRouter } from "vue-router";

const router = useRouter();

const modules = [
  {
    title: "數據總覽",
    description: "查看預約量、營收、待匯款與即將到來的場次。",
    route: "/stats",
    enabled: true,
  },
  {
    title: "服務項目",
    description: "管理服務名稱、價格、時長與顯示順序。",
    route: "/services",
    enabled: true,
  },
  {
    title: "訊息範本",
    description: "管理預約、付款與審核結果的回覆內容。",
    route: "/messages",
    enabled: true,
  },
  {
    title: "營業設定",
    description: "管理營業時段、休假日與預約間隔。",
    route: "/settings",
    enabled: true,
  },
];

function openModule(module) {
  if (module.enabled && module.route) {
    router.push(module.route);
  }
}
</script>

<template>
  <div>
    <div class="page-heading">
      <p class="eyebrow">Dashboard</p>
      <h1>管理總覽</h1>
      <p>已登入。可從左側選單或下方卡片進入各管理功能。</p>
    </div>

    <el-row :gutter="20">
      <el-col
        v-for="module in modules"
        :key="module.title"
        :xs="24"
        :sm="12"
        :md="12"
        :lg="6"
      >
        <el-card shadow="hover" class="module-card">
          <h2>{{ module.title }}</h2>
          <p>{{ module.description }}</p>
          <el-button
            :type="module.enabled ? 'primary' : 'default'"
            :disabled="!module.enabled"
            @click="openModule(module)"
          >
            {{ module.enabled ? "進入" : "尚未開放" }}
          </el-button>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>
