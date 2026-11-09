# QGrid WebGL explorer

A single-screen, four-panel Three.js planning workbench for the saved North San Jose / Alviso case. The blue, cyan, green, amber, and steel palette follows QGrid's project identity.

## Run

```sh
npm ci
npm run dev
```

From the repository root, also run `python -m viz.webgl.server.local_api` in a second terminal for the native execution endpoint. On Windows, the worker uses Ubuntu WSL and the existing `~/qsite-venv` environment. On Linux/macOS, install `psiqdk==2.5.0` in the API Python environment. Open the Local URL printed by Vite. `npm test` checks the scenario evaluator; `npm run build` creates `dist/`.

## Explore

- **In:** orbit, zoom, and select substations in the live-rendered 3D grid; set the site load, growth, and deadline.
- Adjust 11 numerical controls, five obligation toggles, and a source-outage selector. The eight screening checks, allocation labels, power-flow animation, and GREEN / AMBER / RED verdict update immediately.
- Use Baseline, Flexible, Conditional, and Stressed presets, or export and re-import a scenario JSON file.
- **Find:** Run PsiQDK sends a bounded job to `/api/quantum`. It runs the actual `quantum.grover_psiqdk` circuit with the repository oracle, samples 32 shots, selects a measured feasible candidate, and returns native superposition, phase-flip, amplified states, package versions, cross-checks, and resource estimates. The 3D quantum-computer visual runs while the request is active. No NumPy execution fallback is accepted.
- **Check:** orbit a transmission-span view with current pulses proportional to allocated route MW, thermal-screen colors, and stopped flow for an offline source. The spans and temperature-driven sag are illustrative geometry; they do not solve conductor temperature or new AC physics. Inspect the capacity, thermal, and firm N-1 screens below.
- **Prove:** inspect the actual `verdict_green_iff_all` theorem from `lean/QSiteProof/Basic.lean` in a Lean editor card, scenario assumptions, and rule status. The earlier archived Lean certificate is retained only as a superseded record. A changed scenario needs a new Lean run; a new formal certificate is not claimed.
- View Model & sources for the complete screening equations, assumptions, provenance, and jurisdiction caveats.

## Scope

The overall browser color follows the Lean rules: **RED if any hard rule (capacity, thermal, firm N-1) fails; AMBER if only negotiable conditions are unmet; GREEN when all 8 pass**. This display does not alter the actual pipeline or Lean verdict. The 150 MW baseline has seven passing screens and one blocking firm N-1 check, so its browser display is RED, matching the transmission pipeline result under the recorded 19.9 MW firm cap per selected source. DLR and reconductoring do not inflate those caps. The Flexible preset reduces net demand to 30 MW and passes the browser screen. The older GREEN certificate is retained only as a superseded historical record.

The sliders update an analytical sensitivity screen. **Run PsiQDK does execute the native PsiQDK Workbench simulator**, using at most eight register qubits and 32 shots per bounded request. This is a classical simulation of a fault-tolerant quantum circuit, not a quantum-hardware run; the oracle marking list is classically enumerated, so no quantum advantage is claimed. The browser Check / Prove screens do **not** execute pandapower or Lean and do not issue a new formal certificate or utility approval. The saved Lean result and its evidence hash remain separate from the scenario state.

Real geographic inputs come from the repository's cached OSM line/substation geometry and Terrain Tiles elevation. Equipment geometry and proposed routes are visual abstractions. Transmission topology, headroom, upgrade factors, deadline assumptions, battery support, and flood protection are scoped as model assumptions. The distribution curve comes from the cached PG&E GRIP analysis and remains directional.

`npm run data:sync` refreshes `public/data/` from `docs/demo_run/`, `data/l2/flex_headroom.json`, the cached OSM lines, and the terrain heightmap. The checked-in snapshot lets production builds work independently of Python or live APIs.

## Vercel

Import the QGrid GitHub repository into Vercel using its repository root. The root `vercel.json` installs and builds this folder and serves `viz/webgl/dist`. No API keys or environment variables are required. Deploy the **repository root** so Vercel also builds `api/quantum.py`. The root `pyproject.toml` selects Python 3.12 and the native Linux PsiQDK package. The function includes only the necessary repository engine and cached snapshot, rejects non-PsiQDK execution, limits payload size, and serializes jobs within each function process. A static-only deployment cannot run the native quantum action.

## Quantum search semantics

The browser search uses the two displayed connection sources in 25% split steps. Battery and curtailment sliders become upper bounds for a discrete search; the returned measured plan may use less and replaces those candidate values only if the search inputs have not changed. Firm transformer caps remain fixed. DLR changes line assumptions, not firm transformer capacity. Reconductoring is passed through as a plan assumption rather than varied by the circuit. Downstream permitting / commitment changes do not invalidate a completed search.

The native-state view uses the actual returned statevector indices and measured histogram. The visual hardware is an illustrative photonic-computer concept.


### Card 2 workspace

One set of tabs contains all native-run views: **Grover amplitudes** (3D probability bars or a signed-amplitude plot), **Bloch spheres** for every register qubit, **Photonic concept** (animated dual-rail waveguides or the 3D computer), and **Counts** with the independent cross-check and measured candidate. The shared player covers superposition, the first phase flip, every returned Grover iteration, and observed measurements. Detector brightness comes from actual per-qubit shot counts; the chip layout, photon motion, and visual tweening are illustrative.

The validated recorded native run stays explicitly labeled with its original settings and timestamp. A successful live PsiQDK job replaces the record across all views; changing search inputs or the site marks it stale. Native search currently runs the bounded Alviso model, so other site cases cannot silently apply an Alviso candidate. Playback and photonics honor reduced motion, and WebGL resources are disposed on exit.
