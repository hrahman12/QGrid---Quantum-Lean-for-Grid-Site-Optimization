import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { CSS2DRenderer, CSS2DObject } from 'three/addons/renderers/CSS2DRenderer.js';

const COLORS = { GREEN: 0x45e6a1, AMBER: 0xffbd58, RED: 0xff6373 };
export function createScene(container, run, geography, onSelect) {
  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
  } catch (error) {
    document.querySelector('#webgl-fallback').hidden = false;
    document.querySelector('#loading').hidden = true;
    document.querySelector('#render-state').textContent = '2D scenario mode';
    return { update() {}, select() {}, home() {}, top() {}, rotate() {}, layer() {}, quantum() {}, quantumStep() {}, flow() {}, dispose() {} };
  }
  const reducedMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.6));
  renderer.setClearColor(0x071019, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.25;
  container.append(renderer.domElement);
  const labels = new CSS2DRenderer();
  labels.domElement.className = 'labels';
  container.append(labels.domElement);
  const scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x09151e, 0.012);
  const camera = new THREE.PerspectiveCamera(40, 1, 0.1, 300);
  camera.position.set(24, 29, 37);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(1, 0, 5);
  controls.enableDamping = true;
  controls.dampingFactor = 0.07;
  controls.minDistance = 13;
  controls.maxDistance = 95;
  controls.maxPolarAngle = Math.PI * 0.48;
  controls.autoRotateSpeed = 0.22;
  scene.add(new THREE.HemisphereLight(0xb9edff, 0x13252b, 2.1));
  const sun = new THREE.DirectionalLight(0xe4f4ff, 2.5); sun.position.set(15, 25, 15); scene.add(sun);
  const blue = new THREE.DirectionalLight(0x2599c8, 2); blue.position.set(-20, 10, -15); scene.add(blue);
  const gridWorld = new THREE.Group(); scene.add(gridWorld);
  const terrain = geography.terrain;
  const origin = run.site;
  const project = (lat, lon) => new THREE.Vector3((lon - origin.lon) * 111.32 * Math.cos(origin.lat * Math.PI / 180) * 3, 0, -(lat - origin.lat) * 111.32 * 3);
  const terrainOrigin = project(terrain.origin.lat, terrain.origin.lon);
  const elevation = (x, z) => {
    const mx = (x - terrainOrigin.x) / 3 * 1000;
    const my = -(z - terrainOrigin.z) / 3 * 1000;
    const col = Math.round((mx - terrain.x_min) / (terrain.x_max - terrain.x_min) * (terrain.n - 1));
    const row = Math.round((terrain.y_max - my) / (terrain.y_max - terrain.y_min) * (terrain.n - 1));
    if (row < 0 || col < 0 || row >= terrain.n || col >= terrain.n) return 0;
    return Math.max(-0.05, terrain.heights[row * terrain.n + col] * 0.003 * 1.5);
  };
  const base = new THREE.Mesh(new THREE.BoxGeometry(68, .34, 72), new THREE.MeshStandardMaterial({ color: 0x0c202b, roughness: .8, metalness: .2 }));
  base.position.set(1, -.45, 1); gridWorld.add(base);
  const terrainGeometry = new THREE.PlaneGeometry(1, 1, terrain.n - 1, terrain.n - 1);
  const positions = terrainGeometry.attributes.position;
  const colors = [];
  for (let row = 0; row < terrain.n; row++) for (let col = 0; col < terrain.n; col++) {
    const i = row * terrain.n + col;
    const x = terrain.x_min + col / (terrain.n - 1) * (terrain.x_max - terrain.x_min);
    const north = terrain.y_max - row / (terrain.n - 1) * (terrain.y_max - terrain.y_min);
    const h = terrain.heights[i];
    positions.setXYZ(i, terrainOrigin.x + x / 1000 * 3, Math.max(-.05, h * .003 * 1.5), terrainOrigin.z - north / 1000 * 3);
    const color = h <= .5 ? new THREE.Color(0x0b343c) : new THREE.Color(0x15313b).lerp(new THREE.Color(0x3d5452), Math.min(h / 850, 1));
    colors.push(color.r, color.g, color.b);
  }
  terrainGeometry.setAttribute('color', new THREE.Float32BufferAttribute(colors, 3));
  terrainGeometry.computeVertexNormals();
  const terrainMesh = new THREE.Mesh(terrainGeometry, new THREE.MeshStandardMaterial({ vertexColors: true, roughness: .97, metalness: .08, side: THREE.DoubleSide }));
  gridWorld.add(terrainMesh);
  const groundGrid = new THREE.GridHelper(68, 34, 0x2d5764, 0x1c3c4a);
  groundGrid.position.y = .055;
  groundGrid.material.transparent = true; groundGrid.material.opacity = .3;
  gridWorld.add(groundGrid);
  const geoLines = new THREE.Group();
  const lineVertices = [];
  for (const line of geography.lines) for (let i = 1; i < line.length; i++) {
    for (const [lon, lat] of [line[i - 1], line[i]]) {
      const p = project(lat, lon); p.y = elevation(p.x, p.z) + .11;
      lineVertices.push(p.x, p.y, p.z);
    }
  }
  const actualLines = new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(lineVertices, 3)), new THREE.LineBasicMaterial({ color: 0x35647a, transparent: true, opacity: .43 }));
  geoLines.add(actualLines); gridWorld.add(geoLines);
  const steel = new THREE.MeshStandardMaterial({ color: 0x9cb7c5, roughness: .38, metalness: .7 });
  const darkSteel = new THREE.MeshStandardMaterial({ color: 0x294451, roughness: .55, metalness: .55 });
  const copper = new THREE.MeshStandardMaterial({ color: 0xb57a3f, roughness: .45, metalness: .65 });
  const whiteLine = new THREE.LineBasicMaterial({ color: 0xa8d0df });
  const pickables = [], nodes = new Map(), labelElements = new Map();
  const nodePositions = new Map();
  const materialsToDispose = [];
  const box = (w, h, d, mat, x, y, z, parent) => { const mesh = new THREE.Mesh(new THREE.BoxGeometry(w, h, d), mat); mesh.position.set(x, y, z); parent.add(mesh); return mesh; };
  const addLabel = (text, position, cls = '') => {
    const div = document.createElement('div'); div.className = `node-label ${cls}`; div.textContent = text;
    const label = new CSS2DObject(div); label.position.copy(position); gridWorld.add(label);
    return { div, label };
  };
  const tower = (parent) => {
    const v = [];
    const edge = (a, b) => v.push(...a, ...b);
    const levels = [{ y: .25, w: .6 }, { y: 1.4, w: .35 }, { y: 2.5, w: .17 }, { y: 3.3, w: .02 }];
    for (let k = 0; k < levels.length - 1; k++) {
      const a = levels[k], b = levels[k + 1];
      for (const [sx, sz] of [[1, 1], [1, -1], [-1, 1], [-1, -1]]) {
        edge([sx*a.w,a.y,sz*a.w],[sx*b.w,b.y,sz*b.w]);
        edge([sx*a.w,a.y,sz*a.w],[-sx*b.w,b.y,sz*b.w]);
        edge([sx*a.w,a.y,sz*a.w],[sx*a.w,a.y,-sz*a.w]);
      }
    }
    for (const [y, w] of [[1.8, 1.1], [2.5, .85]]) {
      edge([-w,y,0],[w,y,0]); edge([-w,y,0],[0,y+.38,0]); edge([w,y,0],[0,y+.38,0]);
      for (const sx of [-1,1]) {
        const insulator = new THREE.Mesh(new THREE.CylinderGeometry(.08,.08,.22,8), copper);
        insulator.position.set(sx*w,y-.15,0); parent.add(insulator);
      }
    }
    parent.add(new THREE.LineSegments(new THREE.BufferGeometry().setAttribute('position', new THREE.Float32BufferAttribute(v,3)),whiteLine));
  };
  for (const sub of run.grid_snapshot.substations) {
    const p = project(sub.lat, sub.lon); p.y = elevation(p.x, p.z) + .13; nodePositions.set(sub.id, p);
    const group = new THREE.Group(); group.position.copy(p); group.userData.id = sub.id; gridWorld.add(group); nodes.set(sub.id,group);
    const baseMat = new THREE.MeshStandardMaterial({color:0x29444f,roughness:.6,metalness:.2}); materialsToDispose.push(baseMat);
    const platform = box(2.7,.15,2,baseMat,0,0,0,group); platform.userData.id=sub.id; pickables.push(platform);
    const loadIndicator=new THREE.Mesh(new THREE.CylinderGeometry(.12,.12,1,8),new THREE.MeshBasicMaterial({color:0x41d9ef}));
    loadIndicator.position.set(-1.5,.6,0);group.add(loadIndicator);group.userData.loadIndicator=loadIndicator;
    const line = new THREE.LineSegments(new THREE.EdgesGeometry(platform.geometry),new THREE.LineBasicMaterial({color:0x63a6b3})); platform.add(line);
    const t = new THREE.Group(); t.position.set(.45,.05,-.3); tower(t); group.add(t);
    for (let j=0;j<2;j++) {
      const x=-.8+j*1.05;
      box(.72,.65,.68,darkSteel,x,.4,.55,group);
      box(.8,.09,.72,copper,x,.77,.55,group);
      for(let fin=0;fin<5;fin++) box(.035,.52,.75,steel,x-.3+fin*.15,.4,.55,group);
      for(let k=0;k<2;k++) {
        const ins=new THREE.Mesh(new THREE.CylinderGeometry(.055,.075,.24,6),steel);
        ins.position.set(x-.17+k*.34,.92,.55);group.add(ins);
      }
    }
    const hit=new THREE.Mesh(new THREE.SphereGeometry(1.8,8,8),new THREE.MeshBasicMaterial({visible:false}));
    hit.position.y=1;hit.userData.id=sub.id;group.add(hit);pickables.push(hit);
    const label=addLabel(sub.name.replace(' Substation','').replace(' Station',''),p.clone().add(new THREE.Vector3(0,4,0)));
    labelElements.set(sub.id,label.div);
  }
  const sitePosition=new THREE.Vector3(0,elevation(0,0)+.2,0);nodePositions.set('site',sitePosition);
  const compute=new THREE.Group();compute.position.copy(sitePosition);gridWorld.add(compute);nodes.set('site',compute);
  const siteMat=new THREE.MeshStandardMaterial({color:0x286d7d,metalness:.55,roughness:.35});
  const pad=box(4,.23,3.25,darkSteel,0,0,0,compute);pad.userData.id='site';pickables.push(pad);
  for(let j=0;j<3;j++){
    box(.85,1.6,1.3,darkSteel,-1.12+j*1.12,.9,0,compute);
    box(.88,.1,1.35,steel,-1.12+j*1.12,1.75,0,compute);
    for(let k=0;k<5;k++) box(.57,.05,.035,new THREE.MeshBasicMaterial({color:k%2?0x45e6a1:0x41d9ef}),-1.12+j*1.12,.4+k*.25,.67,compute);
  }
  const siteRing=new THREE.Mesh(new THREE.TorusGeometry(3.1,.035,8,100),new THREE.MeshBasicMaterial({color:0x41d9ef,transparent:true,opacity:.65}));
  siteRing.rotation.x=Math.PI/2;siteRing.position.y=.2;compute.add(siteRing);
  const siteLabel=addLabel('COMPUTE SITE',sitePosition.clone().add(new THREE.Vector3(0,3.1,0)),'site');
  labelElements.set('site',siteLabel.div);
  const modelLines=new THREE.Group();gridWorld.add(modelLines);
  for(const link of run.grid_snapshot.lines){
    const a=nodePositions.get(link.from).clone(),b=nodePositions.get(link.to).clone();a.y+=1.5;b.y+=1.5;
    const curve=new THREE.QuadraticBezierCurve3(a,a.clone().lerp(b,.5).add(new THREE.Vector3(0,-.6,0)),b);
    const line=new THREE.Line(new THREE.BufferGeometry().setFromPoints(curve.getPoints(40)),new THREE.LineDashedMaterial({color:0x5a737d,dashSize:.25,gapSize:.22,transparent:true,opacity:.55}));line.computeLineDistances();modelLines.add(line);
  }
  const flowGroup=new THREE.Group();gridWorld.add(flowGroup);const flows=[];
  for(const [index,split] of run.candidate_plan.splits.entries()){
    const start=nodePositions.get(split.substation_id).clone().add(new THREE.Vector3(0,1.3,0));
    const end=sitePosition.clone().add(new THREE.Vector3(index?1:-1,.5,.5));
    const mid=start.clone().lerp(end,.5).add(new THREE.Vector3(index?1.4:-1.4,2.8,0));
    const curve=new THREE.QuadraticBezierCurve3(start,mid,end);
    const mat=new THREE.MeshBasicMaterial({color:index?0x45e6a1:0x41d9ef,transparent:true,opacity:.8});
    const tube=new THREE.Mesh(new THREE.TubeGeometry(curve,64,.065,6,false),mat);flowGroup.add(tube);
    const particles=[];const dotMat=new THREE.MeshBasicMaterial({color:0xbffff1});
    for(let k=0;k<6;k++){const dot=new THREE.Mesh(new THREE.SphereGeometry(.115,8,8),dotMat);flowGroup.add(dot);particles.push(dot);}
    flows.push({curve,mat,tube,particles,share:1});
  }
  const distribution=new THREE.Group();distribution.visible=false;gridWorld.add(distribution);
  for(const sub of run.grid_snapshot.distribution.substations){
    const p=project(sub.lat,sub.lon);p.y=elevation(p.x,p.z)+.2;
    const marker=new THREE.Mesh(new THREE.CylinderGeometry(.28,.28,.4,6),new THREE.MeshStandardMaterial({color:sub.connectable_mw>0?0xffbd58:0x596e77,emissive:sub.connectable_mw>0?0x36230b:0x000000}));
    marker.position.copy(p);distribution.add(marker);
  }
  for(const [text,lat,lon] of [['ALVISO',37.432,-121.98],['SAN JOSE',37.365,-121.975],['MILPITAS',37.42,-121.9],['BAYLANDS',37.47,-122.02]]){
    const p=project(lat,lon);p.y=elevation(p.x,p.z)+.2;const {div,label}=addLabel(text,p);div.className='place-label';
  }
  const quantumWorld=new THREE.Group();quantumWorld.visible=false;scene.add(quantumWorld);
  const qGrid=new THREE.GridHelper(30,32,0x355460,0x1b3542);qGrid.position.y=-.1;quantumWorld.add(qGrid);
  const qGeometry=new THREE.BoxGeometry(.65,1,.65);
  const qMesh=new THREE.InstancedMesh(qGeometry,new THREE.MeshStandardMaterial({color:0xffffff,metalness:.2,roughness:.55}),1024);
  quantumWorld.add(qMesh);const dummy=new THREE.Object3D();let qStage=1;
  function updateQuantum(){
    const probability=run.quantum.per_iteration[Math.max(0,Math.min(qStage,run.quantum.per_iteration.length-1))].p_marked;
    for(let i=0;i<1024;i++){
      const marked=i<run.quantum.marked;
      const p=marked?probability/run.quantum.marked:(1-probability)/(1024-run.quantum.marked);
      const height=Math.max(.1,p*1150);
      dummy.position.set((i%32-15.5)*.9,(qStage===-1&&marked?-1:1)*height/2,(Math.floor(i/32)-15.5)*.9);dummy.scale.set(1,height,1);dummy.updateMatrix();qMesh.setMatrixAt(i,dummy.matrix);
      qMesh.setColorAt(i,new THREE.Color(marked?(qStage===-1?0xffbd58:0x45e6a1):0x23556c));
    }
    qMesh.instanceMatrix.needsUpdate=true;if(qMesh.instanceColor)qMesh.instanceColor.needsUpdate=true;
  }
  updateQuantum();
  const caption=document.createElement('div');caption.className='quantum-caption';caption.hidden=true;
  caption.innerHTML=`<strong>${(run.quantum.per_iteration.at(-1).p_marked*100).toFixed(1)}% marked-state probability</strong>Archived pre-firm-N-1 PsiQDK run · ${run.quantum.marked} marked / ${run.quantum.space.padded_N} states<br>Aggregate probabilities; spatial ordering is illustrative. Not a current search.`;container.append(caption);
  const raycaster=new THREE.Raycaster(),pointer=new THREE.Vector2();let down=null,selected='site',quantumMode=false,alive=true,frame=0;
  renderer.domElement.addEventListener('pointerdown',(e)=>{down=[e.clientX,e.clientY];});
  renderer.domElement.addEventListener('pointerup',(e)=>{
    if(!down||quantumMode||Math.hypot(e.clientX-down[0],e.clientY-down[1])>5)return;
    const rect=renderer.domElement.getBoundingClientRect();pointer.set((e.clientX-rect.left)/rect.width*2-1,-(e.clientY-rect.top)/rect.height*2+1);raycaster.setFromCamera(pointer,camera);
    const hit=raycaster.intersectObjects(pickables,false)[0];if(hit)onSelect(hit.object.userData.id);
  });
  let cameraTarget=null,lookTarget=null;
  const resize=()=>{const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;renderer.setSize(w,h);labels.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};
  const observer=new ResizeObserver(resize);observer.observe(container);resize();
  renderer.domElement.addEventListener('webglcontextlost',(e)=>{e.preventDefault();document.querySelector('#render-state').textContent='WebGL context lost · reload to restore';alive=false;});
  const started=performance.now();
  const animate=()=>{
    if(!alive)return;frame=requestAnimationFrame(animate);const time=(performance.now()-started)/1000;
    if(cameraTarget){camera.position.lerp(cameraTarget,.07);controls.target.lerp(lookTarget,.07);if(camera.position.distanceTo(cameraTarget)<.08)cameraTarget=null;}
    flows.forEach((flow,i)=>{for(let k=0;k<flow.particles.length;k++){
      const dot=flow.particles[k];dot.visible=!reducedMotion&&flow.share>0;dot.position.copy(flow.curve.getPoint((time*(.075+flow.share*.04)+k/6+i*.16)%1));
    }});
    if(!reducedMotion)siteRing.material.opacity=.5+Math.sin(time*1.7)*.14;
    controls.update();renderer.render(scene,camera);labels.render(scene,camera);
  };
  animate();document.querySelector('#loading').hidden=true;document.querySelector('#render-state').textContent='3D WEBGL · INTERACTIVE';
  return {
    update(result){
      flows.forEach((flow,i)=>{const allocation=result.allocations[i];flow.share=allocation.mw/result.requested;flow.tube.visible=allocation.mw>0;flow.mat.color.setHex(result.status==='GREEN'?(i?0x45e6a1:0x41d9ef):COLORS[result.status]);flow.mat.opacity=allocation.offline ? .12 : .85;
        const indicator=nodes.get(allocation.id).userData.loadIndicator;const h=Math.min(5,Math.max(.08,allocation.mw/Math.max(1,allocation.capacity)*5));indicator.scale.y=h;indicator.position.y=.1+h/2;indicator.material.color.setHex(allocation.offline?0xff6373:COLORS[result.status]);
        for(const dot of flow.particles)dot.scale.setScalar(.8+Math.min(allocation.mw/150,2));
        const label=labelElements.get(allocation.id);label.replaceChildren(document.createTextNode(allocation.name.replace(' Substation','').replace(' Station','')));const b=document.createElement('b');b.textContent=`${allocation.mw.toFixed(1)} MW`;label.append(b);
      });
      siteMat.color.setHex(COLORS[result.status]);siteRing.material.color.setHex(COLORS[result.status]);compute.scale.y=.8+Math.min(result.requested/500,1)*.9;
    },
    select(id){selected=id;for(const [key,div] of labelElements)div.classList.toggle('selected',key===id);const p=nodePositions.get(id);if(p&&!quantumMode){lookTarget=p.clone();cameraTarget=p.clone().add(new THREE.Vector3(14,20,24));}},
    home(){lookTarget=new THREE.Vector3(1,0,5);cameraTarget=new THREE.Vector3(24,29,37);},
    top(){lookTarget=new THREE.Vector3(1,0,5);cameraTarget=new THREE.Vector3(1,54,5.01);},
    rotate(value){controls.autoRotate=value&&!reducedMotion;},
    flow(stage){flowGroup.visible=stage>0;modelLines.visible=stage>0;},
    quantumStep(step){
      if(step===3){this.quantum(false);return;}
      this.quantum(true);qStage=step===1?-1:step===0?0:1;updateQuantum();
      const titles=['Uniform superposition','Phase flip: marked amplitudes change sign','Interference amplifies marked states'];
      caption.replaceChildren();const strong=document.createElement('strong');strong.textContent=titles[step];caption.append(strong,document.createTextNode('Archived pre-firm-N-1 simulation · aggregate state ordering is illustrative.'));
    },
    layer(name,value){({terrain:terrainMesh,lines:geoLines,distribution})[name].visible=value;},
    quantum(value){quantumMode=value;quantumWorld.visible=value;gridWorld.visible=!value;caption.hidden=!value;lookTarget=new THREE.Vector3(0,0,value?0:5);cameraTarget=value?new THREE.Vector3(24,29,30):new THREE.Vector3(24,29,37);},
    dispose(){alive=false;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();scene.traverse((o)=>{o.geometry?.dispose();if(o.material){for(const m of Array.isArray(o.material)?o.material:[o.material])m.dispose();}});renderer.dispose();labels.domElement.remove();renderer.domElement.remove();},
  };
}
