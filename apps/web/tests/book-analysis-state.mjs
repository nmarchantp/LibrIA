import assert from 'node:assert/strict'
import { bookAnalysisMessages, shouldPollBookAnalysis } from '../src/components/bookAnalysisState.js'

for (const state of ['not_eligible', 'requires_review', 'waiting_nightly_processing', 'queued', 'processing', 'completed', 'update_pending', 'update_processing', 'failed']) {
  assert.equal(bookAnalysisMessages[state].length, 2, `Mensaje completo para ${state}`)
  assert.ok(bookAnalysisMessages[state].every(Boolean))
  assert.doesNotMatch(bookAnalysisMessages[state].join(' '), /ETL|worker|fingerprint|Gemini|batch/)
}
for (const status of ['waiting_nightly_processing', 'requires_review', 'not_eligible', 'completed', 'failed', 'update_pending']) {
  assert.equal(shouldPollBookAnalysis({ status }), false, `Sin sondeo durante ${status}`)
}
for (const status of ['queued', 'processing', 'update_processing']) {
  assert.equal(shouldPollBookAnalysis({ status }), true)
}
assert.equal(shouldPollBookAnalysis({ status: 'update_pending', job: { status: 'pending' } }), true)
assert.match(bookAnalysisMessages.waiting_nightly_processing[1], /medianoche/)
assert.match(bookAnalysisMessages.waiting_nightly_processing[1], /administrador/)
assert.match(bookAnalysisMessages.update_pending[1], /administrador/)
assert.equal(shouldPollBookAnalysis({ status: 'queued', job: { status: 'pending' }, generation_enabled: false }), false)
assert.equal(shouldPollBookAnalysis({ status: 'processing', job: { status: 'processing' }, generation_enabled: false }), true)
console.log('Estados y sondeo del análisis individual: OK')
