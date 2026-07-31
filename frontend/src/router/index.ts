import { createRouter, createWebHistory } from "vue-router"
import type { RouteRecordRaw, RouteMeta } from "vue-router"
import { useUserStore } from "@/store"

// Augment Vue Router meta types
declare module "vue-router" {
  interface RouteMeta {
    requiresAuth?: boolean
    roles?: string[]
  }
}

function isMobileDevice(): boolean {
  if (typeof window === "undefined") return false
  return window.innerWidth < 768
}

const routes: RouteRecordRaw[] = [
  {
    path: "/login",
    name: "Login",
    component: () => import("@/views/Login.vue"),
  },
  {
    path: "/",
    name: "Dashboard",
    component: () =>
      isMobileDevice()
        ? import("@/views/mobile/MobileDashboard.vue")
        : import("@/views/Dashboard.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/dashboard/layouts",
    name: "DashboardLayouts",
    component: () => import("@/views/LayoutList.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/datasources",
    name: "DataSourceList",
    component: () => import("@/views/DataSourceList.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/datasources/create",
    name: "DataSourceCreate",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/datasources/:id/edit",
    name: "DataSourceEdit",
    component: () => import("@/views/DataSourceForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/proxy-servers",
    name: "ProxyServerList",
    component: () => import("@/views/ProxyServerList.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/proxy-servers/create",
    name: "ProxyServerCreate",
    component: () => import("@/views/ProxyServerForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/proxy-servers/:id/edit",
    name: "ProxyServerEdit",
    component: () => import("@/views/ProxyServerForm.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/query",
    name: "QueryEditor",
    component: () =>
      isMobileDevice()
        ? import("@/views/mobile/MobileQuery.vue")
        : import("@/views/QueryEditor.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/nl2sql",
    name: "NL2SQL",
    component: () => import("@/views/NL2SQLEditor.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/charts",
    name: "Charts",
    component: () => import("@/views/ChartViewer.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/templates",
    name: "Templates",
    component: () =>
      isMobileDevice()
        ? import("@/views/mobile/MobileTemplates.vue")
        : import("@/views/TemplateList.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/templates/create",
    name: "TemplateCreate",
    component: () => import("@/views/TemplateForm.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/templates/:id",
    name: "TemplateDetail",
    component: () => import("@/views/TemplateDetail.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/templates/:id/edit",
    name: "TemplateEdit",
    component: () => import("@/views/TemplateForm.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/templates/:id/versions",
    name: "TemplateVersions",
    component: () => import("@/views/TemplateVersion.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/templates/:id/version-history",
    name: "TemplateVersionHistory",
    component: () => import("@/views/TemplateVersionHistory.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/async-export",
    name: "AsyncExport",
    component: () => import("@/views/AsyncExport.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/template-share",
    name: "TemplateShare",
    component: () => import("@/views/TemplateShare.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/favorites",
    name: "Favorites",
    component: () => import("@/views/Favorites.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/menus",
    name: "MenuList",
    component: () => import("@/views/MenuList.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/report/:id",
    name: "ReportView",
    component: () => import("@/views/ReportView.vue"),
    meta: { requiresAuth: true },
  },
  {
    path: "/sales-forecast",
    name: "SalesForecast",
    component: () => import("@/views/SalesForecast.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/forecast-results",
    name: "ForecastResults",
    component: () => import("@/views/ForecastResultQuery.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/scheduled-reports",
    name: "ScheduledReports",
    component: () => import("@/views/ScheduledReportList.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/subscriptions",
    name: "Subscriptions",
    component: () => import("@/views/SubscriptionList.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/sql-reviews",
    name: "SqlReviews",
    component: () => import("@/views/SqlReviewList.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/model-compare",
    name: "ModelCompare",
    component: () => import("@/views/ModelCompare.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/pool-monitor",
    name: "PoolMonitor",
    component: () => import("@/views/PoolMonitor.vue"),
    meta: { requiresAuth: true, roles: ["admin"] },
  },
  {
    path: "/semantic-metrics",
    name: "SemanticMetrics",
    component: () => import("@/views/SemanticMetricList.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/ai-analyst",
    name: "AIAnalyst",
    component: () => import("@/views/AIAnalyst.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor", "user"] },
  },
  {
    path: "/ai-design",
    name: "AIDesignStudio",
    component: () => import("@/views/AIDesignStudio.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/rca",
    name: "RcaDashboard",
    component: () => import("@/views/RcaDashboard.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
  {
    path: "/rca/:taskId",
    name: "RcaAnomalies",
    component: () => import("@/views/RcaAnomalies.vue"),
    meta: { requiresAuth: true, roles: ["admin", "editor"] },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to, _from, next) => {
  const userStore = useUserStore()
  const hasToken = !!userStore.token

  if (to.path === "/login" && hasToken) {
    next("/")
    return
  }

  if (to.meta.requiresAuth && !hasToken) {
    next("/login")
    return
  }

  if (to.meta.roles && !userStore.hasRole(to.meta.roles)) {
    next("/")
    return
  }

  next()
})

export default router
