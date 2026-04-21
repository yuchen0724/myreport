// frontend/src/api/nl2sql.js
import request from "@/utils/request"

export function parseQuestion(data) {
  return request({
    url: "/nl2sql/parse",
    method: "post",
    data
  })
}
