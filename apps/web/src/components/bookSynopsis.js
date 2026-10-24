import { createElement, Fragment } from 'react'

const allowed = new Set(['B', 'STRONG', 'I', 'EM', 'P', 'BR'])
const blocked = new Set(['SCRIPT', 'STYLE', 'IFRAME', 'OBJECT', 'EMBED', 'SVG', 'MATH', 'TEMPLATE'])

// Rebuild an allowlisted React tree: no source attributes, HTML injection or URLs survive.
export function parseBookSynopsis(description) {
  const doc = new DOMParser().parseFromString(String(description || ''), 'text/html')
  const clean = node => {
    if (node.nodeType === 3) return { text: node.textContent, content: node.textContent }
    if (node.nodeType !== 1 || blocked.has(node.tagName)) return { text: '', content: null }
    const children = [...node.childNodes].map(clean)
    const content = children.map((child, key) => createElement(Fragment, { key }, child.content))
    const text = children.map(child => child.text).join('')
    if (node.tagName === 'BR') return { text: '\n', content: createElement('br') }
    return { text: text + (node.tagName === 'P' ? '\n\n' : ''), content: allowed.has(node.tagName) ? createElement(node.tagName.toLowerCase(), null, content) : content }
  }
  const children = [...doc.body.childNodes].map(clean)
  return { text: children.map(child => child.text).join('').trim(), content: children.map((child, key) => createElement(Fragment, { key }, child.content)) }
}
