import { createRouter, createWebHistory } from "vue-router";

import { isLoggedIn } from "./auth";
import AdminLayout from "./layouts/AdminLayout.vue";
import DashboardView from "./views/DashboardView.vue";
import LoginView from "./views/LoginView.vue";
import ServicesView from "./views/ServicesView.vue";
import MessagesView from "./views/MessagesView.vue";
import SettingsView from "./views/SettingsView.vue";
import StatsView from "./views/StatsView.vue";
import CouponsView from "./views/CouponsView.vue";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: LoginView,
      meta: { public: true },
    },
    {
      path: "/",
      component: AdminLayout,
      children: [
        {
          path: "",
          name: "dashboard",
          component: DashboardView,
        },
        {
          path: "stats",
          name: "stats",
          component: StatsView,
        },
        {
          path: "services",
          name: "services",
          component: ServicesView,
        },
        {
          path: "coupons",
          name: "coupons",
          component: CouponsView,
        },
        {
          path: "messages",
          name: "messages",
          component: MessagesView,
        },
        {
          path: "settings",
          name: "settings",
          component: SettingsView,
        },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      redirect: "/",
    },
  ],
});

router.beforeEach((to) => {
  if (to.meta.public) {
    if (to.name === "login" && isLoggedIn()) {
      return { name: "dashboard" };
    }
    return true;
  }

  if (!isLoggedIn()) {
    return { name: "login", query: { redirect: to.fullPath } };
  }

  return true;
});

export default router;
