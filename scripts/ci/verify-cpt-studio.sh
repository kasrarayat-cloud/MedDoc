#!/usr/bin/env bash
# CPT Studio gates: Django system checks, migration drift, the full Django suite
# (discovered from tests/, never an explicit list), every ops unit-test suite and a
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

# Installer, download-verifier, verification-generator and browser-verifier unit
# tests: no Docker or sudo. unittest and node also report success when they find
# nothing, so every suite must show that it ran: a count floor per runner and the
# named ops modules. ops/verification has no __init__.py, so `discover -s ops`
# never reaches it; it is discovered on its own.
require_ran() {  # <log> <label>
  local count
  count=$(sed -nE 's/^Ran ([0-9]+) tests? in .*/\1/p' "$1" | tail -n 1)
  if [[ -z "$count" || "$count" -eq 0 ]]; then
    echo "$2: no tests ran." >&2
    exit 1
  fi
}
"$python" -B -m unittest discover -s ops -p 'test_*.py' -v 2>&1 | tee "$log"
require_ran "$log" 'ops unit tests'
for module in test_install test_verify_downloads; do
  if ! grep -q "($module\." "$log"; then
    echo "The ops suite $module did not run." >&2
    exit 1
  fi
done
"$python" -B -m unittest discover -s ops/verification -p 'test_*.py' -v 2>&1 | tee "$log"
require_ran "$log" 'verification generator tests'
if ! grep -q '(test_generate\.' "$log"; then
  echo 'The verification generator suite test_generate did not run.' >&2
  exit 1
fi
# node counts a test FILE that registers no tests as one passing test, so a count alone proves nothing:
# require the TAP summary, a pass floor near the committed count, and a named test that guards truth rule 5.
node --test --test-reporter=tap ops/verification/test_verify_browser.cjs 2>&1 | tee "$log"
node_pass=$(sed -nE 's/^# pass ([0-9]+)$/\1/p' "$log" | tail -n 1)
node_failed=$(sed -nE 's/^# fail ([0-9]+)$/\1/p' "$log" | tail -n 1)
if [[ -z "$node_pass" || "$node_pass" -lt 20 || "$node_failed" != 0 ]] \
    || ! grep -qE '^ok [0-9]+ - checkIncomplete refuses a dropped or silently completed incomplete service$' "$log"; then
  echo "Browser-verifier tests: passed ${node_pass:-none}, failed ${node_failed:-unknown}, or the named test did not run." >&2
  exit 1
fi

cd "$repo_root"
"$python" -m pip_audit -r cpt-studio/requirements.txt -r cpt-studio/requirements-dev.txt
