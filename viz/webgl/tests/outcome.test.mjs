import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { categorize, headline, whatIf } from '../src/outcome.js';
const run = JSON.parse(await readFile(new URL('../public/data/run.json', import.meta.url)));
const alviso = { ...run.current_run, risk: run.risk_layers, edge: run.scenarios.edge };

test('the live Alviso result is RED: grid too small, 39.8 MW firm of 150 MW, 45.2 MW short', () => {
  const h = headline(alviso);
  assert.equal(h.verdict, 'RED'); assert.equal(h.phrase, 'Grid too small');
  assert.equal(h.firm, 39.8); assert.equal(h.short, 45.2); assert.equal(h.requested, 150);
});
test('six categories, each with a traffic light from evidence; grid is RED', () => {
  const cats = categorize(alviso);
  assert.deepEqual(cats.map((c) => c.id), ['grid', 'climate', 'nature', 'community', 'economics', 'timeline']);
  assert.equal(cats.find((c) => c.id === 'grid').status, 'RED');
  assert.ok(cats.every((c) => ['GREEN', 'AMBER', 'RED'].includes(c.status)));
  assert.equal(cats.flatMap((c) => c.items).filter((i) => i.source === 'pipeline').length, run.current_run.certificate.checks.length);
});
test('what-if lists 3-6 conditions with the colour each moves to', () => {
  const w = whatIf(alviso);
  assert.ok(w.length >= 3 && w.length <= 6);
  assert.ok(w.every((x) => ['GREEN', 'AMBER', 'RED'].includes(x.to)));
});
test('precomputed cases without risk layers show NOT SCREENED instead of invented colours', () => {
  for (const c of Object.values(run.cases)) {
    const cats = categorize(c);
    assert.equal(cats.find((x) => x.id === 'community').status, 'NONE');
    assert.ok(['GREEN', 'AMBER', 'RED'].includes(headline(c).verdict));
  }
});
