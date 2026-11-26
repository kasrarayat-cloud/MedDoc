#!/usr/bin/env bash
# CPT Studio gates: Django system checks, migration drift, the full Django suite
# (discovered from tests/, never an explicit list), every ops unit-test suite, the
# browser walk's own tests and a dependency audit. Synthetic data only; nothing is
# sent to the coding service and no production service or host configuration is
# touched. Needs a disposable PostgreSQL and the CPT_STUDIO_* variables the
# workflow sets.
set -euo pipefail
repo_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)
python=${CPT_STUDIO_CI_PYTHON:-python3}
if [[ "$python" == */* && "$python" != /* ]]; then
  python="$repo_root/$python"
fi

: "${CPT_STUDIO_SECRET_KEY:?Supply a synthetic CI secret}"
: "${CPT_STUDIO_DB_PASSWORD:?Supply the isolated CI database password}"
# CPT_STUDIO_CODING_MODE is the one setting that sends anything (studio/fable/client.py).
if [[ "${CPT_STUDIO_CODING_MODE:-disabled}" != disabled ]]; then
  echo 'The CPT Studio gates run with CPT_STUDIO_CODING_MODE=disabled only.' >&2
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
# Release 2 (R2-3, D358): tests/test_request_identity.py pins what the coder is sent and the coding files' blob ids.
# The suite above ran it among the rest; here each of its tests must run and pass with none skipped (this is a git
# checkout, so its blob test reads HEAD too), so the pin cannot leave the gate by vanishing or by a skip.
require_request_identity() {  # <log>
  local pinned
  for pinned in TheCoderIsSentWhatRelease1SentTests.test_the_settings_are_release_1_s \
      TheCoderIsSentWhatRelease1SentTests.test_each_request_is_release_1_s \
      TheCodingFilesKeepTheirBlobsTests.test_each_file_on_disk_is_release_1_s_blob \
      TheCodingFilesKeepTheirBlobsTests.test_git_s_head_names_the_same_blobs; do
    if ! grep -qF "(tests.test_request_identity.$pinned) ... ok" "$1" || ! grep -qx 'OK' "$1"; then
      echo "The request identity pin (R2-3): $pinned did not run and pass, or a test of it failed or was skipped." >&2
      exit 1
    fi
  done
}
PYTHONUNBUFFERED=1 "$python" manage.py test tests.test_request_identity --noinput -v 2 2>&1 | tee "$log"
require_request_identity "$log"

# Installer, sign-in verifier, customer-scanner, verification and browser-walk unit
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
for module in test_install test_install_coding test_verify_login test_verify_scan_customer; do
  require_module_passed "$log" "$module" "The ops suite $module"
done
"$python" -B -m unittest discover -s ops/verification -p 'test_*.py' -v 2>&1 | tee "$log"
require_ran "$log" 'verification generator tests'
require_module_passed "$log" test_generate 'The verification generator suite test_generate'
# node counts a test FILE that registers no tests as one passing test, so a count alone proves nothing:
# require the TAP summary, a pass floor, '# fail 0', and three named tests: one guards the customer surface's
# denylist (no vendor or model name reaches a customer), two the operator gate (release 1: the console lives on the
# admin host and no operator reads an encounter on the doctors' site, A11 and D10, so the doctors' side and the
# gate's own control are two tests; the old name, with 'and the operator reads the encounter', is gone with that
# guarantee). Release 2 (R2-1): the floor is the 59 tests that need no browser; the browser tests are skipped where
# Playwright is not installed, as on this runner, and a skip for any other reason fails here, so no test leaves the
# gate by being skipped. Where Playwright is installed the same file is the local browser gate (at least 104 tests,
# none failed, none skipped: a release gate, run on the host).
require_walk_passed() {  # <log>
  local passed failed skipped_otherwise
  passed=$(sed -nE 's/^# pass ([0-9]+)$/\1/p' "$1" | tail -n 1)
  failed=$(sed -nE 's/^# fail ([0-9]+)$/\1/p' "$1" | tail -n 1)
  skipped_otherwise=$(grep -E ' # SKIP' "$1" | grep -cvE ' # SKIP no Playwright at ' || true)
  if [[ -z "$passed" || "$passed" -lt 59 || "$failed" != 0 || "$skipped_otherwise" != 0 ]] \
      || ! grep -qE '^ok [0-9]+ - the denylist scan finds exactly what every vector of customer-denylist\.json says, as its other readers do$' "$1" \
      || ! grep -qE "^ok [0-9]+ - every /ops/ path is 404 to the customer and never 200 to nobody, its POSTs with the session's CSRF token$" "$1" \
      || ! grep -qE "^ok [0-9]+ - the operator gate's control needs no operator: the admin gate, the doctors' 404, the member refused \(A11\)$" "$1"; then
    echo "Browser-walk tests: passed ${passed:-none}, failed ${failed:-unknown}, ${skipped_otherwise} skipped for a reason other than no Playwright, or a named test did not run." >&2
    exit 1
  fi
}
node --test --test-reporter=tap ops/test_walk.cjs 2>&1 | tee "$log"
require_walk_passed "$log"

cd "$repo_root"
"$python" -m pip_audit -r cpt-studio/requirements.txt -r cpt-studio/requirements-dev.txt
