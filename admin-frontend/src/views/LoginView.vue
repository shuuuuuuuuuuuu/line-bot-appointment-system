<script setup>
import { reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { ElMessage } from "element-plus";

import { login } from "../api";
import { setToken } from "../auth";

const router = useRouter();
const loading = ref(false);
const form = reactive({
  email: "",
  password: "",
});

async function onSubmit() {
  if (!form.email || !form.password) {
    ElMessage.warning("請輸入帳號與密碼");
    return;
  }

  loading.value = true;
  try {
    const data = await login(form.email, form.password);
    setToken(data.access_token);
    ElMessage.success("登入成功");
    router.replace("/");
  } catch (error) {
    const detail = error.response?.data?.detail;
    ElMessage.error(detail || "登入失敗，請確認帳號密碼");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-page">
    <el-card class="login-card" shadow="never">
      <p class="eyebrow">Admin</p>
      <h1>預約系統管理後台</h1>
      <p class="subtitle">請使用管理員帳號登入</p>

      <el-form label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="Email">
          <el-input
            v-model="form.email"
            type="email"
            autocomplete="username"
            placeholder="owner@example.com"
          />
        </el-form-item>
        <el-form-item label="密碼">
          <el-input
            v-model="form.password"
            type="password"
            show-password
            autocomplete="current-password"
            placeholder="至少 8 個字元"
            @keyup.enter="onSubmit"
          />
        </el-form-item>
        <el-button
          type="primary"
          class="login-button"
          :loading="loading"
          @click="onSubmit"
        >
          登入
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>
