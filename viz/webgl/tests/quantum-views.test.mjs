import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { blochVector, blochVectors, railCounts, groverSteps } from '../src/quantum-views.js';

const close = (a, b, eps = 1e-12) => assert.ok(Math.abs(a - b) < eps, `${a} != ${b}`);
const basis = (n, index) => Array.from({ length: 2 ** n }, (_, i) => [i === index ? 1 : 0, 0]);

test('|0...0> gives z = 1 for every qubit', () => {
  for (const v of blochVectors(basis(3, 0))) { close(v.z, 1); close(v.x, 0); close(v.y, 0); close(v.r, 1); }
});
test('|1> on qubit k gives z = -1 on that qubit only (q0 = LSB)', () => {
  const v = blochVectors(basis(3, 0b010));
  close(v[0].z, 1); close(v[1].z, -1); close(v[2].z, 1);
});
test('uniform superposition gives x = 1', () => {
  const n = 4, a = 1 / Math.sqrt(2 ** n);
  for (const v of blochVectors(Array.from({ length: 2 ** n }, () => [a, 0]))) { close(v.x, 1); close(v.z, 0); close(v.r, 1); }
});
test('|+i> gives y = 1 (rho = (I + xX + yY + zZ)/2)', () => {
  const s = Math.SQRT1_2; const v = blochVector([[s, 0], [0, s]], 0);
  close(v.y, 1); close(v.x, 0); close(v.z, 0);
});
test('Bell state (|00> + |11>)/sqrt2 gives zero-length Bloch vectors', () => {
  const s = Math.SQRT1_2; const state = [[s, 0], [0, 0], [0, 0], [s, 0]];
  for (const v of blochVectors(state)) close(v.r, 0);
});
test('recorded native job: Bloch lengths in [0,1], steps and counts match the record', () => {
  const job = JSON.parse(readFileSync(new URL('../public/data/native_job.json', import.meta.url)));
  const steps = groverSteps(job);
  assert.equal(steps.length, job.result.states.length + 1);
  assert.equal(steps[1].phase, true);
  for (const m of job.marked_indices) assert.ok(steps[1].vec[m][0] < 0);
  for (const s of steps) for (const v of blochVectors(s.vec)) assert.ok(v.r >= -1e-12 && v.r <= 1 + 1e-9);
  // probability on marked indices in the final recorded state equals the recorded p_marked
  const last = job.result.states.at(-1), p = job.marked_indices.reduce((a, m) => a + last[m][0] ** 2 + last[m][1] ** 2, 0);
  close(p, job.result.per_iteration.at(-1).p_marked, 1e-9);
  const rails = railCounts(job.measurements, job.space.n_qubits);
  for (const [zero, one] of rails) assert.equal(zero + one, job.result.shots);
  assert.deepEqual(job.measurements, { 59: 20, 71: 12 });
});
