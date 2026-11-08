"""Region adapters: international sites build a valid grid_snapshot from the committed OSM cache; US path unchanged."""
import json
from pathlib import Path

import jsonschema
import pytest

from grid import adapters
from grid.snapshot import get_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = json.loads((ROOT / "contracts" / "grid_snapshot.schema.json").read_text(encoding="utf-8"))
SITE_SCHEMA = json.loads((ROOT / "contracts" / "site.schema.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("sid", ["frankfurt-de-120", "johor-my-100"])
def test_global_snapshot_from_cache(sid, monkeypatch):
    monkeypatch.setenv("QSITE_OFFLINE", "1")
    site = json.loads((ROOT / "data" / "l1" / f"site_{sid}.json").read_text(encoding="utf-8"))
    jsonschema.validate(site, SITE_SCHEMA)
    assert isinstance(adapters.get_adapter(site), adapters.GlobalOsm)
    snap = get_snapshot(site)
    jsonschema.validate(snap, SCHEMA)
    assert snap["adapter"] == "global_osm" and "distribution" not in snap
    assert all(s["rating_source"].startswith("ASSUMED") for s in snap["substations"])
    assert snap["iso"]["source"].startswith(f"static:grid_signals.json[{site['country']}]")


def test_us_site_uses_unchanged_path(monkeypatch):
    monkeypatch.setenv("QSITE_OFFLINE", "1")
    site = json.loads((ROOT / "data" / "l1" / "site.json").read_text(encoding="utf-8"))
    assert isinstance(adapters.get_adapter(site), adapters.UsCaiso)
    snap = get_snapshot(site)
    jsonschema.validate(snap, SCHEMA)
    assert "adapter" not in snap and snap["substations"][0]["id"].startswith("osm-")
