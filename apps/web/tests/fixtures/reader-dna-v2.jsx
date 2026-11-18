import { useEffect, useState } from 'react'
import { createRoot } from 'react-dom/client'
import { ThemeProvider, useTheme } from '/src/context/ThemeContext'
import ReaderEssence from '/src/components/ReaderEssence'
import ReaderDnaEvolution from '/src/components/ReaderDnaEvolution'
import DnaProfileSections from '/src/components/DnaProfileSections'
import '/src/styles.css'
import '/src/theme/themes.css'
import '/src/components/ReaderDna.css'

const previous = { reader_essence: { evidence_level: 'sufficient', archetype: 'El viajero de las preguntas', summary: 'Tus reseñas destacan las decisiones de los personajes.\n\nDisfrutas los conflictos que dejan preguntas abiertas.', traits: ['Reflexivo', 'Atento a los personajes', 'Explorador'] },
  narrative_preferences: ['Decisiones complejas'], character_preferences: ['Personajes que evolucionan'], themes_and_conflicts: ['Conflictos morales'], emotional_patterns: ['Finales que invitan a reflexionar'], rating_patterns: ['Valoras la coherencia narrativa'], genres_and_styles: ['Fantasía'], interests_from_notes_and_theories: ['Vínculos entre personajes'] }
const current = { ...previous, reader_essence: { ...previous.reader_essence, archetype: 'El explorador de los dilemas' }, evolution: {
  reference_version_id: 'previous', has_meaningful_changes: true, summary: 'Tus reflexiones recientes prestan mayor atención a los dilemas morales.',
  stable_patterns: [{ text: 'Sigues valorando la evolución de los personajes.' }], emerging_interests: [{ text: 'Exploras decisiones con consecuencias ambiguas.' }], changing_preferences: [],
} }
const versions = [{ id: 'current-analysis', dna_version_id: 'current', version: 2, created_at: '2026-11-18T12:00:00Z', content: current }, { id: 'old-analysis', dna_version_id: 'previous', version: 1, created_at: '2026-10-18T12:00:00Z', content: previous }]
window.dnaTest = { historyReads: 0 }
// eslint-disable-next-line react-refresh/only-export-components
function Demo() {
  const { selectTheme } = useTheme()
  const [history, setHistory] = useState(null)
  const [mode, setMode] = useState('sufficient')
  useEffect(() => { window.dnaTest.selectTheme = selectTheme; window.dnaTest.setMode = setMode }, [selectTheme])
  const essence = mode === 'legacy' ? undefined : mode === 'insufficient' ? { evidence_level: 'insufficient' } : current.reader_essence
  return <main className="reader-dna-view" style={{ padding: 20, maxWidth: 1100, margin: 'auto' }}><ReaderEssence essence={essence} /><h3>Las dimensiones de tu ADN</h3><DnaProfileSections content={current} />
    <ReaderDnaEvolution content={mode === 'sufficient' ? current : {}} currentId="current" currentAnalysisId="current-analysis" history={history} busy={false} onLoad={() => { window.dnaTest.historyReads++; setHistory(versions) }} /></main>
}
createRoot(document.getElementById('root')).render(<ThemeProvider><Demo /></ThemeProvider>)
