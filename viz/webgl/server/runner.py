import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from viz.webgl.server.search_service import run_native

if __name__ == '__main__':
    result = run_native(json.load(sys.stdin))
    print('QGRID_RESULT=' + json.dumps(result, allow_nan=False))
