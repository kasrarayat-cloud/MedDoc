# Launch Checklist — TranscribeMD First-Doctor Pilot

Pre-launch operational tracker. Every box below must be checked before
the first real doctor's credentials get issued and real PHI starts
flowing. Audit-clean code (T-M18.1–18.3: 27/27 findings resolved) is
the _starting_ condition for this list, not the end of it.

This doc complements — does not replace:
- `docs/DEPLOYMENT_RUNBOOK.md` — how to deploy
- `docs/BAA_CHECKLIST.md` — third-party BAA processor matrix
- `docs/ROTATION_RUNBOOK.md` — credential rotation procedure
- `docs/KNOWN_ISSUES.md` — open operational caveats

Last reviewed: **2026-04-21** (post T-M18.3 merge)

---

## Launch gate — all must be ✅ before first doctor login

This is the TL;DR. Every item below is expanded in its own section.

- [x] **1. Domain purchased + A records set** (§1) — `quillmd.com` + 3 subdomains live (T-M19)
- [x] **2. HTTPS live via Caddy MODE B** (§2) — Let's Encrypt certs for all 4 hostnames (T-M19.1)
- [ ] **3. All four BAAs signed + on file** — Anthropic, OpenAI, Deepgram, hosting provider (§3)
- [ ] **4. Stripe subscription flow working end-to-end** ($49/mo tier) (§4)
- [ ] **5. Resend sender domain verified** (SPF/DKIM/DMARC green) (§5)
- [ ] **6. OPENAI_API_KEY rotated + old key revoked** (§6)
- [ ] **7. Legal docs reviewed + published** — ToS, Privacy, BAA template, HIPAA attestation (§7)
- [ ] **8. Monitoring wired** — Sentry alerts + uptime probe + cron heartbeat alerts (§8)
- [ ] **9. Pilot doctor(s) onboarded** with feedback channel live (§9)

No item can be skipped. If one is blocked, the launch is blocked —
flag it in §10 ("Blockers & open decisions") rather than silently dropping it.

---

## 1. Domain purchase

**Status:** pending user decision.

TranscribeMD currently answers on `http://5.231.107.93:9020` (MODE A,
plaintext). No real doctor sees that URL — plaintext carrying PHI is a
HIPAA violation regardless of BAA status. A domain unlocks: HTTPS,
sender-verified email, a trustworthy URL on Stripe receipts, and
canonical references in Terms/Privacy.

### Decisions needed
- [ ] Pick the apex domain (suggested: `transcribemd.com` / `.ai` / `.health`)
- [ ] Decide on subdomain layout. Current code expects three URLs:
  - `app.<domain>` (TranscribeMD, was `:9020`)
  - `www.<domain>` or apex (marketing, was `:9010`)
  - `pro.<domain>` (MedDoc Pro CRM, was `:80`)
  - Three hostnames ⇒ three `A` records ⇒ three Caddy blocks

### Action
- [ ] Purchase domain through any registrar (Cloudflare Registrar, Namecheap, Porkbun — registrar choice doesn't matter)
- [ ] Do NOT enable Cloudflare proxy (orange cloud) — Caddy needs to terminate TLS with a real cert, not a Cloudflare-origin cert
- [ ] Record the domain in `docs/DEPLOYMENT_RUNBOOK.md` §1 as the canonical deploy host

---

## 2. DNS + Caddy HTTPS setup

**Status:** ✅ shipped 2026-04-21 (T-M19.1 + T-M19.2).

Caddy cut over from MODE A (IP-based plaintext) to MODE B (domain-based
HTTPS with HSTS + CSP Report-Only). Let's Encrypt certs issued on first
hit for all four hostnames, persisted in the `caddy_data` volume.

### Pre-flight
- [x] Ports `80` + `443` open on the VPS firewall
- [x] Four `A` records pointing at the VPS IP: `@`, `www`, `app`, `pro` (all four — `pro` added for the MedDoc Pro CRM subdomain that the original plan missed)
- [x] DNS propagated — all four `dig +short A` lookups returned the VPS IP before cutover

### Cutover (done)
- [x] Uncommented MODE B blocks in `Caddyfile`, commented out MODE A (`:80` / `:9010` / `:9020`) as rollback reference with HSTS-safe-rollback note
- [x] Updated `.env` (kept out of git) with production URL envs:
  - `PUBLIC_URL=https://pro.quillmd.com`
  - `TRANSCRIBE_MD_AUTH_URL=https://app.quillmd.com`
  - `MARKETING_URL=https://quillmd.com`
  - `AUTH_COOKIE_DOMAIN=` (left empty — meddoc-pro + transcribe-md run independent auth stacks; sharing a cookie scope would risk JWT cross-verification gaps)
- [x] `docker compose up -d --force-recreate caddy transcribe-md meddoc-pro marketing`
- [x] Let's Encrypt E7/E8 certs obtained for all four hostnames on first hit
- [x] Smoke test: `curl -I https://app.quillmd.com/api/health` → `HTTP/2 200` with HSTS header present

### T-M19.2 follow-up fix
- [x] Marketing "Sign In" link was baked in at build-time with the old `http://5.231.107.93:9020` fallback — `NEXT_PUBLIC_*` vars weren't landing in the Next builder stage (monorepo `next build` doesn't read root `.env`). Fixed by wiring `NEXT_PUBLIC_TRANSCRIBE_MD_APP_URL` + `NEXT_PUBLIC_MARKETING_URL` as `build: args:` in `docker-compose.yml` + `ARG`/`ENV` in both Dockerfiles. Marketing rebuilt with correct URLs post-fix.
- [x] `/api/health` version string fix (`??` → `||`) so compose's `${APP_VERSION:-}` empty-string default falls back correctly to the hardcoded milestone.

### Post-cutover regressions to re-run
- [ ] `bash scripts/verify-t-m18-2.sh` — adjust the hardcoded `http://localhost:9020` URLs to the new HTTPS hostname before running, or keep localhost-probes in parallel
- [ ] `bash scripts/verify-t-m18-3.sh` — same
- [ ] Browser-test the full signup → email-verify → login → dashboard flow from `https://quillmd.com` through `https://app.quillmd.com/dashboard` — in progress as of this PR

---

## 3. BAA agreements

**Status:** **ZERO signed** as of this writing. Launch blocker.

Detail lives in `docs/BAA_CHECKLIST.md` (processor matrix + PHI flow
per processor). This section tracks the sign-and-file workflow only.

Critical path: **no real patient data hits any of these until the BAA
is counter-signed + archived.** The code path is already live; the gate
is paper.

### Per-processor
- [ ] **Anthropic** — request BAA via https://support.anthropic.com (fill the HIPAA-BAA contact form). Requires an Anthropic org on a paid plan. Confirm the signed PDF covers Claude Sonnet 4.6 + embedding + all future Claude model IDs.
- [ ] **OpenAI** — request via the Enterprise/Business tier (Startup credits tier does NOT include a BAA). Scope must cover `text-embedding-3-small` + any `gpt-*` models currently referenced in `packages/ai/src/openai.ts`.
- [ ] **Deepgram** — standard BAA template at https://deepgram.com/legal. Scope must cover `nova-3-medical`.
- [ ] **VPS hosting provider** — whoever the current VPS is rented from needs a signed BAA too. Postgres + MinIO store PHI on their infrastructure. Check current provider's HIPAA program or migrate to one that has one (AWS, GCP, Azure, Linode-Akamai all have compliant programs).

### File + surface
- [ ] Store signed PDFs in a secure, access-logged location (NOT in the git repo)
- [ ] Update `docs/BAA_CHECKLIST.md` table: flip each `☐ NOT YET` to `✅ YYYY-MM-DD` with the date on the signed document
- [ ] When all four are signed, check the master gate item in §0 of this doc

### Sentry note
`docs/BAA_CHECKLIST.md` flags Sentry as needing a BAA before `SENTRY_DSN_*`
env vars are set. Currently these env vars are blank — that's the
safe default. Do NOT populate them on production until either:
(a) Sentry BAA signed, or (b) self-hosted Sentry inside the VPS perimeter.

---

## 4. Stripe subscription — $49/mo tier

**Status:** not yet integrated (no `STRIPE_*` vars in `.env.production.example`).

The product currently has no billing surface. Pilot doctors will need
one (even if the first 1–3 are comped) so the infrastructure is in
place when we onboard paying users.

### Stripe account setup
- [ ] Create a live-mode Stripe account (if not already done) and complete onboarding
- [ ] Enable Tax (Stripe auto-collects sales tax where applicable)
- [ ] Confirm Stripe's HIPAA posture: standard Stripe does NOT need a BAA because billing metadata is not PHI — but confirm no PHI is ever sent in `description`, `metadata`, or receipt line-items

### Product + price
- [ ] Create one Product: "TranscribeMD Doctor Subscription"
- [ ] Create one Price: `$49.00 USD / month`, recurring, active
- [ ] Note the `price_id` — it'll go into `STRIPE_DEFAULT_PRICE_ID` env

### Integration work (code change — scope outside this doc)
- [ ] Stripe Checkout Session creation endpoint
- [ ] Webhook endpoint `/api/webhooks/stripe` (verify with `STRIPE_WEBHOOK_SECRET`)
- [ ] Handle: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- [ ] Customer Portal link for self-serve cancel / card update
- [ ] Gate the app on `User.subscriptionStatus` (new column); expired = read-only dashboard
- [ ] Ship behind a feature flag so pilot doctors can bypass until we're ready to collect payment

### Env vars to add
- [ ] `STRIPE_SECRET_KEY=sk_live_...`
- [ ] `STRIPE_WEBHOOK_SECRET=whsec_...`
- [ ] `STRIPE_DEFAULT_PRICE_ID=price_...`
- [ ] `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_live_...`

---

## 5. Resend domain verification

**Status:** config scaffolded; blocked on §1.

`.env.production.example` already has `RESEND_API_KEY` + `RESEND_FROM` +
`RESEND_FROM_VERIFIED=false`. The last flag gates production sends —
the code refuses to send from an unverified sender per T-M16.2. Flipping
to `true` is the last step, not the first.

### Sender setup (post-domain)
- [ ] Log into Resend dashboard, add `<domain>` as a sender domain
- [ ] Resend emits four DNS records: three TXT (SPF, DKIM, DMARC) + one MX
- [ ] Add all four records at your DNS registrar
- [ ] Wait for Resend to verify (polls DNS; usually <10 min)
- [ ] Pick a production sender address: `noreply@<domain>` or `hello@<domain>`

### Env flip
- [ ] `RESEND_API_KEY=re_...` (live key, not test)
- [ ] `RESEND_FROM=noreply@<domain>`
- [ ] `RESEND_FROM_VERIFIED=true`  ← only after DNS verified
- [ ] `docker compose up -d --force-recreate transcribe-md meddoc-pro`

### Smoke test
- [ ] Trigger a password-reset email to a real mailbox you control
- [ ] Confirm: inbox (not spam), valid DKIM signature, sender shows as `<domain>` not `resend.dev`
- [ ] Check Resend dashboard — delivery event recorded

---

## 6. `OPENAI_API_KEY` rotation (leaked during development)

**Status:** open security debt. Key was exposed in a dev log / commit / screen-share
(root cause TBD below). Must rotate before production use.

### Rotate
- [ ] Log into OpenAI dashboard → API Keys → Delete the leaked key (don't just name-rename — fully revoke)
- [ ] Generate a new key, name-tag it `prod-transcribe-md-<date>`
- [ ] Update `.env` on the VPS: `OPENAI_API_KEY=sk-proj-<new>`
- [ ] `docker compose up -d --force-recreate transcribe-md transcribe-md-worker`
- [ ] Verify: kick off a test visit that hits OpenAI embedding (the edit-tracking hook) and confirm the call succeeds in worker logs

### Audit exposure
- [ ] Pull billing data for the leaked-key window (OpenAI dashboard → Usage → filter by API key if possible). Any spend not attributable to our own dev activity = possible unauthorized use
- [ ] Check for any suspicious IPs in the usage analytics
- [ ] If unauthorized use observed, file with OpenAI support for credit + report the incident

### Prevent next time
- [ ] Add the key pattern (`sk-proj-[A-Za-z0-9]{40,}`) to a pre-commit secret-scanner (git-secrets, detect-secrets, gitleaks) — pick one and install on the repo
- [ ] Document the incident + rotation in `docs/ROTATION_RUNBOOK.md` with the date so future rotations have a reference
- [ ] Verify `.env` is still gitignored (it is — just re-confirm before the next commit)

---

## 7. Legal review

**Status:** all four documents TODO. Requires outside counsel — allocate
2–4 weeks lead time and real budget.

### Terms of Service
- [ ] Draft with counsel familiar with digital health / SaaS
- [ ] Required clauses: acceptable use, IP ownership (doctor owns their SOAP notes; we own the service), limitation of liability, arbitration/venue, termination, survival
- [ ] Publish at `https://<domain>/terms` — a page already exists in marketing; swap in the real content
- [ ] Signup flow's ToS checkbox already references `/terms` (existing code)

### Privacy Policy
- [ ] Draft with counsel — must cover both HIPAA (PHI specifically) AND general data privacy (CCPA at minimum, given likely California doctor customers)
- [ ] Enumerate: what data we collect, what's PHI vs PII, sub-processors (the four from §3), retention periods (180 days audio per T-M16.2; 7 years notes per HIPAA), export + deletion rights
- [ ] Publish at `https://<domain>/privacy`

### BAA template (for clinic customers)
- [ ] Counsel drafts the template we'll offer to any practice that signs up
- [ ] Should be offered as an attachment to the ToS for Practice-tier customers (when that tier exists)
- [ ] Store template as a PDF on the marketing site: `https://<domain>/baa-template.pdf`

### HIPAA attestation
- [ ] Brief public-facing statement at `https://<domain>/hipaa` describing our safeguards: encryption at rest (Postgres + MinIO on encrypted disk), in transit (TLS 1.2+ post §2), access controls (single-session enforcement, bcrypt-12, lockouts), audit logging (audit_logs table), BAA posture (§3), breach notification commitment
- [ ] Link this page from: footer of every marketing page, settings → "your data" section, every outgoing email footer

---

## 8. Pre-launch monitoring

**Status:** infrastructure scaffolded; alert rules not yet configured.

Code ships with Sentry integration + `/api/health` with `cleanup_crons[]`
(from T-M18.2 A13). We have observability primitives; we haven't written
the alerting on top.

### 8a. Sentry alert rules
- [ ] Populate `SENTRY_DSN_MEDDOC_PRO`, `SENTRY_DSN_TRANSCRIBE_MD`, etc. on prod — **but only after Sentry BAA signed** (see §3 Sentry note)
- [ ] In Sentry dashboard, create alert rules:
  - [ ] **Error rate**: >5 uncaught exceptions per 5-minute window across any app → page oncall
  - [ ] **PHI regex detection in events**: Sentry has built-in data scrubber patterns; enable the PII pack on top of our `redactPhi` hook so double-redaction catches any gaps
  - [ ] **New issue**: first occurrence of any error type → email (not page)
  - [ ] **Worker failures**: spike in `tm_*` AI-call SCHEMA_FAIL / JSON_PARSE_FAIL beyond T-M17.1 retry tolerance
- [ ] `SENTRY_RELEASE` should auto-populate per build; confirm by checking an event's Release tag

### 8b. External uptime probe
- [ ] Sign up for UptimeRobot (free tier fine for 50 monitors at 5-min cadence)
- [ ] Three monitors: each hostname's `/api/health` → expect 200
- [ ] On failure: email + SMS to oncall
- [ ] Failure threshold: 2 consecutive checks (10 min) before paging — avoids flapping on a single network blip

### 8c. Cron heartbeat alerts
`/api/health` returns `cleanup_crons[]` with `ageSeconds` per job
(T-M18.2 A13). Three crons tracked: `stale-visit-cleanup` (daily 03:00 UTC),
`retention-sweep` (daily 04:00 UTC), `minio-orphan-cleanup` (disabled until
`MINIO_ORPHAN_CLEANUP_ENABLED=true`).

- [ ] Write a tiny external checker (GitHub Action cron / separate UptimeRobot keyword match) that hits `/api/health` and fails if any `ageSeconds > 26 * 3600` (24h expected cadence + 2h grace)
- [ ] Page on failure — a cron that stops ticking silently is the class of problem that costs a week of audit evidence

### 8d. Postgres backup verification (T-M16.4 sidecar)
- [ ] Confirm `meddoc-pro-postgres-backup-1` sidecar is producing daily dumps (check `/opt/meddoc-pro/backups/`)
- [ ] Test a restore once into a scratch container before launch — an untested backup is not a backup

---

## 9. Pilot plan (1–3 doctors)

**Status:** plan TBD. Candidate doctors not yet identified.

Goal: prove the system handles real clinical visits end-to-end, with
real doctors providing real feedback, before opening signup to the
public.

### Candidate selection
- [ ] Identify 1–3 doctors willing to pilot. Prefer:
  - Specialties we've already validated (T-M17.x live data: Cardiology, Internal Medicine, Orthopedics)
  - Low visit volume — 5-10 visits/week so we can investigate every anomaly
  - Tech-comfortable enough to tolerate rough UX edges

### Onboarding flow
- [ ] Write a one-page onboarding doc ("getting started" — signup, first visit, how to sign a SOAP note, how to report issues)
- [ ] Comp their subscription ($49/mo waived via Stripe coupon 100% off, or practice-tier account created manually)
- [ ] Pre-load their account with their common specialty + set realistic expectations about: audio quality (push-to-talk vs background capture), confidence scores, when the AI gets medication names wrong
- [ ] Schedule a 30-min kickoff call each — screen-share the first visit so we catch any setup foot-guns live

### Feedback collection
- [ ] Dedicated email inbox or shared Slack channel for pilot feedback
- [ ] Weekly 15-min check-in call per doctor for the first month
- [ ] Explicit ask after each visit: "anything the AI got wrong?" — this becomes our real audit data
- [ ] Log every piece of feedback in a single tracker (GitHub issues tagged `pilot-feedback` works) so nothing gets dropped

### Success metrics (exit criteria for "pilot → GA")
- [ ] **Quality:** ≥90% of signed SOAPs required no AI correction beyond doctor's normal edit behavior (measurable via T-M14.1 edit-distance telemetry)
- [ ] **Reliability:** ≥99% visit completion rate (QUEUED → SIGNED without a manual retry intervention)
- [ ] **Latency:** median time-to-draft (audio upload → SOAP visible) ≤90 seconds for visits under 10 min of audio
- [ ] **Support burden:** ≤2 hours/week of founder time on pilot support after the first two weeks
- [ ] **Doctor NPS:** ≥8/10 from each pilot doctor after one month of use

If any metric misses, don't open GA — triage the gap, fix, re-measure.

---

## 10. Blockers & open decisions

Things that must be resolved before the relevant section above can
progress. Keep this short — if it grows, promote items to a proper
issue tracker.

- [ ] **Domain name choice** (§1) — blocker for §2, §5, §7
- [ ] **Stripe product pricing** — is $49/mo the final number? Any yearly discount tier? Practice (multi-doctor) tier pricing?
- [ ] **Hosting provider BAA** (§3) — current VPS provider's HIPAA program may require migrating to a different host. Research before signing BAAs with the AI providers.
- [ ] **Legal counsel retained** (§7) — need a lawyer familiar with digital-health SaaS. 2–4 week lead time.
- [ ] **Pilot doctor candidates** (§9) — names + specialties + visit volume.

---

## Out of scope for this checklist

Explicitly deferred to post-launch:
- GA marketing (paid ads, SEO, content) — pilot first, scale later
- Multi-doctor practices / org billing tier
- Mobile app (web-only launch is fine for pilot)
- EHR integrations (DrChrono is the only legacy surface and is read-only)
- Horizontally-scaled web tier (see `KI-4` in `KNOWN_ISSUES.md`)

If a pilot doctor asks for one of these, log the ask in the feedback
tracker — don't commit until post-pilot retrospective.
