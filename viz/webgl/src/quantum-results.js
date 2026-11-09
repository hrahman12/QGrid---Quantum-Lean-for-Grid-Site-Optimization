export function validateQuantumResult(job) {
  if(job.backend!=='psiqdk'||job.result?.numpy_crosscheck_ok!==true)throw new Error('Native PsiQDK cross-check did not pass.');
  const n=job.space.padded_N;
  if(n!==2**job.space.n_qubits||n>256||!Array.isArray(job.result.states)||!job.result.states.length)throw new Error('Invalid native register.');
  for(const vector of [...job.result.states,job.phase_state]) {
    if(!Array.isArray(vector)||vector.length!==n||vector.some(a=>!Array.isArray(a)||a.length!==2||a.some(v=>!Number.isFinite(v))))throw new Error('Invalid native statevector.');
    if(Math.abs(vector.reduce((s,[r,i])=>s+r*r+i*i,0)-1)>1e-5)throw new Error('Native state is not normalized.');
  }
  if(!Array.isArray(job.result.samples)||job.result.samples.length!==job.result.shots)throw new Error('Measurement count mismatch.');
  const counts={};for(const sample of job.result.samples){if(!Number.isInteger(sample)||sample<0||sample>=n)throw new Error('Invalid measurement.');counts[sample]=(counts[sample]||0)+1;}
  if(Object.keys({...counts,...job.measurements}).some(k=>counts[k]!==job.measurements[k]))throw new Error('Measurement histogram mismatch.');
  return job;
}

// Partial trace of the full native state onto the least-significant register bit.
// Entanglement can put this vector INSIDE the sphere. It is not the full Grover state.
export function reducedBloch(vector) {
  let x=0,y=0,z=0;
  for(let i=0;i<vector.length;i+=2){const [ar,ai]=vector[i],[br,bi]=vector[i+1];x+=2*(ar*br+ai*bi);y+=2*(ar*bi-ai*br);z+=ar*ar+ai*ai-br*br-bi*bi;}
  return {x,y,z,length:Math.hypot(x,y,z)};
}

export function stageVector(job,step){return step===0?job.result.states[0]:step===1?job.phase_state:job.result.states.at(-1);}
export function measurementBloch(job){let z=0;for(const [i,count] of Object.entries(job.measurements))z+=(Number(i)%2?-1:1)*count/job.result.shots;return {x:0,y:0,z,length:Math.abs(z)};}
