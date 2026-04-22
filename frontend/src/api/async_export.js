// frontend/src/api/async_export.js
import request from "@/utils/request"

export function createExportTask(data) {
  return request({
    url: "/async-export/create",
    method: "post",
    data
  })
}

export function getTaskStatus(taskId) {
  return request({
    url: `/async-export/task/${taskId}`,
    method: "get"
  })
}

export function getUserTasks(params) {
  return request({
    url: "/async-export/tasks",
    method: "get",
    params
  })
}

export function downloadExportFile(taskId) {
  return request({
    url: `/async-export/download/${taskId}`,
    method: "get",
    responseType: "blob"
  })
}
