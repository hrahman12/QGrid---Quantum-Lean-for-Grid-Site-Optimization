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
  return CATEGORIES.map(([id, name]) => {
    const evidence = items[id].filter((i) => !i.scenario);
    return { id, name, items: items[id], status: evidence.length ? worst(evidence.map((i) => i.status)) : 'NONE' };
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
  if (edge) out.push({ text: `Phase it: start with ${live.edge.site.requested_mw} MW of small edge sites on local distribution`, to: edge.verdict, note: 'pipeline result for that phase' });
  else if (h.verdict !== 'GREEN') out.push({ text: `Phase it: start with the ${h.firm} MW the grid can guarantee now`, to: 'GREEN', note: 'firm capacity only; needs a rerun' });
  if (live.certificate.checks.some((c) => c.name === 'flex_commitment' && !c.pass))
    out.push({ text: 'Sign the battery / curtailment commitment', to: worst(live.certificate.checks.filter((c) => !c.pass && c.name !== 'flex_commitment').map((c) => (c.tag === 'hard' ? 'RED' : 'AMBER'))), note: 'clears the commitment rule; grid limit remains' });
  const banks = live.edge?.bank_capacity_mw_by_curtailment_pct;
  if (banks) out.push({ text: `Accept 2% curtailment in grid emergencies (local room ${banks['0']} → ${banks['2']} MW)`, to: 'AMBER', note: 'more room, still short of the full request' });
  if (live.risk) {
    const sim = Object.fromEntries((live.risk.mirofish?.scenarios || []).map((s) => [s.scenario, s]));
    const [s0, s1] = [sim.S0_baseline, sim.S1_cba_hiring];
    out.push({ text: 'Community benefit agreement + local hiring', to: 'AMBER',
      note: s0 && s1 ? `simulated opposing groups fall from ${s0.oppose} to ${s1.oppose}` : 'eases the main community concerns' });
    out.push({ text: 'Recycled-water or closed-loop cooling', to: 'AMBER', note: 'answers the high water-stress and city cooling concerns' });
  }
  if (Number.isFinite(h.short) && h.short > 0)
    out.push({ text: `Firm transmission upgrade adding ~${r1(h.short)} MW, finished before ${live.site.deadline}`, to: 'GREEN', note: 'grid rules; upgrade lead time is ASSUMED' });
  return out.slice(0, 6);
}
