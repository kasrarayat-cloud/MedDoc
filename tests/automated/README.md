# tests/automated — solo-dev regression harness

Everything runs itself and tells you what broke. No manual clicking.

## Layout

```
tests/automated/
├── smoke/           # post-deploy health checks, ~5s
├── e2e/             # Playwright specs against prod URLs
├── monitoring/      # cron-driven uptime / disk / container watchers
├── reports/         # generated HTML + JSON reports (gitignored)
├── lib/             # shared helpers (bash + python)
├── .env.test.example
├── run-all.sh       # master runner
├── setup-cron.sh    # install/uninstall cron entries
└── README.md
```

## Quick start

```bash
cp tests/automated/.env.test.example tests/automated/.env.test
# fill in TEST_APP_EMAIL / TEST_APP_PASSWORD at minimum
bash tests/automated/run-all.sh --smoke
```

If every check passes you'll see a final timestamped HTML report at
`tests/automated/reports/YYYY-MM-DD-HH-MM.html`. Open it in a browser —
the filters on top let you hide everything except failures.

## Running suites

```bash
bash tests/automated/run-all.sh --smoke        # ~5s, runs against prod
bash tests/automated/run-all.sh --monitoring   # disk + container check
bash tests/automated/run-all.sh --e2e          # full Playwright run
bash tests/automated/run-all.sh --all          # everything
```

Individual scripts work on their own too:

```bash
bash tests/automated/smoke/health.sh           # colored text
OUTPUT_MODE=json bash tests/automated/smoke/health.sh   # JSON only
```

Playwright specs can run without the wrapper:

```bash
cd apps/transcribe-md
npx playwright test --config=/opt/meddoc-pro/tests/automated/e2e/playwright.config.ts
```

## Suites

### Smoke (`smoke/`)
- `health.sh` — 5 public URLs + docker container state + disk + memory.
  Ignores the caddy wget-fork healthcheck because the service routes
  traffic correctly regardless.
- `auth-flow.sh` — NextAuth credentials login/logout round-trip on
  app.quillmd.com. Skips cleanly when creds aren't set.

### E2E (`e2e/*.spec.ts`)
- `password-policy.spec.ts` — signup form enforces 10+char/upper/lower/digit.
- `rate-limiting.spec.ts` — 6th failed login is rate-limited.
  Opt-in via `E2E_READ_ONLY=false` — leaves the test IP blocked for 15 min.
- `full-visit-flow.spec.ts` — login → new visit → upload audio → wait
  for READY → SOAP present → sign. Opt-in (mutates prod state).
- `mobile-responsiveness.spec.ts` — iPhone 13 viewport; asserts no
  horizontal overflow; screenshots land under `reports/screenshots/`.
- `soap-determinism.spec.ts` — three identical dictations → cosine
  similarity ≥ 0.80 on the SOAP text. Opt-in
  (`ENABLE_DETERMINISM_TEST=true` + `E2E_READ_ONLY=false`).

### Monitoring (`monitoring/`)
Each script runs, checks once, and exits. Stateful dedupe in
`/var/log/meddoc-alerts.state` (falls back to `~/.meddoc-alerts.state`).

- `uptime-check.sh` — cron every 5 min; alerts after two consecutive
  failures; announces recovery.
- `disk-monitor.sh` — hourly; alerts on <10GB free OR >90% used.
- `container-health.sh` — every 10 min; flags any unhealthy /
  non-Up meddoc-pro container (caddy whitelisted).

## Adding a new test

### New smoke check

Add a function to `smoke/health.sh` (or create a new file — the
runner picks up `smoke/*.sh`). Use the shared helpers:

```bash
source "$HERE/../lib/common.sh"
load_test_env

t0=$(now_ms)
# ... do the check ...
record_result "my new check" pass $(( $(now_ms) - t0 )) "optional detail"
```

End the script with `emit_and_exit "my-suite-name"` — this is what
makes the JSON shape the runner expects.

### New Playwright spec

Drop a new file in `e2e/*.spec.ts`. Import shared helpers from
`./helpers/*`. Follow the pattern: call `requireTestCreds('app')`
and `test.skip(!creds, '...')` at the top of any spec that needs to
be logged in, so missing creds skip cleanly instead of failing.

For anything that mutates prod (signing visits, creating patients,
sending emails), guard with `test.skip(E2E_READ_ONLY, '...')`.

### New monitoring check

Copy `disk-monitor.sh` as a template. The Resend-backed `send_alert`
helper is inlined in each script on purpose — no cross-script
dependencies, so each can be edited/debugged in isolation.

## Interpreting reports

The HTML report shows one section per suite. Each section has a
pass/fail summary and a per-test table. Filter toolbar at the top:

- **All** (default): everything
- **Fail only**: the important view when you're debugging
- **Pass only**: rarely useful, included for symmetry

Click a row's **Details** cell to copy the error message — paste
straight into an issue.

JSON reports alongside the HTML have the same data in a machine-
readable form:

```json
{
  "generatedAt": "…Z",
  "suites": [
    { "suite": "smoke-health", "pass": 8, "fail": 0, "results": [ … ] }
  ]
}
```

## Setting up alerting

1. Create a Resend API key.
2. Add to `.env.test`:
   ```
   TEST_ALERT_RESEND_API_KEY=re_...
   TEST_ALERT_FROM=alerts@quillmd.com
   TEST_ALERT_TO=you@example.com
   ```
3. Run `bash tests/automated/setup-cron.sh` to install the recurring
   checks. Verify with `crontab -l`.

Without Resend configured, alerts land only in `/var/log/meddoc-alerts.log`
(or `~/.meddoc-alerts.log` when /var/log isn't writeable). That's still
usable as forensic evidence after the fact, just not proactive.

## GitHub Actions

`.github/workflows/nightly-tests.yml` runs smoke + e2e at 02:00 UTC
daily, uploads the report as an artefact, and opens a GitHub issue
on failure. Set these repo secrets to enable the authenticated
specs in CI:

- `TEST_APP_EMAIL`, `TEST_APP_PASSWORD` — transcribe-md test user
- `TEST_PRO_EMAIL`, `TEST_PRO_PASSWORD` — meddoc-pro test user (optional)

Missing secrets just mean the dependent specs skip.

## Troubleshooting

### "dotenv tip" in playwright output
Harmless — dotenv@17 emits a promotional line on every load.
`playwright.config.ts` sets `quiet: true` so it doesn't land in
reports; it can still appear when you invoke playwright manually.

### Smoke auth-flow skipped
`TEST_APP_EMAIL` / `TEST_APP_PASSWORD` aren't set in `.env.test`.
Create an account on app.quillmd.com that the suite can reuse
(keep the password strong, don't reuse a real user's).

### Report HTML is 1 big blob with no styling
Make sure you opened the `.html` in a browser, not the `.json`.

### Cron entries not firing
- Check `crontab -l` shows the MEDDOC-TESTS block.
- `tail -f /var/log/meddoc-cron.log` to see what happened.
- `bash tests/automated/setup-cron.sh --dry` prints the block it
  would install without applying.
- Non-privileged crontab doesn't have access to `docker ps` unless
  the running user is in the `docker` group.

### Playwright complains about missing browsers
```bash
cd apps/transcribe-md && npx playwright install chromium
```

### Rate-limit spec blocked the test IP
Expected — wait 15 min, or set `E2E_READ_ONLY=true` so that spec
skips on future runs.
