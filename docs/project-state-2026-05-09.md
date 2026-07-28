# QuillMD project state — 2026-05-09

> **Memory-priming snapshot.** Three-day delta since `project-state-2026-05-06.md`. Bullets, no prose.
> Anchor SHA on main: **`eb87a97`** (PR #175 merge, 2026-05-06).
> Working tree on main: **dirty** — `Caddyfile` + `docker-compose.yml` carry the `_design-references → /_preview/*` wiring (uncommitted).

---

## 1 · PRs merged in last 14 days (oldest → newest)

### 2026-05-04 · Round-3 audit closures (PR-D…PR-J)
- `1899bde` PR #115 — **PR-D** AI safety deterministic backstops · Round-3
- `52ae6a4` PR #117 — **PR-C.1** docs · defer audit_logs immutability to Phase 7
- `dc723d3` PR #118 — **PR-E** data integrity · Rx warning unique + SOAP optimistic concurrency
- `43e9118` PR #119 — **PR-F** auth hardening · disable EMAIL_AUTO_CONFIRM in prod, signup anti-enum, NextAuth pin
- `c3b6817` PR #120 — **PR-G** docs · BAA reality + IR runbook + DR runbook
- `cf1fbbc` PR #121 — **PR-H** observability · Sentry source maps + user/visit context, Redis AOF, worker healthcheck
- `5a93da1` PR #122 — **PR-I** a11y · skip-link target, focus indicators, contrast bump (text-3 → #828995, 4.6:1), audio toggle group
- `5a18ce7` PR #123 — **PR-J** input validation · magic-byte audio sniff, prompt-injection delimiters, server-side caps
- `16c5540` PR #124 — docs · POST_MERGE_TODO §24.H/I/J closures + operator steps

### 2026-05-05 · Q0/Q1 quality fix-pack + QA-agent v1.x → v3.x
- `dea0987` PR #125 — Q0-2 L7c pediatric Rx framing (mg/kg + weight gate)
- `95b4dd7` PR #126 — Q0-1 wire `validateRxDose` into L7c · deterministic safety floor live
- `5111615` PR #127 — Q0-3 upgrade L4/L5/L7c → **Opus 4.7**
- `820bc38` PR #128 — Q0-5 propagate Deepgram per-utterance confidence + auto-flag low-quality audio
- `47c8702` PR #129 — docs · POST_MERGE_TODO §26 closures + per-PR sub-agent reports
- `1abe74f` PR #130 — Q2 quick-wins · temperature/schema/keyterm tightening + per-code confidence flag + Rx action coverage
- `b0ebef8` PR #131 — fix(ai) · strip `temperature` for Opus 4.x + treat 400 invalid_request as permanent + capture API error bodies
- `c25f35f` PR #132 — fix(visits) · wire CodingRail confirm-sign + bump-additions persistence (Phase 5.2 stubs)
- `ccb3f00` PR #133 — feat(agents) · **QA Interaction Auditor v1** added
- `30adacb` PR #134 — fix(visits) · wire remaining Phase 5.2 stubs (EM override + SOAP highlight/edit/boost) + seed QA test user
- `280840d` PR #135 — feat(qa-agent) · full-site coverage expansion + seed-script F-07/F-08 fixes (**Phase 5.2 stub-wave cleanup complete**)
- `8ceb25a` PR #136 — feat(qa-agent v3.1) · storageState session reuse + rich fixture seeds + `deepWalk` helper
- `9dc4972` PR #137 — feat(qa-agent v3.2) · deep walkers for 5 high-traffic doctor pages
- `751da08` PR #138 — fix(audit) · close 3 §164.312(b) gaps surfaced by QA agent v3.2
- `a2e221b` PR #139 — fix(dashboard) · close F-12 NAB; tests pinning existing error boundary
- `41edf2a` PR #140 — fix(qa-v3.2-cleanup) · close F-13/F-14/F-15/F-16 (orphan dispatcher + dead code + audit race + walker locator)
- `58403cb` PR #141 — feat(security) · **PR-K** supply-chain hardening · Dependabot + base-image SHA pins + npm audit baseline (high+critical CI gate)

### 2026-05-06 · PR-L/M/N security wave + processing-screen UX + agents-v3.3
- `ae2cd8e` PR #162 — feat(pipeline) · **PR-L** clinical-resilience · Whisper fallback + BullMQ DLQ + admin queue dashboard
- `c845cf0` PR #163 — feat(pipeline) · wire `transcribe()` orchestrator into Layer-1 + provider audit (PR-L follow-up)
- `861ae09` PR #164 — feat(security) · **PR-M** finalize MinIO SSE-S3 bootstrap (Path B; KES deferred per NAB)
- `bc60261` PR #165 — feat(security) · **PR-N** `edge-security-apply.sh` operator wrapper
- `b209650` PR #166 — docs(sentry) · close PR-O as NAB + refresh project state + capture polish backlog
- `6d1de17` PR #167 — feat(qa-agent) · visit-record walker · `getUserMedia` mock + draft-mode fixture (v3.3)
- `a977149` PR #168 — feat(qa-agent v3.3) · broader walker depth · 23 stubs promoted to ✅ deep (3-tier taxonomy)
- `109c9a4` PR #169 — feat(agents) · **AI Pipeline Auditor** design doc · DORMANT until pilot data
- `aa85826` PR #170 — feat(agents) · **HIPAA Compliance Auditor** design doc · staged activation
- `f7d3f71` PR #171 — docs(audit) · Q1 fix-pack triage · re-baseline 19-finding backlog vs post-Round-3 + post-v3.x state
- `4fe7f03` PR #172 — feat(transcribe-md) · **typewriter-SOAP processing screen** · replaces minimal-dot post-upload
- `eb9703f` PR #173 — feat(transcribe-md) · typewriter SOAP types real content (PATH B-lite preview)
- `f4a8d24` PR #174 — fix(transcribe-md) · typewriter content truncation + done-state freeze
- `eb87a97` PR #175 — fix(transcribe-md) · typewriter typography + scope · max-width, markdown render, drop transcript phase

---

## 2 · PRs currently open

### Substantive · 1
- **#176** `fix/rx-warnings-rail-override-button` — wire critical Rx override modal into visit-page `RxWarningsRail`. State: **OPEN · MERGEABLE · mergeStateStatus=UNSTABLE**.
  - **Blocker:** axe-core sweep (chromium × desktop+mobile) **FAILURE** in CI.
  - Other checks green: `test`, `TruffleHog`, `npm audit`.
  - Closes a production defect: doctor sees critical Rx warning on `/visits/<id>` Rx tab → hits Sign & Deliver → 422 `OVERRIDE_REQUIRED` toast → no action button. Modal + server action + audit table + sign-API guard already shipped; this PR adds the missing JSX bridge.
  - Files: `rx-warnings-rail.tsx`, `rx-tab.tsx`, `page.tsx`, `visit-ready-view.tsx`, `sweep-visit-page.mjs`.
  - Action: axe failure is **NOT** on the override button — root cause is `aria-progressbar-name` on `processing-typewriter.tsx` (introduced in PRs #172-#175, the typewriter-SOAP processing screen). PR #176 doesn't touch that surface; the failure is inherited site-wide. Fixed in PR #180; #176 clears once rebased.

### Dependabot bumps · 18 open (all 2026-05-06, no review)
- **#177** monorepo-root-minor-patch group across 1 directory · 23 updates
- **#161** `@deepgram/sdk` 4.11.3 → 5.1.0
- **#160** `tailwind-merge` 2.6.1 → 3.5.0
- **#159** `resend` 4.8.0 → 6.12.2
- **#158** `eslint` 9.39.4 → 10.3.0 (root dev)
- **#156** `typescript` 5.9.3 → 6.0.3 in transcribe-md
- **#155** `@types/node` 20.x → 25.x in transcribe-md
- **#154** `@types/bcryptjs` 2.x → 3.x in transcribe-md
- **#153** `resend` 4.8.0 → 6.12.2 in transcribe-md
- **#152** `eslint` 9.x → 10.3.0 in marketing
- **#151** `framer-motion` 11.18.2 → 12.38.0 in marketing
- **#150** `@types/node` 20.x → 25.x in marketing
- **#149** `transcribe-md-minor-patch` group · 5 updates
- **#148** `tailwind-merge` 2.x → 3.5.0 in marketing
- **#147** `marketing-minor-patch` group · 3 updates
- **#146** `@deepgram/sdk` 4.x → 5.1.0 in packages/ai
- **#145** `@anthropic-ai/sdk` 0.85.0 → 0.95.0 in packages/ai (`ai-minor-patch`)
- **#144** `actions/cache` v4 → v5
- **#143** `actions/github-script` v7 → v9
- **#142** `actions/setup-node` v4 → v6
- **Pattern:** all created same-day after PR-K Dependabot wiring landed; none reviewed yet.
- **Closed/superseded:** #157 (CLOSED — replaced by #177).

---

## 3 · Recent investigations / bugs (status)

| ID | Topic | Status |
|---|---|---|
| **Site-wide axe failure** | `aria-progressbar-name` on `processing-typewriter.tsx` (introduced in PRs #172-#175) | **Fix in PR #180** — single `aria-label` add. PR #176 + PR #178 inherited this failure; both clear once #180 lands and they rebase. |
| **Phase 6.1 reboot-test** | systemd `pgdata-encrypted.service` reboot validation | **Pending** · within 30 days of 2026-05-04 — needs Kasra |
| **PR-B Edge security execution** | UFW + fail2ban + sshd hardening | **Not yet executed on live VPS.** `ufw inactive`, `fail2ban not-installed`, `sshd_config` still `PermitRootLogin yes`. PR-N (`edge-security-apply.sh`) shipped wrapper but did not run it. Needs operator-sudo. |
| **Sentry BAA** | DSN env vars empty pending BAA execution | **Pending** — flip env to activate (no code change) |
| **Backblaze B2 BAA** | Phase 6.2 offsite encrypted backup | **Pending** — request via Backblaze support → "HIPAA BAA" ticket |
| **DrChrono integration** | Legacy MedDoc Pro EHR sync | **Verify** — was scoped to MedDoc Pro (decommissioned per POST_MERGE_TODO §21); confirm no code path remains |
| **Q1 fix-pack 19-finding backlog** | Re-baselined 2026-05-06 (PR #171) | Triaged against post-Round-3 + post-v3.x state — see `docs/quality-fix-packs/Q1-rebaseline-20260506.md` (referenced in PR #171) |
| **Round-3 closure tracker** | POST_MERGE_TODO §24 PR-A…PR-L | All shipped or formally NAB-closed; sequence complete as of PR #166 |
| **§164.312(b) audit-row gaps** | Surfaced by QA agent v3.2 deep walks | **Closed** by PR #138 (3 gaps fixed) |
| **Phase 5.2 stub-wave** | "Pretend success" fallbacks across CodingRail / SOAP / EM override | **Complete** as of PR #135 — full QA-agent-driven cleanup |

---

## 4 · Design references on disk

`/opt/meddoc-pro/_design-references/` (mounted into Caddy at `/_preview/*` on `app.quillmd.com`):

| File | Size | Mtime | What |
|---|---|---|---|
| `quillmd-design-tokens.md` | 27 KB | 2026-05-09 | **NEW today.** Production design-system reference — exact tokens (colors, type, spacing, components) extracted from `apps/transcribe-md/src/app/globals.css`. Consumed by SOAP redesign mockups + future CD prompts. |
| `quillmd-soap-mockups.html` | 158 KB | 2026-05-09 | **REPLACED today.** 5 SOAP-redesign concepts (Index+Body / Problem-Forward / Hero+Detail / Smart Highlights / Active vs Reference) using production tokens. Live at `https://app.quillmd.com/_preview/quillmd-soap-mockups.html`. Replaces an earlier 15-concept attempt that used wrong fonts (Lora) and wrong sage (#9eb5a0). |
| `quillmd-processing-mockups.html` | 81 KB | 2026-05-06 | Processing-screen exploration that informed PR #172's typewriter-SOAP design. |
| `quillmd-marketing-snapshot-20260505T162009Z.zip` | 12.6 MB | 2026-05-05 | Marketing-site snapshot bundle. |

**Caveat (CSP):** `app.quillmd.com` ships `style-src 'self' 'unsafe-inline'` + `font-src 'self' data:`. Google Fonts `<link>` in mockup HTML is blocked by CSP; mockups fall back to the production `-apple-system, BlinkMacSystemFont, 'Segoe UI', system-ui, sans-serif` chain — visually near-identical to production but not pixel-perfect Inter on viewers without Inter installed locally. For exact parity, self-host fonts under `_design-references/fonts/` and switch the link to local `@font-face`.

---

## 5 · Custom agents · `.claude/agents/`

| Agent | Status | Trigger | Notes |
|---|---|---|---|
| `qa-interaction-auditor` | **ACTIVE · v3.3** | "Run the QA agent" / "Run a QA sweep" | 23 stubs promoted to ✅ deep walks (PR #168). Walker for visit-record (PR #167) handles `getUserMedia` mock + draft-mode fixture. Recent reports under `docs/qa-reports/`. |
| `ai-pipeline-auditor` | **DORMANT (designed)** | "Run the AI pipeline audit" (post-activation) | Gate: ≥20 real visits across ≥3 distinct doctors with `status=READY` in `transcribe_visits`. Below threshold findings would be stylistic. |
| `hipaa-compliance-auditor` | **DORMANT (staged)** | "Run the HIPAA compliance audit" (post-activation) | Phases 0/1/4/5/6/7/8/9 can run today; phases 2+3 (audit controls + integrity) gated on same pilot threshold. Initial activation enables today-runnable phases; mid-pilot enables 2+3. |

Each agent dir contains: `README.md`, `SKILL.md` (registration), `skills/` (methodology + domain knowledge), `fixtures/`, `scripts/`, optional `tests/`.

`.claude/agents/README.md` is the operator-facing index — keep that as source of truth.

---

## 6 · Operator queue (Kasra-pending)

Ordered by criticality. Items below are NOT actionable by Lead — operator-sudo or external-vendor account access required.

1. **Processing-screen aria fix** (PR #180) · `aria-label` on the typewriter-SOAP progressbar · clears the site-wide axe-core gate that's inherited by PR #176 + PR #178. Lead-pushed.
2. **PR-B edge security execution** · Run `scripts/edge-security-apply.sh` with sudo · enables UFW, installs fail2ban, hardens sshd (`PermitRootLogin no`, key-only auth). Live VPS currently exposed.
3. **Phase 6.1 systemd reboot-test** · Reboot VPS once and verify `pgdata-encrypted.service` re-mounts encrypted Postgres volume cleanly · within 30 days of 2026-05-04.
4. **Phase 6.2 Backblaze B2 BAA** · Submit via Backblaze support → "HIPAA BAA" ticket. Required before activating offsite backup destination. Per `COMPLIANCE_REGISTER.md` row 1.
5. **Phase 6.2 activation** · Per `POST_MERGE_TODO.md §22` and `docs/phase-6.2-backup-strategy.md`. **Memory says 2 runbook gaps remain** (see `docs/round-3-deep-audit-2026-05-04/findings/agent-12/P1-002-phase-6.2-runbook-gaps-minio.md`).
6. **Sentry BAA** · Self-serve at sentry.io → Settings → Legal & Compliance · then flip `SENTRY_DSN` env on transcribe-md + worker + marketing.
7. **DrChrono row review** · `COMPLIANCE_REGISTER.md` row 25 · verify whether any DrChrono code path remains in active build now that MedDoc Pro is decommissioned.
8. **Dependabot triage** · 18 open dep-bump PRs (~all of 2026-05-06). Likely 1-2 require code adjustments (`@deepgram/sdk` major, `tailwind-merge` major, `resend` major, `framer-motion` major, `typescript` major, `eslint` major). Batch-review session recommended.

---

## 7 · Active work-in-progress (branches)

### On the wire
- **`fix/rx-warnings-rail-override-button`** · pushed as PR #176 · axe-core CI red. Most-recent commit 2026-05-06.

### Local (no PR or stale)
Local branches sorted by `committerdate` — top 14:
- `2026-05-06 fix/rx-warnings-rail-override-button` → PR #176
- `2026-05-06 main` → at `eb87a97`
- `2026-05-04 chore/e2e-smoke-test-2026-05-04` — unclear merge state, likely stale
- `2026-05-04 chore/audit-round2-cleanup-2026-05-03` — likely merged via Round-3 wave
- `2026-05-04 chore/audit-cleanup-2026-05-03` — likely merged via Round-3 wave
- `2026-05-04 feat/phase-6-2-backblaze-b2-encrypted-backup` — pre-Phase-6.2 work, status unclear
- `2026-05-04 chore/skip-meddoc-pro-e2e-decommissioned` — landed pattern; can prune
- `2026-05-04 fix/meddoc-pro-e2e-baseline` — likely landed; can prune
- `2026-05-04 fix/coding-coach-a11y-structural` — likely subsumed by Round-3 PR-I (#122)
- `2026-05-04 fix/p2-001-email-max-length` — Round-3 finding; verify merged
- `2026-05-04 fix/p2-003-mobile-tap-targets` — landed; can prune
- `2026-05-03 fix/p2-002-specialty-catalog` — verify
- `2026-05-03 fix/p1-001-export-metadata-phi-leak` — verify
- `2026-05-03 chore/ci-a11y-include-dev-deps` — landed; can prune

**Older Phase 4 / Phase 5 / Phase 5.2 feature branches** still present locally (`feature/phase4-*`, `feature/phase5-*`, `feature/phase5.1-*`, `feature/phase5.2-*`) — all merged into main long ago, never deleted. **Branch hygiene pass** is overdue.

### Working tree (uncommitted on `main`)
```
M  Caddyfile          (+10 lines: handle /_preview/* { … } block)
M  docker-compose.yml (+5 lines:  -./_design-references:/srv/_design-references:ro mount)
```
Both are the **`/_preview/*` design-review wiring**. Comments in both files mark them as "Temporary — remove with the matching block when the review window closes." Per memory, the URL `https://app.quillmd.com/_preview/quillmd-soap-mockups.html` and `…/quillmd-processing-mockups.html` depend on this; do NOT revert until the review windows close.

### Untracked (notable)
- `_design-references/` — covered above
- `docs/design-directions-v3-landing/`, `v4-landing/`, `v5-designer/` — landing-page exploration dirs
- `docs/landing-immersive-enhance/`, `docs/landing-v6-migration/` — marketing iterations + post-deploy screenshots (desktop + mobile)
- `docs/preflight-reports/preflight-20260503*` × 6, `preflight-20260505T173407Z.md` — operator pre-flight runs
- `docs/qa-reports/20260505*`, `docs/qa-reports/20260506*` × 9 — QA-agent v3.x sweep outputs (incl. F09/F10/F11 closure)
- `docs/qa-sweep-2026-05-03/`, `docs/qa-sweep-authenticated-2026-05-03/` — early-week sweeps

---

## 8 · Useful pointers (fast lookups)

- **Production token reference:** `_design-references/quillmd-design-tokens.md` (NEW today).
- **Phase-6.2 runbook + gaps:** `docs/phase-6.2-backup-strategy.md` + `docs/round-3-deep-audit-2026-05-04/findings/agent-12/P1-002-phase-6.2-runbook-gaps-minio.md`.
- **POST_MERGE_TODO master tracker:** `docs/POST_MERGE_TODO.md` (139 KB; §22 = Phase 6.2, §24 = Round-3 sequence, §26 = Q0/Q1 closures).
- **Compliance register:** `docs/COMPLIANCE_REGISTER.md` (vendor-by-vendor BAA status).
- **Prior project state:** `docs/project-state-2026-05-06.md` — 2026-05-06 baseline; this doc is the 3-day delta on top.
- **Operator-facing pre-flight:** `docs/preflight-reports/` (latest `20260505T173407Z.md`).
- **QA-agent reports:** `docs/qa-reports/` (most recent `20260506T062422Z.md`).
- **Custom agents index:** `.claude/agents/README.md`.

---

## 9 · Memory-priming TL;DR

- Main HEAD `eb87a97` (2026-05-06).
- **One** substantive open PR (#176 — Rx override bridge, CI red on axe).
- **Eighteen** dependabot bumps queued; no triage yet.
- Working tree dirty by **design** — `/_preview/*` wiring is intentional + documented inline.
- Custom-agent fleet: 1 active (qa-interaction-auditor v3.3), 2 dormant (ai-pipeline-auditor, hipaa-compliance-auditor).
- Operator queue is bounded: **edge-security execution + Phase 6.1 reboot-test + Phase 6.2 BAA/activation + Sentry BAA**. Everything else has shipped or has a tracker row.
- Round-3 audit officially closed; Q1 fix-pack re-baselined 2026-05-06 (PR #171).
- **No active fires** — the typewriter-SOAP processing screen + Phase 5.2 stub wave landed clean.
- New today: production design-token doc + 5-concept SOAP redesign mockups (Linear V1 Faithful — Inter / JetBrains Mono / `#08090a` / `#7AA68C`).
