import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { gridFacts } from '../src/grid-views.js';

const run = JSON.parse(readFileSync(new URL('../public/data/run.json', import.meta.url)));

test('gridFacts reads firm N-1, loading, voltage and the outage shortfall from run.json', () => {
  const f = gridFacts(run);
  assert.deepEqual(f.subs.map(s => s.name), ['Northern Receiving Station', 'Los Esteros Substation']);
  for (const s of f.subs) { assert.equal(s.mw, 75); assert.equal(s.netMw, 42.5); assert.equal(s.firmMw, 19.9); assert.equal(s.status, 'RED'); }
  assert.equal(f.loading.pct, 68.6); assert.equal(f.loading.status, 'GREEN');
  assert.equal(f.voltage.min.toFixed(2), '0.99'); assert.equal(f.voltage.max.toFixed(2), '1.02'); assert.equal(f.voltage.status, 'GREEN');
  assert.equal(f.outage.n1Pass, false); assert.equal(f.outage.failing, 'Northern Receiving Station'); assert.equal(f.outage.shortfallMw, 45.2);
});

test('gridFacts goes GREEN when firm headroom covers the plan', () => {
  const cr = structuredClone(run.current_run);
  for (const s of cr.candidate_plan.splits) s.headroom_mw_n1_firm = 80;
  cr.physics_result.n1_pass = true; cr.physics_result.violations = [];
  cr.certificate.checks = cr.certificate.checks.filter(c => c.name !== 'firm_n1');
  const f = gridFacts({ ...run, current_run: cr });
  assert.ok(f.subs.every(s => s.status === 'GREEN')); assert.equal(f.outage.failing, null); assert.equal(f.outage.shortfallMw, 0);
});
