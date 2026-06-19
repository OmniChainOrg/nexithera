const { formulationGoals, routesOfAdministration, regulatoryBodies, assetPresets } = require('./catalog');
const { buildEpistemicTrace, hashObject } = require('./epistemicos');
const DISCLAIMER = 'ChronoThera simulations are preliminary formulation-intelligence outputs for research and planning only. Results are not validated PK/PD predictions, regulatory advice, clinical recommendations, or manufacturing instructions.';
function clamp(n, min = 0, max = 100) { return Math.max(min, Math.min(max, Math.round(n))); }
const DOSE_UNIT_TO_MG = { mcg: 0.001, mg: 1, g: 1000 };
const SUPPORTED_DOSE_UNITS = new Set([...Object.keys(DOSE_UNIT_TO_MG), 'U']);
function doseAmountToMg(api) {
  const unit = api.doseUnit || api.dose_unit || 'mg';
  if (!SUPPORTED_DOSE_UNITS.has(unit)) throw new Error('Unsupported API dose unit');
  const amount = api.doseAmount ?? api.dose_amount ?? api.doseMg ?? api.dose_mg ?? 1;
  if (unit === 'U') return Number(amount);
  return Number(amount) * DOSE_UNIT_TO_MG[unit];
}
function validateSimulationInput(input) {
  if (!input || typeof input !== 'object') throw new Error('Simulation input is required');
  if (!Array.isArray(input.apis) || input.apis.length === 0) throw new Error('At least one API is required');
  if (input.apis.length > 5) throw new Error('ChronoThera supports up to five APIs per simulation');
  input.apis.forEach((api) => {
    const doseMg = doseAmountToMg(typeof api === 'object' ? api : { doseMg: 1 });
    if (!Number.isFinite(doseMg) || doseMg <= 0) throw new Error('Each API requires a positive dose');
  });
  if (!Array.isArray(input.excipients) || input.excipients.length === 0) throw new Error('At least one excipient is required');
  input.excipients.forEach((excipient) => {
    const e = typeof excipient === 'object' ? excipient : {};
    const amount = Number(e.amount ?? e.amount_mg ?? e.amountMg ?? 1);
    if (!Number.isFinite(amount) || amount <= 0) throw new Error('Each excipient requires a positive quantitative amount');
    const unit = e.unit || 'mg';
    if (!['mg', 'g'].includes(unit)) throw new Error('Unsupported excipient amount unit');
  });
  if (!formulationGoals.includes(input.formulationGoal)) throw new Error('Unsupported formulation goal');
  if (!routesOfAdministration.includes(input.routeOfAdministration)) throw new Error('Unsupported route of administration');
  if (!regulatoryBodies.includes(input.regulatoryBody)) throw new Error('Unsupported regulatory body');
  const weeks = Number(input.releaseDurationWeeks);
  if (!Number.isInteger(weeks) || weeks < 1 || weeks > 24) throw new Error('Release duration must be an integer from 1 to 24 weeks');
}
function normalizeInput(input) {
  return {
    assetId: input.assetId || '',
    formulationGoal: input.formulationGoal,
    apis: input.apis.map((a) => {
      const api = typeof a === 'object' ? a : { name: a, doseMg: 1 };
      const doseUnit = api.doseUnit || api.dose_unit || 'mg';
      const doseAmount = Number(api.doseAmount ?? api.dose_amount ?? api.doseMg ?? api.dose_mg ?? 1);
      return { name: String(api.name || a), doseAmount, doseUnit, doseMg: doseAmountToMg(api) };
    }),
    excipients: input.excipients.map((e) => {
      const excipient = typeof e === 'object' ? e : { name: e };
      const amount = Number(excipient.amount ?? excipient.amount_mg ?? excipient.amountMg ?? 1);
      const unit = excipient.unit || 'mg';
      return {
        name: String(excipient.name || e),
        percentage: Number(excipient.percentage || 1),
        amount,
        unit,
        amountMg: unit === 'g' ? amount * 1000 : amount,
      };
    }),
    releaseDurationWeeks: Number(input.releaseDurationWeeks),
    regulatoryBody: input.regulatoryBody,
    routeOfAdministration: input.routeOfAdministration,
    optimizeExcipientPercentages: Boolean(input.optimizeExcipientPercentages),
  };
}
function curve(goal, t, apiIndex) {
  const offset = apiIndex * 0.015;
  if (goal === 'Depot-injection') return 100 * (1 - Math.exp(-2.1 * Math.max(0, t - 0.08))) - 6 + offset * 100;
  if (goal === 'Targeted-delivery') return 100 / (1 + Math.exp(-8 * (t - 0.48 + offset)));
  if (goal === 'Chronotherapeutic') return 18 + (Math.floor(t * 4) * 18) + 12 * Math.sin(t * Math.PI * 6);
  return 100 * (1 - Math.exp(-2.8 * Math.pow(t, 1.25))) + offset * 100;
}
function generateReleaseProfile(input) {
  const labels = Array.from({ length: input.releaseDurationWeeks }, (_, i) => `Week ${i + 1}`);
  const datasets = input.apis.map((api, apiIndex) => {
    let prior = 0;
    const cumulativeRelease = labels.map((_, i) => {
      const t = (i + 1) / input.releaseDurationWeeks;
      prior = clamp(Math.max(prior, curve(input.formulationGoal, t, apiIndex)), 0, 98);
      return prior;
    });
    return { api: api.name, cumulativeRelease };
  });
  return { labels, datasets };
}
function includesExcipient(input, name) { return input.excipients.some(e => e.name.toLowerCase() === name.toLowerCase()); }
function generateChronoTheraScorecard(input, releaseProfile) {
  const asset = assetPresets.find(a => a.id === input.assetId);
  const goalRouteFit = (input.formulationGoal === 'Depot-injection' && ['SC', 'IM'].includes(input.routeOfAdministration)) || (input.formulationGoal === 'Extended-release' && input.routeOfAdministration === 'oral') || (input.formulationGoal === 'Targeted-delivery' && input.routeOfAdministration !== 'IV') || input.formulationGoal === 'Chronotherapeutic';
  const routeCompatibility = clamp(68 + (goalRouteFit ? 16 : -12) + (asset?.suggestedRoutes?.includes(input.routeOfAdministration) ? 10 : 0) - (input.routeOfAdministration === 'IV' ? 18 : 0));
  const excipientCompatibility = clamp(62 + (includesExcipient(input, 'PLGA') && input.formulationGoal === 'Depot-injection' ? 14 : 0) + (includesExcipient(input, 'HPMC') && input.formulationGoal === 'Extended-release' ? 12 : 0) + (includesExcipient(input, 'Eudragit') && input.routeOfAdministration === 'oral' ? 10 : 0) + (includesExcipient(input, 'PEG') ? 6 : 0) - Math.max(0, input.excipients.length - 3) * 4);
  const releaseFeasibility = clamp(70 + (input.releaseDurationWeeks <= 12 ? 8 : -8) + (input.optimizeExcipientPercentages ? 5 : 0) - input.apis.length * 2);
  const pkpdAlignment = clamp(66 + (input.formulationGoal === 'Chronotherapeutic' ? 8 : 0) + (input.apis.length > 1 ? 4 : 0) - (input.releaseDurationWeeks > 16 ? 7 : 0));
  const stabilityRisk = clamp(74 - (input.releaseDurationWeeks > 12 ? 16 : 0) - (input.routeOfAdministration === 'IV' ? 12 : 0) - input.apis.length * 3 + (includesExcipient(input, 'PEG') ? 6 : 0));
  const manufacturability = clamp(72 - input.excipients.length * 2 - (input.releaseDurationWeeks > 18 ? 10 : 0) - (input.routeOfAdministration === 'ocular' ? 6 : 0) + (input.optimizeExcipientPercentages ? 4 : 0));
  const patientCentricity = clamp(69 + (['oral', 'SC'].includes(input.routeOfAdministration) ? 12 : 0) + (input.releaseDurationWeeks >= 4 ? 6 : 0) - (input.routeOfAdministration === 'IV' ? 20 : 0));
  const regulatoryFit = clamp(70 - (input.routeOfAdministration === 'IV' ? 15 : 0) - (input.releaseDurationWeeks > 12 ? 8 : 0) - (asset?.category?.includes('Rapid Response') ? 10 : 0));
  const vals = { releaseFeasibility, routeCompatibility, excipientCompatibility, pkpdAlignment, stabilityRisk, manufacturability, patientCentricity, regulatoryFit };
  return { ...vals, overallChronoTheraScore: clamp(Object.values(vals).reduce((a, b) => a + b, 0) / 8) };
}
function buildGuardianReview(input, scorecard) {
  const asset = assetPresets.find(a => a.id === input.assetId);
  const reasons = [];
  if (scorecard.overallChronoTheraScore < 65) reasons.push('Overall ChronoThera score below threshold');
  if (input.releaseDurationWeeks > 12) reasons.push('Long release duration');
  if (input.routeOfAdministration === 'IV') reasons.push('IV route of administration');
  if (asset?.category?.includes('Rapid Response')) reasons.push('Rapid Response Program');
  if (scorecard.regulatoryFit < 60) reasons.push('Regulatory fit below threshold');
  if (scorecard.stabilityRisk < 60) reasons.push('Stability risk requires review');
  if (scorecard.manufacturability < 60) reasons.push('Manufacturability requires review');
  return { required: reasons.length > 0, status: reasons.length > 0 ? 'pending' : 'not-required', reasons };
}
function runChronoTheraSimulation(rawInput) {
  validateSimulationInput(rawInput);
  const input = normalizeInput(rawInput);
  const releaseProfile = generateReleaseProfile(input);
  const scorecard = generateChronoTheraScorecard(input, releaseProfile);
  const epistemicTrace = buildEpistemicTrace(input, releaseProfile, scorecard);
  const guardianReview = buildGuardianReview(input, scorecard);
  const seed = hashObject(input);
  return { id: `chrono-${seed.slice(0, 12)}`, createdAt: epistemicTrace.provenance.generatedAt, assetId: input.assetId, input, releaseProfile, scorecard, epistemicTrace, guardianReview, disclaimer: DISCLAIMER };
}
module.exports = { runChronoTheraSimulation, validateSimulationInput, generateReleaseProfile, generateChronoTheraScorecard, buildGuardianReview, DISCLAIMER };
