# Prospective declaration: CPT Studio's Fable coding build at cpt.quillmd.com (e426c747c7b7 to 7dd813005077), installed blue/green with the demo kept serving, migration 0016 applied (four new tables, additive only), the coding step live at effort max under a 25 US dollar per-document ceiling and 4 documents at once, nothing re-coded

Authority: the owner's directions of 2026-11-20, each recorded verbatim with this programme's interpretation in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its 2026-11-20 sections) and a RULINGS.md row:

- D351: "0 line from old code also fable should be take too old code palce completely idont wanna see any single old
  code that cause us a patching or fixing remove it ... i dont want you to build a system by code i want you to use
  agent in order to use api report me what is your plan before procced";
- D352: the plan approved - "i approve all of your decison" and "you have my full permission to run the new design tho"
  (Claude Fable 5.2 reads the original file twice, as the reader and as an independent checker; Corti, Astra and the
  earlier Fable 5.1 participant dropped; tested on his de-identified PDFs first);
- D358: "start it but dont crate the old system engine again dotforget pls" (every fix is plumbing only: no rule reads
  the note's meaning or holds or changes a code Fable returned);
- D360: "ok gotta sleep make sure everthing run until installation to live i wanna see my new desgin tomarrow" - the
  install is authorized without asking again, under the conditions this session recorded with it: no unresolved
  critical or high finding, every suite green, CI green on the merged commit, this declaration committed before the
  act, the pre-app rehearsal on a restored copy of live passed, preflight not BLOCK; the act only through
  scripts/run-ruled-mutation.sh; a live walk with the two synthetic walk documents afterwards; a report either way;
- D361: "make sure you terst that pdf link share file they are more important" - his de-identified PDFs were run end to
  end through this revision's image on the test server before this declaration (below; never on the live site).

They stand on the standing directions this install keeps: the 2026-10-23 directive cited in
docs/foundation/mutations/20261023-cpt-studio-install.md (a protected synthetic demonstration; provider credentials
server-side; app.quillmd.com and unrelated services preserved); the per-document ceiling of 25 US dollars and 4 at once
(D326, counted per version of a document, D329 (4)); and "dont worry about the api budget ill take care of it by my
self" (D331: the Anthropic account is his to manage). The integration and deployment owner is session `738699b2`.

CPT Studio stays standalone and synthetic-only (Workspace.synthetic_only, the upload attestation, the banners and the
live gate unchanged). No purchase, agreement, new key or payment change is part of this act: the coding step uses CPT
Studio's existing Anthropic credential, /etc/cpt-studio/anthropic-credentials.env (10150:10150 0400, copied from the
owner's source under docs/foundation/mutations/20261102-cpt-studio-participant-credentials.md), read by path at send
time and mounted read-only into the worker alone. Real patient documents need a HIPAA business associate agreement,
which is the owner's decision and not part of this act.

Revision to install: `7dd8130050773f57c98dd48dfa6c128d4fd20292`, the merge commit of PR #1498 (branch feat/cpt-studio-fable-judge-20261120, head
`6bdb9725d758df8a488e16600168d2654125c075`; the merge commit's tree under cpt-studio/, scripts/run-ruled-mutation.sh and scripts/lib/ equals the head's:
`git diff --quiet 6bdb9725d758df8a488e16600168d2654125c075 7dd8130050773f57c98dd48dfa6c128d4fd20292 -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`
exit 0, and the whole trees are equal too, exit 0). It contains origin/main as of the merge (323381358, PR #1497). Image tag cpt-studio:`7dd813005077`. Its citation, on the revision:
`CI, secrets-scan and cpt-studio on 7dd8130050773f57c98dd48dfa6c128d4fd20292, started at the merge (2026-11-20T12:17:45Z) and in progress when this file was committed; each must have completed with success, read in both views (by commit and by branch), before the first phase runs - a run that is not success is a stop. The merge commit's whole tree equals the PR head's, so its runs repeat the head's, which passed`. The PR
head's citation: `CI 44730241630 success, secrets-scan 44730241522 success and cpt-studio 44730241550 success on 6bdb9725d758df8a488e16600168d2654125c075 (completed 2026-11-20T12:17:17Z), read in both views`. cpt-studio is not a required check; it is required
here.

It replaces the live revision e426c747c7b73996d7f9fb4d598517aa0bc4d89a (image cpt-studio:e426c747c7b7, id
sha256:f9dd1601241ee171ca25cb6753692cb1528281c4f1b48b53c12bdb79c05f1dd4, its web on 127.0.0.1:9151 since that install's
switch from 9150 at 2026-11-19T22:03:56Z), installed 2026-11-19 under
docs/foundation/mutations/20261119-cpt-studio-fable-interpreter-install.md (landed by PR #1497 as 323381358). That image
is kept as the rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh, with `RULED_ACT_MAX_SECS=9000` (the installer
refuses app, switch-back and rollback-app below 9,000 s: the worker's stop bound is 3,600 s), as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 7dd8130050773f57c98dd48dfa6c128d4fd20292 --receipts /home/claude/cpt-studio-install-20261023`
(install-judge/act_j.sh, the r3 install's wrapper with this release's names, arguments and ceiling).

Phases, in this order: preflight; image; app (with `--coding-mode live --authorization-ref
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`); verify. The installer gives every container it starts - the web,
the worker and each one-shot - the coder's effort and the owner's two figures, read from the revision's
cpt-studio/cptstudio/settings.py defaults: `CPT_STUDIO_CODING_EFFORT=max`, `CPT_STUDIO_DOCUMENT_CEILING_USD=25` and
`CPT_STUDIO_CONCURRENT_DOCUMENTS=4`; the web and the worker run with `CPT_STUDIO_CODING_MODE=live` and the authorization
reference. Corti, the participants and the interpreter are started disabled: their code is not in this revision, and
their modes are a switch-back's alone. No monthly spending threshold is written: the Anthropic account's own limit is
the only monthly bound (a figure only the owner sets, class d).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-fable-judge-act-20261120). That commit must be a descendant of the revision that
changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/ (the installer's check_tree): nothing
under cpt-studio/ is edited in the declaration's PR. Read each receipt before the next phase. The receipts directory is
the live install's own; no receipt there is changed: each file is created once.

Not run: secrets (the three-file set and the Anthropic copy exist; this act's preflight receipt must read the Anthropic
copy present), db, reference, passages and license-note (their data is byte-identical to the live revision's and both
already ran on 2026-11-19 for e426c747c7b7; nothing in this revision reads the passages), provision, operators,
http-vhost, cert, https-vhost, rollback-vhost, rollback-app and switch-back. switch-back is the incident path (below),
run only by a decision recorded under this declaration, after a fresh preflight; rollback-app only by such a decision.
No re-coding is run: no document is sent by the install. An earlier document is coded only when a member presses
"Review again" on it.

Between e426c747c7b73996d7f9fb4d598517aa0bc4d89a and the revision, these are byte-identical (`exit 0 on the PR head
6bdb9725d758 (read 2026-11-20T11:5xZ); re-measured on the act checkout`): cpt-studio/deploy/ apart from the Dockerfile (entrypoint.sh,
gunicorn.conf.py, the nginx templates); cpt-studio/studio/reference/data/; scripts/run-ruled-mutation.sh, scripts/lib/
and scripts/check-cotenants.sh. These change, and are named here: everything the delta below lists - among them
cpt-studio/deploy/Dockerfile (LibreOffice Writer and DejaVu fonts in, for the bounded Word-to-PDF conversion; tesseract
and poppler out), cpt-studio/requirements.txt (anthropic 2.11.0 and its dependencies in; pypdf, python-docx, lxml,
cryptography, requests, certifi, charset-normalizer and urllib3 out), cpt-studio/cptstudio/settings.py and urls.py,
cpt-studio/studio/models.py and migration 0016, the customer page (the client contract becomes customer-2026-11-22), and
the installer itself (cpt-studio/ops/install.py, ops/INSTALL.md): this act runs this revision's installer.

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet e426c747c7b73996d7f9fb4d598517aa0bc4d89a HEAD -- cpt-studio/deploy/entrypoint.sh cpt-studio/deploy/gunicorn.conf.py cpt-studio/deploy/nginx cpt-studio/studio/reference/data scripts/run-ruled-mutation.sh scripts/lib scripts/check-cotenants.sh`, exit 0;
- `git diff --name-status e426c747c7b73996d7f9fb4d598517aa0bc4d89a HEAD -- cpt-studio/studio/migrations`, listing
  exactly `A cpt-studio/studio/migrations/0016_fable_coding.py`;
- `git diff --name-only 7dd8130050773f57c98dd48dfa6c128d4fd20292 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5, before this declaration is committed;
install-judge/held_check_j.sh): `the range e426c747c7b7..7dd813005077 is two merges (#1497, docs only; #1498); its 223
runtime files (git diff --name-only, docs, tests and markdown aside: 221 under cpt-studio/, .github/workflows/cpt-studio.yml
and scripts/ci/verify-cpt-studio.sh) were searched for by path, with and without the cpt-studio/ prefix, across
docs/deploy-reports/, docs/foundation/deploys/ and docs/foundation/mutations/ as of 7dd813005077 on 2026-11-20, after the
positive control (deploy-prod.sh: 61 files). Twenty-one files name some of them - sixteen declarations (the CPT Studio
installs and credential acts from 20261023 to 20261119 and 20261101-quillmd-rebuild-release-797199c7c625) and five deploy
reports (evidence, not declarations). None is HELD: every revision each declaration names is an ancestor of, or is, the
running e426c747c7b7 (git merge-base --is-ancestor), so each has shipped and cannot be overtaken. #1498 has this
declaration; #1497 is yesterday's declaration itself (install-judge/held-check-7dd81300.txt)`.

## The migration

**0016_fable_coding** (additive only; the installer's migration_safety accepts it): four new tables -
`studio_codinground`, `studio_codinganswer`, `studio_codedecision` and `studio_exportartifact` - and nothing altered,
dropped or backfilled in any existing table. The earlier pipeline's tables, rows and model classes stay exactly as they
are (the model classes are kept in models.py as legacy records, read by nothing in the coding path).

## Delta shipped (e426c747c7b7 to the revision)

**This is a TREE, not one change.** The range carries two merges: #1497 (yesterday's install declaration, docs only) and
#1498, the Fable coding build with its two fix passes. #1498 replaces the earlier pipeline (DECISIONS D351-D359): the
deterministic coding engine, its word lists and code-family rules, the Corti prediction, the Astra and Fable 5.1
participants, the interpreter and its question stage, OCR and the local PDF and Word readers are removed (`git
diff --shortstat e426c747c7b7 7dd813005077 -- cpt-studio: 1562 files changed, 22829 insertions(+), 1008056 deletions(-)`). In their place: studio/fable/ (the Anthropic SDK client,
the prompts, the document preparation - a PDF sent as itself with page citations, a Word file converted to PDF by
LibreOffice in a bounded child with external relationships dropped first, a text file as a text document - the strict
reading of the answer's shape, and the pricing); studio/jobs.py (one coding stage per round: the reader's send, then the
checker's; no automatic resend of a paid request, ever; a per-revision ceiling counted from every run's usage, a send's
worst case doubled for the server-side fallback; holds on an authentication, permission, payment or quota refusal);
combine() as the only decision logic (a line is ready only when every review naming it agrees; anything else needs a
human); line identity (L1..Ln, M1..Mk) through rounds, decisions, quotes and exports; the customer page (statuses,
questions and answers, the review dialog with the exact acknowledgement, stop, resume, retry, exports, the in-page
document viewer opened at a quoted page); the operator page; the installer's switch-back for this design.

## What members see after the install, and what they no longer see (an accepted-capability loss, class b)

- A new upload is coded by Claude Fable 5.2 twice (reader and independent checker) from the original file. Each code
  line reads ready for approval, needs an answer, needs review, or not supported; a question is answered on the page and
  starts the next round; a human approves each line with the acknowledgement; exports are the draft and the approved
  codes.
- **The 89 earlier documents stay in the database untouched, and the page lists them as "Earlier review" with no codes.**
  Their earlier codes, clarifications and decisions, and their 209 earlier reports, are no longer shown or downloadable
  on the page: the code that rendered them is part of the earlier pipeline the owner ordered removed (D351: "idont wanna
  see any single old code"). Nothing is deleted. "Review again" codes the document with this revision (paid, about 2 US
  dollars per document, D353). A switch-back to e426c747c7b7 shows them again as they were.
- **Approvals and answers made in this revision are not carried back by a switch-back** (ops/INSTALL.md "Switching back
  to the pipeline before the Fable coding build" (d)): the earlier revision reads none of the four new tables, so after a
  switch-back the members redo there the reviews they made here; the rows stay for this revision's next `app`.

These are stated here so the next incident finds them: the first follows from D351 and is surfaced again to the owner in
this act's report; the second is the switch-back's declared loss.

## Cost and time

Measured on the owner's documents (D353): about 2.12 US dollars and 4 to 12 minutes per document for both reads at
effort max; an answered question adds a round of about the same cost. The ceiling counts every coding run of a
document's revision (a run whose cost is not known counts at its reserved worst case) plus the next send's worst case,
doubled for the server-side fallback; a send that would pass 25 US dollars is not made and the round fails as over the
ceiling (with the doubling, a send is refused once about 16.5 dollars are spent; a document of about 450 pages or more
cannot finish).

## Measured before this declaration

**The test-server rehearsal of the owner's documents (D361)**: `install-judge/rehearse_j.sh on a restored copy of live
(read-only dump of 2026-11-20T10:55:06Z) migrated with cpt-studio-test:6bdb9725d758 (exactly 0016), the test web and
worker on 127.0.0.1:9371 with the coding step live (the test-only copy of the key), ops/walk.cjs of the tree on each of
the owner's seven de-identified PDFs (documents A to G), two at a time, insurance commercial: 7 of 7 walks PASS on every
check (the JSON and page contracts, quotes and their page jumps, the viewer, one answer round, one approval through the
review dialog and its Undo, both exports byte-compared, the 390-pixel viewport, the operator gate, the vendor-name scan).
Round 1 gave the same actionable codes as the proof (D353) on 6 of 7; on the seventh (F) the sedation line the proof held
for review is now not supported by both reads, and its ready code equals the proof's. No code reached ready that the
proof or the lead's reading of the document did not support; the documents with a contradiction (biopsy in the title
only; screening against rectal bleeding) asked, and after the walk's answer "not documented" the next round kept only
the supported code. Cost US$29.71 for 12 rounds (about 2.50 dollars per round); 10 to 22 minutes per document with its
answer round (DECISIONS D364)`.

**The switch-back rehearsal on that copy** (ops/INSTALL.md: "A rehearsal on a restored copy of live, before an install,
is the operator's"): `with 7 coded encounters on the copy (12 rounds, 5 answers, 6 approvals and 6 undos, 13 exports): the
revision's UNDO_HAZARDS_READ none; CLOSE_STAGES closed 0 and named the 7 to relabel; CODING_MADE counted them;
e426c747c7b7's own PUT_BACK_STATES moved the 7 to its "processing" (ops/INSTALL.md (c)); e426c747c7b7's API answered 200
for all 96 encounters as the customer; forward again, the revision's RECOMPUTE_STATES restored the 7 (ready 6,
awaiting_answer 1) and kept 89; no row deleted; the copy and its volume dropped`.

**Offline predictions** (install-judge/predict_j.sh on a throwaway restore of a fresh read-only dump of live, in the
revision's test image cpt-studio-test:6bdb9725d758 - id sha256:31c0cac6dfc8663d2907f273036c931a2a0a541b486bda7a604bae760be4ec0a,
built as the image phase builds - and in cpt-studio:e426c747c7b7): `dump of 2026-11-20T11:46:11Z, 44 TABLE DATA entries;
migrate applied exactly studio.0016_fable_coding; the schema 16 migrations, last 0016_fable_coding, the four tables present
and empty, studio_codedecision.line present; UNRUNNABLE_STAGES {"known": ["code"], "stuck": 0}; V1_ROWS none;
INSTALL_COUNTS 89 encounters, 0 coded, 0 unknown, 0 in flight (reserved 0, sending 0), the four tables 0, standing holds
0; RECOMPUTE_STATES {"encounters": 0, "changed": {}, "kept": 89}; in e426c747c7b7's image TARGET_MODEL_READS
["member_answer", "modifier"] and PUT_BACK_STATES over all 89 encounters {"changed": {}} (the earlier pair's own
derivation leaves every stored state as it is on the migrated copy); table deltas: django_migrations 30 to 31 and the
four new tables absent to 0, nothing else; encounter states after: extraction_failed 1, needs_clarification 47, no_codes
4, ready_for_review 8, reviewed 29 - as before` (install-judge/predict-6bdb9725.txt). The installer's own conversion gate
(ops/install.py image_conversion) on that test image: `%PDF-, 10357 bytes, 3.7 s`; inside it, the real LibreOffice
network-isolation test (tests.test_fable_document, a crafted Word file pointing at a local listener) passes - no request
reached the listener.

## Baseline (read-only, `2026-11-20T12:19:33Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_j.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts and states only, never a document, response or credential):

    bash /home/claude/cpt-studio-completion-20261106/gemini-migration/install-judge/live_baseline_j.sh
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:e426c747c7b7 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

live_baseline_j.sh is the r3 install's baseline script with the rows of migration 0016's four tables (absent before the
app phase), the code jobs, the coding runs and the standing interpreter holds appended. pre_app_j.sh re-reads it before
app and compares it with the copy this section was pasted from (read_at and the last audit's age aside).

    read_at 2026-11-20T12:19:33Z
    transaction_read_only on
    encounters 89
    revisions 90
    source_files 83
    contexts 106
    routing_runs 116
    provider_runs 287
    provider_runs_sent 251
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1407
    reports 209
    jobs 653
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 112
    reference_sources 2
    reference_facts 34665
    studio_migrations 15
    studio_migration_last 0015_inventory_appraisal
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
    run_participant anthropic interpretation succeeded 3
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 44
    run_participant astra peer_review succeeded 46
    run_participant fable independent succeeded 45
    run_participant fable peer_review failed 1
    run_participant fable peer_review succeeded 41
    credits_sum 4.452079999999999826
    usage_keys anthropic cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready_for_review 8
    encounter_state reviewed 29
    run anthropic appraisal succeeded t f 4
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
    last_audit assessment.created 2026-11-19T22:48:58Z 48635
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
    current_context_by_version none 1
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
    studio_codinground absent
    studio_codinganswer absent
    studio_codedecision absent
    studio_exportartifact absent
    interpreter_holds_standing 0

    # scripts/check-cotenants.sh (last lines)
    HOST                   EXPECTED  OBSERVED
      🟢 quillmd.com          200       200
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    503       503
      🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).

    # docker ps -a --filter label=org.quillmd.cpt-studio=1; docker image inspect cpt-studio:e426c747c7b7
    cpt-studio-worker f9dd1601241e Up 14 hours 8000/tcp
    cpt-studio-web f9dd1601241e Up 14 hours (healthy) 127.0.0.1:9151->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 5 days 127.0.0.1:55451->5432/tcp
    sha256:f9dd1601241ee171ca25cb6753692cb1528281c4f1b48b53c12bdb79c05f1dd4 e426c747c7b73996d7f9fb4d598517aa0bc4d89a

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline the switch is verified against: the quillmd-cpt vhost as this
  installer's HTTPS stage for 9151 (sha256 f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65, as the r3
  app receipt app-20261119T220629668586Z.json left it); 9151 held by cpt-studio-web alone and 9150 free; no
  cpt-studio-web-next; co-tenant routing and https://app.quillmd.com/health/; the Anthropic copy present.
- **image:** a new local image cpt-studio:`7dd813005077`, built from git archive of the revision's cpt-studio/, labelled with
  the revision. Before it builds, the migration check accepts 0006 to 0016. The image's own checks: `manage check`, the
  WSGI application loading as uid 10150 on a read-only root, soffice present, anthropic 2.11.0 importable, and the
  conversion gate (a synthetic DOCX converted to PDF through the image's bounded child). The apt and pip steps run (the
  Dockerfile and requirements changed); the expected image size is about 560 MB (the test image of the head:
  `560124065 bytes`). cpt-studio:e426c747c7b7 is kept.
- **Before app, outside the installer and read-only on the database** (install-judge/pre_app_j.sh): one `pg_dump -Fc` of
  the cptstudio database through the database container's own pg_dump in a read-only transaction, to
  /home/claude/cpt-studio-install-20261023/pre-app-`7dd813005077`-UTC.dump (0600), whose `pg_restore --list` shows 44 TABLE
  DATA entries (the schema is still e426c747c7b7's); a restore of it on the test server migrated with the revision's test
  image (exactly 0016 applies); the baseline re-read equals the declared one (read_at and the last audit's age aside),
  with jobs_active 0, no provider run reserved or sending, no unreconciled unknown outcome, no reading job running and no
  audit event newer than 10 minutes. Its log ends "PRE-APP PASS" only when every step passed; act_j.sh's app phase
  requires it.
- **app (the blue/green switch):** the coding credential read in the worker's mount layout with no network (format and
  permissions only); **migrate applies `studio.0016_fable_coding` and nothing else** while the e426c747c7b7 pair still
  serves; the queue read finds 0 stages this revision cannot run; V1_ROWS finds none; **INSTALL_COUNTS** records 89
  encounters (0 coded), the jobs and runs by kind and state as the baseline lists them, 0 unknown, 0 in flight, the four
  tables at 0 and 0 standing holds - printed, never a refusal - each difference from the prediction explained by a
  recorded member act; the replacement plan reads blue/green (quillmd-cpt is the HTTPS stage for 9151; 9150 free);
  **S1** cpt-studio-web-next starts on 127.0.0.1:9150 and answers /health/ with the revision; **S2** the old worker is
  parked (idle); **S3** the vhost's proxy_pass is switched 127.0.0.1:9151 to 127.0.0.1:9150 (sha256 f816a27d... to
  259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, the 9150 rendering; deploy/nginx/ unchanged by the
  byte-identical list), `nginx -t` clean, a graceful reload, https://cpt.quillmd.com/health/ serving the revision, the
  co-tenants and app.quillmd.com as the preflight found them; **S4** the new worker starts with the coding step live,
  binding /etc/cpt-studio/anthropic-credentials.env read-only (and no other credentials file), with the effort and the
  two figures in its environment; **S5** the old web drained, stopped and parked; **S6** RECOMPUTE_STATES changes
  nothing (`{"encounters": 0, "changed": {}, "kept": 89}`: no encounter has a coding round). The receipt names the
  replaced pair (e426c747c7b7's web and worker), which a switch-back returns to.
- **verify:** nothing changes; its receipt reads the site, the health, the containers and the vhost.

**Database deltas after app, against the baseline:** `django_migrations` +1 (studio.0016_fable_coding); the four new
tables present with 0 rows; every other count of the baseline unchanged - encounters 89, revisions, source files,
provider runs, assessments, proposals, clarifications, decisions, reports, jobs, users 5, memberships 3, workspaces 1,
reference sources 2, reference facts 34665, passages - and every encounter's stored state unchanged; audit events +0
from the install itself `(the installer writes none: ops/install.py names no audit write, and RECOMPUTE_STATES updates only the state of encounters with a coding round - none); studio_workerbeat stays 1 row (both revisions beat as name 'worker', update_or_create)`; login attempts may grow by the
members' own sign-ins.

## After the install: the acceptance walk (ordinary use, not a phase)

ops/walk.cjs of the revision against https://cpt.quillmd.com with the review-agent account and the ops-agent operator,
on the two synthetic walk documents (gi-01.txt and gi-02.pdf), live (`--allow-live-provider`; about 2 US dollars per
document plus an answer round): the page and the JSON against the contracts, one answered question, one approval through
the review dialog, both exports, the 390-pixel viewport, the operator gate and the vendor-name scan. Its rows are
expected and are not part of the install's judgment: encounters +2 and their revisions and files, coding jobs, coding
runs (reader and checker per round), rounds, at most one answer and one approval per document, the exports and the
audit events they write. The owner's own walk with his documents follows when he chooses.

## Must not change

The 89 earlier encounters and every row of every earlier table; the accounts, memberships, workspace, reference sources,
reference facts and passages; the database container and its volumes; /etc/cpt-studio/ (no file written: the Anthropic
copy is read, not copied); the co-tenants' HTTP answers (scripts/check-cotenants.sh) and https://app.quillmd.com/health/;
every other nginx vhost; every image (nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded and the conversion gate passed; pre_app_j.sh ending PRE-APP PASS; app exit 0 with migrate's log listing exactly
0016, the counts as declared, the switch applied and https://cpt.quillmd.com/health/ serving the revision; verify exit
0. After app: live_baseline_j.sh read again and compared with this declaration's deltas; scripts/check-cotenants.sh.

## Rollback per phase, and its limits

- preflight, verify: nothing to undo.
- image: nothing to undo (a new image; the live pair untouched).
- app before the switch (S1, S2): the installer's own undo stops the incoming web and restarts the parked worker; the
  migration stays (additive; e426c747c7b7 ignores the four tables - the prediction ran its own state derivation on a
  migrated copy and it changed nothing).
- app after the switch: the installer's own undo switches back on failure; after a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_j.sh switch-back with SWITCH_BACK_DECISION recorded): the e426c747c7b7 pair
  returns with its own modes (Corti, the participants and the interpreter live), coding jobs are closed (ops/INSTALL.md
  (a)-(c)), and the loss (d) applies.
- The receipts, the pre-app dump and the image stay.

## What is not claimed

Coding accuracy beyond the documents measured (D353 and the rehearsal above); any use with real patient documents (the
site stays synthetic-only); a highlight of the quoted text inside the PDF viewer (the viewer opens at the quoted page;
highlighting is a later, separate item if the owner wants it); that the server-side fallback was ever exercised (it was
never used in the proof); the earlier pipeline's capabilities (removed by D351).

## Stop conditions

Any phase exiting non-zero; a receipt or a reading that differs from this declaration (a difference not declared here is
THE finding, whatever its explanation); migrate applying anything but 0016; an encounter's stored state changing in app;
the citation not success in both views; a held declaration found; preflight BLOCK (the session's health check) or the
installer's preflight refusing; the door's ceiling reached; a co-tenant's or app.quillmd.com's answer changing; the
acceptance walk failing a check (judged, then reported; a defect found there is fixed under D358 and installed under a
new declaration, or the site switched back - never patched in place).
