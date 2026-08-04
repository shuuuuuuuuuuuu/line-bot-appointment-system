<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { ElMessage } from "element-plus";
import { Menu } from "@element-plus/icons-vue";

import { fetchCurrentAdmin } from "../api";
import { clearToken } from "../auth";

const route = useRoute();
const router = useRouter();
const admin = ref(null);
const loading = ref(true);
const isMobile = ref(false);
const drawerOpen = ref(false);

const activeMenu = computed(() => {
  if (route.path.startsWith("/stats")) return "stats";
  if (route.path.startsWith("/services")) return "services";
  if (route.path.startsWith("/coupons")) return "coupons";
  if (route.path.startsWith("/messages")) return "messages";
  if (route.path.startsWith("/settings")) return "settings";
  return "dashboard";
});

function updateViewport() {
  isMobile.value = window.matchMedia("(max-width: 767px)").matches;
  if (!isMobile.value) {
    drawerOpen.value = false;
  }
}

onMounted(async () => {
  updateViewport();
  window.addEventListener("resize", updateViewport);

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

onBeforeUnmount(() => {
  window.removeEventListener("resize", updateViewport);
});

function onMenuSelect(index) {
  if (index === "dashboard") {
    router.push("/");
  } else if (index === "stats") {
    router.push("/stats");
  } else if (index === "services") {
    router.push("/services");
  } else if (index === "coupons") {
    router.push("/coupons");
  } else if (index === "messages") {
    router.push("/messages");
  } else if (index === "settings") {
    router.push("/settings");
  }

  if (isMobile.value) {
    drawerOpen.value = false;
  }
}

function logout() {
  clearToken();
  router.replace("/login");
}
</script>

<template>
  <el-container v-loading="loading" class="admin-shell">
    <el-aside v-show="!isMobile" width="220px" class="sidebar desktop-sidebar">
      <div class="brand">預約管理後台</div>
      <el-menu :default-active="activeMenu" @select="onMenuSelect">
        <el-menu-item index="dashboard">總覽</el-menu-item>
        <el-menu-item index="stats">數據總覽</el-menu-item>
        <el-menu-item index="services">服務項目</el-menu-item>
        <el-menu-item index="coupons">折扣碼</el-menu-item>
        <el-menu-item index="messages">訊息範本</el-menu-item>
        <el-menu-item index="settings">營業設定</el-menu-item>
      </el-menu>
    </el-aside>

    <el-drawer
      v-model="drawerOpen"
      direction="ltr"
      size="260px"
      :with-header="false"
      class="mobile-nav-drawer"
    >
      <div class="brand drawer-brand">預約管理後台</div>
      <el-menu :default-active="activeMenu" @select="onMenuSelect">
        <el-menu-item index="dashboard">總覽</el-menu-item>
        <el-menu-item index="stats">數據總覽</el-menu-item>
        <el-menu-item index="services">服務項目</el-menu-item>
        <el-menu-item index="coupons">折扣碼</el-menu-item>
        <el-menu-item index="messages">訊息範本</el-menu-item>
        <el-menu-item index="settings">營業設定</el-menu-item>
      </el-menu>
    </el-drawer>

    <el-container class="admin-main-pane">
      <el-header class="header">
        <div class="header-left">
          <el-button
            v-if="isMobile"
            class="menu-toggle"
            text
            :icon="Menu"
            aria-label="開啟選單"
            @click="drawerOpen = true"
          />
          <span class="header-title">管理控制台</span>
        </div>
        <div class="header-actions">
          <span v-if="admin" class="admin-email">{{ admin.email }}</span>
          <el-button text type="primary" @click="logout">登出</el-button>
        </div>
      </el-header>

      <el-main class="admin-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
