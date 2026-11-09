import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { PRESETS, evaluate } from '../src/model.js';
import { categorize, scenarioHeadline, scenarioWhatIf } from '../src/outcome.js';
const run = JSON.parse(await readFile(new URL('../public/data/run.json', import.meta.url)));
const live = { ...run.current_run, risk: run.risk_layers, edge: run.scenarios.edge };
// The page shows one verdict: flow PROVE box, OUT headline, Why panel and card-4 stage output all read these values.
const page = (preset) => {
  const r = evaluate(PRESETS[preset], run), h = scenarioHeadline(r), cats = categorize(live, r.checks);
  return { r, h, w: scenarioWhatIf(r, run), cat: Object.fromEntries(cats.map((c) => [c.id, c])) };
};

test('Baseline is RED everywhere: grid too small, 39.8 MW guaranteed of 150 MW', () => {
  const { r, h, cat } = page('baseline');
  assert.equal(r.status, 'RED'); assert.equal(h.verdict, 'RED');
  assert.equal(h.phrase, 'Grid too small');
  assert.equal(h.level, '39.8 MW guaranteed now of 150 MW requested');
  assert.equal(cat.grid.status, 'RED');
});
test('Flexible is GREEN everywhere, with the levers named from its own numbers', () => {
  const { r, h, w, cat } = page('flexible');
  assert.equal(r.status, 'GREEN'); assert.equal(h.verdict, 'GREEN');
  assert.equal(h.phrase, 'Fits with flexibility'); assert.equal(h.why, 'Everything fits');
  assert.match(h.level, /^100 MW with battery 60 MW, pausing use 10% \(curtailment\)/);
  assert.equal(cat.grid.status, 'GREEN'); assert.equal(cat.timeline.status, 'GREEN');
  assert.equal(w.title, 'WHAT THIS DEPENDS ON');
  assert.ok(w.items.some((i) => /battery/i.test(i.text) && i.to === 'RED'));
  assert.ok(w.items.some((i) => /flood/i.test(i.text) && i.to === 'AMBER'));
});
test('Stressed is RED and names its own failing check', () => {
  const { h, cat } = page('stressed');
  assert.equal(h.verdict, 'RED'); assert.equal(h.first.id, 'capacity');
  assert.match(h.level, /of headroom for 420 MW/);
  assert.equal(cat.grid.status, 'RED');
});
test('Conditional is AMBER and names the unmet deadline', () => {
  const { h, w, cat } = page('conditional');
  assert.equal(h.verdict, 'AMBER'); assert.equal(h.first.id, 'deadline');
  assert.match(h.level, /6 months available.*18/);
  assert.equal(cat.timeline.status, 'AMBER'); assert.equal(cat.grid.status, 'GREEN');
  assert.deepEqual(w.items.map((i) => i.to), ['GREEN']);
});
test('what-if differs between Baseline and Flexible; site-data categories do not move', () => {
  const b = page('baseline'), f = page('flexible');
  assert.notDeepEqual(b.w.items.map((i) => i.text), f.w.items.map((i) => i.text));
  assert.equal(b.w.title, 'WHAT IF');
  assert.ok(b.w.items.some((i) => i.to === 'GREEN') && b.w.items.some((i) => i.to === 'RED'));
  for (const id of ['climate', 'nature', 'community', 'economics']) {
    assert.equal(b.cat[id].status, f.cat[id].status);
    assert.equal(b.cat[id].note, 'site data, same in every scenario');
  }
});
test('each scenario gets its own what-if list (text, target colour and note)', () => {
  const sig = (p) => JSON.stringify(page(p).w);
  const all = ['baseline', 'flexible', 'conditional', 'stressed'].map(sig);
  assert.equal(new Set(all).size, 4);
});
test('preset button edges show each preset verdict, whichever preset is selected', () => {
  // main.js colours each button once from evaluate(PRESETS[name]); it never depends on the current settings.
  assert.deepEqual(Object.keys(PRESETS).map((p) => evaluate(PRESETS[p], run).status), ['RED', 'GREEN', 'AMBER', 'RED']);
});
