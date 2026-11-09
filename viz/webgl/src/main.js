import './style.css';
import { DEFAULTS, PRESETS, evaluate, normalize, exportScenario, round } from './model.js';
import { createScene } from './scene.js';
import { createQuantumComputer } from './quantum-computer.js';
import { createGridPhysics } from './grid-physics.js';
import { validateQuantumResult } from './quantum-results.js';
import { drawGridDiagnostics } from './grid-diagnostics.js';
const $ = (s) => document.querySelector(s);
const make = (tag, text, cls) => { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; };
let lastPhysics=null,lastPhysicsSettings=null,physicsPending=false,physicsNetwork=false;
let run, scene, quantumComputer, gridPhysics, result, lastQuantum=null, lastQuantumSettings=null, quantumPending=false, selected = 'site', settings = { ...PRESETS.flexible };
const units = { load:' MW', growth:'%', utilization:'%', split:'%', storage:' MW', curtailment:'%', dlr:'%', temperature:'°C', lineLimit:'%', months:' mo' };
const dialog = $('#detail-dialog');
const searchSignature = value => JSON.stringify(['load','growth','utilization','split','storage','curtailment','dlr','temperature','reconductor','requireN1','outage'].map(key=>[key,value[key]]));
function toast(text){ $('#toast').textContent=text; $('#toast').classList.add('show'); setTimeout(()=>$('#toast').classList.remove('show'),3000); }
function showDialog(title, content){ $('#dialog-eyebrow').textContent=title; $('#dialog-content').replaceChildren(...content); dialog.showModal(); }
function checkNode(check){
 const d=make('details',undefined,'check'); d.dataset.id=check.id; d.dataset.status=check.status;
 const s=make('summary'); s.append(make('span',check.status==='GREEN'?'✓':check.status==='AMBER'?'!':'×','indicator'),make('span',check.name),make('small',check.status==='GREEN'?'PASS':check.status==='AMBER'?'IF':'BLOCK'));
 d.append(s,make('p',check.detail)); return d;
}
const physicsSignature=s=>JSON.stringify([...JSON.parse(searchSignature(s)),['lineLimit',s.lineLimit]]);
function render(){
 settings=normalize(settings); const ac=lastPhysics&&physicsSignature(settings)===lastPhysicsSettings?lastPhysics:null;result=evaluate(settings,run,ac?.result);
 for(const [key,value] of Object.entries(settings)){
  const input=document.getElementById(key); if(input.type==='checkbox') input.checked=value; else input.value=value;
  if(input.type==='range'){input.style.setProperty('--fill',`${(Number(value)-input.min)/(input.max-input.min)*100}%`);input.setAttribute('aria-valuetext',`${value}${units[key]||''}`);document.querySelector(`[data-output="${key}"]`).textContent=`${value}${units[key]||''}`;}
 }
 for(const b of document.querySelectorAll('[data-preset]')){const p=PRESETS[b.dataset.preset];const on=Object.keys(DEFAULTS).every(k=>p[k]===settings[k]);b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));}
 const passed=result.checks.filter(c=>c.status==='GREEN').length;
 $('#verdict').dataset.status=result.status;
 $('#verdict-title').textContent=`${result.status==='AMBER'?'YELLOW':result.status} — ${passed} / 8 rules pass`;
 const first=result.blocking.find(c=>c.status==='RED')||result.blocking[0];
 $('#verdict-description').textContent=first?first.detail:'All selected scenario conditions pass. New physics and Lean evidence are required for formal certification.';
 $('#input-output').textContent=`${round(result.requested)} MW · ${settings.months} months`;
 $('#plan-output').textContent=result.allocations.map(a=>`${round(a.mw)} MW`).join(' + ')+` · ${round(result.delivered)} MW net`;
 $('#metric-demand').textContent=`${round(result.delivered)} MW`;$('#metric-firm').textContent=`${round(result.n1Capacity)} MW`;
 const loading=ac?ac.result.max_line_loading_pct:result.projectedLoading;$('#metric-loading').textContent=loading===null?'?':`${round(loading)}%`;$('#physics-metric-label').textContent=ac?'solved AC peak loading':'preview peak loading';
 const thermal=result.checks.find(c=>c.id==='thermal');$('#metric-loading').style.color=`var(--${thermal.status==='GREEN'?'cyan':thermal.status==='AMBER'?'amber':'red'})`;
 $('#physics-state').textContent=thermal.status==='RED'?'OVERLOAD':thermal.status==='AMBER'?'NEAR LIMIT':'WITHIN LIMIT';$('#physics-state').dataset.status=thermal.status;
 $('#physics-routes').replaceChildren(...result.allocations.map(a=>{const row=make('div');row.dataset.offline=String(a.offline);row.append(make('span',a.name),make('b',a.offline?'OFFLINE':`${round(a.mw)} MW`));return row;}));
 $('#loading-bar').style.width=`${Math.min(100,(loading??0)/120*100)}%`;$('#loading-bar').style.background=`var(--${thermal.status.toLowerCase()})`;$('#limit-marker').style.left=`${settings.lineLimit/120*100}%`;
 const opens=new Set([...document.querySelectorAll('.check[open]')].map(n=>n.dataset.id));
 $('#physics-checks').replaceChildren(...result.checks.filter(c=>['capacity','thermal','n1'].includes(c.id)).map(checkNode));
 $('#checks').replaceChildren(...result.checks.filter(c=>!['capacity','thermal','n1'].includes(c.id)).map(checkNode));
 for(const n of document.querySelectorAll('.check')) n.open=opens.has(n.dataset.id);
 const physicsBlocked=result.checks.some(c=>['capacity','thermal','n1'].includes(c.id)&&c.status==='RED');
 $('#physics-output').textContent=physicsBlocked?'Blocked — revise the candidate':'Grid screening passes';
 $('#proof-output').textContent=`${result.status} · ${passed} / 8 scenario checks pass`;$('#passed-count').textContent=`${passed} / 8`;
 $('#lean-goal-status').textContent={GREEN:'READY TO PROVE',AMBER:'1 RULE UNMET',RED:'RULES UNMET'}[result.status];$('#lean-goal-status').dataset.status=result.status;$('#passed-count').style.color=`var(--${result.status.toLowerCase()})`;
 $('#flow-input').textContent=`${round(result.requested)} MW`;$('#flow-plan').textContent=`${result.allocations.filter(a=>a.mw>0).length} routes`;
 $('#flow-check').textContent=physicsBlocked?'Blocked':'Pass';$('#flow-check').style.color=physicsBlocked?'var(--red)':'var(--green)';$('#flow-result').textContent=result.status;$('#flow-result').style.color=`var(--${result.status.toLowerCase()})`;
 $('#reason-title').textContent=first?`${first.name} ${first.status==='RED'?'blocks this plan.':'is conditional.'}`:'Every scenario condition holds.';
 $('#reason-text').textContent=first?first.detail:'This is a screening result. Run the actual pipeline to obtain new physics and formal evidence.';
 scene?.update(result);gridPhysics?.update(result);updateSelection();
 if(!physicsPending){$('#physics-engine-tag').textContent=ac?'PANDAPOWER · SOLVED':lastPhysics?'STALE · RERUN AC':'Preview · AC not run';}
 if(physicsNetwork)drawGridDiagnostics($('#ac-network'),ac);
 if(lastQuantum && !quantumPending && searchSignature(settings)!==lastQuantumSettings){$('#quantum-status').textContent='Inputs changed — run PsiQDK again';$('#quantum-engine-tag').textContent='Previous result is stale';}
}
function updateSelection(){
 const a=run.grid_snapshot.substations.find(s=>s.id===selected);const allocation=result.allocations.find(s=>s.id===selected);
 $('#asset-name').textContent=a?a.name:'North San Jose compute site';
 $('#asset-info').textContent=a?`${a.kv} kV · ${a.distance_km} km · ${round(allocation?allocation.capacity:a.headroom_mw)} MW scenario headroom`:`${round(result.requested)} MW request · drag to orbit, scroll to zoom`;
 for(const b of document.querySelectorAll('[data-asset]'))b.classList.toggle('active',b.dataset.asset===selected);
}
function selectAsset(id){selected=id;updateSelection();scene.select(id);}
function explain(){
 const head=make('h2',`${result.status}: why this verdict?`);head.style.color=`var(--${result.status.toLowerCase()})`;
 const p=make('p',`${round(result.requested)} MW gross demand − ${round(result.curtailed)} MW curtailment − ${round(result.storage)} MW assumed battery support = ${round(result.delivered)} MW net grid demand. Firm N-1 capacity is ${round(result.n1Capacity)} MW.`);
 const rows=result.checks.flatMap(c=>[make('h3',`${c.status} · ${c.name}`),make('p',c.detail)]);
 const next=make('p',result.blocking.length?'Resolve every unmet rule listed above, then check again. Yellow means exactly seven of eight screens pass; any blocking physics limit still needs to be resolved. Line uprating does not increase firm transformer caps.':'The browser checks pass. A changed plan still needs the actual quantum / physics / Lean pipeline before formal certification.');
 showDialog('THIS SCENARIO / EXACT REASONS',[head,p,...rows,make('h3','What to do next'),next]);
}
function showRecord() {
  const heading = make('h2', `Archived certificate: ${run.certificate.result} (superseded)`);
  heading.style.color = 'var(--amber)';
  const text = make('p', `This historical 150 MW run (${run.quantum.generated_utc}) predates the firm N-1 transformer review. Its GREEN verdict is superseded: the current 150 MW baseline is blocked by firm transformer caps. It is retained for comparison, not as a current certificate. Scenario knobs do not change this archive.`);
  const rows = run.certificate.checks.map((check) => {
    const row = make('div', undefined, 'certificate-row'); row.append(make('span', check.name.replaceAll('_', ' ')), make('span', check.pass ? 'PASS' : 'FAIL')); row.title = check.detail; return row;
  });
  const metrics = make('p', `Recorded pandapower result: ${run.physics_result.max_line_loading_pct}% maximum loading; ${run.physics_result.v_min_pu}–${run.physics_result.v_max_pu} pu voltage; N-1 ${run.physics_result.n1_pass ? 'pass' : 'fail'}.`);
  const hash = make('code', run.certificate.evidence_sha256);
  const note = make('p', run.certificate.scope_note);
  const download = make('button', '↓ Download saved certificate', 'outline-button'); download.style.marginTop = '18px'; download.onclick = () => downloadJson('qgrid-saved-certificate.json', run.certificate);
  showDialog('RECORDED EVIDENCE / IMMUTABLE', [heading, text, ...rows, make('h3', 'Physics evidence'), metrics, make('h3', 'Evidence SHA-256'), hash, make('h3', 'Certificate scope'), note, download]);
}
function showSources() {
  const header = make('h2', 'What the explorer computes');
  const intro = make('p', 'This is an offline, interactive scenario screen built around the recorded North San Jose / Alviso case. Geometry is geographic; equipment models and proposed connections are visual abstractions. It does not claim new power-flow or formal-proof results.');
  const equations = make('ul');
  for (const text of [
    'Gross demand = requested load × (1 + demand growth). Net grid demand subtracts selected curtailment and assumed battery MW.',
    'Scenario headroom scales the recorded assumed headroom by (100 − utilization) / 35, DLR uplift, a 20% reconductoring factor, and a heat penalty of 0.8% per °C above 25°C.',
    'Thermal loading scales the recorded 71.7% result by net load, the largest route share relative to 75%, utilization, heat, and the selected upgrade factors. This is a sensitivity proxy, not an AC or IEEE 738 calculation.',
    'Firm N-1 screening uses the recorded firm transformer headroom: 19.9 MW per selected source before an outage. Line-rating uplift and reconductoring never increase those firm caps. It does not solve line contingencies or validate protection and topology.',
    'Assumed delivery times: DLR 12 months, battery 18 months, reconductoring 36 months. ROW, flood protection, and storage commitment toggles are scenario assumptions, not evidence of permits or commitments.',
    'GRIP distribution MW comes from the cached 2028 flexibility curve, linearly interpolated between published scenario points. Above 10% curtailment the display is capped at the last data point.',
    'Overall display: GREEN when 8/8 screens pass, YELLOW (AMBER) when exactly 7/8 pass, RED when 6/8 or fewer pass. Unmet includes a failed limit or an unresolved condition. Individual blocking physics rules remain red regardless of the overall count. This display rule does not change the pipeline or Lean verdict.',
  ]) equations.append(make('li', text));
  const sources = make('ul');
  for (const [label, url] of [
    ['Saved pipeline run and Lean evidence', 'https://github.com/hrahman12/QGrid---Quantum-Lean-for-Grid-Site-Optimization/tree/main/docs/demo_run'],
    ['Recorded GRIP flexibility curve and assumptions', 'https://github.com/hrahman12/QGrid---Quantum-Lean-for-Grid-Site-Optimization/blob/main/data/l2/flex_headroom.json'],
    ['OpenStreetMap contributors · ODbL', 'https://www.openstreetmap.org/copyright'],
    ['Terrain Tiles / USGS terrain attribution', 'https://github.com/tilezen/joerd/blob/master/docs/attribution.md'],
    ['Three.js WebGL renderer and controls', 'https://threejs.org/'],
  ]) { const li = make('li'); const a = make('a', label); a.href = url; a.target = '_blank'; a.rel = 'noreferrer'; li.append(a); sources.append(li); }
  showDialog('MODEL / ASSUMPTIONS / SOURCES', [header, intro, make('h3', 'Scenario equations and verdict rules'), equations, make('h3', 'Source data'), sources, make('p', 'The saved grid model includes substations in different utility jurisdictions. Inferred topology and assumed ratings are not an approved PG&E or Silicon Valley Power connection plan. Terrain relief is exaggerated 1.5×; low-elevation water coloring is a heuristic, not a flood map.')]);
}
function downloadJson(filename, data) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }));
  const a = make('a'); a.href = url; a.download = filename; document.body.append(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
async function runPhysics(){
 if(physicsPending)return;physicsPending=true;const submitted={...settings},signature=physicsSignature(settings),controller=new AbortController(),timeout=setTimeout(()=>controller.abort(),110000);
 $('#run-physics').disabled=true;$('#physics-engine-tag').textContent='SOLVING AC + N-1';$('#physics-run-status').textContent='Solving the base case and each model line outage…';
 try{const response=await fetch('/api/physics',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settings:submitted}),signal:controller.signal});if(!(response.headers.get('content-type')||'').includes('application/json'))throw new Error('Physics API unavailable.');const data=await response.json();if(!response.ok)throw new Error(data.error||'AC solver failed.');if(data.engine!=='pandapower'||!data.result)throw new Error('No pandapower evidence returned.');lastPhysics=data;lastPhysicsSettings=signature;$('#physics-evidence').disabled=false;physicsNetwork=true;$('#ac-network').hidden=false;$('#physics-viewport').hidden=true;$('#physics-view').textContent='3D spans';$('#physics-run-status').textContent=`${data.result.converged?'Converged':'No convergence'} · V ${data.result.v_min_pu??'?'}–${data.result.v_max_pu??'?'} pu · N-1 ${data.result.n1_pass?'PASS':'FAIL'} · ${data.wall_s}s`;}
 catch(error){$('#physics-run-status').textContent=error.name==='AbortError'?'AC job timed out; no result fabricated.':error.message;}
 finally{clearTimeout(timeout);physicsPending=false;$('#run-physics').disabled=false;render();}
}
function selectQuantumView(mode){quantumComputer.step(mode);for(const [id,m] of [['view-grid','computer'],['view-quantum','grover'],['view-bloch','bloch']])document.getElementById(id).classList.toggle('active',mode===m);$('.quantum-steps').hidden=mode==='computer'||!lastQuantum;}
async function runQuantum(){
 if(quantumPending)return;
 const submitted={...settings},signature=searchSignature(settings),controller=new AbortController();
 const timeout=setTimeout(()=>controller.abort(),110000);quantumPending=true;
 $('#run-quantum').disabled=true;$('#run-quantum').textContent='Running…';$('#quantum-status').textContent='Executing the PsiQDK native circuit';$('#quantum-summary').textContent='Building the oracle, applying Grover interference, and collecting measurements…';$('#quantum-engine-tag').textContent='RUNNING';quantumComputer.running(true);
 try{
  const response=await fetch('/api/quantum',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settings:submitted}),signal:controller.signal});
  const type=response.headers.get('content-type')||'';if(!type.includes('application/json'))throw new Error('The native execution service is not available. Start the API server or deploy the repository root.');const data=await response.json();if(!response.ok)throw new Error(data.error||'PsiQDK execution failed.');
  validateQuantumResult(data);
  lastQuantum=data;quantumComputer.result(data);$('#quantum-evidence').disabled=false;selectQuantumView('grover');document.querySelectorAll('[data-quantum-step]').forEach(b=>b.classList.toggle('active',b.dataset.quantumStep==='2'));quantumComputer.step(2);
  if(searchSignature(settings)===signature && data.selected_settings){settings=normalize({...settings,...Object.fromEntries(['storage','curtailment','dlr','split'].map(key=>[key,data.selected_settings[key]]))});lastQuantumSettings=searchSignature(settings);render();}else lastQuantumSettings=signature;
  const metrics=data.result.resources?.qpu_metrics||{};
  $('#quantum-status').textContent=data.plan?'PsiQDK completed · measured candidate applied':'PsiQDK completed · no feasible candidate measured';
  $('#quantum-summary').textContent=`${data.space.n_qubits} qubits · ${data.space.N} plans / ${data.space.padded_N} slots · ${data.marked_indices.length} marked · ${data.result.iterations} Grover iterations · ${data.result.samples_marked}/${data.result.shots} marked shots · AV ${metrics.active_volume??'n/a'} · ${data.wall_s}s · cross-check PASS`;
  $('#quantum-engine-tag').textContent='PSIQDK · COMPLETED';
  if(searchSignature(settings)!==lastQuantumSettings){$('#quantum-status').textContent='PsiQDK completed for earlier inputs — run again';$('#quantum-engine-tag').textContent='RESULT STALE';}
  $('.quantum-steps small').textContent=`Returned native states · job ${data.job_id.slice(0,8)} · ${Object.entries(data.result.versions).map(([k,v])=>`${k} ${v}`).join(' · ')}`;
 }catch(error){$('#quantum-status').textContent='PsiQDK did not complete';$('#quantum-summary').textContent=error.name==='AbortError'?'The job timed out. No fallback result was used.':error.message;$('#quantum-engine-tag').textContent='UNAVAILABLE';}
 finally{clearTimeout(timeout);quantumPending=false;quantumComputer.running(false);$('#run-quantum').disabled=false;$('#run-quantum').textContent='▶ Run now · native PsiQDK';}
}
async function init(){
 try{
  const get=async p=>{const r=await fetch(`${import.meta.env.BASE_URL}data/${p}.json`);if(!r.ok)throw new Error('Data unavailable');return r.json();};
  const values=await Promise.all([get('run'),get('geography')]);run=values[0];scene=createScene($('#viewport'),run,values[1],selectAsset);scene.flow(1);quantumComputer=createQuantumComputer($('#quantum-viewport'));gridPhysics=createGridPhysics($('#physics-viewport'));
  $('#asset-list').replaceChildren(...run.grid_snapshot.substations.map(s=>{const b=make('button',s.name);b.dataset.asset=s.id;b.onclick=()=>selectAsset(s.id);return b;}));
  $('#knobs').addEventListener('input',e=>{const i=e.target;if(!(i.name in DEFAULTS))return;settings[i.name]=i.type==='checkbox'?i.checked:i.type==='range'?Number(i.value):i.value;render();});
  $('#knobs').addEventListener('focusin',e=>{const card=e.target.closest('.stage-card');if(card)document.querySelectorAll('.stage-card').forEach(n=>n.classList.toggle('selected',n===card));});
  document.querySelectorAll('[data-preset]').forEach(b=>b.onclick=()=>{settings={...PRESETS[b.dataset.preset]};render();});
  $('#reset').onclick=()=>{settings={...DEFAULTS};render();scene.home();toast('Baseline restored');};
  document.querySelectorAll('[data-pane]').forEach(b=>b.onclick=()=>{const card=b.closest('.stage-card');card.querySelectorAll('[data-pane]').forEach(n=>{const on=n===b;n.classList.toggle('active',on);n.setAttribute('aria-selected',String(on));});card.querySelectorAll('[data-pane-body]').forEach(n=>n.hidden=n.dataset.paneBody!==b.dataset.pane);});
  document.querySelectorAll('[data-jump]').forEach(b=>b.onclick=()=>{const card=document.querySelector(`[data-step="${b.dataset.jump}"]`);$('#knobs').scrollTo({left:card.offsetLeft-$('#knobs').offsetLeft,behavior:'instant'});document.querySelectorAll('[data-jump]').forEach(n=>n.classList.toggle('active',n===b));});
  $('#home-camera').onclick=()=>scene.home();$('#top-camera').onclick=()=>scene.top();
  $('#rotate-camera').onclick=e=>{const on=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(on));scene.rotate(on);};
  for(const [id,name] of [['terrain-toggle','terrain'],['lines-toggle','lines'],['distribution-toggle','distribution']])document.getElementById(id).onclick=e=>{const on=e.currentTarget.getAttribute('aria-pressed')!=='true';e.currentTarget.setAttribute('aria-pressed',String(on));scene.layer(name,on);};
  $('#view-grid').onclick=()=>selectQuantumView('computer');
  $('#view-quantum').onclick=()=>selectQuantumView('grover');
  $('#view-bloch').onclick=()=>selectQuantumView('bloch');
  $('#quantum-evidence').onclick=()=>{if(!lastQuantum)return;const d=lastQuantum,rows=Object.entries(d.measurements).sort((a,b)=>b[1]-a[1]).map(([i,count])=>make('p',`|${Number(i).toString(2).padStart(d.space.n_qubits,'0')}⟩ · plan slot ${i} · ${count}/${d.result.shots} shots${d.marked_indices.includes(Number(i))?' · marked':''}`));showDialog('ACTUAL NATIVE RUN',[make('h2',`${d.space.n_qubits} qubits · ${d.space.N} plans`),make('p',`Job ${d.job_id} · ${d.completed_utc} · independent numerical cross-check PASS`),make('p',`Largest amplitude difference: ${Math.max(...d.result.numpy_crosscheck_max_abs_diff_per_iteration).toExponential(3)}. Bloch view traces out all register bits except the least-significant bit. Interior points indicate a mixed reduced state.`),...rows,make('p',Object.entries(d.result.versions).map(([k,v])=>`${k} ${v}`).join(' · '))]);};
  document.querySelectorAll('[data-quantum-step]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-quantum-step]').forEach(n=>n.classList.toggle('active',n===b));quantumComputer.step(Number(b.dataset.quantumStep));});
  $('#run-quantum').onclick=runQuantum;
  $('#run-physics').onclick=runPhysics;
  $('#physics-view').onclick=()=>{physicsNetwork=!physicsNetwork;$('#ac-network').hidden=!physicsNetwork;$('#physics-viewport').hidden=physicsNetwork;$('#physics-view').textContent=physicsNetwork?'3D spans':'Solved network';render();};
  $('#physics-evidence').onclick=()=>{const d=lastPhysics;if(!d)return;showDialog('ACTUAL GRID PHYSICS',[make('h2',`pandapower · ${d.result.converged?'converged':'not converged'}`),make('p',`Job ${d.job_id} · ${d.completed_utc}${physicsSignature(settings)!==lastPhysicsSettings?' · STALE INPUTS':''}`),make('p',d.scope),...d.result.violations.map(v=>make('p',v)),make('h3','Solved branches'),...d.edges.map(e=>make('p',`${e.kind} ${e.name}: ${e.loading_pct?.toFixed(1)??'?'}% loading · ${e.p_mw?.toFixed(2)??'?'} MW`))]);};
  $('#why-button').onclick=explain;$('#sources-button').onclick=showSources;$('#record-button').onclick=showRecord;
  $('#export').onclick=()=>downloadJson('qgrid-scenario.json',exportScenario(settings,run));
  $('#import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>100000)throw new Error('Too big');const d=JSON.parse(await f.text());if(d.format!=='qgrid-scenario-preview/1'||!d.settings||typeof d.settings!=='object'||Array.isArray(d.settings))throw new Error('Invalid');settings=normalize(d.settings);render();toast('Scenario imported');}catch{toast('Import a QGrid scenario JSON file under 100 KB.');}e.target.value='';};
  render();document.querySelector('[data-jump="0"]').classList.add('active');
 }catch(e){$('#loading').hidden=true;$('#webgl-fallback').hidden=false;$('#webgl-fallback').textContent='Unable to load case-study data. Reload or run npm run dev.';console.error(e);}
}
$('#close-dialog').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});addEventListener('pagehide',()=>{scene?.dispose();quantumComputer?.dispose();gridPhysics?.dispose();});init();
