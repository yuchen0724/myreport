import request from "@/utils/request"

export function exportExcel(data) {
  return request({
    url: "/report/excel",
    method: "post",
    data,
    responseType: "blob"
  })
}

export function exportExcelAsync(data) {
  return request({
    url: "/report/excel/async",
    method: "post",
    data
  })
}

export function getExportTask(taskId) {
  return request({
    url: `/report/task/${taskId}`,
    method: "get"
  })
}

export function downloadExportFile(taskId) {
  return request({
    url: `/report/download/${taskId}`,
    method: "get",
    responseType: "blob"
  })
}