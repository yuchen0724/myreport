import request from "@/utils/request"

export function getWidgetConfig() {
  return request({
    url: "/dashboard/widgets",
    method: "get"
  })
}

export function saveWidgetConfig(data) {
  return request({
    url: "/dashboard/widgets",
    method: "put",
    data
  })
}

export function getDashboardData() {
  return request({
    url: "/dashboard/data",
    method: "get"
  })
}
