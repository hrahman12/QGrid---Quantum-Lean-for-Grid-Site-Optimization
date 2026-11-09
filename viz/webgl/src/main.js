import './style.css';
import { DEFAULTS, PRESETS, evaluate, normalize, exportScenario, round } from './model.js';
import { createScene } from './scene.js';
import { createQuantumComputer } from './quantum-computer.js';
import { createGridPhysics } from './grid-physics.js';
import { categorize, headline, whatIf } from './outcome.js';
const $ = (s) => document.querySelector(s);
const make = (tag, text, cls) => { const n = document.createElement(tag); if(text !== undefined) n.textContent = text; if(cls) n.className = cls; return n; };
let run, scene, quantumComputer, gridPhysics, result, lastQuantum=null, lastQuantumSettings=null, quantumPending=false, selected = 'site', settings = { ...DEFAULTS }, caseId = 'alviso';
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
function render(){
 settings=normalize(settings); result=evaluate(settings,run);
 for(const [key,value] of Object.entries(settings)){
  const input=document.getElementById(key); if(input.type==='checkbox') input.checked=value; else input.value=value;
  if(input.type==='range'){input.style.setProperty('--fill',`${(Number(value)-input.min)/(input.max-input.min)*100}%`);input.setAttribute('aria-valuetext',`${value}${units[key]||''}`);document.querySelector(`[data-output="${key}"]`).textContent=`${value}${units[key]||''}`;}
 }
 for(const b of document.querySelectorAll('[data-preset]')){const p=PRESETS[b.dataset.preset];const on=Object.keys(DEFAULTS).every(k=>p[k]===settings[k]);b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));}
 const passed=result.checks.filter(c=>c.status==='GREEN').length;
 $('#verdict-scenario').textContent=`Alviso scenario sliders: ${result.status==='AMBER'?'YELLOW':result.status} — ${passed} / 8 screens pass (browser preview, not the pipeline result).`;
 const first=result.blocking.find(c=>c.status==='RED')||result.blocking[0];
 $('#input-output').textContent=`${round(result.requested)} MW · ${settings.months} months`;
 $('#plan-output').textContent=result.allocations.map(a=>`${round(a.mw)} MW`).join(' + ')+` · ${round(result.delivered)} MW net`;
 $('#metric-demand').textContent=`${round(result.delivered)} MW`;$('#metric-firm').textContent=`${round(result.n1Capacity)} MW`;
 $('#metric-loading').textContent=`${round(result.projectedLoading)}%`;
 const thermal=result.checks.find(c=>c.id==='thermal');$('#metric-loading').style.color=`var(--${thermal.status==='GREEN'?'cyan':thermal.status==='AMBER'?'amber':'red'})`;
 $('#physics-state').textContent=thermal.status==='RED'?'OVERLOAD':thermal.status==='AMBER'?'NEAR LIMIT':'WITHIN LIMIT';$('#physics-state').dataset.status=thermal.status;
 $('#physics-routes').replaceChildren(...result.allocations.map(a=>{const row=make('div');row.dataset.offline=String(a.offline);row.append(make('span',a.name),make('b',a.offline?'OFFLINE':`${round(a.mw)} MW`));return row;}));
 $('#loading-bar').style.width=`${Math.min(100,result.projectedLoading/120*100)}%`;$('#loading-bar').style.background=`var(--${thermal.status.toLowerCase()})`;$('#limit-marker').style.left=`${settings.lineLimit/120*100}%`;
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
 renderLive();
 scene?.update(result);gridPhysics?.update(result);updateSelection();
 if(lastQuantum && !quantumPending && searchSignature(settings)!==lastQuantumSettings){$('#quantum-status').textContent='Inputs changed — run PsiQDK again';$('#quantum-engine-tag').textContent='Previous result is stale';}
}
function liveCase(){
 if(caseId==='alviso')return {...run.current_run,risk:run.risk_layers,edge:run.scenarios.edge};
 return run.cases[caseId];
}
function renderLive(){
 const live=liveCase(),h=headline(live),word=h.verdict==='AMBER'?'YELLOW':h.verdict;
 const [place,region]=live.site.name.split(/,(.*)/s);
 if(caseId==='alviso')$('#site-name').replaceChildren('North San Jose',make('br'),make('span','/ Alviso'));else $('#site-name').replaceChildren(place.replace(/ campus$/,''),make('br'),make('span',`${live.site.requested_mw} MW · ASSUMED`));
 $('#site-region').textContent=caseId==='alviso'?'Santa Clara County, California':`${(region||'').replace(/\s*\(.*$/,'').trim()} · ${live.site.grid_operator||''}`;
 $('#site-coordinate').textContent=`${Math.abs(live.site.lat).toFixed(4)}° ${live.site.lat>=0?'N':'S'} · ${Math.abs(live.site.lon).toFixed(4)}° ${live.site.lon>=0?'E':'W'}`;
 for(const b of document.querySelectorAll('[data-case]')){const on=b.dataset.case===caseId;b.classList.toggle('active',on);b.setAttribute('aria-pressed',String(on));}
 const opens=new Set([...document.querySelectorAll('.category[open]')].map(n=>n.dataset.id));
 $('#categories').replaceChildren(...categorize(live,caseId==='alviso'?result.checks:[]).map(cat=>{
  const d=make('details',undefined,'category');d.dataset.id=cat.id;d.dataset.status=cat.status;d.open=opens.has(cat.id);
  const s=make('summary');s.append(make('span',{GREEN:'✓',AMBER:'!',RED:'×',NONE:'–'}[cat.status],'indicator'),make('span',cat.name),make('small',cat.status==='NONE'?'NOT SCREENED':cat.status==='AMBER'?'YELLOW':cat.status));
  const body=cat.items.length?cat.items.map(i=>checkNode({id:`${cat.id}-${i.name}`,name:i.name,status:i.status,detail:i.detail})):[make('p','No data for this site yet. Nature, climate, community and economics layers were built for Alviso only; this site needs those runs.')];
  d.append(s,...body);return d;}));
 $('#verdict').dataset.status=h.verdict;
 $('#verdict-title').textContent=`${word} — ${h.phrase}`;
 $('#verdict-level').textContent=h.level;
 $('#verdict-description').textContent=h.meaning;
 $('#what-if').replaceChildren(...whatIf(live,h).map(w=>{const li=make('li');li.dataset.status=w.to;li.append(make('span',w.text),make('b',`→ ${w.to==='AMBER'?'YELLOW':w.to}`),make('small',w.note));return li;}));
 $('#reason-word').textContent=h.phrase;$('#reason-word').dataset.status=h.verdict;
 $('#reason-title').textContent=h.sentence;
}
function chooseCase(id,note){
 caseId=id;renderLive();
 $('#location-note').textContent=note||(id==='alviso'?'Default: North San Jose / Alviso (full analysis).':'Precomputed pipeline run. Substations from OpenStreetMap with ASSUMED ratings (utility distribution data exists only for PG&E / California). Requested MW is ASSUMED. The 3D map and sliders stay the Alviso reference model.');
}
const km=(a,b)=>{const r=Math.PI/180,x=(b.lon-a.lon)*r*Math.cos((a.lat+b.lat)*r/2),y=(b.lat-a.lat)*r;return 6371*Math.hypot(x,y);};
async function lookUp(query){
 if(!query.trim())return;
 $('#location-note').textContent='Looking up the address…';
 try{
  // Nominatim usage policy: one request per explicit submit, no autocomplete; the browser sends the page as Referer.
  const r=await fetch(`https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=us&q=${encodeURIComponent(query.slice(0,200))}`,{headers:{Accept:'application/json'}});
  if(!r.ok)throw new Error();const [hit]=await r.json();
  if(!hit){$('#location-note').textContent='No US match found. Try a street address with city and state.';return;}
  const p={lat:Number(hit.lat),lon:Number(hit.lon)};
  const all=[['alviso',run.current_run.site],...Object.entries(run.cases).map(([id,c])=>[id,c.site])].map(([id,s])=>({id,d:km(p,s)})).sort((a,b)=>a.d-b.d);
  const near=all[0];
  if(near.d<=25)chooseCase(near.id,`${hit.display_name.slice(0,90)} is ${near.d.toFixed(1)} km from a precomputed site — showing that site's result, not a new run.`);
  else $('#location-note').textContent=`${hit.display_name.slice(0,90)} (${p.lat.toFixed(3)}, ${p.lon.toFixed(3)}): screening is available for precomputed sites only; this address needs a pipeline run. Nearest precomputed site is ${near.d.toFixed(0)} km away.`;
 }catch{$('#location-note').textContent='Address lookup is unavailable right now. Pick a precomputed site.';}
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
async function runQuantum(){
 if(quantumPending)return;
 const submitted={...settings},signature=searchSignature(settings),controller=new AbortController();
 const timeout=setTimeout(()=>controller.abort(),110000);quantumPending=true;
 $('#run-quantum').disabled=true;$('#run-quantum').textContent='Running…';$('#quantum-status').textContent='Executing the PsiQDK native circuit';$('#quantum-summary').textContent='Building the oracle, applying Grover interference, and collecting measurements…';$('#quantum-engine-tag').textContent='RUNNING';quantumComputer.running(true);
 try{
  const response=await fetch('/api/quantum',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({settings:submitted}),signal:controller.signal});
  const type=response.headers.get('content-type')||'';if(!type.includes('application/json'))throw new Error('The native execution service is not available. Start the API server or deploy the repository root.');const data=await response.json();if(!response.ok)throw new Error(data.error||'PsiQDK execution failed.');
  if(data.backend!=='psiqdk'||!data.result?.numpy_crosscheck_ok)throw new Error('The response did not contain a verified PsiQDK result.');
  lastQuantum=data;quantumComputer.result(data);$('#view-quantum').disabled=false;
  if(searchSignature(settings)===signature && data.selected_settings){settings=normalize({...settings,...Object.fromEntries(['storage','curtailment','dlr','split'].map(key=>[key,data.selected_settings[key]]))});lastQuantumSettings=searchSignature(settings);render();}else lastQuantumSettings=signature;
  const metrics=data.result.resources?.qpu_metrics||{};
  $('#quantum-status').textContent=data.plan?'PsiQDK completed · measured candidate applied':'PsiQDK completed · no feasible candidate measured';
  $('#quantum-summary').textContent=`${data.space.n_qubits} qubits · ${data.space.padded_N} states · ${data.marked_indices.length} marked · ${data.result.iterations} Grover iterations · ${data.result.samples_marked}/${data.result.shots} marked shots · AV ${metrics.active_volume??'n/a'} · ${data.wall_s}s`;
  $('#quantum-engine-tag').textContent='PSIQDK · COMPLETED';
  if(searchSignature(settings)!==lastQuantumSettings){$('#quantum-status').textContent='PsiQDK completed for earlier inputs — run again';$('#quantum-engine-tag').textContent='RESULT STALE';}
  $('.quantum-steps small').textContent=`Returned native states · job ${data.job_id.slice(0,8)} · ${Object.entries(data.result.versions).map(([k,v])=>`${k} ${v}`).join(' · ')}`;
 }catch(error){$('#quantum-status').textContent='PsiQDK did not complete';$('#quantum-summary').textContent=error.name==='AbortError'?'The job timed out. No fallback result was used.':error.message;$('#quantum-engine-tag').textContent='UNAVAILABLE';}
 finally{clearTimeout(timeout);quantumPending=false;quantumComputer.running(false);$('#run-quantum').disabled=false;$('#run-quantum').textContent='▶ Run PsiQDK';}
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
  $('#view-grid').onclick=()=>{quantumComputer.step('computer');$('#view-grid').classList.add('active');$('#view-quantum').classList.remove('active');$('.quantum-steps').hidden=true;};
  $('#view-quantum').onclick=()=>{if(!lastQuantum)return;quantumComputer.step(0);$('.quantum-steps').hidden=false;$('#view-quantum').classList.add('active');$('#view-grid').classList.remove('active');};
  document.querySelectorAll('[data-quantum-step]').forEach(b=>b.onclick=()=>{document.querySelectorAll('[data-quantum-step]').forEach(n=>n.classList.toggle('active',n===b));quantumComputer.step(Number(b.dataset.quantumStep));});
  $('#run-quantum').onclick=runQuantum;
  $('#case-list').replaceChildren(...[['alviso','Alviso, CA (default)'],...Object.entries(run.cases).map(([id,c])=>[id,c.site.name.split(',')[0].replace(/^NOVVA /,'NOVVA ')])].map(([id,text])=>{const b=make('button',text);b.type='button';b.dataset.case=id;b.onclick=()=>chooseCase(id);return b;}));
  $('#address-form').onsubmit=e=>{e.preventDefault();lookUp($('#address').value);};
  $('#why-button').onclick=explain;$('#sources-button').onclick=showSources;$('#record-button').onclick=showRecord;
  $('#export').onclick=()=>downloadJson('qgrid-scenario.json',exportScenario(settings,run));
  $('#import').onchange=async e=>{try{const f=e.target.files[0];if(!f)return;if(f.size>100000)throw new Error('Too big');const d=JSON.parse(await f.text());if(d.format!=='qgrid-scenario-preview/1'||!d.settings||typeof d.settings!=='object'||Array.isArray(d.settings))throw new Error('Invalid');settings=normalize(d.settings);render();toast('Scenario imported');}catch{toast('Import a QGrid scenario JSON file under 100 KB.');}e.target.value='';};
  render();document.querySelector('[data-jump="0"]').classList.add('active');
 }catch(e){$('#loading').hidden=true;$('#webgl-fallback').hidden=false;$('#webgl-fallback').textContent='Unable to load case-study data. Reload or run npm run dev.';console.error(e);}
}
$('#close-dialog').onclick=()=>dialog.close();dialog.addEventListener('click',e=>{if(e.target===dialog){const r=dialog.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)dialog.close();}});addEventListener('pagehide',()=>{scene?.dispose();quantumComputer?.dispose();gridPhysics?.dispose();});init();
