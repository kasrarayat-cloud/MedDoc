# Post-merge cleanup tasks

Items deferred from the Phase 2 Clinician remodel — to be addressed AFTER `feature/clinician-remodel` lands on `main`. None of these block the merge.

Created: 2026-04-29 during Phase 2 D+E gate review.

---

## 1. ✅ Verified: `/dev/rx-warnings` 404 in production is INTENTIONAL

**Status:** documented; no action needed.

`apps/transcribe-md/src/app/dev/rx-warnings/page.tsx:51` explicitly calls `notFound()` when `process.env.NODE_ENV === 'production'`. The route is a designer/QA preview surface for the RxWarningCard variants and is gated to development builds only. The page header itself notes "Dev-only route. 404s in production." (line 75).

QA Layer 3b's 404 on this route during Strategy A (production build) is therefore the **correct behavior**, not a regression. Surfaced here for forward-looking clarity so future contributors don't chase the 404 as a bug.

---

## 2. ✅ Fixed: typo `processing-state.tsx:426` literal `’` in JSX text

**Status:** fixed during merge prep, commit `87340e0`. Replaced the 8-character literal escape with the actual U+2019 character.

**Original notes (kept for archival):**

**Severity:** trivial; not Clinician-scope.

```tsx
// Line 426 — current:
Elapsed {elapsedMin} min · leave the page and we’ll finish in the background
```

JSX text content does NOT interpret backslash escapes like `’`, so users see the literal characters `we’ll` instead of the typographically-correct `we'll`.

**Fix options:**

- **Simplest:** replace `we’ll` with the actual Unicode character `we'll` (U+2019 right single quotation mark).
- **Or:** ASCII apostrophe `we'll`.
- **Or:** template-wrap inside JSX: `we{'’'}ll`.

Any of the above is a one-line change. Pre-existed before Phase 2; preserved verbatim through the Batch D dual-theme migration (commit `34e5dad remodel(clinician): processing-state dual-theme via theme prop`).

---

## 3. A11y pass via Playwright/axe-core

**Severity:** test-coverage gap; needs to run before final merge.

Layer 6 (a11y smoke) of the `qa-clinician-remodel` skill was SKIPPED in every batch (B+C, D, E) because the QA sandbox host has no headed browser binary. The a11y harness must run on a dev box or in CI before the PR ships.

**Suggested setup** (per the skill spec):

```javascript
// browser_evaluate in Playwright MCP
await import('https://cdn.jsdelivr.net/npm/axe-core@4.10.0/+esm')
  .then(m => m.default || m);
const results = await axe.run(document, { resultTypes: ['violations'] });
return results.violations.filter(
  v => v.impact === 'critical' || v.impact === 'serious'
);
```

**Routes to cover** (per QA skill):
- `/login`, `/signup`, `/forgot-password`, `/reset-password`, `/check-email` (Batch A + F)
- `/dashboard` (Batch C)
- `/visits`, `/visits/[id]?status=READY`, `?status=SIGNED`, `?status=PROCESSING` (Batch D)
- `/visits/new`, `/visits/[id]/record` (Batch E)
- `/admin/audit-logs` (Batch G — when complete)

**Pass criterion:** zero critical OR serious violations (color-contrast, missing-alt, missing-label, role-lacks-required-children).

---

## 4. (Reserved) Items surfaced during Batch G

To be appended after Batch G QA completes.

---

## 6. 📝 Pull mockup-fidelity dashboard content (Phase 3)

Current dashboard renders 4 metric cards + 1 patient pill. The Clinician mockup at `docs/design-directions-v3/clinician/dashboard.html` shows a richer surface: morning greeting ("Good morning, Dr. Chen."), 11-row patient list with colored avatars per specialty, "Three drafts, ready when you are." section with named surface CTAs.

Implementation gap is content/data-emit, not visual — palette + typography 100% match the mockup. Phase 3 task: extend dashboard data layer to surface the mockup's content density.

**Surfaced by:** merge-prep round 1 verdict `🟡 PASS-WITH-FLAGS` (report `merge-prep-20260430T001246Z.md`, Flag #2). Deferred per user decision at the merge-prep gate; merge-prep round 2 (`merge-prep-20260430T010915Z.md`) confirmed the deferral and proceeded to 🟢 PASS without it.

---

## 7. ✅ Phase 4 follow-up bugs — completed 2026-05-01

Three post-deploy bugs from user QA fixed and deployed via PR #89:

- **Bug 1 — visit-detail hero band too short.** `min-height` 280→360px on `.qm-cl-app .qm-cin-band-tall` so the cinematic photo crop opens up from ~30 % of vertical content to ~40 %. Recording band (`.qm-cin-band-short`, 200 px) unchanged. Commit `d153dc3`.
- **Bug 2 — `/patients` route never migrated to Phase 2 Clinician.** `apps/transcribe-md/src/app/patients/page.tsx` and `[id]/page.tsx` were rendering the legacy dark navy + violet `app-redesign-v1` theme via `<AppFrame>` / `<PageHeader>` defaults. Both files now pass `theme="clinician"` to opt into the existing Clinician branches of those shared components — no new components created. `<PatientCard>`, server actions, Prisma queries, auth gates byte-identical. Commits `fff6460` + `cf9bea0`.
- **Bug 3 — cream baseline too cool.** `--color-clinician-cream` `#FAF7F2 → #F2EBDC` in BOTH `apps/transcribe-md/src/app/globals.css` and `apps/marketing/src/app/globals.css`. Warmth +6 → +18; WCAG vs `--ink #2B2620`: 14.0:1 → 12.6:1 (still AAA Large + Normal). `--cream-card` and `--cream-2` tokens unchanged per user direction; revisit if section-band visibility looks off post-deploy. Commit `15d13f4`.

**Live verification:**
- `qm-cin-band-tall { min-height: 360px; padding: 32px 32px 28px; }` confirmed in `/_next/static/chunks/*.css` on `app.quillmd.com`.
- `color-clinician-cream: #f2ebdc` confirmed in served CSS on both `app.quillmd.com` and `quillmd.com`.
- `/patients` returns body class `qm-cl-app` (the Phase 2 Clinician scope marker; previously absent).

### Lesson learned for pre-launch

`docs/CLINICIAN_MIGRATION_ORDER.md` was incomplete — `/patients` slipped through Phase 2/3/4 without re-skin because it was never enumerated as an in-scope route. Before the pilot launch, do a full route inventory with this command and address any hits:

```bash
grep -rE 'AppFrame|gradient-violet|text-text-muted' \
  apps/transcribe-md/src/app/ | grep -v '_components' | grep -v 'node_modules'
```

Should return 0 hits across all routes (not counting routes that legitimately render the legacy `<AppFrame theme="default">`). Add this as a CI check in a follow-up PR — a tiny `grep` step in the existing GitHub Actions workflow next to the a11y job is sufficient.

---

## 8. ✅ Phase 5 — Linear V1 Faithful — completed 2026-05-01

Full visual replacement of Phases 2/3/4 with Linear V1 Faithful aesthetic. PR #90, 87 commits, ~$0 cost (pure CSS, no image gen).

### What changed
- Canvas: cream → dark (#08090a)
- Accent: sage retained (#7AA68C, replacing Linear's purple)
- Typography: Source Serif 4 fully removed; Inter + JetBrains Mono everywhere
- Chrome: cinematic photo heroes deleted; Linear-style top bar + thin sidebar + Cmd+K everywhere
- Tokens: `--color-clinician-*` / `qm-cl-*` / `qm-cin-*` / `av1-*` families fully removed; `--color-linear-*` / `qm-lin-*` canonical

### What survived (functional contracts)
- NextAuth, Server Actions, API routes, Prisma queries
- MediaRecorder + WebSocket + AudioContext lifecycle (recording pipeline byte-identical, verified by Subagent 4 diff)
- SUPER_ADMIN gate, RBAC, audit-log writes
- Rx warning class family (`.qm-warn-*`) — re-themed dark, names preserved (180 refs intact)
- Specialty templates, SOAP structure, visit lifecycle states

### Live verification (post-deploy)
- `#08090a` + 19 `--color-linear-*` tokens present in `/_next/static/chunks/*.css` on `quillmd.com`
- 10+ `.qm-lin-*` utilities served (`.qm-lin-app`, `.qm-lin-btn-primary`, `.qm-lin-cmdk`, `.qm-lin-pill`, `.qm-lin-fade-in`, etc.)
- 0 stale `qm-cl-app` / `qm-cin-` / `av1-` / `--color-clinician-` / `Source Serif` references in served CSS
- External smoke: `app.quillmd.com` 307 (auth redirect, expected), `pro.quillmd.com` 200, `quillmd.com` 200, `app.quillmd.com/login` 200, `quillmd.com/pricing` 200
- Deploy outage: ~11 seconds (UP-START 14:48:30Z → both healthy 14:48:41Z)

### Lessons added
- **Stage 2.5 (sequential shared-chrome migration before parallel surface fan-out) eliminated all merge conflicts** in Stage 4 (zero file overlap between any pair of 5 sibling branches). Fold this pattern into future large refactors: when N parallel subagents will all consume shared chrome, migrate the chrome sequentially first so the parallel agents work on isolated surface code only.
- **Pre-flight image-prune saved deploy time** (53 MB freed before build).
- **Worktree symlink quirk:** Turbopack rejects `node_modules` symlinks that cross filesystem boundaries (e.g. `/tmp/wt-…` → `/opt/meddoc-pro/node_modules`). Subagents must use `--webpack` flag in worktree builds, OR keep the worktree path inside the same filesystem as the project (e.g. `/opt/meddoc-pro/wt-…`). Production CI on `main` is unaffected (no symlinks).
- **Backward-compatible deprecated props pattern:** When migrating shared components (AppFrame, TopNav, etc.), keep the old `theme` prop in the type signature as a no-op while collapsing the rendered branches to one. Lets parallel surface subagents proceed without TS errors at every call site; deprecated props can be removed in a follow-up sweep without coordinating across branches.

---

## 9. ✅ Phase 5.1 — visit-detail tab interiors — completed 2026-05-01

Five tab content bodies re-implemented per v9 design exploration picks: SOAP V3 split-pane, Transcript V3 split-pane, Codes V2 power-table, Rx V3 split-pane, Extras V4 card-stream. PR #92, 15 commits, $0 cost (pure CSS, no AI image gen).

### What landed
- **SOAP NOTE** — V3 split-pane: 4 sections left (S/O/A/P with status pills + sage section letter chips + mono uppercase eyebrows), Sources rail right (transcript turn citations)
- **TRANSCRIPT** — V3 split-pane: diarised turns left (speaker chip + mono timestamp + body, low-confidence dotted-underline), audio waveform + speed picker + visit metadata rail right
- **CODES** — V2 power-table: ICD-10 + CPT sortable tables, 4 px sage confidence bars, evidence-quote popover, AI-suggestion accept/reject (rail), "(coming in T-M21)" tooltips on Add/Edit/Remove until mutations land
- **RX** — V3 split-pane: Rx list left with 4-col dose grid, severity-grouped warnings rail right (CRITICAL → SERIOUS → MODERATE → INFO with pulsing critical dot). `.qm-warn-critical/-serious/-moderate/-info` class names byte-identical (Subagent B grep-confirmed); worker emits 3-band severity (`critical|major|minor`), mapped at component boundary to 4-band rail (`major→serious`, `minor→info`)
- **EXTRAS** — V4 card-stream: 7 stacked cards with hairline borders, em-dash placeholders for the 6 unwired categories, AI extras (the existing `referrals + patientSummary`) wired today

### Live verification (post-deploy, 2026-05-01T18:01:33Z)
- 16 Phase 5.1 `qm-lin-*` utilities served across both prod CSS chunks (split, soap-section, source-card, tx-stream, tx-turn, codes-frame, codes-row, rx-split, rx-rail, card-stream, extras-card, extras-head, extras-vitals-tiles, etc.)
- Phase 5 baseline intact (`#08090a`, `--color-linear-sage`, `.qm-lin-app`, `.qm-lin-cmdk` all served)
- Avatar bug class regression: 0 renewed `4024354389` errors in last 2 min
- External smoke: `/login` 200, `/dashboard` 307 (auth), `/patients` 307 (auth)
- Deploy outage: 9 seconds (UP-START 18:01:24Z → HEALTHY 18:01:33Z)

### Follow-up PRs needed (UI in place, data plumbing pending)
- **T-M21:** SOAP citations field on Server Action (powers the Sources rail filter — currently shows all turns until per-section citation IDs are emitted by the SOAP draft worker)
- **T-M22:** `/api/visits/[id]/audio` streaming endpoint (powers the Transcript V3 audio scrubber — currently decorative; only the dictation-flow audio endpoint exists)
- **T-M23:** Extras data plumbing (vitals, allergies, current meds, problem list, demographics, audit log fetches threaded through `extras-tab` props — cards already render, just need wire data)
- **T-M24:** Code/Rx mutation Server Actions (Add / Edit / Remove buttons currently stubbed `disabled` with "(coming in T-M21)" tooltip — sort / expand / copy work today)

### Lessons added
- **Naive conflict-strip on additive globals.css broke a CSS rule mid-block.** When 3 parallel subagents all append utility classes to globals.css, git's 3-way merge conflicts span both branches' tail-additions. Stripping `<<<<<<<`/`=======`/`>>>>>>>` markers naively can leave a `.foo { ... }` opener separated from its closer by the conflict boundary. Fix used: `git show <branch>:globals.css` for each branch's clean version, then surgical concatenation of base + each branch's tail-additions. Brace balance check (`{ count == } count`) caught the issue. Future large additive merges should use this surgical pattern from the start, not after the conflict-strip fails.
- **Worktree path inside project dir works with Turbopack.** Phase 5 hit a cross-fs Turbopack quirk when worktrees lived at `/tmp/wt-*` symlinking back to `/opt/meddoc-pro/node_modules`. Phase 5.1 kept worktrees at `/opt/meddoc-pro/wt-p51-*` (same filesystem) and Turbopack worked unchanged. Faster build path. Worktree-symlinked node_modules across mountpoints still need `--webpack`.

---

## 10. ✅ Phase 5.1.1 — Extras 7-card wiring fix — completed 2026-05-01

Audit-driven fix. PR #92 claimed 5/5 tabs migrated; user spotted Extras still showing legacy empty-state on iPad ("hanoz hamoon sample ghadimiye"). Audit (read-only side-by-side vs v9 mockups + DOM count assertions on test instance with rich Mei-Ling Park seed) confirmed 🔴 NOT migrated. Other 4 tabs verified 🟢. Root cause: `visit-ready-view.tsx` didn't thread the 7 new V4 data props to `<ExtrasTab>` — Subagent C built the cards but the orchestrator wasn't updated. PR #93, 2 files, 210 LOC.

### What landed
- **page.tsx:** patient select extended with `mrn` + `insurance` + `problemList`; visit select extended with `createdAt`. 7 new optional props plumbed through `<VisitBody>`.
- **visit-ready-view.tsx:** `VisitReadyViewProps` extended with optional patient demographics + problem list + visitCreatedAt; `parseProblemList` helper added (normalizes the 2 jsonb shapes the schema documents); `synthesizeAuditEvents` helper added (derives 4-event timeline from `createdAt → processingStartedAt → processingFinishedAt → signedAt` — no new Prisma query, per Subagent C's "audit log is READ-ONLY, derived from visit fields" design). 7 props threaded to `<ExtrasTab>`.
- **No new Prisma queries.** Audit log is derived. Vitals/allergies/current-meds pass empty-data props so cards render their own per-field "Not recorded" empty states.

### Live verification (post-deploy 2026-05-01T22:41:38Z)
- 5 Phase 5.1.1 utilities served in prod CSS (`.qm-lin-card-stream`, `.qm-lin-extras-card`, `.qm-lin-extras-vitals-tiles`, `.qm-lin-extras-audit-ev`, `.qm-lin-extras-kv-grid`)
- External smoke: `app.quillmd.com/login` 200
- 0 errors / 0 "Event handlers cannot be passed" in last 2 min
- Deploy outage: 10 seconds (UP-START 22:41:28Z → HEALTHY 22:41:38Z)
- Test-instance DOM probe pre-deploy: 7/7 V4 cards rendered with correct titles (Demographics / Vitals / Allergies / Current medications / Problem list / Visit metadata / Audit log)

### qa-bug-hunter bumped to v1.1.0
Skill at `~/.claude/skills/qa-bug-hunter/SKILL.md` now adds **per-tab structural DOM count assertions**:

| Tab | Assertion |
|---|---|
| SOAP NOTE | `.qm-lin-split` ≥ 1 + `.qm-lin-soap-section` ≥ 4 |
| TRANSCRIPT | `.qm-lin-split` ≥ 1 + (`.qm-lin-tx-stream` OR `.qm-lin-tx-search`) ≥ 1 |
| CODES | `.qm-lin-codes-frame` + `.qm-lin-codes-table` ≥ 1 each |
| RX | `.qm-lin-rx-split` + (`.qm-lin-rx-row` ≥ 1 OR "No prescriptions" empty-state text) |
| EXTRAS | `.qm-lin-card-stream` + `.qm-lin-extras-card` **≥ 7** |

v1.1 self-test on the fixed build with rich seed data: 5/5 structural assertions pass. The Extras assertion is the smoking-gun fix — v1.0 saw 1 empty-state card and signed off green; v1.1 requires ≥7 (one per V4 category).

### Schema gaps remaining (T-M23 follow-up)
- vitals table — Vitals card renders 8 em-dash tiles
- allergies table for transcribe-md scope — AllergiesCard shows "None known"
- current chronic meds for transcribe-md scope — MedicationsCard shows "Not recorded"

Cards render correctly with empty-state UI for now.

### Lessons added
- **Smoke checks (no errors, HTTP 200) are NECESSARY but NOT SUFFICIENT.** A tab can render the WRONG chrome cleanly with 0 errors. Always assert STRUCTURAL DOM presence for the chosen design variation per tab. v1.0 of qa-bug-hunter missed Phase 5.1 Extras because the empty-state legacy card rendered cleanly; the user spotted it on iPad before any automation did. v1.1's structural-DOM-count assertions catch this regression class at the smoke layer.
- **Subagent claims need orchestrator-side verification.** Subagent C's report said "the 7 cards are wired through new optional props on `ExtrasTab`; the existing call site in `visit-ready-view.tsx` is untouched." That's literally true — they shipped the cards but didn't update the call site. Future subagent briefs should require the orchestrator wiring as part of the same commit, OR the lead's verification step should specifically check that new component props are actually being PASSED, not just declared.
- **Audit-log without a new Prisma query is fine.** The Subagent C design comment "derive from visit fields" is the right call — read-only display surfaces should synthesize timelines from existing data rather than load the full audit_logs table (which has its own RBAC/query-cost concerns).

## 11. ✅ Phase 5.2 — SOAP Coding Coach (V6 hybrid) — completed 2026-05-02

First production feature in QuillMD with real LLM cost in the chart-review path. Live AMA 2021 E&M scoring rail next to the SOAP body — competitive moat vs Athena/Epic/Cerner which only show coding feedback POST-sign.

PR #94, 18 commits, ~3.5K LOC. Merge SHA `7f8e351`. Tag `phase-5.2-soap-coding-coach`.

### Architecture
- Path C (hybrid): deterministic for HPI/ROS/exam/PFSH counts; LLM-judged for MDM tier; both layers cached
- Anthropic prompt cache (5-min ephemeral) on the ~2.6K-token rubric system prompt
- Redis 7-day cache on the JUDGEMENT (cache key: SHA-256 of normalized SOAP body, 20% drift bypass)
- 30s LLM timeout (8s missed ~50% of cold calls)
- Fail-soft: rail renders skeleton if engine throws

### Cost shape
- Cold: ~$0.003/call
- Warm (Anthropic cache): ~$0.0003/call (90% input cost off)
- Cached judgement (Redis): $0
- Weighted average: ~$0.001-0.003/visit
- Vs. ~$30 upcoding delta per accepted Bump CTA → ROI 10000:1+

### Calibration findings worth remembering
- Anthropic prompt cache threshold for Sonnet 4.6 is EMPIRICALLY ~2048 tokens, NOT the 1024 figure in older docs. A 1591-token prompt silently no-op'd cache_creation. Verify via response.usage.cache_creation_input_tokens > 0 on first call.
- LLM-MDM cold-call latency on Sonnet 4.6 with structured JSON output and full rubric: 6-10s typical. Set timeouts >= 30s.

### Deploy timeline
- BUILD-START: 2026-05-02T21:16:52Z
- BUILD-EXIT (0): 2026-05-02T21:18:09Z (1m17s)
- UP-START: 2026-05-02T21:18:16Z
- HEALTHY: ~2026-05-02T21:18:25Z (~9s outage)

### Verification
- 9/9 containers healthy post-deploy
- HTTP 200 on /login, 307 on /dashboard (auth redirect)
- Phase 5.2 sentinels live in prod CSS: `qm-lin-coach-grid`, `qm-lin-coding-bump`, `qm-lin-coding-rail`, `qm-lin-em-criterion`, `qm-lin-soap-section-v6` (5/5)
- Phase 5.1 baseline preserved: `qm-lin-card-stream`, `qm-lin-codes-frame`, `qm-lin-extras-card`, `qm-lin-rx-split` (4/4)
- Phase 5.0 baseline preserved: `qm-lin-app`, `qm-lin-cmdk`, `#08090a`, `--color-linear-sage`
- 0 renewed avatar errors (4024354389), 0 Server-Component handler errors, 0 em-mdm timeouts in last 1 min

### Lessons added
- Always probe cache eligibility empirically with `response.usage.cache_creation_input_tokens`, never trust documented thresholds blindly
- "Silent degradation" is the worst failure mode for AI features: Path C silently became Path A on every cold call until the timeout fix landed. Add `llmJudged: true` assertion to the smoke layer
- Layout density check on iPad before merging any information-dense feature — desktop browsers hide gap problems that show up immediately on tablet
- CI pre-existing failures (meddoc-pro tenancy/admin e2e) are NOT a merge blocker for changes scoped to a different app, but they DO obscure regression detection. Consider scope-tagged CI labels or moving meddoc-pro tenancy tests to a parallel job that doesn't gate transcribe-md merges.

## 12. ✅ Phase 6.1 (h8) — Postgres encrypted volume migration — completed 2026-05-02

HIPAA encryption-at-rest blocker cleared. Migrated postgres data from the plaintext `pgdata` named volume to a LUKS2-encrypted sparse file at `/opt/meddoc-pro/secrets/pgdata.luks`, opened as `/dev/mapper/pg-encrypted`, ext4 inside, mounted at `/mnt/pgdata-encrypted`, bind-mounted into the postgres compose service.

### Cipher
- LUKS2 + AES-256-XTS + SHA-256 + Argon2id PBKDF
- Keyfile: `/etc/quillmd/pg-luks.key` (root:root 0400, 512 bytes /dev/urandom)
- LUKS file: `/opt/meddoc-pro/secrets/pgdata.luks` (1 GB sparse, root:root 0600)
- Mount: `/mnt/pgdata-encrypted` (owner uid 999:999, mode 700)

### Boot auto-mount
- systemd unit: `/etc/systemd/system/pgdata-encrypted.service`
- Runs `Before=docker.service`, opens LUKS + mounts before postgres container starts
- **Reboot test PENDING — must reboot VPS once in next 30 days during low-traffic window to verify the unit actually fires before docker.service**
- Recommended window: Sun 04:00 UTC (lowest doctor traffic globally)

### Compose adjustment beyond the original brief
The original brief swapped one volume line. We also added one env var:

```yaml
environment:
  PGDATA: /var/lib/postgresql/data/pgdata
```

Reason: ext4's `lost+found` directory at the mount root blocks `initdb` (it refuses non-empty data dirs). Pointing `PGDATA` at a subdir of the mount is the standard postgres-image pattern when bind-mounting an ext4 filesystem. No behavioral change beyond that — postgres internal layout is identical to a docker-volume install.

### Downtime
- DOWNTIME-START: 2026-05-02T23:06:13Z
- DOWNTIME-END:   2026-05-02T23:10:08Z
- **Total: 3m 55s** (budget was 15 min; 19 MB DB → restore was sub-second)

### Row counts pre vs post (verified identical)
| Table | Rows |
|---|---|
| ai_calls | 507 |
| api_usage_events | 118 |
| patients (CRM) | 4 |
| transcribe_md_patients | 43 |
| transcribe_visits | 46 |
| users | 30 |
| **TOTAL** | **748** |

### Encryption proof (Stage 3.7)
- 11/11 plaintext markers searched in raw LUKS bytes — **0 hits**
  - Tested needles: `Mei-Ling`, `Park`, `transcribe_visits`, `bronchitis`, `lisinopril`, `qa-iPad`, `qa-ipad`, `SUBJECTIVE`, `OBJECTIVE`, `@quillmd.com`, `@quillmd-test.local`
- LUKS2 header magic valid at offset 0
- Decrypted view (`/dev/mapper/pg-encrypted`) contains postgres internals as expected → decrypt path healthy

### Production smoke
- `app.quillmd.com/login` 200, `/dashboard` 307 (auth redirect)
- `quillmd.com` 200, `pro.quillmd.com` 200
- Phase 5.2 sentinels live: `qm-lin-coach-grid`, `qm-lin-coding-rail`, `qm-lin-em-criterion`
- Phase 5.1 baseline: `qm-lin-card-stream`
- Phase 5.0 baseline: `qm-lin-app`
- 9/9 containers healthy

### Rollback recipe (kept for 30+ days)

The old plaintext `pgdata` named volume is preserved (NOT deleted). To revert:

```bash
cd /opt/meddoc-pro
docker compose stop transcribe-md transcribe-md-worker meddoc-pro postgres-backup postgres
cp docker-compose.yml.pre-h8 docker-compose.yml
docker compose up -d postgres
# Wait healthy, then bring dependents back
docker compose up -d transcribe-md transcribe-md-worker meddoc-pro postgres-backup
```

This swaps the bind-mount line back to the original `pgdata:/var/lib/postgresql/data` and removes the `PGDATA` env var. Old data on the named volume picks up immediately; encrypted volume can be removed later with `cryptsetup close pg-encrypted && rm /opt/meddoc-pro/secrets/pgdata.luks`.

Insurance dump: `/opt/meddoc-pro/backups/migration/meddoc-pre-h8-20260502T230142Z.dump` (2.1 MB, custom format, `pg_restore`-able). Owner `dnsmasq:systemd-journal`, mode 0640 — matches the rest of the postgres-backup tree. Original `/tmp/migration/` copy left on disk; tmpwatch will sweep it eventually.

### Lessons added
- **Sparse-file LUKS works fine on a single-partition VPS.** No repartition, no reboot, clean rollback. Loopback overhead is invisible at our scale (75 MB postgres data dir).
- **ext4 `lost+found` blocks `initdb` when bind-mounting an ext4 filesystem root.** Always bind-mount a subdir or set `PGDATA` env. Discovered live during Stage 3.4; restart-loop visible in logs within 30 s.
- **The `claude` host user has no passwordless sudo.** Privileged ops (cryptsetup, mkfs, mount, systemctl, chown 999:999) require an interactive sudo step from the operator. Pattern that worked: write a self-contained idempotent shell script to `/tmp`, ask the operator to run `! sudo bash /tmp/script.sh` once, surface output back into Claude session, continue. Repeat for the encryption-proof step (read `/dev/mapper/*` requires root). Two interactive sudo handoffs total for a non-trivial migration is acceptable; document the script paths so the operator can audit before running.

### Open follow-ups
- Reboot test (recommended Sun 04:00 UTC; can also schedule via host at-job)
- ~~Move pre-migration dump from `/tmp` to `/opt/meddoc-pro/backups/migration/`~~ → DONE 2026-05-02. File at `/opt/meddoc-pro/backups/migration/meddoc-pre-h8-20260502T230142Z.dump`, owner `dnsmasq:systemd-journal`, mode 0640.
- Phase 6.2 (deferred): S3 keyfile (compromise-resistance bump) — currently keyfile is on the VPS root partition, which is HIPAA-acceptable but not best-in-class

## 13. ✅ Phase 7 — Landing v6 (Apple Product Page) — completed 2026-05-03

The marketing site `quillmd.com` was redesigned from the Phase 5 Linear V1
("Faithful") grammar to the Phase 7 v6 "Apple Product Page" design picked
from the 10-variant designer-mode exploration in
`docs/design-directions-v5-designer/`. Hero-led, full-viewport stages,
sentence-per-section pacing. Same brand identity (sage palette, dark canvas,
Inter + JetBrains Mono); same content (every headline / sub / feature blurb
/ dialogue line / SOAP body / ICD-CPT code / FAQ / footer link byte-identical
to the production source-of-truth content map).

### PR + tag + release SHAs
- PR: [#95](https://github.com/kasrarayat-cloud/MedDoc/pull/95) — squash-merged 2026-05-03
- Squash SHA on main: `e4644dc`
- Hotfix during deploy (May-3 backups dir blocking docker context): `dc4e36f`
  added `backups/` + `docs/` to `.dockerignore`
- Tag: `phase-7-landing-v6-live` (pushed to origin)

### Files changed
- 17 modified components in `apps/marketing/src/components/home/` + `app/`
- New: `apps/marketing/src/app/icon.svg` (sage gradient brand-quill favicon —
  also kills the pre-existing `/favicon.ico` 404)
- New: `apps/marketing/src/components/home/HeroVisual.tsx` (the only new
  client component — mouse-move 3D parallax on the floating SOAP card,
  desktop ≥961px, reduced-motion respected)
- Full rewrite: `apps/marketing/src/app/landing.css` (Phase 5 Linear V1
  grammar replaced with Phase 7 v6 grammar)
- `next/font` Inter weights extended to `{400,500,600,700}` (700 for the
  v6 hero h1; weight 800 dropped — was unused)

### Lighthouse 12 (against local prod build before deploy)
| Category | Mobile (sim 4G + 4× CPU) | Desktop |
|---|---|---|
| Performance | 88 (target ≥95) | **100** |
| Accessibility | **100** | **100** |
| Best Practices | **100** | **100** |
| SEO | **100** | **100** |

Mobile 88 is render-delay-bound on the giant hero h1 (clamp 44-108px,
weight 700, gradient text); already optimized (LCP-friendly anim,
content-visibility on offscreen sections, dropped Inter 800, removed
filter:drop-shadow on giant text on mobile). Real-device mid-range
Android expected 92-97. Desktop nails 100 on every metric.

### Production smoke (post-deploy)
| Path | HTTP |
|---|---|
| `https://quillmd.com/` | 200 |
| `https://quillmd.com/privacy` | 200 |
| `https://quillmd.com/terms` | 200 |
| `https://quillmd.com/pricing` | 200 |
| `https://quillmd.com/icon.svg` | 200 |
| `https://app.quillmd.com/login` | 200 |

V6-distinctive strings present in served HTML:
- "actually use" (hero h1)
- "Solo physician" (pricing card badge)
- "Real visit. Real note." (demo section)
- `/icon.svg` `<link rel="icon">` reference

0 console errors at 1440×900 + 375×812 (Playwright headless against live URL).

### Visual fidelity
- Production = source mockup (`docs/design-directions-v5-designer/v6-apple-product.html`)
  pixel-faithful at both viewports — within sub-pixel font rendering tolerance
- Before/after pairs at `docs/landing-v6-migration/screenshots/` (before-* vs
  prod-* / post-deploy-*)
- Per-section walkthrough at `docs/landing-v6-migration/screenshots/walkthrough/`
  (29 mobile shots covering every section)

### What was preserved byte-identical
- `layout.tsx` metadata (title, description, openGraph, viewport)
- `next.config.ts` (output: standalone, optimizePackageImports)
- `lib/constants.ts` (`APP_URL` + `APP_SIGNUP_URL`)
- All other pages (about, contact, demo, hipaa, pricing, privacy,
  security, signup, terms) — verified HTTP 200 on each
- Reused intact: `useReveal` hook, `useCounter` hook, `RevealMount`
  invisible client component, `globals.css` `@theme` Linear V1 sage tokens
- 0 analytics / tracking pixels existed before; none added
  (no funnel-break risk)

### Animation strategy
- Scroll fade-up `.reveal` → `.in`: existing `useReveal` IntersectionObserver
- Hero `2.0` counter: existing `useCounter` hook
- Hero card 3D float (9s loop): pure CSS `@keyframes float`
- Hero card mouse-move parallax: `HeroVisual.tsx` (only new client logic)
- Live-dot pulse, wave bars, doc-line draw, ring-pulse, orb breath, blink
  cursor: pure CSS keyframes
- `prefers-reduced-motion` honoured throughout

### Deploy lessons added
- **`/opt/meddoc-pro/backups/migration/` is mode 0750 owned by
  `dnsmasq:systemd-journal`.** The May-3 daily backup process writes new
  subdirs there, and the `claude` host user can't read them. This blocks
  `docker compose build` because the build context loader walks the
  whole repo. Permanent fix: `backups/` (and `docs/`) added to
  `.dockerignore`. Future ops: any new sibling dir that the postgres-backup
  container creates with restrictive perms will need the same exclusion.
- **`docker compose build <service>` runs serially even on this VPS.**
  Did NOT need to disable parallel — only one service was passed. The
  "no parallel docker builds" rule (in user memory) applies when running
  `docker compose build` with no service argument (which builds all 3
  app services concurrently).
- **`gh pr merge --squash --delete-branch` switches local checkout to
  `main` automatically and deletes the local feature branch.** No need
  to run `git checkout main` manually after the merge — but harmless.

### Open follow-ups
- `framer-motion` is still in `apps/marketing/package.json` from earlier
  phases but the v6 landing components do not import it. Could be removed
  in a small cleanup PR (would shave ~50KB from `node_modules` install
  time but no runtime impact since tree-shaken out). Low priority.
- Consider preloading the Inter 700 weight via `<link rel="preload">` in
  layout.tsx if a real-mobile Lighthouse run still scores <92 — would
  shave the LCP webfont-swap delay further.

## 14. ✅ Phase 7-QA — email auto-confirm bypass (QA harness only) — completed 2026-05-03

### Why
The QA sweep at `docs/qa-sweep-2026-05-03/` could not complete Stages 3-6
(authenticated app, core flow, Coding Coach, settings) because the
synthetic test email `*@quillmd-test.local` is non-deliverable. The
production Resend API key is correctly scoped send-only (cannot list
dispatched emails), and `auth_tokens` only stores the hash of the
verification token, so QA had no way to retrieve the plaintext token
and complete email verification.

### What
Added a narrowly-scoped, env-gated bypass that auto-confirms email at
signup time for an allowlisted RESERVED test domain only. Production
sets `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local` (RFC 6762 reserved
TLD). All real-mail domains (gmail.com / outlook.com / yahoo.com /
icloud.com / quillmd.com / etc.) are **hard-denylisted** inside the
helper as a defense-in-depth guard against env-var misconfiguration.

### Files
- **NEW**: `apps/transcribe-md/src/lib/email-auto-confirm.ts`
  - `isAutoConfirmDomain(email): boolean` — returns true iff:
    - env `EMAIL_AUTO_CONFIRM_DOMAINS` is non-empty
    - email's domain (right of last `@`, lowercased) is in the env allowlist
    - AND domain is NOT in `REAL_MAIL_DENYLIST` (gmail/outlook/yahoo/icloud/quillmd.com/...)
  - 28-line denylist; positive opt-in; case-insensitive; substring match never used
- **NEW**: `apps/transcribe-md/src/lib/email-auto-confirm.test.ts`
  - vitest, 9 cases:
    1. `quillmd-test.local` allowlisted → fires
    2. `gmail.com` in env (defensive) → does NOT fire
    3. `quillmd.com` in env (production domain) → does NOT fire
    4. env unset → never fires
    5. env empty/whitespace → never fires
    6. domain not in allowlist → does not fire
    7. comma-separated parsing with whitespace
    8. case-insensitive matching
    9. malformed input + non-string defensive guards
- **EDIT**: `apps/transcribe-md/src/actions/auth.ts`
  - signupAction: `verifyEnabled = isEmailDeliveryEnabled() && !autoConfirm`
  - When bypass fires, emits a `console.warn` with `[QA-BYPASS]` prefix +
    the email so it shows up in `docker logs transcribe-md`
- **EDIT**: `docker-compose.yml`
  - Plumbed `EMAIL_AUTO_CONFIRM_DOMAINS: ${EMAIL_AUTO_CONFIRM_DOMAINS:-}`
    into the `transcribe-md` service environment block (next to the
    pipeline-tab gate)
- **EDIT**: `/opt/meddoc-pro/.env` (host)
  - Added `EMAIL_AUTO_CONFIRM_DOMAINS=quillmd-test.local`

### Safety reasoning
1. **Default is safe.** Empty env var → bypass never fires. Existing
   real-user signups behave identically to before this PR.
2. **Denylist trumps allowlist.** Even if env is mis-set to
   `gmail.com,quillmd-test.local`, only the second domain bypasses;
   gmail.com is refused.
3. **Reserved TLD only.** `.local` is RFC 6762 reserved (mDNS); no
   real mailboxes can exist there. Same for `.test`, `.example`,
   `.invalid` if added later.
4. **Visible.** Every bypass fires emits a `[QA-BYPASS]` warning in
   the container log; auditable from `docker compose logs transcribe-md`.
5. **Localised.** The bypass only affects the signup path (one
   `if`-branch in `signupAction`). Login, password-reset, change-email,
   Resend dispatch, audit-log emission are all unchanged.

### Verification
- Unit tests: 9/9 pass via `pnpm --filter transcribe-md test:unit`
- Production smoke (post-deploy):
  - Signup with `qa-bypass-${ts}@quillmd-test.local` → DB shows
    `emailVerified` set to NOW(), no `auth_tokens.EMAIL_VERIFICATION`
    row, container log shows `[QA-BYPASS] auto-confirmed email for ...`
  - Signup with `qa-control@example.com` (control, not on allowlist)
    → DB shows `emailVerified=NULL`, `auth_tokens.EMAIL_VERIFICATION`
    row exists, normal verify-email flow taken (no bypass log line)

### Cleanup
- The Phase 7-QA bypass is intended to STAY ON in production (gated
  on the reserved test domain only). Future QA sweeps can re-use it
  by signing up with any `*@quillmd-test.local` address.
- If we ever want to retire it, just unset `EMAIL_AUTO_CONFIRM_DOMAINS`
  on the host and `docker compose up -d --force-recreate transcribe-md`
  (no rebuild needed; the env var is read at request time, not
  compile time).


