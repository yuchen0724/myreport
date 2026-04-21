// frontend/src/api/chart.js
import request from "@/utils/request"

export function generateChart(data) {
  return request({
    url: "/charts/generate",
    method: "post",
    data
  })
}
