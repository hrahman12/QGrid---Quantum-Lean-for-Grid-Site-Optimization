import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { DEFAULTS, PRESETS, evaluate, normalize, exportScenario } from '../src/model.js';
const run = JSON.parse(await readFile(new URL('../public/data/run.json', import.meta.url)));

test('the baseline keeps the archived load and split but fails the current firm N-1 screen', () => {
  const r = evaluate(DEFAULTS, run);
  assert.equal(r.status, 'RED'); assert.equal(r.delivered, 150);
  assert.equal(r.n1Capacity, 39.8);
  assert.equal(r.checks.find((c) => c.id === 'n1').status, 'RED');
  assert.deepEqual(r.allocations.map((a) => a.mw), [112.5, 37.5]);
  assert.equal(r.projectedLoading, run.physics_result.max_line_loading_pct);
});
test('the three verdict presets are distinct and respect hard versus conditional failures', () => {
  assert.equal(evaluate(PRESETS.flexible, run).status, 'GREEN');
  const conditional = evaluate(PRESETS.conditional, run);
  assert.equal(conditional.status, 'AMBER');
  assert.ok(conditional.blocking.some((c) => c.id === 'deadline'));
  assert.ok(conditional.blocking.some((c) => c.id === 'row'));
  const stressed = evaluate(PRESETS.stressed, run);
  assert.equal(stressed.status, 'RED');
  assert.ok(stressed.checks.some((c) => c.id === 'capacity' && c.status === 'RED'));
});
test('outages remove source capacity and reroute all net load without losing MW', () => {
  const r = evaluate({ ...DEFAULTS, outage: 'northern', storage: 20 }, run);
  assert.equal(r.allocations[0].capacity, 0); assert.equal(r.allocations[0].mw, 0);
  assert.equal(r.allocations[1].mw, 130);
  assert.equal(r.allocations.reduce((sum, a) => sum + a.mw, 0) + r.storage + r.curtailed, r.requested);
});
test('deadline and permit conditions clear only when the corresponding knobs resolve them', () => {
  const r = evaluate({ ...PRESETS.conditional, months: 40, rowPermit: true }, run);
  assert.equal(r.checks.find((c) => c.id === 'deadline').status, 'GREEN');
  assert.equal(r.checks.find((c) => c.id === 'row').status, 'GREEN');
  assert.equal(r.status, 'GREEN');
});
test('uncommitted storage and excess curtailment remain conditional', () => {
  const r = evaluate({ ...PRESETS.flexible, storageCommitted: false, curtailment: 15 }, run);
  assert.equal(r.status, 'AMBER');
  assert.equal(r.checks.find((c) => c.id === 'commitment').status, 'AMBER');
  assert.equal(r.checks.find((c) => c.id === 'penalty').status, 'AMBER');
  assert.equal(r.distribution, run.flexibility.curve.at(-1).distribution_mw);
  assert.equal(r.distributionExtrapolated, true);
});
test('line upgrades never inflate the firm transformer N-1 cap', () => {
  const a = evaluate(DEFAULTS, run);
  const b = evaluate({ ...DEFAULTS, dlr: 30, reconductor: true, rowPermit: true, months: 60 }, run);
  assert.equal(a.n1Capacity, b.n1Capacity);
  assert.equal(b.checks.find((c) => c.id === 'n1').status, 'RED');
});
test('imports clamp invalid inputs and never overwrite saved evidence', () => {
  const before = JSON.stringify(run);
  const state = normalize({ load: -100, split: 999, temperature: 'NaN', rowPermit: 'yes', outage: 'anything' });
  assert.equal(state.load, 25); assert.equal(state.split, 100); assert.equal(state.temperature, 25);
  assert.equal(state.rowPermit, false); assert.equal(state.outage, 'none');
  const output = exportScenario(state, run);
  assert.equal(output.format, 'qgrid-scenario-preview/1'); assert.match(output.scope, /Not a pandapower/);
  assert.equal(JSON.stringify(run), before);
});
