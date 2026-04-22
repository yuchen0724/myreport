// frontend/src/api/user.js
import request from "@/utils/request"

export function getUserList(params) {
  return request({
    url: "/api/users",
    method: "get",
    params
  })
}
