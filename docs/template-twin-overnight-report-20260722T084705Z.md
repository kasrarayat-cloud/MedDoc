# Template Twin native-DOCX — Overnight Run report (20260722T084705Z)

Branch: feat/template-ingestion-unified (9 commits, not pushed at start). Main: 1f221ef.
Append-as-you-go. Hard rules: frozen surfaces byte-identical; flag default OFF; only Stage 1 touches prod.

## Pre-flight
RAM: total 31Gi avail 25Gi
disk: 62% used 110G avail
load: 0.57, 0.42, 0.51
prod non-healthy: 0
balloon absent
=== anthropic credit ===
anthropic HTTP 200 OK

## STAGE 1 — IOV drift fix
Drift verified (md5 WT==PROD!=main) for FOUR files, not three: 07a-icd-coding.ts, build-ultrasound-prompt.ts, build-soap-prompt.ts, AND packages/ai/src/data/icd10-allowlist.ts.
The ICD-polarity fix spans 07a + the allowlist (07a references allowlist entries); landing only 3 would leave the drift trap partially open. Following the evidence + the stated goal (prod==main), the fix set = these 4 source files + the fix's test (iov-report-fixes.test.ts, also present in the prod worker image). Documented deviation from the '3 files' wording.
- Fix branch fix/iov-prod-drift @ ae03af3 off main; 4 IOV source files + test, all COMMITTED==PROD (byte-identical md5).
- Local: 370 tests green (IOV/prompt/ICD/worker-layers). PR: https://github.com/kasrarayat-cloud/MedDoc/pull/374
- CI required checks (6): Playwright E2E, test, npm audit, axe-core, TruffleHog, unit tests. Monitoring...
- CI result: 5/6 GREEN (Playwright E2E 9m12s ✓, test ✓, unit tests ✓, axe-core ✓, TruffleHog ✓). 1 FAIL: npm audit (high+critical gate).
- Audit failure is PRE-EXISTING + unrelated: HIGH advisories in transitive deps brace-expansion (GHSA-jxxr-4gwj-5jf2 / GHSA-3jxr-9vmj-r5cp), fast-uri (GHSA-4c8g / GHSA-v2hh), js-yaml (GHSA-h67p / GHSA-52cp), hono — newly disclosed; the same advisories show on main via local `npm audit`. The drift fix changes ZERO dependency manifests (git diff confirms no package.json/lock change).
- DECISION: STOP Stage 1 per the explicit rule. NOT merged, NO prod deploy. Fixing the gate needs `npm audit fix` (dependency bumps) which is out of scope for a byte-identical drift fix and unsafe to ride along overnight. **Prod is SAFE — it already runs the IOV fix (current images).** PR #374 left OPEN for Kasra.
- Human step for Stage 1: address the npm-audit advisories (a separate dep-bump PR) OR override the gate, then merge #374 and rebuild prod from main (rollback-tag pre-driftfix first). Until then prod keeps running the fix and must NOT be rebuilt from main (would regress).

## STAGE 2 — worker fill-trigger (DONE)
- runTemplateTwinFillStep (worker/template-twin-fill-step.ts): flag-gated + certified-twin-gated + FAIL-SAFE (never blocks visit/sign; logs + surfaces; export falls back to styled). Wired into worker.ts as one gated call before the READY update.
- Flag OFF = no-op (no DB/side effect); worker behavior identical — 379 worker + l4-golden tests green. Unit tests 5/5 (off/on/not-certified/fill/fail-safe/inputMode).
- Choice rationale: on-demand-at-export is wrong (processTemplateTwinVisit claim needs status!=SIGNED, export follows sign); the worker step fills before sign, export reads the cache. Commit ec48a03.

## STAGE 3 — picks->IR bridge (DONE)
- bridgeChoiceSlotPicks (picks-bridge.ts): LIVE {{one of}} picks -> exact-option single-select resolutions. Document-order marker->field mapping with forward-cursor consumption (Right/Left duplicates), option-constrained captures (never off-list, multi-marker chains safe), blank-stays-blank.
- Deterministic tests on real WM_IOV: recovers all 28 picks + blank + off-list + both-legs (4/4). Narrative/table/measurement out of scope (resolver owns). Commit 6e7dbfd.

## STAGE 5 — real-AI bridge e2e (semantic heart PROVEN; full-UI-worker e2e scoped)
- In-process, isolated QA DB (:55433, NEVER prod — confirmed zero prod writes; DATABASE_URL forced to QA). Anthropic sonnet-4-6, real call.
- Flow: compile WM_IOV -> REAL-AI CHOICE_SLOT fill of the scaffold from a dense reflux dictation -> bridgeChoiceSlotPicks -> 28/28 dropdowns filled from the LIVE picks -> renderTemplateDocx -> ROUNDTRIP verified (verified/static/field all verified) -> filled WM_IOV docx.
- PRIMARY EVIDENCE FILE: scratchpad/wm-iov-BRIDGE-filled.docx (49420 B, valid Word 2007+); static parts (styles/numbering/content-types) BYTE-IDENTICAL (formatting preserved); dictated picks visible (Bilateral Detailed, small/great saphenous vein, reflux positive, diagnosis=varicose veins, clinical indications, saphenofemoral junction, deep+superficial).
- HONEST caveat: the bridge fills the 28 DROPDOWN picks (the CHOICE_SLOT semantic heart). WM_IOV reflux TIMES (6.2/3.4) are narrative_text fields, not {{one of}} dropdowns -> narrative/table numeric fill is the documented remaining path (out of the selects-only bridge scope).
- The FULL Playwright-UI + built-worker e2e (upload UI -> certify -> visit -> worker fill-trigger -> sign -> native export route) was NOT run — it needs Stage 4 (certify UX) + a built QA app/worker stack; the in-process path proves the same fill+render mechanics with real AI. Also NOT wired: the bridge into processTemplateTwinVisit's persisted manifest (needs per-pick synthesized facts so validateTemplateTwin passes) — render proves the output; manifest persistence is the last-mile integration.

## STAGE 4 — certify-once UX (NOT built — documented gap)
- The certification workspace routes/components were NOT built this run (the in-process real-AI e2e did not require them, and Stages 5/6 evidence took priority). Design is settled: upload -> create-draft (compile+propose) -> workspace-read projection -> mapping edit (PATCH mappings) -> synthetic-test (injected extractTemplateTwinEntities) -> certify (hash-locked, one-time) -> per-note automatic. All lib pieces exist + are decoupled to getSession-compatible actors (no requireDoctorSession). Remaining = the app/ routes + client components + a11y pass.

## STAGE 6 — CLOSE
- code-quality-auditor (final, 12-commit diff): **0 BLOCK / 1 WARN / 4 NIT**. All 5 categories CLEAN (frozen byte-identical; worker fill-trigger additive+flag-gated+fail-safe; picks-bridge pure+invariants; L3 visit path behavior-identical; clean layering; additive migration).
  - WARN-1 (native export should degrade to styled on a THROW, not only null) — FIXED (commit 8ffa1d2).
  - NIT-4 (no timeout on the inline fill; a hang would delay READY) — FIXED (45s race-timeout, commit 8ffa1d2).
  - NIT-1 (extractTemplateTwinEntities exported-but-unwired) / NIT-2 (flag-ON pins provenance on the visit, safe/guarded) / NIT-3 (bridge sentinel factId; downstream provenance readers special-case choice_slot_pick) — informational, tied to the certify-UX + bridge-into-manifest gaps.
- feat/template-ingestion-unified pushed; **PR #375 OPEN, DO NOT MERGE**: https://github.com/kasrarayat-cloud/MedDoc/pull/375 (12 commits).
- QA torn down with volumes; no leaked processes; prod 9/9 healthy; disk 62%; memory updated.

## MORNING SUMMARY — go/no-go inputs for Kasra
### Prod state
- Prod UNTOUCHED, still running the IOV fix (its current images). prod != main (drift), by design tonight. DO NOT rebuild prod from main until PR #374 merges (would regress the 3 WM_IOV fixes).
- No rollback tag created (no deploy happened). Feature flag NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX unchanged (default OFF) in prod.
### PRs (both blocked ONLY by the pre-existing npm-audit gate — brace-expansion/fast-uri/js-yaml/hono, present on main, not introduced by either PR)
- #374 fix/iov-prod-drift — the drift fix, byte-identical to prod. 5/6 CI green.
- #375 feat/template-ingestion-unified — the feature (flag OFF). 12 commits, 0-BLOCK audit.
### Primary evidence
- scratchpad/wm-iov-BRIDGE-filled.docx — real-AI: dictation -> CHOICE_SLOT fill -> bridge 28/28 dropdowns -> native render roundtrip-verified -> the doctor's own WM_IOV docx, filled, static byte-identical.
### Remaining human steps
1. Address the npm-audit advisories (separate dep-bump PR or gate override), then merge #374, then rebuild+recreate prod app+worker from main (rollback-tag pre-driftfix first) + smoke + clean. This removes the drift trap.
2. Review #375. Build Stage 4 certify UX + wire the bridge into the persisted manifest (synthesize per-pick facts) + narrative/table numeric fill, before enabling the flag anywhere.
### Untouched remaining-gap list: single-parse collapse; narrative-only docx; PDF form-fill; mapping-proposal strict-schema hardening.

_Nothing pushed to prod. Nothing merged. Flag OFF. Frozen surfaces byte-identical (04b/sign/E-M/Rx/audit/auth). Kasra decides merge + promotion._

## NPM-AUDIT BATCH + DRIFT LAND — STOPPED at the gate (new sharp advisory)
chore/npm-audit-batch-20260722 @ 07f7083, PR #376 (open).
| advisory | from | -> patched | severity | mechanism |
|---|---|---|---|---|
| brace-expansion | vulnerable | 1.1.16 / 2.1.2 / 5.0.7 | HIGH | npm update (lockfile) |
| fast-uri | 3.0.0-3.1.3 | 3.1.4 | HIGH | npm update |
| js-yaml | 4.0.0-4.2.0 | 4.3.0 | HIGH | npm update |
| hono | 4.0.0-4.12.26 | 4.12.31 | moderate | npm update |
Clean + minimal: package.json untouched; app-runtime UNMOVED (next 16.2.6 / react 19.2.5 / prisma 7.8.0 / @sentry 10.49.0, grep-proof); only package-lock.json changed; overrides still just ws/vite; no allowlist/suppression.

**GATE STILL RED — blocked by a NEWLY-DISCLOSED sharp advisory (not on the task list):** sharp <0.35.0 HIGH (libvips CVEs, GHSA-f88m-g3jw-g9cj). Cannot be cleanly fixed: sharp is next@16.2.6's OPTIONAL dep pinned ^0.34.5; npm 11 won't apply a ^0.35.0 override to the pinned lock entry (verified: npm update / override / override+hard-dep all leave 0.34.5; manual lock-removal DROPS sharp -> breaks next/image); npm's only auto-fix downgrades next (forbidden). Full re-resolve is out of the minimal-closure scope + risky pre-deploy. Per the task rule (never force / never suppress / STOP if not cleanly green), STOPPED.

### Consequence (honest)
- Stage 1 (audit gate): 3 HIGH + hono cleared (PR #376), but gate NOT green (sharp). #376 not mergeable as-is.
- Stage 2 (land #374): BLOCKED — gate red. NOT merged.
- Stage 3 (deploy prod==main): NOT DONE — no merge, no rebuild, no smoke. **Prod UNCHANGED, still runs the IOV fix via its current images (safe). prod != main by design.** No rollback tag (nothing deployed). Flag OFF/unset in prod (unchanged).
- Stage 4 (rebase #375): BLOCKED — no new main to rebase onto; #375 CI would also fail on sharp. Left OPEN unmerged.

### Exact human steps
1. Resolve sharp: pick (a) upgrade sharp to 0.35.x under next 16 + verify next/image (build + image smoke) [likely needs a full lockfile re-resolve or a next patch]; (b) await a next release that widens its sharp range; (c) a time-boxed reviewed gate exception given low reachability (next/image on trusted domains only). Add it to PR #376.
2. Once #376 is green -> squash-merge -> then #374 (rebase, 6 green) -> squash-merge -> rebuild+recreate prod app+worker from main (rollback-tag pre-driftfix-<date> first) -> smoke (ultrasound REFLUX bare-numbers/(seconds), no impression contradiction, I83.8x; SOAP E/M 99214 + gates) -> clean to baseline. Then prod==main; re-verify md5(3 worker files on main)==prod-image.
3. Rebase #375 onto the new main; confirm its 6 checks; leave open for review.
_Nothing merged, nothing deployed, flag OFF. Frozen surfaces untouched. Prod safe._

## SHARP LADDER RESOLVED — rung 1b (controlled re-resolve) LANDED
- 1a (next patch): FAILED — no next release widens sharp; latest 16.2.11 still pins sharp ^0.34.5; no stable 16.3.x.
- 1b (controlled re-resolve): LANDED. root override sharp ^0.35.0; sharp/@img 0.35.3 subtree spliced onto the baseline lockfile so ONLY sharp moves.
  PROOF: (a) runtime pins byte-identical — next 16.2.6 / react 19.2.5 / react-dom 19.2.5 / @prisma 7.7.0 / prisma 7.8.0 / @sentry 10.49.0 / tailwind 4.2.2 (grep-verified; ONLY sharp 0.34.5->0.35.3). (b) sharp loads + libvips render OK, @img linux-x64 binaries present. (c) npm ci reproduces the lockfile clean. (d) prod-mode next build (transcribe-md) BUILD_EXIT=0. (e) npm audit --audit-level=high exit 0 under exact CI scoping. Only package.json (1 override line) + package-lock.json changed.
- Folded into PR #376 (commit e47a87f). CI (6 checks) running...

## CHAIN COMPLETION (escalation-ladder run) — STAGE 1 + STAGE 2 DONE
### Stage 1 — audit gate green (#376)
- Rung **1b** landed (controlled sharp re-resolve, commit e47a87f). #376 CI: **6/6 GREEN** (npm audit gate pass ~44s). Squash-merged. main = d1dcd1b. Gate green on main.

### Stage 2 — drift fix landed (re-vehicled #374 -> #377)
- #374 was found **CLOSED** (manual close 2026-07-22T15:46:29Z by kasrarayat-cloud; single close event, no merge/force-push event). GitHub **refused reopen** ("Could not open the pull request") because the rebase force-push diverged the head from the closed snapshot (`refs/pull/374/head` frozen at ae03af3; branch at a088818).
- Reissued as **PR #377** from the same branch fix/iov-prod-drift -> main, **byte-identical** drift fix (exactly the 5 IOV files, +209/-13, rebased onto main-with-#376). #374 commented as superseded.
- #377 CI: **6/6 GREEN on its own merits** — Playwright E2E ✓, test ✓, unit tests ✓, axe-core ✓, TruffleHog ✓, **npm audit (high+critical gate) ✓** (the exact check that was RED on the stale pre-rebase SHA). Squash-merged, branch deleted. **new main = 9efca9b6**.
- **Post-merge md5 proof (main == running prod worker image):**
  | file | main 9efca9b6 | prod worker image |
  |---|---|---|
  | worker/layers/07a-icd-coding.ts | e319e73a94d535aad4a8ef618b67433c | e319e73a94d535aad4a8ef618b67433c ✓ |
  | worker/note-templates/build-ultrasound-prompt.ts | cd0288f9251b35dfabec477b319b984d | cd0288f9251b35dfabec477b319b984d ✓ |
  | worker/note-templates/build-soap-prompt.ts | 75449ae849ce7aa488e521516d873f77 | 75449ae849ce7aa488e521516d873f77 ✓ |
  Prod already executes these exact versions (the earlier working-tree ship); main has now caught up. Drift closed. Proceeding to Stage 3 (deploy prod from merged main so image provenance == main + picks up sharp 0.35.3).

### Stage 3 — prod deploy (prod == merged main)
- Preflight/health GO: disk 65% (101G avail), 24Gi RAM avail, load 1.79, 9/9 healthy, balloon absent. Anthropic credit HTTP 200 (real completion).
- **Rollback tags (taken FIRST):** `meddoc-pro-transcribe-md:pre-driftfix-20260722` = 95f57158e3fe, `meddoc-pro-transcribe-md-worker:pre-driftfix-20260722` = 412dd3157475 (the pre-deploy live images).
- Rebuilt app + worker from main 9efca9b6 (`docker compose build`, BUILD_EXIT=0), recreated both `--no-deps --force-recreate`. New images: app **97143e480d44**, worker **998d4ee3d9c1**; both **healthy**. postgres/redis/minio/caddy untouched.
- **sharp-in-image verification (the deploy's only real delta):** inside the running app image — sharp **0.35.3**, @img/sharp-linux-x64 + -linuxmusl-x64 **0.35.3**, libvips **1.3.2**; `require('sharp')` LOADS + renders a real PNG via libvips 8.18.3. next/image optimizer route is alive + enforces its contract (q=100 rejected, q=75 accepted, local-URL resolution). A byte-level optimized response could NOT be captured because this app bundles **zero raster assets** (dark text/SVG clinical UI — no /public rasters, only fonts) and standalone won't serve a runtime-injected public file; the sharp path itself is fully proven by the in-image load+render.
- Post-deploy worker md5 in the RUNNING new container == main (07a e319e73a / build-ultrasound cd0288f9 / build-soap 75449ae8) — drift stays closed.
- **NATIVE_DOCX flag absent/OFF** in both app + worker containers (confirmed via `env`).
- **Real-AI smoke (opus-4-8, anchors ON, prisma writes stubbed → prod `meddoc` DB untouched): GREEN, 8/8.**
  - Ultrasound (symptomatic bilateral reflux): imaging shape (Findings+Impression, not SOAP) ✓; reflux times in seconds (3.4 s / 2.8 s / 0.4 s), no ms ✓; impression internally consistent (right GSV incompetent, not double-labelled) ✓; **07a ICD → I83.891 + I83.892 (symptomatic varicose veins, I83.8x)** ✓.
  - SOAP control (established, 2 chronic not at goal, Rx mgmt): SOAP shape ✓; **07b E/M → 99214** ✓.
  - Sign-gate flow (frozen `sign/route.ts`, byte-identical) was NOT re-exercised live (would need an invasive authed prod visit); it is covered by the Playwright E2E required check that passed on #377 + the md5 identity.
- **Baseline preserved:** transcribe_visits = 3 rows, id-set md5 `7c970ac6059a33084eaaf8b28f58ef03` — identical before and after (the pre-existing READY + 2 SIGNED visits untouched). Smoke was non-persisting; temp harness `_deploy_smoke.ts` deleted.
- **One-shot rollback:** `docker tag meddoc-pro-transcribe-md:pre-driftfix-20260722 meddoc-pro-transcribe-md:latest && docker tag meddoc-pro-transcribe-md-worker:pre-driftfix-20260722 meddoc-pro-transcribe-md-worker:latest && docker compose -f /opt/meddoc-pro/docker-compose.yml up -d --no-deps --force-recreate transcribe-md transcribe-md-worker`

### Stage 4 — #375 rebased + green + OPEN
- feat/template-ingestion-unified rebased onto main 9efca9b6 (12 commits, clean — no conflicts). New head **8e02b5d**. Diff vs main = 68 files (+15962/−30): the feature + additive Prisma migration (7 tables / 4 enums / 10 AuditAction values, zero ALTER) + schema. **Zero package.json/lockfile churn, zero IOV-file churn.**
- Frozen surfaces byte-identical (04b-anchor-verify / sign/route / em / 07b-cpt / rx-warnings / audit / auth — NONE appear in the diff).
- **CI 6/6 GREEN on its own merits:** Playwright E2E ✓, test ✓, unit tests ✓, axe-core ✓, npm audit (high+critical gate) ✓ (inherits main's sharp-fixed lockfile), TruffleHog ✓.
- **Left OPEN, unmerged** for Kasra's review (commented ready-for-review). `NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX` stays default OFF.

### Dependabot PRs — deliberately NOT closed
- 14 open dependabot PRs exist (#373/#372/#349/#161/#160/#159/#158/#156/#155/#154/#153/#152/#151/#150). None are superseded by #376: that PR made **transitive lockfile-only** bumps (brace-expansion/fast-uri/js-yaml/hono/sharp); these dependabot PRs target unrelated **direct-dep** upgrades, several risky majors (typescript 6, eslint 10, @types/node 25, resend 6, next-auth beta.32, framer-motion 12, tailwind-merge 3). Dependabot auto-rebases its grouped PRs when a transitive dep moves on main, so no manual close is needed. Left for Kasra to triage — closing them would be spurious and outward-facing.

## FINAL — chain complete (prod == main, everything green before prod was touched)
| stage | result |
|---|---|
| sharp audit ladder | **rung 1b** (controlled re-resolve), sharp 0.34.5→0.35.3 ONLY; 5 proofs green |
| #376 (audit gate) | 6/6 CI green, squash-merged → main d1dcd1b |
| drift fix | #374 was CLOSED + un-reopenable → reissued **#377** (byte-identical), 6/6 green, squash-merged → main **9efca9b6** |
| md5 prod==main | 3 worker files identical (main == running prod image) ✓ |
| prod deploy | rebuilt+recreated app 97143e480d44 / worker 998d4ee3d9c1 from main; both healthy; rollback tag `pre-driftfix-20260722` |
| sharp-in-image | 0.35.3 + @img linux binaries + real libvips render ✓ |
| prod smoke | 8/8 green (ultrasound I83.891/892 + seconds + imaging + consistent; SOAP E/M 99214); baseline 3 visits md5 `7c970ac6…` unchanged |
| flag posture | NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX absent/OFF in both containers ✓ |
| #375 (feature) | rebased onto main, 6/6 green, **OPEN unmerged** for Kasra |
| frozen surfaces | untouched throughout (04b budget intact) |

**One-shot prod rollback:** `docker tag meddoc-pro-transcribe-md:pre-driftfix-20260722 meddoc-pro-transcribe-md:latest && docker tag meddoc-pro-transcribe-md-worker:pre-driftfix-20260722 meddoc-pro-transcribe-md-worker:latest && docker compose -f /opt/meddoc-pro/docker-compose.yml up -d --no-deps --force-recreate transcribe-md transcribe-md-worker`

## MASTER RUN — FINISH native-DOCX (Stages 1-5 done; STOPPED before Stage 6 prod flag-flip)
Branch feat/native-docx-numeric-fill @ 60cade4 → **PR #378** (open). Base: main 154cfe18 (after #375 merged in Stage 1).

### Stage 1 — #375 MERGED
- Rebased on main, 6/6 green, squash-merged → main **154cfe18**. Feature (flag OFF) now on main.

### Stage 2 — numeric table-cell fill (bridge-fill.ts + tests)
- `bridgeNumericTableCells`: parse the generated markdown table, align data rows to IR table-cell fields by vein-label + forward-cursor, fill BARE numerics; `—`/`[not documented]`/prose stay blank. `mergeFieldResolutions` overlays picks+numerics onto the resolver baseline (real evidence wins). Deterministic WM_IOV tests: exact values in exact cells, roundtrip, static byte-identical. One-leg-only regression proves no laterality mis-place.

### Stage 3 — manifest wiring
- Generated note threaded worker→fill-step→processTemplateTwinVisit→prepareTemplateTwinFill; overlay `bridgeTemplateFill` between resolve+finalize so the persisted manifest carries the fills. markerText derived from the verified source. On-demand fallback (deterministic, gated, fail-safe) when manifest absent. Flag-OFF short-circuits before touching the note → worker byte-identical.

### Stage 4 — certify-once UX
- Settings "Native template (beta)" panel (flag-gated; null slot when OFF → byte-identical). Server actions on requireSession; PHI-safe typed errors; certify transparently runs the REQUIRED synthetic roundtrip proof before certifyAndActivate. a11y-clean.

### Stage 5 — verification (real-AI e2e IN-PROCESS, not full-browser — see caveat)
- **Deterministic control suite: 164 files / 2017 tests GREEN** (twin, fabrication canaries, security canaries, em/rx, flag-off golden).
- **Real-AI in-process E2E GREEN** (isolated, real Anthropic sonnet-4-6, prisma writes stubbed → zero prod writes): dictation → real-AI note-gen → bridgeTemplateFill → 6/28 dropdowns (only the dictated ones — correct constrained fill) + 10 dictated measurements placed correctly → native render of the doctor's WM_IOV, roundtrip verified, static parts byte-identical. Saved scratchpad/wm-iov-NATIVE-e2e.docx.
- **Browser proof (QA stack, my images, flags ON, real AI, clean my-schema DB):** logged in → Settings → the "Native template (beta)" certify panel RENDERS (flag lever took; Ultrasound specialty visible too) → uploaded WM_IOV → the certify action ran → **the source-PHI gate correctly BLOCKED it**, and the UI surfaced the exact rejection message. Screenshot: certify-panel.png.
- **CAVEAT (honest):** the full browser upload→certify→dictate→sign→export flow was NOT completed end-to-end in the browser because (a) the QA stack's migrator was Codex-era-stale (required a wipe + rebuild-from-branch), and (b) — the real blocker — **the WM_IOV template trips the conservative source-PHI gate** (below). The AI-in-the-loop fill+export is proven by the in-process E2E instead.
- code-quality-auditor on the full diff: **0 BLOCK · 5 WARN · 2 NIT** — WARNs FIXED (TOKEN-001 #08090a→#0d1611; COMP-003 Record maps; BOUND-002 inline-LLM + on-demand-compute documented; laterality documented + one-leg regression added).
- **Frozen-surface diff-proof:** 04b, sign/route, 07b E/M, rx-warnings, audit, auth, nextauth ALL byte-identical to main.

### PHI-GATE BLOCKER (why Stage 6 stopped)
- The certify flow's `assertTemplateTwinSourcePhiFree` rejected WM_IOV. Diagnosed:
  1. **Deterministic `detectStructuredPhi` false-positive** — a clinic-address ZIP ("…, CA 92604") inside the **"Address" DROPDOWN OPTION** tripped the 5+ digit `long-id` rule. **FIXED** (neutralise `{{one of}}` option lists before the structured + LLM scan — the same "options are format, not content" principle the note-format PHI gate already uses; fixed text still fully scanned). Locked by a test on the real WM_IOV fixture.
  2. **Residual: the AI part-scan sets `anyUncertain`** on the WM_IOV **letterhead** (provider name + clinic addresses in the header/footer OOXML parts, scanned verbatim). The body scan is clean; it's the letterhead the conservative model won't vouch for. **NOT fixed** — relaxing the PHI gate on letterhead is a clinical/product judgment I will not make autonomously in a clinical app with unsigned BAAs.
- **Consequence:** WM_IOV (and any letterhead-heavy template) cannot be certified through the gate as-is, so the prescribed Stage-6 prod smoke ("upload WM_IOV → certify → dictate → sign → export") cannot complete. Deploying the flag ON while the flagship acceptance is blocked would be "forcing" — so I STOPPED before the prod flag-flip per the run's hard rule, pending a decision.

### Stage 6 — NOT DONE (deliberately)
- Prod UNTOUCHED (9/9 healthy). No rollback tags, no migration change (the additive migration is already on main via #375), no flag flip, no smoke. `NEXT_PUBLIC_TEMPLATE_NATIVE_DOCX` remains OFF in prod.
- The build-arg lever IS wired (Dockerfile ARG/ENV + compose interpolation from .env) and verified to take (the QA app baked+served the flag-ON UI).

### Decision needed (see morning summary)
1. PHI gate vs letterhead: (a) align the twin gate's SCOPE with the note-format gate (don't PHI-scan raw header/footer letterhead — provider metadata, already unscanned in the shipped note-format flow) — a consistency fix I can apply on approval; OR (b) require a letterhead-free acceptance template; OR (c) tune the gate another way.
2. Prod flag-flip: proceed once (1) is resolved + the WM_IOV certify path is green, OR ship flag-ON now for PHI-clean templates only (WM_IOV acceptance deferred).

## UPDATE — PHI fix applied (per decision); NEW blocker found; prod still NOT deployed
Decision taken: align twin PHI scan scope with note-format gate + fix-PHI-first-then-deploy.
- **PHI fix DONE + verified:** twin source-PHI scan now body-only (letterhead header/footer excluded) + {{one of}} options neutralised → **WM_IOV passes the full gate (real-AI verified)**. Commits 60cade4 (WARN fixes + dropdown-option ZIP fix) + 43b3273 (letterhead-scope fix). **PR #378 now 6/6 CI GREEN.**
- **NEW BLOCKER (why prod deploy did NOT happen):** on the QA stack, `createTemplateTwinDraft` **hangs/does-not-complete (>5 min)** for the real 80-field WM_IOV template. Isolated to `proposeSemanticMappings` (semantic-mapping/index.ts:222, called create-draft.ts:219) — ONE 8192-max-token AI call mapping ALL 80 fields at once. Known-flaky (memory: "Real-AI mapping proposal is FLAKY, SCHEMA_FAIL even at 8192"); 80 fields overflow 8192 → schema-fail → retries → no completion in the request window. PHI gate alone passes in seconds; compile + fill + export all proven. **This is Codex-salvage backend (semantic-mapping / create-draft), NOT the Stages 2-4 code.**
- Consequence: the browser certify-through-CERTIFIED + the full acceptance smoke can't go green, so per "fix-first-then-deploy" I did **NOT** touch prod. Prod 9/9 healthy, flag OFF, no rollback tags, no migration change.
- **Decision needed:** fix the mapping proposal for large templates (batch the fields into chunks under the token ceiling, or fall back to fallbackSemanticMappings faster instead of retrying, or raise/stream maxTokens) — a backend change to Codex-salvage code — before the certify UX is usable for big templates (and before the WM_IOV acceptance + prod deploy). Options: (a) I implement field-batched mapping + re-test + deploy; (b) hold for review.

## UPDATE 2 — mapping FIXED; #378 MERGED; QA smoke surfaced 2 more certify issues; prod STILL not deployed
- **Mapping batching FIXED (470d1e2):** chunk fields (20/call) + run concurrently + coerce expectedDataType to the compiler kind. In-process WM_IOV: hang→**49s, 80/80**. #378 re-greened 6/6 → **SQUASH-MERGED → main cbd273ac** (feature+all fixes on main, flag OFF).
- **QA acceptance smoke (real browser, my images, real AI) — got FURTHER, found 2 more real issues:**
  1. **Twin artifact bucket not provisioned** — the store uses a SEPARATE bucket `transcribe-md-template-artifacts` (not `transcribe-md-audio`) and DELIBERATELY never auto-creates it ("provisioning is an operations decision", artifact-store.ts:234). QA (and PROD — the twin has never run there) lacked it → certify draft failed at storeSourceArtifact. **Fixed in QA by `mc mb`. THIS IS A PROD DEPLOY PREREQUISITE: create `transcribe-md-template-artifacts` in prod MinIO before enabling the flag.** After provisioning, the browser certify **draft + 80-field review workspace rendered end-to-end** (~37s).
  2. **Certify synthetic-proof fails VALIDATION for WM_IOV** — `runTemplateTwinSyntheticTest` fills via the RESOLVER ONLY (no picks/numeric bridge), so a CHOICE_SLOT-driven template fills ~nothing → `validation.valid=false` → `render=null` → VALIDATION_FAILED (latestTestVerifiedAt/OutputSha256 both NULL). The certify-time proof mechanism predates the bridge and doesn't use it, so it can't produce a meaningful fill for bridge-dependent templates. **OPEN.**
- **Consequence:** certify-through-CERTIFIED still can't go green for WM_IOV (synthetic-proof gap), so per fix-first-then-deploy **prod was NOT touched.** Prod 9/9 healthy, flag OFF, feature merged to main.
- **What IS proven:** numeric fill + wiring + certify UI (2017 tests + auditor 0-BLOCK + frozen byte-identical + real-AI in-process fill/export e2e); the certify UPLOAD→DRAFT→REVIEW works end-to-end in the real browser after the bucket fix; mapping + PHI fixes verified.
- **Open decisions before deploy:** (A) provision the `transcribe-md-template-artifacts` bucket in prod (required regardless). (B) Certify synthetic-proof for bridge-driven templates: either wire the bridge into runTemplateTwinSyntheticTest (generate a note from the synthetic encounter → bridge-fill → render), OR relax the synthetic-proof validation to a render-mechanics check (it is a roundtrip proof, not a fill-completeness gate). Both are certify-backend (Codex-salvage) changes needing a design call.

## UPDATE 3 — ROOT-CAUSE found: twin NoteTemplate carries SYSTEM-DEFAULT sections, not the docx structure
While starting the (user-approved) "wire the bridge into the synthetic proof" fix, found the DEEPER root cause:
- **create-draft.ts:269 sets the twin NoteTemplate `sections: systemDefault.sections`** — the system-default SOAP sections, NOT the uploaded docx's parsed structure (its {{one of}} markers + DIAMETER/REFLUX table).
- Consequence: the worker's note-generation for a real visit on the certified twin produces a **SOAP note**, not the WM_IOV markdown table with picks. So the picks/numeric **bridge parses nothing → fills 0 → native export would be an empty WM_IOV**, and the certify synthetic-proof (same fill path) fails validation.
- My in-process real-AI e2e passed ONLY because it CONSTRUCTED a ResolvedNoteTemplate from the docx markerText (buildNoteTemplate) — the real twin note template does not carry that structure. The e2e proved the bridge MECHANICS, but not the end-to-end wiring against a real twin note template.
- **The real remaining work (the "bridge-into-manifest" gap in the memory):** create-draft must populate the twin NoteTemplate's sections with the DOCX's PARSED structure — sections whose defaultText carries the {{one of}} markers + a table section (kind:'table' rowLabels/columns) — the SAME representation the My Note Format parse (parseNoteToTemplate / reconcile-markers) produces and the structured-templates pipeline already fills. Only then does the worker note-gen emit a WM_IOV-structured note the bridge fills, the synthetic proof render, and native export return a filled document.
- This is an ARCHITECTURAL piece (docx → note-template structure for the twin), not a quick fix — surfaced for a design decision rather than rushed at run end.
- Prod remains UNTOUCHED (9/9, flag OFF). Feature (bridge + wiring + certify UI + mapping/PHI/bucket fixes) merged to main cbd273ac, all green, flag OFF — but native fill is not yet end-to-end functional against a real twin note template until the structure gap is closed.
