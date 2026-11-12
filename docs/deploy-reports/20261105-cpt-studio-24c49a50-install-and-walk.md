# Install record: CPT Studio core repair at cpt.quillmd.com, 24c49a5032d5 (2026-11-05), and its first acceptance walk

Evidence written after the act, judged against its declaration:
`docs/foundation/mutations/20261104-cpt-studio-core-ux-install.md` (landed by PR #1467). The decision recorded after the app
phase was landed by PR #1468, before the next phase ran. Receipts are in `/home/claude/cpt-studio-install-20261023`, the live
install's own directory. Session a12d8fb3.

## Installed

Revision `24c49a5032d5bb0185e5efda08ebe71f54a2845f` (the merge commit of PR #1466; it carries PR #1465). Image
`cpt-studio:24c49a5032d5`, `sha256:5ac7981790d7…`. It replaces `41e03656df61`, which is kept as the rollback image.
`https://cpt.quillmd.com/health/` serves `{"status": "ok", "service": "cpt-studio", "data_mode": "synthetic-only",
"release": "24c49a5032d5bb0185e5efda08ebe71f54a2845f", "database": "ok"}`.

| phase | when (UTC) | result |
|---|---|---|
| preflight | 00:29 | ok |
| image | 00:30 | ok. The apt, user, requirements and pip steps were CACHED. The `dpkg-query` lists of the old and new images (166 packages) are identical. pypdf is 6.21.2 and the image runs as user 10150 |
| pre-app dump | 00:30 | `pre-app-24c49a5032d5-20261105T003041Z.dump` (0600), with 34 TABLE DATA entries. It is kept until a separate, recorded decision removes it |
| app | 00:33 | ok. migrate applied exactly 0009 to 0012. The switch went from port 9150 to 9151, and the vhost sha256 from `259b895d…` to `f816a27d…`. Availability: 301 samples, 0 not 200, releases 41e03656df61 then 24c49a50. Drain 130.6 s. states_recomputed `{"encounters": 49, "changed": {}}`. No leftover container |
| decision after app | 00:35 | Committed as `2f3b0009` and merged as PR #1468 before the next phase (finding 1 below) |
| passages, license-note | 00:58 | ok; no-ops (`imported: 0`) |
| operators | 00:59 | ok. ops-agent (agent) and platform-operator (human) were created, each with an operator grant and no membership: users 3 to 5, operator grants 0 to 2, memberships +0. No credential value was printed |
| verify | 00:59 | ok |
| reassess (Mara) | 01:00 | The dry run queued 0 jobs. The real run queued 1 job (key ending `:c:680cfe8dea28`). Provider runs, exchanges and tool calls +0. Mara now reads ready_for_review, with 43239, 45380 and 45385 selected and ready and 0 open questions |

The demo kept serving: no maintenance page was put up at any point. The app phase recorded 301 availability samples of the public /health/ across the switch, none of them other than 200. Outside the switch, availability rests on spot reads, which is a lesser claim.

## Findings against the declaration

1. **`studio_workerbeat` holds 1 row where the declaration said the five new tables are empty.** It is the new worker's
   own heartbeat (one row per worker name, carrying no document data). The app phase was stopped and diagnosed
   read-only, and the decision was recorded and landed (PR #1468) before the next phase ran.
2. **The reassessment's derived rows were not enumerated.** The declaration named "assessments +1, audit
   'assessment.refreshed' +1". The real run also wrote what an assessment always writes beside itself: routing_runs +1,
   proposals +12 (3 selected and 9 alternatives, the count the offline prediction showed), and audit `assessment.created`
   +1. No provider activity: provider runs, exchanges and tool calls +0. A declaration that names an assessment should
   name its routing run, its proposals and its audit pair. The next declaration does.

## The first acceptance walk (01:02:12 to 01:04:06Z)

`ops/verify_browser.cjs` ran through review-agent, with ops-agent beside it. The document was the held-out fresh-f2
(sealed 2026-11-04T13:29:08Z, with expectations written before unsealing). Encounter `6798b4c4-d457-4073-8d6a-3d45a2cd2683`.

- **The workflow worked end to end:**
  - the upload was acknowledged;
  - the reload while processing kept the same encounter and jobs;
  - Stop was requested 5.5 s after the upload (HTTP 200), and the panel read "Processing stopped" with its steps, the
    notice and Resume;
  - Resume (HTTP 201) ran to "Results ready";
  - 45385 and 45380 were ready, each bound to its own lesion, as the author expected before unsealing;
  - 45380 was approved at 390x844 with XS and 45385 at 1440x1000 (each HTTP 201), as agent-executed synthetic reviews;
  - after a reload every decision persisted;
  - the draft and approved TXT and CSV downloads were made.
- **The walk exited 1:** 145 of 156 assertions passed, with 7 hard failures, 2 soft warnings and 1 skip. Diagnosed
  against the screenshots, the served JSON and the database (read-only), six were the walk's own expectations and one was
  the page's:

| check | cause | whose |
|---|---|---|
| `stop.leave_note` | the stopped panel says nothing about leaving, though the server serves `can_leave` for every state and the directive (section 5) asks the page to make it clear when the user can leave and return; a failed panel has the same gap | **the page's** |
| `stop.message` | the served message is the error's own sentence, which the page says in the notice and not in the head (by design); the walk read only the head | the walk's |
| `progress.idle.steps`, `.message`, `.leave_note` | a finished document is one compact line, its title and the time it took (by design); the walk held it to the whole panel's contract | the walk's |
| `provenance.models`, `provenance.trace` (and soft `returned_models`) | Corti's coding API names no model (its response carries codes, candidates and usageInfo only); the walk asked one of it | the walk's |
| soft `upload.client_key` | Playwright serves no multipart body that holds a file; the encounter stored its key, and the server stores one only when the page sends it | the walk's |

- **The download check** (`ops/verify_downloads.py`) passed 110 of 110 checks on the four real downloads. The approved
  CSV and TXT list exactly 45380 (XS) and 45385, with units as persisted, each approver and its kind, the
  agent-executed synthetic review label, and every quotation an exact slice and a supporting passage.
- **The customer scan** (`ops/scan_customer.py --all`, GET only, 50 encounters) found no provider identity. It made 5
  hits, all stored records rather than system output:
  - three decision notes typed on 2026-11-03 by the earlier acceptance-reviewer walk (interpretation 63), which say in
    their own words that they are a "session-made synthetic acceptance-test approval, not a human review (CPT Studio
    harness live walk)";
  - one filename chosen at upload on 2026-10-26 (`gi-10-ercp-sphincterotomy-stone-extraction.txt`), in its body and its
    Content-Disposition header.

  All are preserved as records.
- **Counts against the declared bounds** (SELECT only, before and after):
  - provider runs +5 of at most 5, each sent once;
  - provider exchanges +7 of at most 16, and tool calls +4;
  - jobs +10 of at most 11 (one, Astra's, cancelled by the Stop before it sent anything);
  - assessments +2 of at most 3;
  - second-review runs +0; finding confirmations 0;
  - decisions +2 and reports +4 (the HTTP 201s); member answers +0; jobs_active back to 0;
  - nothing on Mara: 0 decisions since the walk began.
- **Measured usage:**
  - Corti: 0.048752 credits;
  - Astra: 12,457 input and 1,465 output tokens (its first reading 8,553 / 1,402; its peer review 3,904 / 63);
  - Fable: 38,123 input and 3,267 output tokens (17,171 / 2,717; 20,952 / 550);
  - no US-dollar estimate is recorded by the system for any run (`estimated_cost_usd` null).

The page gap and the six walk expectations were fixed in PR #1469, and the fix was installed with a second walk under
`docs/foundation/mutations/20261105-cpt-studio-leave-note-install.md`.
