import assert from 'node:assert/strict'
import { resolveApiLocation } from '../src/api/apiLocation.js'

for (const host of ['localhost', '127.0.0.1', '[::1]']) {
  assert.equal(resolveApiLocation(`http://${host}:8000/api`, 'http://192.168.1.193:5173', true), 'http://192.168.1.193:5173/api')
}
assert.equal(resolveApiLocation('http://localhost:8000/api', 'http://localhost:5173', true), 'http://localhost:5173/api')
assert.equal(resolveApiLocation('/api', 'https://libria.example', false), 'https://libria.example/api')
assert.equal(resolveApiLocation('https://api.example/api', 'https://libria.example', true), 'https://api.example/api')
assert.equal(resolveApiLocation('http://localhost:8000/api', 'http://localhost:5173', false), 'http://localhost:8000/api')
console.log('PASS: LAN and desktop development use the API proxy; explicit remote and production URLs are preserved')
