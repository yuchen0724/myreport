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
  },
  {
    path: "/nl2sql",
    name: "NL2SQL",
    component: () => import("@/views/NL2SQLEditor.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/charts",
    name: "Charts",
    component: () => import("@/views/ChartViewer.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates",
    name: "Templates",
    component: () => import("@/views/TemplateList.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates/create",
    name: "TemplateCreate",
    component: () => import("@/views/TemplateForm.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates/:id",
    name: "TemplateDetail",
    component: () => import("@/views/TemplateDetail.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates/:id/edit",
    name: "TemplateEdit",
    component: () => import("@/views/TemplateForm.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates/:id/versions",
    name: "TemplateVersions",
    component: () => import("@/views/TemplateVersion.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/templates/:id/version-history",
    name: "TemplateVersionHistory",
    component: () => import("@/views/TemplateVersionHistory.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/async-export",
    name: "AsyncExport",
    component: () => import("@/views/AsyncExport.vue"),
    meta: { requiresAuth: true }
  },
  {
    path: "/template-share",
    name: "TemplateShare",
    component: () => import("@/views/TemplateShare.vue"),
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
