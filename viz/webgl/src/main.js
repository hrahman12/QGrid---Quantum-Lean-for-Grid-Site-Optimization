import './style.css';
import { DEFAULTS, PRESETS, evaluate, normalize, exportScenario, round } from './model.js';
import { createScene } from './scene.js';

const $ = (selector) => document.querySelector(selector);
const make = (tag, text, className) => { const node = document.createElement(tag); if (text !== undefined) node.textContent = text; if (className) node.className = className; return node; };
let run, scene, settings = { ...DEFAULTS }, result, selected = 'site', stage = 0, playback;
const units = { load: ' MW', growth: '%', utilization: '%', split: '%', storage: ' MW', curtailment: '%', dlr: '%', temperature: '°C', lineLimit: '%', months: ' mo' };
const descriptions = {
  GREEN: ['Connection looks viable', 'All screening conditions pass under the selected assumptions. Inspect the saved certificate for the recorded run.'],
  AMBER: ['Viable, with conditions', 'A path may exist if the outstanding conditions are resolved. Open a check below to see what needs to change.'],
  RED: ['Connection blocked', 'The current scenario exceeds a hard screening limit. Adjust load, routing, or flexibility to find another path.'],
};
const dialog = $('#detail-dialog');
function toast(text) { $('#toast').textContent = text; $('#toast').classList.add('show'); setTimeout(() => $('#toast').classList.remove('show'), 3500); }
function syncForm() {
  for (const [key, value] of Object.entries(settings)) {
    const input = document.getElementById(key);
    if (input.type === 'checkbox') input.checked = value; else input.value = value;
    if (input.type === 'range') {
      input.style.setProperty('--fill', `${(Number(value) - input.min) / (input.max - input.min) * 100}%`);
      input.setAttribute('aria-valuetext', `${value}${units[key] || ''}`);
      document.querySelector(`[data-output="${key}"]`).textContent = `${value}${units[key] || ''}`;
    }
  }
  for (const button of document.querySelectorAll('[data-preset]')) {
    const preset = PRESETS[button.dataset.preset];
    const active = Object.keys(DEFAULTS).every((key) => settings[key] === preset[key]);
    button.classList.toggle('active', active); button.setAttribute('aria-pressed', active);
  }
}
function render() {
  settings = normalize(settings); result = evaluate(settings, run); syncForm();
  $('#verdict').dataset.status = result.status;
  $('#verdict-title').textContent = descriptions[result.status][0];
  $('#verdict-description').textContent = descriptions[result.status][1];
  $('#passed-count').textContent = `${result.checks.filter((c) => c.status === 'GREEN').length} / ${result.checks.length}`;
  $('#mobile-verdict').dataset.status = result.status;
  $('#mobile-verdict').replaceChildren(document.createTextNode(`${result.status} · ${result.checks.filter((c) => c.status === 'GREEN').length} / ${result.checks.length} checks`), make('span', 'View result ↑'));
  $('#metric-demand').textContent = round(result.delivered).toFixed(1);
  $('#metric-loading').textContent = `${round(result.projectedLoading).toFixed(1)}%`;
  $('#metric-loading').style.color = result.projectedLoading > settings.lineLimit ? 'var(--red)' : result.projectedLoading > settings.lineLimit * .9 ? 'var(--amber)' : '';
  $('#metric-routes').textContent = String(result.allocations.filter((a) => a.mw > 0).length).padStart(2, '0');
  $('#metric-distribution').textContent = `${round(result.distribution).toFixed(1)}${result.distributionExtrapolated ? '*' : ''}`;
  $('#metric-distribution').nextElementSibling.textContent = result.distributionExtrapolated ? '* curve capped at 10% curtailment' : 'MW directional screen';
  const openChecks = new Set([...document.querySelectorAll('.check[open]')].map((c) => c.dataset.id));
  $('#checks').replaceChildren(...result.checks.map((check) => {
    const details = make('details', undefined, 'check'); details.dataset.id = check.id; details.dataset.status = check.status; details.open = openChecks.has(check.id);
    const summary = make('summary'); summary.append(make('span', check.status === 'GREEN' ? '✓' : check.status === 'AMBER' ? '!' : '×', 'indicator'), make('span', check.name), make('small', check.status === 'GREEN' ? 'PASS' : check.status === 'AMBER' ? 'IF' : 'BLOCK'));
    details.append(summary, make('p', check.detail)); return details;
  }));
  $('#allocations').replaceChildren(...result.allocations.map((a) => {
    const row = make('div', undefined, 'allocation-row'); row.append(make('span', a.name.replace(' Substation', '').replace(' Station', '')), make('b', `${round(a.mw)} MW${a.offline ? ' · offline' : ''}`)); return row;
  }));
  $('#split-northern').style.width = `${result.allocations[0].share * 100}%`;
  $('#split-esteros').style.width = `${result.allocations[1].share * 100}%`;
  scene?.update(result); updateSelection();
}
function updateSelection() {
  const asset = run.grid_snapshot.substations.find((s) => s.id === selected);
  const allocation = result.allocations.find((a) => a.id === selected);
  $('#asset-name').textContent = asset ? asset.name : 'North San Jose compute site';
  $('#asset-info').textContent = asset ? `${asset.kv} kV · ${asset.distance_km} km from site · ${allocation ? round(allocation.capacity) : asset.headroom_mw} MW ${allocation ? 'scenario' : 'recorded model'} headroom${allocation?.offline ? ' · OFFLINE' : ''}` : `Illustrative site · ${round(result.requested)} MW gross demand · ${run.site.deadline} recorded deadline`;
  for (const button of document.querySelectorAll('[data-asset]')) button.classList.toggle('active', button.dataset.asset === selected);
}
function selectAsset(id) { selected = id; updateSelection(); scene.select(id); }
function showDialog(title, content) { $('#dialog-eyebrow').textContent = title; $('#dialog-content').replaceChildren(...content); dialog.showModal(); }
function showRecord() {
  const heading = make('h2', `Saved certificate: ${run.certificate.result}`);
  heading.style.color = 'var(--green)';
  const text = make('p', `This is the repository's saved 150 MW run from ${run.quantum.generated_utc}. Scenario knobs do not change this evidence.`);
  const rows = run.certificate.checks.map((check) => {
    const row = make('div', undefined, 'certificate-row'); row.append(make('span', check.name.replaceAll('_', ' ')), make('span', check.pass ? 'PASS' : 'FAIL')); row.title = check.detail; return row;
  });
  const metrics = make('p', `Recorded pandapower result: ${run.physics_result.max_line_loading_pct}% maximum loading; ${run.physics_result.v_min_pu}–${run.physics_result.v_max_pu} pu voltage; N-1 ${run.physics_result.n1_pass ? 'pass' : 'fail'}.`);
  const hash = make('code', run.certificate.evidence_sha256);
  const note = make('p', run.certificate.scope_note);
  const download = make('button', '↓ Download saved certificate', 'outline-button'); download.style.marginTop = '18px'; download.onclick = () => downloadJson('qgrid-saved-certificate.json', run.certificate);
  showDialog('RECORDED EVIDENCE / IMMUTABLE', [heading, text, ...rows, make('h3', 'Physics evidence'), metrics, make('h3', 'Evidence SHA-256'), hash, make('h3', 'Certificate scope'), note, download]);
}
function showSources() {
  const header = make('h2', 'What the explorer computes');
  const intro = make('p', 'This is an offline, interactive scenario screen built around the recorded North San Jose / Alviso case. Geometry is geographic; equipment models and proposed connections are visual abstractions. It does not claim new power-flow or formal-proof results.');
  const equations = make('ul');
  for (const text of [
    'Gross demand = requested load × (1 + demand growth). Net grid demand subtracts selected curtailment and assumed battery MW.',
    'Scenario headroom scales the recorded assumed headroom by (100 − utilization) / 35, DLR uplift, a 20% reconductoring factor, and a heat penalty of 0.8% per °C above 25°C.',
    'Thermal loading scales the recorded 71.7% result by net load, the largest route share relative to 75%, utilization, heat, and the selected upgrade factors. This is a sensitivity proxy, not an AC or IEEE 738 calculation.',
    'N-1 uses aggregate remaining headroom after a source outage. It does not solve line contingencies or validate protection and topology.',
    'Assumed delivery times: DLR 12 months, battery 18 months, reconductoring 36 months. ROW, flood protection, and storage commitment toggles are scenario assumptions, not evidence of permits or commitments.',
    'GRIP distribution MW comes from the cached 2028 flexibility curve, linearly interpolated between published scenario points. Above 10% curtailment the display is capped at the last data point.',
    'RED: capacity, thermal, or required N-1 screening fails. AMBER: a near-limit margin or a missing commitment, deadline, permit, mitigation, or curtailment condition. GREEN: all eight screening checks pass.',
  ]) equations.append(make('li', text));
  const sources = make('ul');
  for (const [label, url] of [
    ['Saved pipeline run and Lean evidence', 'https://github.com/hrahman12/QGrid---Quantum-Lean-for-Grid-Site-Optimization/tree/main/docs/demo_run'],
    ['Recorded GRIP flexibility curve and assumptions', 'https://github.com/hrahman12/QGrid---Quantum-Lean-for-Grid-Site-Optimization/blob/main/data/l2/flex_headroom.json'],
    ['OpenStreetMap contributors · ODbL', 'https://www.openstreetmap.org/copyright'],
    ['Terrain Tiles / USGS terrain attribution', 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md'],
    ['Three.js WebGL renderer and controls', 'https://threejs.org/'],
  ]) { const li = make('li'); const a = make('a', label); a.href = url; a.target = '_blank'; a.rel = 'noreferrer'; li.append(a); sources.append(li); }
  showDialog('MODEL / ASSUMPTIONS / SOURCES', [header, intro, make('h3', 'Scenario equations and verdict rules'), equations, make('h3', 'Source data'), sources, make('p', 'The saved grid model includes substations in different utility jurisdictions. Inferred topology and assumed ratings are not an approved PG&E or Silicon Valley Power connection plan. Terrain relief is exaggerated 1.5×; low-elevation water coloring is a heuristic, not a flood map.')]);
}
function downloadJson(filename, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const a = make('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function setStage(value) {
  stage = value;
  for (const button of document.querySelectorAll('[data-stage]')) button.classList.toggle('active', Number(button.dataset.stage) === value);
  const detail = [
    `${run.quantum.space.N} candidate plans · ${run.quantum.space.n_qubits} qubits · ${run.quantum.iterations} Grover iteration in the recorded simulation.`,
    `Recorded pandapower check: ${run.physics_result.max_line_loading_pct}% peak loading · ${run.physics_result.v_min_pu}–${run.physics_result.v_max_pu} pu · N-1 ${run.physics_result.n1_pass ? 'pass' : 'fail'}.`,
    `Saved Lean 4 certificate: ${run.certificate.checks.filter((c) => c.pass).length}/${run.certificate.checks.length} encoded obligations pass. Inspect the certificate for its evidence and assumptions.`,
  ];
  $('#stage-detail').textContent = detail[value];
  const quantum = value === 0;
  scene.quantum(quantum);
  $('#view-quantum').classList.toggle('active', quantum); $('#view-grid').classList.toggle('active', !quantum);
  if (value === 2) toast('Saved result: GREEN · scope limited to encoded rules');
}
async function init() {
  try {
    const fetchJson = async (path) => { const response = await fetch(path); if (!response.ok) throw new Error(`Could not load ${path}`); return response.json(); };
    const geographyPromise = fetchJson(`${import.meta.env.BASE_URL}data/geography.json`);
    run = await fetchJson(`${import.meta.env.BASE_URL}data/run.json`);
    const geography = await geographyPromise;
    scene = createScene($('#viewport'), run, geography, selectAsset);
    $('#asset-list').replaceChildren(...run.grid_snapshot.substations.map((sub) => {
      const button = make('button', sub.name.replace(' Substation', '').replace(' Station', '')); button.dataset.asset = sub.id; button.onclick = () => selectAsset(sub.id); return button;
    }));
    $('#knobs').addEventListener('input', (event) => {
      const input = event.target; if (!(input.name in DEFAULTS)) return;
      settings[input.name] = input.type === 'checkbox' ? input.checked : input.type === 'range' ? Number(input.value) : input.value;
      render();
    });
    for (const button of document.querySelectorAll('[data-preset]')) button.onclick = () => { settings = { ...PRESETS[button.dataset.preset] }; render(); };
    $('#reset').onclick = () => { settings = { ...DEFAULTS }; render(); scene.home(); toast('Baseline restored'); };
    $('#home-camera').onclick = () => scene.home(); $('#top-camera').onclick = () => scene.top();
    $('#rotate-camera').onclick = (event) => { const on = event.currentTarget.getAttribute('aria-pressed') !== 'true'; event.currentTarget.setAttribute('aria-pressed', String(on)); scene.rotate(on); };
    for (const [id, name] of [['terrain-toggle', 'terrain'], ['lines-toggle', 'lines'], ['distribution-toggle', 'distribution']]) {
      $(id.startsWith('#') ? id : `#${id}`).onclick = (event) => { const on = event.currentTarget.getAttribute('aria-pressed') !== 'true'; event.currentTarget.setAttribute('aria-pressed', String(on)); scene.layer(name, on); };
    }
    $('#view-grid').onclick = () => { scene.quantum(false); $('#view-grid').classList.add('active'); $('#view-quantum').classList.remove('active'); };
    $('#view-quantum').onclick = () => { scene.quantum(true); $('#view-quantum').classList.add('active'); $('#view-grid').classList.remove('active'); };
    $('#clear-selection').onclick = () => selectAsset('site');
    $('#sources-button').onclick = showSources; $('#record-button').onclick = showRecord;
    $('#export').onclick = () => { downloadJson('qgrid-scenario.json', exportScenario(settings, run)); toast('Scenario exported'); };
    $('#import').onchange = async (event) => {
      try {
        const file = event.target.files[0]; if (!file) return; if (file.size > 100_000) throw new Error('File too large');
        const data = JSON.parse(await file.text());
        if (data.format !== 'qgrid-scenario-preview/1' || !data.settings || Array.isArray(data.settings)) throw new Error('Not a QGrid scenario');
        settings = normalize(data.settings); render(); toast('Scenario imported');
      } catch { toast('Import a QGrid scenario JSON file under 100 KB.'); }
      event.target.value = '';
    };
    for (const button of document.querySelectorAll('[data-stage]')) button.onclick = () => { clearInterval(playback); playback = undefined; $('#play-run').textContent = '▶ Play walkthrough'; setStage(Number(button.dataset.stage)); };
    $('#play-run').onclick = () => {
      if (playback) { clearInterval(playback); playback = undefined; $('#play-run').textContent = '▶ Play walkthrough'; return; }
      setStage(0); $('#play-run').textContent = 'Ⅱ Pause walkthrough';
      playback = setInterval(() => { if (stage >= 2) { clearInterval(playback); playback = undefined; $('#play-run').textContent = '↺ Replay walkthrough'; return; } setStage(stage + 1); }, 4200);
    };
    render();
  } catch (error) {
    $('#loading').hidden = true; $('#webgl-fallback').hidden = false;
    $('#webgl-fallback').textContent = 'The saved case-study data could not be loaded. Please reload the page or serve the app with npm run dev.';
    $('#render-state').textContent = 'Data loading failed';
    console.error(error);
  }
}
$('#close-dialog').onclick = () => dialog.close();
$('#mobile-verdict').onclick = () => $('.results-panel').scrollIntoView({ behavior: matchMedia('(prefers-reduced-motion: reduce)').matches ? 'instant' : 'smooth' });
dialog.addEventListener('click', (event) => { if (event.target === dialog) { const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close(); } });
addEventListener('pagehide', () => { clearInterval(playback); scene?.dispose(); });
init();
