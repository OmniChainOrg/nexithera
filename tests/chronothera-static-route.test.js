const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

test('internal ChronoThera route has static cockpit shell and noindex metadata', () => {
  const html = fs.readFileSync(path.join(__dirname, '..', 'platform', 'chronothera', 'index.html'), 'utf8');
  assert.match(html, /<meta name="robots" content="noindex,nofollow"/);
  assert.match(html, /Internal Formulation &amp; Delivery Intelligence/);
  assert.match(html, /id="simulation-form"/);
  assert.match(html, /id="releaseChart"/);
  assert.match(html, /id="scorecard"/);
  assert.match(html, /id="guardianStatus"/);
  assert.match(html, /platform\/chronothera\/chronothera\.js/);
});

test('server serves directory index files before public homepage fallback', () => {
  const server = fs.readFileSync(path.join(__dirname, '..', 'server.js'), 'utf8');
  assert.match(server, /stats\.isDirectory\(\)/);
  assert.match(server, /path\.join\(candidatePath, 'index\.html'\)/);
});
