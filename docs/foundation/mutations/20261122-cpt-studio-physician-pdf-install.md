# Prospective declaration: the CPT Studio physician PDF report at cpt.quillmd.com (c28ff379ba40 to 9dab92ba0f98), installed blue/green with the site kept serving: no migration, one new runtime dependency (ReportLab), drafts and approved reports as searchable PDFs built from saved data, and the PDF the only report made

Authority: the owner's direction of 2026-11-21 recorded verbatim, with this programme's interpretation, in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its section "Owner direction, 2026-11-21 — the physician PDF
export, implemented and installed", landed with the change in PR #1506) and a RULINGS.md row:

- D387: "Implement and install the approved CPT Studio physician PDF export ... Build a real searchable PDF using the
  encounter's saved data ... Make PDF the primary doctor-facing export and retain CSV as a secondary option ... Only saved
  accepted codes may appear in approved output. Keep provider names and technical logs out of customer-facing reports ...
  Follow the normal release process with rollback available. Continue through routine fixes until the installed export
  works". The session's recorded interpretation: a third export format inside the existing export system (no
  migration); TXT kept; nothing inferred (no patient identifier or service label exists, so neither is printed); the
  approval path proven on the rehearsal and live downloads limited to existing saved states; ReportLab 4.5.1 to the
  runtime requirements, the design's OFL fonts and a DejaVu fallback shipped with their provenance.

- D388: "OK ALSO I JUST WANT TO PROVIDE MY OFFICIAL pdf code report no txt and csv removed all ofthem and let ppl only
  downlaod our pdf report how do you think?" The session's recorded interpretation: new exports are PDF only (a TXT or
  CSV request is refused, 400); TXT and CSV files already made stay stored, listed and downloadable as records (deleting
  them was not asked for and would be the owner's class d); the PDF's character notes name CPT Studio's saved record,
  which keeps every character (refutation round 4); the live check also downloads the approved report of 6c450473, which already holds a saved approval.

It stands on the standing directions this install keeps:
- D358, "start it but dont crate the old system engine again": the change is plumbing and display. Nothing reads a note
  to decide, holds or changes a code; the coding review, its instructions, the decisions and the approval rules are
  untouched. A PDF is made from the same snapshot the TXT and CSV exports were made from.
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved).
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed; preflight not BLOCK; the
  act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it.

Revision to install: `9dab92ba0f98a647b4fb5522e067560ba4e8afd8`, the merge commit of PR #1506 (branch feat/cpt-studio-physician-pdf-export-20261121, head
`c59bdb8bc196e2a0d6e47b0565795f36d56f53ca`; the two trees are one: main had not moved since the branch point 113deb53c, so `git rev-parse` gives a8f620b473fa5eb1132a14328252fdf68d894f14 for both). It contains origin/main as of the merge. Image tag cpt-studio:`9dab92ba0f98`. Its citation, on
the revision: `CI 44968552960 success, cpt-studio 44968552976 success, secrets-scan 44968553012 success (all on 9dab92ba0f98)`. The PR head's citation: `CI 44966064395 success, cpt-studio 44966064398 success, secrets-scan 44966064405 success (all on c59bdb8bc; one earlier head, 2a7fc24aa, needed one re-run of CI's "Fresh application tests" for a timing test in rebuild/ops that this change does not touch, then passed)`. cpt-studio is not a required check; it is
required here.

It replaces the live revision c28ff379ba40edb461cf5476c94968e228dcac03 (image cpt-studio:c28ff379ba40, id
sha256:64dc0913f57ec27425b91fb1aed83d5aad94c17fef5779a810c8c821313d94f7, its web on 127.0.0.1:9150 since that install's
switch on 2026-11-21), installed under docs/foundation/mutations/20261121-cpt-studio-question-ids-install.md (PR #1504,
a46f1ed54b5c). That image is kept as the rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 --receipts /home/claude/cpt-studio-install-20261023`
(export-20261121/install/act_p.sh: the question release's act_q.sh with this release's names).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify.

The installer gives the web and the worker the same coder settings as the live pair (the revision's settings.py
defaults: effort max, the 25 US dollar per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-pdf-act-20261122). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase.

Not run: secrets, db, reference, passages, license-note, provision, operators, http-vhost, cert, https-vhost,
rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the
install.

Between c28ff379ba40edb461cf5476c94968e228dcac03 and the revision, these are byte-identical
(`git diff --quiet c28ff379ba40edb461cf5476c94968e228dcac03 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 -- <these paths>: exit 0, 2026-11-22T00:24Z, on the PR head whose tree the revision has`): the migrations (still 0016_fable_coding, the last), the coding path (studio/fable/, jobs.py, intake.py, state.py), decisions.py, storage.py, access.py, audit.py, views.py, the operator console (operator.py and its templates), the sign-in page, the pinned PDF library (studio/static/studio/lib), cptstudio/ (settings.py among it), ops/install.py and deploy/ (the Dockerfile). These change, and are named here: the export path (studio/exports.py; new: studio/physician_report.py, studio/physician_pdf.py and the fonts under studio/report_fonts/), api.py (the format refusal and the 503), customer.py (the name filter), models.py (a docstring only), the page (studio/static/studio/app.js, styles.css, templates/studio/index.html), requirements.txt and requirements.in (ReportLab 4.5.1, pillow 13.0.0, charset-normalizer 3.5.1; the dev pins likewise), ops/walk.cjs, ops/scan_customer.py, ops/dev_preview_server.cjs, ops/verification/ (the customer contract's and denylist's texts), the tests, and the docs (API.md, ARCHITECTURE.md, CORE-UX-DESIGN.md, ops/INSTALL.md); outside cpt-studio/, docs only (CPT-HARNESS-CHECKLIST.md, docs/foundation/RULINGS.md, docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, and the question-ids release's declaration and report).

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet c28ff379ba40edb461cf5476c94968e228dcac03 HEAD -- cpt-studio/studio/migrations cpt-studio/studio/storage.py cpt-studio/studio/intake.py cpt-studio/studio/jobs.py cpt-studio/studio/state.py cpt-studio/studio/access.py cpt-studio/studio/decisions.py cpt-studio/studio/operator.py cpt-studio/studio/views.py cpt-studio/studio/audit.py cpt-studio/studio/fable cpt-studio/studio/static/studio/lib cpt-studio/studio/templates/studio/login.html cpt-studio/studio/templates/studio/ops_base.html cpt-studio/studio/templates/studio/ops_encounter.html cpt-studio/studio/templates/studio/ops_index.html cpt-studio/cptstudio cpt-studio/ops/install.py cpt-studio/deploy`, exit 0;
- `git diff --name-only c28ff379ba40edb461cf5476c94968e228dcac03 HEAD -- cpt-studio/studio/migrations`, printing nothing;
- `git diff --name-only 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh c28ff379ba40edb461cf5476c94968e228dcac03 9dab92ba0f98a647b4fb5522e067560ba4e8afd8, 2026-11-22T00:54Z: the range's first-parent merges are #1506, #1505 and #1504; 29 runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 64 files) passed; 19 declarations and reports name a runtime file of the range, and every revision each names is an ancestor of the running revision; possibly held: 0`.

## Delta shipped (c28ff379ba40 to the revision)

**This is a TREE, not one change**, but its only runtime change is the physician PDF report: the range carries #1506
(this change: 8 commits) and #1504 and #1505 (the question-ids release's declaration and install report, docs only).

- Runtime, on the export path: a draft or an approved report is made as a searchable PDF (studio/physician_report.py,
  studio/physician_pdf.py; ReportLab 4.5.1 with the design's fonts bundled under studio/report_fonts/) from the same
  saved snapshot the earlier exports were made from, stored, and served exactly as stored. New TXT and CSV exports are
  refused (400); those already stored stay listed and download exactly as stored. api.py refuses any other format and
  answers 503, storing nothing, when a PDF cannot be made; models.py changes a docstring only. The export dialog
  (studio/static/studio/app.js, styles.css, templates/studio/index.html) offers one Download PDF in each group. The
  customer name filter (studio/customer.py) reads a Claude model named with its family or a short version, or a whole
  Claude model id, as "the system" whole; the shared denylist's rules are unchanged. No migration, no setting of the
  coder, no stored round re-read or re-coded: the coding engines, validation, approval rules, decisions and records are
  untouched.
- Ops: ops/walk.cjs downloads and reads the PDF reports and records its scan of them as skipped; ops/scan_customer.py
  reads a PDF as a reader sees it (the release's scan of the reports' wording and of the downloads' answers); the
  customer contract's and denylist's texts, the dev preview and their tests follow.
- Docs and records: API.md, ARCHITECTURE.md (how the PDF prints text, and its known limits after six refutation
  rounds), CORE-UX-DESIGN.md, ops/INSTALL.md; CPT-HARNESS-CHECKLIST.md (its physician PDF section); RULINGS.md and the
  CPT Studio rulings file (D387, D388).

## What members see after the install

- The export dialog offers one **Download PDF** in each group (Draft report, Approved report) and nothing else: TXT and
  CSV are no longer made. Files made before, TXT and CSV among them, stay listed under Earlier downloads with their
  format and download exactly as stored. The dialog says while a PDF is being prepared, says when it is ready, and on a
  refusal shows the reason and lets the member try again. A page left open from before the install still offers TXT
  and CSV; the server refuses them ("Choose a draft or an approved PDF report.") until the page is reloaded.
- The draft PDF (DRAFT · REVIEW REQUIRED on every page): every code line of the latest coding review with its status
  and any saved decision (who and when, UTC), its units and modifiers, the evidence with its locators, what still needs
  a decision and the documentation notes. The approved PDF: only lines whose current decision is approve, each with who
  approved it and when; an agent's approval says it is not clinical approval. Both are marked synthetic, not for billing.
- Text the coding review wrote that names a Claude model with its family ("Claude 3 Opus", "Claude Sonnet 4.5", also
  across a line break, a non-breaking space or an invisible character) now reads "the system" whole on the page and in
  the PDF, where it read "the system Opus" before; a family name alone, and clinical words such as the OPUS trial or a
  MED-EL SONNET 2 processor, are left as written. The denylist's rules are unchanged.
- Nothing else changes: the codes, the decisions, the approval rules, the questions, the viewer and the highlight. Every
  export already made stays listed and downloads exactly as stored.

## Cost and time

No paid request. The image build reuses the cached apt layer (the Dockerfile is unchanged) and rebuilds the pip layer,
because requirements.txt gains ReportLab 4.5.1, pillow 13.0.0 and charset-normalizer 3.5.1 (fetched from PyPI during the
build; the revision's test image cpt-studio-test:9dab92ba0f98 (sha256:822bc99e376e..., built the same way) shares 7 of its 11 layers with the live image cpt-studio:c28ff379ba40; its pip layer is 118 MB). The app phase takes about 3 minutes (the blue/green switch; the worker's stop bound).

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): on the PR head c59bdb8bc196e2a0d6e47b0565795f36d56f53ca (its tree is the revision's tree: main had not moved since the branch point), with the CI interpreter's version line (Python 3.12): Django suite 601 tests OK (1 skipped), ops 532 OK, verification 35 OK, walk node tests 95 of 95, pip-audit "No known vulnerabilities found"; exit 0 (export-20261121/gate-final.log).

**The refutation of the finished diff** (it decides what a doctor-facing report says): six rounds of independent lenses over the finished diff, each told to refute, each in a sealed copy of the tree with no write access to the author's files, every finding verified before it was believed: round 1 38 findings, round 2 39 (2 high), round 3 17, round 4 22 (1 high), round 5 10 (1 high: the walk claimed a scan of the PDF downloads it no longer ran), round 6 8 (no high, no medium regression: the passes stop there). Every repair of every round is proven by a mutation its test kills, each file restored byte-identical by sha256; the residuals are recorded as known limits in ARCHITECTURE.md (export-20261121/refute-r2..r6-findings.md).

**Offline predictions** (export-20261121/install/predict_p.sh on a throwaway restore of a fresh read-only dump of live,
in the revision's test image): run 2026-11-22T00:54:33Z on a fresh read-only dump of live (taken 00:54:36Z; 48 tables hold data), restored as cptg_hpred_20261122t005433z on gi4-cpt-test-pg and dropped on exit with its files volume: migrate in the candidate image applied nothing (still 16 migrations, 0016_fable_coding the last); every encounter's customer view built by the installed and by the candidate image, 95 and 95, 0 errors, 0 differing; UNRUNNABLE_STAGES stuck 0; RECOMPUTE_STATES 6 coded encounters, none changed, 89 kept; every draft and approved physician PDF the export rules allow, built from exports.snapshot and rendered in the candidate image without storing anything: 9 rendered (181 not ready, 0 errors), 4 to 11 pages, a second render byte-identical for 9 of 9, 0 vendor or model strings in any printed field, no character outside the body font; no table delta; encounter states awaiting_answer 2, extraction_failed 1, needs_clarification 47, no_codes 4, ready 2, ready_for_review 8, reviewed 31; the two walk documents: 255e92ac ready (a draft can be made, no approved report: 3 lines, none approved), 6c450473 reviewed (a draft and an approved report: 3 lines, 1 approved) (export-20261121/install/predict-p-run2.txt).

**The rehearsal on a restored copy of live**: rehearse_j.sh setup at 2026-11-22T00:56:32Z on a fresh read-only dump of live (taken 00:56:35Z) restored as cptg_jreh_20261122t005632z on gi4-cpt-test-pg, the revision's test image serving on 127.0.0.1:9371 with every provider mode and coding disabled (migrate applied nothing; 95 encounters). pdf_check.cjs as the review agent on 255e92ac and 6c450473, with --rehearsal-approve 255e92ac L1 43239 (approved through the API, the approved PDF checked, the approval undone): ok; 6 PDFs (255e92ac: the desktop and phone drafts, 5 pages, and the approved report after the rehearsal approval, 4 pages; 6c450473: the desktop and phone drafts, 6 pages, and the approved report, 4 pages), every comparison with the saved state true, the downloads from Earlier downloads equal to the stored bytes, the phone width without sideways overflow; 118 GET, 8 POST (the sign-in and sign-out, the reports, the approval and its undo), no violation, no page error. scan_pdfs.py: 8 PDFs (with the two history copies), 0 hits. scan_live_p.sh: 0 hits on every surface (JSON, headers, files, the page's scripts and styles); all 16 report checks passed (every stored export of the two documents, the earlier TXT among them, read and scanned, none with X-Content-SHA256); the /ops/ and removed URLs 404; the sign-out proven. Its only failures were the 4 original and view checks, answered 409 because the copy's files volume starts empty (testinst/stack_j.sh mounts a new cptg-files volume; no original is copied); live holds the originals. Table deltas, exactly: studio_exportartifact +6, studio_auditevent +8 (6 export.created, 2 decisions), studio_codedecision +2 (the rehearsal approval and its undo, made only on the copy), studio_loginattempt +2 (the two sign-ins); nothing else (export-20261121/install/reh3-*).

**The switch-back rehearsal on that copy**: rehearse_j.sh switchback c28ff379ba40 on the same copy after those checks: the stack stopped; the candidate's UNDO_HAZARDS_READ none, TOUCHED_SINCE_READ the two walk documents, CLOSE_STAGES closed 0 (no round cancelled or failed), CODING_MADE the 6 coded encounters; the installed image's UNRUNNABLE_STAGES stuck 0 before and after, PUT_BACK_STATES 6 encounters, none changed; the installed image's own API read as the customer: the list 200 and all 95 encounters 200; forward again, RECOMPUTE_STATES none changed; encounter states identical throughout; rounds done=6. The installed image also serves the revision's PDF exports: all 6 answered 200 as application/octet-stream with their .pdf name and the stored bytes (sha256 equal), no hash header, and an encounter's list names them (3 PDF of its 5 reports) (export-20261121/install/reh3-switchback.txt, reh3-prev-download.txt).

## Baseline (read-only, `2026-11-22T01:12:38Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_p.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts and states only, never a document, response or credential):

    bash /home/claude/cpt-studio-completion-20261106/gemini-migration/install-judge/live_baseline_j.sh
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:c28ff379ba40 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

    read_at 2026-11-22T01:12:38Z
    transaction_read_only on
    encounters 95
    revisions 96
    source_files 89
    contexts 106
    routing_runs 116
    provider_runs 299
    provider_runs_sent 263
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1465
    reports 209
    jobs 659
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 121
    reference_sources 2
    reference_facts 34665
    studio_migrations 16
    studio_migration_last 0016_fable_coding
    studio_providerexchange 264
    studio_toolcall 173
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 29
    studio_memberanswerrevocation 6
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_clarification.answer_id present
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_memberanswer.question present
    column studio_reportartifact.audience present
    member_answers_standing 23
    member_answers_by_value cannot_confirm 17
    member_answers_by_value not_documented 12
    run_participant anthropic appraisal succeeded 4
    run_participant anthropic coding_checker succeeded 6
    run_participant anthropic coding_reader succeeded 6
    run_participant anthropic interpretation succeeded 3
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 44
    run_participant astra peer_review succeeded 46
    run_participant fable independent succeeded 45
    run_participant fable peer_review failed 1
    run_participant fable peer_review succeeded 41
    credits_sum 4.452079999999999826
    usage_keys anthropic cache_creation,cache_creation_input_tokens,cache_read_input_tokens,fallback_credit,inference_geo,input_tokens,iterations,output_tokens,output_tokens_details,server_tool_use,service_tier,speed
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state awaiting_answer 2
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 2
    encounter_state ready_for_review 8
    encounter_state reviewed 31
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 6
    run anthropic coding_reader succeeded t f 6
    run anthropic interpretation succeeded t f 3
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 7
    run astra independent succeeded t f 37
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 44
    run corti primary not_sent f f 4
    run corti primary succeeded f t 13
    run corti primary succeeded t f 81
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 7
    run fable independent succeeded t f 38
    run fable peer_review failed t f 1
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 39
    job analyze succeeded 89
    job appraise succeeded 3
    job assess succeeded 186
    job astra cancelled 3
    job astra succeeded 45
    job astra_peer succeeded 46
    job code succeeded 6
    job extract succeeded 90
    job fable cancelled 4
    job fable succeeded 45
    job fable_peer cancelled 1
    job fable_peer succeeded 41
    job interpret succeeded 3
    job predict succeeded 94
    job question succeeded 1
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit decision.recorded 2026-11-21T03:11:07Z 79291
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-events@3 6
    assessments_by_engine cpt-studio-validation@10 57
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6
    assessments_by_engine cpt-studio-validation@9 23
    contexts_by_version gemini-context@2 3
    contexts_by_version gi-context@1 12
    contexts_by_version gi-context@2 26
    contexts_by_version gi-context@3 19
    contexts_by_version gi-context@4 35
    contexts_by_version gi-context@5 11
    current_context_by_version gemini-context@2 3
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version gi-context@5 11
    current_context_by_version none 7
    routing_by_version gemini-routing@2 3
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@11 8
    routing_by_version gi-routing@12 11
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12
    studio_eventinventory 3
    studio_interpreterhold 0
    studio_interpreterholdrelease 0
    studio_providerhold 0
    studio_providerholdrelease 0
    column studio_assessment.event_inventory_id present
    column studio_assessment.interpretation present
    column studio_encountercontext.earlier_assessment_id present
    column studio_encountercontext.event_inventory_id present
    column studio_eventinventory.appraisal_run_id present
    jobs_reading appraise succeeded 3
    jobs_reading interpret succeeded 3
    jobs_reading question succeeded 1
    runs_interpreter anthropic appraisal 4
    runs_interpreter anthropic interpretation 3
    assessments_new_path 6
    contexts_new_path 3
    decisions_on_current_assessments approve 52 32
    decisions_on_current_assessments reinstate 1 1
    decisions_on_current_assessments reject 6 6
    decisions_on_current_assessments revoke 2 1
    studio_codinground 6
    studio_codinganswer 0
    studio_codedecision 8
    studio_exportartifact 6
    jobs_code succeeded 6
    runs_coding coding_checker succeeded 6
    runs_coding coding_reader succeeded 6
    interpreter_holds_standing 0
    --- cotenants
      🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-worker 64dc0913f57e Up 13 hours 8000/tcp
    cpt-studio-web 64dc0913f57e Up 13 hours (healthy) 127.0.0.1:9150->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 7 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:64dc0913f57ec27425b91fb1aed83d5aad94c17fef5779a810c8c821313d94f7 c28ff379ba40edb461cf5476c94968e228dcac03

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for 9150
  (sha256 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c); 9150 held by cpt-studio-web alone and 9151
  free; no cpt-studio-web-next; co-tenant routing and https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`9dab92ba0f98`, built from git archive of the revision's cpt-studio/ and labelled
  with the revision. Expected from the test image built the same way: 7 of 11 layers shared with cpt-studio:c28ff379ba40 (the base and the apt layer), about 608 MB (608,089,549 bytes against the live image's 572,411,319: ReportLab, pillow and the bundled fonts); its id differs from the test image's, whose tag and labels are not the installer's. The image phase's WSGI-import gate now also imports ReportLab and loads the
  report fonts (physician_pdf registers them at import), so a broken library or a missing font refuses the image.
  cpt-studio:c28ff379ba40 is kept.
- **Before app, read-only on the database** (pre_app_p.sh): one `pg_dump -Fc` through the database container's own
  pg_dump in a read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the revision's
  image, where nothing applies; the baseline re-read equals the declared one, with no job active, no run reserved or
  sending, and no audit event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_p.sh's app phase requires it.
- **app (the blue/green switch):** **migrate applies nothing**; UNRUNNABLE_STAGES finds none; V1_ROWS none;
  INSTALL_COUNTS as the prediction (its report again notes the Fable tables' existing rows); S1 cpt-studio-web-next starts
  on 127.0.0.1:9151 and answers /health/ with the revision; S2 the old worker parked; S3 the vhost's proxy_pass switched
  127.0.0.1:9150 to 127.0.0.1:9151 (sha256 259b895d... to
  f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65), `nginx -t` clean, graceful reload,
  https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new worker starts with the coding
  step live, as the live worker does; S5 the old web drained, stopped and parked; S6 RECOMPUTE_STATES changes nothing (predicted: 6 coded encounters, none changed, 89 kept). The
  receipt names the replaced pair (c28ff379ba40's web and worker), which a switch-back returns to.
- **verify:** nothing changes.

**Database deltas after app, against the baseline:** none from the install: every count and every encounter's stored
state unchanged. Rows written by members in the window are their own and are named if they appear.

## After the install: the authenticated download check (ordinary use, not a phase)

export-20261121/install/pdf_check.cjs (sha256 ac2f1b5decd3a5e3ed829f04a7371d654d2d74e010a8396e2eba14b4c51b6dae), using the revision's ops/walk.cjs, against
https://cpt.quillmd.com with the review-agent account (an ordinary member of the synthetic workspace), on the two
synthetic walk documents of 2026-11-20 (255e92ac, gi-02, a PDF; 6c450473, gi-01, a text). It signs in through the form and
for each document reads the saved state as that member (GET /api/encounters/<id>), opens the export dialog and presses
Download PDF: on a desktop viewport (the draft, and the approved report where the saved state allows one: 6c450473 has
one current approval, 255e92ac none), then at phone width after a reload (the draft), then after another reload downloads
the desktop draft again from Earlier downloads. Every file is read with the walk's PDF reader and compared with the saved
state (codes in order, only current approvals in an approved report, units, modifiers, quotations, decisions with their
reviewer and UTC time, status and page numbering on every page); the stored copy is fetched again and compared byte for
byte. Each saved PDF's wording is then scanned by export-20261121/install/scan_pdfs.py (sha256 24dfaee6d6d9eceb21a32fdf93f35b26107eae421c3eabfbe2513ed87ac37daa) with the
revision's ops/scan_customer.py (scan_pdf: read as a reader sees it, only the printed quotations of the document set
aside); it reads files and writes no row. Requests: GET and HEAD, the sign-in and sign-out POSTs, and POST
/api/encounters/<those two ids>/reports; anything else, or a request leaving the origin, fails it. No decision is made,
no document is uploaded, no real document is opened. Its database rows, exactly: studio_exportartifact +5 (255e92ac: the
desktop draft and the phone draft; 6c450473: the desktop draft, the desktop approved report and the phone draft),
studio_auditevent +5 (export.created, one per report), studio_loginattempt +1 (the sign-in); nothing else. The export
rows are immutable and stay, listed as the review agent's downloads.

Then export-20261121/install/scan_live_p.sh (sha256 284b183e527bcd9d5e3f312610e0605533f134b1ba8959cfb515d9337e8ffad7) runs the revision's own customer scanner,
ops/scan_customer.py in its live mode, signed in as the same member on the same two documents: the page and its own
scripts and styles, the session, the list and each encounter against the customer contract, each document's original
and view (status and headers only), every stored export of the two documents - the new PDFs and the earlier TXT and CSV -
scanned whole with its answer headers (no X-Content-SHA256), every /ops/ and removed URL (each 404), then the sign-out
proof (refutation round 6, R6-2-1: the walk does not scan the downloads' answers; this does). GET requests only, plus the
sign-in and sign-out POSTs. Its database rows, exactly: studio_loginattempt +1 (the sign-in); nothing else (a download
writes no row). The two checks together: studio_exportartifact +5, studio_auditevent +5, studio_loginattempt +2.

## Must not change

Every encounter and every row of every table apart from the check's rows above; the accounts, memberships, workspace,
decisions, coding rounds, reference sources, facts and passages; the database container and its volumes;
/etc/cpt-studio/; the co-tenants' HTTP answers and https://app.quillmd.com/health/; every other nginx vhost; every image
(nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_p.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the counts as declared, the switch
applied and https://cpt.quillmd.com/health/ serving the revision; verify exit 0. After app: post_check_p.sh against
this declaration's deltas; scripts/check-cotenants.sh; then the download check and post_check_p.sh again with its rows.

## Rollback per phase, and its limits

- preflight, verify: nothing to undo.
- image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_p.sh switch-back with SWITCH_BACK_DECISION recorded). The c28ff379ba40 pair
  returns with its own modes. Both revisions share the schema, so no coding job is closed and no state changes
  (rehearsed on a restored copy: nothing closed, no state changed, the installed image reads all 95 encounters and serves the PDF exports' stored bytes). PDF exports made under the revision stay (immutable): the previous revision lists them
  and serves their stored bytes as application/octet-stream with their .pdf name (rehearsed). A page of the revision left
  open across a switch-back still offers only Download PDF, which the previous server refuses; after a reload the
  previous revision's page offers TXT and CSV again (written limit).
- The receipts, the pre-app dump and the images stay.

## What is not claimed

- Any clinical coding correctness: the PDF prints the saved codes and decisions; it decides nothing.
- Right-to-left scripts in visual order: they print in stored order, and the report says so where they occur.
- Characters neither report font draws: they print in their compatibility form or as U+FFFD, and the report says so.
- That text the coding review wrote never names machinery (a request id, a cost, a token count): the PDF prints it as
  the page does; the customer scanner flags it (written limit, as for every customer surface).
- Past the known limits written in cpt-studio/ARCHITECTURE.md and API.md for the physician PDF.

## Stop conditions

- Any phase exiting non-zero.
- A receipt or reading that differs from this declaration: a difference not declared here is THE finding, whatever its
  explanation.
- migrate applying anything.
- An encounter's stored state changing in app.
- The citation not success in both views.
- A held declaration found.
- Preflight BLOCK, or the installer's preflight refusing.
- The door's ceiling reached.
- A co-tenant's or app.quillmd.com's answer changing.
- The download check failing: judged, then reported. A defect found there is fixed under D358 and installed under a new
  declaration, or the site is switched back. It is never patched in place.
