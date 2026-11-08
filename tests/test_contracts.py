import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def test_validate_passes():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "validate.py")], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_validate_catches_bad_green():
    from pipeline import coherence_errors
    import json
    load = lambda n: json.loads((ROOT / "fixtures" / f"{n}.json").read_text(encoding="utf-8"))
    site, snap, plan, phys, cert = (load(n) for n in ["site", "grid_snapshot", "candidate_plan", "physics_result", "certificate"])
    plan["splits"][0]["mw"] = 999
    assert coherence_errors(site, snap, plan, phys, cert)


def test_pipeline_runs_end_to_end(tmp_path):
    import pipeline
    out, sources, problems, run_dir = pipeline.run(out_root=tmp_path)
    assert problems == []
    assert out["certificate"]["result"] in {"GREEN", "RED"}
    assert sorted(p.name for p in run_dir.glob("*.json")) == sorted(
        ["site.json", "grid_snapshot.json", "candidate_plan.json", "physics_result.json", "certificate.json", "sources.json", "rounds.json"])


def test_live_stage_used_when_lane_module_exists(tmp_path, monkeypatch):
    import types
    import pipeline
    fake = types.ModuleType("grid.snapshot")
    fake.get_snapshot = lambda site: pipeline.fixture("grid_snapshot")
    monkeypatch.setitem(sys.modules, "grid", types.ModuleType("grid"))
    monkeypatch.setitem(sys.modules, "grid.snapshot", fake)
    _, sources, problems, _ = pipeline.run(out_root=tmp_path)
    assert sources["grid_snapshot"] == "live"  # later stages may be live too now that L3 exists
    assert problems == []
