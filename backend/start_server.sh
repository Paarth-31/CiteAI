#!/usr/bin/env bash
set -euo pipefail

backend_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$backend_dir"

if [[ ! -x .venv/bin/python ]]; then
  printf 'Backend virtual environment not found at %s/.venv\n' "$backend_dir" >&2
  exit 1
fi

exec .venv/bin/python -m flask --app manage run --host 127.0.0.1 --port 8000
