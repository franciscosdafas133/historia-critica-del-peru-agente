import { Fragment } from 'react'

/**
 * Renderiza texto narrativo del backend (párrafos, negritas, citas [n],
 * listas con guion o viñeta, encabezados) como JSX seguro, sin
 * dangerouslySetInnerHTML. Porta el mismo criterio de formateo que
 * formatearMD() en servidor.py, adaptado a componentes React.
 */
function renderInline(text: string, keyPrefix: string) {
  const parts = text.split(/(\*\*.+?\*\*|\[\d+\])/g).filter(Boolean)
  return parts.map((part, i) => {
    const key = `${keyPrefix}-${i}`
    if (part.startsWith('**') && part.endsWith('**')) {
      return <b key={key}>{part.slice(2, -2)}</b>
    }
    const citation = part.match(/^\[(\d+)\]$/)
    if (citation) {
      return (
        <span key={key} className="rounded bg-brand-50 px-1 text-xs font-semibold text-brand-600">
          [{citation[1]}]
        </span>
      )
    }
    return <Fragment key={key}>{part}</Fragment>
  })
}

export function FormattedAnswer({ text }: { text: string }) {
  const blocks = text.split(/\n\s*\n/).map((b) => b.trim()).filter(Boolean)

  return (
    <div className="space-y-3">
      {blocks.map((block, i) => {
        const heading = block.match(/^#{1,3}\s*(.+)$/)
        if (heading) {
          return (
            <h3 key={i} className="text-sm font-semibold text-ink-900">
              {renderInline(heading[1], `h-${i}`)}
            </h3>
          )
        }

        const isList = /^[-*•]\s/m.test(block)
        if (isList) {
          const items = block.split('\n').filter((l) => l.trim())
          return (
            <ul key={i} className="list-inside list-disc space-y-1 text-sm leading-relaxed text-ink-700">
              {items.map((item, j) => (
                <li key={j}>{renderInline(item.replace(/^[-*•]\s*/, ''), `li-${i}-${j}`)}</li>
              ))}
            </ul>
          )
        }

        const isSources = /^(\*\*)?FUENTES/i.test(block)
        return (
          <p
            key={i}
            className={`text-sm leading-relaxed ${isSources ? 'text-ink-500' : 'text-ink-900'} whitespace-pre-line`}
          >
            {renderInline(block, `p-${i}`)}
          </p>
        )
      })}
    </div>
  )
}
