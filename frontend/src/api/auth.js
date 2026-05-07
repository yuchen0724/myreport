import request from "@/utils/request"

export function login(username, password) {
  const formData = new URLSearchParams()
  formData.append('username', username)
  formData.append('password', password)
  return request({
    url: "/auth/login",
    method: "post",
    data: formData,
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