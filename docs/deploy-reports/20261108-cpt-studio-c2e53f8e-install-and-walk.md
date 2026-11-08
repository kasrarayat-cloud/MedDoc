# CPT Studio structure round: install of c2e53f8e7d33 and its acceptance walk (owner directive 2026-11-06, items 7 to 9)

## What is installed
- **Revision:** c2e53f8e7d33732d5badd4ce9b681f274eb5c471 (PR #1489), image cpt-studio:c2e53f8e7d33
  (sha256:02a99d53026f).
- **Installed:** 2026-11-08, app phase 22:53:32-22:56:31Z.
- **Declaration:** docs/foundation/mutations/20261108-cpt-studio-structure-round-install.md, committed 16a0ec28 (22:14:10Z)
  and corrected by 696595b3 (22:19:41Z) before the merge and the act: the c4 walk's peer reviews are sent again, not
  reused. Merged as 09c4eab2 (PR #1490) before the act.
- **Receipts,** in /home/claude/cpt-studio-install-20261023/:
  - preflight-20261108T225200993090Z.json
  - image-20261108T225225014330Z.json
  - app-20261108T225631452167Z.json
  - verify-20261108T225654112452Z.json
  - reassess-20261108T225758685106Z.json (dry run)
  - reassess-20261108T225856001655Z.json
- **Rollback image:** cpt-studio:aeae34bebbe5, kept.
- **Served:** https://cpt.quillmd.com/health/ reports release c2e53f8e7d33732d5badd4ce9b681f274eb5c471; the worker beat
  reports the same revision; no migration.
- **The declaration, row by row:** every declared row matched (the judgment is reproduced below). No stop condition
  was met.
  - The gi-context@4 comparison on the pre-app dump: 0 of 35 contexts (31 current) differ under @5, and the control is
    detected.
  - No migration.
  - Nothing sent: provider runs 229, sent 204, exchanges 204, tool calls 140 and credits unchanged through app, verify
    and reassess.
  - Availability: 305 of 305 samples 200, with releases_seen aeae34be then c2e53f8e.
  - states_recomputed {"encounters": 79, "changed": {}}.
  - The four retained encounters were re-assessed as predicted, under gi-routing@12, with nothing sent and no open
    question:
    - 39f0ac49: 43239, 45380, 45385, 43247 READY;
    - d44a77b3: 43239, 45385, 45381, 43247 READY;
    - e888f9ce: 45385, 45380 READY (its two decisions as they were);
    - 88d9db32: 45380, 45381, 43239, 43249, 45390, 45385 READY.
  - Co-tenants unchanged.

## Fresh acceptance results

Every approval below is an agent-executed synthetic review (review-agent; ops-agent beside it), and no human clinical
review is claimed. The expectations are each author's provisional reading, not a qualified coder's adjudication.

### c5 (written blind, the independent evidence): 0 of 3

c5 was written and sealed at 2026-11-08T08:07:40Z by an agent blind to the repair. Its four sha256 values were checked
by the manifest builder before anything read it, and its manifest was built from its expectations alone at 22:59:53Z,
after the install. The walk ran 23:00:10-23:08:02Z (evidence-c5-s-c2e53f8e).

Every failure is a hold, never a false READY: no code the author marked must-not-be-READY was READY. The causes were read
offline on the installed tree:

- **c5a** (PDF, an EGD for a food impaction, with biopsies): 43239 and 43247 are held with performed-status questions,
  and the EGD routes as "historical". The title "UPPER ENDOSCOPY (EGD) - URGENT ADD-ON" carries an aside the title
  rules do not list. That one line has three effects:
  - it is an unsafe title, so the instrument reader stops below it (I7);
  - it is no procedure title, so the document is not read as a procedure report (I9);
  - the title itself reads uncertain.
  The "Procedure:" paragraph is a procedure section and its gastroscope meets every other instrument condition, but no
  mention there is read. What remains is the title (uncertain), a 2024 outside EGD (historical) and "Repeat EGD"
  (planned). **U29, new.** Stop and Resume worked on this fresh document (stop 200, resume 201).
- **c5b** (Word, a colonoscopy with a piecemeal cold-snare polypectomy and a tattoo): 45385 and 45381 are held. The
  colonoscopy routes as performed, and the documented-service inventory reads both snare removals. One sentence holds
  both codes: "It was removed piecemeal with a cold snare in four pieces, without submucosal injection."
  - 45385: the routing-era reading of that sentence is an unresolved negation. The engine releases one only where the
    passage overlaps no not-done act, and this one overlaps the denied lift injection. The narrower exception was
    refuted three times and dropped (HARNESS.md, the harness repair's round 3).
  - 45381: the denied lift injection is read against the tattoo's injection, an act of the same kind, so it is held
    for the reviewer.
  **U30.**
- **c5c** (PDF, an EGD with biopsies and a colonoscopy with a cold-snare polypectomy, in one session): 43239 is held, and
  every family routes as "historical".
  - The Indication's hard-wrapped "Past\nhistory: ERCP ..." puts "history:" at the start of a line, where it is read as
    a heading.
  - The 'history' section it opens swallows the bare "EGD" and "COLONOSCOPY" headings, which open no section (U20's
    class), and both narratives with them.
  - The title "ENDOSCOPY NOTE - EGD AND COLONOSCOPY, SAME SESSION" is also an unsafe title (U29).
  - 45385 is correctly held: the colonoscopy's extent is not documented, as the author expected.
  **U31.**

### c4 walked again (the repairs' evidence; not blind): the repairs read as designed, and two codes are still held

The same bytes reused the retained Corti run and Astra and Fable first readings; each peer review was sent again, as
the corrected declaration says. The walk ran 23:12:51-23:16:41Z (evidence-c4-s-c2e53f8e).

- **c4c** passes every product check:
  - 43239 is READY at the extent the U14 repair reads;
  - it was approved, and the decision persisted after a reload;
  - the approved report downloads (TXT and CSV) match it;
  - no must-not code is READY.
  Its one hard failure is the session's manifest builder's recorded artifact: the builder required the colonoscopy "not
  performed", which the document contradicts (recorded in the recall round's record).
- **c4b**: 43239 is READY, approved and persisted. 43247 is held, although the documented-service inventory now reads the
  bolus removal as performed: the U16 repair works at the reader. The hold comes from Corti's citation for 43247,
  which includes "The bolus was discarded and was not sent to pathology." That passage reads as an unresolved negation,
  and a cited passage that hedges holds the code. **U30.**
- **c4a**: both families now route as performed; the labelled release (U18) works on the live text. All four codes are
  still held:
  - 45385: Corti's citation includes another lesion's "narrow-band imaging, and it was not sampled." (U30);
  - 43248: the dilation over the wire is not read as done, and the organ-list reach gives no extent (U15/U17, U19);
  - 43239: no extent (U19);
  - 45381: "the site was tattooed: a saline bleb was raised in the submucosa" is not read as an injection.
  The declaration predicted 45385 READY. The prediction cited the snare sentence alone, by hand, on the source text. The
  live engine reads Corti's retained citation, five passages, on the PDF's extracted text. Routing on the two texts is
  identical; the citation set differs. **Offline predictions of a re-walk must use the retained provider responses on
  the extracted text.** The same holds for c4b's 43247.
- Stop and Resume worked on c4a mid-peer-review: Fable's peer review was stopped after one exchange, and the resumed
  chain sent it again.

## The three participants' contributions
On every c5 document the three participants reached the codes the blind author expected, and CPT Studio's own readers
held them:
- c5a: 43239 and 43247 by all three.
- c5b: 45385 and 45381 by all three.
- c5c: 43239 by all three; 45385 by Corti and Fable (correctly held for its undocumented extent).
- c4 reused its retained first readings and recorded new peer reviews.

## Decisions and downloads
- Approved and persisted after a reload: c4b 43239, c4c 43239.
- c4c's approved report downloaded (TXT and CSV) and matches the decision.
- Elsewhere the remaining codes were held, so no other decision was possible. The suggested-codes draft (TXT and CSV)
  downloaded for every document; the approved report is withheld, with its blockers listed, wherever a code is held.

## Usage and cost
- c5 (fresh uploads): 15 provider runs, all sent and all succeeded.
  - Corti: 0.150720 credits.
  - Astra: 52,109 input and 7,821 output tokens.
  - Fable: 159,269 input and 17,893 output tokens.
  - The product's own estimate for the first readings is about 1.99 USD; the peer reviews' tokens are included above.
- c4 (identical re-uploads): 9 reused runs (no new usage) and 7 peer reviews sent.
  - Astra: 3 peer reviews, 20,317 / 1,416 tokens.
  - Fable: 4 peer reviews, 81,774 / 5,580 tokens; one was stopped by the walk's Stop after one exchange and sent again
    on Resume.
- No unknown outcome; nothing purchased.

## Reported separately
- Clinical validation: not performed, and no human clinical review is claimed.
- Content-use permissions (D3 to D5): open, as recorded.
- Limitations: L1 (pypdf 6.21.2's seven advisories, accounted, not resolved), L2 (NCCI PTP not connected).
- Owner questions: Q1, Q2, 4.6 (D7 stays off).
- Open defects: U15, U17, U19, U20, U22, U23, U24 to U28, and the new U29, U30 and U31, with the residuals in
  ACCURACY-RESIDUALS.md. The blind c5 walk failed on holds, so completion is not claimed.

## The install judgment (verbatim from the session directory): c2e53f8e7d33 at cpt.quillmd.com (2026-11-08), against docs/foundation/mutations/20261108-cpt-studio-structure-round-install.md

Declaration committed 16a0ec28 at 2026-11-08T22:14:10Z and corrected by 696595b3 at 22:19:41Z, before the merge and the act:
the c4 walk's peer reviews are sent again, not reused. Landed by PR #1490 as 09c4eab2 (merged 22:50:52Z; it changes only
the declaration and the checklist since c2e53f8e). Act checkout: /opt/meddoc-pro/.worktrees/cpt-structure-act-20261108 at
09c4eab2 (clean, detached).
- Pre-checks: the declared byte-identical paths exit 0 against aeae34be; nothing under cpt-studio, run-ruled-mutation.sh
  or scripts/lib since the revision (exit 0); the delta is 18 files, 4373+/67- as declared.
- Preflight health check GO: docs/preflight-reports/preflight-20261108T225138Z.md, in the h2-repair worktree.

| phase | started (door) | receipt | judged |
|---|---|---|---|
| preflight | 22:51:54Z | preflight-20261108T225200993090Z.json | ok; tree descendant-without-runtime-change (09c4eab2); door: declaration sha256 30bf9093 = the file; nginx -t ok (existing warnings only); ports 9151 active / 9150 idle; participant sources present; co-tenants as before |
| image | 22:52:15Z | image-20261108T225225014330Z.json | cpt-studio:c2e53f8e7d33 = sha256:02a99d53026f; every step CACHED, apt and pip never ran (the one log line naming apt-get install is the step's own header). Offline: dpkg 166 packages; sorted-list sha 0201a269fab18f06 under the declared command (sorted on the host, en_US.UTF-8) = cpt-studio:aeae34bebbe5's (500b6abda58b9a3e for both, sorted in C, as the walk round's offline check measured); pypdf 6.21.2; user 10150:10150; CPT_STUDIO_RELEASE_SHA and the revision label c2e53f8e |
| pre-app | 22:53:18Z | pre-app-c2e53f8e7d33-20261108T225318Z.dump (0600) | 39 TABLE DATA; the gi-context@4 comparison on its restore: 35 contexts (31 current), 0 differing, CONTROL ok (restore dropped); baseline re-read = the declared baseline (every row; last audit 2026-11-08T07:13:30Z; jobs_active 0; reserved/sending 0; unreconciled 0) |
| app | 22:53:32Z | app-20261108T225631452167Z.json | migrate "No migrations to apply"; unrunnable stages none; blue/green 9151 -> 9150; availability 305 samples, 305 x 200, releases_seen aeae34be then c2e53f8e; states_recomputed {"encounters": 79, "changed": {}}; no access check; counts after app = pre-app on every row (contexts by version included: nothing remade, nothing sent); worker beat revision c2e53f8e; no *-previous / *-next container |
| verify | 22:56:50Z | verify-20261108T225654112452Z.json | /health/ release c2e53f8e under normal certificate verification, security headers once each; co-tenants and app.quillmd.com unchanged. Against the preflight baseline, the only nginx file that differs is sites-available/quillmd-cpt (proxy_pass 127.0.0.1:9150); nginx.conf, the enabled links and both file sets are unchanged |
| reassess dry run | 22:57:58Z | reassess-20261108T225758685106Z.json | each of the 4 plans carries the declared final assessment, Astra and Fable runs and peer runs (all 20 ids); 0 jobs |
| reassess | 22:58:29Z | reassess-20261108T225856001655Z.json | 4 jobs (one each), assess succeeded 22:58:41-22:58:54Z; counts: routing_runs 102->106, assessments 157->161, proposals 2157->2226, audit_events 1170->1178, jobs 545->549 (assess succeeded 157->161; assessments under cpt-studio-validation@10 34->38; routing gi-routing@12 0->4); nothing else moved (provider runs 229, sent 204, exchanges 204, tool calls 140, credits_sum, decisions 60, invalidations 2, contexts by version, encounter states); 0 provider runs created since app started |

Readings after reassess (exactly as declared; engine cpt-studio-validation@10, routing gi-routing@12):
- 39f0ac49 ready_for_review: 43239, 45380, 45385, 43247 READY; no open question.
- d44a77b3 ready_for_review: 43239, 45385, 45381, 43247 READY; no open question.
- e888f9ce ready_for_review: 45385, 45380 READY; no open question; its two decisions as they were.
- 88d9db32 ready_for_review: 45380, 45381, 43239, 43249, 45390, 45385 READY; no open question.

Co-tenants after: quillmd.com 200, www 200, app 302, admin 503, pro 410 (as before). No stop condition met.
