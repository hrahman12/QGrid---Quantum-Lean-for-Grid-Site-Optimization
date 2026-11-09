export const DEFAULTS = Object.freeze({
  load: 150, growth: 0, utilization: 65, split: 75, storage: 0,
  curtailment: 0, dlr: 0, temperature: 25, lineLimit: 100,
  months: 20, reconductor: false, rowPermit: false, floodProtected: true,
  storageCommitted: true, requireN1: true, outage: 'none',
});
export const PRESETS = {
  baseline: { ...DEFAULTS },
  flexible: { ...DEFAULTS, load: 100, split: 50, storage: 60, curtailment: 10, dlr: 15, months: 24 },
  conditional: { ...DEFAULTS, load: 100, split: 50, storage: 60, curtailment: 10, months: 6 },
  stressed: { ...DEFAULTS, load: 350, utilization: 88, temperature: 42, growth: 20 },
};
const BOUNDS = { load: [25, 500], growth: [0, 50], utilization: [40, 95], split: [0, 100],
  storage: [0, 100], curtailment: [0, 20], dlr: [0, 30], temperature: [10, 50],
  lineLimit: [60, 100], months: [0, 60] };
export function normalize(input = {}) {
  const result = { ...DEFAULTS };
  for (const [key, [lo, hi]] of Object.entries(BOUNDS)) {
    const value = Number(input[key]);
    if (input[key] !== undefined && Number.isFinite(value)) result[key] = Math.min(hi, Math.max(lo, value));
  }
  for (const key of ['reconductor', 'rowPermit', 'floodProtected', 'storageCommitted', 'requireN1']) {
    if (typeof input[key] === 'boolean') result[key] = input[key];
  }
  if (['none', 'northern', 'esteros'].includes(input.outage)) result.outage = input.outage;
  return result;
}
export const round = (n, decimals = 1) => Number(n.toFixed(decimals));
export function screeningStatus(checks) {
  // Same as the Lean rules: any hard-rule failure is RED; only negotiable conditions unmet is AMBER.
  return checks.some(c => c.status === 'RED') ? 'RED' : checks.some(c => c.status !== 'GREEN') ? 'AMBER' : 'GREEN';
}
export function evaluate(input, run) {
  const s = normalize(input);
  const selected = run.candidate_plan.splits.map((split) => ({
    ...run.grid_snapshot.substations.find((sub) => sub.id === split.substation_id),
    recorded_mw: split.mw,
  }));
  const requested = s.load * (1 + s.growth / 100);
  const curtailed = requested * s.curtailment / 100;
  const storage = Math.min(s.storage, requested - curtailed);
  const delivered = Math.max(0, requested - curtailed - storage);
  const upgrade = s.reconductor ? 1.2 : 1;
  const heat = Math.max(0, s.temperature - 25) * 0.008;
  const shares = [s.split / 100, 1 - s.split / 100];
  if (s.outage === 'northern') { shares[0] = 0; shares[1] = 1; }
  if (s.outage === 'esteros') { shares[0] = 1; shares[1] = 0; }
  const allocations = selected.map((sub, i) => {
    const offline = (i === 0 && s.outage === 'northern') || (i === 1 && s.outage === 'esteros');
    const capacity = offline ? 0 : sub.headroom_mw * ((100 - s.utilization) / 35) * (1 + s.dlr / 100) * upgrade / (1 + heat);
    return { ...sub, capacity, mw: delivered * shares[i], offline, share: shares[i] };
  });
  const total = allocations.reduce((a, b) => a + b.capacity, 0);
  const minMargin = Math.min(...allocations.filter((a) => !a.offline).map((a) => a.capacity - a.mw));
  const worstShare = Math.max(...shares) / 0.75;
  const projectedLoading = run.physics_result.max_line_loading_pct * delivered / 150 * worstShare *
    (1 + heat) * (s.utilization / 65) / ((1 + s.dlr / 100) * upgrade);
  const leadMonths = Math.max(s.storage > 0 ? 18 : 0, s.dlr > 0 ? 12 : 0, s.reconductor ? 36 : 0);
  const n1Capacity = allocations.reduce((sum, a) => sum + (a.offline ? 0 : Math.max(0, a.headroom_mw_n1_firm ?? 0)), 0);
  const n1Overload = allocations.find((a) => a.mw > (a.offline ? 0 : Math.max(0, a.headroom_mw_n1_firm ?? 0)) + .001);
  const checks = [];
  const add = (id, name, status, detail) => checks.push({ id, name, status, detail });
  const overload = allocations.find((a) => a.mw > a.capacity + 0.001);
  add('capacity', 'Connection capacity', overload ? 'RED' : minMargin < delivered * 0.1 ? 'AMBER' : 'GREEN',
    overload ? `${overload.name}: ${round(overload.mw)} MW allocated exceeds ${round(overload.capacity)} MW scenario headroom.`
      : `${round(delivered)} MW net grid demand; smallest route margin ${round(minMargin)} MW.`);
  add('thermal', 'Thermal screen', projectedLoading > s.lineLimit ? 'RED' : projectedLoading > s.lineLimit * 0.9 ? 'AMBER' : 'GREEN',
    `Estimated peak loading ${round(projectedLoading)}% against a ${s.lineLimit}% limit. Analytical proxy, not AC power flow.`);
  add('n1', 'Firm N-1 capacity', !s.requireN1 ? 'AMBER' : n1Overload ? 'RED' : 'GREEN',
    !s.requireN1 ? 'Single-outage resilience is not required in this scenario.' : n1Overload ? `${n1Overload.name}: ${round(n1Overload.mw)} MW exceeds its ${round(n1Overload.headroom_mw_n1_firm || 0)} MW firm cap. DLR and reconductoring do not raise firm transformer caps.` : `${round(delivered)} MW net demand fits the individual firm caps (${round(n1Capacity)} MW combined). Network topology is not solved.`);
  add('commitment', 'Storage commitment', storage > 0 && !s.storageCommitted ? 'AMBER' : 'GREEN',
    storage > 0 ? `${round(storage)} MW storage assumed available at the critical hour${s.storageCommitted ? ' and committed in this scenario' : '; commitment is still needed'}. Energy duration is not modelled.` : 'No battery support required in this scenario.');
  add('deadline', 'Delivery deadline', s.months < leadMonths ? 'AMBER' : 'GREEN',
    `${s.months} months available; selected upgrades have an assumed ${leadMonths}-month lead time.`);
  add('row', 'Permit / right-of-way', s.reconductor && !s.rowPermit ? 'AMBER' : 'GREEN',
    s.reconductor ? (s.rowPermit ? 'ROW permission is assumed granted for this scenario.' : 'Reconductoring needs the assumed ROW permission.') : 'No reconductoring selected; this screen adds no ROW requirement.');
  add('flood', 'Flood mitigation', s.floodProtected ? 'GREEN' : 'AMBER',
    s.floodProtected ? 'Protection is assumed in this scenario for the recorded FEMA AE flood-zone context.' : 'Flood-zone AE mitigation evidence is still needed.');
  add('penalty', 'Curtailment obligation', s.curtailment > 10 ? 'AMBER' : 'GREEN',
    `${s.curtailment}% curtailment selected; the screening penalty cap is assumed at 10%.`);
  const status = screeningStatus(checks);
  const blocking = checks.filter((c) => c.status !== 'GREEN');
  const isBaseline = Object.keys(DEFAULTS).every((key) => s[key] === DEFAULTS[key]);
  const curve = run.flexibility.curve;
  const lower = [...curve].reverse().find((p) => p.curtailment_pct <= s.curtailment) || curve[0];
  const upper = curve.find((p) => p.curtailment_pct >= s.curtailment) || curve.at(-1);
  const t = upper.curtailment_pct === lower.curtailment_pct ? 0 : (s.curtailment - lower.curtailment_pct) / (upper.curtailment_pct - lower.curtailment_pct);
  const distribution = lower.distribution_mw + (upper.distribution_mw - lower.distribution_mw) * t;
  return { settings: s, status, checks, blocking, requested, curtailed, storage, delivered,
    allocations, total, projectedLoading, minMargin, leadMonths, isBaseline,
    distribution, n1Capacity, distributionExtrapolated: s.curtailment > curve.at(-1).curtailment_pct };
}
export function exportScenario(input, run) {
  return { format: 'qgrid-scenario-preview/1', settings: normalize(input), evaluation: evaluate(input, run),
    scope: 'Browser screening only. Not a pandapower result, quantum run, Lean certificate, or utility approval.',
    recorded_evidence_sha256: run.certificate.evidence_sha256 };
}
