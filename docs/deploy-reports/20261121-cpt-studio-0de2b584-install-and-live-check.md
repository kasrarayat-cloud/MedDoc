# CPT Studio's PDF quote highlight installed at cpt.quillmd.com (7dd813005077 to 0de2b5844857), and its view-only live check

Session `738699b2`, 2026-11-21. Owner direction D368 ("ok do highlight"); declaration
`docs/foundation/mutations/20261121-cpt-studio-pdf-highlight-install.md` (committed 51fde5d69489 at 09:32:26Z, merged
in #1501 as a141c2ea85d7 at 10:07:59Z). Every phase ran through `scripts/run-ruled-mutation.sh` from the clean, detached
act checkout `/opt/meddoc-pro/.worktrees/cpt-highlight-act-20261121` (a141c2ea85d7, a descendant of the revision that
changes nothing under `cpt-studio/` or the door). Receipts are in `/home/claude/cpt-studio-install-20261023/`; the
wrapper's logs are in `highlight-20261120/install/` (act-h-*.log, pre-app-h-*.log, baseline-h-after-*.txt).

**Result: installed and verified. The live check passed. Every row of the declaration matched but one, the
installer's own "item for the owner" note, recorded below as a finding with no data effect.**

## The revision

`0de2b5844857daf9593663f5f730e3ebc7a65130`, the merge commit of #1500 (its tree is the PR head d7eedf5f9629's tree).
Citation on the revision: CI 44887491312, cpt-studio 44887491304, secrets-scan 44887491306, all success, the same three in
both views. Held declarations over the range: none (5 name a runtime file of the range; each names only shipped
revisions).

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 10:08:35 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261121T100835Z.md` |
| preflight | 10:08:55-10:09:06 | exit 0, "baseline recorded; no blocking problem" | as declared: the quillmd-cpt vhost 259b895d... for 9150; 9150 active, 9151 idle, no port problem, no cpt-studio-web-next; co-tenants and app.quillmd.com/health/ as expected; nginx -t clean |
| image | 10:09:24-10:09:45 | exit 0, cpt-studio:0de2b5844857 = sha256:83283df751fa | as declared: built from the cache in 18 s, labelled with the revision, the conversion smoke passed; cpt-studio:7dd813005077 kept |
| pre-app (first run) | 10:10:01 | stopped short, no PRE-APP PASS | not a pass, so app could not run: a defect of the wrapper, below |
| pre-app (TAG r2) | 10:11:13-10:11:23 | PRE-APP PASS | as declared: dump 48 TABLE DATA (sha256 a295c8d6...), the restore migrated with cpt-studio:0de2b5844857 applied nothing, the baseline equal to the declared one, jobs_active 0, no run reserved or sending or unknown, no reading job, last audit 25216 s old |
| app | 10:11:33-10:14:34 | exit 0 | as declared but for one note: migrate "No migrations to apply"; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS equal to the prediction key by key (encounters 95, 6 coded; jobs, runs, tables, unknowns); S1 at 10:11:53 web-next on 9151; S2 old worker parked; S3 at 10:12:03 the vhost 259b895d... to f816a27de9e6... (the declared value), HTTPS 200; S4 the new worker, coding live, effort max, 25 US dollar ceiling, 4 documents; S5 the old web drained (0 connections, 130.9 s) and parked; S6 RECOMPUTE_STATES changed {} (6 coded, 89 kept); availability 309 samples, 0 not 200, both releases seen; the replaced pair named (7dd813005077's web and worker) |
| post-check after app | 10:15:31 | unexpected differences 0 | /health/ serves 0de2b5844857; co-tenants as expected |
| verify | 10:15:41-10:15:48 | exit 0, "installed 0de2b5844857 verified; co-tenants and app.quillmd.com unchanged" | as declared; web port 9151, image sha256:83283df751fa |
| view-only live check | 10:16:03-10:16:34 | pass | below |
| post-check after the live check | 10:16:44 | unexpected differences 0 | login_attempts 118 to 119: the check's one sign-in, as declared |

## The view-only live check

`highlight-20261120/install/hl_check.cjs` (sha256 ba96d6bc..., the declared copy) with the revision's `ops/walk.cjs`
against https://cpt.quillmd.com, signed in as the review agent through the form, on the two synthetic walk documents:

- 255e92ac (gi-02, a PDF with real Fable citations): the viewer drew it in the page; 15 of 15 quotes marked once, each
  judged by the walk's own Node reading of the PDF; the marks judged again after Zoom in and Fit width (2 of 2).
- 6c450473 (gi-01, a text): 17 of 17 quotes marked once.
- 21 GET requests and the sign-in and sign-out POSTs; no other request, none leaving the origin; no page error; signed
  out cleanly. No real document was opened.

## Findings

1. **The pre-app wrapper stopped silently on the expected path (fixed before app).** `pre_app_h.sh` read the restore's
   migrate output with `grep 'Applying ...'` under `set -o pipefail`: on a code-only release grep finds no line, exits 1,
   and errexit ended the script without a word; its exit trap then dropped the throwaway restore. The log ended short of
   PRE-APP PASS, so `act_h.sh` would have refused app, as designed. The migrate itself had answered "No migrations to
   apply" (the previous release applied 0016, so the path was never exercised). Fixed in the wrapper (the empty result
   tolerated; any unnamed early exit now prints a PRE-APP STOP line); the rerun under TAG r2 passed. Nothing on live was
   touched by either run (both read-only).
2. **The installer's app receipt carried one "item for the owner" the prediction did not show.** Its INSTALL_COUNTS
   report reads the Fable coding tables' rows (CodeDecision 8, CodingRound 6, ExportArtifact 6 - the counts the
   prediction read, identical) as "a reinstall or a same-revision run", the wording of a check written for the first
   install over a revision before those tables. This install is neither: it is the first over a revision that already
   carries them. No row changed (both post-checks: 0 unexpected differences). Recorded, not acted on; the installer's
   check should recognise an install over a Fable-schema revision in a later release.

## Measured before the act (in the declaration)

The offline prediction (nothing applies, no table delta, no state change), the rehearsal on a restored copy of live
(the live check passing there; its first run failed honestly because the copy's files volume held no originals, and
both viewers said the document could not be downloaded), the switch-back rehearsal (no hazard, nothing closed, every
encounter readable by the previous image), and the owner's six PDFs offline (264 citations, 240 marked once, 24 more than
once, 0 not found).

## Rollback

Not needed. The 7dd813005077 pair is parked and its image kept; the incident path is `switch-back` under the
declaration (a fresh preflight first). The pre-app dumps (`pre-app-0de2b5844857-*.dump`, 0600) stay with the receipts.

## Next

The question-ids fix (D372/D379, branch feat/cpt-studio-question-ids-20261120 at 8ee7b906d) goes to its own PR,
declaration and code-only install.
