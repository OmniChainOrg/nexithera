const fs = require('fs/promises');
const path = require('path');
const dataFile = path.join(__dirname, '..', '..', 'data', 'chronothera', 'simulations.json');
async function ensureStore() { await fs.mkdir(path.dirname(dataFile), { recursive: true }); try { await fs.access(dataFile); } catch { await fs.writeFile(dataFile, JSON.stringify({ simulations: [] }, null, 2)); } }
async function readStore() { await ensureStore(); return JSON.parse(await fs.readFile(dataFile, 'utf8')); }
async function writeStore(store) { await ensureStore(); await fs.writeFile(dataFile, JSON.stringify(store, null, 2)); }
async function listSimulations() { return (await readStore()).simulations; }
async function saveSimulation(sim) { const store = await readStore(); store.simulations = store.simulations.filter(s => s.id !== sim.id); store.simulations.unshift(sim); await writeStore(store); return sim; }
async function getSimulation(id) { return (await listSimulations()).find(s => s.id === id); }
async function listSimulationsByAsset(assetId) { return (await listSimulations()).filter(s => s.assetId === assetId); }
async function updateGuardianReview(id, review) { const store = await readStore(); const sim = store.simulations.find(s => s.id === id); if (!sim) return null; sim.guardianReview = { ...sim.guardianReview, ...review, reviewedAt: new Date().toISOString() }; await writeStore(store); return sim; }
module.exports = { listSimulations, saveSimulation, getSimulation, listSimulationsByAsset, updateGuardianReview, dataFile };
