#!/usr/bin/env sh
# Usage: ./run.sh setup|validate|test|pipeline|demo
set -e
cd "$(dirname "$0")"
PY=.venv/bin/python; [ -x "$PY" ] || PY=.venv/Scripts/python
case "$1" in
  setup)    python3 -m venv .venv && "$PY" -m pip install -r requirements.txt ;;
  validate) "$PY" scripts/validate.py ;;
  test)     "$PY" -m pytest -q ;;
  pipeline) shift; "$PY" pipeline.py "$@" ;;
  demo)     export QSITE_OFFLINE=1 PYTHONUTF8=1
            for f in pipeline.py scenarios/edge_alviso.py scenarios/growth_alviso.py report/summary.py; do "$PY" "$f"; done ;;
  *) echo "usage: $0 setup|validate|test|pipeline [site.json]|demo"; exit 2 ;;
esac
