/** Shared API response types */

/** Standard paginated list response */
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

/** Standard API error response from backend (app/schemas/error.py) */
export interface ApiError {
  error_code: string
  message: string
  details?: Record<string, unknown>
  path?: string
  request_id?: string
  errors?: Array<{ field: string; message: string; type: string }>
}

/** Wrap axios response data — use when backend returns {data: T} top-level */
export interface DataWrapper<T> {
  data: T
}

/** Generic API list response wrapper */
export interface ListResponse<T> {
  data: T[]
}
