# CPT Studio walk round: install of 73dcf8b4b40a and its acceptance walk (owner directive 2026-11-06, items 7 to 9)

## What is installed
- Revision: 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 (PR #1483), image cpt-studio:73dcf8b4b40a, installed 2026-11-07 (app phase 10:13:39-10:16:24Z)
  under docs/foundation/mutations/20261107-cpt-studio-walk-round-install.md (declaration commit 545afba7 (committed 08:49:25Z), merged as
  9842ed9c (PR #1484), before the act); receipts /home/claude/cpt-studio-install-20261023/preflight-20261107T101226918251Z.json, image-20261107T101256107597Z.json, app-20261107T101631568183Z.json, verify-20261107T101703144637Z.json, reassess-20261107T101745516777Z.json (dry run), reassess-20261107T101834553658Z.json. Rollback image
  cpt-studio:6f306af1b030 kept.
- Served: https://cpt.quillmd.com/health/ release 73dcf8b4b40a63a1bb8d95882d4ebc571732be13; worker beat revision 73dcf8b4b40a63a1bb8d95882d4ebc571732be13; no migration.
- The declaration, row by row: every declared row matched (install/judgment-walk.md in the session directory, reproduced below): no migration; nothing sent (provider runs 174, sent 163, exchanges 147, tool calls 100 and credits unchanged through app, verify and reassess); availability 300 of 300 samples 200 with releases_seen 6f306af1 then 73dcf8b4; states_recomputed {"encounters": 68, "changed": {}}; the four retained encounters re-assessed as predicted (39f0ac49 43239/43247/45380/45385, d44a77b3 43239/43247/45381/45385, e888f9ce 45380/45385 with no incompleteness check, 88d9db32 43239/43249/45380/45381/45385/45390 READY; no open question); co-tenants unchanged. No stop condition met.

## The walk findings of 6f306af1, before and after
| finding | before (6f306af1) | after (73dcf8b4) | evidence |
|---|---|---|---|
| 1 labelled paragraphs refused | refused | released under P1-P3/N1 | c3a shows the release still refuses a labelled paragraph on an ordinary word (N1): see the c3 results |
| 2 Savary dilation over a wire | held | OPEN (U15): held, as installed | ACCURACY-RESIDUALS.md |
| 3 extent from the first landmark | false incompleteness warning | OPEN (U14): as installed | ACCURACY-RESIDUALS.md |
| 4 bolus "brought out" | held | OPEN (U16): held, as installed | ACCURACY-RESIDUALS.md |
| 5 another polyp's failed attempt | held | READY beside the done act | c1b 45385 READY live, approved and persisted (evidence-c1-r73dcf8b4) |
| 6 the walk's list check | out of date | lists an answered-away code | c1c after_details.customer.codes.listed passes (the answered-away 45338 listed) |
| 7 the addendum response | revision id | revision number | c1c scan.json passes: no internal id in the addenda response |

## Fresh acceptance results
### c3 (written blind, the independent evidence)
0 of 3 (evidence-c3). Every failure is a hold or a false incompleteness warning, never a false READY. On all three
documents Corti, Astra and Fable proposed the expected codes. The causes were traced by an analysis workflow (an analyst
per document, a skeptic per claim; every attribution survived) and verified here with minimal pairs on the installed
tree. PREVIOUS (6f306af1) and BASE (b452c6c4) read every c3 document the same way: no regression, and none of the
causes is a recorded open finding (U14-U17).
- **c3a** (43239 and 45380 held). Neither labelled paragraph is released, so both narratives read under the
  Indications and no extent is found. Three independent gates hold the upper endoscopy, each enough alone, peeled
  one at a time here:
  - N1: "biopsies were taken from both" reads as an unanchored place;
  - N3: the consent sentence before the label ("after a discussion ...", "before each procedure") announces it;
  - the colonoscopy then falls by P4, and once N3 is gone by N2: a hard-wrapped "(Boston\nscore 8: 2-3-3)" puts
    "score 8:" at a line start, read as a label that cuts the paragraph;
  - latent beyond those: "prior", "in two bites", "the proximal side of a fold" (more N1 signals).
  Separately, "The duodenal bulb and second portion looked normal" is no reach (REACHED_AFTER needs the verb right after
  the landmark; "second portion" alone is no landmark).
- **c3b** (codes READY, routing failed). The organ-by-organ findings list "Stomach: Normal, including the retroflexed
  view of the cardia." reads as a reach, and "Duodenum: The bulb and second portion were normal." does not, so the
  stomach becomes the deepest point ("incomplete: stomach"). Verified: "Duodenum: Normal bulb and second portion."
  reads the duodenum. This document's bolus removal wording WAS read: 43247 READY.
- **c3c** (43248, 45380 and 45381 held). Two gaps, each enough alone to lose the upper extent:
  - numbered "PROCEDURE 1 - EGD" / "PROCEDURE 2 - COLONOSCOPY" headings open no section, so the HISTORY section runs
    over both narratives and every act reads historical (the recorded residual "gap a", here with a dash and under
    HISTORY);
  - "The stomach and the duodenum to the second portion were normal." is no reach.
  Verified: fixing both reads the second part of the duodenum. The colonoscopy extent is truly unstated ("inserted and
  advanced"): the blind author's expected question. details.request failed only because the false upper-extent
  question made a second extent row; the plan named no code (a builder limit, fixed by naming the code).
- **Walk-tool and builder changes for the next walk:** after a withdrawal, wait for the row to read unsaved; carry
  stop_and_resume on a fresh document; name the code in a family-level question's details entry.
### c1 (written by this session, walked beside it as regression)
1 of 3 pass (c1a). The two failures are the walk tool's timing, not the product's (evidence-c1-r73dcf8b4):
- **c1b:** its code passes (finding 5 live: 45385 READY, approved, persisted, the approved downloads matching). Stop
  was not exercised: the byte-identical re-upload reused the retained Corti, Astra and Fable results (duplicate
  prevention), so processing took 18 s against 106 s before, and the panel's Stop was gone when the walk asked for it
  at 16 s. Stop and Resume need a fresh document; they are carried to the next walk.
- **c1c:** the answered-away 45338 is listed (finding 6) and the addenda response carries no internal id (finding 7).
  The addendum step failed on a race: the withdrawal recomputed in under a second, the walk read the snapshot from
  before it (0 open rows), and the extent row was in fact open and offering the addendum. The fix is in the walk tool:
  wait for the row to read unsaved.
### c2: not walked again
c2a and c2b hold 43248 and 43247 offline exactly as on 6f306af1 (findings 2 and 4, open); walking them again would repeat
an identical failing paid attempt.

## The three participants' contributions
On every c3 document the three participants reached the codes the blind author expected, and CPT Studio's own readers
held them:
- c3a: 43239 and 45380 proposed by Corti, Astra and Fable; both held.
- c3b: 43247 by all three and 43239 by Astra and Fable; both READY (with a false incompleteness warning).
- c3c: 43248 and 45380 by all three, 45381 by Astra and Fable; all held.
- c1 (retained results reused): c1a 43239, 45385, 45381 by all three and 43247 by Astra and Fable; c1b 45385 and 45380
  by all three; c1c 45338 by Astra and Fable.

## Decisions and downloads
Every decision is labelled an agent-executed synthetic review (the review-agent account); no human clinical review is
claimed.
- Approved and persisted after a reload: c3b 43247 and 43239; c1a 43239, 45385, 45381 and 43247; c1b 45385 and 45380.
- No decision on c3a, c3c or c1c: their codes were held.
- Downloads: the suggested-codes draft (TXT at 390x844, CSV at desktop) for every document; the approved TXT and CSV
  for c3b, c1a and c1b, each re-fetched and equal to the operator's stored bytes; elsewhere the approved option is
  withheld with its blockers listed.

## Usage and cost
- c3 (fresh uploads): 15 provider runs, all sent - Corti 0.186388 credits; Astra 51,002 input / 8,817 output tokens; Fable 166,232 input / 19,450 output tokens.
- c1 (identical re-uploads): 15 provider runs, 11 reused retained results (no new usage) and 4 peer reviews sent - Corti 0 credits; Astra 7,497 / 404 tokens; Fable 20,555 / 1,361 tokens.
- No unknown outcome; nothing purchased.

## Reported separately
- Clinical validation: not performed; every approval in the walk is an agent-executed synthetic review, and no human
  clinical review is claimed.
- Content-use permissions (D3 to D5): open, as recorded.
- Limitations: L1 (pypdf 6.21.2's seven advisories, accounted, not resolved), L2 (NCCI PTP not connected).
- Owner questions: Q1, Q2, 4.6 (D7 stays off).
- Open defects: U14, U15, U16 (walk findings 3, 2, 4) and U17 (pre-existing installed false READYs found by the round's
  fourth lens); completion is not claimed while they are open.

## The install judgment (verbatim from the session directory): 73dcf8b4b40a at cpt.quillmd.com (2026-11-07), against docs/foundation/mutations/20261107-cpt-studio-walk-round-install.md

Declaration committed 545afba7 at 2026-11-07T08:49:25Z; landed by PR #1484 as 9842ed9c (changes only the declaration since
73dcf8b4). Act checkout: /opt/meddoc-pro/.worktrees/cpt-walk-round-act-20261107 at 9842ed9c (clean, detached). Pre-checks:
the declared byte-identical paths exit 0; nothing under cpt-studio or the gate scripts since the revision (exit 0).
Preflight health check GO (docs/preflight-reports/preflight-20261107T101211Z.md, in the walk-round worktree).

| phase | started (door) | receipt | judged |
|---|---|---|---|
| preflight | 10:12:21Z | preflight-20261107T101226918251Z.json | ok; tree descendant-without-runtime-change (9842ed9c); nginx -t ok; ports 9151 active / 9150 idle; participant sources present; co-tenants as before |
| image | 10:12:48Z | image-20261107T101256107597Z.json | cpt-studio:73dcf8b4b40a = sha256:089b13d4acb6...; every step CACHED (apt and pip never ran); offline: dpkg 166 packages sha 500b6abda58b9a3e = 6f306af1b030's, pypdf 6.21.2, uid 10150, CPT_STUDIO_RELEASE_SHA = 73dcf8b4 |
| pre-app dump | 10:13:30Z | pre-app-73dcf8b4b40a-20261107T101330Z.dump (0600) | 39 TABLE DATA; baseline re-read = the declared baseline (every row; last audit 05:21:19Z; jobs_active 0; reserved/sending 0; unreconciled 0) |
| app | 10:13:39Z | app-20261107T101631568183Z.json | migrate "No migrations to apply"; unrunnable stages none; blue/green 9151 -> 9150; availability 300 samples, 300 x 200, releases_seen 6f306af1 then 73dcf8b4; states_recomputed {"encounters": 68, "changed": {}}; no access check; counts after app = pre-app on every row (nothing sent); worker beat revision 73dcf8b4; no *-previous / *-next container |
| verify | 10:16:59Z | verify-20261107T101703144637Z.json | /health/ release 73dcf8b4 under normal certificate verification, security headers once each; co-tenants and app.quillmd.com unchanged |
| reassess dry run | 10:17:22Z | reassess-20261107T101745516777Z.json | each of the 4 plans carries the declared final assessment, Astra and Fable runs and peer runs; 0 jobs (433 jobs, 0 active) |
| reassess | 10:18:11Z | reassess-20261107T101834553658Z.json | 4 jobs (one each), assess succeeded 10:18:22-10:18:33Z; counts: routing_runs 83->87, assessments 123->127, proposals 1643->1712, audit_events 925->933, jobs 433->437; nothing else moved (provider runs 174, sent 163, exchanges 147, tool calls 100, credits_sum, decisions 51, invalidations 2, encounter states) |

Readings after reassess (exactly as declared and as the predictions read them; engine cpt-studio-validation@10):
- 39f0ac49 ready_for_review: 43239, 43247, 45380, 45385 READY; no open question.
- d44a77b3 ready_for_review: 43239, 43247, 45381, 45385 READY; no open question.
- e888f9ce ready_for_review: 45380, 45385 READY, no incompleteness check on either; no open question.
- 88d9db32 ready_for_review: 43239, 43249, 45380, 45381, 45385, 45390 READY; no open question.

Co-tenants after: quillmd.com 200, www 200, app 302, admin 503, pro 410 (as before). No stop condition met.
