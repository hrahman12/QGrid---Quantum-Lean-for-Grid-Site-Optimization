// Plain-language live result: pipeline certificate + risk layers -> categories, headline and what-if list.
const RANK = { GREEN: 0, AMBER: 1, RED: 2 };
export const worst = (list) => list.reduce((w, s) => (RANK[s] > RANK[w] ? s : w), 'GREEN');
const CLIMATE = /flood|fire|heat|hot days|temperature|drought|wind|storm|hurricane/i;
const CERT_CATEGORY = { capacity: 'grid', thermal_voltage: 'grid', n1: 'grid', firm_n1: 'grid', bank: 'grid',
  storage_relief: 'grid', evidence_binding: 'grid', permit_row: 'nature', deadline: 'timeline',
  flex_commitment: 'timeline', penalty_trigger: 'timeline' };
const SCENARIO_CATEGORY = { capacity: 'grid', thermal: 'grid', n1: 'grid', flood: 'climate', row: 'nature',
  commitment: 'timeline', deadline: 'timeline', penalty: 'timeline' };
export const CATEGORIES = [
  ['grid', 'Grid capacity'], ['climate', 'Climate risk protection'], ['nature', 'Nature & permits'],
  ['community', 'Community & social'], ['economics', 'Economics'], ['timeline', 'Timeline & commitments'],
];
const label = (s) => s.replaceAll('_', ' ').replace(/^./, (c) => c.toUpperCase());

/** live = { site, candidate_plan, certificate, risk?: risk_layers }; scenarioChecks are the slider screens. */
export function categorize(live, scenarioChecks = []) {
  const items = Object.fromEntries(CATEGORIES.map(([id]) => [id, []]));
  for (const c of live.certificate.checks) {
    items[CERT_CATEGORY[c.name] || 'grid'].push({ name: label(c.name), detail: c.detail,
      status: c.pass ? 'GREEN' : c.tag === 'negotiable' ? 'AMBER' : 'RED', source: 'pipeline' });
  }
  const r = live.risk;
  if (r) {
    for (const i of r.nature.indicators) items[CLIMATE.test(i.name) ? 'climate' : 'nature']
      .push({ name: i.name, detail: `${i.value}${i.unit ? ` ${i.unit}` : ''}`, status: i.rag, source: 'risk layer' });
    items.community.push({ name: 'Local consent score', status: r.consent.verdict, source: 'risk layer',
      detail: `${r.consent.consent_score} (0-1). ${r.consent.verdict_note}` });
    const st = r.social.social_summary.all.by_stance;
    items.community.push({ name: 'Public opposition (news + social posts)', source: 'risk layer',
      status: st.oppose > st.support * 2 ? 'RED' : st.oppose > st.support ? 'AMBER' : 'GREEN',
      detail: `${st.oppose} oppose · ${st.neutral} neutral · ${st.support} support of ${r.social.social_summary.all.n} items.` });
    items.community.push({ name: 'Engagement plan', status: 'AMBER', source: 'risk layer',
      detail: `${r.social.engagement_levers.levers.length} levers identified (e.g. community benefit agreement); none signed yet.` });
    items.economics.push({ name: label(r.socioeconomic.headline), status: r.socioeconomic.overall_rag, source: 'risk layer',
      detail: `${r.socioeconomic.counts.red} red · ${r.socioeconomic.counts.amber} amber · ${r.socioeconomic.counts.green} green local indicators (${r.socioeconomic.county}).` });
  }
  for (const c of scenarioChecks) items[SCENARIO_CATEGORY[c.id] || 'timeline']
    .push({ name: `Scenario screen: ${c.name}`, detail: c.detail, status: c.status, source: 'scenario', scenario: true });
  // Grid and timeline follow the selected scenario's screens; the other four are site data the knobs do not change.
  const follows = (id) => scenarioChecks.length && (id === 'grid' || id === 'timeline');
  return CATEGORIES.map(([id, name]) => {
    const list = follows(id) ? items[id].filter((i) => i.scenario) : items[id];
    const evidence = list.filter((i) => follows(id) || !i.scenario);
    return { id, name, items: list, status: evidence.length ? worst(evidence.map((i) => i.status)) : 'NONE',
      note: scenarioChecks.length && !follows(id) ? 'site data, same in every scenario' : '' };
  });
}

const r1 = (n) => Math.round(n * 10) / 10;
/** Headline numbers and the one-word reason. */
export function headline(live) {
  const cert = live.certificate, requested = live.site.requested_mw;
  const splits = live.candidate_plan.splits;
  const firm = r1(splits.reduce((s, x) => s + Math.max(0, x.headroom_mw_n1_firm ?? x.headroom_mw ?? 0), 0));
  const failed = cert.checks.filter((c) => !c.pass);
  const hard = failed.find((c) => c.tag === 'hard');
  const short = Number(/by ([\d.]+) MW/.exec(cert.blocking_condition || '')?.[1] ?? NaN);
  let phrase, sentence;
  if (cert.result === 'GREEN') { phrase = 'Fits the grid'; sentence = `Every encoded rule passes for ${requested} MW on the nearby substations.`; }
  else if (hard && /n1|capacity|bank/.test(hard.name)) {
    phrase = 'Grid too small';
    sentence = `${splits.every((x) => x.headroom_mw_n1_firm != null) ? 'If one transformer fails, nearby substations can only guarantee' : 'The chosen nearby substations can only offer (assumed ratings)'} about ${firm} MW${Number.isFinite(short) ? `, ${r1(short)} MW short of what the plan needs` : ''}.`;
  } else if (hard) { phrase = label(hard.name); sentence = hard.detail; }
  else { phrase = 'Needs a signed commitment'; sentence = failed.map((c) => c.detail).join(' '); }
  const meaning = cert.result === 'GREEN' ? 'The plan passes the encoded rules; it is still a screen, not a utility approval.'
    : cert.result === 'AMBER' ? 'It can work if the listed conditions are signed.'
      : `It cannot connect ${requested} MW reliably today without the changes below.`;
  const firmKnown = splits.every((x) => x.headroom_mw_n1_firm != null);
  return { verdict: cert.result, requested, firm, short, phrase, sentence, meaning, firmKnown,
    level: firmKnown ? `${firm} MW guaranteed now of ${requested} MW requested`
      : `${firm} MW assumed headroom on the chosen substations for ${requested} MW requested` };
}

/** 3-6 plain conditions, each with the colour it moves to (scope stated in the text). */
export function whatIf(live, h = headline(live)) {
  const out = [];
  const edge = live.edge?.final;
  if (edge) out.push({ text: `Phase it: start with ${live.edge.site.requested_mw} MW of small sites on the local grid (edge sites)`, to: edge.verdict, note: 'pipeline result for that phase' });
  else if (h.verdict !== 'GREEN') out.push({ text: `Phase it: start with the ${h.firm} MW the grid can guarantee now`, to: 'GREEN', note: 'guaranteed capacity only; needs a rerun' });
  if (live.certificate.checks.some((c) => c.name === 'flex_commitment' && !c.pass))
    out.push({ text: 'Sign the battery / pausing-use (curtailment) commitment', to: worst(live.certificate.checks.filter((c) => !c.pass && c.name !== 'flex_commitment').map((c) => (c.tag === 'hard' ? 'RED' : 'AMBER'))), note: 'clears the commitment rule; grid limit remains' });
  const banks = live.edge?.bank_capacity_mw_by_curtailment_pct;
  if (banks) out.push({ text: `Pause use in a few peak hours, about 2% (curtailment) (local room ${banks['0']} → ${banks['2']} MW)`, to: 'AMBER', note: 'more room, still short of the full request' });
  if (live.risk) {
    const sim = Object.fromEntries((live.risk.mirofish?.scenarios || []).map((s) => [s.scenario, s]));
    const [s0, s1] = [sim.S0_baseline, sim.S1_cba_hiring];
    out.push({ text: 'Community benefit agreement + local hiring', to: 'AMBER',
      note: s0 && s1 ? `simulated opposing groups fall from ${s0.oppose} to ${s1.oppose}` : 'eases the main community concerns' });
    out.push({ text: 'Recycled-water or closed-loop cooling', to: 'AMBER', note: 'answers the high water-stress and city cooling concerns' });
  }
  if (Number.isFinite(h.short) && h.short > 0)
    out.push({ text: `Guaranteed transmission upgrade (firm) adding ~${r1(h.short)} MW, finished before ${live.site.deadline}`, to: 'GREEN', note: 'grid rules; upgrade lead time is ASSUMED' });
  return out.slice(0, 6);
}

// ===== Selected scenario -> one verdict for the whole page (headline, why, what-if) =====
import { evaluate, round } from './model.js';
const SCENARIO_REASON = {
  capacity: (r) => ['Not enough grid room', `${round(r.total)} MW of headroom for ${round(r.delivered)} MW from the grid`,
    `The nearby substations have about ${round(r.total)} MW of room in this scenario, less than the ${round(r.delivered)} MW the site would draw.`],
  thermal: (r) => ['Lines overheat', `${round(r.projectedLoading)}% peak line loading vs a ${r.settings.lineLimit}% limit`,
    `At peak the power lines would run at about ${round(r.projectedLoading)}% of their limit, above the ${r.settings.lineLimit}% allowed.`],
  n1: (r) => r.settings.requireN1
    ? ['Grid too small', `${round(r.n1Capacity)} MW guaranteed now of ${round(r.requested)} MW requested${r.delivered < r.requested - 0.05 ? ` (${round(r.delivered)} MW from the grid)` : ''}`,
      `If one transformer fails, the nearby substations can only guarantee about ${round(r.n1Capacity)} MW, and this plan needs ${round(r.delivered)} MW from the grid.`]
    : ['Backup not required (N-1 off)', `${round(r.delivered)} MW from the grid with no single-failure backup`, 'This scenario switches off the rule that the site must stay powered if one transformer fails.'],
  commitment: (r) => ['Needs a signed battery commitment', `${round(r.storage)} MW of battery support not yet committed`,
    `The plan relies on ${round(r.storage)} MW of battery support, but nobody has committed to provide it yet.`],
  deadline: (r) => ['Needs more time', `${r.settings.months} months available, the chosen upgrades need ${r.leadMonths}`,
    `Batteries or line upgrades in this plan take about ${r.leadMonths} months to deliver, but only ${r.settings.months} months are available.`],
  row: () => ['Needs right-of-way permission', 'Line rebuild without right-of-way permission',
    'Rebuilding the lines needs permission to work on the land they cross, which is not secured yet.'],
  flood: () => ['Needs flood protection', 'Flood protection not in place',
    'The site sits in a FEMA flood zone (AE) and the plan has no flood protection yet.'],
  penalty: (r) => ['Too much pausing use', `pausing use ${r.settings.curtailment}% of the time (curtailment) vs a 10% cap`,
    `The plan cuts the site's power ${r.settings.curtailment}% of the time in grid emergencies, above the 10% cap assumed acceptable.`],
};
const flexParts = (s, r) => [r.storage > 0 && `battery ${round(r.storage)} MW`, s.curtailment > 0 && `pausing use ${s.curtailment}% (curtailment)`,
  s.dlr > 0 && `weather-based line rating +${s.dlr}% (DLR)`, s.reconductor && 'stronger wires (reconductoring)'].filter(Boolean);

/** Headline + why sentence for the selected scenario; the scenario verdict is the single displayed verdict. */
export function scenarioHeadline(r) {
  const s = r.settings, passed = r.checks.filter((c) => c.status === 'GREEN').length;
  const first = r.checks.find((c) => c.status === 'RED') || r.checks.find((c) => c.status !== 'GREEN');
  if (!first) {
    const flex = flexParts(s, r);
    const assumes = [...flex, s.storageCommitted && r.storage > 0 && 'the battery commitment signed', s.floodProtected && 'flood protection in place',
      s.reconductor && s.rowPermit && 'right-of-way permission granted'].filter(Boolean);
    return { verdict: 'GREEN', phrase: flex.length ? 'Fits with flexibility' : 'Fits the grid', why: 'Everything fits', passed, first: null,
      level: `${round(r.requested)} MW${flex.length ? ` with ${flex.join(', ')}` : ` within ${round(r.n1Capacity)} MW guaranteed`}`,
      sentence: `All 8 checks pass for ${round(r.requested)} MW${assumes.length ? `, assuming ${assumes.join(', ')}` : ''}.`,
      meaning: 'The plan passes the encoded rules; it is still a screen, not a utility approval.' };
  }
  const [phrase, level, sentence] = SCENARIO_REASON[first.id](r);
  return { verdict: r.status, phrase, why: phrase, level, sentence, passed, first,
    meaning: r.status === 'AMBER' ? 'It can work if the listed conditions are met.' : `It cannot connect ${round(r.requested)} MW reliably without the changes below.` };
}

/** RED/AMBER: levers for the failing checks, each re-evaluated. GREEN: what keeps it green, and what breaks it. */
export function scenarioWhatIf(r, run) {
  const s = r.settings, fail = new Set(r.checks.filter((c) => c.status !== 'GREEN').map((c) => c.id));
  const tryIt = (change) => evaluate({ ...s, ...change }, run);
  const left = (e) => { const f = e.checks.filter((c) => c.status !== 'GREEN'); return f.length ? `still unmet: ${f.map((c) => c.name).join(', ')}` : 'all 8 checks pass'; };
  const items = [];
  if (r.status === 'GREEN') {
    const dep = (cond, text, change) => { if (!cond) return; const e = tryIt(change); if (e.status !== 'GREEN') items.push({ text, to: e.status, if: true, note: `would leave unmet: ${e.checks.filter((c) => c.status !== 'GREEN').map((c) => c.name).join(', ')}` }); };
    dep(r.storage > 0, `Battery support of ${round(r.storage)} MW gets built`, { storage: 0 });
    dep(r.storage > 0 && s.storageCommitted, 'The battery commitment is signed', { storageCommitted: false });
    dep(s.curtailment > 0, `The site accepts pausing use ${s.curtailment}% of the time in grid emergencies (curtailment)`, { curtailment: 0 });
    dep(s.dlr > 0, `Weather-based line rating of +${s.dlr}% (DLR) is installed`, { dlr: 0 });
    dep(s.reconductor && s.rowPermit, 'Right-of-way permission is granted', { rowPermit: false });
    dep(s.floodProtected, 'Flood protection is built', { floodProtected: false });
    dep(r.requested < 150, `The request stays at ${round(r.requested)} MW, not the full 150 MW`, { load: 150, growth: 0 });
    return { title: 'WHAT THIS DEPENDS ON', items: items.slice(0, 6) };
  }
  const lever = (cond, text, change) => { if (cond) { const e = tryIt(change); items.push({ text, to: e.status, note: left(e) }); } };
  const gridFail = fail.has('capacity') || fail.has('thermal') || (fail.has('n1') && s.requireN1);
  const F = { load: 100, storage: 60, curtailment: 10, dlr: 15, split: 50 }; // the Flexible preset's levers
  lever(gridFail, `Phase it: start with the ${round(r.n1Capacity)} MW the grid can guarantee now (firm N-1)`, { load: r.n1Capacity, growth: 0, split: 50 });
  lever(gridFail, `Add flexibility: ${F.storage} MW battery, pausing use ${F.curtailment}% (curtailment), +${F.dlr}% weather-based line rating (DLR)`,
    { storage: Math.max(s.storage, F.storage), curtailment: Math.max(s.curtailment, F.curtailment), dlr: Math.max(s.dlr, F.dlr), split: F.split, months: Math.max(s.months, 18) });
  lever(gridFail && r.requested > F.load, `Shrink to ${F.load} MW and add that flexibility`, { ...F, growth: 0, months: Math.max(s.months, 18) });
  lever(fail.has('capacity') || fail.has('thermal'), 'Upgrade the lines: +30% weather-based rating (DLR) and stronger wires (reconductoring)', { dlr: 30, reconductor: true, rowPermit: true, months: Math.max(s.months, 36) });
  lever(fail.has('commitment'), 'Sign the battery commitment', { storageCommitted: true });
  lever(fail.has('deadline'), `Allow ${r.leadMonths} months instead of ${s.months}`, { months: r.leadMonths });
  lever(fail.has('row'), 'Secure right-of-way permission', { rowPermit: true });
  lever(fail.has('flood'), 'Build flood protection', { floodProtected: true });
  lever(fail.has('penalty'), 'Keep pausing use at or below 10% (curtailment)', { curtailment: 10 });
  lever(fail.has('n1') && !s.requireN1, 'Require single-failure backup again', { requireN1: true });
  return { title: 'WHAT IF', items: items.slice(0, 6) };
}
