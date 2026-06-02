import request from "@/utils/request"

export interface FavoriteItem {
  id: number
  template_id: number
  template_name: string
  user_id: number
  created_at: string
}

export function getFavorites(): Promise<FavoriteItem[]> {
  return request({ url: "/favorites", method: "get" }) as Promise<FavoriteItem[]>
}

export function addFavorite(templateId: number): Promise<void> {
  return request({ url: "/favorites", method: "post", data: { template_id: templateId } }) as Promise<void>
}

export function removeFavorite(templateId: number): Promise<void> {
  return request({ url: `/favorites/${templateId}`, method: "delete" }) as Promise<void>
}

// ── Legacy name aliases ───────────────────────────────────
export const updateFavorite = addFavorite
export const removeFavoriteByTemplate = removeFavorite
export function checkFavorite(templateId: number): Promise<{ is_favorite: boolean }> {
  return request({ url: `/favorites/check/${templateId}`, method: "get" }) as Promise<{ is_favorite: boolean }>
}
