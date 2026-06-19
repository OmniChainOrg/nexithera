let catalog;
let latestSimulation;

const $ = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || 'Request failed');
  return data;
}

function option(value, label = value) {
  return `<option value="${value}">${label}</option>`;
}

function checkbox(name, value, checked = false) {
  return `<label><input type="checkbox" name="${name}" value="${value}" ${checked ? 'checked' : ''}/> ${value}</label>`;
}

function selectedValues(name) {
  return [...document.querySelectorAll(`input[name="${name}"]:checked`)].map((input) => input.value);
}

const API_DOSE_UNITS = [
  { value: 'mcg', label: 'micrograms (mcg)' },
  { value: 'mg', label: 'milligrams (mg)' },
  { value: 'g', label: 'grams (g)' },
  { value: 'U', label: 'Units (UI / U)' },
];

function doseUnitOptions(selectedUnit = 'mg') {
  return API_DOSE_UNITS.map((unit) => option(unit.value, unit.label))
    .join('')
    .replace(`value="${selectedUnit}"`, `value="${selectedUnit}" selected`);
}

function doseToMg(amount, unit) {
  const numericAmount = Number(amount);
  if (unit === 'mcg') return numericAmount / 1000;
  if (unit === 'g') return numericAmount * 1000;
  return numericAmount;
}

function fillForm() {
  $('assetId').innerHTML = option('', 'Custom research-use simulation')
    + catalog.assetPresets.map((asset) => option(asset.id, `${asset.label} · ${asset.category}`)).join('');
  $('formulationGoal').innerHTML = catalog.formulationGoals.map((goal) => option(goal)).join('');
  $('regulatoryBody').innerHTML = catalog.regulatoryBodies.map((body) => option(body)).join('');
  $('routeOfAdministration').innerHTML = catalog.routesOfAdministration.map((route) => option(route)).join('');
  $('apiOptions').innerHTML = catalog.apis.map((apiItem, index) => checkbox('apis', apiItem.name, index === 0)).join('');
  $('excipientOptions').innerHTML = catalog.excipients
    .map((excipient, index) => checkbox('excipients', excipient.name, index === 0 || index === 4))
    .join('');
  renderDynamicInputs();
}

function renderDynamicInputs() {
  const apis = selectedValues('apis').slice(0, 5);
  $('apiDoses').innerHTML = apis.map((name) => {
    const defaultDose = catalog.apis.find((apiItem) => apiItem.name === name)?.defaultDoseMg || 1;
    return `
      <div class="dose-row">
        <label>${name} dose
          <input type="number" min="0" step="any" data-api="${name}" value="${defaultDose}"/>
        </label>
        <label>Unit
          <select data-api-unit="${name}">${doseUnitOptions('mg')}</select>
        </label>
      </div>
    `;
  }).join('');

  const excipients = selectedValues('excipients');
  $('excipientPercentages').innerHTML = excipients.map((name) => {
    const defaultPercentage = catalog.excipients.find((excipient) => excipient.name === name)?.defaultPercentage || 5;
    return `<label>${name} %<input type="number" min="0" max="100" step="0.1" data-excipient="${name}" value="${defaultPercentage}"/></label>`;
  }).join('');
}

function applyPreset() {
  const preset = catalog.assetPresets.find((asset) => asset.id === $('assetId').value);
  if (!preset) return;
  [...document.querySelectorAll('input[name="apis"]')].forEach((input) => {
    input.checked = preset.defaultApis?.includes(input.value);
  });
  $('formulationGoal').value = preset.formulationGoals[0];
  $('routeOfAdministration').value = preset.suggestedRoutes[0];
  renderDynamicInputs();
}

function collectInput() {
  const apis = [...document.querySelectorAll('[data-api]')].map((input) => {
    const unit = document.querySelector(`[data-api-unit="${input.dataset.api}"]`)?.value || 'mg';
    const amount = Number(input.value);
    return {
      name: input.dataset.api,
      doseAmount: amount,
      doseUnit: unit,
      doseMg: doseToMg(amount, unit),
    };
  });
  const excipients = [...document.querySelectorAll('[data-excipient]')].map((input) => ({
    name: input.dataset.excipient,
    percentage: Number(input.value),
  }));

  return {
    assetId: $('assetId').value,
    formulationGoal: $('formulationGoal').value,
    apis,
    excipients,
    releaseDurationWeeks: Number($('releaseDurationWeeks').value),
    regulatoryBody: $('regulatoryBody').value,
    routeOfAdministration: $('routeOfAdministration').value,
    optimizeExcipientPercentages: $('optimizeExcipientPercentages').checked,
  };
}

function drawChart(profile) {
  const canvas = $('releaseChart');
  const ctx = canvas.getContext('2d');
  const width = canvas.width;
  const height = canvas.height;
  ctx.clearRect(0, 0, width, height);
  ctx.strokeStyle = 'rgba(148,163,184,.25)';
  ctx.lineWidth = 1;

  for (let index = 0; index <= 4; index += 1) {
    const y = 30 + (index * (height - 60)) / 4;
    ctx.beginPath();
    ctx.moveTo(48, y);
    ctx.lineTo(width - 24, y);
    ctx.stroke();
    ctx.fillStyle = '#94a3b8';
    ctx.fillText(`${100 - index * 25}%`, 10, y + 4);
  }

  const colors = ['#34d399', '#8b5cf6', '#38bdf8', '#f59e0b', '#f472b6'];
  profile.datasets.forEach((dataset, datasetIndex) => {
    ctx.strokeStyle = colors[datasetIndex % colors.length];
    ctx.lineWidth = 3;
    ctx.beginPath();
    dataset.cumulativeRelease.forEach((value, index) => {
      const x = 48 + (index / (profile.labels.length - 1 || 1)) * (width - 80);
      const y = height - 30 - (value / 100) * (height - 70);
      if (index) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
    ctx.fillStyle = colors[datasetIndex % colors.length];
    ctx.fillText(dataset.api, 60, 24 + datasetIndex * 18);
  });
}

function labelize(key) {
  return key.replace(/([A-Z])/g, ' $1').replace(/^./, (letter) => letter.toUpperCase());
}

function scoreValue(score) {
  return typeof score === 'number' ? score : score.score;
}

function scoreDetail(score) {
  if (typeof score === 'number') return '';
  return `<small>${score.rationale}<br/>Next step: ${score.nextBestStep || score.next_best_step}</small>`;
}

function renderSimulation(simulation) {
  latestSimulation = simulation;
  drawChart(simulation.releaseProfile);
  $('scorecard').innerHTML = Object.entries(simulation.scorecard).map(([key, value]) => `
    <div class="score-badge">
      <strong>${scoreValue(value)}</strong>
      <span>${labelize(key)}</span>
      ${scoreDetail(value)}
    </div>
  `).join('');
  $('disclaimer').textContent = simulation.disclaimer;
  $('zones').innerHTML = simulation.epistemicTrace.zones.map((zone) => `<li>${zone}</li>`).join('');
  $('cxus').innerHTML = simulation.epistemicTrace.cxus.map((cxu) => `
    <div class="cxu-card">
      <strong>${cxu.id}</strong>
      <p>${cxu.question}</p>
      <small>Confidence ${Math.round(cxu.confidence * 100)}% · ${cxu.uncertainty.join('; ')}</small>
    </div>
  `).join('');
  $('swarm').innerHTML = `
    <div class="cxu-card">
      <strong>${simulation.epistemicTrace.swarm.id}</strong>
      <p>Mode: ${simulation.epistemicTrace.swarm.mode}</p>
      <p>Consensus score: ${simulation.epistemicTrace.swarm.consensusScore}</p>
    </div>
  `;

  const guardian = simulation.guardianReview;
  $('guardianStatus').classList.toggle('required', guardian.required);
  $('guardianStatus').innerHTML = `<strong>Guardian ${guardian.status}</strong><br>${guardian.required ? guardian.reasons.join('<br>') : 'No Guardian review required by current thresholds.'}`;
  $('exportJson').disabled = false;
  loadHistory();
}

async function loadHistory() {
  const data = await api('/api/chronothera/simulations');
  $('history').innerHTML = (data.simulations || []).slice(0, 8).map((simulation) => `
    <button class="history-item" data-id="${simulation.id}">
      <strong>${simulation.input.apis.map((apiItem) => apiItem.name).join(' + ')}</strong><br>
      <span>${simulation.input.formulationGoal} · ${simulation.scorecard.overallChronoTheraScore}</span>
    </button>
  `).join('') || '<p>No simulations yet.</p>';
}

document.addEventListener('DOMContentLoaded', async () => {
  try {
    catalog = await api('/api/chronothera/catalog');
    fillForm();
    await loadHistory();
  } catch (error) {
    $('form-error').textContent = error.message;
  }

  document.body.addEventListener('change', (event) => {
    if (event.target.name === 'apis') {
      if (selectedValues('apis').length > 5) {
        event.target.checked = false;
        alert('Select up to five APIs.');
      }
      renderDynamicInputs();
    }
    if (event.target.name === 'excipients') renderDynamicInputs();
    if (event.target.id === 'assetId') applyPreset();
  });

  $('simulation-form').addEventListener('submit', async (event) => {
    event.preventDefault();
    $('form-error').textContent = '';
    try {
      const simulation = await api('/api/chronothera/simulations', {
        method: 'POST',
        body: JSON.stringify(collectInput()),
      });
      renderSimulation(simulation);
    } catch (error) {
      $('form-error').textContent = error.message;
    }
  });

  $('history').addEventListener('click', async (event) => {
    const button = event.target.closest('[data-id]');
    if (button) renderSimulation(await api(`/api/chronothera/simulations/${button.dataset.id}`));
  });

  $('exportJson').addEventListener('click', () => {
    const blob = new Blob([JSON.stringify(latestSimulation, null, 2)], { type: 'application/json' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `${latestSimulation.id}.json`;
    link.click();
    URL.revokeObjectURL(link.href);
  });
});
