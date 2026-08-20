import axios from "axios";
import { clearToken, getToken } from "./auth";

const api = axios.create({
  baseURL:
    import.meta.env.VITE_ADMIN_API_URL ||
    import.meta.env.VITE_API_URL ||
    "http://localhost:8000",
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
  }
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
    payload
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

export async function updateWeeklyHours(payload) {
  const { data } = await api.put("/api/admin/business-settings/weekly-hours", payload);
  return data;
}

export async function upsertDateOverride(payload) {
  const { data } = await api.post("/api/admin/business-settings/date-overrides", payload);
  return data;
}

export async function deleteDateOverride(overrideId) {
  const { data } = await api.delete(
    `/api/admin/business-settings/date-overrides/${overrideId}`
  );
  return data;
}

export async function createBusinessHoliday(payload) {
  const { data } = await api.post("/api/admin/business-holidays", payload);
  return data;
}

export async function deleteBusinessHoliday(holidayId) {
  const { data } = await api.delete(
    `/api/admin/business-holidays/${holidayId}`
  );
  return data;
}

export async function fetchAdminStats(period = "month") {
  const { data } = await api.get("/api/admin/stats", {
    params: { period },
  });
  return data;
}

export async function exportAdminAppointments(period = "month", appointmentIds) {
  const response = await api.post(
    "/api/admin/stats/appointments/export",
    {
      period,
      appointment_ids: appointmentIds,
    },
    { responseType: "blob" },
  );
  return response;
}

export async function fetchAdminCoupons() {
  const { data } = await api.get("/api/admin/coupons");
  return data;
}

export async function createCoupon(payload) {
  const { data } = await api.post("/api/admin/coupons", payload);
  return data;
}

export async function updateCoupon(couponId, payload) {
  const { data } = await api.put(`/api/admin/coupons/${couponId}`, payload);
  return data;
}

export async function deleteCoupon(couponId) {
  const { data } = await api.delete(`/api/admin/coupons/${couponId}`);
  return data;
}

export async function fetchAdminClients(q) {
  const { data } = await api.get("/api/admin/clients", {
    params: q ? { q } : undefined,
  });
  return data;
}

export async function fetchCouponEligibilities(couponId) {
  const { data } = await api.get(`/api/admin/coupons/${couponId}/eligibilities`);
  return data;
}

export async function addCouponEligibilities(couponId, lineUserIds) {
  const { data } = await api.post(`/api/admin/coupons/${couponId}/eligibilities`, {
    line_user_ids: lineUserIds,
  });
  return data;
}

export async function removeCouponEligibility(couponId, eligibilityId) {
  const { data } = await api.delete(
    `/api/admin/coupons/${couponId}/eligibilities/${eligibilityId}`,
  );
  return data;
}

export default api;
