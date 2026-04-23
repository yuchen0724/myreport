import request from "@/utils/request"

export function executeSQL(data) {
  return request({
    url: "/query/sql",
    method: "post",
    data
  })
}

export function executeQuery(data) {
  return request({
    url: "/query/sql",
    method: "post",
    data
  })
}

export function getQueryHistory(params) {
  return request({
    url: "/query/history",
    method: "get",
    params
  })
}