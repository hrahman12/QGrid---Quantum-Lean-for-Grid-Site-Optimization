import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

// Illustrative spans: scenario MW, outage state, and thermal screening color.
// Geometry and its temperature response do not represent a solved conductor model.
export function createGridPhysics(container) {
  let renderer;
  try { renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true }); }
  catch { container.textContent = 'Transmission view unavailable. Physics screening remains usable.'; return { update() {}, dispose() {} }; }
  renderer.setPixelRatio(Math.min(devicePixelRatio, 1.5)); renderer.setClearColor(0x091725, 0);
  renderer.toneMapping = THREE.ACESFilmicToneMapping; container.append(renderer.domElement);
  const scene = new THREE.Scene(), camera = new THREE.PerspectiveCamera(35, 1, .1, 100);
  camera.position.set(7, 5.8, 10);
  const controls = new OrbitControls(camera, renderer.domElement);
  controls.target.set(0, 1.7, 0); controls.enableDamping = true; controls.enablePan = false;
  controls.minDistance = 8; controls.maxDistance = 20; controls.maxPolarAngle = Math.PI * .48;
  scene.add(new THREE.HemisphereLight(0xd3edff, 0x122c3d, 3));
  const light = new THREE.DirectionalLight(0xe5efff, 3); light.position.set(0, 7, 5); scene.add(light);
  const ground = new THREE.Mesh(new THREE.BoxGeometry(9, .12, 4.7), new THREE.MeshStandardMaterial({ color: 0x142d3a, roughness: .9 }));
  ground.position.y = -.12; scene.add(ground);
  const grid = new THREE.GridHelper(9, 18, 0x315166, 0x203e4e); grid.position.y = -.05; scene.add(grid);
  const steel = new THREE.MeshStandardMaterial({ color: 0x7898ac, metalness: .75, roughness: .4 });
  const insulator = new THREE.MeshStandardMaterial({ color: 0x91c9c5, metalness: .15, roughness: .4 });
  const barGeometry = new THREE.CylinderGeometry(.024, .024, 1, 5);
  function beam(a, b, material = steel) {
    const start = new THREE.Vector3(...a), end = new THREE.Vector3(...b), v = end.clone().sub(start);
    const mesh = new THREE.Mesh(barGeometry, material); mesh.position.copy(start).add(end).multiplyScalar(.5);
    mesh.scale.y = v.length(); mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0, 1, 0), v.normalize()); scene.add(mesh);
  }
  function tower(x, z) {
    for (const side of [-1, 1]) {
      beam([x + side*.5, 0, z], [x + side*.13, 3.5, z]);
      beam([x, 0, z + side*.38], [x, 3.5, z + side*.1]);
    }
    for (let y = .15; y < 2.9; y += .65) {
      const w = .5 - y*.1, next = .5 - (y+.65)*.1;
      beam([x-w,y,z],[x+next,y+.65,z]); beam([x+w,y,z],[x-next,y+.65,z]);
    }
    for (const y of [2.75, 3.4]) {
      beam([x,y,z-.65],[x,y,z+.65]);
      beam([x,y-.4,z],[x,y,z-.65]); beam([x,y-.4,z],[x,y,z+.65]);
    }
    for (const dz of [-.55, 0, .55]) beam([x,3.4,z+dz],[x,3.13,z+dz],insulator);
  }
  const routes = [-1.15, 1.15].map(z => {
    tower(-3.35,z); tower(3.35,z);
    const material = new THREE.LineBasicMaterial({ color: 0x49dca6 });
    const wires = [-.55,0,.55].map(dz => {
      const geometry = new THREE.BufferGeometry(); geometry.setAttribute('position',new THREE.BufferAttribute(new Float32Array(49*3),3));
      const line = new THREE.Line(geometry,material); scene.add(line); return {line,z:z+dz};
    });
    const pulseMaterial = new THREE.MeshBasicMaterial({ color: 0x9dffe3 });
    const particles = Array.from({length:6},() => {const p=new THREE.Mesh(new THREE.SphereGeometry(.055,6,6),pulseMaterial);scene.add(p);return p;});
    return {wires,material,particles,z,mw:0,offline:false,sag:.5};
  });
  function point(t,z,sag) {
    const span=6.7, a=span*span/(8*sag), x=(t-.5)*span;
    return new THREE.Vector3(x,3.13 + a*(Math.cosh(x/a)-Math.cosh(span/(2*a))),z);
  }
  const resize = () => {const w=container.clientWidth,h=container.clientHeight;if(!w||!h)return;renderer.setSize(w,h);camera.aspect=w/h;camera.updateProjectionMatrix();};
  const observer=new ResizeObserver(resize); observer.observe(container); resize();
  let frame,alive=true; const reduced=matchMedia('(prefers-reduced-motion: reduce)').matches;
  function draw() {
    if(!alive)return;frame=requestAnimationFrame(draw);controls.update();const time=performance.now()/1000;
    for(const route of routes)route.particles.forEach((p,i)=>{
      p.visible=!reduced&&!route.offline&&route.mw>.01;
      p.position.copy(point((time*(.08+Math.min(route.mw,200)/450)+i/6)%1,route.z,route.sag));
    });
    renderer.render(scene,camera);
  }
  draw();
  return {
    update(result) {
      const thermal=result.checks.find(c=>c.id==='thermal').status;
      routes.forEach((route,i)=>{
        const a=result.allocations[i];route.mw=a.mw;route.offline=a.offline;route.sag=.38+(result.settings.temperature-10)*.012;
        route.material.color.setHex(a.offline?0x3b4e60:thermal==='RED'?0xfa7081:thermal==='AMBER'?0xffbd4c:0x47dca2);
        route.wires.forEach(({line,z})=>{const attr=line.geometry.attributes.position;for(let j=0;j<attr.count;j++){const p=point(j/(attr.count-1),z,route.sag);attr.setXYZ(j,p.x,p.y,p.z);}attr.needsUpdate=true;line.geometry.computeBoundingSphere();});
      });
    },
    dispose() {alive=false;cancelAnimationFrame(frame);observer.disconnect();controls.dispose();const geometries=new Set(),materials=new Set();scene.traverse(o=>{if(o.geometry)geometries.add(o.geometry);if(o.material)materials.add(o.material);});geometries.forEach(g=>g.dispose());materials.forEach(m=>m.dispose());renderer.dispose();container.replaceChildren();},
  };
}
