// Renders **bold** and *italic* from plain-text posts as React elements (never as HTML).
const pattern = /(\*\*[^*\n]+\*\*|\*[^*\n]+\*)/g

export default function FormattedText({ text = '', className }) {
  return <p className={className}>{text.split(pattern).map((part, index) => {
    if (/^\*\*[^*\n]+\*\*$/.test(part)) return <strong key={index}>{part.slice(2, -2)}</strong>
    if (/^\*[^*\n]+\*$/.test(part)) return <em key={index}>{part.slice(1, -1)}</em>
    return part
  })}</p>
}
