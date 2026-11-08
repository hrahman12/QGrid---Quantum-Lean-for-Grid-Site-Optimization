# QGrid WebGL explorer

A Three.js planning workbench for the saved North San Jose / Alviso case. The blue, cyan, green, amber, and steel palette follows QGrid's project identity.

## Run

```sh
npm ci
npm run dev
```

Open the Local URL printed by Vite. `npm test` checks the scenario evaluator; `npm run build` creates `dist/`.

## Explore

- Orbit, zoom, select substations, switch to a top-down camera, and toggle terrain, OSM line geometry, or GRIP nodes.
- Adjust 11 numerical controls, five obligation toggles, and a source-outage selector. The eight screening checks, allocation labels, power-flow animation, and GREEN / AMBER / RED verdict update immediately.
- Use Baseline, Flexible, Conditional, and Stressed presets, or export and re-import a scenario JSON file.
- Play the saved Find / Check / Prove walkthrough, inspect aggregate Grover probabilities, and open or download the immutable saved Lean certificate.
- View Model & sources for the complete screening equations, assumptions, provenance, and jurisdiction caveats.

## Scope

The browser evaluator is an analytical sensitivity screen. It does **not** execute pandapower, PsiQDK, or Lean and it does not issue a formal certificate or utility approval. The saved Lean result and its evidence hash remain separate from the scenario state.

Real geographic inputs come from the repository's cached OSM line/substation geometry and Terrain Tiles elevation. Equipment geometry and proposed routes are visual abstractions. Transmission topology, headroom, upgrade factors, deadline assumptions, battery support, and flood protection are scoped as model assumptions. The distribution curve comes from the cached PG&E GRIP analysis and remains directional.

`npm run data:sync` refreshes `public/data/` from `docs/demo_run/`, `data/l2/flex_headroom.json`, the cached OSM lines, and the terrain heightmap. The checked-in snapshot lets production builds work independently of Python or live APIs.

## Vercel

Import the QGrid GitHub repository into Vercel using its repository root. The root `vercel.json` installs and builds this folder and serves `viz/webgl/dist`. No API keys or environment variables are required. The nested `vercel.json` also supports deploying `viz/webgl` directly from the CLI.
