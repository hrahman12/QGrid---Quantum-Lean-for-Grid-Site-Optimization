// Card 3 grid-physics views: firm N-1 per candidate substation, peak line loading, voltage band,
// and the "one transformer fails" callout, all read from the recorded pandapower run in run.json.
// Pure DOM (no three, no CSS import) so node --test can import gridFacts.

const LOADING_LIMIT_PCT = 100, V_LO = 0.95, V_HI = 1.05; // match certificate scope_note defaults

export function gridFacts(run) {
  const cr = run.current_run ?? run;
  const snap = cr.grid_snapshot ?? run.grid_snapshot ?? { substations: [] };
  const pr = cr.physics_result, cert = cr.certificate;
  const nameOf = id => snap.substations.find(s => s.id === id)?.name ?? id;
  const netKw = Object.fromEntries((cert?.evidence?.splits ?? []).map(s => [s.substation_id, s.net_kw]));
  const subs = cr.candidate_plan.splits.map(s => {
    const net = netKw[s.substation_id] != null ? netKw[s.substation_id] / 1000 : s.mw;
    return { id: s.substation_id, name: nameOf(s.substation_id), mw: s.mw, netMw: net, firmMw: s.headroom_mw_n1_firm, status: net > s.headroom_mw_n1_firm ? 'RED' : 'GREEN' };
  });
  const firmCheck = cert?.checks?.find(c => c.name === 'firm_n1');
  const m = firmCheck?.detail?.match(/by ([\d.]+) MW/);
  const shortfallMw = m ? Number(m[1]) : Math.max(0, subs.reduce((a, s) => a + s.netMw - s.firmMw, 0));
  const xf = pr.violations?.[0]?.match(/transformer XF-(\S+)/)?.[1];
  return {
    subs,
    loading: { pct: pr.max_line_loading_pct, limit: LOADING_LIMIT_PCT, status: pr.max_line_loading_pct <= LOADING_LIMIT_PCT ? 'GREEN' : 'RED' },
    voltage: { min: pr.v_min_pu, max: pr.v_max_pu, lo: V_LO, hi: V_HI, status: pr.v_min_pu >= V_LO && pr.v_max_pu <= V_HI ? 'GREEN' : 'RED' },
    outage: { n1Pass: pr.n1_pass, failing: xf ? nameOf(xf) : null, others: subs.filter(s => s.id !== xf).map(s => s.name), shortfallMw: firmCheck?.pass ? 0 : shortfallMw },
  };
}

const el = (tag, cls = '', text = '') => { const n = document.createElement(tag); if (cls) n.className = cls; if (text) n.textContent = text; return n; };
const fmt = n => `${Number(n.toFixed(1))} MW`;

export function mountGridViews(host, f) {
  host.classList.add('gv');
  host.append(el('p', 'gv-lead', 'We simulate the real local grid, including what happens if one transformer fails.'));
  host.append(el('div', 'gv-source', 'Recorded pandapower run (live snapshot) · the preview below re-estimates as you move the knobs'));

  const diagram = el('div', 'gv-line'); diagram.setAttribute('role', 'list'); diagram.setAttribute('aria-label', 'Candidate substations: planned MW vs firm N-1 headroom');
  diagram.append(el('div', 'gv-site', 'SITE'));
  for (const s of f.subs) {
    const node = el('div', 'gv-sub'); node.dataset.status = s.status; node.setAttribute('role', 'listitem');
    node.append(el('b', '', s.name), el('span', 'gv-plan', `${fmt(s.mw)} planned`), el('small', '', `${fmt(s.netMw)} net vs ${fmt(s.firmMw)} firm N-1`));
    const bar = el('div', 'gv-bar'), max = Math.max(s.netMw, s.firmMw) || 1;
    const need = el('i'); need.style.width = `${(s.netMw / max) * 100}%`;
    const firm = el('span'); firm.style.left = `${(s.firmMw / max) * 100}%`; firm.title = 'firm N-1 headroom';
    bar.append(need, firm); node.append(bar);
    diagram.append(el('i', 'gv-wire'), node);
  }
  host.append(diagram);

  const meter = (label, value, status, left, width, ticks) => {
    const row = el('div', 'gv-meter'); row.dataset.status = status;
    const head = el('div', 'gv-meter-head'); head.append(el('span', '', label), el('b', '', value));
    const track = el('div', 'gv-track'), bar = el('i');
    bar.style.left = `${left}%`; bar.style.width = `${width}%`; track.append(bar);
    for (const at of ticks) { const t = el('span'); t.style.left = `${at}%`; track.append(t); }
    row.append(head, track); return row;
  };
  const L = f.loading, V = f.voltage, vPos = v => ((v - V.lo) / (V.hi - V.lo)) * 100;
  host.append(meter('Peak line loading', `${L.pct}% of ${L.limit}% limit`, L.status, 0, Math.min(100, L.pct), [100]));
  host.append(meter('Voltage band', `${V.min.toFixed(2)}–${V.max.toFixed(2)} pu (allowed ${V.lo}–${V.hi})`, V.status, vPos(V.min), vPos(V.max) - vPos(V.min), [0, 100]));

  const o = f.outage, call = el('div', 'gv-outage'); call.dataset.status = o.n1Pass ? 'GREEN' : 'RED';
  call.append(el('b', '', 'If one transformer fails'));
  call.append(el('p', '', o.n1Pass || !o.failing
    ? 'Losing any single transformer still leaves enough firm capacity for the plan.'
    : `If the largest transformer at ${o.failing} fails${o.others.length ? ` (the same holds at ${o.others.join(', ')})` : ''}, each substation can only firmly carry ${fmt(f.subs[0].firmMw)}. Together the plan is ${fmt(o.shortfallMw)} short.`));
  host.append(call);
  return host;
}
