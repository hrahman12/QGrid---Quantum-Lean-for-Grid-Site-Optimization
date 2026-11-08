#!/usr/bin/env bash
# Runs quantum.grover_psiqdk inside WSL (PsiQDK's native simulator wheel is Linux/macOS only).
# usage: bash quantum/_wsl_grover.sh <repo root, WSL path> <job.json, WSL path> <result.json, WSL path>
# exit 3 = no ~/qsite-venv (caller falls back to the numpy simulation)
set -e
export PATH="$HOME/.local/bin:$HOME/.elan/bin:$PATH"
[ -f "$HOME/qsite-venv/bin/activate" ] || { echo "no ~/qsite-venv in WSL" >&2; exit 3; }
. "$HOME/qsite-venv/bin/activate"
cd "$1"
python -m quantum.grover_psiqdk --in "$2" --out "$3"
