const crypto = require('crypto');
const ENGINE_VERSION = 'chronothera-engine-v0.1';
function stableStringify(value) {
  if (Array.isArray(value)) return `[${value.map(stableStringify).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${stableStringify(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}
function hashObject(value) { return crypto.createHash('sha256').update(stableStringify(value)).digest('hex'); }
function buildEpistemicTrace(input, releaseProfile, scorecard) {
  const inputHash = hashObject(input);
  const outputHash = hashObject({ releaseProfile, scorecard });
  return {
    zoneCluster: 'ChronoThera Formulation & Delivery Zone Cluster',
    zones: ['Formulation Zone', 'Delivery Zone', 'PK/PD Optimization Zone', 'Stability & Manufacturability Zone', 'Patient-Centric Design Zone', 'Regulatory Bridge Zone'],
    cxus: [
      { id: 'CXU_RELEASE_KINETICS', question: 'Does the selected formulation goal produce a plausible research-use release profile?', confidence: 0.72, uncertainty: ['Placeholder model', 'No wet-lab data', 'No validated PK model'] },
      { id: 'CXU_EXCIPIENT_COMPATIBILITY', question: 'Are selected excipients compatible with the API and route assumptions?', confidence: 0.68, uncertainty: ['Compatibility matrix is provisional'] },
      { id: 'CXU_ROUTE_FEASIBILITY', question: 'Does the route fit the selected formulation goal and portfolio context?', confidence: scorecard.routeCompatibility / 100, uncertainty: ['Route assessment is heuristic'] },
      { id: 'CXU_GUARDIAN_REVIEW', question: 'Does this preliminary output require Guardian review?', confidence: 0.7, uncertainty: ['Policy thresholds are configurable'] }
    ],
    swarm: { id: 'CHRONOTHERA_FORMULATION_SWARM', mode: 'cooperative', participants: ['Release Kinetics CXU', 'Excipient Compatibility CXU', 'Route Feasibility CXU', 'Manufacturability CXU', 'Patient-Centricity CXU', 'Regulatory Bridge CXU'], consensusScore: scorecard.overallChronoTheraScore },
    provenance: { inputHash, outputHash, engineVersion: ENGINE_VERSION, generatedAt: new Date(1704067200000 + parseInt(inputHash.slice(0, 8), 16) * 1000).toISOString() }
  };
}
module.exports = { buildEpistemicTrace, hashObject, stableStringify, ENGINE_VERSION };
