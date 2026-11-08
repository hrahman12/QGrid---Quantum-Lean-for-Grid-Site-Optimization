"""RED -> constraint -> re-propose loop in pipeline.run (Astra #10)."""
import importlib
import json

import pipeline
from report import labels


def _fake_cert(result, blocking=None):
    return {"checks": [{"name": "capacity", "pass": blocking is None, "detail": blocking or "ok"}],
            "result": result, "blocking_condition": f"capacity: {blocking}" if blocking else None,
            "scope_note": "x", "engine": "python-mirror"}


def test_red_then_green_runs_two_rounds_and_passes_constraint(monkeypatch, tmp_path):
    seen, verdicts = [], iter([_fake_cert("RED", "osm-way-1 split 9 MW > headroom 1 MW"), _fake_cert("GREEN")])
    search = importlib.import_module("quantum.search")
    real = search.propose
    monkeypatch.setattr(search, "propose", lambda site, snap, constraints=None: (seen.append(list(constraints)), real(site, snap, constraints))[1])
    monkeypatch.setattr(importlib.import_module("lean.certify"), "certify", lambda *a, **k: next(verdicts))

    _, _, _, run_dir = pipeline.run(out_root=tmp_path)

    assert len(seen) == 2 and seen[0] == []
    assert seen[1][0]["rule"] == "capacity" and "osm-way-1" in seen[1][0]["detail"]
    rounds = json.loads((run_dir / "rounds.json").read_text(encoding="utf-8"))
    assert [r["verdict"] for r in rounds] == ["RED", "GREEN"]
    assert rounds[0]["blocking_rule"] == "capacity" and rounds[1]["constraints_in"] == seen[1]


def test_rounds_bound_and_stall(monkeypatch, tmp_path):
    monkeypatch.setattr(importlib.import_module("lean.certify"), "certify",
                        lambda *a, **k: _fake_cert("RED", "SUB-X split 9 MW > headroom 1 MW"))
    _, _, _, run_dir = pipeline.run(out_root=tmp_path, rounds=3)
    rounds = json.loads((run_dir / "rounds.json").read_text(encoding="utf-8"))
    assert len(rounds) <= 3 and rounds[-1]["verdict"] == "RED"


def test_labels():
    assert labels.cert_engine({"engine": "lean4"}) == "Lean 4"
    assert "Lean did not run" in labels.cert_engine({"scope_note": "Rules checked by python-mirror (Lean unavailable)"})
    assert "fallback" in labels.search_engine({"search": {"method": "heuristic"}})
    assert labels.verdict_label("GREEN").endswith("over the supplied evidence")
