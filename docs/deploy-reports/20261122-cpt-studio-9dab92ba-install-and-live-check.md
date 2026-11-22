# CPT Studio's physician PDF report installed at cpt.quillmd.com (c28ff379ba40 to 9dab92ba0f98), and its authenticated download check

Session `738699b2`, 2026-11-22. Owner directions D387 (implement and install the approved physician PDF export) and
D388 (the PDF is the only report); declaration `docs/foundation/mutations/20261122-cpt-studio-physician-pdf-install.md`
(committed a4bd4c6272f5 at 01:13:41Z, merged in #1507 as ddb69890e0ce at 01:37:48Z). Every phase ran through
`scripts/run-ruled-mutation.sh` from the clean, detached act checkout `/opt/meddoc-pro/.worktrees/cpt-pdf-act-20261122`
(ddb69890e0ce, a descendant of the revision that changes nothing under `cpt-studio/` or the door). Receipts are in
`/home/claude/cpt-studio-install-20261023/`; the wrapper's logs and the check's evidence are in
`export-20261121/install/` (act-p-*.log, pre-app-p-9dab92ba0f98.log, baseline-p-after-*.txt, live-out/, live-scan/).

**Result: installed and verified, with the site serving throughout. The authenticated download check passed. Every row
of the declaration matched, with no finding.**

## The revision

`9dab92ba0f98a647b4fb5522e067560ba4e8afd8`, the merge commit of #1506 (its tree is the PR head c59bdb8bc196's tree:
main had not moved since the branch point). Citation on the revision: CI 44968552960, cpt-studio 44968552976,
secrets-scan 44968553012, all success, the same three in both views. Held declarations over the range: none (29 runtime
files, all under cpt-studio/; 19 declarations and reports name one, every revision they name an ancestor of the running
revision).

## The act, phase by phase

| step | when (UTC) | result | judged against the declaration |
|---|---|---|---|
| preflight-health-check | 01:38:17 | FIX-AND-GO (disk 89%) | not BLOCK; `docs/preflight-reports/preflight-20261122T013817Z.md` |
| preflight | 01:38:27-01:38:33 | exit 0, "baseline recorded; no blocking problem" | as declared: the quillmd-cpt vhost 259b895d... for 9150; 9150 active, 9151 idle, no port problem; co-tenants and app.quillmd.com/health/ recorded |
| image | 01:38:49-01:39:30 | exit 0, cpt-studio:9dab92ba0f98 = sha256:6e409ad596bc | as declared: 608,089,549 bytes, 7 of its 11 layers shared with cpt-studio:c28ff379ba40, labelled with the revision; the smoke gate (Django check, which loads the URL conf and with it the PDF code, ReportLab and the report fonts; the WSGI import) passed; cpt-studio:c28ff379ba40 kept |
| pre-app | 01:40:16-01:40:26 | PRE-APP PASS | as declared: dump 48 TABLE DATA (sha256 a5e23b595d51...), the restore migrated with cpt-studio:9dab92ba0f98 applied nothing, the baseline equal to the declared one, jobs_active 0, no run reserved or sending, the last audit event 80,959 s old |
| app | 01:40:37-01:43:38 | exit 0 | as declared: migrate "No migrations to apply"; UNRUNNABLE_STAGES stuck 0; V1_ROWS none; INSTALL_COUNTS equal to the prediction, its one note for the owner the declared one on the Fable tables' existing rows; S1 01:40:58 cpt-studio-web-next on 9151; S2 01:41:04 the old worker parked; S3 01:41:07 the vhost switched 9150 to 9151 (259b895d... to f816a27d...), `nginx -t` clean, https 200; S4 01:41:09 the new worker, coding live at effort max with the 25 dollar ceiling and 4 documents at once, as before; S5 the old web drained in 130.9 s with 0 open connections, stopped and parked; S6 RECOMPUTE_STATES 6 coded encounters, none changed, 89 kept. The installer's availability probe: 307 samples at 0.5 s, all 200, the releases seen c28ff379ba40 then 9dab92ba0f98; an independent probe at 2 s: 86 samples, all 200 |
| verify | 01:44:20-01:44:26 | exit 0, "installed 9dab92ba0f98 verified; co-tenants and app.quillmd.com unchanged" | as declared |
| post-check after app | 01:44:33 | unexpected differences 0 | /health/ serves 9dab92ba0f98; co-tenants as expected |
| authenticated download check | 01:44:56-01:45:12 | pass | below |
| live customer scan | 01:45:28-01:45:30 | pass | below |
| post-check after the checks | 01:45:37 | unexpected differences 0 | studio_exportartifact 6 to 11 and audit_events 1465 to 1470, as declared; login_attempts 121 to 123 (the two sign-ins, set aside by the comparison and as declared); decisions 63 and studio_codedecision 8 unchanged |

## The authenticated download check

`export-20261121/install/pdf_check.cjs` (sha256 ac2f1b5d...), with the revision's ops/walk.cjs (byte-identical to the act
checkout's, sha256 fc72207c...), against https://cpt.quillmd.com, signed in through the form as the review agent (an
ordinary member of the synthetic workspace), on the two synthetic walk documents of 2026-11-20:

| document | saved state | downloaded (PDF, pages) | compared with the saved state |
|---|---|---|---|
| 255e92ac (gi-02, a PDF) | 3 lines, none approved: a draft only | desktop draft (5), phone draft (5), the desktop draft again from Earlier downloads | every comparison true; the history copy equal to the stored bytes |
| 6c450473 (gi-01, a text) | 3 lines, L1 99214 approved 2026-11-20T15:45:25Z | desktop draft (6), desktop approved report (4), phone draft (6), the desktop draft again from Earlier downloads | every comparison true; the approved report carries APPROVED and not DRAFT, and holds 99214 only, without the two lines that have no saved decision (re-read independently with pypdf) |

Requests: 103 GET, 7 POST (the sign-in, the sign-out and the five reports); no decision, no upload, no request off the
origin; no violation, no page error. The phone width showed no sideways overflow. The five PDFs and the phone dialog
captures are kept, 0600, in `export-20261121/install/live-out/` (synthetic documents only).

Then `scan_pdfs.py` (sha256 24dfaee6...) with the revision's ops/scan_customer.py: 7 PDFs (with the two history copies),
0 hits. And `scan_live_p.sh` (sha256 284b183e...): the revision's customer scanner in its live mode, signed in as the
same member on the same two documents, GET only besides the sign-in and the sign-out: every check passed (34: the page
and its own scripts and styles, the session, the list and each encounter against the customer contract, each document's
original and view, every stored export of the two documents - the five new PDFs read as a reader sees them, and the
earlier TXT - scanned whole with its answer headers and none carrying X-Content-SHA256, every /ops/ and removed URL 404,
the sign-out proven); hits 0 on every surface.

## Measured before the act (in the declaration)

The full gate on the revision's tree; six refutation rounds (38, 39, 17, 22, 10 and 8 findings; the last round found no
high finding and no medium regression), every repair mutation-proven; the offline prediction on a fresh read-only dump of
live (no migration, every encounter's customer view identical, 9 eligible PDFs rendered deterministically with no vendor
string, no table delta); the rehearsal on a restored copy of live (the same download check with one approval and its
undo, both scans, exact table deltas) and the switch-back rehearsal (nothing closed, no state changed, the previous
image reading all 95 encounters and serving the new PDFs' stored bytes).

## Rollback

The previous pair (c28ff379ba40, image sha256:64dc0913f57e...) is parked with the image kept; the incident path is the
installer's `switch-back` (a fresh preflight, then act_p.sh switch-back with SWITCH_BACK_DECISION recorded), rehearsed.
The PDF exports made under the revision stay and the previous revision serves their stored bytes.

## Notes for the next release

- The rehearsal copy starts with an empty files volume, so a live-mode customer scan there fails its original and view
  checks with 409; on live they pass. Read those four checks as the copy's, or seed the copy's files volume first.
- The declaration PR runs CI and secrets-scan only (the cpt-studio workflow is path-filtered): wait for two runs, not
  three.
- The act checkout has no node modules; the download check ran the byte-identical walk from the feature worktree.
