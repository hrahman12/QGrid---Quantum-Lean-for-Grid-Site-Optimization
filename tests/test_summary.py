import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import pipeline  # noqa: E402
from report import summary  # noqa: E402
from scenarios import edge_alviso  # noqa: E402


def test_summary_has_both_loops_growth_and_consent(tmp_path):
    pipeline.run(out_root=tmp_path)
    edge_alviso.run(out_root=tmp_path)
    d = summary.load(summary.newest("certificate.json", tmp_path), tmp_path)
    txt = summary.to_text(summary.sections(d), d["run_dir"])
    for needle in ("FEEDBACK LOOP 1", "FEEDBACK LOOP 2", "bank_cap", "GROWTH TABLE", "CONSENT LAYER",
                   "Consent score", "Amber conditions", labels_data()):
        assert needle in txt
    assert "<table>" in summary.to_html(summary.sections(d), d["run_dir"])


def labels_data():
    from report import labels
    return labels.DATA_LABEL


def test_site_stage_is_live_not_fixture(tmp_path):
    _, sources, _, _ = pipeline.run(out_root=tmp_path)
    assert sources["site"] == "data/l1/site.json"
