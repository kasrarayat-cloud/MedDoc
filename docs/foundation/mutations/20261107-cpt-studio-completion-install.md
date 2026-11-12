# Prospective declaration: CPT Studio completion repair at cpt.quillmd.com (fd8040d71e44 to 6f306af1b030), installed blue/green with the demo kept serving, migration 0013 applied, and the four retained encounters re-assessed from their retained responses

Authority: the owner's directive of 2026-11-06 ("Continue the existing CPT Studio GI project through completion of the
remaining core repair"), recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's
interpretations. Its required outcome: "a working website where an uploaded GI PDF or Word document is assessed by
Corti, Astra and Fable, supported proposals reach review, decisions persist, and the downloaded report matches those
decisions." Its item 8 asks to "install via the established process with rollback" and to verify the served revision,
worker, records, privacy and workflow; its rules keep cpt.quillmd.com accessible. Session a12d8fb3 is the integration and
deployment owner.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md
(a protected synthetic demonstration; provider credentials server-side; app.quillmd.com and unrelated services
preserved). CPT Studio stays standalone. No purchase, agreement, new key or payment change is part of this act. D3 to D5
stay open, and decision (m) and checklist item 4.6 stay the owner's.

Revision to install: 6f306af1b03049b7adf289bb22918b2dcb765819, the merge commit of PR #1480 (branch fix/cpt-studio-completion-20261106, head
5ba990b3fde477d99a9cda8489333a19c4631b7c). Image tag cpt-studio:6f306af1b030. Its citation: on 6f306af1b03049b7adf289bb22918b2dcb765819: CI run 42322888721 success (Fresh application tests; Marketing build; Private browser and accessibility); secrets-scan run 42322888649 success; cpt-studio run 42322888566: its checks, migrations and every test pass (6,389 Django, 524 ops, 43 verification, 135 browser verifier), and its dependency audit is red on pypdf 6.21.2's seven advisories, accounted for and not resolved (docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md); cpt-studio is not a required check. The PR head 5ba990b3fde477d99a9cda8489333a19c4631b7c carries the same tree and the same citation (CI run 42319122765, secrets-scan run 42319122578, cpt-studio run 42319122544).

It replaces the live revision fd8040d71e448c31ca6762e92ed9714e57aef4e5, installed 2026-11-06 under
docs/foundation/mutations/20261106-cpt-studio-harness-repair3-install.md (image cpt-studio:fd8040d71e44, kept as the
rollback image).

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 6f306af1b03049b7adf289bb22918b2dcb765819 --receipts /home/claude/cpt-studio-install-20261023`.

Phases, in this order: preflight; image; app (with `--provider-mode live --astra-mode live --fable-mode live
--authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`, no `--access-check`); verify; reassess
(`--encounter 39f0ac49-eecc-4c72-bd23-9d542f7f4aa3 --encounter d44a77b3-52fe-40c0-8ccb-2722f87a496b --encounter
e888f9ce-dad1-48ba-a384-028fbe526730 --encounter 88d9db32-65b5-4a55-98ee-b82ce0da8941 --dry-run`, then the same without
`--dry-run`).

Run them from a clean, detached checkout of the merge commit that lands this declaration. That commit must be a descendant
of the revision that changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt
before the next phase. The receipts directory is the live install's own, and no receipt there is changed: each file is
created once.

Not run: secrets, db, reference, provision, http-vhost, cert, https-vhost, rollback-vhost, passages, license-note,
operators and switch-back. Their objects exist and do not change, and nothing in this revision asks for them.

Between fd8040d71e448c31ca6762e92ed9714e57aef4e5 and 6f306af1b03049b7adf289bb22918b2dcb765819, these are byte-identical: cpt-studio/deploy/
(Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore); cpt-studio/requirements.txt, requirements.in and
requirements-dev.txt; cpt-studio/cptstudio/; scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh.
These change, and are named here: cpt-studio/studio/models.py and cpt-studio/studio/migrations/0013_completion_answer_binding.py
(the migration below), cpt-studio/ops/install.py and ops/INSTALL.md (the member-answer rollback hazard's wording and its
read of the stored answer marker; no phase changes), and the tooling no phase runs: ops/verify_browser.cjs with
ops/verification/ (the walk's verifier reads the new customer fields) and ops/gi4/completion.py (the offline completion
report and re-pin tool).

Before preflight the operator runs, in the act's checkout,
`git diff --quiet fd8040d71e448c31ca6762e92ed9714e57aef4e5 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio`
and `git diff --name-only fd8040d71e448c31ca6762e92ed9714e57aef4e5 HEAD -- cpt-studio/studio/migrations cpt-studio/studio/models.py`
must list exactly cpt-studio/studio/migrations/0013_completion_answer_binding.py and cpt-studio/studio/models.py. Any other
difference is a stop.

## The migration

`0013_completion_answer_binding` (additive; `ops/install.py migration_verdict` safe): `studio_memberanswer.question`
(varchar 64, database default '') and `studio_clarification.answer_id` (nullable foreign key to studio_memberanswer,
PROTECT). The previous release's web and worker never read either; a row they insert stays valid. Applied by the app
phase's migrate one-shot before the switch.

## Delta shipped (fd8040d71e44 to 6f306af1b030)

    git diff --stat fd8040d71e448c31ca6762e92ed9714e57aef4e5 6f306af1b03049b7adf289bb22918b2dcb765819 -- cpt-studio: 123 files changed, 76458 insertions(+), 1697 deletions(-)

The files that change what the service does are twenty-one, all under cpt-studio/studio/: eighteen Python modules,
migration 0013, and the customer page's app.js and styles.css. Most of the rest are test fixtures and pins.

The completion repair (owner directive 2026-11-06), integrated from five builders and refuted in four cycles of distinct
lenses and a differential round over the fourth cycle's repair (cpt-studio/HARNESS.md, "Completion repair (2026-11-06)"
through "The differential round over cycle 4's repair"; CPT-HARNESS-CHECKLIST.md, the completion section):
- **studio/gi/structure.py** (new): labelled procedure paragraphs released only where they read as their heading twin
  (layout parity); one derived layout read by routing, the services reader, reconcile and the engine;
  `sections.layout()` unchanged (the freeze gate).
- **studio/gi/clauses.py** (new), **studio/gi/detect.py**, **studio/gi/cues.py**: a sub-act's failure is not the
  examination's, in one closed attempt form read in bounded steps and gated as an instrument course is (I8, I12); the
  instrument's own course as a family mention under its guards; one extent; the services reader's failure words the
  installed three.
- **studio/gi/purpose.py** (new), **studio/gi/services.py**, **studio/gi/catalogue.py**: acts bound to their antecedents
  and outcomes in closed positive forms; placement never overrides outcome; dispositions; purpose time; the dilation
  technique; a labelled paragraph's binding cut at its first later scope sentence.
- **studio/validation/engine.py, reconcile.py, checks.py, review_view.py**: equal eligibility of every proposer's codes;
  competition read alike; truthful reasons; the technique test.
- **studio/validation/questions.py** (new), **studio/answers.py, review.py, jobs.py**, migration 0013: truthful questions
  with their passages; an answer recomputes the assessment (nothing sent); an answer binds to the question it answered
  (its fingerprint), and the engine reads only such an answer to a question no review decision opens or closes - an
  answer stored before the binding, or one to base_included, separate_em or a competition, is the review overlay's, read
  at read time over the current decisions as the installed release reads every answer; a base_included or separate_em
  answer binds by its key in every reader; another code's checks read again without an answered code keep that code's
  fingerprint.
- **studio/customer_api.py, serializers.py, static/studio/app.js, styles.css**: each question shown with its passages, and
  the operator queue's question read as the review overlay leaves it open.
- **ops/install.py, ops/INSTALL.md**: the member-answer rollback hazard.
- **Labels:** gi-routing@7 to @9 (@8 skipped), gi-services@5 to @6, cpt-studio-validation@8 to @9, gi-catalogue@1 to @2;
  gi-context@4 unchanged.
- **New readings** apply to new uploads, addenda, member saves, the stages they queue, and the four reassessments below.
  The install re-assesses or re-sends no other encounter.

## Measured before this declaration

**Image precheck** (2026-11-07T01:14:29Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py): 
- the image is cpt-studio-precheck:6f306af1b030
  (sha256:33ac062ef0b4ec0cbc8997af1638e49feeb608b483ddba72d02a9a501058790e), built from the merge commit;
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) are CACHED; only the application copy and collectstatic ran;
- its `dpkg-query` list (166 packages, sha256 prefix 500b6abda58b9a3e) is identical to cpt-studio:fd8040d71e44's;
- pypdf is 6.21.2 and the uid is 10150.

The builder is not pruned between that measurement and the image phase.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-completion-20261106/install/predict_c.sh
6f306af1b03049b7adf289bb22918b2dcb765819; output install/predict-merge-6f306af1b030.out), over one read-only `pg_dump -Fc` of the live database taken through the
database container's own pg_dump in a read-only transaction (taken 2026-11-07T01:14:30Z, sha256 prefix 0013e9280c3eb3dc, 39 TABLE DATA entries), restored into throwaway databases on the test
server gi4-cpt-test-pg (127.0.0.1:55461), never the live port. The installer's own one-shot scripts run as its app phase
runs them, with every provider disabled:
- **migrate:** applies `studio.0013_completion_answer_binding` and nothing else; the schema then reads 13 migrations, last
  0013, both columns present; the 14 stored member answers carry no fingerprint and no clarification is bound to one.
- **RECOMPUTE_STATES:** {"encounters": 61, "changed": {}} with this revision, with fd8040d71e44's code (no migration),
  again after the four reassessments below, and as the rolled-back revision reads the migrated database.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter (e888f9ce) to
  provider_unknown, so the measurement can see a change.
- **The reassessments of the four encounters,** as the reassess phase makes them (reassess_retained --participants
  astra,fable, then run_worker --once with Astra and Fable live and no credential file, Corti disabled). Each dry run
  names its plan and queues nothing:
  - 39f0ac49: final assessment e5e3b37f-4b40-4371-a3b5-352c8f88eb53; Astra's run a873ac6a-d28d-4c55-bd1c-923bb6f3c8b1 with its peer run 6b3e413f-a546-4ca6-8fcc-27d316868b98; Fable's run cc217632-5157-4bbf-96b3-e94775de1471 with its peer run 6053cb63-d2fa-4d2a-8b91-c81c1bf0c06c;
  - d44a77b3: final assessment 89a8b2a7-2a63-4012-bf7c-bfea626230e4; Astra's run a377a00c-ef75-4b2f-afeb-3fbdda4acad4 with its peer run 233a73f1-10d3-48da-bb13-d4b6a16b8b6f; Fable's run e90a4825-9c96-4f65-844c-1f5f26bd3e17 with its peer run af396ad5-b234-40ea-9db0-f02571b82bae;
  - e888f9ce: final assessment ff5118b1-d081-44b8-893d-033097852d84; Astra's run 1f17208c-202e-4893-9ff7-6d1e533082c2 with its peer run 3c626b74-bbfd-418b-b8a8-126e4fda49e5; Fable's run 501c3eb3-be62-407b-91d0-eaf690254466 with its peer run 7b9af233-615f-478d-9652-61a6667b88d2;
  - 88d9db32: final assessment 986f8be0-359f-454d-96ce-ef44c015093e; Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2 with its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6; Fable's run 437e6278-4bbc-4b0b-b4a9-727482b7fdbf with its peer run d6a8101c-14fe-4136-ab10-1cabe93a336d.

  The real runs queue one assess job each, and the worker makes them from the retained answers:
  - nothing is sent: runs 135 sent 124 exchanges 97 toolcalls 67 before and after;
  - tables: studio_assessment 100->104 (+4); studio_auditevent 744->752 (+8); studio_decisioninvalidation 0->2 (+2); studio_job 354->358 (+4); studio_proposal 1308->1377 (+69); studio_routingrun 71->75 (+4). No other table moves;
  - **39f0ac49** goes from reviewed to **ready_for_review**: ready 43239, 45380, 45385, 43247, all selected;
  - **d44a77b3** goes from needs_clarification to **ready_for_review**: ready 43239, 45385, 45381, 43247, all selected;
  - **e888f9ce** goes from reviewed (2 decisions) to **ready_for_review**: ready 45385, 45380, with no
    incompleteness flag; its two decisions are invalidated (the two studio_decisioninvalidation rows above);
  - **88d9db32** stays ready_for_review: ready 45380, 45381, 43239, 43249, 45390, 45385, all selected;
  - no open question on any of the four; the alternatives are informational.

The predictions hold only while the re-read baseline shows no live activity on the four encounters.

## Baseline (read-only, 2026-11-07T01:48:58Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-07T01:48:58Z
    transaction_read_only on
    encounters 61
    revisions 61
    source_files 55
    contexts 77
    routing_runs 71
    provider_runs 135
    provider_runs_sent 124
    assessments 100
    proposals 1308
    clarifications 160
    decisions 41
    decision_invalidations 0
    audit_events 744
    reports 145
    jobs 354
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 80
    reference_sources 2
    reference_facts 34665
    studio_migrations 12
    studio_migration_last 0012_cux_worker_beat
    studio_providerexchange 97
    studio_toolcall 67
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 14
    studio_memberanswerrevocation 0
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_reportartifact.audience present
    column studio_clarification.answer_id absent
    column studio_memberanswer.question absent
    member_answers_standing 14
    member_answers_by_value cannot_confirm 7
    member_answers_by_value not_documented 7
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 15
    run_participant astra peer_review succeeded 17
    run_participant fable independent succeeded 16
    run_participant fable peer_review succeeded 13
    credits_sum 3.164167999999999860
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 29
    encounter_state no_codes 4
    encounter_state ready_for_review 5
    encounter_state reviewed 22
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded t f 15
    run astra peer_review succeeded f t 1
    run astra peer_review succeeded t f 16
    run corti primary not_sent f f 4
    run corti primary succeeded f t 4
    run corti primary succeeded t f 61
    run corti second_review succeeded t f 2
    run fable independent succeeded t f 16
    run fable peer_review succeeded f t 1
    run fable peer_review succeeded t f 12
    job analyze succeeded 60
    job assess succeeded 100
    job astra cancelled 3
    job astra succeeded 16
    job astra_peer succeeded 17
    job extract succeeded 61
    job fable cancelled 1
    job fable succeeded 16
    job fable_peer succeeded 13
    job predict succeeded 65
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit report.generated 2026-11-06T05:26:43Z 73334
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:6f306af1b030, built from git archive of 6f306af1b03049b7adf289bb22918b2dcb765819 cpt-studio/, labelled with
  the revision, user 10150, CPT_STUDIO_RELEASE_SHA=6f306af1b03049b7adf289bb22918b2dcb765819; the apt, user, WORKDIR, requirements and pip steps CACHED
  (as measured above); pypdf 6.21.2 and the `dpkg-query` list identical to cpt-studio:fd8040d71e44's, checked offline
  after the phase. A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database
  through the database container's own pg_dump to /home/claude/cpt-studio-install-20261023/pre-app-6f306af1b030-<UTC>.dump
  (0600); its `pg_restore --list` shows 39 TABLE DATA entries. Kept until a separate, recorded decision removes it.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network; **migrate (a one-shot) applies `studio.0013_completion_answer_binding` and nothing else**; the queue read
    finds 0 stages this revision cannot run;
  - S1 to S5 as the installer runs them (the incoming web on the idle port answering /health/ with release 6f306af1b03049b7adf289bb22918b2dcb765819,
    the old worker parked, the vhost's proxy_pass switched, nginx -t clean and a graceful reload, the new worker, the old
    web drained and parked, the incoming renamed);
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    fd8040d71e448c31ca6762e92ed9714e57aef4e5 then 6f306af1b03049b7adf289bb22918b2dcb765819; non_200_count 0;
  - **states_recomputed {"encounters": <the baseline's encounters>, "changed": {}}** (predicted above; the 14 stored
    answers carry no fingerprint, so the review overlay reads them exactly as the installed release does and no settled
    record reopens). The parked pair is removed;
  - nothing is sent: no access check, the one-shots run with every provider disabled;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act (identified
    read-only by encounter and acting account, recorded, set aside); **studio_migrations 12 to 13, last
    0013_completion_answer_binding; columns studio_memberanswer.question and studio_clarification.answer_id present**
    (every stored answer's question '', every clarification's answer null); studio_workerbeat stays one row named
    'worker', its revision 6f306af1b03049b7adf289bb22918b2dcb765819 once the new worker beats.
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line;
  https://cpt.quillmd.com/health/ serves 6f306af1b03049b7adf289bb22918b2dcb765819 under normal certificate verification, the security headers once each.
- **reassess (the four encounters, one run each for the dry run and the real one):**
  - each dry run names its plan (the final assessment, Astra's and Fable's first readings and peer reviews by id) and
    queues nothing;
  - each real run queues exactly one assess job, which the running worker makes from the retained answers: nothing is
    sent (provider runs, sent runs, provider exchanges, tool calls and credits_sum unchanged); tables together, as
    predicted: studio_assessment 100->104 (+4); studio_auditevent 744->752 (+8); studio_decisioninvalidation 0->2 (+2); studio_job 354->358 (+4); studio_proposal 1308->1377 (+69); studio_routingrun 71->75 (+4);
  - **e888f9ce's two current decisions (the 2026-11-05 walk's agent-executed synthetic approvals of 45385 and 45380) are
    invalidated** by the existing fingerprint rule (review._carry_decisions: a decision carries only to a proposal whose
    fingerprint is unchanged; its proposals' checks moved): two studio_decisioninvalidation rows, each with its recorded
    reason; the decision rows stay. No other decision is created, removed or invalidated;
  - the encounters then read: 39f0ac49 ready_for_review (ready 43239, 45380, 45385, 43247); d44a77b3 ready_for_review (ready 43239, 45385, 45381, 43247); e888f9ce ready_for_review (ready 45385, 45380, no incompleteness flag); 88d9db32 ready_for_review (ready 45380, 45381, 43239, 43249, 45390, 45385); no open question on any.
- Image cpt-studio:fd8040d71e44 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessments
build and send no request (their participants' readings are the retained ones). Immediately before app: jobs_active 0;
no provider run reserved or sending; no unreconciled unknown outcome; no audit event newer than 10 minutes. Checked
after app and after each reassess: provider runs, sent runs, provider exchanges, tool calls and credits_sum equal their
pre-app reading; no provider run has a created_at at or after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

The directive's item 7 runs as ordinary use of the installed service, after verify and reassess, by the synthetic agent
accounts review-agent (the customer page) and ops-agent (the operator views).
- **Its inputs:** two sealed sets of synthetic documents, each checked by hash before anything reads it:
  - **c2, the independent acceptance evidence:** three documents written by an agent blind to the repair (it read
    nothing under /opt/meddoc-pro or the session's directory), sealed (mode 0400, directory 0500) at 2026-11-06T14:11:22Z
    in /home/claude/cpt-studio-completion-20261106/acceptance/sealed-c2/. sha256: c2a.txt
    358e42f28f26a4e1b66a566b130bce275d3b73387d5ab4ac808384bd8cd714ae (PDF), c2b.txt
    811efefbb15f95184fbe6c11686cce5221820e964130779a0423b6882631fbef (PDF), c2c.txt
    2c884ef1a2d1462b66257cd0230b781314b81cdf08597403cc61f372d81b0070 (Word), expectations-c2.json
    7174de3cdfb579c543808549c1d5f1dfa768f1031419206b79fdd5fb844af718. Nobody read it before the code was frozen. Its
    manifest was built from its expectations alone (acceptance/tools/build_c2_manifest.py, which verified the four sha256
    values) at 2026-11-07T01:19Z, after this revision was merged and its image precheck and predictions were read; its
    documents were rendered by ops/verification/generate.py. Nothing in the code has changed since.
  - **c1, walked beside it:** three documents written and sealed by this session at 2026-11-06T08:39Z to 08:40Z, before
    the repair's code existed (sealed/; sha256 prefixes c1a 976be07404d0fe93, c1b 477dbbd5679ac420, c1c 2e59f3a1c00fa967,
    expectations-c1.json f131fd2a0bce250a). The session that wrote it also integrated the repair, so it is never the
    independent evidence.
- **What it sends:** real requests to Corti, Astra and Fable through the existing authorized accounts, one document at a
  time (concurrency one), with the product's own deadlines, Stop and duplicate prevention; its usage and cost are recorded
  from the provider runs it creates. A Stop and Resume (c1b), a member's "Not documented" answer and the physician's
  addendum as a new revision (c1c) are exercised through the ordinary page.
- **What it claims:** every approval is labelled an agent-executed synthetic review; no human clinical review is claimed.

## Must not change

- Every other encounter's assessments, proposals, clarifications, decisions, reports and audit rows.
- The reference sources (cms-pfs-rvu26d, cms-mue-practitioner-2026q4) and their facts.
- Users, memberships, workspaces, operator grants, the credentials files and their modes.
- app.quillmd.com, quillmd.com and every co-tenant's status (scripts/check-cotenants.sh before and after).
- The live database's schema beyond migration 0013's two columns.

## Validation per phase

Each phase's receipt is read before the next: preflight, every check passes; image, CACHED steps and the dpkg list as
declared; app, the migration, availability, releases_seen, states_recomputed and the counts as declared; verify, the vhost
and health as declared; reassess, each dry run's plan, then the job, the counts, the invalidations and the readings as
declared.

## Rollback per phase, and its limits

- image: nothing to undo; the new image is unused until app.
- app: the installer's own undo restores the fd8040d71e44 web and worker (rollback-app) and the vhost's proxy_pass. The
  migration stays applied: its two columns are additive, the previous release never reads them, and a row it inserts
  stays valid. The rolled-back revision recomputes states (predicted above: the rollback read changes no encounter).
  ⚠️ An assessment this release re-made with a member's answer carries support 'answered', which the previous release
  reads as an ordinary exclusion that holds nothing: the installer's undo names it ('member_answer'), and such an encounter
  is re-assessed after a rollback. None exists at install time.
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting rows.
  The two invalidated e888f9ce decisions stay invalidated; the walk encounter is re-reviewed, never restored by hand.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy and
billing readiness are not claimed, and this act establishes neither.
- NCCI PTP stays unconnected: modifiers are considerations only (limitation L2). D3 to D5 and decision (m) stay open.
- The recorded residuals stand (HARNESS.md: the base's own false READYs this release does not close, the recorded false
  holds, the owner's questions Q1, Q2 and 4.6).
- The cpt-studio workflow's dependency audit stays red on pypdf 6.21.2's seven advisories (limitation L1), accounted for
  in docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved; it is not a required check; no
  readiness for wider or untrusted uploads is claimed.

## Stop conditions

Any of these stops the act: an undeclared count movement; a migration other than 0013; a provider run, exchange or tool
call created by app, verify or reassess; a non-200 availability sample, or a releases_seen other than the two declared;
states_recomputed naming any changed encounter; a build log showing apt or pip ran; a leftover *-previous or *-next
container after app; a dry run that queues a job, or a reassess that queues more than one; a decision invalidated other
than e888f9ce's two; any of the four encounters not reading as predicted.
