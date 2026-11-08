"""Live current weather for the QSiteProof site (no history, no replay).

Sources
  * NWS latest METAR-derived observation, station KSJC (San Jose Mineta Intl):
      https://api.weather.gov/stations/KSJC/observations/latest
    API docs: https://www.weather.gov/documentation/services-web-api (User-Agent required).
    This is a MEASUREMENT (ASOS). Values may be null (e.g. calm/variable wind, QC fail).
  * Open-Meteo "current" block (optional), for shortwave radiation (GHI):
      https://api.open-meteo.com/v1/forecast?latitude=..&longitude=..&current=shortwave_radiation
    Docs: https://open-meteo.com/en/docs. This is a NUMERICAL-MODEL nowcast value, not a
    measurement; it is labelled as such in the output.

Only the single latest value is ever requested. Anything unavailable is returned as None.
"""
from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Optional

USER_AGENT = "QSiteProof-hack/0.1 (research prototype)"
SITE_LAT, SITE_LON = 37.4275, -121.9650
NWS_STATION = "KSJC"
NWS_URL = "https://api.weather.gov/stations/{station}/observations/latest"
OPEN_METEO_URL = ("https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}"
                  "&current=shortwave_radiation,temperature_2m,wind_speed_10m,wind_direction_10m"
                  "&wind_speed_unit=ms&timezone=UTC")


def _get_json(url: str, timeout: float = 10.0, accept: str = "application/geo+json") -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0088  # IUGG mean Earth radius
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _qv(prop: Optional[dict]) -> tuple[Optional[float], Optional[str]]:
    if not prop:
        return None, None
    return prop.get("value"), prop.get("unitCode")


def _to_ms(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    u = (unit or "").lower()
    if "km_h" in u:
        return value / 3.6
    if "m_s" in u:
        return value
    if "kt" in u or "knot" in u:
        return value * 0.514444
    return None


def _to_c(value: Optional[float], unit: Optional[str]) -> Optional[float]:
    if value is None:
        return None
    u = (unit or "").lower()
    if "degc" in u:
        return value
    if "degf" in u:
        return (value - 32) * 5 / 9
    if u.endswith(":k"):
        return value - 273.15
    return None


def nws_latest(station: str = NWS_STATION) -> dict:
    """Latest NWS observation for `station`, SI units. Raises on network failure."""
    d = _get_json(NWS_URL.format(station=station))
    p = d.get("properties", {})
    coords = (d.get("geometry") or {}).get("coordinates") or [None, None]
    st_lon, st_lat = coords[0], coords[1]
    t_c = _to_c(*_qv(p.get("temperature")))
    ws = _to_ms(*_qv(p.get("windSpeed")))
    wg = _to_ms(*_qv(p.get("windGust")))
    wd, _ = _qv(p.get("windDirection"))
    obs_time = p.get("timestamp")
    age_min = None
    if obs_time:
        age_min = (datetime.now(timezone.utc) - datetime.fromisoformat(obs_time)).total_seconds() / 60
    calm = ws is not None and ws == 0.0
    if calm:
        wd = None  # METAR 00000KT: direction is meaningless when calm
    return {
        "calm": calm,
        "stale": age_min is not None and age_min > 90,  # ASOS reports hourly; >90 min = missed report
        "source": f"NWS api.weather.gov latest observation, station {station} (ASOS measurement)",
        "url": NWS_URL.format(station=station),
        "station": station,
        "station_lat": st_lat,
        "station_lon": st_lon,
        "station_elevation_m": (p.get("elevation") or {}).get("value"),
        "distance_to_site_km": (_haversine_km(SITE_LAT, SITE_LON, st_lat, st_lon)
                                if st_lat is not None else None),
        "observed_at_utc": obs_time,
        "age_minutes": age_min,
        "air_temp_c": t_c,
        "wind_speed_ms": ws,
        "wind_gust_ms": wg,
        "wind_dir_deg_from": wd,  # meteorological: direction wind blows FROM, deg true; None if variable
        "text": p.get("textDescription"),
        "raw_metar": p.get("rawMessage"),
    }


def open_meteo_current(lat: float = SITE_LAT, lon: float = SITE_LON) -> dict:
    d = _get_json(OPEN_METEO_URL.format(lat=lat, lon=lon), accept="application/json")
    c = d.get("current", {}) or {}
    return {
        "source": "Open-Meteo current block (numerical model nowcast, NOT a measurement)",
        "url": OPEN_METEO_URL.format(lat=lat, lon=lon),
        "valid_at_utc": c.get("time"),
        "interval_s": c.get("interval"),
        "shortwave_radiation_wm2": c.get("shortwave_radiation"),
        "model_temp_c": c.get("temperature_2m"),
        "model_wind_speed_ms": c.get("wind_speed_10m"),
        "model_wind_dir_deg_from": c.get("wind_direction_10m"),
    }


def current_conditions(station: str = NWS_STATION, with_irradiance: bool = True) -> dict:
    """One poll: measured air temp / wind from NWS + optional model GHI. Missing -> None."""
    out = {"polled_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "air_temp_c": None, "wind_speed_ms": None, "wind_dir_deg_from": None,
           "ghi_wm2": None, "nws": None, "open_meteo": None, "errors": []}
    try:
        n = nws_latest(station)
        out["nws"] = n
        out["air_temp_c"] = n["air_temp_c"]
        out["wind_speed_ms"] = n["wind_speed_ms"]
        out["wind_dir_deg_from"] = n["wind_dir_deg_from"]
        out["calm"] = n["calm"]
        out["stale"] = n["stale"]
    except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
        out["errors"].append(f"NWS: {e!r}")
    if with_irradiance:
        try:
            om = open_meteo_current()
            out["open_meteo"] = om
            out["ghi_wm2"] = om["shortwave_radiation_wm2"]
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as e:
            out["errors"].append(f"Open-Meteo: {e!r}")
    return out


if __name__ == "__main__":
    print(json.dumps(current_conditions(), indent=2, default=str))
