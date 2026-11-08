"""Offline summary map: distribution-connectable MW vs the request. Run: python grid/map.py -> data/l1/distribution_map.html
Uses the snapshot's `distribution` view (GRIP) and transmission substations; inline SVG, no network."""
import html
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QSITE_OFFLINE", "1")
from grid.snapshot import get_snapshot  # noqa: E402

W, H, PAD = 900, 620, 40


def render(site, snap):
    d = snap.get("distribution")
    if not d:
        raise SystemExit("no distribution view: data/shared/grip/grip_capacity.json (or QSITE_GRIP_JSON) not found")
    pts = [(site["lat"], site["lon"])] + [(s["lat"], s["lon"]) for s in snap["substations"]] + [(s["lat"], s["lon"]) for s in d["substations"]]
    lat0, lat1 = min(p[0] for p in pts), max(p[0] for p in pts)
    lon0, lon1 = min(p[1] for p in pts), max(p[1] for p in pts)
    k = min((W - 2 * PAD) / ((lon1 - lon0) * 0.8 or 1), (H - 2 * PAD - 60) / ((lat1 - lat0) or 1))  # 0.8 ~ cos(37 deg)
    xy = lambda lat, lon: (PAD + (lon - lon0) * 0.8 * k, H - PAD - (lat - lat0) * k)  # noqa: E731
    g = []
    for s in d["substations"]:
        x, y = xy(s["lat"], s["lon"])
        r = 4 + 3.2 * s["connectable_mw"] ** 0.5
        g.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{r:.1f}" class="dist"><title>{html.escape(s["name"])}: {s["connectable_mw"]} MW at distribution '
                 f'(bank headroom {s["bank_headroom_mw"]} MW)</title></circle>')
        if s["connectable_mw"] > 0:
            g.append(f'<text x="{x+r+3:.0f}" y="{y+4:.0f}" class="lbl">{html.escape(s["name"].title())} {s["connectable_mw"]:.1f}</text>')
    for s in snap["substations"]:
        x, y = xy(s["lat"], s["lon"])
        g.append(f'<rect x="{x-5:.0f}" y="{y-5:.0f}" width="10" height="10" class="tx"><title>{html.escape(s["name"])} {s["kv"]:.0f} kV (transmission)</title></rect>')
    x, y = xy(site["lat"], site["lon"])
    g.append(f'<path d="M{x:.0f} {y-10:.0f} l9 17 h-18 z" class="site"><title>{html.escape(site["name"])}</title></path>')
    summ = (f'{d["connectable_at_distribution_mw"]:.1f} MW of the {d["requested_mw"]:.0f} MW request fits at distribution as '
            f'{d["n_edge_sites"]} edge sites (0.5-10 MW); {d["needs_transmission_mw"]:.1f} MW needs transmission.')
    return f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Distribution-connectable MW</title><style>
:root{{--bg:#fff;--fg:#1a1a1a;--mut:#666;--dist:#1f7a4d;--tx:#b45309;--site:#b91c1c}}
@media(prefers-color-scheme:dark){{:root{{--bg:#14161a;--fg:#e8e8e8;--mut:#9aa;--dist:#4ade80;--tx:#fbbf24;--site:#f87171}}}}
body{{margin:0;padding:16px;background:var(--bg);color:var(--fg);font:15px system-ui,sans-serif}}
h1{{font-size:18px;margin:0 0 6px}}p{{margin:4px 0;color:var(--mut)}}svg{{max-width:100%;height:auto}}
.dist{{fill:var(--dist);fill-opacity:.55;stroke:var(--dist)}}.tx{{fill:var(--tx)}}.site{{fill:var(--site)}}.lbl{{fill:var(--fg);font-size:11px}}
</style><h1>{html.escape(site["name"])}</h1><p><b style="color:var(--fg)">{summ}</b></p>
<p>Green circles: PG&amp;E distribution substations, area = MW connectable at distribution. Orange squares: transmission substations (OSM + assumed ratings). Red triangle: site.
Directional estimate from PG&amp;E GRIP hosting capacity; not a utility approval.</p>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="Map of connectable distribution MW">{"".join(g)}</svg></html>"""


if __name__ == "__main__":
    sites = json.loads((ROOT / "data/l1/sites.json").read_text(encoding="utf-8"))
    site = sites[0]
    out = ROOT / "data/l1/distribution_map.html"
    out.write_text(render(site, get_snapshot(site)), encoding="utf-8")
    print(f"wrote {out}")
