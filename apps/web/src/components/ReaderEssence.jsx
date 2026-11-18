import { Sparkles } from 'lucide-react'

export default function ReaderEssence({ essence }) {
  return <section className="dna-card dna-essence" aria-label="Tu esencia como lector">
    <header className="dna-card-heading"><div><span className="dna-kicker"><Sparkles size={15} aria-hidden="true" />Tu esencia como lector</span>
      <h3>{essence?.archetype || (essence?.evidence_level === 'partial' ? 'Tus primeras tendencias literarias' : 'Una identidad que se está construyendo')}</h3></div></header>
    {!essence ? <p className="dna-muted">Este análisis es de una versión anterior. Tu esencia podrá incorporarse en una próxima actualización, sin perder las dimensiones ya guardadas.</p>
      : essence.evidence_level === 'insufficient' ? <p className="dna-muted">Todavía faltan reflexiones personales para interpretar tu esencia con suficiente respaldo. Comparte qué disfrutaste, qué te incomodó y por qué en tus reseñas y notas de lectura.</p>
        : <><span className="dna-badge">{essence.evidence_level === 'partial' ? 'Tendencias preliminares' : 'Basado en tus experiencias de lectura'}</span>
          <div className="dna-essence-narrative">{essence.summary?.split(/\n\s*\n/).filter(Boolean).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
          {essence.traits?.length > 0 && <ul className="dna-tags" aria-label="Rasgos literarios">{essence.traits.map(trait => <li key={trait}>{trait}</li>)}</ul>}</>}
  </section>
}
