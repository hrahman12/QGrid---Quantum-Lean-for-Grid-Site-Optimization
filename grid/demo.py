"""site -> snapshot -> one hand-made plan -> physics. Run: python grid/demo.py [site_id]"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from grid.physics import check  # noqa: E402
from grid.snapshot import get_snapshot  # noqa: E402

sites = {s["id"]: s for s in json.loads((ROOT / "data/l1/sites.json").read_text(encoding="utf-8"))}
site = sites[sys.argv[1] if len(sys.argv) > 1 else "nsj-alviso-150"]
snap = get_snapshot(site)
subs = snap["substations"]
print(f"{site['name']}: {site['requested_mw']} MW, ISO {snap['iso']['source']} load={snap['iso']['load']} lmp={snap['iso']['lmp']}")
for s in subs:
    print(f"  {s['id']:20} {s['kv']:5.0f} kV {s['distance_km']:5.1f} km headroom {s['headroom_mw']:6.1f} MW  {s['name']}")

# hand-made plan: spread the request pro-rata to headroom across all candidates
total_head = sum(s["headroom_mw"] for s in subs)
plan = {"splits": [{"substation_id": s["id"], "mw": round(site["requested_mw"] * s["headroom_mw"] / total_head, 1)} for s in subs],
        "flex": {"dlr": False, "storage_mw": 0, "curtailment_mw": 0, "reconductor": False},
        "search": {"method": "heuristic", "evals": 1}}
for label, flex in (("no flex", plan["flex"]),
                    ("DLR + 20 MW storage", {**plan["flex"], "dlr": True, "storage_mw": 20})):
    plan["flex"] = flex
    r = check(plan, snap)
    print(f"[{label}] splits={[(x['substation_id'][4:], x['mw']) for x in plan['splits']]}")
    print(json.dumps(r, indent=1)[:900])
