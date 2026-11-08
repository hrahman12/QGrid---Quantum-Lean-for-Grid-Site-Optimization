"""Build data/l2/ciso_2025_stress.json: when CAISO is stressed, for curtailment windows.

Input (cached, offline): data/l2/cache/ciso_hourly_2025_eia930.csv, the CISO rows of the hack-day
event pack https://github.com/arhamshah08/energy-hack data/grid-hourly-2025/us_grid_hourly_2025.csv
(US EIA Form 930, 2025, hourly averages, hour-ending; public domain). No prices in EIA-930, so
stress is defined on demand and on net load (demand - solar - wind).

Organizers' framing: a large load that accepts curtailment in the few hottest hours (~98%
availability) connects much sooner. So the key window is the top 2% of hours (~175 h/yr).
Output cells use local month (1-12) and local hour-beginning (0-23) like GRIP's limiting_month /
limiting_hour, so a Lean rule can check "curtail in the GRIP limiting hour AND the CISO stress hours".

Usage: python data/l2/build_ciso_stress.py
"""
import json
import math
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
CACHE = HERE / "cache" / "ciso_hourly_2025_eia930.csv"
OUT = HERE / "ciso_2025_stress.json"
SOURCE = ("US EIA Form 930 via the SF x MIT Hack Day Energy pack, "
          "https://github.com/arhamshah08/energy-hack/blob/main/data/grid-hourly-2025/us_grid_hourly_2025.csv "
          "(ba == CISO), cached as data/l2/cache/ciso_hourly_2025_eia930.csv")


def load():
    df = pd.read_csv(CACHE)
    t = pd.to_datetime(df["local_time_end"]) - pd.Timedelta(hours=1)  # hour-beginning, local
    df["month"], df["hour"], df["date"] = t.dt.month, t.dt.hour, t.dt.date
    df["net_load_mw"] = df["demand_mw"] - df["solar_mw"].fillna(0) - df["wind_mw"].fillna(0)
    return df


def window(df, col, top_share):
    n = math.ceil(top_share * len(df))
    top = df.nlargest(n, col)
    thr = float(top[col].min())
    cells = top.groupby(["month", "hour"]).size().rename("hours").reset_index()
    cells = cells.sort_values("hours", ascending=False)
    by_month = {int(m): sorted(int(h) for h in g["hour"]) for m, g in cells.groupby("month")}
    return {
        "metric": col,
        "top_share": top_share,
        "availability_if_curtailed_pct": round(100 * (1 - n / len(df)), 2),
        "hours_per_year": n,
        "threshold_mw": round(thr, 1),
        "days_with_stress": int(top["date"].nunique()),
        "max_stress_hours_in_one_day": int(top.groupby("date").size().max()),
        "months": sorted(by_month),
        "hours_by_month": {str(m): hs for m, hs in by_month.items()},
        "cells": [{"month": int(r.month), "hour": int(r.hour), "hours": int(r.hours)} for r in cells.itertuples()],
    }


def main():
    df = load()
    q = {p: round(float(df["demand_mw"].quantile(p / 100)), 1) for p in (50, 90, 95, 98, 99)}
    doc = {
        "ba": "CISO",
        "year": 2025,
        "source": SOURCE,
        "time_convention": "month 1-12 and hour 0-23 are local (Pacific) hour-beginning, matching GRIP limiting_month/limiting_hour",
        "stress_definition": "hours in the top X% of the year by the metric; no prices in EIA-930",
        "demand_mw_percentiles": q,
        "demand_peak_mw": round(float(df["demand_mw"].max()), 1),
        "curtailment_windows": {
            "demand_top2pct": window(df, "demand_mw", 0.02),
            "net_load_top2pct": window(df, "net_load_mw", 0.02),
            "demand_top5pct": window(df, "demand_mw", 0.05),
        },
        "note": "System-level CAISO stress, not feeder-level. Pair with GRIP feeder limiting month/hour for local stress. Directional, not a utility curtailment agreement.",
    }
    OUT.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    w = doc["curtailment_windows"]
    for k, v in w.items():
        print(f"{k}: {v['hours_per_year']} h/yr, avail {v['availability_if_curtailed_pct']}%, thr {v['threshold_mw']} MW, "
              f"{v['days_with_stress']} days, months {v['months']}, top cells {[(c['month'], c['hour'], c['hours']) for c in v['cells'][:5]]}")


if __name__ == "__main__":
    main()
