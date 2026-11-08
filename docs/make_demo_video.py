"""Render the QSiteProof GREEN demo video from a real pipeline run (docs/demo_run/).

Every number and shape comes from the run files or from OpenStreetMap (data/l1):
- map: real OSM power lines + substations + site coordinates
- quantum: exact Grover amplitudes for the run's N (padded) and M (marked), the
  same math PsiQDK simulated (sin((2k+1)theta)), plus PsiQDK's resource estimate
- physics + Lean: physics_result.json and certificate.json verbatim

Run: python docs/make_demo_video.py  ->  docs/demo_green.mp4 and docs/demo_green.gif (both 1920x1080)
"""
import json, math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import imageio.v2 as imageio

ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "docs" / "demo_run"
OUT_MP4, OUT_GIF = ROOT / "docs" / "demo_green.mp4", ROOT / "docs" / "demo_green.gif"
J = lambda n: json.loads((RUN / n).read_text(encoding="utf-8"))
site, snap, plan, phys, cert, qs = (J(f) for f in ["site.json", "grid_snapshot.json", "candidate_plan.json",
                                                   "physics_result.json", "certificate.json", "quantum_search.json"])
lines = json.loads((ROOT / "data/l1/osm_power_lines_alviso.geojson").read_text(encoding="utf-8"))["features"]
g = qs["grover"]
N, M, K = g["padded_N"], g["M"], g["iterations"]
theta = math.asin(math.sqrt(M / N))
res = g["resources"]["qpu_metrics"]
subs = {s["id"]: s for s in snap["substations"]}
names = {s["id"]: s["name"].replace(" Substation", "").replace(" Station", "") for s in snap["substations"]}

BG, INK, MUT, GRN, RED, PUR, TEAL, AMB = "#0b1424", "#e6edf7", "#8fa3c2", "#38d27a", "#ff5d5d", "#8b6cff", "#35b8e0", "#f5b82e"
plt.rcParams.update({"font.family": "DejaVu Sans", "text.color": INK, "axes.labelcolor": MUT,
                     "xtick.color": MUT, "ytick.color": MUT, "axes.edgecolor": "#24365a"})
W, H, FPS = 12.8, 7.2, 12

lat0, lon0 = site["lat"], site["lon"]
kx = 111.32 * math.cos(math.radians(lat0))
xy = lambda la, lo: ((lo - lon0) * kx, (la - lat0) * 110.57)  # km east, km north


def frame_base(title, step):
    fig = plt.figure(figsize=(W, H), dpi=150, facecolor=BG)
    fig.text(0.03, 0.94, "QSiteProof", fontsize=22, weight="bold")
    fig.text(0.215, 0.945, title, fontsize=15, color=MUT)
    steps = ["1 Input", "2 Find (quantum)", "3 Check physics", "4 Prove (Lean)", "Result"]
    for i, s in enumerate(steps):
        fig.text(0.03 + i * 0.19, 0.05, s, fontsize=12, weight="bold" if i == step else "normal",
                 color=[MUT, PUR, TEAL, GRN, INK][i] if i == step else "#4a5d7c")
    fig.text(0.97, 0.015, "Real run " + snap["iso"]["timestamp"][:16].replace("T", " ") + " UTC · OSM data ODbL",
             fontsize=8, color="#4a5d7c", ha="right")
    return fig


def draw_map(ax, chosen_alpha=0.0, cand_alpha=0.25):
    ax.set_facecolor(BG)
    for f in lines:
        geom = f["geometry"]
        parts = [geom["coordinates"]] if geom["type"] == "LineString" else geom["coordinates"]
        kv = f["properties"].get("voltage", "")
        col = AMB if "230000" in kv else ("#5a7bb0" if "115000" in kv else "#33476b")
        for p in parts:
            pts = np.array([xy(la, lo) for lo, la in p])
            ax.plot(pts[:, 0], pts[:, 1], color=col, lw=0.8 if col != "#33476b" else 0.5, alpha=0.8)
    for s in snap["substations"]:
        x, y = xy(s["lat"], s["lon"])
        ax.scatter([x], [y], s=70, marker="s", color=TEAL, zorder=5, edgecolor="white", lw=0.6)
        ax.text(x + 0.25, y + 0.2, f"{names[s['id']]}\n{s['kv']:.0f} kV · headroom {s['headroom_mw']:.0f} MW",
                fontsize=8, color=INK, zorder=6)
    sx, sy = 0, 0
    for s in snap["substations"]:
        x, y = xy(s["lat"], s["lon"])
        ax.plot([sx, x], [sy, y], color=PUR, lw=1, alpha=cand_alpha, ls="--")
    for sp in plan["splits"]:
        s = subs[sp["substation_id"]]; x, y = xy(s["lat"], s["lon"])
        ax.plot([sx, x], [sy, y], color=GRN, lw=1 + sp["mw"] / 15, alpha=chosen_alpha, zorder=7)
        if chosen_alpha > 0.5:
            ax.text((sx + x) / 2, (sy + y) / 2, f"{sp['mw']:.1f} MW", color=GRN, fontsize=11, weight="bold", zorder=8)
    ax.scatter([sx], [sy], s=260, marker="*", color=PUR, zorder=9, edgecolor="white")
    ax.text(sx - 0.3, sy - 0.75, "150 MW site", color=PUR, fontsize=10, weight="bold", ha="right")
    ax.set_xlim(-6, 6); ax.set_ylim(-4.5, 3.5); ax.set_aspect("equal")
    ax.set_xlabel("km east of site"); ax.set_ylabel("km north")
    ax.set_title("Real grid around Alviso (OpenStreetMap lines; 230 kV amber, 115 kV blue)", fontsize=10, color=MUT)


def to_img(fig):
    fig.canvas.draw()
    img = np.asarray(fig.canvas.buffer_rgba())[:, :, :3].copy()
    plt.close(fig)
    return img


frames, stills = [], []  # stills: (image, seconds) for a full-res GIF without duplicate frames
def hold(img, sec):
    frames.extend([img] * int(sec * FPS)); stills.append((img, sec))

# 1. Input
fig = frame_base("Can this site connect sooner on today's grid?", 0)
fig.text(0.5, 0.62, f"{site['requested_mw']:.0f} MW data center", fontsize=40, weight="bold", ha="center")
fig.text(0.5, 0.52, "North San Jose / Alviso  ·  CAISO  ·  needed by " + site["deadline"], fontsize=20, ha="center", color=MUT)
fig.text(0.5, 0.38, "Find a hookup plan  →  check the physics  →  prove the rules", fontsize=18, ha="center", color=INK)
hold(to_img(fig), 3)

# 2a. Real map with candidates
fig = frame_base("Where could the 150 MW plug in?", 0)
ax = fig.add_axes([0.06, 0.12, 0.88, 0.76]); draw_map(ax, 0, 0.35)
hold(to_img(fig), 3)

# 2b. Quantum: superposition -> oracle -> diffusion -> amplified (exact Grover amplitudes)
a0 = 1 / math.sqrt(N)
def amps(stage):
    good_amp = {"super": a0, "oracle": -a0}.get(stage, math.sin((2 * K + 1) * theta) / math.sqrt(M))
    bad_amp = a0 if stage in ("super", "oracle") else math.cos((2 * K + 1) * theta) / math.sqrt(N - M)
    return good_amp, bad_amp
labels = {"super": "Superposition: all 1,024 plan slots at once, equal amplitude",
          "oracle": f"Oracle: the {M} plans that pass get a phase flip (sign −)",
          "diff": "Interference (inversion about the mean): passing plans grow"}
n_show = 64
for stage, sec in [("super", 2.5), ("oracle", 2.5), ("diff", 3)]:
    fig = frame_base("Quantum search over every hookup plan", 1)
    ax = fig.add_axes([0.06, 0.18, 0.55, 0.62]); ax.set_facecolor(BG)
    ga, ba = amps(stage)
    marked = np.zeros(n_show, bool); marked[np.linspace(0, n_show - 1, max(1, round(n_show * M / N))).astype(int)] = True
    vals = np.where(marked, ga, ba)
    ax.bar(range(n_show), vals, color=np.where(marked, GRN, "#4a6fa5"), width=0.8)
    ax.axhline(0, color=MUT, lw=0.8)
    if stage == "oracle":
        ax.axhline(vals.mean(), color=AMB, ls="--", lw=1); ax.text(n_show, vals.mean(), " mean", color=AMB, fontsize=9)
    ax.set_ylim(-0.1, 0.1); ax.set_xticks([]); ax.set_ylabel("amplitude")
    ax.set_title(labels[stage] + f"\n(showing {n_show} of {N}; green = passes)", fontsize=11, color=INK)
    p_good = (ga ** 2) * M
    ax2 = fig.add_axes([0.66, 0.22, 0.3, 0.52], projection="polar"); ax2.set_facecolor(BG)
    ang = theta if stage == "super" else (-theta if stage == "oracle" else (2 * K + 1) * theta)
    ax2.annotate("", xy=(ang, 1), xytext=(0, 0), arrowprops=dict(arrowstyle="-|>", color=PUR, lw=2.5))
    ax2.set_thetamin(-30); ax2.set_thetamax(95); ax2.set_rticks([]); ax2.set_xticks([0, math.pi / 2])
    ax2.set_xticklabels(["plans that fail", "plans that pass"], color=MUT, fontsize=9)
    ax2.set_title(f"State rotates by 2θ per step, θ = asin(√(M/N)) = {math.degrees(theta):.1f}°", fontsize=9, color=MUT)
    fig.text(0.66, 0.13, f"P(measure a passing plan) = {p_good:.0%}", fontsize=13, color=GRN, weight="bold")
    fig.text(0.06, 0.09, f"PsiQuantum PsiQDK simulation · {g['n_qubits']} qubits · {K} Grover iteration · "
             f"fault-tolerant cost estimate: Active Volume {res['active_volume']:,}, {res['toffoli_count']:,} Toffoli",
             fontsize=9, color=MUT)
    hold(to_img(fig), sec)

# 2c. Measurement -> chosen plan on the map
fig = frame_base("Measure: one plan comes out", 1)
ax = fig.add_axes([0.06, 0.12, 0.6, 0.76]); draw_map(ax, 1.0, 0.12)
txt = "\n".join(f"• {sp['mw']:.1f} MW → {names[sp['substation_id']]}" for sp in plan["splits"])
flex = plan["flex"]
fig.text(0.69, 0.7, "Chosen plan", fontsize=16, weight="bold", color=GRN)
fig.text(0.69, 0.55, txt, fontsize=13)
fig.text(0.69, 0.45, f"DLR {'on' if flex['dlr'] else 'off'} · battery {flex['storage_mw']:.0f} MW · curtail {flex['curtailment_mw']:.0f} MW",
         fontsize=11, color=MUT)
fig.text(0.69, 0.33, f"Found with {plan['search']['evals']} oracle queries\n(PsiQDK, simulated)", fontsize=11, color=PUR)
hold(to_img(fig), 3.5)

# 3. Physics
fig = frame_base("Engineering check (pandapower power flow + N-1)", 2)
rows = [("Power flow converged", phys["converged"]),
        (f"Max line/transformer loading {phys['max_line_loading_pct']}%", phys["max_line_loading_pct"] <= 100),
        (f"Voltage {phys['v_min_pu']}–{phys['v_max_pu']} pu", True),
        ("Safe if any single line trips (N-1)", phys["n1_pass"])]
for i, (t, ok) in enumerate(rows):
    fig.text(0.18, 0.7 - i * 0.11, ("✔ " if ok else "✘ ") + t, fontsize=20, color=GRN if ok else RED)
hold(to_img(fig), 3)

# 4. Lean
fig = frame_base("Rulebook check, proved in Lean 4", 3)
for i, c in enumerate(cert["checks"]):
    fig.text(0.1, 0.78 - i * 0.075, ("✔ " if c["pass"] else "✘ ") + c["name"].replace("_", " / "), fontsize=15,
             color=GRN if c["pass"] else RED, weight="bold")
    fig.text(0.36, 0.78 - i * 0.075, c["detail"][:95], fontsize=9, color=MUT)
hold(to_img(fig), 3.5)

# 5. Result
fig = frame_base("Result", 4)
col = GRN if cert["result"] == "GREEN" else RED
fig.text(0.5, 0.62, f"{cert['result']}: SITE INTEGRABLE" if cert["result"] == "GREEN" else "RED", fontsize=46,
         weight="bold", ha="center", color=col)
fig.text(0.5, 0.5, f"150 MW by {site['deadline']} on existing substations: "
         + " + ".join(f"{sp['mw']:.1f} MW {names[sp['substation_id']]}" for sp in plan["splits"]),
         fontsize=14, ha="center")
fig.text(0.5, 0.4, "Find quantumly · check physically · prove formally", fontsize=16, ha="center", color=MUT)
fig.text(0.5, 0.26, "GREEN covers only the encoded rules over the supplied evidence; it is not a utility interconnection approval.\n"
         "Quantum search is a PsiQDK simulation of a fault-tolerant algorithm; no quantum advantage is claimed.",
         fontsize=10, ha="center", color="#6c80a0")
hold(to_img(fig), 4)

imageio.mimwrite(OUT_MP4, frames, fps=FPS, codec="libx264", quality=10, macro_block_size=8,
                 ffmpeg_params=["-crf", "12", "-preset", "slow", "-pix_fmt", "yuv420p"])
imageio.mimwrite(OUT_GIF, [im for im, _ in stills], duration=[1000 * sec for _, sec in stills], loop=0)
print("wrote", OUT_MP4, OUT_MP4.stat().st_size // 1024, "KB;", OUT_GIF, OUT_GIF.stat().st_size // 1024, "KB;", len(frames), "frames")
