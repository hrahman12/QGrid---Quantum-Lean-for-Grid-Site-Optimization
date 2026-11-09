import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { blochVector, blochVectors, railCounts, groverSteps, quantumOutcomeSummary } from '../src/quantum-views.js';

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

const summaryJob = (states, marked, measurements) => ({space:{N:states[0].length,padded_N:states[0].length},marked_indices:marked,phase_state:states[0],measurements,result:{states,shots:Object.values(measurements).reduce((a,b)=>a+b,0)}});
test('summary detects a Bell register and does not invent entanglement for a product state', () => {
  const a=Math.SQRT1_2;
  close(quantumOutcomeSummary(summaryJob([[[a,0],[0,0],[0,0],[a,0]]],[0,3],{0:1,3:1})).peak.mean,1);
  close(quantumOutcomeSummary(summaryJob([[[.5,0],[.5,0],[.5,0],[.5,0]]],[0],{0:1})).peak.mean,0);
});
test('summary reports SDK probabilities separately from observed counts', () => {
  const job=JSON.parse(readFileSync(new URL('../public/data/native_job.json',import.meta.url)));
  const s=quantumOutcomeSummary(job);
  close(s.initialProbability,2/128);close(s.finalProbability,job.result.per_iteration.at(-1).p_marked,1e-9);
  close(s.probabilityBoost,s.finalProbability/(2/128));
  assert.equal(s.support,128);assert.equal(s.plans,120);assert.equal(s.markedShots,32);assert.equal(s.shots,32);
  assert.ok(s.peak.mean>0&&s.peak.mean<=1);
});
test('summary handles an unmarked search without an infinite probability multiplier', () => {
  const s=quantumOutcomeSummary(summaryJob([[[Math.SQRT1_2,0],[Math.SQRT1_2,0]]],[],{0:2,1:2}));
  assert.equal(s.probabilityBoost,null);assert.equal(s.markedShots,0);close(s.peak.mean,0);
});

test('summary derives register size from each run rather than assuming seven qubits', () => {
  for (const n of [1, 3, 5, 8]) {
    const size = 2 ** n, a = 1 / Math.sqrt(size);
    const s = quantumOutcomeSummary(summaryJob([Array.from({length:size}, () => [a,0])], [0], {0:3}));
    assert.equal(s.peak.mixedness.length, n);
    assert.equal(s.basisStates, size);
    assert.equal(s.support, size);
    close(s.initialProbability, 1 / size);
    close(s.peak.mean, 0);
  }
});
