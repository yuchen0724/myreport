// frontend/src/api/user.js
import request from "@/utils/request"

export function getUserList(params) {
  return request({
    url: "/users",
    method: "get",
    params
  })
}
