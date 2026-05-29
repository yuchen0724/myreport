const BLOCKED_TAGS = new Set([
  'script',
  'style',
  'iframe',
  'object',
  'embed',
  'link',
  'meta',
  'base',
  'form',
  'input',
  'button',
])

const URI_ATTRS = new Set(['href', 'src', 'xlink:href', 'formaction'])
const SAFE_URI_PATTERN = /^(https?:|mailto:|tel:|#|\/(?!\/))/i

function sanitizeNode(node) {
  if (node.nodeType !== Node.ELEMENT_NODE) {
    return
  }

  const element = node
  const tag = element.tagName.toLowerCase()

  if (BLOCKED_TAGS.has(tag)) {
    element.remove()
    return
  }

  for (const attr of Array.from(element.attributes)) {
    const name = attr.name.toLowerCase()
    const value = attr.value.trim()

    if (name.startsWith('on') || name === 'style') {
      element.removeAttribute(attr.name)
      continue
    }

    if (URI_ATTRS.has(name) && value && !SAFE_URI_PATTERN.test(value)) {
      element.removeAttribute(attr.name)
    }
  }

  for (const child of Array.from(element.childNodes)) {
    sanitizeNode(child)
  }
}

export function sanitizeHtml(html) {
  if (!html) return ''

  if (typeof window === 'undefined' || typeof DOMParser === 'undefined') {
    return String(html)
      .replace(/<script[\s\S]*?<\/script>/gi, '')
      .replace(/\s+on\w+\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\s+style\s*=\s*["'][^"']*["']/gi, '')
      .replace(/\s+(href|src)\s*=\s*["']\s*javascript:[^"']*["']/gi, '')
  }

  const parser = new DOMParser()
  const doc = parser.parseFromString(`<template>${html}</template>`, 'text/html')
  const template = doc.querySelector('template')

  for (const child of Array.from(template.content.childNodes)) {
    sanitizeNode(child)
  }

  const container = document.createElement('div')
  container.appendChild(template.content.cloneNode(true))
  return container.innerHTML
}
