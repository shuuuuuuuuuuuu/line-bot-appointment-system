<script setup>
const modules = [
  {
    title: "服務項目",
    description: "管理服務名稱、價格、時長與顯示順序。",
  },
  {
    title: "訊息範本",
    description: "管理預約、付款與審核結果的回覆內容。",
  },
  {
    title: "營業設定",
    description: "管理營業時段、休假日與預約間隔。",
  },
];
</script>

<template>
  <el-container class="admin-shell">
    <el-aside width="220px" class="sidebar">
      <div class="brand">預約管理後台</div>
      <el-menu default-active="dashboard">
        <el-menu-item index="dashboard">總覽</el-menu-item>
        <el-menu-item index="services" disabled>服務項目</el-menu-item>
        <el-menu-item index="messages" disabled>訊息範本</el-menu-item>
        <el-menu-item index="settings" disabled>營業設定</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header class="header">
        <span>管理控制台</span>
        <el-tag type="warning" effect="plain">開發中</el-tag>
      </el-header>

      <el-main>
        <div class="page-heading">
          <p class="eyebrow">Dashboard</p>
          <h1>後台已準備好開始開發</h1>
          <p>
            管理介面已與 LINE LIFF 預約頁分開，後續功能會透過
            <code>/api/admin</code> 存取後端。
          </p>
        </div>

        <el-row :gutter="20">
          <el-col
            v-for="module in modules"
            :key="module.title"
            :xs="24"
            :md="8"
          >
            <el-card shadow="hover" class="module-card">
              <h2>{{ module.title }}</h2>
              <p>{{ module.description }}</p>
              <el-button disabled>尚未開放</el-button>
            </el-card>
          </el-col>
        </el-row>

        <el-alert
          title="建立任何管理 API 前，請先完成管理員登入與權限驗證。"
          type="warning"
          :closable="false"
          show-icon
        />
      </el-main>
    </el-container>
  </el-container>
</template>
