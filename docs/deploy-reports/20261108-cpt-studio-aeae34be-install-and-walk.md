# CPT Studio recall round: install of aeae34bebbe5 and its acceptance walk (owner directive 2026-11-06, items 7 to 9)

## What is installed
- **Revision:** aeae34bebbe57d907ac7870e2456904a6515a2a0 (PR #1486), image cpt-studio:aeae34bebbe5
  (sha256:78fc009b900c).
- **Installed:** 2026-11-08, app phase 06:54:55-06:57:47Z.
- **Declaration:** docs/foundation/mutations/20261108-cpt-studio-recall-round-install.md, commit 5e59e9a4 (committed
  06:19:51Z), merged as 015c3ff7 (PR #1487) before the act.
- **Receipts,** in /home/claude/cpt-studio-install-20261023/:
  - preflight-20261108T065400349287Z.json
  - image-20261108T065422652624Z.json
  - app-20261108T065747983657Z.json
  - verify-20261108T065810077764Z.json
  - reassess-20261108T065843448395Z.json (dry run)
  - reassess-20261108T065929138028Z.json
- **Rollback image:** cpt-studio:73dcf8b4b40a, kept.
- **Served:** https://cpt.quillmd.com/health/ reports release aeae34bebbe57d907ac7870e2456904a6515a2a0; the worker beat
  reports the same revision; no migration.
- **The declaration, row by row:** every declared row matched (the judgment is reproduced below). No stop condition
  was met.
  - The gi-context@4 comparison on the pre-app dump: 0 of 31 current contexts differ under @5, and the control is
    detected.
  - No migration.
  - Nothing sent: provider runs 209, sent 187, exchanges 180, tool calls 123 and credits unchanged through app, verify
    and reassess.
  - Availability: 301 of 301 samples 200, with releases_seen 73dcf8b4 then aeae34be.
  - states_recomputed {"encounters": 75, "changed": {}}.
  - The four retained encounters were re-assessed as predicted, with nothing sent and no open question:
    - 39f0ac49: 43239, 45380, 45385, 43247 READY;
    - d44a77b3: 43239, 45385, 45381, 43247 READY;
    - e888f9ce: 45385, 45380 READY;
    - 88d9db32: 45380, 45381, 43239, 43249, 45390, 45385 READY.
  - Co-tenants unchanged.

## Fresh acceptance results

Every approval below is an agent-executed synthetic review (review-agent; ops-agent beside it), and no human clinical
review is claimed. The expectations are each author's provisional reading, not a qualified coder's adjudication.

### c4 (written blind, the independent evidence): 0 of 3

c4 was written and sealed at 2026-11-07T10:39-10:40Z by an agent blind to the repair. Its four sha256 values were checked
by the manifest builder before anything read it, and its manifest was built from its expectations alone at 07:00:22Z,
after the install. The walk ran 07:00:35-07:09:14Z (evidence-c4-r-aeae34be).

Every failure is a hold, never a false READY: no code the author marked must-not-be-READY was READY. Each cause is a
recorded OPEN finding, read on the installed tree with minimal pairs:

- **c4a** (PDF, an EGD with dilation and biopsies, and a colonoscopy with polypectomy): 43248, 43239, 45385 and 45381 are
  all held, each with a performed-status and an extent question. Both procedure narratives sit in labelled paragraphs
  ("UPPER ENDOSCOPY: The gastroscope ...", "COLONOSCOPY: A digital rectal exam ...").
  - The upper one is refused by the labelled release's N1: "the wire mark was noted **at the bite block**" is a place
    adjunct the allow-list does not anchor.
  - The colonoscopy follows it and is refused by P4.
  - Both narratives therefore read as not today's. **U18** (the labelled release refused on ordinary content).
  - Stop and Resume worked on this fresh document (stop 200, resume 201).
- **c4b** (Word, a food-bolus removal with EGD biopsies): 43239 is READY and was approved, and the approval persisted
  after a reload. 43247 is held with a performed-status question: the bolus "captured ... and brought out through the
  mouth" states no removal the reader reads. **U16.**
- **c4c** (PDF, an EGD with biopsies, and a colonoscopy whose extent the report never states): 43239 is held for the
  EGD's extent. "advanced ... down a normal esophagus to the gastroesophageal junction, where ..., then on through the
  stomach and the pylorus to the third portion of the duodenum" reads no extent. The same sentence without the opening
  reads "incomplete: stomach": the reach's continuation past its first landmark is not read. **U14.**
  - 45385 is correctly held: the colonoscopy's extent is not documented, as the author expected.
  - Two of c4c's failed checks are artifacts of the session's manifest builder, not the product's. The author's extent
    question was about "45385 vs 45338", which the builder mapped to no family. It therefore required the colonoscopy
    "not performed", which the document contradicts and the product rightly does not do. It also named no code for the
    details answer, so the walk found no single row to answer.

### c1c (written by this session, the regression of the walk round's addendum race): fail, on the walk tool

The identical re-upload reused the retained Corti, Astra and Fable results. The member's "Not documented" extent answer
excluded 45338, as before. After the answer was withdrawn, the product re-opened the row: the final read shows 45338
needing its extent detail, with the row unsaved and offering the addendum.

The walk tool's fix of the race (cd5212b9f) is itself wrong. It waits until no row of the fact and code shows the
withdrawn answer as saved, and that is also true while the row is briefly absent during the recompute. The walk read 0
open rows and stopped before the addendum, and persist.assessment followed from the stop. The wait must be for exactly one
open row of the fact and code that offers the addendum. That fix goes into the next round's tooling.

### c3 and c2: not walked again
Offline, c3's routing and date read exactly as on 73dcf8b4 (U18, the organ-list extent, U20), and c2a and c2b hold
exactly as before (U15, U16). Walking them again would repeat identical failing paid attempts.

## The three participants' contributions
On every c4 document the three participants reached the codes the blind author expected, and CPT Studio's own readers
held them:
- c4a: 43248, 45381 and 45385 by Corti; 45385, 43248, 43239 and 45381 by Astra; 43248, 43239, 45385 and 45381 by Fable.
- c4b: 43239 and 43247 by all three.
- c4c: 43239 by all three; 45385 by Corti and Fable (correctly held for its extent).
- c1c (retained results reused): 45338, as before.

## Decisions and downloads
- Approved and persisted after a reload: c4b 43239.
- No other decision was possible: the remaining codes were held.
- Downloads: the suggested-codes draft (TXT and CSV) for every document. The approved report is withheld, with its
  blockers listed, wherever a code is held.

## Usage and cost
- c4 (fresh uploads): 15 provider runs, all sent and all succeeded.
  - Corti: 0.170568 credits.
  - Astra: 54,558 input and 9,597 output tokens.
  - Fable: 165,832 input and 21,378 output tokens.
  - The participants' own estimate is about 2.23 USD.
- c1c (identical re-upload): 5 provider runs.
  - 3 reused retained results (no new usage).
  - 2 peer reviews were sent: Astra 3,289 / 339 tokens; Fable 12,826 / 1,132 tokens.
- No unknown outcome; nothing purchased.

## Reported separately
- Clinical validation: not performed, and no human clinical review is claimed.
- Content-use permissions (D3 to D5): open, as recorded.
- Limitations: L1 (pypdf 6.21.2's seven advisories, accounted, not resolved), L2 (NCCI PTP not connected).
- Owner questions: Q1, Q2, 4.6 (D7 stays off).
- Open defects: U14, U15, U16, U17, U18, U20, U22 and U23, and the residuals in ACCURACY-RESIDUALS.md. The blind walk
  failed on U14, U16 and U18, so completion is not claimed.

## The install judgment (verbatim from the session directory): aeae34bebbe5 at cpt.quillmd.com (2026-11-08), against docs/foundation/mutations/20261108-cpt-studio-recall-round-install.md

Declaration committed 5e59e9a4 at 2026-11-08T06:19:51Z; landed by PR #1487 as 015c3ff7 (merged 06:53:01Z; changes only the
declaration and the checklist since aeae34be). Act checkout: /opt/meddoc-pro/.worktrees/cpt-recall-act-20261108 at
015c3ff7 (clean, detached). Pre-checks: the declared byte-identical paths exit 0; nothing under cpt-studio or the gate
scripts since the revision (exit 0). Preflight health check GO
(docs/preflight-reports/preflight-20261108T065352Z.md, in the h2-repair worktree).

| phase | started (door) | receipt | judged |
|---|---|---|---|
| preflight | 06:53:55Z | preflight-20261108T065400349287Z.json | ok; tree descendant-without-runtime-change (015c3ff7); nginx -t ok; ports 9150 active / 9151 idle; participant sources present; co-tenants as before |
| image | 06:54:15Z | image-20261108T065422652624Z.json | cpt-studio:aeae34bebbe5 = sha256:78fc009b900c; every step CACHED (apt and pip never ran); offline: dpkg 166 packages, sorted-list sha 0201a269fab18f06 = cpt-studio:73dcf8b4b40a's, pypdf 6.21.2, user 10150:10150, CPT_STUDIO_RELEASE_SHA = aeae34be |
| pre-app | 06:54:44Z | pre-app-aeae34bebbe5-20261108T065444Z.dump (0600) | 39 TABLE DATA; the gi-context@4 comparison on its restore: 35 contexts (31 current), 0 differing, CONTROL ok (restore dropped); baseline re-read = the declared baseline (every row; last audit 2026-11-07T10:33:19Z; jobs_active 0; reserved/sending 0; unreconciled 0) |
| app | 06:54:54Z | app-20261108T065747983657Z.json | migrate "No migrations to apply"; unrunnable stages none; blue/green 9150 -> 9151; availability 301 samples, 301 x 200, releases_seen 73dcf8b4 then aeae34be; states_recomputed {"encounters": 75, "changed": {}}; no access check; counts after app = pre-app on every row (contexts by version included: nothing remade, nothing sent); worker beat revision aeae34be; no *-previous / *-next container |
| verify | 06:58:07Z | verify-20261108T065810077764Z.json | /health/ release aeae34be under normal certificate verification, security headers once each; co-tenants and app.quillmd.com unchanged |
| reassess dry run | 06:58:22Z | reassess-20261108T065843448395Z.json | each of the 4 plans carries the declared final assessment, Astra and Fable runs and peer runs; 0 jobs |
| reassess | 06:59:12Z | reassess-20261108T065929138028Z.json | 4 jobs (one each), assess succeeded 06:59:17-06:59:28Z; counts: routing_runs 94->98, assessments 143->147, proposals 1952->2021, audit_events 1076->1084, jobs 502->506; nothing else moved (provider runs 209, sent 187, exchanges 180, tool calls 123, credits_sum, decisions 59, invalidations 2, contexts by version, encounter states); 0 provider runs created since app started |

Readings after reassess (exactly as declared; engine cpt-studio-validation@10, routing gi-routing@11):
- 39f0ac49 ready_for_review: 43239, 45380, 45385, 43247 READY; no open question.
- d44a77b3 ready_for_review: 43239, 45385, 45381, 43247 READY; no open question.
- e888f9ce ready_for_review: 45385, 45380 READY; no open question.
- 88d9db32 ready_for_review: 45380, 45381, 43239, 43249, 45390, 45385 READY; no open question.

Co-tenants after: quillmd.com 200, www 200, app 302, admin 503, pro 410 (as before). No stop condition met.
