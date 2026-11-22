# Prospective declaration: Neurosurgery and Orthopedic Surgery at cpt.quillmd.com (9dab92ba0f98 to 3ce5383ce485), installed blue/green with the site kept serving: no migration, no new dependency, the member's specialty shown on the page, the CPT book's marks read, and each new specialty's workspace and accounts provisioned

Authority: the owner's direction of 2026-11-22 recorded verbatim, with this programme's interpretation (a)-(f), in
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md (its D390 section, landed with the change in PR #1509) and a
RULINGS.md row:

- D390: "can we add neuro and orthopedic suregy for now then after that we decid can we?"; "make sure you fable cover
  every code for that both category i dont want to miss any and also username are cool for testing and and make sure
  like everything id as same as gi dont create old enigne or any enigne by coding which make us compilated same as GI
  which fable take care of all the stuff"; "for testing only test one short and one long for both category until you get
  a approval for live relase i will test the majority of that both categiry by my self dont spend to much for testing
  dont forget only one short and one long realistic long not a 20 pages until eveyrhting works fine". The recorded
  interpretation: two categories beside Gastroenterology, each its own workspace with its own logins (owner-neuro,
  owner-ortho, review-agent-neuro, review-agent-ortho); no engine, code list, routing or specialty rule (D358); the
  answer reader reads the CPT book's marks so that no code Fable writes is lost; paid testing exactly one short and one
  realistic synthetic document per specialty on a rehearsal copy with the test key; the live release only after the
  owner's approval.

- **The owner's approval of this release**, 2026-11-22, verbatim: "ok", in reply to the session's report of the paid
  rehearsal, which ended "Nothing is live yet. It's waiting for your OK to release." This declaration records it in the
  rulings file's D390 section, in the same commit.

It stands on the standing directions this install keeps:
- D358, "start it but dont crate the old system engine again": the change is plumbing and display. Nothing reads a note
  to decide, holds or changes a code; the coding review, its instructions, the decisions and the approval rules are
  untouched, for Gastroenterology and for the new specialties alike. The coder is not told the specialty.
- The 2026-10-23 directive (a protected synthetic demonstration; app.quillmd.com and unrelated services preserved).
- D360's install conditions: no unresolved critical or high finding; every suite green; CI green on the merged commit;
  this declaration committed before the act; the rehearsal on a restored copy of live passed; preflight not BLOCK; the
  act only through the door; a check on the live site afterwards; a report either way.

The integration and deployment owner is session `738699b2`. CPT Studio stays standalone and synthetic-only. No purchase,
agreement, key or payment change is part of this act, and no paid request is made by it.

Revision to install: `3ce5383ce485c39339a839d1f8f8468c41ef9a53`, the merge commit of PR #1509 (branch
feat/cpt-studio-neuro-ortho-specialties-20261122, head `af1ebb26faefa55da1847bffc6e428e0fc3a0ab5`; the two trees are
one: main had not moved since the branch point a7f4cdbf6, `git rev-parse <commit>^{tree}` equal for both). Image tag
cpt-studio:`3ce5383ce485`. Its citation, on the revision: `CI 45004766500 success, cpt-studio 45004766452 success, secrets-scan 45004766384 success (all on 3ce5383ce485, the same three in both views)`. The PR head's citation: `CI 44998081574
success, cpt-studio 44998081456 success, secrets-scan 44998081506 success (all on af1ebb26f, the same three in both views)`.
cpt-studio is not a required check; it is required here.

It replaces the live revision 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 (image cpt-studio:9dab92ba0f98, id
sha256:6e409ad596bc3bca4d03c55de9e73a9111e9215a5ceb2390096c0d5d2d85bf41, its web on 127.0.0.1:9151 since that install's
switch on 2026-11-22), installed under docs/foundation/mutations/20261122-cpt-studio-physician-pdf-install.md (PR #1507,
ddb69890e0ce). That image is kept as the rollback image (switch-back). That declaration and its receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with `RULED_ACT_MAX_SECS=9000`, as
`python3 -B cpt-studio/ops/install.py --phase PHASE --revision 3ce5383ce485c39339a839d1f8f8468c41ef9a53 --receipts /home/claude/cpt-studio-install-20261023`
plus each phase's fixed arguments (neuro-ortho-20261122/act_n.sh: the physician PDF release's act_p.sh with this
release's names and its two provisioning phases).

Phases, in this order:
1. preflight;
2. image;
3. app, with `--coding-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, the modes
   the live pair runs with;
4. verify;
5. provision, with `--specialty neurosurgery --owner-username owner-neuro` (act_n.sh provision-neurosurgery): the
   workspace "Neurosurgery" (the installer's default for the specialty), its owner owner-neuro and its review agent
   review-agent-neuro (the installer's default);
6. provision, with `--specialty orthopedic-surgery --owner-username owner-ortho` (act_n.sh
   provision-orthopedic-surgery): the workspace "Orthopedic Surgery", owner-ortho and review-agent-ortho.

act_n.sh refuses a provisioning phase unless app ended exit 0, the newest verify after it (untagged or tagged) ended
exit 0, the newest preflight after it (if one ran) ended exit 0, no switch-back has run and https://cpt.quillmd.com/health/
answers status ok, database ok and the revision; and it refuses provision-orthopedic-surgery unless
provision-neurosurgery ended exit 0 (provisioning runs in the installed image, so it follows the switch, in this
order). It refuses any REV other than this declaration's "Revision to install". The installer gives the web and the worker the same coder settings as the live pair
(the revision's settings.py defaults: effort max, the 25 US dollar per-document ceiling, 4 documents at once).

Run them from a clean, detached checkout of the merge commit that lands this declaration
(/opt/meddoc-pro/.worktrees/cpt-neuro-ortho-act-20261122). That commit must be a descendant of the revision that changes
nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase.

Not run: secrets, db, reference, passages, license-note, operators, http-vhost, cert, https-vhost, rollback-vhost,
rollback-app and switch-back. switch-back is the incident path (below). No document is sent by the install.

Between 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 and the revision, these are byte-identical
(`git diff --quiet 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 3ce5383ce485c39339a839d1f8f8468c41ef9a53 -- <these paths>: exit 0, 2026-11-22`):
the migrations (still 0016_fable_coding, the last), the coding path apart from the answer reader (studio/fable/
__init__.py, client.py, credentials.py, document.py, pricing.py, prompts.py; jobs.py, intake.py, state.py), decisions.py,
storage.py, access.py, audit.py, api.py, models.py, the export path (exports.py, physician_report.py, physician_pdf.py,
report_fonts/), the operator console (operator.py and its templates), the sign-in page, the pinned PDF library
(studio/static/studio/lib), styles.css, cptstudio/ (settings.py among it), deploy/ (the Dockerfile) and the requirements.
These change, and are named here: studio/fable/result.py (the CPT book's marks read wherever an answer names a code),
studio/customer.py (GET /api/session gains workspace.specialty), studio/views.py and templates/studio/index.html (the
page renders the member's specialty), studio/static/studio/app.js (the Specialty field and the review heading follow the
session; empty states no longer say GI), studio/management/commands/provision.py (--specialty; the workspace-name rules;
one login never added to a second workspace; one run at a time), ops/install.py (provision --specialty: per-specialty
credentials files and review agent; an empty --workspace-name refused; names passed as --option=value - no other phase
changes), ops/walk.cjs (--workspace), ops/verify_login.py (the specialty kept in its evidence), ops/dev_preview_server.cjs,
ops/verification/ (the customer contract's workspace.specialty; 30 new synthetic documents and their manifest entries),
the tests, and the docs (API.md, ARCHITECTURE.md, ops/INSTALL.md); outside cpt-studio/, docs only (CPT-HARNESS-CHECKLIST.md,
docs/foundation/RULINGS.md, docs/foundation/rulings/2026-10-23-cpt-studio-gi.md, and the physician PDF release's
declaration and report).

Before preflight the operator runs, in the act's checkout:
- `git diff --quiet 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 HEAD -- cpt-studio/studio/migrations cpt-studio/studio/storage.py cpt-studio/studio/intake.py cpt-studio/studio/jobs.py cpt-studio/studio/state.py cpt-studio/studio/access.py cpt-studio/studio/decisions.py cpt-studio/studio/operator.py cpt-studio/studio/audit.py cpt-studio/studio/api.py cpt-studio/studio/models.py cpt-studio/studio/exports.py cpt-studio/studio/physician_report.py cpt-studio/studio/physician_pdf.py cpt-studio/studio/report_fonts cpt-studio/studio/fable/__init__.py cpt-studio/studio/fable/client.py cpt-studio/studio/fable/credentials.py cpt-studio/studio/fable/document.py cpt-studio/studio/fable/pricing.py cpt-studio/studio/fable/prompts.py cpt-studio/studio/static/studio/lib cpt-studio/studio/static/studio/styles.css cpt-studio/studio/templates/studio/login.html cpt-studio/studio/templates/studio/ops_base.html cpt-studio/studio/templates/studio/ops_encounter.html cpt-studio/studio/templates/studio/ops_index.html cpt-studio/cptstudio cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in`, exit 0;
- `git diff --name-only 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 HEAD -- cpt-studio/studio/migrations`, printing nothing;
- `git diff --name-only 3ce5383ce485c39339a839d1f8f8468c41ef9a53 HEAD -- cpt-studio scripts/run-ruled-mutation.sh scripts/lib`, printing nothing.

Any other difference is a stop.

**The deploy range against held declarations** (docs/DEPLOYMENT_RUNBOOK.md 2.5; install-judge/held_check_j.sh with this
range): `install-judge/held_check_j.sh 9dab92ba0f98a647b4fb5522e067560ba4e8afd8 3ce5383ce485c39339a839d1f8f8468c41ef9a53, 2026-11-22: the range's first-parent merges are #1509, #1508 and #1507; 43 runtime files, all under cpt-studio/; positive control (deploy-prod.sh named by 65 files) passed; 22 declarations and reports name a runtime file of the range, and every revision each names is an ancestor of the running revision; possibly held: 0`.

## Delta shipped (9dab92ba0f98 to the revision)

**This is a TREE, not one change**, but its only runtime change is the two specialties: the range carries #1509 (this
change) and #1507 and #1508 (the physician PDF release's declaration and install report, docs only).

- Runtime, display: GET /api/session's workspace gains `specialty`, the workspace category's name (Gastroenterology,
  Neurosurgery, Orthopedic Surgery); the page renders it in the upload form's Specialty field and the review heading, and
  re-reads the session when the upload dialog or a document opens. The PDF report already printed the category. The
  client contract version is unchanged; the customer contract file lists the key, so the scanner and the walk hold the
  server to it.
- Runtime, the answer reader (studio/fable/result.py, FIX-SPEC-2 section 2's lossless conversions): a code written with
  the CPT book's marks - "+" (add-on) and "#" (resequenced), at most one of each in either order - is read as the code,
  wherever an answer names one (a code line, a missed code, a review's code, the checker's correction, a question's
  target, a section marker). Before, a marked code made the whole round unreadable. A code line's code in any other form
  stays unreadable; a review's code, a correction or a target in another form is kept as written and matched as before.
  **Gastroenterology, stated exactly:** an answer with no book mark is read exactly as before (a differential over the
  reader, the checker, the citations, the listing and the combination); a GI round whose checker writes a marked code
  ("+99153") now pairs that review with the line it marks, where the installed revision sent the line to review. Stored
  rounds are read again whenever a page shows them, so the pre-app checks require that no stored round holds a marked
  code (predicted: 0 of 8).
- Runtime, provisioning (manage provision; not reached by members): --specialty; an existing workspace found by its name
  exactly as stored and a name stored as given, as before; a new workspace's name does not name another specialty (read
  by its letters and digits, case aside) and is not another specialty's workspace's exact name; a run never adds an
  account to a second workspace; one run at a time (a transaction-level advisory lock); refusals state facts.
- Ops: ops/install.py's provision phase takes --specialty (its own credentials files: /etc/cpt-studio/initial-credentials-
  <specialty>.json and ~/.cpt-studio/agent-credentials-<specialty>.json; Gastroenterology keeps its two files) and refuses
  an empty --workspace-name; ops/walk.cjs --workspace; ops/verify_login.py and the dev preview follow.
- Docs and records: API.md, ARCHITECTURE.md, ops/INSTALL.md; CPT-HARNESS-CHECKLIST.md; RULINGS.md and the CPT Studio
  rulings file (D390). Thirty synthetic verification documents (16 neurosurgery, 14 orthopedic surgery), author
  expectations only.

## What members see after the install

- Gastroenterology's members: the Specialty field and the review heading read "Gastroenterology", as before; the empty
  states say "synthetic document" where they said "synthetic GI document". Every encounter's view, every PDF and every
  decision are unchanged (predicted: 97 views and 194 PDF rows identical).
- The two new workspaces exist with their accounts: owner-neuro and owner-ortho (the owner's logins; their passwords are
  in /etc/cpt-studio/initial-credentials-neurosurgery.json and -orthopedic-surgery.json, root-only), review-agent-neuro and
  review-agent-ortho (the release checks' agents; ~/.cpt-studio/agent-credentials-<specialty>.json). Each sees its own
  workspace, empty, with its specialty on the page; neither sees Gastroenterology's documents (rehearsed: each new
  workspace lists 0 encounters, Gastroenterology's members 97).
- Nothing else changes: the codes, the decisions, the approval rules, the questions, the viewer, the highlight and the
  PDF report.

## Cost and time

No paid request. The image build reuses the cached apt and pip layers (the Dockerfile and requirements are unchanged)
and rebuilds the application layers: the revision's test image cpt-studio-test:3ce5383ce485 (sha256:cd823f4b3fb6...,
built the same way) is 608,193,451 bytes and shares 7 of its 11 layers with the live image cpt-studio:9dab92ba0f98
(608,089,549 bytes). The app phase takes about 3 minutes (the blue/green switch; the worker's stop bound); each
provisioning phase under a minute.

## Measured before this declaration

**The full gate** (scripts/ci/verify-cpt-studio.sh on the revision's tree): on the PR head af1ebb26f (its tree is the
revision's tree), with the CI interpreter: Django suite 628 tests OK (1 skipped), ops 538 OK, verification 37 OK, walk
node tests 97 of 97, pip-audit "No known vulnerabilities found"; exit 0 (neuro-ortho-20261122/gate-8.log).

**The refutation of the finished diff** (the answer reader is on the coding path): seven rounds of independent lenses
over the finished diff, each told to refute, each in a sealed copy of the tree with no write access to the author's
files, every finding verified before it was believed: 15, 13, 12, 9, 7, 8 and 8 findings. Rounds 2-6 kept finding refusal
chains in provisioning's name rules; round 6 removed the look-alike and spacing rules and every instruction in a refusal.
Round 7 found no high finding and no medium regression (the stop rule); its findings were repaired. Every repair of
every round is proven by a mutation its test kills (59 in all), each file restored byte-identical by sha256; the
residuals are recorded as limits (neuro-ortho-20261122/refute-n1..n7-dispositions.md).

**The paid rehearsal** (D390 (f): exactly one short and one realistic synthetic document per specialty): the head's test
image cpt-studio-test:af1ebb26faef on a fresh copy of live (cptg_jreh_20261122t073536z), coding live on the TEST-ONLY
key, copy-only accounts. Neurosurgery 07:36-07:46Z: ns-16 (a new-patient visit) 99205 ready; ns-02 (an L4-L5 TLIF) 22633,
22840, 63052, 22853, 61783, 20936, 20930 ready, the reader's 63047 marked not supported; $4.19. Orthopedic Surgery
07:46-07:56Z: or-10 (a knee aspiration and injection) 20610-RT and J3301 x4 ready, 99213 and 20611 not supported; or-03 (a
shoulder repair) 29827-RT, 29826-RT and 23430 (59, 51, RT) ready, 29828 and 29823 not supported; $4.37. 8 of 8 requests
answered 200; every walk passed (the session served the right workspace and specialty); 13 of 13 author-expected codes
ready; 0 questions; $8.56 in all (gemini-migration/USAGE-LEDGER.md section 5). The copy was torn down.

**Offline predictions** (neuro-ortho-20261122/predict_n.sh on a throwaway restore of a fresh read-only dump of live, in the
revision's test image): run 2026-11-22T08:53:32Z on a fresh read-only dump of live (taken 08:53:34Z; 48 tables hold
data), restored as cptg_npred_20261122t085332z on gi4-cpt-test-pg and dropped on exit with its files volume: migrate in the
candidate image applied nothing (still 16 migrations, 0016_fable_coding the last); every encounter's customer view built
by the installed and by the candidate image, 97 and 97, 0 errors, 0 differing; every active membership's session (3), 0
differing but the specialty, which equals the category's name in 3 of 3; stored rounds holding a marked code 0 of 8;
UNRUNNABLE_STAGES stuck 0; RECOMPUTE_STATES 8 coded encounters, none changed, 89 kept; every draft and approved physician
PDF the export rules allow, rendered in both images from exports.snapshot without storing anything: 12 rendered (182 not
ready, 0 errors), 4 to 11 pages, deterministic 12 of 12, 0 vendor strings, and 0 of 194 rows differing between the two
images; no table delta; encounter states awaiting_answer 3, extraction_failed 1, needs_clarification 47, no_codes 4, ready
2, ready_for_review 8, reviewed 32 (neuro-ortho-20261122/predict-n-run1.txt).

**The install rehearsal on a restored copy of live**, every output on file (neuro-ortho-20261122/reh3/, reh3.sh):
rehearse_j.sh setup at 2026-11-22T09:44:03Z on a fresh read-only dump of live restored as cptg_jreh_20261122t094403z,
the revision's test image on 127.0.0.1:9371 with every provider mode and coding disabled (migrate applied nothing; 97
encounters). The two specialties provisioned with the revision's own provision command and the installer's own argument
forms (--specialty, --workspace-name=, --owner-display-name=, --agent-display-name=; provision_copy.sh): table deltas,
exactly, studio_category +2, studio_workspace +2, studio_user +4, studio_membership +4, studio_auditevent +4 (one
account.provisioned per account); nothing else; the four new membership rows exactly as declared below and
Gastroenterology's three unchanged. Every active membership's session and encounter list read in-image by the installed
image and by the revision's: 7 of 7 without an error under each; Gastroenterology's three members list 97 encounters,
each new workspace's members 0; the session's specialty absent under the installed image, the category's name under the
revision's (members-read-prev.txt, members-read-cand.txt). specialty_check_n.py as review-agent-neuro, review-agent-ortho
and Gastroenterology's review-agent: all three pass - each served its own workspace and specialty on the page
(data-specialty and the Specialty field) and in the session, an agent reviewer, the sign-out proven. Two negative controls
fail as they must: review-agent-neuro checked against the Gastroenterology specialty (page.specialty and
session.specialty fail) and against the Gastroenterology workspace (session.workspace fails). The five sign-ins'
footprint, measured: studio_loginattempt +5 and nothing else counted; last_login set on the three agents signed in
(Gastroenterology's review-agent among them); django_session unchanged in count (each sign-out deletes the session the
sign-in made); no membership row changed. Not rehearsed against a copy, because the installer reaches the live database
by construction: the installer-only steps of its provision phase (manage provision as the host user with its read-only
/dev/shm password mounts, the staging and committing of the root-only file through H_ROOT_FILE, the agent file's link).
They are the steps Gastroenterology's provisioning ran on 2026-10-23, the file names now parameterized by specialty
(ops/test_install.py, SpecialtyProvisionTests).

**The switch-back rehearsal on that copy**, after the provisioning and the checks: rehearse_j.sh switchback
9dab92ba0f98: the stack stopped; CLOSE_STAGES closed 0; the installed image's PUT_BACK_STATES changed nothing and its own
API read as the customer answered the list 200 and all 97 encounters 200; forward again, RECOMPUTE_STATES none changed;
encounter states identical throughout; rounds done=8 (reh3/switchback.txt). The installed image reading every
membership's session and list without an error, the new workspaces' among them, is the in-image read above.

**The release package's review** (this declaration, act_n.sh, pre_app_n.sh, post_check_n.sh, baseline_n.sh,
specialty_check_n.py and the evidence, before this commit): two rounds of read-only lenses told to refute, each in a sealed
copy - round 1, two lenses, 19 findings (3 medium: an evidence sentence with no file behind it, and a provisioning phase
able to run out of order); round 2, one lens on the repairs, 5 findings (1 medium, not a regression: the order guard read
an earlier verify, not the newest). No high finding; every finding repaired, each repair self-tested on copies with
synthetic inputs (neuro-ortho-20261122/release-review-dispositions.md).

**The provisioning wrapper**: ops/install.py's provision phase names its files only through credentials_files(specialty),
the specialty one of argparse's three choices; the root helper (H_ROOT_FILE) writes whatever name it is given inside
/etc/cpt-studio, so the new names need no change there; Gastroenterology's two files are never named by a Neurosurgery or
Orthopedic Surgery run (ops/test_install.py, SpecialtyProvisionTests).

## Baseline (read-only, `2026-11-22T10:12:14Z`; re-read immediately before the commit that lands this declaration; this act's preflight receipt and pre_app_n.sh are binding)

Read with these commands, all read-only (the SQL is SELECT only, in a read-only transaction, through the database
container's own psql; counts, names and states only, never a document, response or credential):

    bash /home/claude/cpt-studio-completion-20261106/gemini-migration/neuro-ortho-20261122/baseline_n.sh
    bash scripts/check-cotenants.sh
    docker ps -a --filter label=org.quillmd.cpt-studio=1 --format '{{.Names}} {{.Image}} {{.Status}} {{.Ports}}'
    docker image inspect cpt-studio:9dab92ba0f98 --format '{{.Id}} {{index .Config.Labels "org.opencontainers.image.revision"}}'

baseline_n.sh is install-judge/live_baseline_j.sh unchanged plus this release's rows: every category, every workspace,
every membership (account, category, workspace, role, active), the categories count, the stored-round gate and the
sha256 of Gastroenterology's review-agent credentials file.

    read_at 2026-11-22T10:12:14Z
    transaction_read_only on
    encounters 97
    revisions 98
    source_files 91
    contexts 106
    routing_runs 116
    provider_runs 303
    provider_runs_sent 267
    assessments 186
    proposals 2549
    clarifications 348
    decisions 63
    decision_invalidations 2
    audit_events 1489
    reports 209
    jobs 661
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 124
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
    run_participant anthropic coding_checker succeeded 8
    run_participant anthropic coding_reader succeeded 8
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
    encounter_state awaiting_answer 3
    encounter_state extraction_failed 1
    encounter_state needs_clarification 47
    encounter_state no_codes 4
    encounter_state ready 2
    encounter_state ready_for_review 8
    encounter_state reviewed 32
    run anthropic appraisal succeeded t f 4
    run anthropic coding_checker succeeded t f 8
    run anthropic coding_reader succeeded t f 8
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
    job code succeeded 8
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
    last_audit export.created 2026-11-22T03:26:53Z 24321
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
    current_context_by_version none 9
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
    studio_codinground 8
    studio_codinganswer 0
    studio_codedecision 11
    studio_exportartifact 13
    jobs_code succeeded 8
    runs_coding coding_checker succeeded 8
    runs_coding coding_reader succeeded 8
    interpreter_holds_standing 0
    categories 1
    category gastroenterology gi-profiles@3 present
    workspace gastroenterology Gastroenterology present
    member demo-reviewer gastroenterology Gastroenterology reviewer t
    member owner gastroenterology Gastroenterology owner t
    member review-agent gastroenterology Gastroenterology reviewer t
    marked_stored_rounds 0
    gi_agent_credentials_sha256 765b5aaa2ec60c5a4d1076bd81bad929d0e81647afb1339fd72e13ff4aa7abbe
    --- co-tenants
      🟢 www.quillmd.com      200       200
      🟢 app.quillmd.com      302       302
      🟢 admin.quillmd.com    503       503
      🟢 pro.quillmd.com      410       410
    🟢 every co-tenant answers its expected status (4 distinct codes — the probe discriminates).
    --- containers
    cpt-studio-worker 6e409ad596bc Up 9 hours 8000/tcp
    cpt-studio-web 6e409ad596bc Up 9 hours (healthy) 127.0.0.1:9151->8000/tcp
    cpt-studio-db postgres:17.11-alpine Up 7 days 127.0.0.1:55451->5432/tcp
    --- image
    sha256:6e409ad596bc3bca4d03c55de9e73a9111e9215a5ceb2390096c0d5d2d85bf41 9dab92ba0f98a647b4fb5522e067560ba4e8afd8

## Expected changes, per phase

- **preflight:** none. Its receipt records the baseline: the quillmd-cpt vhost as this installer's HTTPS stage for 9151
  (the physician PDF release's switch left it at sha256 f816a27de9e64af51d6a905484e22fdfc5f13a941a246931261bfc0df1e3ca65);
  9151 held by cpt-studio-web alone and 9150 free; no cpt-studio-web-next; co-tenant routing and
  https://app.quillmd.com/health/.
- **image:** a new local image cpt-studio:`3ce5383ce485`, built from git archive of the revision's cpt-studio/ and
  labelled with the revision. Expected from the test image built the same way: 7 of 11 layers shared with
  cpt-studio:9dab92ba0f98, about 608 MB (608,193,451 bytes); its id differs from the test image's, whose tag and labels
  are not the installer's. The image phase's gate (Django check; the WSGI import) passes. cpt-studio:9dab92ba0f98 is kept.
- **Before app, read-only on the database** (pre_app_n.sh): the declared baseline file must be mode 0600 or 0400 and
  equal, exactly, the baseline part of this declaration's Baseline block (its read_at line up to the co-tenants reading); one `pg_dump -Fc` through the database container's own pg_dump in a
  read-only transaction, 48 TABLE DATA entries; a restore on the test server migrated with the revision's image, where
  nothing applies; the baseline re-read (baseline_n.sh) equals the declared one (read_at, the last audit and the sign-in
  count aside, as post_check_n.sh sets them aside), with no job active, no run
  reserved or sending, no run unreconciled, **no stored round holding a marked code (marked_stored_rounds 0)**, no reading
  job queued or running, and no audit event newer than 10 minutes. Its log ends "PRE-APP PASS"; act_n.sh's app phase
  requires it.
- **app (the blue/green switch):** **migrate applies nothing**; UNRUNNABLE_STAGES finds none; V1_ROWS none;
  INSTALL_COUNTS as the prediction; S1 cpt-studio-web-next starts on 127.0.0.1:9150 and answers /health/ with the
  revision; S2 the old worker parked; S3 the vhost's proxy_pass switched 127.0.0.1:9151 to 127.0.0.1:9150 (sha256 f816a27de9e6... to
  259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, the 9150 form the physician PDF release's preflight
  recorded: the rendering depends on the port alone, and ops/install.py's vhost code is unchanged), `nginx -t` clean, graceful reload, https://cpt.quillmd.com/health/ serving the revision, the co-tenants unchanged; S4 the new
  worker starts with the coding step live, as the live worker does; S5 the old web drained, stopped and parked; S6
  RECOMPUTE_STATES changes nothing (predicted: 8 coded encounters, none changed, 89 kept). The receipt names the replaced
  pair (9dab92ba0f98's web and worker), which a switch-back returns to.
- **verify:** nothing changes.
- **provision-neurosurgery:** the installer's provision phase in the installed image: the workspace category
  neurosurgery (name Neurosurgery, profiles_version fable-coding@1), the workspace "Neurosurgery", owner-neuro (a human
  owner) and review-agent-neuro (an agent reviewer), both active, each with a generated password; one account.provisioned
  audit event per account; /etc/cpt-studio/initial-credentials-neurosurgery.json (root, 0600; both accounts) and
  ~/.cpt-studio/agent-credentials-neurosurgery.json (0600; the agent) written; its receipt and provision log, whose last
  line reads "(Neurosurgery, neurosurgery) created".
- **provision-orthopedic-surgery:** the same for orthopedic-surgery (Orthopedic Surgery, fable-coding@1), the workspace
  "Orthopedic Surgery", owner-ortho and review-agent-ortho, initial-credentials-orthopedic-surgery.json and
  agent-credentials-orthopedic-surgery.json, last line "(Orthopedic Surgery, orthopedic-surgery) created".

**Database deltas against the baseline:** after app and verify, none from the install: every count and every
encounter's stored state unchanged. After both provisioning phases, exactly: users +4, memberships +4, workspaces +2,
categories +2, audit_events +4; four new account rows (owner-neuro human owner active, review-agent-neuro agent reviewer
active, owner-ortho human owner active, review-agent-ortho agent reviewer active); four new membership rows
(owner-neuro and review-agent-neuro in neurosurgery's "Neurosurgery", owner-ortho and review-agent-ortho in
orthopedic-surgery's "Orthopedic Surgery", each with its role, active) and Gastroenterology's three unchanged; two new
category rows (neurosurgery fable-coding@1, orthopedic-surgery fable-coding@1) and two new workspace rows (neurosurgery
Neurosurgery, orthopedic-surgery Orthopedic Surgery); marked_stored_rounds still 0; nothing else. post_check_n.sh judges
both directions - every difference must be declared, and every declared change must have happened exactly - and exits
non-zero on any finding, on /health/ not answering status ok, database ok and the revision, or on a co-tenant change. It judges each against the
declared baseline with neuro-ortho-20261122/act/expected-after-provision-neurosurgery.txt and
expected-after-provision-orthopedic-surgery.txt (these rows, written before the act). A post-check that exits non-zero stops the act until it is judged: it then lists every audit event since the baseline's
last one (event, account, kind, workspace, time; read-only). A member's own activity in the window - an event with that
member as its account, and the rows such an event explains - is named in the report, and the act continues; anything
else, or a row no audit event explains, is THE finding.

## After the install: the specialty check (ordinary use, not a phase)

neuro-ortho-20261122/specialty_check_n.py, with the act checkout's ops/verify_login.py for its transport, against
https://cpt.quillmd.com, three times: as review-agent-neuro (~/.cpt-studio/agent-credentials-neurosurgery.json; workspace
"Neurosurgery", specialty "Neurosurgery"), as review-agent-ortho (~/.cpt-studio/agent-credentials-orthopedic-surgery.json;
"Orthopedic Surgery", "Orthopedic Surgery") and as Gastroenterology's review-agent (walk/review-agent.flat.json;
"Gastroenterology", "Gastroenterology"). Each signs in through the form, reads the page (data-specialty and the Specialty
field must name the specialty) and the session (the workspace's name and specialty, an agent reviewer, can_review true),
signs out and proves the session refused (401). Six requests each; nothing is uploaded, decided or exported, and no
owner's account is signed in. Its database footprint, exactly: studio_loginattempt +3 (the three sign-ins); each sign-in
also sets that account's last_login (Django's own behaviour on every sign-in; review-agent's, review-agent-neuro's and
review-agent-ortho's) and creates a session row that its sign-out deletes (django_session unchanged in count); nothing
else (measured on the rehearsal copy: reh3/).
post_check_n.sh runs once more after it with expected-after-provision-orthopedic-surgery.txt (login attempts are set
aside by the comparison and named here).

## Must not change

Every encounter and every row of every table apart from the provisioning's and the check's rows above;
Gastroenterology's category (gastroenterology, gi-profiles@3), workspace, memberships and accounts (apart from the
review agent's last_login, set by the check's sign-in); Gastroenterology's review-agent
credentials file (its sha256 in the baseline; the installer never names it on these runs); the decisions, coding rounds,
exports, reference sources, facts and passages; the database container and its volumes; every file in /etc/cpt-studio/
other than the two new initial-credentials files; the co-tenants' HTTP answers and https://app.quillmd.com/health/;
every other nginx vhost; every image (nothing is removed).

## Validation per phase

Each receipt is read before the next phase: preflight exit 0 with the baseline above; image exit 0 with the image id
recorded; pre_app_n.sh ending PRE-APP PASS; app exit 0 with migrate applying nothing, the counts as declared, the switch
applied and https://cpt.quillmd.com/health/ serving the revision; verify exit 0; post_check_n.sh after app with no
expected-deltas file: exit 0, 0 unexpected; provision-neurosurgery exit 0 with both accounts created, then post_check_n.sh with
expected-after-provision-neurosurgery.txt: 0 unexpected; provision-orthopedic-surgery exit 0 likewise, then post_check_n.sh
with expected-after-provision-orthopedic-surgery.txt: exit 0, 0 unexpected; then the specialty check, all three pass,
and post_check_n.sh again: exit 0, 0 unexpected; scripts/check-cotenants.sh.

## Rollback per phase, and its limits

- preflight, verify: nothing to undo.
- image: nothing to undo.
- app before the switch: the installer's own undo stops the incoming web and restarts the parked worker.
- app after the switch: the installer's own undo switches back on failure. After a successful app, the incident path is
  `switch-back` (a fresh preflight, then act_n.sh switch-back with SWITCH_BACK_DECISION recorded). The 9dab92ba0f98 pair
  returns with its own modes. Both revisions share the schema, so no coding job is closed and no state changes
  (rehearsed with the new workspaces present: nothing closed, no state changed, the installed image reads all 97
  encounters and every membership's session and list). Under the previous revision the new workspaces' members see that
  revision's page, without the specialty in the session (written limit).
- provisioning: a run refused by manage provision leaves nothing behind (one transaction; the installer discards its
  staged files). One state is different: if the installer fails after its one-shot committed (the provision log shows
  the accounts created) - the root helper's commit failing, say - it discards the staged credentials files and the
  accounts exist with passwords no file holds. The recovery is a second run of that phase with --reset-passwords
  (ops/INSTALL.md), decided and recorded under this declaration by hand; act_n.sh never re-runs a phase on its own.
  After such a recovery the act stops there: the remaining phase and its post-checks run only under an amendment to this
  declaration, committed before they run (the recovery writes its own audit events, which the expected rows here do not
  count). After a successful run the workspaces and accounts stay: the installer has no un-provision, and
  deleting accounts or workspaces is the owner's decision (class d), never part of a rollback. They are harmless to the
  previous revision (rehearsed).
- The receipts, the pre-app dump, the credentials files and the images stay.

## What is not claimed

- Any clinical coding correctness for Neurosurgery or Orthopedic Surgery beyond the four rehearsal documents: the owner
  tests the majority of both specialties (D390 (f)).
- A workspace switcher, an organization level or a subcategory picker (deferred by the owner).
- That a name containing or respelling a specialty's name ("Neurosurgery 2", "Orthopaedic Surgery") is refused by
  provisioning (written limit); the installer runs only the two default names here.
- Past the known limits written in cpt-studio/ARCHITECTURE.md, API.md and ops/INSTALL.md, and in the refutation
  dispositions.

## Stop conditions

- Any phase exiting non-zero.
- A receipt or reading that differs from this declaration: a difference not declared here is THE finding, whatever its
  explanation - apart from a member's own activity, identified from the audit events as above and named in the report.
- migrate applying anything.
- A stored round holding a marked code at pre-app.
- An encounter's stored state changing in app.
- The citation not success in both views.
- A held declaration found.
- Preflight BLOCK, or the installer's preflight refusing.
- The door's ceiling reached.
- A co-tenant's or app.quillmd.com's answer changing.
- The specialty check failing: judged, then reported. A defect found there is fixed under D358 and installed under a new
  declaration, or the site is switched back. It is never patched in place.
