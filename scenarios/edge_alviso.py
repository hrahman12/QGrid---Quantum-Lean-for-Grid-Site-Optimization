"""Edge-site case (Track 1): can a portfolio of 0.5-10 MW edge sites connect at PG&E DISTRIBUTION near Alviso?

Runs Hannah's L3 stages unchanged, round by round:
  quantum.search.propose(site, snapshot, constraints)   PsiQDK/numpy Grover over 25% splits x DLR x storage x curtailment
  grid.physics.check(plan, snapshot)                    pandapower + N-1 on the transmission snapshot
  lean.certify.certify(plan, physics, site, snapshot=)  Lean 4 (or its python mirror) over the encoded rules
plus the per-bank rule this case is about (data/l2/l3_inputs.json, GRIP layer 31 feeder->bank links):

  NAIVE view   each feeder is a node with headroom = its GRIP load hosting (edge_site_max_mw).
               Feeder capacity sums to ~430 MW, so a feeder-level search happily places MW.
  BANK RULE    MW on all feeders of one transformer bank <= that bank's GRIP cap (38.8 MW in total at 0%
               curtailment; feeder hosting is NOT additive). HARD. Its blocking condition names the bank's
               feeders, and Hannah's parse_constraints() excludes every node it names in the next round.

Physics: the edge sites' MW is booked on the nearest >=230 kV snapshot substation (the 230/115 kV source,
ASSUMED), so the pandapower model sees the load; distribution-feeder power flow is not modelled here.

Usage: python scenarios/edge_alviso.py [--mw 16] [--rounds 20]
Writes runs/<UTC>/edge_alviso.json. Numbers come only from this run. GREEN covers the encoded rules only;
not a PG&E approval.
"""
from __future__ import annotations

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QSITE_OFFLINE", "1")

from grid.physics import check as physics_check  # noqa: E402
from grid.snapshot import get_snapshot  # noqa: E402
from lean.certify import certify  # noqa: E402
from quantum.search import propose  # noqa: E402

L3 = json.loads((ROOT / "data" / "l2" / "l3_inputs.json").read_text(encoding="utf-8"))


def km(a, b):
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    x = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(b["lon"] - a["lon"]) / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(x))


def feeder_snapshot(site, trans):
    """Distribution snapshot for Hannah's search: one node per GRIP feeder that can take a 25% share
    (the NAIVE capacity view). Smaller feeders are left out so the K nearest always fit at feeder level
    and the plan space stays small; the bank rule does the pruning."""
    nodes = []
    quarter = site["requested_mw"] / 4
    for f in L3["feeders"]:
        if not f["eligible_edge_site"] or not f["bank_id"] or f["edge_site_max_mw"] < quarter:
            continue
        nodes.append({"id": f"feeder-{f['feeder_id']}", "name": f["feeder"], "lat": f["lat"], "lon": f["lon"],
                      "kv": 21.0, "assumed_mva": round(f["edge_site_max_mw"] / 0.95, 3),
                      "distance_km": f["distance_km"], "headroom_mw": f["edge_site_max_mw"],
                      "bank_id": f["bank_id"], "substation": f["substation"], "flood_sfha": f["flood_sfha"]})
    return {"site_id": site["id"], "substations": nodes, "lines": [], "iso": trans["iso"],
            "dlr_uplift_pct": 0.0,  # DLR is a transmission-line lever; it does not raise feeder hosting
            "assumptions": ["NAIVE distribution view: node = GRIP feeder, headroom_mw = GRIP max load hosting (data/l2/l3_inputs.json)"]}


def bank_rule(plan, nodes):
    """HARD: sum of MW on the feeders of each bank <= bank cap at the plan's curtailment level."""
    by_id = {n["id"]: n for n in nodes}
    req = sum(s["mw"] for s in plan["splits"]) or 1.0
    pct = round(100 * plan["flex"]["curtailment_mw"] / req) if req else 0
    key = min(("0", "1", "2", "5", "10"), key=lambda k: abs(int(k) - pct))
    banks = {b["bank_id"]: b for b in L3["banks"]}
    load = {}
    for s in plan["splits"]:
        if s["mw"] > 0:
            load.setdefault(by_id[s["substation_id"]]["bank_id"], []).append(s)
    over = []
    for bid, ss in load.items():
        b = banks[bid]
        cap = (b["cap_mw_by_curtailment_pct"].get(key) if b["has_forecast"] else None) or 0.0
        mw = round(sum(x["mw"] for x in ss), 2)
        if mw > cap + 0.01:
            feeders = sorted({by_id[x["substation_id"]]["name"] for x in ss})
            ids = sorted({x["substation_id"] for x in ss})
            over.append((b, mw, cap, feeders, ids))
    if not over:
        return {"name": "bank_cap", "pass": True, "kind": "hard",
                "detail": f"every transformer bank within its GRIP cap at {key}% curtailment"}, None
    b, mw, cap, feeders, ids = max(over, key=lambda t: t[1] - t[2])
    detail = (f"{b['bank']} ({b['bank_id']}) carries {mw} MW on {', '.join(feeders)} > GRIP cap {cap} MW "
              f"at {key}% curtailment; feeder hosting is not additive"
              + (f" (+{len(over) - 1} more bank(s) over cap)" if len(over) > 1 else ""))
    # learned constraint per over-cap bank: a FULL bank (room < one 25% share) -> exclude all its feeders;
    # a PARTLY full bank -> keep floor(cap/share) of its feeders (largest hosting), exclude the rest, and
    # cap each kept feeder's headroom at cap/kept (applied by the caller through `limits`)
    share = req / 4
    excl, limits = [], {}
    for bk, _mw, cap_b, _f, _i in over:
        feeders_b = sorted((n for n in nodes if n["bank_id"] == bk["bank_id"]), key=lambda n: -n["headroom_mw"])
        keep = int(cap_b // share) if share > 0 else 0
        excl += [n["id"] for n in feeders_b[keep:]]
        for n in feeders_b[:keep]:
            limits[n["id"]] = round(cap_b / keep, 3)
    # constraint text names ONLY the ids to exclude (Hannah's parser also matches node names, so feeder
    # names that should stay available must not appear in it)
    banks_txt = ", ".join(f"{o[0]['bank_id']} {o[1]}>{o[2]} MW" for o in over)
    constraint = f"bank_cap over GRIP cap ({banks_txt}); exclude: {' '.join(excl)}"
    return {"name": "bank_cap", "pass": False, "kind": "hard", "detail": detail, "limits": limits}, constraint


def transmission_plan(plan, nodes, trans):
    """Book each edge site's MW on the nearest >=230 kV snapshot substation for the pandapower check."""
    by_id = {n["id"]: n for n in nodes}
    src = [s for s in trans["substations"] if s["kv"] >= 230] or trans["substations"]
    book = {}
    for s in plan["splits"]:
        if s["mw"] <= 0:
            continue
        up = min(src, key=lambda t: km(t, by_id[s["substation_id"]]))
        book[up["id"]] = book.get(up["id"], 0.0) + s["mw"]
    return {**plan, "splits": [{"substation_id": k, "mw": round(v, 3)} for k, v in book.items()] or plan["splits"],
            "flex": {**plan["flex"], "dlr": False}}


def run(mw=16.0, rounds=20, out_root=None):
    base = json.loads((ROOT / "fixtures" / "site.json").read_text(encoding="utf-8"))
    trans = get_snapshot(base)
    site = {**base, "id": base["id"] + "-edge", "requested_mw": mw,
            "name": f"Alviso edge-site portfolio ({mw} MW as 0.5-10 MW sites at PG&E distribution)"}
    snap = feeder_snapshot(site, trans)
    nodes = snap["substations"]
    naive_feeder_mw = round(sum(n["headroom_mw"] for n in nodes), 1)
    bank_mw = L3["summary"]["distribution_cap_mw_by_curtailment_pct"]["0"]
    # Edge sites carry no on-site battery here. Also: with storage >= the request, the search oracle's
    # net factor (1 - storage/requested) hits 0 and marks every split, while certify checks raw splits.
    rows, constraints, final = [], ["no storage at edge sites (storage_mw must be 0)"], None
    limits = {}  # learned per-feeder headroom caps from partly full banks
    import time
    for r in range(1, rounds + 1):
        t0 = time.time()
        # constraints go to Hannah's parser unchanged (it records how each is applied); nodes it would exclude
        # are also dropped from the candidate list so K stays small instead of widening every round
        from quantum.oracle import parse_constraints
        excluded = parse_constraints(constraints, nodes).excluded_substations
        live = {**snap, "substations": [{**n, "headroom_mw": min(n["headroom_mw"], limits.get(n["id"], n["headroom_mw"]))}
                                        for n in nodes if n["id"] not in excluded]}
        plan = propose(site, live, constraints)
        print(f"  [round {r}: search {time.time() - t0:.1f}s, {plan['search']['method']}]", flush=True)
        phys = physics_check(transmission_plan(plan, nodes, trans), trans)
        cert = certify(plan, phys, site, snapshot=live, write_evidence=False)
        brule, new_c = bank_rule(plan, nodes)
        flood = sorted({nodes_by["name"] for s in plan["splits"] if s["mw"] > 0
                        for nodes_by in [next(n for n in nodes if n["id"] == s["substation_id"])] if nodes_by["flood_sfha"]})
        flex_used = plan["flex"]["storage_mw"] > 0 or plan["flex"]["curtailment_mw"] > 0
        if cert["result"] == "RED":
            verdict, blocking = "RED", cert["blocking_condition"]
        elif not brule["pass"]:
            verdict, blocking = "RED", "bank_cap: " + brule["detail"]
        elif flood or flex_used:
            verdict, blocking = "AMBER", ("flood: elevate above BFE 12 ft at " + ", ".join(flood)) if flood else "flex commitment (storage/curtailment)"
        else:
            verdict, blocking = "GREEN", None
        sites = [(next(n["name"] for n in nodes if n["id"] == s["substation_id"]), s["mw"]) for s in plan["splits"] if s["mw"] > 0]
        rows.append({"round": r, "constraints_in": len(constraints), "method": plan["search"]["method"],
                     "evals": plan["search"]["evals"], "edge_sites": sites,
                     "flex": plan["flex"], "physics": {k: phys[k] for k in ("converged", "max_line_loading_pct", "n1_pass")},
                     "l3_certificate": cert["result"], "bank_rule": brule, "verdict": verdict, "blocking": blocking})
        if verdict == "RED" and r > 1 and rows[-1]["edge_sites"] == rows[-2]["edge_sites"] if len(rows) > 1 else False:
            rows[-1]["blocking"] = (rows[-1]["blocking"] or "") + " | STOP: search found no new feasible plan in this space (try a smaller portfolio or curtailment)"
            break
        if verdict == "RED" and new_c:
            constraints.append(new_c)
            limits.update(brule.get("limits", {}))
        elif verdict == "RED":
            constraints.append(cert["blocking_condition"] or blocking)
        else:
            final = rows[-1]
            break
    out = {"site": site, "naive_feeder_capacity_mw": naive_feeder_mw, "bank_capacity_mw_0pct": bank_mw,
           "bank_capacity_mw_by_curtailment_pct": L3["summary"]["distribution_cap_mw_by_curtailment_pct"],
           "rounds": rows, "final": final,
           "note": "Hannah's propose()/certify() unchanged; bank rule from data/l2/l3_inputs.json (GRIP). Directional; not a PG&E approval."}
    run_dir = Path(out_root or ROOT / "runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "edge_alviso.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"EDGE-SITE CASE  {site['name']}")
    print(f"  naive feeder view: {naive_feeder_mw} MW of feeder hosting | transformer-bank caps: {bank_mw} MW "
          f"(0% curtailment), {L3['summary']['distribution_cap_mw_by_curtailment_pct']['2']} MW at 2%")
    print("  round  search(evals)   edge sites (MW)                                               physics     L3 cert  bank rule  VERDICT")
    for x in rows:
        s = ", ".join(f"{n} {m:g}" for n, m in x["edge_sites"])
        ph = f"{x['physics']['max_line_loading_pct']}% N-1 {'ok' if x['physics']['n1_pass'] else 'FAIL'}"
        print(f"  {x['round']:>5}  {x['method']:>7}({x['evals']:>4})  {s[:60]:<60}  {ph:<11} {x['l3_certificate']:<7}  "
              f"{'PASS' if x['bank_rule']['pass'] else 'FAIL':<9}  {x['verdict']}")
        if x["blocking"]:
            print(f"         -> {x['blocking'][:150]}")
    print(f"  wrote {run_dir / 'edge_alviso.json'}")
    return out


if __name__ == "__main__":
    a = sys.argv[1:]
    mw = float(a[a.index("--mw") + 1]) if "--mw" in a else 16.0
    n = int(a[a.index("--rounds") + 1]) if "--rounds" in a else 20
    run(mw, n)
