"""One-screen demo summary: terminal text + report/summary.html (offline, no external JS/CSS).

Reads the latest runs/<timestamp>/ pipeline output and runs/scenarios/growth_alviso.json
(computed on the fly when missing). Usage: python report/summary.py [run_dir]
"""
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from report import labels  # noqa: E402
from scenarios import growth_alviso  # noqa: E402

NEVER = "Never claimed: quantum advantage; utility or PG&E approval; real substation ratings where we assumed them; numbers we did not run."
BASE, STRESS = "baseline_grip_2028", "stress_plus20pct_assumed"


def newest(name, runs=None):
    """Newest runs/<timestamp>/ directory containing `name` (pipeline and edge runs write separate dirs), else None."""
    hits = sorted((runs or ROOT / "runs").glob(f"2*/{name}"))
    return hits[-1].parent if hits else None


def latest_run():
    run = newest("certificate.json")
    if run is None:
        sys.exit("no runs/<timestamp>/ found: run `python pipeline.py` first")
    return run


def load(run_dir, runs=None):
    run_dir = Path(run_dir)
    d = {n: json.loads((run_dir / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("site", "candidate_plan", "physics_result", "certificate", "grid_snapshot", "sources")}
    rj = run_dir / "rounds.json"
    d["rounds"] = json.loads(rj.read_text(encoding="utf-8")) if rj.exists() else []
    sc = growth_alviso.OUT
    d["growth"] = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else growth_alviso.run()
    edge = newest("edge_alviso.json", runs)
    d["edge"] = json.loads((edge / "edge_alviso.json").read_text(encoding="utf-8")) if edge else None
    socio = ROOT / "data/shared/socio/alviso.json"
    d["socio"] = json.loads(socio.read_text(encoding="utf-8")) if socio.exists() else None
    d["run_dir"] = run_dir
    return d


def clip(x, n=110):
    return x if len(x) <= n else x[:n - 3] + "..."


def edge_section(e):
    if not e:
        return ["not run: `python scenarios/edge_alviso.py`"]
    rows = [["round", "edge sites (MW)", "L3 cert", "bank rule", "verdict", "blocking"]] + [
        [str(r["round"]), ", ".join(f"{n} {mw:g}" for n, mw in r["edge_sites"]), r["l3_certificate"],
         "pass" if r["bank_rule"]["pass"] else "FAIL", r["verdict"], r["blocking"] or "-"] for r in e["rounds"]]
    return [f"Edge-site case ({e['site']['requested_mw']:g} MW on distribution feeders): "
            f"naive feeder-sum capacity {e['naive_feeder_capacity_mw']:g} MW vs bank-aware {e['bank_capacity_mw_0pct']:g} MW at 0% curtailment (GRIP, directional)",
            rows]


def consent_section(c):
    if not c:
        return ["data/shared/socio/alviso.json missing"]
    top = sorted(c["items"], key=lambda i: -i["weight"])[:3]
    return ([f"Consent score {c['consent_score']} ({c['verdict']}); {c['verdict_note']}", "Top 3 items by weight:"]
            + [f"  [{i['effect']}] w={i['weight']} {i['type']}: {i['id']}" for i in top]
            + ["Amber conditions:"] + [f"  - {a}" for a in c["amber_conditions"]])


def sections(d):
    site, plan, phys, cert, snap = d["site"], d["candidate_plan"], d["physics_result"], d["certificate"], d["grid_snapshot"]
    names = {s["id"]: s.get("name", s["id"]) for s in snap["substations"]}
    g = d["growth"]["scenarios"]
    mw = lambda sc, p: g[sc]["by_curtailment_pct"][p]["distribution_mw"]  # noqa: E731
    cur = plan["flex"]
    flex = ", ".join(k.replace("_", " ") + f" {v}" for k, v in cur.items() if v) or "none"
    stale = [k for k, v in d["sources"].items() if v == "FIXTURE"]
    return [
        ("The question", [f"Can {site['name']} get {site['requested_mw']} MW by {site['deadline']}?"]),
        ("Verdict", [f"RESULT: {labels.verdict_label(cert['result'])}" + (f" (blocked by {cert['blocking_condition']})" if cert["blocking_condition"] else "")]
         + [f"Certificate engine: {labels.cert_engine(cert)}", f"Rules covered: {labels.RULES_LABEL}"]
         + [f"{'PASS' if c['pass'] else 'FAIL'}  {c['name']}" for c in cert["checks"]]),
        ("The plan", [f"{names.get(s['substation_id'], s['substation_id'])}: {s['mw']:.1f} MW" for s in plan["splits"]]
         + [f"Flex levers: {flex}", f"Search engine: {labels.search_engine(plan)}, {plan['search']['evals']} evals"]),
        ("Feedback loop 1: transmission case (" + f"{site['requested_mw']} MW, propose -> physics -> certify)", [
            [["round", "verdict", "blocking rule", "evals", "plan"]]
            + [[str(r["round"]), r["verdict"], r["blocking_rule"] or "-", str(r["evals"]), r["plan"] + (f" ({r['stopped']})" if r.get("stopped") else "")]
               for r in d["rounds"]]] if d["rounds"] else ["single pass (no rounds.json)"]),
        ("Feedback loop 2: edge-site case (distribution feeders, bank rule)", edge_section(d["edge"])),
        ("Physics (pandapower)", [f"Converged: {phys['converged']}   Max line loading: {phys['max_line_loading_pct']}%",
                                  f"Voltage: {phys['v_min_pu']} to {phys['v_max_pu']} pu   N-1: {'pass' if phys['n1_pass'] else 'FAIL'}"]),
        ("Growth table: distribution headroom near Alviso", [
            "Data: " + labels.DATA_LABEL,
            f"{mw(BASE, '0'):.1f} MW firm on the local distribution grid; the rest needs transmission (7-10 years)",
            f"{mw(BASE, '2'):.1f} MW if the site accepts curtailment in ~2% of hours (98% availability)",
            [["scenario", "0%", "2%", "5%", "10%", "banks at 0 MW (0%)"]]
            + [[name, *(f"{mw(sc, p):.1f} MW" for p in ("0", "2", "5", "10")), str(len(g[sc]["by_curtailment_pct"]["0"]["banks_at_zero"]))]
               for name, sc in (("baseline GRIP 2028", BASE), ("ASSUMED +20% load", STRESS))],
            f"At +20%, {len(g[STRESS]['by_curtailment_pct']['0']['banks_at_zero'])} banks have 0 MW firm headroom "
            f"(baseline {len(g[BASE]['by_curtailment_pct']['0']['banks_at_zero'])}).",
        ]),
        ("Consent layer (Alviso; ASSUMED weights, heuristic, not a validated model)", consent_section(d["socio"])),
        ("Scope", [NEVER, "Headroom/connectivity/ratings are " + labels.DATA_LABEL + ". +20% is an assumed stress scenario, not a utility forecast."]
         + ([f"NOTE: stages using synthetic fixtures, not live results: {', '.join(stale)}"] if stale else [])),
    ]


def text_table(rows):
    w = [max(len(clip(c)) for c in col) for col in zip(*rows)]
    return ["  " + "  ".join(clip(c).ljust(n) for c, n in zip(r, w)).rstrip() for r in rows]


def to_text(secs, run_dir):
    out = ["QSITEPROOF DEMO SUMMARY  (" + Path(run_dir).name + ")", "=" * 72]
    for h, lines in secs:
        out += ["", h.upper()]
        for x in lines:
            out += text_table(x) if isinstance(x, list) else ["  " + x]
    return "\n".join(out)


def html_item(x):
    if not isinstance(x, list):
        return f"<li class='{x.split()[0].lower() if x.split()[0] in ('PASS', 'FAIL') else ''}'>{html.escape(x)}</li>"
    cell = lambda t, c: f"<{t}>{html.escape(c)}</{t}>"  # noqa: E731
    return ("<li><table>" + "".join("<tr>" + "".join(cell("th" if i == 0 else "td", c) for c in r) + "</tr>" for i, r in enumerate(x))
            + "</table></li>")


def to_html(secs, run_dir):
    body = []
    for h, lines in secs:
        items = "".join(html_item(x) for x in lines)
        extra = " verdict" if h == "Verdict" else ""
        body.append(f"<section class='{extra.strip()}'><h2>{html.escape(h)}</h2><ul>{items}</ul></section>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>QSiteProof demo summary</title><style>"
            "body{font:22px/1.4 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px 24px;background:#fff;color:#111}"
            "h1{font-size:34px;margin:8px 0}h2{font-size:24px;margin:20px 0 6px;border-bottom:2px solid #ccc}"
            "ul{list-style:none;padding:0;margin:0}li{padding:2px 0}li.pass{color:#0a7a2f}li.fail{color:#b00020;font-weight:700}li.pass,li.fail{font-size:20px}"
            "table{border-collapse:collapse;font-size:16px}th,td{border:1px solid #ccc;padding:3px 8px;text-align:left;vertical-align:top}th{background:#eee}"
            ".verdict li:first-child{font-size:32px;font-weight:700}small{color:#555}"
            "</style></head><body><h1>QSiteProof</h1><small>run " + html.escape(Path(run_dir).name) + "</small>"
            + "".join(body) + "</body></html>")


def main():
    d = load(sys.argv[1] if len(sys.argv) > 1 else latest_run())
    secs = sections(d)
    print(to_text(secs, d["run_dir"]))
    out = Path(__file__).with_name("summary.html")
    out.write_text(to_html(secs, d["run_dir"]), encoding="utf-8")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
