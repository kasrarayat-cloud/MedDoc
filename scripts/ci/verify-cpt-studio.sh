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

# Django and unittest report success when discovery finds nothing, and their
# "Ran N" counts SKIPPED tests too, so a suite that vanished (a renamed package, a
# broken __init__) or whose every test is skipped would pass silently. Each
# runner must show more tests ran than were skipped.
require_ran() {  # <log> <label>
  local count skipped
  count=$(sed -nE 's/^Ran ([0-9]+) tests? in .*/\1/p' "$1" | tail -n 1)
  skipped=$(sed -nE 's/^(OK|FAILED) \(.*skipped=([0-9]+).*\)$/\2/p' "$1" | tail -n 1)
  if [[ -z "$count" || "$count" -le "${skipped:-0}" ]]; then
    echo "$2: no tests ran (ran ${count:-none}, skipped ${skipped:-0})." >&2
    exit 1
  fi
}
log=$(mktemp)
trap 'rm -f "$log"' EXIT
"$python" manage.py test tests --noinput 2>&1 | tee "$log"
require_ran "$log" 'CPT Studio Django tests'

# Installer, download-verifier, verification-generator and browser-verifier unit
# tests: no Docker or sudo. Every suite must show that it ran: a count floor per
# runner, and at least one PASSING test in each named ops module (a module whose
# tests are all skipped prints its test lines too, ending '... skipped').
# ops/verification has no __init__.py, so `discover -s ops` never reaches it; it
# is discovered on its own.
require_module_passed() {  # <log> <module> <label>
  if ! grep -qE "\\($2\\.[^)]*\\) \\.\\.\\. ok\$" "$1"; then
    echo "$3 did not run: no test in it passed." >&2
    exit 1
  fi
}
"$python" -B -m unittest discover -s ops -p 'test_*.py' -v 2>&1 | tee "$log"
require_ran "$log" 'ops unit tests'
for module in test_install test_verify_downloads; do
  require_module_passed "$log" "$module" "The ops suite $module"
done
"$python" -B -m unittest discover -s ops/verification -p 'test_*.py' -v 2>&1 | tee "$log"
require_ran "$log" 'verification generator tests'
require_module_passed "$log" test_generate 'The verification generator suite test_generate'
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
