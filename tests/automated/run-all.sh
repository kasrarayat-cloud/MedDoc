#!/usr/bin/env bash
# tests/automated/run-all.sh — master runner + HTML reporter.
#
# Usage:
#   bash tests/automated/run-all.sh --smoke        # ~5s
#   bash tests/automated/run-all.sh --monitoring   # quick monitoring pass
#   bash tests/automated/run-all.sh --e2e          # full Playwright run
#   bash tests/automated/run-all.sh --all          # everything
#
# Behavior:
#   - Each sub-suite produces JSON on stdout (smoke/*) or in
#     reports/playwright-latest.json (e2e).
#   - Results are aggregated into reports/YYYY-MM-DD-HH-MM.json and
#     rendered to reports/YYYY-MM-DD-HH-MM.html via the Node helper.
#   - Exits 0 iff every suite passed. Exits 1 otherwise — usable as a
#     post-deploy gate or a CI step.

set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
# shellcheck disable=SC1091
source "$HERE/lib/common.sh"
load_test_env

SUITE_SMOKE=false
SUITE_MONITORING=false
SUITE_E2E=false

for arg in "$@"; do
  case "$arg" in
    --smoke)       SUITE_SMOKE=true ;;
    --monitoring)  SUITE_MONITORING=true ;;
    --e2e)         SUITE_E2E=true ;;
    --all)         SUITE_SMOKE=true; SUITE_MONITORING=true; SUITE_E2E=true ;;
    -h|--help)
      head -n 15 "$0" | sed 's/^# \?//'
      exit 0 ;;
    *) echo "unknown flag: $arg" >&2; exit 2 ;;
  esac
done

if ! $SUITE_SMOKE && ! $SUITE_MONITORING && ! $SUITE_E2E; then
  echo "Pass at least one of: --smoke --monitoring --e2e --all" >&2
  exit 2
fi

TS=$(date -u '+%Y-%m-%d-%H-%M')
REPORT_JSON="$HERE/reports/$TS.json"
REPORT_HTML="$HERE/reports/$TS.html"
mkdir -p "$HERE/reports/screenshots"

# --- aggregate suite results -----------------------------------------------
# Every suite appends one line of JSON to $REPORT_JSON.tmp. At the end we
# wrap the lines in a parent array and hand it to the Node renderer.
TMP_JSONL="$REPORT_JSON.tmp"
: > "$TMP_JSONL"
FAIL=0

run_shell_suite() {
  local label="$1" script="$2"
  echo "${C_BLUE}▶ $label${C_RESET}"
  local out
  if ! out=$(OUTPUT_MODE=json bash "$script" 2>&1); then FAIL=1; fi
  # The shell suites emit one JSON object on their last line.
  local last
  last=$(echo "$out" | tail -n 1)
  if ! python3 -c 'import json,sys; json.loads(sys.argv[1])' "$last" 2>/dev/null; then
    # If JSON parse fails, synthesize a failure record so the report
    # still shows something meaningful.
    last=$(python3 -c 'import json,sys; print(json.dumps({
      "suite": sys.argv[1],
      "pass": 0, "fail": 1, "warn": 0, "skip": 0,
      "results": [{"name": "runner parse", "status": "fail", "durationMs": 0, "details": sys.argv[2]}],
    }))' "$label" "$(echo "$out" | tail -n 20)")
    FAIL=1
  fi
  echo "$last" >> "$TMP_JSONL"
}

run_playwright_suite() {
  echo "${C_BLUE}▶ e2e (Playwright)${C_RESET}"
  # Playwright runs from the transcribe-md workspace (where the package
  # is installed) but uses our config under tests/automated/e2e/. No
  # --reporter override on the CLI: that would replace the config's
  # reporter list and the json file with outputFile would never be
  # written. Config-level reporters include list, json (our file), html.
  (
    cd /opt/meddoc-pro/apps/transcribe-md
    npx playwright test --config="$HERE/e2e/playwright.config.ts" \
      >/dev/null 2>&1
  ) || FAIL=1

  local pw="$HERE/reports/playwright-latest.json"
  if [[ ! -s "$pw" ]]; then
    python3 -c 'import json; print(json.dumps({
      "suite": "e2e",
      "pass": 0, "fail": 1, "warn": 0, "skip": 0,
      "results": [{"name": "playwright runner", "status": "fail", "durationMs": 0,
                   "details": "no playwright-latest.json produced"}],
    }))' >> "$TMP_JSONL"
    return
  fi

  # Flatten Playwright's native JSON into our shape.
  python3 "$HERE/lib/flatten_playwright.py" "$pw" >> "$TMP_JSONL"
}

if $SUITE_SMOKE; then
  run_shell_suite "smoke / health"     "$HERE/smoke/health.sh"
  run_shell_suite "smoke / auth-flow"  "$HERE/smoke/auth-flow.sh"
fi
if $SUITE_MONITORING; then
  run_shell_suite "monitoring / disk"       "$HERE/monitoring/disk-monitor.sh"
  run_shell_suite "monitoring / containers" "$HERE/monitoring/container-health.sh"
fi
if $SUITE_E2E; then
  run_playwright_suite
fi

# --- wrap + render --------------------------------------------------------
python3 -c '
import json, sys, time
with open(sys.argv[1]) as f:
    lines = [l for l in f.read().splitlines() if l.strip()]
suites = [json.loads(l) for l in lines]
report = {
  "generatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "suites": suites,
}
with open(sys.argv[2], "w") as f:
    json.dump(report, f, indent=2)
' "$TMP_JSONL" "$REPORT_JSON"
rm -f "$TMP_JSONL"

python3 "$HERE/lib/render_report.py" "$REPORT_JSON" "$HERE/reports/template.html" "$REPORT_HTML"

echo
echo "${C_DIM}→ json: $REPORT_JSON${C_RESET}"
echo "${C_DIM}→ html: $REPORT_HTML${C_RESET}"

exit $FAIL
