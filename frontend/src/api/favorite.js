// frontend/src/api/favorite.js
import request from '@/utils/request'

export function getFavorites(category) {
  const params = {}
  if (category) params.category = category
  return request({
    url: '/favorites',
    method: 'get',
    params
  })
}

export function addFavorite(data) {
  return request({
    url: '/favorites',
    method: 'post',
    data
  })
}

export function updateFavorite(id, data) {
  return request({
    url: `/favorites/${id}`,
    method: 'put',
    data
  })
}

export function removeFavorite(id) {
  return request({
    url: `/favorites/${id}`,
    method: 'delete'
  })
}

export function removeFavoriteByTemplate(templateId) {
  return request({
    url: `/favorites/by-template/${templateId}`,
    method: 'delete'
  })
}

export function checkFavorite(templateId) {
  return request({
    url: `/favorites/check/${templateId}`,
    method: 'get'
  })
}
