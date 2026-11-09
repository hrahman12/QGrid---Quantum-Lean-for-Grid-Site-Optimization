import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

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
  const dummy=new THREE.Object3D(); let job=null,source='live',isRunning=false,frame,alive=true,step=0;
  const caption=document.createElement('div');caption.className='processor-caption';caption.textContent='Light-based computer concept · quantum simulator (PsiQDK)';container.append(caption);
  const resize=()=>{const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};const observer=new ResizeObserver(resize);observer.observe(container);resize();
  const start=performance.now(),reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function draw(){if(!alive)return;frame=requestAnimationFrame(draw);const t=(performance.now()-start)/1000;controls.update();
    pulses.forEach(({curve,particle},i)=>{particle.visible=isRunning&&!reduced;particle.position.copy(curve.getPoint((t*.35+i/8)%1));});
    chip.material.color.setHex(isRunning?0x6af3cf:job?0x62b8ff:0x28556a);
    pathMaterials.forEach((m,i)=>{m.opacity=isRunning ? .6+Math.sin(t*4+i)*.3 : .35;});
    renderer.render(scene,camera);
  }draw();
  function displayStep(value){
    step=value;if(!job)return;
    hardware.visible=false;states.visible=true;
    const vector=value===0?job.result.states[0]:value===1?job.phase_state:job.result.states.at(-1);
    const n=vector.length,cols=Math.ceil(Math.sqrt(n)),marked=new Set(job.marked_indices),maxShare=Math.max(1,...Object.values(job.measurements||{}))/job.result.shots;bars.count=n;
    for(let i=0;i<n;i++){
      const [re,im]=vector[i];let probability=re*re+im*im;
      if(value===3)probability=(job.measurements[String(i)]||0)/job.result.shots;
      const h=value===3?Math.max(.02,5*probability/maxShare):Math.min(6,Math.max(.02,probability*n*.7)),negative=value===1&&re<0;
      dummy.position.set((i%cols-(cols-1)/2)*.4,negative?-h/2:h/2,(Math.floor(i/cols)-(cols-1)/2)*.4);dummy.scale.set(1,h,1);dummy.updateMatrix();bars.setMatrixAt(i,dummy.matrix);
      bars.setColorAt(i,new THREE.Color(negative?0xffbd58:marked.has(i)?0x45e6a1:0x2c6f99));
    }bars.instanceMatrix.needsUpdate=true;bars.instanceColor.needsUpdate=true;
    caption.textContent=(source==='recorded'?'Recorded run · ':'')+['Real simulator state: all options equally likely (uniform superposition)','Real simulator state: right answers flagged (phase flip)','Real simulator state: right answers boosted (amplified probabilities)',`Real simulator measurements: ${job.result.shots} samples`][value];
  }
  return {
    running(on){isRunning=on;if(on){hardware.visible=true;states.visible=false;caption.textContent='Running the quantum simulation…';}else if(!job)caption.textContent='No verified simulator result yet';},
    result(value,kind='live'){job=value;source=kind;hardware.visible=true;states.visible=false;caption.textContent=kind==='recorded'?`Recorded simulator run · ${value.space.n_qubits} qubits · ${value.result.shots} shots`:`Simulation done · ${value.space.n_qubits} qubits · ${value.result.shots} shots`;},
    step(value){if(value==='computer'){hardware.visible=true;states.visible=false;caption.textContent=job?(source==='recorded'?'Recorded run · quantum simulator':'Completed on the quantum simulator'):'Light-based computer concept · quantum simulator (PsiQDK)';}else displayStep(value);},
    dispose(){alive=false;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();scene.traverse(o=>{o.geometry?.dispose();if(o.material)for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();});renderer.dispose();}
  };
}
