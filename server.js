const http = require('http');
const fs = require('fs');
const path = require('path');
const catalog = require('./lib/chronothera/catalog');
const { runChronoTheraSimulation } = require('./lib/chronothera/engine');
const { listSimulations, saveSimulation, getSimulation, listSimulationsByAsset, updateGuardianReview } = require('./lib/chronothera/storage');

const port = process.env.PORT || 3000;
const root = __dirname;

const mimeTypes = {
  '.html': 'text/html; charset=utf-8', '.css': 'text/css; charset=utf-8', '.js': 'application/javascript; charset=utf-8', '.json': 'application/json; charset=utf-8', '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.ico': 'image/x-icon', '.txt': 'text/plain; charset=utf-8'
};
function sendJson(res, status, body) { res.writeHead(status, { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-cache' }); res.end(JSON.stringify(body)); }
function readJson(req) { return new Promise((resolve, reject) => { let body = ''; req.on('data', c => { body += c; if (body.length > 1e6) { req.destroy(); reject(new Error('Request body too large')); } }); req.on('end', () => { try { resolve(body ? JSON.parse(body) : {}); } catch { reject(new Error('Invalid JSON body')); } }); req.on('error', reject); }); }
function sendFile(filePath, res) { fs.readFile(filePath, (err, data) => { if (err) { res.writeHead(500, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('Internal server error'); return; } const ext = path.extname(filePath).toLowerCase(); res.writeHead(200, { 'Content-Type': mimeTypes[ext] || 'application/octet-stream', 'Cache-Control': ext === '.html' ? 'no-cache' : 'public, max-age=3600' }); res.end(data); }); }
async function handleChronoTheraApi(req, res, requestPath) {
  try {
    if (req.method === 'GET' && requestPath === '/api/chronothera/catalog') return sendJson(res, 200, catalog);
    if (req.method === 'GET' && requestPath === '/api/chronothera/simulations') return sendJson(res, 200, { simulations: await listSimulations() });
    if (req.method === 'POST' && requestPath === '/api/chronothera/simulations') { const input = await readJson(req); const sim = runChronoTheraSimulation(input); await saveSimulation(sim); return sendJson(res, 201, sim); }
    const assetMatch = requestPath.match(/^\/api\/chronothera\/assets\/([^/]+)\/simulations$/);
    if (req.method === 'GET' && assetMatch) return sendJson(res, 200, { simulations: await listSimulationsByAsset(assetMatch[1]) });
    const reviewMatch = requestPath.match(/^\/api\/chronothera\/simulations\/([^/]+)\/guardian-review$/);
    if (req.method === 'POST' && reviewMatch) { const body = await readJson(req); if (!['approved', 'needs-revision', 'rejected'].includes(body.decision)) return sendJson(res, 400, { error: 'Guardian decision must be approved, needs-revision, or rejected' }); const sim = await updateGuardianReview(reviewMatch[1], { status: body.decision, reviewer: body.reviewer || 'Guardian', notes: body.notes || '' }); return sim ? sendJson(res, 200, sim) : sendJson(res, 404, { error: 'Simulation not found' }); }
    const simMatch = requestPath.match(/^\/api\/chronothera\/simulations\/([^/]+)$/);
    if (req.method === 'GET' && simMatch) { const sim = await getSimulation(simMatch[1]); return sim ? sendJson(res, 200, sim) : sendJson(res, 404, { error: 'Simulation not found' }); }
    return sendJson(res, 404, { error: 'ChronoThera API route not found' });
  } catch (error) { return sendJson(res, 400, { error: error.message }); }
}
const server = http.createServer((req, res) => {
  const requestPath = decodeURIComponent(req.url.split('?')[0]);
  if (requestPath.startsWith('/api/chronothera/')) { handleChronoTheraApi(req, res, requestPath); return; }
  const candidatePath = path.join(root, requestPath);
  if (!candidatePath.startsWith(root)) { res.writeHead(403, { 'Content-Type': 'text/plain; charset=utf-8' }); res.end('Forbidden'); return; }
  fs.stat(candidatePath, (err, stats) => { if (!err && stats.isFile()) { sendFile(candidatePath, res); return; } sendFile(path.join(root, 'index.html'), res); });
});
server.listen(port, () => { console.log(`NexiThera web service running on port ${port}`); });
