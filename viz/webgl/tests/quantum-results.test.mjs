import test from 'node:test';
import assert from 'node:assert/strict';
import {reducedBloch,measurementBloch,validateQuantumResult} from '../src/quantum-results.js';
const near=(a,b)=>assert.ok(Math.abs(a-b)<1e-9,`${a} != ${b}`);
test('Bloch axes preserve complex phase and computational-basis convention',()=>{
  near(reducedBloch([[1,0],[0,0]]).z,1);near(reducedBloch([[0,0],[1,0]]).z,-1);
  near(reducedBloch([[Math.SQRT1_2,0],[Math.SQRT1_2,0]]).x,1);
  near(reducedBloch([[Math.SQRT1_2,0],[0,Math.SQRT1_2]]).y,1);
});
test('an entangled Bell register has a mixed reduced state at the center',()=>{
  near(reducedBloch([[Math.SQRT1_2,0],[0,0],[0,0],[Math.SQRT1_2,0]]).length,0);
});
test('measured mixture uses actual bit counts and discards coherence',()=>{
  const b=measurementBloch({measurements:{0:3,1:1},result:{shots:4}});near(b.z,.5);near(b.x,0);near(b.y,0);
});
test('UI rejects nonnative, unnormalized, and inconsistent returned evidence',()=>{
  const job={backend:'psiqdk',space:{padded_N:2,n_qubits:1},phase_state:[[1,0],[0,0]],result:{numpy_crosscheck_ok:true,states:[[[1,0],[0,0]]],samples:[0,0],shots:2},measurements:{0:2}};
  assert.equal(validateQuantumResult(job),job);
  assert.throws(()=>validateQuantumResult({...job,backend:'numpy'}));
  assert.throws(()=>validateQuantumResult({...job,phase_state:[[2,0],[0,0]]}));
  assert.throws(()=>validateQuantumResult({...job,measurements:{0:1}}));
});
