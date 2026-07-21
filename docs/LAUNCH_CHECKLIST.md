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

Last reviewed: **2026-04-22** (post T-M19 HTTPS cutover + T-M19.3 email + T-M20 product polish)

---

## Launch gate — all must be ✅ before first doctor login

This is the TL;DR. Every item below is expanded in its own section.

- [x] **1. Domain purchased + A records set** (§1) — `quillmd.com` + 3 subdomains live (T-M19)
- [x] **2. HTTPS live via Caddy MODE B** (§2) — Let's Encrypt certs for all 4 hostnames (T-M19.1)
- [ ] **3. All four BAAs signed + on file** — Anthropic, OpenAI, Deepgram, hosting provider (§3)
- [ ] **4. Stripe subscription flow working end-to-end** ($49/mo tier) (§4)
- [x] **5. Resend sender domain verified** (SPF/DKIM/DMARC green) (§5) — `quillmd.com` green, delivery gate on, forgot-password verified end-to-end 2026-04-22 (T-M19.3)
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

### T-M20 product polish (2026-04-22)

Non-gate-but-launch-blocking issues caught during the browser-test pass on the new HTTPS deployment:

- [x] **T-M20.1** — PDF label overlap when SOAP fields were `[not documented]` (PR #40). Root cause in `renderInlineWithBold`'s split on bold-markdown producing empty slots that pdfkit failed to finalize. One-line fix + a committed regression script (`apps/transcribe-md/scripts/gen-test-pdf.ts`) that reproduces the scenario end-to-end.
- [x] **T-M20.2** — Rebrand TranscribeMD → QuillMD across all 26 user-facing string surfaces: email templates (subjects + bodies), PDF header/watermark/metadata, DOCX export, EHR-paste footer, app nav + auth pages, marketing site (PR #41). Internal identifiers (Docker services, package names, DB schemas, enum values, code comments) explicitly left alone to keep the change surface to 80 inserts / 80 deletes.
- [x] **T-M20.3** — Pipeline tab (raw entities JSON, wall-time, cost, critique) gated behind `NEXT_PUBLIC_SHOW_PIPELINE_TAB`, defaulting hidden in production (PR #42). Gate lives in the server page so a dev can flip via runtime env override + force-recreate — no rebuild required.

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

**Status:** ✅ shipped 2026-04-22 (T-M19.3). `quillmd.com` fully
verified at Resend, delivery gate flipped on, forgot-password +
email-verification both confirmed delivering to a real mailbox
with a valid DKIM signature.

### Sender setup (post-domain)

- [x] Added `quillmd.com` as a sender domain in the Resend dashboard
- [x] All four DNS records landed at Namecheap: SPF TXT, DKIM TXT, DMARC TXT, MX
- [x] Resend verified all four records (green)
- [x] Production sender chosen: `noreply@quillmd.com` (branded as `QuillMD <noreply@quillmd.com>`)

### Env flip

- [x] `RESEND_API_KEY=re_...` live key, loaded from `/opt/meddoc-pro/.env`
- [x] `RESEND_FROM=QuillMD <noreply@quillmd.com>`
- [x] `RESEND_FROM_VERIFIED=true` — gate now `isEmailDeliveryEnabled() === true`
- [x] `docker compose up -d --force-recreate transcribe-md`
- [x] Source `DEFAULT_FROM` in `apps/transcribe-md/src/lib/email.ts` bumped to `QuillMD <noreply@quillmd.com>` (PR #38) so a deploy that forgets the env override still ships from a verified sender

### Smoke test

- [x] Password-reset email delivered end-to-end to a real mailbox
- [x] Inbox (not spam); DKIM signature validates against `quillmd.com`; sender displayed as `QuillMD` not `resend.dev`
- [x] Resend dashboard recorded the `delivered` event

---

## 6. Credential rotation sweep — Round 3 PR-A (2026-05-04)

**Status:** ✅ Vendor-side rotation complete; ⏳ .env paste pending PR-A merge.

The Round 3 audit (PR #111) findings A01-P0-001..003 + A02-P0-002 + A07-P3-001 documented that eight secrets had been baked into shipped Docker images and/or sat in world-readable `.env.backup`/`.env.local` on the VPS. The structural fix landed in Round 3 PR-A (`fix(round-3-pr-a): secrets sweep …`):

- `.dockerignore` rewritten so `COPY . .` no longer pulls `.env*` into image layers (root cause of A01-P0-001).
- `.env.backup`, `.env.local` (root), and `apps/meddoc-pro/.env.local` deleted from the VPS.
- `.env` mode tightened to `0600` (was 0640).
- All five affected images rebuilt `--no-cache` against the new ignore list and verified via `docker save … | tar tv | grep .env` (clean).
- CI `secrets-scan.yml` workflow added (trufflehog `--only-verified` on every PR) to prevent regression.

### Rotation status (vendor-side — done by Kasra 2026-05-04)

All eight secrets were considered compromised and rotated through the vendor consoles. Old values are dead at the vendor; new values live in Kasra's password manager pending the `.env` paste.

- [x] `OPENAI_API_KEY` (was `sk-proj-K8_…` per audit A01-P0-002) — revoked + new key issued
- [x] `ANTHROPIC_API_KEY` — revoked + new key issued
- [x] `DEEPGRAM_API_KEY` — revoked + new key issued
- [x] `RESEND_API_KEY` — revoked + new key issued
- [x] `AUTH_SECRET` — regenerated via `openssl rand -base64 33`
- [x] `DB_PASSWORD` — Postgres `meddoc` role password rotated
- [x] `MINIO_ROOT_PASSWORD` — MinIO root credential rotated
- [x] `SCRIBE_SERVICE_TOKEN` — regenerated

### Operator step (Kasra, post-PR-A merge)

- [ ] Paste the eight new values into `/opt/meddoc-pro/.env`
- [ ] `docker compose up -d --force-recreate postgres minio redis transcribe-md transcribe-md-worker meddoc-pro marketing` (postgres + minio first to pick up the new root credentials, then app tier)
- [ ] Smoke-verify: `curl -sI https://app.quillmd.com` returns 307; `curl -sI https://pro.quillmd.com` returns 200; kick off a test visit and confirm the AI pipeline reaches Claude / Deepgram / OpenAI from worker logs
- [ ] Confirm `.env` mode is still `0600` after the paste (`stat -c '%a %n' /opt/meddoc-pro/.env`)

### Audit exposure (post-rotation)

- [ ] Pull billing data for the leaked-key window from OpenAI / Anthropic / Deepgram / Resend dashboards. Any spend not attributable to our own dev activity = possible unauthorized use; file with vendor support for credit
- [ ] Check usage analytics for suspicious IPs / regions
- [ ] If unauthorized use observed, document in `docs/incidents/2026-05-04-credential-leak.md` (incident-response runbook is itself a Round 3 finding A12-P0-002 — to be authored under PR-G)

### Prevent next time (closed by this PR)

- [x] CI guard: `.github/workflows/secrets-scan.yml` runs trufflehog `--only-verified` on every PR; fails on any verified-live secret in the diff or working tree
- [x] `.dockerignore` rewritten so `COPY . .` cannot bake `.env*` into images (closes A01-P0-001 root cause)
- [x] On-disk leftovers (`.env.backup`, `.env.local`) deleted; mode tightened to 0600
- [ ] Document this rotation event in `docs/ROTATION_RUNBOOK.md` (deferred to follow-up PR — `ROTATION_RUNBOOK.md` already exists per audit A12 positives but should record the 2026-05-04 sweep date)

---

## 6.5. Edge security hardening — Round 3 PR-B (2026-05-04)

**Status:** 🚧 PR-B open — runbook + recommended configs in repo; live execution is the operator step below.

Closes Round 3 audit findings A07-P0-001 (sshd `PermitRootLogin yes`), A07-P0-002 (UFW disabled, no nftables, fail2ban absent), A07-P0-003 (root `ai-deal-hunter` uvicorn cohabits PHI VPS).

The runbook lives at [`docs/runbooks/edge-security.md`](runbooks/edge-security.md). Execute it from a root shell with the Zap Hosting web console open as a fallback path. Wall time ~25-35 min.

### Pre-flight (operator)

- [ ] Zap Hosting web console open in browser tab (lockout fallback)
- [ ] Second SSH session as `root@<vps>` open in a separate terminal
- [ ] All 9 containers healthy
- [ ] No active visit being processed (`bull:transcribe-md:active` LLEN = 0)

### §1. Prerequisites — non-root sudo user with key auth

- [ ] `/home/ubuntu/.ssh/authorized_keys` contains operator's public key (mode 0600, owner `ubuntu:ubuntu`)
- [ ] `groups ubuntu` includes `sudo`
- [ ] **Verified `ssh ubuntu@<vps>` succeeds from operator's laptop in a NEW terminal**
- [ ] **Verified `sudo -n true` succeeds as `ubuntu`**

### §3. SSH hardening (after §2 pre-stage)

- [ ] `/etc/ssh/sshd_config` replaced with `infra/ssh/sshd_config.recommended`
- [ ] `sshd -t` exits 0
- [ ] `systemctl reload sshd` succeeds; sshd `active (running)`
- [ ] `ssh root@<vps>` rejected from laptop
- [ ] `ssh ubuntu@<vps>` succeeds; `ssh claude@<vps>` succeeds

### §4. UFW + Docker compatibility

- [ ] `infra/ufw/after.rules.fragment` appended to `/etc/ufw/after.rules` before final COMMIT
- [ ] `ufw default deny incoming` + `ufw default allow outgoing` set
- [ ] `ufw allow 22/tcp`, `ufw allow 80/tcp`, `ufw allow 443/tcp` configured
- [ ] `ufw --force enable` succeeds
- [ ] `ufw status verbose` shows the 3 allow rules + `Status: active`
- [ ] `curl https://app.quillmd.com` returns 307 (smoke external)
- [ ] `curl https://pro.quillmd.com` returns 200
- [ ] `curl https://quillmd.com` returns 200
- [ ] All 9 containers still `(healthy)` in `docker compose ps`
- [ ] Container-to-internet works (`docker exec transcribe-md wget -qO- https://api.anthropic.com/v1/messages`)
- [ ] `systemctl enable ufw` (persists across reboot)

### §5. fail2ban

- [ ] `apt-get install -y fail2ban` succeeds
- [ ] `infra/fail2ban/jail.local` installed at `/etc/fail2ban/jail.local`
- [ ] `systemctl enable --now fail2ban` succeeds
- [ ] `fail2ban-client status` lists `sshd`
- [ ] `fail2ban-client status sshd` shows `Currently failed: 0`, jail active

### §6. Evict `ai-deal-hunter`

- [ ] Identified launch mechanism (systemd unit / shell / cron)
- [ ] Process stopped (and disabled if systemd)
- [ ] `/root/ai-deal-hunter/` moved to `/root/archive-2026-05-04/ai-deal-hunter/`
- [ ] `ss -tlnp | grep :8000` empty
- [ ] `ps -ef | grep ai-deal` empty (no orphan)
- [ ] `curl -m 3 http://<vps>:8000` connection refused / timeout (UFW + process gone = defense in depth)

### §7. Final verification (must all pass)

- [ ] `ssh root@<vps>` rejected
- [ ] `ssh ubuntu@<vps>` succeeds
- [ ] `ssh claude@<vps>` succeeds
- [ ] All 9 containers healthy
- [ ] `/api/health` from inside transcribe-md returns 200
- [ ] `app.quillmd.com` 307; `pro.quillmd.com` 200; `quillmd.com` 200; `<vps>:8000` refused

### Sign-off

- [ ] All boxes above ticked
- [ ] PR-B merged + tagged `round-3-pr-b-complete`
- [ ] `POST_MERGE_TODO.md §24` PR-B row updated to ✅ MERGED with PR link

---

## 6.6. HIPAA technical safeguards — Round 3 PR-C (2026-05-05)

**Status:** 🚧 PR-C open — code + migrations + scripts in repo; operator steps below.

Closes Round 3 audit findings A05-P0-001..004 (encryption-at-rest gaps; PHI-read audit gap), A09-P0-002 (audit_logs application-mutable), A05-P1-004 (backup public-key fingerprint not validated). Implements HIPAA §164.312(b) (audit controls) and §164.312(c) (integrity).

### Migrations (apply via deploy pipeline)

- [ ] Read-only `docker compose run --rm db-migrate --phase status` proves the
      exact ledger/target, then its freshly verified
      `targetFingerprints.lineage-expand` entry authorizes one approved
      `lineage-expand` cumulative-segment invocation from an eligible exact
      prefix, under `docs/DEPLOYMENT_RUNBOOK.md` §1.4.1. Never reuse or derive
      the phase-, ledger-, accepted-source-, and target-bound entry. The segment
      applies
      `20260505010200_round_3_pr_c_phi_read_audit_actions` (enum +3 values) and
      `20260505010210_round_3_pr_c_revoke_audit_mutation` (REVOKE on
      audit_logs). Do not use the removed raw deploy alias.
- [ ] `bash tests/integrity/audit-logs-immutable.test.sh` returns PASS (was SKIP before deploy).

### MinIO SSE-S3 bootstrap

- [ ] `set -a && . /opt/meddoc-pro/.env && set +a` in operator shell
- [ ] `bash /opt/meddoc-pro/scripts/minio-enable-sse.sh` succeeds (`OK - SSE-S3 active on local/transcribe-md-audio`)
- [ ] `mc encrypt info local/transcribe-md-audio` shows SSE-S3 enabled

### Expected-fingerprint file deploy (one-time)

- [ ] Canonical `/etc/meddoc/offsite-backup-public.age` is in place (deployed during Phase 6.2 §22 step 3 — confirm)
- [ ] `sudo sh -c 'sha256sum /etc/meddoc/offsite-backup-public.age | awk "{print \$1}" > /etc/meddoc/expected-public-key-fingerprint.sha256'`
- [ ] `sudo chmod 644 /etc/meddoc/expected-public-key-fingerprint.sha256`
- [ ] Next `backup-offsite-sync.sh` run logs `INFO: public key fingerprint verified (...)` instead of the transition-mode WARN

### PHI-read audit emit verification

- [ ] Load `/visits` from operator's browser → check admin audit-log dashboard for a fresh `VIEWED_VISIT_LIST` row
- [ ] Open a visit detail → check for `VIEWED_VISIT` row
- [ ] Load `/patients` → check for `VIEWED_PATIENT_LIST` row
- [ ] Open a patient detail → check for `VIEWED_PATIENT_FILE` row
- [ ] Click "Play" on a transcript audio → check for `VIEWED_VISIT_AUDIO` row

### Sign-off

- [ ] All boxes above ticked
- [ ] PR-C merged + tagged `round-3-pr-c-complete`
- [ ] `POST_MERGE_TODO.md §24` PR-C row updated to ✅ MERGED with PR link

---

## 6.7. AI safety deterministic backstops — Round 3 PR-D (2026-05-05)

**Status:** 🚧 PR-D open — code + migrations + 29-drug dose table in repo; clinical data review + 07c integration are operator steps.

Closes Round 3 audit findings A06-P0-001 (empty-transcript guard, FULLY), A06-P0-002 (ICD/CPT allowlist, FULLY), A06-P0-004 (clinical-pharmacology backstop, PARTIALLY — RxNav/drug-drug interactions deferred to Phase 7).

### Migration (apply via deploy pipeline)

- [ ] Read-only `docker compose run --rm db-migrate --phase status` proves the
      exact ledger/target, then its freshly verified
      `targetFingerprints.lineage-expand` entry authorizes one approved
      `lineage-expand` cumulative-segment invocation from an eligible exact
      prefix. Never reuse or derive the phase-, ledger-, accepted-source-, and
      target-bound entry. The segment applies
      `20260505012317_round_3_pr_d_ai_safety` (8 enum values + weightKg +
      allergies columns) under `docs/DEPLOYMENT_RUNBOOK.md` §1.4.1. Do not use
      the removed raw deploy alias.

### Worker redeploy

- [ ] `docker compose up -d --force-recreate transcribe-md-worker` so new guards + allowlist filters go live

### Empty-transcript guard verification

- [ ] Upload a 1-second silent clip → visit lands FAILED with reviewReason "Recording is 1.0s; need at least 3s of audio…"
- [ ] Audit log shows row with `action='PIPELINE_REJECTED_TOO_SHORT'`
- [ ] Upload a 30-second silent clip → visit lands FAILED with reviewReason mentioning word count
- [ ] Audit log shows `PIPELINE_REJECTED_INSUFFICIENT_TRANSCRIPT`

### ICD-10 / CPT allowlist verification

- [ ] Run a normal visit through to completion → ICD-10 codes in `visit.icdCodes.codes[]` are all valid (in `ICD10_ALLOWLIST`)
- [ ] If Claude ever emits a fabricated code, audit log shows `CODING_COACH_REJECTED_INVALID_ICD` / `_CPT` and the rejected code is dropped from the persisted result

### Pre-pilot clinical data review (REQUIRED before pilot go-live)

- [ ] Pharmacist reviews every row in `packages/ai/src/data/dose-ranges.ts` against current local protocols
- [ ] Sign-off captured in `docs/CLINICAL_DATA_REVIEW.md` (create file)
- [ ] ICD-10 starter set reviewed against pilot specialties' billing experience; gaps documented

### Phase 7 follow-ups (post-pilot)

- [ ] RxNav / RxNorm live API integration
- [ ] Drug-drug interaction database
- [ ] 07c-rx-drafting integration of `validateRxDose()`
- [ ] Patient-edit UI for weightKg + allergies
- [ ] Expand ICD-10 starter set to full CMS canonical list
- [ ] Expand CPT allowlist via AMA license OR CMS PFS RVU file

### Sign-off

- [ ] All required boxes above ticked
- [ ] PR-D merged + tagged `round-3-pr-d-complete`
- [ ] `POST_MERGE_TODO.md §24` PR-D row updated to ✅ MERGED with PR link

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
