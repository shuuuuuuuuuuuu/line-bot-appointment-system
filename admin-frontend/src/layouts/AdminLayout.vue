<script setup>
import { computed, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { fetchCurrentAdmin } from "../api";
import { clearToken } from "../auth";

const route = useRoute();
const router = useRouter();
const admin = ref(null);
const loading = ref(true);

const activeMenu = computed(() => {
  if (route.path.startsWith("/services")) return "services";
  if (route.path.startsWith("/messages")) return "messages";
  if (route.path.startsWith("/settings")) return "settings";
  return "dashboard";
});

onMounted(async () => {
  try {
    admin.value = await fetchCurrentAdmin();
  } catch (error) {
    ElMessage.error("無法驗證登入狀態，請重新登入");
    clearToken();
    router.replace("/login");
  } finally {
    loading.value = false;
  }
});

function onMenuSelect(index) {
  if (index === "dashboard") {
    router.push("/");
    return;
  }
  if (index === "services") {
    router.push("/services");
    return;
  }
  if (index === "messages") {
    router.push("/messages");
    return;
  }
  if (index === "settings") {
    router.push("/settings");
  }
}

function logout() {
  clearToken();
  router.replace("/login");
}
</script>

<template>
  <el-container v-loading="loading" class="admin-shell">
    <el-aside width="220px" class="sidebar">
      <div class="brand">預約管理後台</div>
      <el-menu :default-active="activeMenu" @select="onMenuSelect">
        <el-menu-item index="dashboard">總覽</el-menu-item>
        <el-menu-item index="services">服務項目</el-menu-item>
        <el-menu-item index="messages">訊息範本</el-menu-item>
        <el-menu-item index="settings">營業設定</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span>管理控制台</span>
        <div class="header-actions">
          <span v-if="admin" class="admin-email">{{ admin.email }}</span>
          <el-button text type="primary" @click="logout">登出</el-button>
        </div>
      </el-header>

      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
