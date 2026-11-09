// VM views (proposal): Grover amplitudes, per-qubit Bloch spheres, a photonic-chip
// concept illustration and measurement counts, all driven by a PsiQDK job object
// exactly as viz/webgl/server/search_service.py execute() returns it.
// Every displayed number is a recorded value from the job (or, for Bloch vectors,
// computed in the browser from a recorded statevector). Animation only tweens visuals.
import * as THREE from 'three';

// ---------- pure maths (unit-tested in tests/quantum-views.test.mjs) ----------
// state: array of [re, im], length 2^n. Qubit k is bit k of the basis index (q0 = LSB).
// Returns the single-qubit reduced density matrix of qubit k (partial trace over the rest).
export function reducedDensity(state, k) {
  const mask = 1 << k;
  let r00 = 0, r11 = 0, re01 = 0, im01 = 0;
  for (let i = 0; i < state.length; i++) {
    if (i & mask) continue;
    const [ar, ai] = state[i], [br, bi] = state[i | mask];
    r00 += ar * ar + ai * ai;
    r11 += br * br + bi * bi;
    // rho01 = sum_rest a_{..0..} * conj(a_{..1..})
    re01 += ar * br + ai * bi;
    im01 += ai * br - ar * bi;
  }
  return { r00, r11, re01, im01 };
}
// Bloch vector with the standard convention rho = (I + xX + yY + zZ)/2, so
// rho01 = (x - i y)/2  =>  x = 2 Re rho01, y = -2 Im rho01, z = rho00 - rho11.
export function blochVector(state, k) {
  const { r00, r11, re01, im01 } = reducedDensity(state, k);
  const x = 2 * re01, y = -2 * im01, z = r00 - r11;
  return { x, y, z, r: Math.hypot(x, y, z) };
}
export function blochVectors(state) {
  const n = Math.round(Math.log2(state.length));
  return Array.from({ length: n }, (_, k) => blochVector(state, k));
}
// Per-rail detector clicks for a dual-rail picture: for qubit k, how many shots read 0 / 1.
export function railCounts(measurements, nQubits) {
  const rails = Array.from({ length: nQubits }, () => [0, 0]);
  for (const [key, count] of Object.entries(measurements || {})) {
    const index = Number(key);
    for (let k = 0; k < nQubits; k++) rails[k][(index >> k) & 1] += count;
  }
  return rails;
}
export function groverSteps(job) {
  const r = job.result, steps = [];
  r.states.forEach((vec, it) => {
    steps.push({ vec, iteration: it, phase: false, label: it === 0 ? 'k = 0 · uniform superposition' : `k = ${it} · after ${it} Grover iteration${it > 1 ? 's' : ''}` });
    if (it === 0 && job.phase_state) steps.push({ vec: job.phase_state, iteration: 0, phase: true, label: 'k = 0 · oracle phase flip (marked amplitudes negated)' });
  });
  return steps;
}

// ---------- DOM ----------
const el = (tag, cls, text) => { const n = document.createElement(tag); if (cls) n.className = cls; if (text !== undefined) n.textContent = text; return n; };
const fmt = (v, d = 4) => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(d);
const bin = (i, n) => i.toString(2).padStart(n, '0');
const reduced = typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches;
const css = (name, fallback) => getComputedStyle(document.documentElement).getPropertyValue(name).trim() || fallback;

// recordedJob: the fallback job (public/data/native_job.json); getLiveJob: returns the latest live API job or null.
export function mountQuantumViews(container, { getLiveJob = () => null, recordedJob = null } = {}) {
  container.classList.add('vmq');
  const head = el('div', 'vmq-head');
  const source = el('div', 'vmq-source', 'Loading recorded native PsiQDK run…');
  const tabs = el('div', 'vmq-tabs'); tabs.setAttribute('role', 'tablist');
  const names = [['amp', 'Grover amplitudes'], ['bloch', 'Bloch spheres'], ['photonic', 'Photonic concept'], ['counts', 'Counts']];
  const tabButtons = names.map(([id, label]) => { const b = el('button', '', label); b.dataset.vmTab = id; b.setAttribute('role', 'tab'); tabs.append(b); return b; });
  const stepper = el('div', 'vmq-stepper');
  const prev = el('button', '', '‹'), play = el('button', '', '▶'), next = el('button', '', '›');
  prev.setAttribute('aria-label', 'Previous recorded state'); next.setAttribute('aria-label', 'Next recorded state'); play.setAttribute('aria-label', 'Play recorded states');
  const range = el('input'); range.type = 'range'; range.min = 0; range.step = 1; range.setAttribute('aria-label', 'Recorded Grover step');
  const stepLabel = el('div', 'vmq-steplabel');
  stepper.append(prev, play, range, next);
  head.append(source, tabs, stepper, stepLabel);
  const body = el('div', 'vmq-body');
  const panes = {};
  for (const [id] of names) { panes[id] = el('div', `vmq-pane vmq-${id}`); panes[id].dataset.vmPane = id; body.append(panes[id]); }
  const notes = el('div', 'vmq-notes');
  container.replaceChildren(head, body, notes);

  // --- amplitude pane ---
  const ampCanvas = el('canvas', 'vmq-canvas'); const ampFacts = el('div', 'vmq-facts');
  const pCanvas = el('canvas', 'vmq-spark');
  panes.amp.append(ampCanvas, ampFacts, pCanvas, el('small', 'vmq-caption', 'Bars: real part of each recorded basis-state amplitude (128 = 2^7 states). Highlighted: oracle-marked indices. Dim: padding states beyond the plan list. Curve: recorded p(marked) per iteration.'));
  // --- bloch pane ---
  const blochWrap = el('div', 'vmq-bloch-wrap'); const blochGrid = el('div', 'vmq-bloch-grid');
  const blochCaption = el('small', 'vmq-caption', 'Each arrow is one qubit\'s Bloch vector, from a partial trace of the recorded statevector (computed in the browser). Length 1 = a pure, unentangled qubit; shorter than 1 = that qubit is entangled with (or mixed by) the others.');
  blochWrap.append(blochGrid); panes.bloch.append(blochWrap, blochCaption);
  // --- photonic pane ---
  const photoLabel = el('div', 'vmq-photo-label', 'Photonic-computer concept illustration: the run is a PsiQDK statevector simulation, not photonic hardware');
  const photoCanvas = el('canvas', 'vmq-canvas vmq-photo');
  const photoCaption = el('small', 'vmq-caption', 'Dual-rail picture: each qubit is a pair of waveguides (rail 0 / rail 1). Detector brightness = recorded shots in which that qubit read 0 or 1 (from job.measurements). Waveguide mesh and photon motion are decorative.');
  panes.photonic.append(photoLabel, photoCanvas, photoCaption);
  // --- counts pane ---
  const countsList = el('div', 'vmq-counts'); const cross = el('div', 'vmq-cross'); const planLine = el('div', 'vmq-plan');
  panes.counts.append(countsList, cross, planLine);

  let job = null, steps = [], stepIndex = 0, active = 'amp', playing = null, alive = true, frame = 0, liveRef = null;
  let shown = null, target = null, tweenStart = 0, blochShown = null, blochTarget = null, blochFrom = null, ampFrom = null;
  const TWEEN = reduced ? 1 : 450;

  // three.js Bloch renderer: one WebGL context, one viewport per qubit cell.
  let renderer = null, scene, camera, arrow, nQubits = 0, cells = [];
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setPixelRatio(Math.min(devicePixelRatio, 2)); renderer.setClearColor(0x000000, 0);
    renderer.setScissorTest(true); renderer.domElement.className = 'vmq-bloch-canvas'; blochWrap.prepend(renderer.domElement);
    scene = new THREE.Scene(); camera = new THREE.PerspectiveCamera(30, 1, .1, 20); camera.position.set(2.6, 1.7, 3.4); camera.lookAt(0, 0, 0);
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1, 32, 16), new THREE.MeshBasicMaterial({ color: 0x46d9ec, transparent: true, opacity: .07, depthWrite: false })));
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(1, 16, 8), new THREE.MeshBasicMaterial({ color: 0x3f6f99, wireframe: true, transparent: true, opacity: .22 })));
    const ring = (rot) => { const g = new THREE.BufferGeometry().setFromPoints(Array.from({ length: 65 }, (_, i) => { const a = i / 64 * Math.PI * 2; return new THREE.Vector3(Math.cos(a), 0, Math.sin(a)); })); const l = new THREE.Line(g, new THREE.LineBasicMaterial({ color: 0x6f9cc4 })); l.rotation.set(...rot); scene.add(l); };
    ring([0, 0, 0]); ring([Math.PI / 2, 0, 0]);
    const axis = (v, c) => { const g = new THREE.BufferGeometry().setFromPoints([v.clone().multiplyScalar(-1.15), v.clone().multiplyScalar(1.15)]); scene.add(new THREE.Line(g, new THREE.LineBasicMaterial({ color: c, transparent: true, opacity: .6 }))); };
    // Bloch (x, y, z) -> three (x, z-up as y, y as -z)
    axis(new THREE.Vector3(1, 0, 0), 0xff8a99); axis(new THREE.Vector3(0, 0, -1), 0x8fe3b8); axis(new THREE.Vector3(0, 1, 0), 0x9cc8ff);
    arrow = new THREE.ArrowHelper(new THREE.Vector3(0, 1, 0), new THREE.Vector3(), 1, 0xffbd4c, .22, .12); scene.add(arrow);
  } catch { renderer = null; blochWrap.prepend(el('div', 'vmq-nowebgl', 'WebGL unavailable: Bloch vectors listed below.')); }

  function buildCells() {
    blochGrid.replaceChildren(); cells = [];
    for (let k = nQubits - 1; k >= 0; k--) {
      const c = el('div', 'vmq-cell'); const lab = el('b', '', `q${k}`); const val = el('span', '', '');
      c.append(el('div', 'vmq-cell-space'), lab, val); blochGrid.append(c); cells[k] = { c, val, space: c.firstChild };
    }
  }
  function setStep(i, animate = true) {
    if (!job) return;
    stepIndex = Math.max(0, Math.min(steps.length - 1, i)); range.value = stepIndex;
    const s = steps[stepIndex];
    target = s.vec.map(([re]) => re); ampFrom = shown ? shown.slice() : target.slice();
    blochTarget = blochVectors(s.vec); blochFrom = blochShown ? blochShown.map(v => ({ ...v })) : blochTarget.map(v => ({ ...v }));
    tweenStart = animate ? performance.now() : -1e9;
    const pm = job.result.per_iteration[s.iteration];
    stepLabel.replaceChildren(el('b', '', `Step ${stepIndex + 1}/${steps.length}`), document.createTextNode(` ${s.label}`));
    const marked = job.marked_indices;
    ampFacts.replaceChildren(
      factNode('p(marked)', pm.p_marked.toFixed(4), s.phase ? 'recorded per_iteration[0]; a phase flip leaves probabilities unchanged' : `recorded per_iteration[${s.iteration}]`),
      ...marked.slice(0, 4).map(m => factNode(`amp |${m}⟩`, fmt(s.vec[m][0]), s.phase ? 'from phase_state' : `from result.states[${s.iteration}]`)),
    );
    for (let k = 0; k < nQubits; k++) { const v = blochTarget[k]; if (cells[k]) cells[k].val.textContent = `|r| ${v.r.toFixed(3)} · z ${fmt(v.z, 2)} · x ${fmt(v.x, 2)}`; }
    drawSpark();
  }
  function factNode(name, value, note) { const d = el('div', 'vmq-fact'); d.append(el('span', '', name), el('b', '', value), el('small', '', note)); return d; }
  function fitCanvas(c) {
    const w = c.clientWidth, h = c.clientHeight, dpr = Math.min(devicePixelRatio, 2);
    if (!w || !h) return null;
    if (c.width !== Math.round(w * dpr) || c.height !== Math.round(h * dpr)) { c.width = Math.round(w * dpr); c.height = Math.round(h * dpr); }
    const g = c.getContext('2d'); g.setTransform(dpr, 0, 0, dpr, 0, 0); g.clearRect(0, 0, w, h); return { g, w, h };
  }
  function drawAmp(values) {
    const f = fitCanvas(ampCanvas); if (!f || !values) return; const { g, w, h } = f;
    const N = values.length, plans = job.space?.N ?? N, marked = new Set(job.marked_indices);
    const maxAbs = Math.max(...job.result.states.flat().map(([re]) => Math.abs(re)), ...job.phase_state.map(([re]) => Math.abs(re))) * 1.08;
    const top = 14, mid = h * .62, scaleUp = (mid - top) / maxAbs, scaleDown = (h - 14 - mid) / maxAbs, bw = (w - 8) / N;
    g.fillStyle = '#0d1d2f'; g.fillRect(0, 0, w, h);
    g.strokeStyle = '#3a5b7e'; g.lineWidth = 1; g.beginPath(); g.moveTo(4, mid + .5); g.lineTo(w - 4, mid + .5); g.stroke();
    for (let i = 0; i < N; i++) {
      const v = values[i], x = 4 + i * bw, isM = marked.has(i), pad = i >= plans;
      g.fillStyle = isM ? (v < 0 ? '#fa7081' : '#ffbd4c') : pad ? '#2a3d52' : '#46d9ec';
      if (!isM && !pad) g.globalAlpha = .75;
      const hgt = v >= 0 ? v * scaleUp : -v * scaleDown;
      g.fillRect(x + bw * .12, v >= 0 ? mid - hgt : mid, Math.max(1, bw * .76), Math.max(isM ? 1.5 : .5, hgt));
      g.globalAlpha = 1;
    }
    g.font = '600 10px "DM Sans",system-ui,sans-serif'; g.fillStyle = '#ffbd4c';
    for (const m of job.marked_indices) { const x = 4 + (m + .5) * bw, v = values[m]; g.textAlign = 'center'; g.fillText(`|${m}⟩`, Math.min(w - 14, Math.max(14, x)), v >= 0 ? Math.max(11, mid - v * scaleUp - 4) : Math.min(h - 3, mid - v * scaleDown + 11)); }
    g.textAlign = 'left'; g.fillStyle = '#8ca5c3'; g.font = '9px "DM Sans",system-ui,sans-serif';
    g.fillText('0', 4, h - 3); g.textAlign = 'right'; g.fillText(`${N - 1}`, w - 4, h - 3);
    g.textAlign = 'left'; g.fillText('Re(amplitude) +', 6, 10); g.fillText('−', 6, mid + 11);
  }
  function drawSpark() {
    const f = fitCanvas(pCanvas); if (!f || !job) return; const { g, w, h } = f;
    const pts = job.result.per_iteration, n = pts.length, x = i => 26 + i * (w - 40) / Math.max(1, n - 1), y = p => h - 12 - p * (h - 20);
    g.strokeStyle = '#294565'; g.beginPath(); g.moveTo(26, y(0)); g.lineTo(w - 14, y(0)); g.moveTo(26, y(1)); g.lineTo(w - 14, y(1)); g.stroke();
    g.fillStyle = '#8ca5c3'; g.font = '9px "DM Sans",system-ui,sans-serif'; g.textAlign = 'right'; g.fillText('1', 22, y(1) + 3); g.fillText('0', 22, y(0) + 3);
    g.strokeStyle = '#47dca2'; g.lineWidth = 1.5; g.beginPath(); pts.forEach((p, i) => (i ? g.lineTo : g.moveTo).call(g, x(i), y(p.p_marked))); g.stroke();
    const cur = steps[stepIndex].iteration;
    pts.forEach((p, i) => { g.fillStyle = i === cur ? '#ffbd4c' : '#47dca2'; g.beginPath(); g.arc(x(i), y(p.p_marked), i === cur ? 4 : 2.5, 0, 7); g.fill(); });
    g.textAlign = 'center'; g.fillStyle = '#8ca5c3'; pts.forEach((p, i) => g.fillText(`k${p.iteration}`, x(i), h - 1));
  }
  function drawBloch(vs) {
    if (!renderer || !vs) return;
    const canvas = renderer.domElement, rect = blochWrap.getBoundingClientRect();
    if (!rect.width || !rect.height) return;
    renderer.setSize(rect.width, rect.height, false); canvas.style.width = `${rect.width}px`; canvas.style.height = `${rect.height}px`;
    renderer.setScissor(0, 0, rect.width, rect.height); renderer.setViewport(0, 0, rect.width, rect.height); renderer.clear();
    for (let k = 0; k < nQubits; k++) {
      const cell = cells[k]; if (!cell) continue; const r = cell.space.getBoundingClientRect();
      const x = r.left - rect.left, yb = rect.bottom - r.bottom, s = Math.min(r.width, r.height); if (s < 8) continue;
      const vx = x + (r.width - s) / 2; renderer.setViewport(vx, yb, s, s); renderer.setScissor(vx, yb, s, s);
      const v = vs[k], len = v.r;
      const dir = new THREE.Vector3(v.x, v.z, -v.y);
      if (len > 1e-6) { arrow.visible = true; arrow.setDirection(dir.normalize()); arrow.setLength(Math.max(len, .05), Math.min(.22, len * .4 + .02), Math.min(.12, len * .25 + .02)); } else arrow.visible = false;
      arrow.setColor(len > .98 ? 0x47dca2 : 0xffbd4c);
      renderer.render(scene, camera);
    }
  }
  // photonic concept (decorative layout; detector brightness from recorded measurements)
  function drawPhoto(t) {
    const f = fitCanvas(photoCanvas); if (!f || !job) return; const { g, w, h } = f;
    const n = nQubits, rails = 2 * n, shots = job.result.shots, counts = railCounts(job.measurements, n);
    g.fillStyle = '#0a1828'; g.beginPath(); g.roundRect(2, 2, w - 4, h - 4, 10); g.fill(); g.strokeStyle = '#2c4d76'; g.stroke();
    const x0 = 30, x1 = w - 74, yTop = 16, gap = (h - 32) / (rails - 1), ry = r => yTop + r * gap;
    // waveguides
    g.lineWidth = 1.4;
    for (let r = 0; r < rails; r++) { g.strokeStyle = r % 2 ? '#2f6f8f' : '#2a5878'; g.beginPath(); g.moveTo(x0, ry(r)); g.lineTo(x1, ry(r)); g.stroke(); }
    // MZI mesh: directional couplers between neighbouring rails, brick pattern
    const cols = Math.max(4, Math.floor((x1 - x0 - 30) / 34));
    for (let c = 0; c < cols; c++) {
      const cx = x0 + 22 + c * (x1 - x0 - 44) / Math.max(1, cols - 1);
      for (let r = c % 2; r < rails - 1; r += 2) {
        const a = ry(r), b = ry(r + 1), m = (a + b) / 2;
        g.strokeStyle = '#46d9ec'; g.globalAlpha = .55; g.beginPath();
        g.moveTo(cx - 10, a); g.bezierCurveTo(cx - 4, a, cx - 4, m - 1.5, cx, m - 1.5); g.bezierCurveTo(cx + 4, m - 1.5, cx + 4, a, cx + 10, a);
        g.moveTo(cx - 10, b); g.bezierCurveTo(cx - 4, b, cx - 4, m + 1.5, cx, m + 1.5); g.bezierCurveTo(cx + 4, m + 1.5, cx + 4, b, cx + 10, b); g.stroke();
        g.globalAlpha = 1; g.fillStyle = '#c3954b'; g.fillRect(cx + 12, a - 2, 5, 3);
      }
    }
    // sources
    for (let r = 0; r < rails; r++) { g.fillStyle = '#4c94ff'; g.beginPath(); g.arc(x0 - 8, ry(r), 3, 0, 7); g.fill(); }
    // photons
    if (!reduced) {
      for (let r = 0; r < rails; r++) {
        const frac = counts[r >> 1][r & 1] / shots;
        for (let p = 0; p < 3; p++) {
          const u = ((t / 2600) + p / 3 + r * .137) % 1, x = x0 + u * (x1 - x0);
          const a = u < .25 ? .9 : .9 * (.25 + .75 * frac); g.globalAlpha = a; g.fillStyle = '#c9fbff';
          g.beginPath(); g.arc(x, ry(r), 2.2, 0, 7); g.fill();
        }
      }
      g.globalAlpha = 1;
    }
    // detectors
    g.font = '600 9px "DM Sans",system-ui,sans-serif'; g.textAlign = 'left';
    for (let r = 0; r < rails; r++) {
      const k = r >> 1, bit = r & 1, c = counts[k][bit], frac = c / shots, y = ry(r);
      const grad = g.createRadialGradient(x1 + 10, y, 0, x1 + 10, y, 7 + 9 * frac);
      grad.addColorStop(0, `rgba(255,214,120,${.15 + .85 * frac})`); grad.addColorStop(1, 'rgba(255,189,76,0)');
      g.fillStyle = grad; g.beginPath(); g.arc(x1 + 10, y, 7 + 9 * frac, 0, 7); g.fill();
      g.fillStyle = frac > 0 ? '#ffd27a' : '#33465c'; g.fillRect(x1 + 6, y - Math.min(4, gap / 2 - .5), 8, Math.min(8, gap - 1));
      g.fillStyle = frac > 0 ? '#e6eef9' : '#6d86a3'; g.fillText(`q${k}=${bit} ${c}/${shots}`, x1 + 20, y + 3);
    }
  }
  function renderCounts() {
    const n = nQubits, shots = job.result.shots, marked = new Set(job.marked_indices);
    const rows = Object.entries(job.measurements).map(([k, c]) => [Number(k), c]).sort((a, b) => b[1] - a[1]);
    const max = Math.max(1, ...rows.map(r => r[1]));
    countsList.replaceChildren(el('div', 'vmq-counts-head', `job.measurements · ${shots} shots · ${job.result.samples_marked}/${shots} hit a marked index`),
      ...rows.map(([i, c]) => { const row = el('div', 'vmq-count'); row.dataset.index = i; const bar = el('i'); bar.style.width = `${c / max * 100}%`; if (marked.has(i)) row.classList.add('marked');
        row.append(el('span', '', `|${i}⟩`), el('code', '', bin(i, n)), el('div', 'vmq-bar'), el('b', '', String(c))); row.children[2].append(bar); return row; }),
      el('small', 'vmq-caption', `${(job.space?.padded_N ?? 2 ** n) - rows.length} other basis states: 0 counts. Bit string shown q${n - 1}…q0.`));
    const r = job.result, diffs = r.numpy_crosscheck_max_abs_diff_per_iteration || [], maxDiff = diffs.length ? Math.max(...diffs) : null;
    cross.dataset.ok = String(!!r.numpy_crosscheck_ok);
    cross.replaceChildren(el('b', '', r.numpy_crosscheck_ok ? `✓ Numerical cross-check passed (max diff ${maxDiff?.toExponential(1) ?? 'n/a'})` : '× Numerical cross-check did not pass'),
      el('small', '', `Independent NumPy statevector vs PsiQDK, per iteration: ${diffs.map((d, i) => `k${i} ${d.toExponential(1)}`).join(' · ')}`));
    const plan = job.plan; const subs = Object.fromEntries((job.space?.candidate_substations || []).map(s => [s.id, s.name]));
    planLine.textContent = plan ? `Selected measured candidate: ${plan.splits.map(s => `${subs[s.substation_id] || s.substation_id} ${s.mw} MW`).join(' + ')} · storage ${plan.flex.storage_mw} MW · curtailment ${plan.flex.curtailment_mw} MW. ${job.status}` : 'No feasible candidate was measured.';
  }
  function setJob(value, kind) {
    if (!value?.result?.states?.length) return;
    job = value; steps = groverSteps(job); nQubits = job.space?.n_qubits ?? Math.round(Math.log2(job.result.states[0].length));
    const when = (job.completed_utc || '').replace(/\.\d+/, '').replace('+00:00', 'Z');
    source.replaceChildren(el('span', `vmq-badge ${kind}`, kind === 'live' ? 'LIVE PsiQDK RUN' : 'RECORDED NATIVE PsiQDK RUN'),
      document.createTextNode(` job ${job.job_id.slice(0, 8)} · completed ${when} · ${nQubits} qubits · ${job.result.iterations} iterations · psiqdk ${job.result.versions?.psiqdk ?? '?'}`));
    if (kind !== 'live') source.append(el('small', '', ` Settings: load ${job.input_settings.load} MW, storage ${job.input_settings.storage}, curtailment ${job.input_settings.curtailment}%, DLR ${job.input_settings.dlr}%. Shown until a live run returns.`));
    range.max = steps.length - 1; shown = null; blochShown = null; buildCells(); renderCounts();
    notes.replaceChildren(...[job.scope, job.result.simulation_note].filter(Boolean).map(t => el('small', '', t)));
    setStep(Math.min(stepIndex, steps.length - 1), false);
  }
  function setTab(id) {
    active = id; for (const b of tabButtons) { const on = b.dataset.vmTab === id; b.classList.toggle('active', on); b.setAttribute('aria-selected', String(on)); }
    for (const [k, p] of Object.entries(panes)) p.hidden = k !== id;
    stepper.hidden = stepLabel.hidden = !(id === 'amp' || id === 'bloch');
    if (job) { if (id === 'counts') renderCounts(); setStep(stepIndex, false); }
  }
  function stopPlay() { clearInterval(playing); playing = null; play.textContent = '▶'; }
  tabButtons.forEach(b => b.onclick = () => setTab(b.dataset.vmTab));
  prev.onclick = () => { stopPlay(); setStep(stepIndex - 1); }; next.onclick = () => { stopPlay(); setStep(stepIndex + 1); };
  range.oninput = () => { stopPlay(); setStep(Number(range.value)); };
  play.onclick = () => { if (playing) return stopPlay(); if (stepIndex >= steps.length - 1) setStep(0); play.textContent = '❚❚'; playing = setInterval(() => { if (stepIndex >= steps.length - 1) return stopPlay(); setStep(stepIndex + 1); }, 1100); };
  setTab('amp');

  const ease = u => u < 0 ? 0 : u > 1 ? 1 : 1 - (1 - u) ** 3;
  function loop(t) {
    if (!alive) return; frame = requestAnimationFrame(loop);
    const live = getLiveJob(); if (live && live !== liveRef) { liveRef = live; setJob(live, 'live'); }
    if (!job || container.offsetParent === null) return;
    const u = ease((t - tweenStart) / TWEEN);
    if (target) { shown = target.map((v, i) => ampFrom[i] + (v - ampFrom[i]) * u); }
    if (blochTarget) blochShown = blochTarget.map((v, i) => { const a = blochFrom[i]; const x = a.x + (v.x - a.x) * u, y = a.y + (v.y - a.y) * u, z = a.z + (v.z - a.z) * u; return { x, y, z, r: Math.hypot(x, y, z) }; });
    if (active === 'amp') drawAmp(shown);
    else if (active === 'bloch') drawBloch(blochShown);
    else if (active === 'photonic') drawPhoto(t);
  }
  frame = requestAnimationFrame(loop);
  if (recordedJob) setJob(recordedJob, 'recorded'); else source.textContent = 'Recorded native PsiQDK run unavailable; run PsiQDK to populate these views.';
  return {
    setJob, setStep: i => setStep(i, false), setTab,
    get state() { return job && { stepIndex, steps: steps.length, step: steps[stepIndex], bloch: blochVectors(steps[stepIndex].vec), source: liveRef ? 'live' : 'recorded' }; },
    dispose() { alive = false; cancelAnimationFrame(frame); stopPlay(); renderer?.dispose(); container.replaceChildren(); },
  };
}
