import assert from 'node:assert/strict'
import { analysisErrorMessage } from '../src/components/analysisErrors.js'

const secondary = analysisErrorMessage({ error_code: 'provider_quota', error_provider: 'openai' })
assert.match(secondary, /proveedor activo es Gemini/)
assert.doesNotMatch(secondary, /OpenAI/)
assert.match(analysisErrorMessage({ error_code: 'provider_quota', error_provider: 'gemini' }), /Gemini/)
assert.doesNotMatch(analysisErrorMessage({ error_code: 'provider_quota' }), /Gemini|OpenAI/)
assert.match(analysisErrorMessage({ error_code: 'monthly_budget_exhausted', error_provider: 'openai' }), /presupuesto mensual.*LibrIA/)
assert.doesNotMatch(analysisErrorMessage({ error_code: 'provider_timeout', error_provider: 'openai' }), /OpenAI/)
console.log('PASS: actual failing provider, fallback quota, legacy fallback and separate application budget')
