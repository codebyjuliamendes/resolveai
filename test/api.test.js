const { test, before, after } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { once } = require('node:events');
const fs = require('node:fs/promises');
const os = require('node:os');
const path = require('node:path');
let child, baseUrl, tempDir;
before(async () => {
  tempDir = await fs.mkdtemp(path.join(os.tmpdir(), 'resolveai-test-'));
  const port = 20000 + Math.floor(Math.random() * 40000); baseUrl = `http://127.0.0.1:${port}`;
  child = spawn(process.execPath, ['server.js'], { cwd: path.resolve(__dirname, '..'), env: { ...process.env, PORT: String(port), DATABASE_PATH: path.join(tempDir, 'test.sqlite'), OPENAI_API_KEY: '', OPENAI_MODEL: '' }, stdio: 'ignore' });
  for (let i = 0; i < 100; i++) { if (child.exitCode !== null) throw new Error(`Server exited with code ${child.exitCode}`); try { if ((await fetch(`${baseUrl}/api/articles`)).ok) return; } catch {} await new Promise(resolve => setTimeout(resolve, 50)); }
  throw new Error('Test server did not become ready');
});
after(async () => { if (child && child.exitCode === null) { child.kill(); await Promise.race([once(child, 'exit'), new Promise(resolve => setTimeout(resolve, 2000))]); } if (tempDir) await fs.rm(tempDir, { recursive: true, force: true }); });
async function json(url, options) { const response = await fetch(baseUrl + url, { ...options, headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) } }); return { response, body: await response.json() }; }
test('knowledge edits retain prior versions and retrieval suggestions cite the edited source', async () => {
  const created = await json('/api/articles', { method: 'POST', body: JSON.stringify({ title: 'Reset a forgotten password', category: 'Account', body: 'Open account settings, choose password reset, and follow the verified reset link sent to your registered email.' }) }); assert.equal(created.response.status, 201);
  const updated = await json(`/api/articles/${created.body.id}`, { method: 'PUT', body: JSON.stringify({ title: 'Reset a forgotten password', category: 'Account', body: 'Use the account recovery screen and verify identity before changing credentials. Support agents should never ask customers to share passwords.', editor: 'qa reviewer' }) }); assert.equal(updated.response.status, 200); assert.equal(updated.body.version, 1);
  const history = await json(`/api/articles/${created.body.id}/history`); assert.equal(history.body.length, 1); assert.match(history.body[0].body, /verified reset link/); assert.equal(history.body[0].editor, 'qa reviewer');
  const suggestion = await json('/api/suggest', { method: 'POST', body: JSON.stringify({ message: 'How can I reset my password?' }) }); assert.equal(suggestion.response.status, 200); assert.equal(suggestion.body.mode, 'base-local'); assert.equal(suggestion.body.needsReview, true); assert.ok(suggestion.body.sources.some(source => source.id === created.body.id));
  const noSource = await json('/api/suggest', { method: 'POST', body: JSON.stringify({ message: 'Can you explain quantum entanglement?' }) }); assert.equal(noSource.body.mode, 'sem-fonte'); assert.deepEqual(noSource.body.sources, []);
});
