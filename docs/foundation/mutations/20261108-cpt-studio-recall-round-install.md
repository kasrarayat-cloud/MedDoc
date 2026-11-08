# Prospective declaration: CPT Studio recall round at cpt.quillmd.com (73dcf8b4b40a to aeae34bebbe5), installed blue/green with the demo kept serving, no migration, and the four retained encounters re-assessed from their retained responses

Authority: the owner's directive of 2026-11-06 ("Continue the existing CPT Studio GI project through completion of the
remaining core repair"), recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's
interpretations. Its required outcome: "a working website where an uploaded GI PDF or Word document is assessed by
Corti, Astra and Fable, supported proposals reach review, decisions persist, and the downloaded report matches those
decisions." Its item 8 asks to "install via the established process with rollback" and to verify the served revision,
worker, records, privacy and workflow; its rules keep cpt.quillmd.com accessible, and its two-cycle rule says: "Do not
abandon the underlying requirement or repeatedly ship the known failure as completion." The owner's decision of
2026-11-07 (docs/foundation/RULINGS.md, the row "CPT Studio: the date reader may read more unambiguous date forms";
recorded in full with the session's interpretations (a) to (d) and (b') in the same rulings file) governs the date half.
The installed walk round (73dcf8b4b40a) failed its blind c3 walk 0 of 3 on holds only, with no false READY
(docs/deploy-reports/20261107-cpt-studio-73dcf8b4-install-and-walk.md). Session 30a58364 is the integration and
deployment owner.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md
(a protected synthetic demonstration; provider credentials server-side; app.quillmd.com and unrelated services
preserved). CPT Studio stays standalone. No purchase, agreement, new key or payment change is part of this act. D3 to D5
stay open, D7 stays off, and decision (m), checklist item 4.6 and the questions Q1 and Q2 stay the owner's.

Revision to install: aeae34bebbe57d907ac7870e2456904a6515a2a0, the merge commit of PR #1486 (branch fix/cpt-studio-recall-round-20261107, head
0b8926213ccd01d0e3b4deecf1ef07c57eeb4c73). Image tag cpt-studio:aeae34bebbe5. Its citation: on aeae34bebbe57d907ac7870e2456904a6515a2a0: CI run 42451593902 success (Fresh application tests; Marketing build;
Private browser and accessibility); secrets-scan run 42451593903 success (TruffleHog); cpt-studio run 42451593906: its
checks, migrations and every test pass (6,485 Django, 524 ops, 43 verification, 136 browser verifier), and its
dependency audit is red on pypdf 6.21.2's seven advisories, accounted for and not resolved
(docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md). cpt-studio is not a required check; the four
required ones passed. The PR head 0b8926213ccd01d0e3b4deecf1ef07c57eeb4c73 carries the same tree and the same
citation (CI run 42448918779, secrets-scan run 42448918760, cpt-studio run 42448918825).

It replaces the live revision 73dcf8b4b40a63a1bb8d95882d4ebc571732be13, installed 2026-11-07 under
docs/foundation/mutations/20261107-cpt-studio-walk-round-install.md (image cpt-studio:73dcf8b4b40a, kept as the
rollback image).

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision aeae34bebbe57d907ac7870e2456904a6515a2a0 --receipts /home/claude/cpt-studio-install-20261023`.

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

Between 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 and aeae34bebbe57d907ac7870e2456904a6515a2a0, these are byte-identical: cpt-studio/deploy/ (Dockerfile,
entrypoint, gunicorn, nginx templates, .dockerignore); cpt-studio/requirements.txt, requirements.in and
requirements-dev.txt; cpt-studio/cptstudio/; cpt-studio/studio/models.py, cpt-studio/studio/migrations/ and
cpt-studio/studio/management/; cpt-studio/studio/api.py; cpt-studio/studio/gi/services.py, gi/catalogue.py and
gi/structure.py; cpt-studio/studio/validation/engine.py and validation/reconcile.py; cpt-studio/ops/install.py (the
installer itself); scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh. These change, and are
named here: cpt-studio/studio/gi/context.py, gi/cues.py, gi/detect.py and cpt-studio/studio/jobs.py (the readings and
labels below), and the tooling no phase runs: ops/gi4/freeze.py (the H2 freeze gate, taught the owner-ruled movement),
ops/verify_browser.cjs with ops/verification/test_verify_browser.cjs (the walk waits for a withdrawn answer to read
unsaved).

Before preflight the operator runs, in the act's checkout,
`git diff --quiet 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/studio/migrations cpt-studio/studio/models.py cpt-studio/studio/management cpt-studio/studio/api.py cpt-studio/studio/gi/services.py cpt-studio/studio/gi/catalogue.py cpt-studio/studio/gi/structure.py cpt-studio/studio/validation/engine.py cpt-studio/studio/validation/reconcile.py cpt-studio/ops/install.py`.
Any difference is a stop.

## No migration

The revision adds none: studio_migrations stays 13, last 0013_completion_answer_binding. The app phase's migrate one-shot
applies nothing.

## Delta shipped (73dcf8b4b40a to aeae34bebbe5)

    git diff --stat 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 aeae34bebbe57d907ac7870e2456904a6515a2a0 -- cpt-studio: 24 files changed, 6202 insertions(+), 120 deletions(-)

The files that change what the service does are four, all under cpt-studio/studio/: gi/context.py, gi/cues.py,
gi/detect.py and jobs.py. The rest are tests, their pins, a freeze declaration fixture, the documents and tooling no
phase runs.

The recall round (owner directive 2026-11-06 and the owner's decision of 2026-11-07; cpt-studio/HARNESS.md "The recall
round (2026-11-07)"; CPT-HARNESS-CHECKLIST.md). It measured recall on a development corpus (24 synthetic reports by six
blind authors; the installed release held 36 of 45 expected codes) and a held-out corpus (24 more in six new styles, read
by no designer; the installed release held 25 of 44). Each design was refuted in two cycles under the two-cycle rule, and
two survive:
- **studio/gi/detect.py and studio/gi/cues.py (U19, the findings-stated reach):** a reach stated by findings ("Terminal
  ileum normal.", "Duodenal bulb and D2 normal.") is read for routing only. It applies only where the installed readers
  give a family no extent, never creates an incompleteness, and has a fail-closed cost bound. Development corpus 36 -> 31
  held.
- **studio/gi/context.py (U21, the owner's date forms):** a day-first date with a month name and a four-digit year, and a
  weekday before a readable date, are read under the installed labels. "Exam date" and "Date of Operation" are read in
  the document's head only, and only where the installed reader sends no date, as the document's one date. Two-digit
  years and "11-09-2026" stay unread. Held-out corpus: undated documents 10 -> 0, held codes 25 -> 20, newly held 0.
- **studio/jobs.py (labels):** gi-routing@10 to @11 and gi-context@4 to @5. gi-services@6, gi-catalogue@2 and
  cpt-studio-validation@10 are unchanged. No proposal fingerprint reads a label.
- **A context gi-context@4 recorded stays current.** The final refutation pass showed what that keeps: a @4 context that
  asked, then took a member's date answer, sends it where @5 holds it. Retiring @4 was refuted in its turn before merge:
  - it does not close the participant and peer send doors (U22, pre-existing for @1 to @3);
  - it regressed the encounters @4 read (answers applied with no re-assessment, a withdrawal never applied, a
    reconciliation's attempt lost, second reviews withdrawn).
  The class is bounded instead:
  - **by measurement:** none of the live contexts @4 recorded reads differently under @5. This is measured again on the
    pre-app dump, a stop condition below;
  - **by structure:** nothing records @4 once this revision is installed.
  New readings apply to new uploads, addenda, member saves, the stages they queue, and the four reassessments below. The
  install re-assesses or re-sends no other encounter.
- **The H2 freeze (ops/gi4/freeze.py; tooling no phase runs):** it is taught exactly the owner-ruled movement
  (cpt-studio/tests/fixtures/gi4/declarations/dates-owner-ruling-20261107.json). With that movement the gate holds: 176
  sends and 117 held answers are accepted text by text, NEW-TAKE and SEND->ASK are 0, and the layout, requests and mention
  counts are unmoved.
- **Every second-cycle and final-pass finding left standing on the readers is bounded by parity:** the installed release
  makes the same release on the same text written in its installed twin form (a reach verb or a copula; an installed
  "Procedure date:" label or a month-day-year date). The gi-context@4 class is bounded as above. The two classes the
  retirement's refutation found pre-exist on the installed release and are open (U22, U23), and its rollback limit is
  declared below. Each is recorded in cpt-studio/ACCURACY-RESIDUALS.md, "The recall round" and "The
  recall round: the date half, and the final refutation pass". They include two careless false READYs on the
  development corpus (a2-2 43233 and 43245) and one on the held-out corpus (b3-3 43233, the recorded balloon-size class,
  which the missing date had masked).
- **Dropped, with the requirements kept open:** U20 (numbered PROCEDURE headings) and U18 (labelled release). The
  template field scope, instrument attribution and shorthand, the act vocabulary, and the hold-only false-READY profile
  rules were also dropped. Walk findings U14, U15, U16 and U17 read as installed.
- **ops/verify_browser.cjs (tooling no phase runs):** after a withdrawal the walk waits for the row to read unsaved (the
  walk round's c1c race).

## Measured before this declaration

**Image precheck** (2026-11-08T05:39:55Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py, which builds
exactly as the installer's image phase does):
- the image is cpt-studio-precheck:aeae34bebbe5
  (sha256:de50336de03b3588edc085a9bbc093033366167a2872580e1bd4a6b60aefd702), built from the merge commit;
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) are CACHED; only the application copy and collectstatic ran;
- its package list (`dpkg-query -W -f '${Package} ${Version}\n' | sort`: 166 packages, sha256 prefix 0201a269fab18f06)
  is identical to cpt-studio:73dcf8b4b40a's under the same command;
- pypdf is 6.21.2 and the user is 10150:10150.

The builder is not pruned between that measurement and the image phase. The build cache is 670 MB with 11 MB
reclaimable, far under the preflight check's 30 GB prune trigger.

**The gi-context@4 comparison** (install/cmp/cmp_ctx.py with this revision's code, on the predictions' dump below):
- 35 contexts were recorded under gi-context@4, 31 of them current;
- **0 read differently under @5**, on the facts and on the document date where one is stored (6 current contexts have
  none: they were recorded before migration 0012, and the installed release reads that None too);
- the planted control (a stored service date of origin 'user' changed to another date) is detected;
- a context the installed code made of the class itself (install/cmp/real_control.py: a head "Date of Operation:
  11/05/2026" with the member's 11/09) is detected.

The same comparison runs on the pre-app dump of this act; any difference is a stop before app.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-completion-20261106/install/predict_r.sh
aeae34bebbe57d907ac7870e2456904a6515a2a0; output install/predict-merge-aeae34be.out):
- **the input:** one read-only `pg_dump -Fc` of the live database, taken through the database container's own pg_dump in
  a read-only transaction at 2026-11-08T05:40:10Z (sha256 prefix e013e260edec7a01, 39 TABLE DATA entries);
- **where they ran:** throwaway databases restored from it on the test server gi4-cpt-test-pg (127.0.0.1:55461), never
  the live port, and dropped afterwards;
- **how:** the installer's own one-shot scripts, run as its app phase runs them, with every provider disabled.

What they predict:
- **migrate:** "No migrations to apply"; the schema stays at 13 migrations, last 0013.
- **RECOMPUTE_STATES:** {"encounters": 75, "changed": {}} in every reading: with this revision, with 73dcf8b4b40a's
  code, again after the four reassessments below, and as the rolled-back revision reads the database.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter (fd5c0059) to
  provider_unknown, so the measurement can see a change.
- **Current contexts by version:** gi-context@1 12, @2 24, @3 7, @4 31; one encounter has none.
- **The reassessments of the four encounters,** as the reassess phase makes them (reassess_retained --participants
  astra,fable, then run_worker --once with Astra and Fable live and no credential file, Corti disabled). Each dry run
  names its plan and queues nothing:
  - 39f0ac49: final assessment cd935627-ed41-4d2f-9697-c87444406095; Astra's run a873ac6a-d28d-4c55-bd1c-923bb6f3c8b1 with its peer run 6b3e413f-a546-4ca6-8fcc-27d316868b98; Fable's run cc217632-5157-4bbf-96b3-e94775de1471 with its peer run 6053cb63-d2fa-4d2a-8b91-c81c1bf0c06c
  - d44a77b3: final assessment 4a1f271a-cfec-4e71-a551-d72f9a3516da; Astra's run a377a00c-ef75-4b2f-afeb-3fbdda4acad4 with its peer run 233a73f1-10d3-48da-bb13-d4b6a16b8b6f; Fable's run e90a4825-9c96-4f65-844c-1f5f26bd3e17 with its peer run af396ad5-b234-40ea-9db0-f02571b82bae
  - e888f9ce: final assessment 58c7929c-c23b-45de-aa9c-6d3f90a3b372; Astra's run 1f17208c-202e-4893-9ff7-6d1e533082c2 with its peer run 3c626b74-bbfd-418b-b8a8-126e4fda49e5; Fable's run 501c3eb3-be62-407b-91d0-eaf690254466 with its peer run 7b9af233-615f-478d-9652-61a6667b88d2
  - 88d9db32: final assessment 48fc52f0-c8e1-4414-8f9b-486caf249b66; Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2 with its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6; Fable's run 437e6278-4bbc-4b0b-b4a9-727482b7fdbf with its peer run d6a8101c-14fe-4136-ab10-1cabe93a336d

  The real runs queue one assess job each, and the worker makes them from the retained answers:
  - nothing is sent: runs 209, sent 187, exchanges 180 and tool calls 123, before and after;
  - tables: studio_assessment 143->147 (+4); studio_auditevent 1076->1084 (+8); studio_job 502->506 (+4);
    studio_proposal 1952->2021 (+69); studio_routingrun 94->98 (+4). No other table moves, and no decision is
    invalidated;
  - **39f0ac49** stays ready_for_review: ready 43239, 45380, 45385, 43247, all selected;
  - **d44a77b3** stays ready_for_review: ready 43239, 45385, 45381, 43247, all selected;
  - **e888f9ce** stays ready_for_review: ready 45385, 45380; its two decisions stay as they are;
  - **88d9db32** stays ready_for_review: ready 45380, 45381, 43239, 43249, 45390, 45385, all selected;
  - no open question on any of the four; the alternatives are informational.

The predictions hold only while the re-read baseline shows no live activity on the four encounters.

## Baseline (read-only, 2026-11-08T06:19:11Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-08T06:19:11Z
    transaction_read_only on
    encounters 75
    revisions 76
    source_files 69
    contexts 92
    routing_runs 94
    provider_runs 209
    provider_runs_sent 187
    assessments 143
    proposals 1952
    clarifications 229
    decisions 59
    decision_invalidations 2
    audit_events 1076
    reports 181
    jobs 502
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 91
    reference_sources 2
    reference_facts 34665
    studio_migrations 13
    studio_migration_last 0013_completion_answer_binding
    studio_providerexchange 180
    studio_toolcall 123
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 17
    studio_memberanswerrevocation 2
    studio_operatorgrant 2
    studio_operatorrevocation 0
    studio_workerbeat 1
    column studio_clarification.answer_id present
    column studio_decision.modifiers present
    column studio_encounter.client_key present
    column studio_encountercontext.document_date present
    column studio_memberanswer.question present
    column studio_reportartifact.audience present
    member_answers_standing 15
    member_answers_by_value cannot_confirm 7
    member_answers_by_value not_documented 10
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 30
    run_participant astra peer_review succeeded 32
    run_participant fable independent succeeded 31
    run_participant fable peer_review succeeded 27
    credits_sum 3.891923999999999841
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 36
    encounter_state no_codes 4
    encounter_state ready_for_review 8
    encounter_state reviewed 26
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 3
    run astra independent succeeded t f 27
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 30
    run corti primary not_sent f f 4
    run corti primary succeeded f t 7
    run corti primary succeeded t f 73
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 3
    run fable independent succeeded t f 28
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 25
    job analyze succeeded 75
    job assess succeeded 143
    job astra cancelled 3
    job astra succeeded 31
    job astra_peer succeeded 32
    job extract succeeded 76
    job fable cancelled 2
    job fable succeeded 31
    job fable_peer succeeded 27
    job predict succeeded 80
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit report.generated 2026-11-07T10:33:19Z 71152
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@10 20
    assessments_by_engine cpt-studio-validation@3 12
    assessments_by_engine cpt-studio-validation@4 46
    assessments_by_engine cpt-studio-validation@5 13
    assessments_by_engine cpt-studio-validation@6 15
    assessments_by_engine cpt-studio-validation@7 8
    assessments_by_engine cpt-studio-validation@8 6
    assessments_by_engine cpt-studio-validation@9 23
    contexts_by_version gi-context@1 12
    contexts_by_version gi-context@2 26
    contexts_by_version gi-context@3 19
    contexts_by_version gi-context@4 35
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version none 1
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:aeae34bebbe5, built from git archive of aeae34bebbe57d907ac7870e2456904a6515a2a0 cpt-studio/. It is
  labelled with the revision, user 10150 and CPT_STUDIO_RELEASE_SHA=aeae34bebbe57d907ac7870e2456904a6515a2a0. The apt, user, WORKDIR, requirements and pip
  steps are CACHED, as measured above. pypdf 6.21.2 and the `dpkg-query` list are identical to
  cpt-studio:73dcf8b4b40a's, checked offline after the phase. A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database,
  through the database container's own pg_dump, to
  /home/claude/cpt-studio-install-20261023/pre-app-aeae34bebbe5-<UTC>.dump (0600). Its `pg_restore --list` shows 39 TABLE
  DATA entries. It is kept until a separate, recorded decision removes it. The gi-context@4 comparison
  (install/cmp/cmp_ctx.py with this revision's code) runs on a restore of it on the test server, never the live port:
  0 contexts differing and the planted control detected, or a stop before app. The restore is dropped afterwards.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network;
  - **migrate (a one-shot) applies nothing** ("No migrations to apply");
  - the queue read finds 0 stages this revision cannot run;
  - S1 to S5 as the installer runs them: the incoming web on the idle port answering /health/ with release aeae34bebbe57d907ac7870e2456904a6515a2a0; the
    old worker parked; the vhost's proxy_pass switched, nginx -t clean and a graceful reload; the new worker; the old
    web drained and parked; the incoming renamed;
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    73dcf8b4b40a63a1bb8d95882d4ebc571732be13 then aeae34bebbe57d907ac7870e2456904a6515a2a0; non_200_count 0;
  - **states_recomputed {"encounters": <the baseline's encounters>, "changed": {}}** (predicted above). The parked
    pair is removed;
  - nothing is sent: no access check is run, and the one-shots run with every provider disabled. No stage is queued and
    no context is remade: the contexts by version and the current contexts by version equal the pre-app reading;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act (identified
    read-only by encounter and acting account, recorded, set aside). studio_migrations stays 13, last
    0013_completion_answer_binding. studio_workerbeat stays one row named 'worker'; its revision becomes aeae34bebbe57d907ac7870e2456904a6515a2a0 once
    the new worker beats.
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line.
  https://cpt.quillmd.com/health/ serves aeae34bebbe57d907ac7870e2456904a6515a2a0 under normal certificate verification, with each security header once.
- **reassess (the four encounters, one run each for the dry run and the real one):**
  - each dry run names its plan (the final assessment, Astra's and Fable's first readings and peer reviews by id) and
    queues nothing;
  - each real run queues exactly one assess job, which the running worker makes from the retained answers: nothing is
    sent (provider runs, sent runs, provider exchanges, tool calls and credits_sum unchanged);
  - tables together, as predicted: studio_assessment +4, studio_auditevent +8, studio_job +4, studio_proposal +69,
    studio_routingrun +4. No other table moves, and **no decision is created, removed or invalidated**;
  - the encounters then read: 39f0ac49 ready_for_review (ready 43239, 45380, 45385, 43247); d44a77b3 ready_for_review
    (ready 43239, 45385, 45381, 43247); e888f9ce ready_for_review (ready 45385, 45380); 88d9db32 ready_for_review (ready
    45380, 45381, 43239, 43249, 45390, 45385); no open question on any. These are the readings 73dcf8b4b40a gives, and the
    recall round leaves them as they are.
- Image cpt-studio:73dcf8b4b40a is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessments
build and send no request (their participants' readings are the retained ones). Immediately before app: jobs_active 0;
no provider run reserved or sending; no unreconciled unknown outcome; no audit event newer than 10 minutes. Checked after app, after verify and after each reassess: provider runs, sent runs, provider exchanges, tool calls and
credits_sum equal their pre-app reading; no provider run has a created_at at or after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

The directive's item 7 runs as ordinary use of the installed service, after verify, by the synthetic agent accounts
review-agent (the customer page) and ops-agent (the operator views).
- **Its inputs:** sealed sets of synthetic documents, each checked by hash before anything reads it:
  - **c4, the independent acceptance evidence.** Three documents written by an agent blind to the repair (it read
    nothing under /opt/meddoc-pro or the session's directory), sealed (mode 0400, directory 0500) at
    2026-11-07T10:39Z to 10:40Z in /home/claude/cpt-studio-completion-20261106/acceptance/sealed-c4/. sha256: c4a.txt
    bcf546b4eede02c6a89801327a16009af2b3643a41434de9864b03f2609fb54a, c4b.txt
    87921cac1111ba12d53492cc655c85101d1496c58afaf58ffd6d435b97dbcefa, c4c.txt
    ace79a23db4b5d32a195f20701546f42ffc30be4eacce6d31966f976581464b7, expectations-c4.json
    1e8dcb5f987267b9009d5dc2ae6e7b32070c4e0d8886041bb3d4a3e95bfcb42a.
    - Nobody has read it. The recall round's designs, lenses and corpora never opened it; the corpora were written
      separately.
    - Its manifest is built from its expectations alone, after this revision is installed, by
      acceptance/tools/build_c4_manifest.py, which verifies the four sha256 values first.
    - Its first document carries Stop and Resume: a fresh document, so the panel's Stop is there to press.
    - A question the author expects is answered "Not documented" through the details panel, naming its code.
  - **c1c, walked again as regression.** The walk round's addendum step failed on the walk tool's race, fixed in this
    revision's ops/verify_browser.cjs. The same bytes reuse the retained Corti, Astra and Fable results for the first
    revision (duplicate prevention). The physician's addendum is a new revision, and it is sent.
  - **c3 is not walked again.** Offline, routing and the date on c3a, c3b and c3c read exactly as on 73dcf8b4b40a, so
    their three failures stand (the labelled release U18, the organ-list extent, and the numbered headings U20). The
    directive says "Do not repeat identical failing paid attempts". c2 likewise (U15 and U16 are open).
- **What it sends:** real requests to Corti, Astra and Fable through the existing authorized accounts, one document at a
  time (concurrency one), with the product's own deadlines, Stop and duplicate prevention. Its usage and cost are
  recorded from the provider runs it creates.
- **What it claims:** every approval is labelled an agent-executed synthetic review, and no human clinical review is
  claimed. A c4 document that carries the shape of an open finding fails the walk all the same; it is reported as that
  open finding, not hidden.

## Must not change

- Every other encounter's assessments, proposals, clarifications, decisions, reports and audit rows. App and verify
  queue no stage and remake no context: the contexts by version and the current contexts by version equal the pre-app
  reading after app, after verify and after reassess.
- The reference sources (cms-pfs-rvu26d, cms-mue-practitioner-2026q4) and their facts.
- Users, memberships, workspaces, operator grants, the credentials files and their modes.
- app.quillmd.com, quillmd.com and every co-tenant's status (scripts/check-cotenants.sh before and after).
- The live database's schema.

## Validation per phase

Each phase's receipt is read before the next: preflight, every check passes; image, CACHED steps and the dpkg list as
declared; app, no migration, availability, releases_seen, states_recomputed and the counts as declared; verify, the vhost
and health as declared; reassess, each dry run's plan, then the job, the counts and the readings as declared.

## Rollback per phase, and its limits

- image: nothing to undo; the new image is unused until app.
- app: the installer's own undo restores the 73dcf8b4b40a web and worker (rollback-app) and the vhost's proxy_pass.
  The schema does not change, so the rolled-back revision reads the database as it does today. Its states recompute is
  predicted above. One limit: a context remade under gi-context@5 after the install stays @5. The rolled-back
  revision's earlier list ends at @3, so it reads such a context as current, and it sends a date @5 read in an
  owner-decided form as recorded.
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting rows.
- A rollback limit the refutation found: after a rollback, a context made under @5 whose document date the installed
  release cannot read (an owner-decided form, held against a member's date) is offered "Use document date" by the
  installed release. Taking it clears the member's value and reads no date, so the next request is dateless and the date
  is asked again. It needs a context @5 held on an owner-form head date and then a rollback; the live copy has none.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy and billing
readiness are not claimed, and this act establishes neither.
- U18 and U20 (each approach dropped, the requirement open) and walk findings U14, U15, U16 and U17 stay OPEN and read
  as installed. c3's three failures read as installed offline. Completion is not claimed while they are open.
- U22 and U23 stay OPEN. Both pre-exist on the installed release, and the retirement's refutation found them: the
  participant and peer stages on an earlier context, and answers, withdrawals and reconciliations on an earlier context
  applied without a re-assessment.
- The recall round's residuals stand (cpt-studio/ACCURACY-RESIDUALS.md, "The recall round" and "The recall round: the
  date half, and the final refutation pass"), among them three careless false READYs in the corpora, all bounded by
  parity.
- NCCI PTP stays unconnected: modifiers are considerations only (limitation L2). D3 to D5 and decision (m) stay open.
- The cpt-studio workflow's dependency audit stays red on pypdf 6.21.2's seven advisories (limitation L1), accounted for
  in docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved. It is not a required check, and no
  readiness for wider or untrusted uploads is claimed.

## Stop conditions

Any of these stops the act:
- an undeclared count movement;
- any migration applied;
- a provider run, exchange or tool call created by app or verify;
- a job queued, or a context remade, by app or verify;
- any context gi-context@4 recorded reading differently under @5 on the pre-app dump (install/cmp/cmp_ctx.py with this
  revision's code), or that comparison's planted control not detected: a stop before app;
- a dry run that queues a job, or a reassess that queues more than one; any decision invalidated; any of the four
  encounters not reading as predicted;
- a non-200 availability sample, or a releases_seen other than the two declared;
- states_recomputed naming any changed encounter;
- a build log showing apt or pip ran;
- a leftover *-previous or *-next container after app;
- a difference in the byte-identical list above.
