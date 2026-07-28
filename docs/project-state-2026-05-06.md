# QuillMD project state — 2026-05-06

> **Working document for Kasra to review.** Drafted after PR-O's
> NAB closure surfaced that the persistent project-state memory
> (anchored at T-M17.2, 2026-04-20) was ~2.5 weeks stale and had
> caused at least three redundant-PR briefs in one session
> (PR-M / PR-N / PR-O). After review, fold the relevant pieces
> back into Lead's persistent memory so future sessions start
> from current ground truth.

## Production reality

- **Live domains:** `app.quillmd.com` (transcribe-md app),
  `quillmd.com` (marketing), `pro.quillmd.com` (legacy MedDoc Pro
  CRM — **OUT OF SCOPE** per memory #9).
- **Container fleet:** 9 healthy services per the T-M16.4 baseline:
  `transcribe-md`, `transcribe-md-worker`, `marketing`,
  `meddoc-pro` (legacy, kept warm), `caddy`, `postgres`,
  `postgres-backup`, `redis`, `minio`. Plus two utility containers:
  `db-migrate` (compose profile `migrations`, on-demand) and
  `openclaw-openclaw-gateway-1` (separate stack, not QuillMD).
- **Current main HEAD:** `bc60261` (PR-N merge).
- **Postgres:** PG 16 via `pgvector/pgvector:pg16`. Encryption at
  rest via Phase 6.1 LUKS2 (`/mnt/pgdata-encrypted`,
  AES-256-XTS + Argon2id, virtio-balloon blacklisted).
- **MinIO:** SSE-S3 default encryption active on `transcribe-md-audio`
  bucket (PR-M, 2026-05-06). Master key
  `quillmd-master-key-1` lives in `/opt/meddoc-pro/.env` only.
- **Sentry:** SDK + scrubber wired across web app + worker + edge
  runtimes (T-M16.3 + Round 3 PR-H). DSN env vars stay empty
  pending Sentry BAA execution; flipping the env activates without
  a code change.
- **Edge security:** `scripts/edge-security-apply.sh` (PR-N)
  ready to run; UFW + fail2ban + sshd hardening + ai-deal-hunter
  eviction not yet executed on the live VPS (operator-sudo
  handoff needed).

## Major milestones since the prior memory snapshot (2026-04-20)

### Phase 5.x — Coding Coach + stub-completion wave

- **Phase 5.2 SOAP Coding Coach** (PR #94, tag
  `phase-5.2-soap-coding-coach`, merge `85349e2`). Hybrid scoring
  engine in `apps/transcribe-md/src/lib/em-coding/`. Deterministic
  for HPI/ROS/exam/PFSH; LLM-judged MDM tier via Claude Sonnet 4.6
  (direct SDK, NOT the shared ModelClient — explained in inline
  comments). Two cache layers: 5-min Anthropic prompt cache + 7-day
  Redis cache. Per-visit cost 0.001-0.003 USD vs ~30 USD upcoding
  delta per accepted Bump → ROI 10000:1+.
  - **Calibration finding worth keeping:** Anthropic prompt-cache
    eligibility threshold for `claude-sonnet-4-6` is empirically
    ~2048 tokens, not the 1024 figure in older docs. Always verify
    `response.usage.cache_creation_input_tokens > 0` on first call
    when adding `cache_control` to a new feature.
  - **LLM-MDM TIMEOUT_MS = 30s** (was 8s; structured-output
    Sonnet 4.6 cold-call latency on 2.6K-token system prompts is
    realistically 6-10s).
- **Phase 5.2 stub-completion wave** (PRs #131, #132, #134,
  #138-141): wired CodingRail confirm-sign, bump-additions
  persistence, EM override, SOAP highlight/edit/boost, three
  §164.312(b) audit-row gaps. Closed Round 3 PR-B finding
  A07-P0-001 (sshd hardening — runbook authored, not yet applied),
  PR-C (MinIO SSE — bucket-level set in PR-M, finalized 2026-05-06),
  PR-D (deterministic backstops), PR-J (input validation hardening).

### Phase 6.x — Encryption + backup + supply chain

- **Phase 6.1 H8 — Postgres encryption at rest** (tag
  `phase-6.1-h8-encrypted-postgres`, merge `29af277`). LUKS2
  bind-mount migration; downtime 3m55s; row counts identical
  pre/post; encryption proof clean. Reboot-test of the systemd
  unit (`pgdata-encrypted.service`) **still pending** within
  30 days.
- **Phase 6.2 — Backup baseline** (already shipped per pre-existing
  memory; no recent activity).
- **PR-K Supply chain hardening** (PR #141, tag
  `pr-k-supply-chain-hardening`). Dependabot + base-image SHA
  pins + npm audit baseline (`docs/security-audits/npm-audit-baseline-20260506T064154Z.md`).
  CI gate: `npm audit --audit-level=high` blocks high+critical.

### Round 3 deep-audit closures

The Round 3 audit (PR #111) surfaced 138 findings (21 P0 / 47 P1 /
44 P2 / 26 P3). Closure sequence ran PR-A through PR-L with the
post-merge tracker at `docs/POST_MERGE_TODO.md §24`. Highlights
relevant to current state:

- **PR-B Edge security** (PR #113) — runbook + recommended configs
  in `infra/{ssh,ufw,fail2ban}/`. **Runbook NOT YET EXECUTED on
  the live VPS** — `claude` user is in `docker` group only, not
  `sudo`, so applying needs operator-sudo handoff. PR-N (2026-05-06)
  shipped `scripts/edge-security-apply.sh` to make execution safer
  but did NOT execute it. Live VPS: `ufw inactive`,
  `fail2ban not-installed`, sshd_config still `PermitRootLogin yes`.
- **PR-C MinIO SSE-S3** — PR-C shipped `scripts/minio-enable-sse.sh`
  but the env wiring was incomplete (KMS key never set in
  compose). Closed by PR-M (2026-05-06).
- **PR-H Observability** (PR #121) — added user/visit context
  tags to `captureWorkerException` + sourcemap upload + the
  operator-facing `docs/runbooks/sentry-setup.md`. Combined with
  T-M16.3, this delivered the Sentry foundation completely;
  PR-O (2026-05-06) was a NAB-closure on a redundant follow-up.
- **PR-K Supply chain** — see Phase 6.x above.
- **PR-L Pipeline resilience** (PR #162, tag
  `pr-l-pipeline-resilience`). Whisper fallback foundation +
  BullMQ DLQ (`dlq:permanent-failures`) + bull-board admin route at
  `/admin/queues`. **Direction-inversion finding:** the PR-L brief
  asked for "Whisper → Deepgram" fallback; reality is Deepgram-only
  since T-M4, so the actual upgrade is Deepgram-PRIMARY →
  Whisper-FALLBACK (memory #16 surfaced + shipped the inverse).
- **PR-L follow-up** (PR #163, tag
  `pr-l-followup-wire-transcribe-orchestrator`). Wired the
  orchestrator into Layer-1 + Layer-1b; added
  `transcriptionProvider` column to `transcribe_visits`;
  `TRANSCRIPTION_PROVIDER_FALLBACK` audit row emitted on Whisper
  fallback. Visits taking Whisper auto-flag for review (no
  diarization).

### QA Interaction Auditor — agent build-out

- **v1** (PR #133, tag `agent-qa-interaction-auditor-v1`) — initial
  silent-stub-features walker.
- **v2** (PR #135, tag `agent-qa-interaction-auditor-v2`) — full-site
  coverage expansion + seed-script F-07/F-08 fixes.
- **v3.1** (PR #136) — storageState session reuse + rich fixture
  seeds + deepWalk helper.
- **v3.2** (PR #137) — deep walkers for 5 high-traffic doctor pages
  (`280840d` baseline). Memory #20 captured: every new
  `page.tsx` route must ship with site-map row + walker stub +
  sweep-all registry entry.
- **F-09 / F-10 / F-11 / F-12 / F-13 / F-14 / F-15 / F-16 closures**
  (PRs #138-140) — audit-row gaps, dashboard error-boundary NAB,
  4 P3 cleanup items.

### Recent operator-pending state

- **Sentry BAA** — 🟡 Pending per
  `docs/COMPLIANCE_REGISTER.md`. DSN env stays empty until BAA
  signed (operator action: `docs/runbooks/sentry-setup.md` §5).
- **Edge security apply** — `scripts/edge-security-apply.sh`
  (PR-N #165) ready to run. Operator action: arm kill-switch,
  walk through phases pre → ssh → ufw → fail2ban →
  evict-deal-hunter → verify, cancel kill-switch.
- **MinIO SSE legacy-objects sweep** — `transcribe-md-audio`
  pre-PR-M objects are not auto-encrypted at SSE-S3 layer (still
  protected by volume disk encryption only). Migration via
  `mc cp --recursive` documented at
  `docs/security-audits/minio-sse-bootstrap.md` for next
  maintenance window.
- **Phase 6.1 reboot test** — verify `pgdata-encrypted.service`
  systemd unit fires end-to-end on reboot; pending within 30
  days from 2026-05-02.
- **CI flake** — `apps/meddoc-pro` tenancy/admin e2e tests
  (auth-admin-can-sign-in, chart-id auto-assign, three
  tenant-isolation tests) failing since 2026-05-01 with 30s
  timeouts. Out of scope per memory #9 but masks regression
  detection.

## Recent merges (last 10)

| SHA | PR | Title (one-line) |
|---|---|---|
| `bc60261` | #165 | feat(security): edge-security-apply.sh — idempotent operator wrapper for PR-B (PR-N) |
| `861ae09` | #164 | feat(security): finalize MinIO SSE-S3 bootstrap (Path B; KES deferred per NAB) |
| `c845cf0` | #163 | feat(pipeline): wire transcribe() orchestrator into Layer-1 + provider audit (PR-L follow-up) |
| `ae2cd8e` | #162 | feat(pipeline): clinical-resilience — Whisper fallback + BullMQ DLQ + admin queue dashboard (PR-L) |
| `58403cb` | #141 | feat(security): supply chain hardening — Dependabot + base-image SHA pins + npm audit baseline (PR-K) |
| `41edf2a` | #140 | fix(qa-v3.2-cleanup): close F-13..F-16 P3 findings |
| `a2e221b` | #139 | fix(dashboard): close F-12 as NAB; add tests pinning the existing error boundary |
| `751da08` | #138 | fix(audit): close 3 §164.312(b) gaps surfaced by QA agent v3.2 deep walks |
| `9dc4972` | #137 | feat(qa-agent v3.2): deep walkers for 5 high-traffic doctor pages |
| `8ceb25a` | #136 | feat(qa-agent v3.1): storageState session reuse + rich fixture seeds + deepWalk helper |

## Standing rules from active memories (terse pointer; don't duplicate)

- **memory #9 — apps/meddoc-pro out of scope.** Don't read, edit,
  test, or merge into that app.
- **memory #11 + #15 — autonomy + parallelism.** Lead may proceed
  without confirmation on routine decisions; spawn parallel
  subagents when independent work fans out.
- **memory #13 — secrets are operator-managed.** Master keys, DSN
  values, auth tokens never appear in commits, PR bodies, or chat
  output — only the NAME for reference.
- **memory #16 — NAB pushback authority.** Surface false-positive
  findings + redundant briefs; don't ship duplicate work.
  PR-M / PR-N / PR-O all closed via this in one session
  (2026-05-06).
- **memory #17 — preflight health check.** Before major tasks
  (subagent spawn, full builds, full test suites) run
  `userSettings:preflight-health-check`.
- **memory #18 — no time estimates.**
- **memory #20 — every new `page.tsx` ships with site-map row +
  walker stub + sweep-all registry entry.**

## Known operational gotchas (active)

- **virtio-balloon blacklisted** at
  `/etc/modprobe.d/blacklist-virtio-balloon.conf`. If
  `lsmod | grep balloon` ever returns a hit, the blacklist was
  overridden — reapply before continuing.
- **Prisma migration workflow** — `migrate dev` BLOCKED by the
  `t_m24_smart_inject` checksum drift. Use `migrate diff` +
  hand-write folder + `db-migrate` profile (`migrate deploy`).
  Verified working pattern as of PR-L follow-up (2026-05-06).
- **`@meddoc/db` Prisma typing** — shared prisma export is typed
  `any`; `findMany` / `.map` callbacks need explicit row-type
  annotations.
- **MOCK_AI_CALLS** — `false` in prod. Playwright regression runs
  require flipping to `true` + force-recreate transcribe-md +
  transcribe-md-worker, then flipping back.
- **`RESEND_FROM_VERIFIED=false`** in prod — email-verification
  gate is OFF; signup auto-logs in. Domain verification at
  resend.com pending operator action.
