import { createRouter, createWebHistory } from "vue-router"
import { useUserStore } from "@/store"

const routes = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue")
  },
  {
    path: "/",
    name: "Dashboard",
    component: () => import("@/views/Dashboard.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/datasources",
    name: "DataSourceList",
    component: () => import("@/views/DataSourceList.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/datasources/create",
    name: "DataSourceCreate",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/datasources/:id/edit",
    name: "DataSourceEdit",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/query",
    name: "QueryEditor",
    component: () => import("@/views/QueryEditor.vue"),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  if (to.meta.requiresAuth && !userStore.token) {
    next("/login")
  } else if (to.path === "/login" && userStore.token) {
    next("/")
  } else {
    next()
  }
})

export default router