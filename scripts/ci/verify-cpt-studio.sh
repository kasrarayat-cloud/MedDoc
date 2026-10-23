#!/usr/bin/env bash
# CPT Studio gates: Django system checks, migration drift, the full Django suite
# (discovered from tests/, never an explicit list), the ops unit tests and a
# dependency audit. Synthetic data only; no provider, production service or
# host configuration is touched. Needs a disposable PostgreSQL and the
# CPT_STUDIO_* variables the workflow sets.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
python=${CPT_STUDIO_CI_PYTHON:-python3}
if [[ "$python" == */* && "$python" != /* ]]; then
  python="$repo_root/$python"
fi

: "${CPT_STUDIO_SECRET_KEY:?Supply a synthetic CI secret}"
: "${CPT_STUDIO_DB_PASSWORD:?Supply the isolated CI database password}"
if [[ "${CPT_STUDIO_PROVIDER_MODE:-disabled}" != disabled ]]; then
  echo 'The CPT Studio gates run with CPT_STUDIO_PROVIDER_MODE=disabled only.' >&2
  exit 1
fi

cd "$repo_root/cpt-studio"
"$python" manage.py check
"$python" manage.py makemigrations --check --dry-run

# Django reports success when discovery finds nothing, so a suite that vanished
# (a renamed package, a broken __init__) would pass silently. Require tests ran.
log=$(mktemp)
trap 'rm -f "$log"' EXIT
"$python" manage.py test tests --noinput 2>&1 | tee "$log"
ran=$(sed -nE 's/^Ran ([0-9]+) tests? in .*/\1/p' "$log" | tail -n 1)
if [[ -z "$ran" || "$ran" -eq 0 ]]; then
  echo 'No CPT Studio Django tests were discovered.' >&2
  exit 1
fi

# Installer and verifier unit tests: standard library only, no Docker or sudo.
"$python" -B -m unittest discover -s ops -p 'test_*.py' -v

cd "$repo_root"
"$python" -m pip_audit -r cpt-studio/requirements.txt -r cpt-studio/requirements-dev.txt
