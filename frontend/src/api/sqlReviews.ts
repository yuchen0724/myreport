import request from "@/utils/request"

export interface SqlReviewFinding {
  code: string
  severity: "low" | "medium" | "high"
  title: string
  detail: string
  suggestion: string
}

export interface SqlReview {
  id: number
  template_id: number
  submitted_by: number
  status: "pending" | "approved" | "rejected"
  sql_content?: string
  reviewer_id?: number
  review_comment?: string
  ai_risk_level?: "low" | "medium" | "high"
  ai_review?: {
    risk_level: string
    recommendation: string
    findings: SqlReviewFinding[]
    tables: string[]
    ai_summary?: string
  }
  created_at?: string
  reviewed_at?: string
  ai_reviewed_at?: string
  template_name?: string
  submitter_name?: string
  reviewer_name?: string
}

export interface SqlReviewListResponse {
  items: SqlReview[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export const listReviews = getReviewList
export function getReviewList(params?: Record<string, unknown>): Promise<SqlReviewListResponse> {
  return request({ url: "/reviews", method: "get", params }) as Promise<SqlReviewListResponse>
}

export function createReview(data: { template_id: number; sql_content?: string }): Promise<SqlReview> {
  return request({ url: "/reviews", method: "post", data }) as Promise<SqlReview>
}

export function getReview(id: number): Promise<SqlReview> {
  return request({ url: `/reviews/${id}`, method: "get" }) as Promise<SqlReview>
}

export function reviewSql(
  id: number,
  data: { status: "approved" | "rejected"; review_comment?: string },
): Promise<SqlReview> {
  return request({ url: `/reviews/${id}/review`, method: "put", data }) as Promise<SqlReview>
}

export function refreshAiReview(id: number, useLlm = true): Promise<SqlReview> {
  return request({
    url: `/reviews/${id}/ai-review`,
    method: "post",
    params: { use_llm: useLlm },
  }) as Promise<SqlReview>
}

export function deleteReview(id: number): Promise<void> {
  return request({ url: `/reviews/${id}`, method: "delete" }) as Promise<void>
}

export function approveReview(id: number, comment?: string): Promise<SqlReview> {
  return reviewSql(id, { status: "approved", review_comment: comment })
}

export function rejectReview(id: number, comment: string): Promise<SqlReview> {
  return reviewSql(id, { status: "rejected", review_comment: comment })
}
