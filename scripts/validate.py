"""Validate fixtures/ and contracts/examples/ against contracts/*.schema.json.

Exit 1 on any schema error, missing pair, or incoherent set. Usage: python scripts/validate.py
"""
import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

ROOT = Path(__file__).resolve().parent.parent
CONTRACTS = ROOT / "contracts"
STAGES = ["site", "grid_snapshot", "candidate_plan", "physics_result", "certificate"]


def load_schemas():
    schemas = {}
    for name in STAGES:
        schema = json.loads((CONTRACTS / f"{name}.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        schemas[name] = schema
    extra = {p.name for p in CONTRACTS.glob("*.schema.json")} - {f"{n}.schema.json" for n in STAGES}
    if extra:
        raise SystemExit(f"unknown schemas (add to STAGES): {sorted(extra)}")
    return schemas


def schema_errors(name, doc, schemas):
    v = Draft202012Validator(schemas[name], format_checker=FormatChecker())
    return [f"{name}: {'/'.join(map(str, e.path)) or '<root>'}: {e.message}" for e in v.iter_errors(doc)]


def coherence_errors(site, snap, plan, phys, cert):
    """Cross-file rules a schema can't express. A GREEN certificate must be backed by the other files."""
    errs = []
    subs = {s["id"]: s for s in snap["substations"]}
    for s in plan["splits"]:
        if s["substation_id"] not in subs:
            errs.append(f"candidate_plan: substation {s['substation_id']} not in grid_snapshot")
    for line in snap["lines"]:
        for end in (line["from"], line["to"]):
            if end not in subs:
                errs.append(f"grid_snapshot: line {line['id']} references unknown substation {end}")
    if cert["result"] == "RED" and not cert["blocking_condition"]:
        errs.append("certificate: RED needs a blocking_condition")
    if cert["result"] == "GREEN":
        if cert["blocking_condition"] is not None:
            errs.append("certificate: GREEN must have blocking_condition null")
        if not all(c["pass"] for c in cert["checks"]):
            errs.append("certificate: GREEN with a failing check")
        total = sum(s["mw"] for s in plan["splits"])
        if abs(total - site["requested_mw"]) > 0.01:
            errs.append(f"GREEN but splits sum {total} MW != requested {site['requested_mw']} MW")
        # shortcut: ignores flex (DLR/storage) that could raise headroom; extend once lanes encode it
        for s in plan["splits"]:
            sub = subs.get(s["substation_id"])
            if sub and s["mw"] > sub["headroom_mw"]:
                errs.append(f"GREEN but {sub['id']} split {s['mw']} MW > headroom {sub['headroom_mw']} MW")
        if not (phys["converged"] and phys["n1_pass"] and not phys["violations"]):
            errs.append("GREEN but physics_result is not clean (converged, n1_pass, no violations)")
    return errs


def validate_dir(folder, schemas):
    errs, docs = [], {}
    for name in STAGES:
        path = folder / f"{name}.json"
        if not path.exists():
            errs.append(f"{path.relative_to(ROOT)}: missing")
            continue
        docs[name] = json.loads(path.read_text(encoding="utf-8"))
        errs += schema_errors(name, docs[name], schemas)
    stray = {p.stem for p in folder.glob("*.json")} - set(STAGES)
    errs += [f"{folder.relative_to(ROOT)}/{s}.json: no matching schema" for s in sorted(stray)]
    if not errs:
        errs += coherence_errors(*(docs[n] for n in STAGES))
    return errs


def main():
    schemas = load_schemas()
    failed = False
    for folder in (ROOT / "fixtures", CONTRACTS / "examples"):
        errs = validate_dir(folder, schemas)
        status = "FAIL" if errs else "ok"
        print(f"{status:4} {folder.relative_to(ROOT)}")
        for e in errs:
            print(f"     - {e}")
        failed |= bool(errs)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
