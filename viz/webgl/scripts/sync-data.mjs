import { readFile, writeFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';

const app = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repo = path.resolve(app, '../..');
const read = async (p) => JSON.parse(await readFile(path.join(repo, p), 'utf8'));
const run = {};
for (const key of ['site', 'grid_snapshot', 'candidate_plan', 'physics_result', 'certificate', 'sources']) {
  run[key] = await read(`docs/demo_run/${key}.json`);
}
const q = await read('docs/demo_run/quantum_search.json');
run.quantum = {
  generated_utc: q.generated_utc, backend: q.backend, space: q.space,
  marked: q.oracle.M, iterations: q.iterations,
  per_iteration: q.grover.per_iteration, resources: q.grover.resources,
  honesty: q.honesty,
};
run.flexibility = await read('data/l2/flex_headroom.json');
run.provenance = {
  geometry: 'OpenStreetMap contributors, ODbL; cached in data/l1.',
  planning: 'Transmission topology and substation headroom are planning assumptions from the saved run, not utility ratings or approved connections.',
  certificate: 'The saved Lean certificate covers the supplied evidence. Interactive scenario screening does not execute pandapower, PsiQDK, or Lean.',
  source_paths: ['docs/demo_run/', 'data/l2/flex_headroom.json', 'data/l1/osm_power_lines_alviso.geojson', 'viz/data/terrain/heightmap.json'],
};
const { lat, lon } = run.site;
const xy = (p) => [(p[0] - lon) * 111.32 * Math.cos(lat * Math.PI / 180), (p[1] - lat) * 111.32];
const raw = await read('data/l1/osm_power_lines_alviso.geojson');
const lines = [];
for (const feature of raw.features) {
  if (feature.geometry?.type !== 'LineString') continue;
  let segment = [];
  for (const point of feature.geometry.coordinates) {
    const [x, y] = xy(point);
    if (Math.abs(x) < 10 && Math.abs(y) < 10) segment.push(point);
    else { if (segment.length > 1) lines.push(segment); segment = []; }
  }
  if (segment.length > 1) lines.push(segment);
}
const original = await read('viz/data/terrain/heightmap.json');
const n = 65;
const terrain = { n, origin: original.origin, x_min: original.x_min, x_max: original.x_max,
  y_min: original.y_min, y_max: original.y_max, source: original.source, attribution: original['license/attribution'],
  water_note: original.water_note, heights: [] };
for (let row = 0; row < n; row++) for (let col = 0; col < n; col++) {
  const r = Math.round(row / (n - 1) * (original.ny - 1));
  const c = Math.round(col / (n - 1) * (original.nx - 1));
  terrain.heights.push(original.heights[r * original.nx + c]);
}
const dest = path.join(app, 'public/data');
await mkdir(dest, { recursive: true });
await writeFile(path.join(dest, 'run.json'), JSON.stringify(run));
await writeFile(path.join(dest, 'geography.json'), JSON.stringify({ lines, terrain }));
console.log(`Synced saved run, ${lines.length} OSM line segments and ${n}×${n} terrain samples.`);
