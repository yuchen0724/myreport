import { createRouter, createWebHistory } from "vue-router"
import { useUserStore } from "@/store"

// 路由守卫：检查登录和权限
function requireAuth(to, from, next) {
  const userStore = useUserStore()
  
  if (!userStore.token) {
    next("/login")
    return
  }
  
  // 检查角色权限
  if (to.meta.roles && !userStore.hasRole(to.meta.roles)) {
    // 无权限，跳转到首页
    next("/")
    return
  }
  
  next()
}

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
    meta: { requiresAuth: true, roles: ["admin", "editor"] }
  },
  {
    path: "/datasources/create",
    name: "DataSourceCreate",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] }
  },
  {
    path: "/datasources/:id/edit",
    name: "DataSourceEdit",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] }
  },
  {
    path: "/query",
    name: "QueryEditor",
    component: () => import("@/views/QueryEditor.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] }
  },
  {
    path: "/nl2sql",
    name: "NL2SQL",
    component: () => import("@/views/NL2SQLEditor.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] }
  },
  {
    path: "/charts",
    name: "Charts",
    component: () => import("@/views/ChartViewer.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] }
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
  },
  {
    path: "/menus",
    name: "MenuList",
    component: () => import("@/views/MenuList.vue"),
    meta: { requiresAuth: true, roles: ["admin"] }
  },
  {
    path: "/report/:id",
    name: "ReportView",
    component: () => import("@/views/ReportView.vue"),
    meta: { requiresAuth: true }
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const userStore = useUserStore()
  const hasToken = !!userStore.token

  // 已登录用户访问登录页，跳转到首页
  if (to.path === "/login" && hasToken) {
    next("/")
    return
  }
  
  // 检查登录状态（但登录页不需要）
  if (to.meta.requiresAuth && !hasToken) {
    next("/login")
    return
  }
  
  // 检查角色权限
  if (to.meta.roles && !userStore.hasRole(to.meta.roles)) {
    next("/")
    return
  }
  
  next()
})

export default router
