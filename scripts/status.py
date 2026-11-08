"""Print the team status board in the terminal, plus a live check of what's actually in the repo.
Usage: python scripts/status.py [--run]   (--run also runs the pipeline offline and shows each stage's source)"""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHECKS = [  # what each lane delivers, by file
    ("L1", "grid snapshot", "grid/snapshot.py"),
    ("L1", "pandapower physics", "grid/physics.py"),
    ("L1", "GRIP pack", "data/shared/grip/grip_capacity.json"),
    ("L2", "substation ratings", "data/l2/substation_ratings.json"),
    ("L2", "CAISO signal", "data/l2/iso.py"),
    ("L2", "curtailment curve", "data/l2/flex_headroom.json"),
    ("L2", "site risk", "data/l2/site_risk.json"),
    ("L2", "L3 inputs", "data/l2/l3_inputs.json"),
    ("L2", "classical fallback search", "fallback/search.py"),
    ("L3", "PsiQDK search", "quantum/search.py"),
    ("L3", "Lean certify", "lean/certify.py"),
]

sys.stdout.reconfigure(encoding="utf-8")
print((ROOT / "STATUS.md").read_text(encoding="utf-8"))
print("=" * 72)
print("LIVE CHECK (files on this checkout)")
for lane, what, path in CHECKS:
    print(f"  [{'x' if (ROOT / path).exists() else ' '}] {lane}  {what:28} {path}")
try:
    log = subprocess.run(["git", "log", "--oneline", "-5"], cwd=ROOT, capture_output=True, text=True).stdout
    print("\nLatest commits on this checkout:\n" + log)
except OSError:
    pass
if "--run" in sys.argv:
    print("Running pipeline offline...\n")
    subprocess.run([sys.executable, "pipeline.py"], cwd=ROOT, env={**os.environ, "QSITE_OFFLINE": "1"})
