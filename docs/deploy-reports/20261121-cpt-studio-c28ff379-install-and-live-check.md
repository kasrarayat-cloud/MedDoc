# CPT Studio's question-ids fix installed at cpt.quillmd.com (0de2b5844857 to c28ff379ba40), and its view-only live check

Session `738699b2`, 2026-11-21. Owner direction D372 (ask each question once, for every document); declaration
`docs/foundation/mutations/20261121-cpt-studio-question-ids-install.md` (committed a46f1ed54b5c at 11:49:25Z, merged in
#1504 as b76aefdf5925 at 12:16:08Z). Every phase ran through `scripts/run-ruled-mutation.sh` from the clean, detached act
checkout `/opt/meddoc-pro/.worktrees/cpt-questions-act-20261121` (b76aefdf5925, a descendant of the revision that changes
nothing under `cpt-studio/` or the door). Receipts are in `/home/claude/cpt-studio-install-20261023/`; the wrapper's
logs are in `questions-20261121/install/` (act-q-*.log, pre-app-q-*.log, baseline-q-after-*.txt).

**Result: installed and verified. The live check passed. Every row of the declaration matched, with no finding.**

## The revision

`c28ff379ba40edb461cf5476c94968e228dcac03`, the merge commit of #1503 (its tree is the PR head dfd3f955f17a's tree; the
head merged main, the PDF highlight, into the question branch, the two ledgers resolved as proven unions). Citation on the
revision: CI 44898782078, cpt-studio 44898782091, secrets-scan 44898782114, all success, the same three in both views.
Held declarations over the range: none. The question path is byte-identical to 8ee7b906d, the head the paid pair (D379)
ran on.

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 12:16:35 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261121T121635Z.md` |
| preflight | 12:16:48-12:16:59 | exit 0, "baseline recorded; no blocking problem" | as declared: the quillmd-cpt vhost f816a27d... for 9151; 9151 active, 9150 idle, no port problem, no cpt-studio-web-next; co-tenants and app.quillmd.com/health/ as expected; nginx -t clean |
| image | 12:17:15-12:17:36 | exit 0, cpt-studio:c28ff379ba40 = sha256:64dc0913f57e | as declared: built from the cache, labelled with the revision; cpt-studio:0de2b5844857 kept |
| pre-app | 12:17:44-12:17:54 | PRE-APP PASS | as declared: dump 48 TABLE DATA (sha256 f929149d...), the restore migrated with cpt-studio:c28ff379ba40 applied nothing, the baseline equal to the declared one, jobs_active 0, no run reserved, sending or unknown, no reading job |
| app | 12:18:02-12:20:58 | exit 0 | as declared: migrate "No migrations to apply"; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS equal to the prediction key by key, its report note on the Fable tables' existing rows declared beforehand; the switch 9151 to 9150, the vhost f816a27d... to 259b895d..., HTTPS 200; the new worker coding live, effort max, 25 US dollar ceiling, 4 documents; the old web drained (0 connections, 130.7 s) and parked; RECOMPUTE_STATES changed {} (6 coded, 89 kept); availability 303 samples, 0 not 200, both releases seen; the replaced pair named (0de2b5844857's web and worker) |
| post-check after app | 12:21 | unexpected differences 0 | /health/ serves c28ff379ba40; co-tenants as expected |
| verify | 12:21:20-12:21:23 | exit 0, "installed c28ff379ba40 verified; co-tenants and app.quillmd.com unchanged" | as declared |
| view-only live check | 12:21:35-12:22:08 | pass | below |
| post-check after the live check | 12:22 | unexpected differences 0 | login_attempts 119 to 120: the check's one sign-in, as declared |

## The view-only live check

`highlight-20261120/install/hl_check.cjs` (sha256 ba96d6bc..., the declared copy) with the revision's `ops/walk.cjs`
against https://cpt.quillmd.com, as the review agent, on the two synthetic walk documents: 255e92ac (gi-02, a PDF) 15 of
15 quotes marked once, with both redraws judged; 6c450473 (gi-01, a text) 17 of 17. 21 GET requests and the sign-in and
sign-out POSTs, no other request, no page error. Its sign-out navigation was cut short (net::ERR_ABORTED) after the POST,
as in the rehearsal, and was judged by its outcome: GET /api/session answered 401. No real document was opened. The new
question format shows only on a new coding round, a paid request, so it was not exercised here; the paid pair proved it
on a restored copy (D379), and every stored encounter's customer view measured identical under the revision.

## Measured before the act (in the declaration)

The paid pair (D379); the refutation of the finished diff (rounds 1-3, round 4 docs only; written limit QL3-1); the
offline prediction (nothing applies, no table delta, no state change, every stored encounter's customer view identical
under the revision: 95 of 95); the rehearsal on a restored copy of live (the live check passing there) and the
switch-back rehearsal (no hazard, nothing closed, every encounter readable by the previous image).

## Rollback

Not needed. The 0de2b5844857 pair is parked and its image kept; the incident path is `switch-back` under the declaration
(a fresh preflight first). The pre-app dump (`pre-app-c28ff379ba40-*.dump`, 0600) stays with the receipts.

## Notes for the next release

- The sign-out navigation in hl_check was cut short in 3 of its last 7 runs (rehearsals and live); the session always
  ended (401). The tool judges the outcome; the page's own navigation racing the form submit is not a member-facing
  defect, but a later look at the sign-out page is worth an hour.
- The installer's INSTALL_COUNTS report calls the Fable tables' existing rows "a reinstall or a same-revision run": a
  first-install heuristic, declared this time; it should recognise an install over a Fable-schema revision.
