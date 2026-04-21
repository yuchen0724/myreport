import request from "@/utils/request"

export function getDataSourceList(params) {
  return request({
    url: "/datasources",
    method: "get",
    params
  })
}

export function getDataSource(id) {
  return request({
    url: `/datasources/${id}`,
    method: "get"
  })
}

export function createDataSource(data) {
  return request({
    url: "/datasources",
    method: "post",
    data
  })
}

export function updateDataSource(id, data) {
  return request({
    url: `/datasources/${id}`,
    method: "put",
    data
  })
}

export function deleteDataSource(id) {
  return request({
    url: `/datasources/${id}`,
    method: "delete"
  })
}

export function testDataSourceConnection(data) {
  return request({
    url: "/datasources/test",
    method: "post",
    data
  })
}