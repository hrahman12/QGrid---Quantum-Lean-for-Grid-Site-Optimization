"""Live CAISO grid signal for the Alviso site, with an offline cache.

    from data.l2.iso import latest_signal
    latest_signal("CAISO") -> {"lmp", "load", "load_mw", "timestamp", "source", ...}

The returned dict fits contracts/grid_snapshot.schema.json `iso` (lmp, load, timestamp, source);
`load_mw` is the same value, as asked by ORCH. Extra keys are context.

Data (gridstatus, CAISO OASIS):
  - CAISO system load, 5-min, averaged to hourly
  - Day-ahead hourly LMP at TH_NP15_GEN-APND (NP15 trading hub) and DLAP_PGAE-APND (PG&E load zone,
    the closest public price for a San Jose load; no single public node is "the" Alviso node)
Cache: data/l2/caiso_<YYYY-MM-DD>.csv, last 7 days hourly. latest_signal() tries live first (60 s
budget) and falls back to the newest cache file; set QSITE_OFFLINE=1 (same switch as grid/) or QSP_OFFLINE=1 to skip the live call.

CLI: python data/l2/iso.py [--refresh] [--offline]
"""
import concurrent.futures as cf
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
NODES = {"lmp_np15_da": "TH_NP15_GEN-APND", "lmp_pge_dlap_da": "DLAP_PGAE-APND"}
PRICE_COL = "lmp_np15_da"  # the price reported as `lmp`
DAYS = 7
LIVE_TIMEOUT_S = 60
CACHE_MAX_AGE_MIN = 60  # a live pull is reused in-process for this long (search runs many rounds)


def _fetch_frame(days=DAYS):
    import gridstatus

    c = gridstatus.CAISO()
    end = pd.Timestamp.now(tz=c.default_timezone).floor("D") + pd.Timedelta(days=1)
    start = end - pd.Timedelta(days=days + 1)
    load = c.get_load(start=start, end=end)
    load = (load.set_index("Interval Start")["Load"].resample("1h").mean().rename("load_mw"))
    lmp = c.get_lmp(start=start, end=end, market="DAY_AHEAD_HOURLY", locations=list(NODES.values()))
    lmp = lmp.pivot_table(index="Interval Start", columns="Location", values="LMP")
    lmp = lmp.rename(columns={v: k for k, v in NODES.items()})
    df = pd.concat([load, lmp], axis=1).sort_index()
    df.index = df.index.tz_convert("UTC")
    df.index.name = "interval_start_utc"
    cutoff = df.index.max() - pd.Timedelta(days=days)
    return df[df.index > cutoff].reset_index()


LIVE = HERE / "cache" / "live" / "caiso_latest.csv"  # gitignored: live pulls never rewrite tracked files


def refresh_cache(snapshot=False):
    """Pull 7 days live. Writes the gitignored LIVE file; snapshot=True (CLI --refresh) also writes the
    tracked dated data/l2/caiso_<date>.csv that ships with the repo for offline demos."""
    df = _fetch_frame()
    LIVE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(LIVE, index=False, float_format="%.3f")
    path = LIVE
    if snapshot:
        path = HERE / f"caiso_{datetime.now(timezone.utc):%Y-%m-%d}.csv"
        df.to_csv(path, index=False, float_format="%.3f")
    return path, df


def _latest_cache():
    files = sorted(HERE.glob("caiso_*.csv"))
    if LIVE.exists() and (not files or LIVE.stat().st_mtime >= files[-1].stat().st_mtime):
        files.append(LIVE)
    if not files:
        raise FileNotFoundError("no data/l2/caiso_*.csv cache; run python data/l2/iso.py --refresh")
    df = pd.read_csv(files[-1], parse_dates=["interval_start_utc"])
    return files[-1], df


def stress_hours(df, col=PRICE_COL, q=0.9):
    """Hours per day with price above the q-quantile of the whole window (flexibility stress signal)."""
    s = df.set_index("interval_start_utc")[col].dropna()
    p = float(s.quantile(q))
    per_day = (s > p).groupby(s.index.tz_convert("America/Los_Angeles").date).sum()
    return {"price_col": col, "quantile": q, "threshold_usd_mwh": round(p, 2),
            "hours_per_day": {str(d): int(n) for d, n in per_day.items()},
            "mean_hours_per_day": round(float(per_day.mean()), 2)}


def stress_2025(window="net_load_top2pct"):
    """2025 CISO curtailment window from data/l2/ciso_2025_stress.json (EIA-930, event pack).

    Default is net load (demand - solar - wind) top 2%: the evening-ramp hours, ~98% availability.
    Returns None if the file is missing so latest_signal still works.
    """
    p = HERE / "ciso_2025_stress.json"
    if not p.exists():
        return None
    d = json.loads(p.read_text(encoding="utf-8"))
    w = d["curtailment_windows"][window]
    return {"window": window, "availability_if_curtailed_pct": w["availability_if_curtailed_pct"],
            "hours_per_year": w["hours_per_year"], "threshold_mw": w["threshold_mw"],
            "hours_by_month": w["hours_by_month"], "time_convention": d["time_convention"],
            "demand_p90": {k: d["demand_p90_hours_per_day"][k] for k in
                           ("threshold_mw", "hours_per_year", "mean_hours_per_day", "days_with_any",
                            "mean_hours_per_stress_day", "mean_hours_per_day_by_month")},
            "source": "data/l2/ciso_2025_stress.json"}


def _point(df, now=None):
    now = pd.Timestamp(now or datetime.now(timezone.utc))
    now = now.tz_localize("UTC") if now.tzinfo is None else now.tz_convert("UTC")
    have = df.dropna(subset=["load_mw"])
    have = have[have["interval_start_utc"] <= now]
    row = (have if not have.empty else df).iloc[-1]
    return row


_MEMO = {}  # in-process: {"at": epoch s, "path": Path, "df": DataFrame} from the last live pull


def _memo_live():
    m = _MEMO.get("v")
    if m and time.time() - m["at"] < CACHE_MAX_AGE_MIN * 60:
        return m
    return None


def latest_signal(iso="CAISO", live=None, now=None):
    if iso.upper() != "CAISO":
        raise ValueError(f"only CAISO is wired, got {iso}")
    if live is None:
        live = "1" not in (os.environ.get("QSITE_OFFLINE"), os.environ.get("QSP_OFFLINE"))
    source, df, note = None, None, None
    memo = _memo_live()
    if live and memo:  # cache first: a live pull from this process in the last CACHE_MAX_AGE_MIN is reused
        path, df = memo["path"], memo["df"].copy()
        source = f"gridstatus:CAISO (pulled {datetime.fromtimestamp(memo['at'], timezone.utc):%Y-%m-%dT%H:%MZ})"
    elif live:
        ex = cf.ThreadPoolExecutor(1)
        try:
            path, df = ex.submit(refresh_cache).result(timeout=LIVE_TIMEOUT_S)
            _MEMO["v"] = {"at": time.time(), "path": path, "df": df.copy()}
            source = "gridstatus:CAISO"
        except Exception as e:  # network down, OASIS throttling, timeout: use the cache
            note = f"live fetch failed ({type(e).__name__}); using cache"
            df = None
        finally:
            ex.shutdown(wait=False)  # don't block on a hung fetch
    if df is None:
        path, df = _latest_cache()
        source = f"cache:{path.relative_to(HERE.parent.parent).as_posix()}"
    df["interval_start_utc"] = pd.to_datetime(df["interval_start_utc"], utc=True)
    row = _point(df, now)
    ts = row["interval_start_utc"].strftime("%Y-%m-%dT%H:%M:%SZ")
    lmp = None if pd.isna(row[PRICE_COL]) else round(float(row[PRICE_COL]), 2)
    load = None if pd.isna(row["load_mw"]) else round(float(row["load_mw"]), 1)
    out = {
        "lmp": lmp,
        "load": load,
        "load_mw": load,
        "timestamp": ts,
        "source": source,
        "lmp_node": NODES[PRICE_COL] + " (day-ahead hourly)",
        "lmp_pge_dlap": None if pd.isna(row["lmp_pge_dlap_da"]) else round(float(row["lmp_pge_dlap_da"]), 2),
        "stress": stress_hours(df),
        "stress_2025": stress_2025(),
        "cache_file": path.relative_to(HERE.parent.parent).as_posix(),
    }
    if note:
        out["note"] = note
    return out


if __name__ == "__main__":


    if "--refresh" in sys.argv:
        p, d = refresh_cache(snapshot=True)
        print(f"wrote {p.relative_to(HERE.parent.parent)}: {len(d)} hourly rows")
    print(json.dumps(latest_signal("CAISO", live=False if "--offline" in sys.argv else None), indent=2))
