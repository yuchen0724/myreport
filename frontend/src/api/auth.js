import request from "@/utils/request"

export function login(username, password) {
  return request({
    url: "/auth/login",
    method: "post",
    data: `username=${username}&password=${password}`,
    headers: {
      "Content-Type": "application/x-www-form-urlencoded"
    }
  })
}

export function getCurrentUser() {
  return request({
    url: "/auth/me",
    method: "get"
  })
}