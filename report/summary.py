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
from scenarios import growth_alviso  # noqa: E402

NEVER = "Never claimed: quantum advantage; utility or PG&E approval; real substation ratings where we assumed them; numbers we did not run."
BASE, STRESS = "baseline_grip_2028", "stress_plus20pct_assumed"


def latest_run():
    runs = sorted(p for p in (ROOT / "runs").glob("2*") if p.is_dir())
    if not runs:
        sys.exit("no runs/<timestamp>/ found: run `python pipeline.py` first")
    return runs[-1]


def load(run_dir):
    run_dir = Path(run_dir)
    d = {n: json.loads((run_dir / f"{n}.json").read_text(encoding="utf-8"))
         for n in ("site", "candidate_plan", "physics_result", "certificate", "grid_snapshot", "sources")}
    sc = growth_alviso.OUT
    d["growth"] = json.loads(sc.read_text(encoding="utf-8")) if sc.exists() else growth_alviso.run()
    d["run_dir"] = run_dir
    return d


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
        ("Verdict", [f"RESULT: {cert['result']}" + (f" (blocked by {cert['blocking_condition']})" if cert["blocking_condition"] else "")]
         + [f"{'PASS' if c['pass'] else 'FAIL'}  {c['name']}" for c in cert["checks"]]),
        ("The plan", [f"{names.get(s['substation_id'], s['substation_id'])}: {s['mw']:.1f} MW" for s in plan["splits"]]
         + [f"Flex levers: {flex}", f"Search: {plan['search']['method']}, {plan['search']['evals']} evals"]),
        ("Physics (pandapower)", [f"Converged: {phys['converged']}   Max line loading: {phys['max_line_loading_pct']}%",
                                  f"Voltage: {phys['v_min_pu']} to {phys['v_max_pu']} pu   N-1: {'pass' if phys['n1_pass'] else 'FAIL'}"]),
        ("Distribution headroom near Alviso (PG&E GRIP 2028, directional)", [
            f"{mw(BASE, '0'):.1f} MW firm on the local distribution grid; the rest needs transmission (7-10 years)",
            f"{mw(BASE, '2'):.1f} MW if the site accepts curtailment in ~2% of hours (98% availability)",
            f"Curve at 0/2/5/10% curtailment: " + " / ".join(f"{mw(BASE, p):.1f}" for p in ("0", "2", "5", "10")) + " MW",
            f"ASSUMED stress, forecast load +20% (data-center growth): " + " / ".join(f"{mw(STRESS, p):.1f}" for p in ("0", "2", "5", "10")) + " MW",
            f"At +20%, {len(g[STRESS]['by_curtailment_pct']['0']['banks_at_zero'])} banks have 0 MW firm headroom "
            f"(baseline {len(g[BASE]['by_curtailment_pct']['0']['banks_at_zero'])}).",
        ]),
        ("Scope", [NEVER, "GRIP values are directional. +20% is an assumed stress scenario, not a utility forecast."]
         + ([f"NOTE: stages using synthetic fixtures, not live results: {', '.join(stale)}"] if stale else [])),
    ]


def to_text(secs, run_dir):
    out = ["QSITEPROOF DEMO SUMMARY  (" + Path(run_dir).name + ")", "=" * 72]
    for h, lines in secs:
        out += ["", h.upper(), *("  " + x for x in lines)]
    return "\n".join(out)


def to_html(secs, run_dir):
    body = []
    for h, lines in secs:
        items = "".join(f"<li class='{x.split()[0].lower() if x.split()[0] in ('PASS', 'FAIL') else ''}'>{html.escape(x)}</li>" for x in lines)
        extra = " verdict" if h == "Verdict" else ""
        body.append(f"<section class='{extra.strip()}'><h2>{html.escape(h)}</h2><ul>{items}</ul></section>")
    return ("<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>QSiteProof demo summary</title><style>"
            "body{font:22px/1.4 system-ui,sans-serif;max-width:1100px;margin:0 auto;padding:16px 24px;background:#fff;color:#111}"
            "h1{font-size:34px;margin:8px 0}h2{font-size:24px;margin:20px 0 6px;border-bottom:2px solid #ccc}"
            "ul{list-style:none;padding:0;margin:0}li{padding:2px 0}li.pass{color:#0a7a2f}li.fail{color:#b00020;font-weight:700}li.pass,li.fail{font-size:20px}"
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
