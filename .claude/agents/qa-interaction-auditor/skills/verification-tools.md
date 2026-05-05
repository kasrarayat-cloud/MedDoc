# Verification tools

The agent's runtime toolkit. Every snippet here is a copy-paste
template the agent can adapt at run-time. Patterns derived from
real diagnostics this week (PR #131, PR #132, the smoke-test
investigation).

## Playwright — headless browser walk

### Reuse the existing install

Memory: Playwright is already in `/opt/meddoc-pro/node_modules/playwright`
+ Chromium is cached at `~/.cache/ms-playwright/chromium-1217`.
**DO NOT** `npm install playwright` — it would download a fresh
Chromium (~150 MB disk + bandwidth). Import via absolute path.

```javascript
// Top of any Node ESM script the agent runs
import { chromium } from '/opt/meddoc-pro/node_modules/playwright/index.mjs';
```

### Authenticated session — log in as the test user

The test user is seeded per `fixtures/test-user.md`. The agent
loads its credentials from environment, not from a config file
in the repo (so the credentials never get committed).

```javascript
const TEST_EMAIL = process.env.QA_AUDITOR_EMAIL ?? 'qa-auditor@quillmd.test';
const TEST_PASSWORD = process.env.QA_AUDITOR_PASSWORD;
if (!TEST_PASSWORD) {
  console.error('QA_AUDITOR_PASSWORD not set — see fixtures/test-user.md');
  process.exit(1);
}

const browser = await chromium.launch({ headless: true });
const ctx = await browser.newContext({
  baseURL: 'https://app.quillmd.com',
  // Defensive: never store cookies on disk between runs.
  storageState: undefined,
});
const page = await ctx.newPage();

await page.goto('/login');
await page.fill('input[type="email"]', TEST_EMAIL);
await page.fill('input[type="password"]', TEST_PASSWORD);
await page.click('button[type="submit"]');
await page.waitForURL('**/visits**', { timeout: 15_000 });
```

### Enumerate interactive elements on a page

```javascript
const elements = await page.$$eval(
  'button, [role="button"], a[href^="/"], input[type="submit"]',
  (els) =>
    els
      .filter((el) => {
        const r = el.getBoundingClientRect();
        // Skip off-screen / display:none — they're not user-clickable
        return r.width > 0 && r.height > 0;
      })
      .map((el) => ({
        tag: el.tagName.toLowerCase(),
        text: (el.textContent ?? '').trim().slice(0, 80),
        disabled:
          'disabled' in el
            ? (el as HTMLButtonElement).disabled
            : el.getAttribute('aria-disabled') === 'true',
        href: el.getAttribute('href') ?? null,
        ariaLabel: el.getAttribute('aria-label') ?? null,
        role: el.getAttribute('role'),
      }))
);
```

### Click + wait for settle + classify

```javascript
async function clickAndClassify(page, locator, label) {
  // Snapshot Caddy log offset BEFORE click
  const beforeOffset = await snapshotCaddyOffset();
  // Snapshot DB BEFORE click — relevant tables for this page
  const beforeDb = await snapshotVisitState(visitId);

  // Click + wait for the network to settle
  const [response] = await Promise.all([
    page.waitForResponse(
      (r) =>
        r.request().method() !== 'GET' && r.url().includes('/api/'),
      { timeout: 5_000 }
    ).catch(() => null), // null = no mutation request fired
    locator.click(),
  ]);
  await page.waitForTimeout(500); // settle for any DOM mutation

  const afterOffset = await snapshotCaddyOffset();
  const afterDb = await snapshotVisitState(visitId);

  return {
    label,
    networkRequest: response
      ? { url: response.url(), status: response.status() }
      : null,
    caddyLines: await fetchCaddyLines(beforeOffset, afterOffset),
    dbDiff: diffSnapshots(beforeDb, afterDb),
    classification: classify(response, beforeDb, afterDb),
  };
}

function classify(response, before, after) {
  if (!response) return 'NO_NETWORK_FIRED'; // possible orphan dispatcher
  if (response.status() >= 200 && response.status() < 300) {
    if (JSON.stringify(before) === JSON.stringify(after)) {
      return 'PRETEND_SUCCESS_FALLBACK'; // 200 but no DB write
    }
    return 'OK';
  }
  return `HTTP_${response.status()}`;
}
```

### Reduced-motion + dark mode (match production)

QuillMD is dark-mode-only (per the design-reference snapshot).
Always launch contexts with `colorScheme: 'dark'`.

```javascript
const ctx = await browser.newContext({
  baseURL: 'https://app.quillmd.com',
  colorScheme: 'dark',
  reducedMotion: 'reduce', // prevents animation-frame timing flakes
});
```

## DB snapshot — `docker exec` + `psql`

### Snapshot a visit's mutable state

```bash
#!/usr/bin/env bash
# scripts/diff-db-state.sh
# Usage: diff-db-state.sh <visit-id> <label>
set -euo pipefail
VISIT_ID="$1"
LABEL="$2"  # e.g. "before-click" or "after-click"
OUT="/tmp/qa-${LABEL}-${VISIT_ID}.json"

docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA <<SQL > "$OUT"
SELECT row_to_json(t) FROM (
  SELECT
    id, status, "needsReview", "reviewReason",
    LENGTH("soapDraft") AS draft_len,
    LENGTH("soapFinal") AS final_len,
    "icdCodes"::text AS icd_json,
    "cptCodes"::text AS cpt_json,
    "rxDrafts"::text AS rx_json,
    "signedAt"::text AS signed_at,
    "updatedAt"::text AS updated_at
  FROM transcribe_visits WHERE id = '$VISIT_ID'
) t;
SQL

echo "$OUT"
```

### Audit log diff — were the right rows written?

```bash
docker exec meddoc-pro-postgres-1 psql -U meddoc -d meddoc -tA <<SQL
SELECT row_to_json(t) FROM (
  SELECT action, "createdAt"::text, metadata
  FROM audit_logs
  WHERE "targetId" = '$VISIT_ID'
    AND "createdAt" > NOW() - INTERVAL '5 minutes'
  ORDER BY "createdAt" ASC
) t;
SQL
```

The agent expects to see specific actions per workflow step. Map
in `quillmd-workflows.md`. A missing audit row when one was
expected = Pattern B (silent action) or Pattern A (event never
fired).

## Caddy access log inspection

Caddy logs every request to stdout. The agent reads recent log
lines via `docker logs`.

### Snapshot the current log offset

```bash
# Approximate offset as a count of lines in the last N minutes.
# Caddy doesn't expose stable byte offsets via docker logs; the
# agent uses timestamps as the cursor.
docker logs meddoc-pro-caddy-1 --since 5m 2>&1 | wc -l
```

### Filter to mutations within a time window

```bash
docker logs meddoc-pro-caddy-1 --since "30s ago" 2>&1 \
  | grep -oE '"method":"(POST|PATCH|PUT|DELETE)"[^}]*"uri":"[^"]+"' \
  | head -20
```

`scripts/check-network-mutations.mjs` wraps this and emits
structured JSON per request:

```javascript
// scripts/check-network-mutations.mjs
import { execSync } from 'node:child_process';

export function recentMutations(sinceSeconds = 30) {
  const raw = execSync(
    `docker logs meddoc-pro-caddy-1 --since "${sinceSeconds}s ago" 2>&1`,
    { encoding: 'utf-8', maxBuffer: 16 * 1024 * 1024 }
  );
  const mutations = [];
  for (const line of raw.split('\n')) {
    if (!line.includes('"method":')) continue;
    try {
      // Caddy access log lines contain a JSON object embedded in tab-separated fields
      const json = JSON.parse(line.slice(line.indexOf('{')));
      const method = json?.request?.method;
      if (!['POST', 'PATCH', 'PUT', 'DELETE'].includes(method)) continue;
      mutations.push({
        ts: json.ts ?? null,
        method,
        host: json.request.host,
        uri: json.request.uri,
        status: json.status,
        durationMs: Math.round((json.duration ?? 0) * 1000),
      });
    } catch {
      // Non-JSON log line — skip
    }
  }
  return mutations;
}
```

## Sentry breadcrumbs (when wired)

The agent checks `process.env.SENTRY_DSN` (or `NEXT_PUBLIC_SENTRY_DSN_TRANSCRIBE_MD`)
on the host. If unset → Sentry is in pre-BAA mode (per memory:
DSN stays empty until Sentry BAA executes). Skip this section in
that case.

When Sentry IS active, the agent can check Sentry's API for
breadcrumbs from the test user's session ID:

```bash
# Pseudo-curl — actual scope/auth varies per Sentry plan
curl -H "Authorization: Bearer $SENTRY_AUTH_TOKEN" \
  "https://sentry.io/api/0/projects/$SENTRY_ORG/$SENTRY_PROJECT_TRANSCRIBE_MD/events/?query=user.id:$TEST_USER_ID%20age:5m" \
  | jq '.[].breadcrumbs[]'
```

This is mostly a defense-in-depth check — Sentry catches errors
the Caddy log + DB diff don't.

## Worker logs (the BullMQ side)

When the workflow involves async pipeline work (audio processing),
the agent inspects the worker container's logs:

```bash
docker logs meddoc-pro-transcribe-md-worker-1 --since 2m 2>&1 \
  | grep -E "<VISIT_ID>|error|fail|throw" \
  | tail -40
```

Pattern: a visit transitioning READY but the worker logs show
"transient failure, awaiting BullMQ retry" repeatedly = the
classification logic is wrong. Pattern: visit stuck in PROCESSING
> 5 min with no log activity = worker dead.

## Network conditions to verify

Before declaring a click "broken," the agent confirms the basic
plumbing is healthy:

```bash
# Caddy + transcribe-md responding
curl -sI https://app.quillmd.com/api/health -m 5 | head -1
# Expected: HTTP/2 200

# Postgres reachable
docker exec meddoc-pro-postgres-1 pg_isready -U meddoc | head -1
# Expected: postgres:5432 - accepting connections
```

If either fails, the agent surfaces the infra issue and aborts
the walk — bugs found against an unhealthy system are noise.
