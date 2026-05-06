# Sentry setup runbook

**Owner:** Kasra (operator) — pre-pilot
**Audit reference:** Round 3 audit A11-P1-* (observability batch), implemented in PR-H
**Reconciles against:** `docs/COMPLIANCE_REGISTER.md` (Sentry row)

This runbook is the operator-facing companion to the code changes that
ship in Round 3 PR-H. It walks through:

1. Creating two Sentry projects (transcribe-md, marketing)
2. Generating an auth token for sourcemap upload
3. Populating `.env` with the seven Sentry env vars
4. Verifying PHI scrubbing before any real event flows
5. The BAA gate (Sentry must be on the executed-BAA list before pilot)

> **Status as of 2026-05-05:** Sentry BAA is **🟡 Pending** per
> `docs/COMPLIANCE_REGISTER.md`. The DSN env vars in `.env` should
> stay **empty** until the BAA is executed. With empty DSNs every
> `Sentry.init()` is a no-op and zero events leave the cluster — the
> safe default for pre-BAA state.

---

## 1. Create the Sentry projects

Sentry's free tier supports two projects per org, which is the shape
we need.

1. Sign in at sentry.io with the AshTech compliance email
   (`compliance@ashtechgroup.com` — set up the inbox first per
   `docs/runbooks/incident-response.md` §10).
2. Create org if missing: `ashtech-quillmd` (slug). This becomes
   `SENTRY_ORG`.
3. Create project 1: **transcribe-md**
   - Platform: Next.js
   - Alert me on: errors only (no transactions for now)
   - Slug: `transcribe-md` → `SENTRY_PROJECT_TRANSCRIBE_MD`
4. Create project 2: **marketing**
   - Platform: Next.js
   - Alert me on: errors only
   - Slug: `marketing` → `SENTRY_PROJECT_MARKETING`
5. Copy each project's DSN (Settings → Client Keys (DSN)). You'll need
   both DSNs in `.env` — there's a public-side variant and a
   server-side variant; for our config they're the same value but
   exposed under two different keys to mirror Sentry's
   client/server split.

---

## 2. Auth token for sourcemap upload

Sourcemaps make production stack traces useful. Without them, every
error is `<anonymous>:1:9214` and you'll spend twenty minutes
guessing which component threw.

1. sentry.io → Settings → Auth Tokens → **Create token**
2. Name: `quillmd-build-sourcemap-upload`
3. Scopes (minimum):
   - `project:read`
   - `project:releases`
   - `org:read`
4. **Copy the token now.** Sentry only shows it once.
5. Paste into `.env` as `SENTRY_AUTH_TOKEN=...`. Verify
   `chmod 600 /opt/meddoc-pro/.env` is still in place.
6. Tokens have no expiry by default. If a build host is compromised,
   revoke at sentry.io → Settings → Auth Tokens.

> **What happens if the token is missing:** the
> `withSentryConfig({ dryRun: !process.env.SENTRY_AUTH_TOKEN })` guard
> in `apps/*/next.config.ts` skips upload. Builds still complete; runtime
> events still flow; stack traces are minified. Acceptable for dev; not
> acceptable for production after pilot launch.

---

## 3. Populate `.env`

Append the block from `.env.example`:

```bash
SENTRY_DSN_TRANSCRIBE_MD=https://<key>@o<org>.ingest.sentry.io/<project>
SENTRY_DSN_MARKETING=https://<key>@o<org>.ingest.sentry.io/<project>
NEXT_PUBLIC_SENTRY_DSN_TRANSCRIBE_MD=$SENTRY_DSN_TRANSCRIBE_MD
NEXT_PUBLIC_SENTRY_DSN_MARKETING=$SENTRY_DSN_MARKETING
SENTRY_AUTH_TOKEN=<from step 2>
SENTRY_ORG=ashtech-quillmd
SENTRY_PROJECT_TRANSCRIBE_MD=transcribe-md
SENTRY_PROJECT_MARKETING=marketing
SENTRY_ENVIRONMENT=production
SENTRY_RELEASE=$(git -C /opt/meddoc-pro rev-parse --short HEAD)
NEXT_PUBLIC_SENTRY_ENVIRONMENT=production
NEXT_PUBLIC_SENTRY_RELEASE=$SENTRY_RELEASE
```

Then rebuild and restart:

```bash
cd /opt/meddoc-pro
docker compose build transcribe-md transcribe-md-worker marketing
docker compose up -d transcribe-md transcribe-md-worker marketing
```

The build phase uploads sourcemaps (look for `[sentry] Successfully
uploaded source maps` in the build logs). Restart picks up the new
runtime DSNs.

---

## 4. Verify PHI scrubbing BEFORE real traffic

This is the load-bearing step. Skipping it means a Prisma error
quoting a patient name lands in Sentry.

### 4a. Trigger a test exception (transcribe-md)

```bash
# Pick any signed-in test account on the staging environment.
# Visit a non-existent path that the catch-all error.tsx handles.
curl -sI https://app.quillmd.com/visits/__sentry-smoke-test__ \
  -H "Cookie: <your test session cookie>"
```

In Sentry → Issues, find the new event (~30s lag). Click into it and
verify:

- **No email** in any field
- **No patient name** in any breadcrumb
- **No transcript text** in any extra/context field
- The `event.message` and breadcrumb messages have run through
  `redactPhi()` — long strings show as `[REDACTED:NNNw]`, emails as
  `[EMAIL]`, phone numbers as `[PHONE]`.

### 4b. Verify the worker path

Submit a deliberately-malformed audio file (e.g., a renamed `.txt`
file uploaded with `.wav` extension). The worker will throw during
Layer 1; `captureWorkerException` should land an event tagged
`{visitId, layer: "L1", userId, practiceId}` with no audio bytes,
no patient name, no MRN.

### 4c. If PHI leaks

Stop the rollout. The scrub regex lives in
`packages/ai/src/log.ts` (server) and inline in
`apps/*/sentry.edge.config.ts` (edge). Add the leaking pattern to
both, redeploy, retest. Then **delete the Sentry events that leaked**
via sentry.io → Discover → bulk delete; document the incident in
`docs/runbooks/incident-response.md`.

---

## 5. BAA gate

> **Do NOT populate the DSN env vars in production until the Sentry
> BAA is executed.** Per `docs/COMPLIANCE_REGISTER.md`, Sentry is
> currently 🟡 Pending. Sentry offers self-serve BAA at
> sentry.io → Settings → Legal & Compliance → "Sign BAA". Sign it from
> the same org that owns the projects above.

The order is:

1. Create projects + auth token (this can happen any time — they're
   inert until DSNs are wired).
2. **Sign the BAA.** Save the executed PDF to your secret store.
3. Update `docs/COMPLIANCE_REGISTER.md` Sentry row from 🟡 to ✅ with
   the execution date.
4. Populate the DSN env vars in `.env`.
5. Run the verification in §4 against staging.
6. Restart prod.

---

## 6. Operational notes

### Releases

We tag every event with `SENTRY_RELEASE=<short-sha>`. Sentry
correlates this with the sourcemaps uploaded at build time. If
deminified traces stop working after a deploy, check that the
`SENTRY_RELEASE` value matches what was passed to
`withSentryConfig` at build time (Sentry uses release as a
join key — they have to match exactly).

### Worker context

The BullMQ worker initializes Sentry separately
(`apps/transcribe-md/src/worker-sentry.ts`). It uses
`@sentry/node` (not `@sentry/nextjs`) because it's a plain Node
process, but DSN + `redactPhi` posture mirror the Next.js side so
events from the worker land in the same project.

`captureWorkerException` is called from the outer catch in
`worker.ts`. It tags `{visitId, layer, userId, practiceId}` —
all UUIDs, no PHI. The Sentry user scope is set per-error
(`user: {id: userId}`) rather than at process scope (a worker
serves many users).

### Marketing

Marketing has no PHI in scope. The configs at
`apps/marketing/sentry.{client,server,edge}.config.ts` are
narrower than transcribe-md's — no `redactPhi` pass, no user
context wiring. If the marketing site ever starts collecting
form submissions with patient identifiers (it doesn't today),
the configs need to grow a `beforeSend` scrubber.

### Quotas

Sentry's free tier is 5k errors / 10k transactions per month. With
`tracesSampleRate: 0` we don't burn transactions. Errors should
average <100/month at pilot scale. If quota gets exceeded, alerts
silently stop — set up a sentry.io quota alert at 80% to avoid
silent failures.

### Disabling Sentry

To stop all events without a code change, blank both DSN env
vars in `.env` and restart. `Sentry.init()` becomes a no-op
when DSN is unset. This is the right escape hatch if a privacy
issue surfaces and you need to halt event flow while you
investigate.

---

## 7. Reconciliation checklist

After completing this runbook, reconcile:

- [ ] `docs/COMPLIANCE_REGISTER.md` — Sentry row updated to ✅
- [ ] `docs/LAUNCH_CHECKLIST.md` — Sentry box ticked
- [ ] `apps/marketing/src/app/hipaa/page.tsx` — Sentry mention
      reflects executed-BAA reality
- [ ] `.env` — chmod 600 verified post-edit
- [ ] Smoke test §4 ran cleanly with redacted output
- [ ] Quota alert configured at 80% in sentry.io

---

## PR-O closure (2026-05-06)

A separate operator (Claude in chat) drafted a "Sentry foundation"
PR brief on 2026-05-06 unaware that T-M16.3 + Round 3 PR-H had
already shipped the foundation. Lead investigated per memory #16
and closed PR-O as NAB. Three polish items were noted at
`docs/backlog/sentry-polish.md` for future consideration; none
are BAA-blocking.

**Foundation status:** COMPLETE.
**Activation status:** PENDING — gated on Sentry BAA per the
activation flow in §3 + §5 above.

Settled questions captured here so future investigations don't
re-walk them:

- **Why `redactPhi` (from `@meddoc/ai/log.ts`) over a per-PR scrubber?**
  `redactPhi` collapses any string longer than 20 words to a
  length marker (`[REDACTED:NNNw]`). Clinical free-text and
  transcripts routinely exceed 20 words. Replacing it with a
  500-char-threshold variant proposed in the PR-O brief would be
  strictly less safe — most transcripts pass through 500 chars
  before reaching 20 words.
- **Why per-app DSN env vars instead of a single `SENTRY_DSN`?**
  `SENTRY_DSN_TRANSCRIBE_MD` + `SENTRY_DSN_MARKETING` (with
  `SENTRY_DSN` fallback) lets each app land in its own Sentry
  project with its own alert routing. A single DSN would funnel
  marketing typos into the same triage queue as worker pipeline
  errors.
- **Why `tracesSampleRate: 0` permanently in foundation?**
  Performance traces include URL paths and span attributes that
  can carry visit UUIDs / patient IDs. Until the post-activation
  PHI sweep confirms `beforeSend` catches everything, traces
  stay off. Future: `0.1` once the sweep is clean.
- **Why no Sentry session replay?** Replay captures DOM, which
  on the visit-detail page includes transcript text. Permanently
  off-limits regardless of BAA.
