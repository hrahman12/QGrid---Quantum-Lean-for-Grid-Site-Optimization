import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { reducedBloch, measurementBloch, stageVector } from './quantum-results.js';

export function createQuantumComputer(container) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
  catch { container.textContent = 'Quantum execution remains available; 3D rendering is unavailable.'; return { running() {}, result() {}, step() {}, dispose() {} }; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); renderer.setClearColor(0x0c192b, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping; renderer.toneMappingExposure = 1.3;
  container.append(renderer.domElement);
  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, .1, 100); camera.position.set(5, 4.5, 6.5);
  const controls = new OrbitControls(camera, renderer.domElement); controls.target.set(0, .8, 0); controls.enableDamping = true; controls.enablePan = false; controls.minDistance = 7; controls.maxDistance = 22;
  scene.add(new THREE.HemisphereLight(0xd3edff, 0x153b4a, 2.5));
  const light = new THREE.DirectionalLight(0xc5e8ff, 3); light.position.set(3, 8, 4); scene.add(light);
  const hardware = new THREE.Group(); scene.add(hardware);
  const steel = new THREE.MeshStandardMaterial({ color: 0x557a96, metalness: .7, roughness: .32 });
  const ivory = new THREE.MeshStandardMaterial({ color: 0xc8e0e9, metalness: .45, roughness: .3 });
  const gold = new THREE.MeshStandardMaterial({ color: 0xc3954b, metalness: .8, roughness: .3 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x18364c, metalness: .65, roughness: .4 });
  const glow = new THREE.MeshBasicMaterial({ color: 0x45d9f0 });
  const box = (w, h, d, mat, x, y, z) => { const m = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); m.position.set(x, y, z); hardware.add(m); return m; };
  box(7, .3, 4.7, dark, 0, -.35, 0);
  box(4.5, .2, 3.25, steel, -.3, -.08, .1);
  box(2.6, .16, 2.1, gold, -.3, .12, .1);
  box(1.9, .18, 1.5, dark, -.3, .29, .1);
  const chip = box(1.25, .08, .95, glow, -.3, .42, .1);
  const racks = [];
  for (const x of [-2.85, 2.85]) {
    box(.9, 2.9, 1.5, steel, x, 1.15, -.85); box(.8, 2.65, .06, dark, x, 1.16, -.06);
    for (let i = 0; i < 6; i++) { box(.62, .035, .07, ivory, x, .2 + i * .39, -.01); racks.push(box(.08, .05, .08, glow, x + .22, .27 + i * .39, .015)); }
  }
  const pulses = [], pathMaterials = [];
  for (let i = 0; i < 8; i++) {
    const side = i < 4 ? -1 : 1, offset = (i % 4 - 1.5) * .27;
    const points = [new THREE.Vector3(side*2.45,.35+(i%4)*.36,-.05),new THREE.Vector3(side*1.85,1.4+(i%4)*.16,offset),new THREE.Vector3(side*.8,.53,offset),new THREE.Vector3(-.3,.5,offset)];
    const curve = new THREE.CatmullRomCurve3(points);
    const mat = new THREE.MeshBasicMaterial({ color: i%3===0?0xffbd58:0x41d9ef, transparent: true, opacity: .65 }); pathMaterials.push(mat);
    const cable = new THREE.Mesh(new THREE.TubeGeometry(curve,35,.025,5,false),mat); hardware.add(cable);
    const particle = new THREE.Mesh(new THREE.SphereGeometry(.065,8,8),new THREE.MeshBasicMaterial({color:i%3===0?0xffdc83:0x8effe0})); hardware.add(particle); pulses.push({curve,particle});
  }
  const lid = new THREE.Mesh(new THREE.BoxGeometry(4.5,.07,3.25), new THREE.MeshStandardMaterial({color:0x80c8e6,transparent:true,opacity:.12,metalness:.1,roughness:.2})); lid.position.set(-.3,1.05,.1); hardware.add(lid);
  const edges = new THREE.LineSegments(new THREE.EdgesGeometry(lid.geometry),new THREE.LineBasicMaterial({color:0x5486a1,transparent:true,opacity:.55}));lid.add(edges);
  const states = new THREE.Group(); states.visible=false; scene.add(states);
  const bars = new THREE.InstancedMesh(new THREE.BoxGeometry(.3,1,.3),new THREE.MeshStandardMaterial({color:0xffffff,metalness:.2,roughness:.5}),256); states.add(bars);
  const bloch=new THREE.Group();bloch.visible=false;scene.add(bloch);
  bloch.add(new THREE.Mesh(new THREE.SphereGeometry(2.2,24,16),new THREE.MeshBasicMaterial({color:0x367a9e,wireframe:true,transparent:true,opacity:.22})));
  for(const axis of [new THREE.Vector3(1,0,0),new THREE.Vector3(0,1,0),new THREE.Vector3(0,0,1)])bloch.add(new THREE.ArrowHelper(axis,new THREE.Vector3(),2.65,0x5783a3,.15,.07));
  const arrow=new THREE.ArrowHelper(new THREE.Vector3(0,1,0),new THREE.Vector3(),2.2,0x53e8b0,.25,.12);bloch.add(arrow);
  const tip=new THREE.Mesh(new THREE.SphereGeometry(.09,12,12),new THREE.MeshBasicMaterial({color:0x72ffcd}));bloch.add(tip);
  const diagram=document.createElement('div');diagram.className='grover-circuit';diagram.innerHTML='<b>GROVER SEARCH</b><div>H⊗n <span>→</span> Oᶠ <span>→</span> D <span>→</span> M</div><small>Prepare · mark · amplify · measure</small>';container.append(diagram);
  const coords=document.createElement('div');coords.className='bloch-coordinates';coords.hidden=true;container.append(coords);
  const dummy=new THREE.Object3D(); let job=null,isRunning=false,frame,alive=true,step=0,mode='grover';
  hardware.visible=false;states.visible=false;
  const caption=document.createElement('div');caption.className='processor-caption';caption.textContent='Run PsiQDK to inspect native amplitudes and shots';container.append(caption);
  const resize=()=>{const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(container);resize();
  const start=performance.now(),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function draw(){if(!alive)return;frame=requestAnimationFrame(draw);const t=(performance.now()-start)/1000;controls.update();
    pulses.forEach(({curve,particle},i)=>{particle.visible=isRunning&&!reduced;particle.position.copy(curve.getPoint((t*.35+i/8)%1));});
    chip.material.color.setHex(isRunning?0x6af3cf:job?0x62b8ff:0x28556a);
    pathMaterials.forEach((m,i)=>{m.opacity=isRunning ? .6+Math.sin(t*4+i)*.3 : .35;});
    renderer.render(scene,camera);
  }draw();
  function displayStep(value){
    step=value;if(!job)return;tip.visible=true;
    hardware.visible=false;states.visible=mode==='grover';bloch.visible=mode==='bloch';diagram.hidden=mode!=='grover';coords.hidden=mode!=='bloch';
    const vector=stageVector(job,value);
    const b=value===3?measurementBloch(job):reducedBloch(vector),v=new THREE.Vector3(b.x,b.z,-b.y);
    arrow.visible=v.length()>1e-7;if(arrow.visible){arrow.setDirection(v.clone().normalize());arrow.setLength(2.2*b.length,.22,.1);}tip.position.copy(v.multiplyScalar(2.2));
    coords.textContent=`LSB reduced state · x ${b.x.toFixed(3)} · y ${b.y.toFixed(3)} · z ${b.z.toFixed(3)} · |r| ${b.length.toFixed(3)}`;
    const n=vector.length,cols=Math.ceil(Math.sqrt(n)),marked=new Set(job.marked_indices);bars.count=n;
    for(let i=0;i<n;i++){
      const [re,im]=vector[i];let probability=re*re+im*im;
      if(value===3)probability=(job.measurements[String(i)]||0)/job.result.shots;
      const h=Math.min(6,Math.max(.02,probability*n*.7)),negative=value===1&&re<0;
      dummy.position.set((i%cols-(cols-1)/2)*.4,negative?-h/2:h/2,(Math.floor(i/cols)-(cols-1)/2)*.4);dummy.scale.set(1,h,1);dummy.updateMatrix();bars.setMatrixAt(i,dummy.matrix);
      bars.setColorAt(i,new THREE.Color(negative?0xffbd58:marked.has(i)?0x45e6a1:0x2c6f99));
    }bars.instanceMatrix.needsUpdate=true;bars.instanceColor.needsUpdate=true;
    caption.textContent=mode==='bloch'?(value===3?'Measured LSB mixture · not a statevector':'Partial trace of native state · one qubit, not the full register'):['Native superposition · all register slots','Native oracle · negative phases in amber','Native final state · probability per slot',`Native measurements · ${job.result.shots} shots`][value];
  }
  return {
    running(on){isRunning=on;if(on){hardware.visible=true;states.visible=false;bloch.visible=false;diagram.hidden=true;coords.hidden=true;caption.textContent='Executing native PsiQDK · photon motion is illustrative';}else if(!job)caption.textContent='No verified PsiQDK result yet';},
    result(value){job=value;mode='grover';displayStep(2);},
    step(value){if(['computer','grover','bloch'].includes(value)){mode=value;hardware.visible=value==='computer';states.visible=value==='grover'&&!!job;bloch.visible=value==='bloch';diagram.hidden=value!=='grover';coords.hidden=value!=='bloch';if(value==='computer')caption.textContent='Photonic hardware concept · not quantum hardware execution';else if(job)displayStep(step);else{arrow.visible=false;tip.visible=false;caption.textContent='Run PsiQDK to populate this view';}}else{tip.visible=true;displayStep(value);}},
    dispose(){alive=false;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();scene.traverse(o=>{o.geometry?.dispose();if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();});renderer.dispose();}
  };
}
