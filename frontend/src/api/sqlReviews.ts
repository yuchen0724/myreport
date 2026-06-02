import request from "@/utils/request"

export interface SqlReview {
  id: number
  sql: string
  status: string
  reviewer_id?: number
  review_comment?: string
  created_at: string
}

export const listReviews = getReviewList
export function getReviewList(params?: Record<string, unknown>): Promise<SqlReview[]> {
  return request({ url: "/sql-reviews", method: "get", params }) as Promise<SqlReview[]>
}

export function createReview(data: { sql: string; data_source_id: number }): Promise<SqlReview> {
  return request({ url: "/sql-reviews", method: "post", data }) as Promise<SqlReview>
}

export function approveReview(id: number, comment?: string): Promise<void> {
  return request({ url: `/sql-reviews/${id}/approve`, method: "post", data: { comment } }) as Promise<void>
}

export function rejectReview(id: number, comment: string): Promise<void> {
  return request({ url: `/sql-reviews/${id}/reject`, method: "post", data: { comment } }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export function getReview(id: number): Promise<SqlReview> {
  return request({ url: `/sql-reviews/${id}`, method: "get" }) as Promise<SqlReview>
}
export function reviewSql(id: number, data: { status: string; comment?: string }): Promise<void> {
  return request({ url: `/sql-reviews/${id}/review`, method: "post", data }) as Promise<void>
}
export function deleteReview(id: number): Promise<void> {
  return request({ url: `/sql-reviews/${id}`, method: "delete" }) as Promise<void>
}
