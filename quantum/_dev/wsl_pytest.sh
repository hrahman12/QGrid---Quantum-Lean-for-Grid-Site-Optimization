#!/usr/bin/env bash
# Dev helper: run the L3 search tests inside WSL (where psiqdk is installed). Usage: bash quantum/_dev/wsl_pytest.sh [pytest args]
export PATH="$HOME/.local/bin:$HOME/.elan/bin:$PATH"
. "$HOME/qsite-venv/bin/activate"
cd "$(dirname "$0")/../.."
python -c "import requests, gridstatus" 2>&1 | tail -1
python -m pytest -q -p no:cacheprovider quantum/test_search.py "$@"
