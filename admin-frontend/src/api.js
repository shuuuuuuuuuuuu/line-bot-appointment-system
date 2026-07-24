import axios from "axios";
import { clearToken, getToken } from "./auth";

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || "http://localhost:8000",
  timeout: 15000,
  headers: {
    "ngrok-skip-browser-warning": "true",
  },
});

api.interceptors.request.use((config) => {
  const token = getToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      clearToken();
      if (window.location.pathname !== "/login") {
        window.location.assign("/login");
      }
    }
    return Promise.reject(error);
  },
);

export async function login(email, password) {
  const { data } = await api.post("/api/admin/login", { email, password });
  return data;
}

export async function fetchCurrentAdmin() {
  const { data } = await api.get("/api/admin/me");
  return data;
}

export async function fetchAdminCategories() {
  const { data } = await api.get("/api/admin/categories");
  return data;
}

export async function fetchAdminServices(categoryId) {
  const { data } = await api.get("/api/admin/services", {
    params: categoryId ? { category_id: categoryId } : undefined,
  });
  return data;
}

export async function createService(payload) {
  const { data } = await api.post("/api/admin/services", payload);
  return data;
}

export async function updateService(serviceId, payload) {
  const { data } = await api.put(`/api/admin/services/${serviceId}`, payload);
  return data;
}

export async function deleteService(serviceId) {
  const { data } = await api.delete(`/api/admin/services/${serviceId}`);
  return data;
}

export async function reorderServices(items) {
  const { data } = await api.put("/api/admin/services/reorder", { items });
  return data;
}

export async function fetchMessageTemplates(key) {
  const { data } = await api.get("/api/admin/message-templates", {
    params: key ? { key } : undefined,
  });
  return data;
}

export async function updateMessageTemplate(templateId, payload) {
  const { data } = await api.put(
    `/api/admin/message-templates/${templateId}`,
    payload,
  );
  return data;
}

export async function fetchBusinessSettings() {
  const { data } = await api.get("/api/admin/business-settings");
  return data;
}

export async function updateBusinessSettings(payload) {
  const { data } = await api.put("/api/admin/business-settings", payload);
  return data;
}

export async function createBusinessHoliday(payload) {
  const { data } = await api.post("/api/admin/business-holidays", payload);
  return data;
}

export async function deleteBusinessHoliday(holidayId) {
  const { data } = await api.delete(`/api/admin/business-holidays/${holidayId}`);
  return data;
}

export default api;
