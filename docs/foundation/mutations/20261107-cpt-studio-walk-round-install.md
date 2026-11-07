# Prospective declaration: CPT Studio walk round at cpt.quillmd.com (6f306af1b030 to 73dcf8b4b40a), installed blue/green with the demo kept serving, no migration, and the four retained encounters re-assessed from their retained responses

Authority: the owner's directive of 2026-11-06 ("Continue the existing CPT Studio GI project through completion of the
remaining core repair"), recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's
interpretations. Its required outcome: "a working website where an uploaded GI PDF or Word document is assessed by
Corti, Astra and Fable, supported proposals reach review, decisions persist, and the downloaded report matches those
decisions." Its item 8 asks to "install via the established process with rollback" and to verify the served revision,
worker, records, privacy and workflow; its rules keep cpt.quillmd.com accessible, and its two-cycle rule says: "Do not
abandon the underlying requirement or repeatedly ship the known failure as completion." The installed completion repair
(6f306af1b030) failed its acceptance walk on holds only, with no false READY
(docs/deploy-reports/20261107-cpt-studio-6f306af1-install-and-walk.md, findings 1 to 7). This revision repairs
four of them (1, 5, 6 and 7) in the shared readers; findings 2, 3 and 4 stay open (below). Session a12d8fb3 is the integration and deployment owner.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md
(a protected synthetic demonstration; provider credentials server-side; app.quillmd.com and unrelated services
preserved). CPT Studio stays standalone. No purchase, agreement, new key or payment change is part of this act. D3 to D5
stay open, D7 stays off, and decision (m), checklist item 4.6 and the questions Q1 and Q2 stay the owner's.

Revision to install: 73dcf8b4b40a63a1bb8d95882d4ebc571732be13, the merge commit of PR #1483 (branch fix/cpt-studio-walk-round-20261107, head
4b894a99446fd0da922343b7f6aab743fbb6e749). Image tag cpt-studio:73dcf8b4b40a. Its citation: on 73dcf8b4b40a63a1bb8d95882d4ebc571732be13: CI run 42355210812 success (Fresh application tests; Marketing build; Private browser and accessibility); secrets-scan run 42355210704 success; cpt-studio run 42355210683: its checks, migrations and every test pass (6,417 Django, 524 ops, 43 verification, 135 browser verifier), and its dependency audit is red on pypdf 6.21.2's seven advisories, accounted for and not resolved (docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md); cpt-studio is not a required check. The PR head 4b894a99446fd0da922343b7f6aab743fbb6e749 carries the same tree and the same citation (CI run 42352270101, secrets-scan run 42352270046, cpt-studio run 42352270110).

It replaces the live revision 6f306af1b03049b7adf289bb22918b2dcb765819, installed 2026-11-07 under
docs/foundation/mutations/20261107-cpt-studio-completion-install.md (image cpt-studio:6f306af1b030, kept as the
rollback image).

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 --receipts /home/claude/cpt-studio-install-20261023`.

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

Between 6f306af1b03049b7adf289bb22918b2dcb765819 and 73dcf8b4b40a63a1bb8d95882d4ebc571732be13, these are byte-identical: cpt-studio/deploy/
(Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore); cpt-studio/requirements.txt, requirements.in and
requirements-dev.txt; cpt-studio/cptstudio/; cpt-studio/studio/models.py and cpt-studio/studio/migrations/;
cpt-studio/studio/gi/services.py, gi/catalogue.py, gi/context.py and validation/reconcile.py;
scripts/run-ruled-mutation.sh, scripts/lib/ and scripts/check-cotenants.sh. These change, and are named here:
cpt-studio/studio/gi/structure.py, gi/detect.py, validation/engine.py and studio/api.py (the repairs below), and the
tooling no phase runs: ops/verify_browser.cjs with ops/verification/test_verify_browser.cjs (the walk verifier lists a
code a member's answer excluded).

Before preflight the operator runs, in the act's checkout,
`git diff --quiet 6f306af1b03049b7adf289bb22918b2dcb765819 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/studio/migrations cpt-studio/studio/models.py cpt-studio/studio/gi/services.py cpt-studio/studio/gi/catalogue.py cpt-studio/studio/gi/context.py cpt-studio/studio/validation/reconcile.py`.
Any difference is a stop.

## No migration

The revision adds none: studio_migrations stays 13, last 0013_completion_answer_binding. The app phase's migrate one-shot
applies nothing.

## Delta shipped (6f306af1b030 to 73dcf8b4b40a)

    git diff --stat 6f306af1b03049b7adf289bb22918b2dcb765819 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 -- cpt-studio: 21 files changed, 903 insertions(+), 72 deletions(-)

The files that change what the service does are four, all under cpt-studio/studio/: gi/structure.py, gi/detect.py,
validation/engine.py and api.py. The rest are tests, their pins, the documents and the walk verifier.

The walk round (owner directive 2026-11-06; cpt-studio/HARNESS.md "The walk round (2026-11-07)"; CPT-HARNESS-CHECKLIST.md),
refuted in four rounds of lenses:
- **studio/gi/structure.py** (finding 1): a labelled procedure paragraph is released where it reads as its heading twin
  under four structural gates - P1 reads an E/M visit only outside plan sections; P2 is the installed rule plus the frame
  "after informed consent and a time-out" and at most two preparation statements (the patient's position, a digital
  rectal examination: closed allow-lists); P3 reads a procedure line as declaring its families; N1 no longer reads four
  ordinary words as another time or place.
- **studio/gi/detect.py and studio/validation/engine.py** (finding 5): the closed attempt form's negated-passive failure
  is recognised (detect.closed_attempt_failure), and the engine sets it aside only beside a cited performed act the code
  is matched to, on a lesion the reader tells apart, with the units not exceeding those acts - the code then reads as
  with those passages cited alone; cited alone the failure keeps the installed hold, and routing keeps its installed
  doubt.
- **studio/api.py** (finding 7): POST /api/encounters/{id}/addenda answers {"revision": <number>}, never an internal id.
- **ops/verify_browser.cjs** (finding 6; tooling no phase runs): the walk lists a code a member's answer excluded.
- **Findings 2, 3 and 4 stay OPEN** (U15, U14, U16; ACCURACY-RESIDUALS.md "The walk round"): each approach was refuted
  twice and dropped under the two-cycle rule; studio/gi/services.py, studio/validation/reconcile.py, catalogue.py and
  context.py are byte-identical to the installed revision, and the three shapes read exactly as installed (held).
- **Labels:** gi-routing@9 to @10, cpt-studio-validation@9 to @10; gi-services@6, gi-catalogue@2 and gi-context@4
  unchanged. No proposal fingerprint reads a label.
- **New readings** apply to new uploads, addenda, member saves, the stages they queue, and the four reassessments below.
  The install re-assesses or re-sends no other encounter.

## Measured before this declaration

**Image precheck** (2026-11-07T08:22Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py):
- the image is cpt-studio-precheck:73dcf8b4b40a
  (sha256:459696c7ea7a2416e8c11139fb7ea5071be38366677965ad028bff7266d874f6), built from the merge commit;
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) are CACHED; only the application copy and collectstatic ran;
- its `dpkg-query` list (166 packages, sha256 prefix 500b6abda58b9a3e) is identical to cpt-studio:6f306af1b030's;
- pypdf is 6.21.2 and the uid is 10150.

The builder is not pruned between that measurement and the image phase.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-completion-20261106/install/predict_w.sh
73dcf8b4b40a63a1bb8d95882d4ebc571732be13; output install/predict-merge-73dcf8b4b40a.out), over one read-only `pg_dump -Fc` of the live
database taken through the database container's own pg_dump in a read-only transaction (taken 2026-11-07T08:23:45Z,
sha256 prefix 493b1cb2835884c4, 39 TABLE DATA entries), restored into throwaway databases on the test server
gi4-cpt-test-pg (127.0.0.1:55461), never the live port. The installer's own one-shot scripts run as its app phase runs
them, with every provider disabled:
- **migrate:** "No migrations to apply"; the schema stays at 13 migrations, last 0013.
- **RECOMPUTE_STATES:** {"encounters": 68, "changed": {}} with this revision, with 6f306af1b030's code, again after the
  four reassessments below, and as the rolled-back revision reads the database.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter (0cc6cddb) to
  provider_unknown, so the measurement can see a change.
- **The reassessments of the four encounters,** as the reassess phase makes them (reassess_retained --participants
  astra,fable, then run_worker --once with Astra and Fable live and no credential file, Corti disabled). Each dry run
  names its plan and queues nothing:
  - 39f0ac49: final assessment 4f7fc221-49a4-44c3-ac2c-be8a7c45f7f9; Astra's run a873ac6a-d28d-4c55-bd1c-923bb6f3c8b1 with its peer run 6b3e413f-a546-4ca6-8fcc-27d316868b98; Fable's run cc217632-5157-4bbf-96b3-e94775de1471 with its peer run 6053cb63-d2fa-4d2a-8b91-c81c1bf0c06c;
  - d44a77b3: final assessment cae22e47-49fd-413c-ad58-70ec262c33dc; Astra's run a377a00c-ef75-4b2f-afeb-3fbdda4acad4 with its peer run 233a73f1-10d3-48da-bb13-d4b6a16b8b6f; Fable's run e90a4825-9c96-4f65-844c-1f5f26bd3e17 with its peer run af396ad5-b234-40ea-9db0-f02571b82bae;
  - e888f9ce: final assessment 2dc3665b-9537-4452-85c3-179bd63f32ae; Astra's run 1f17208c-202e-4893-9ff7-6d1e533082c2 with its peer run 3c626b74-bbfd-418b-b8a8-126e4fda49e5; Fable's run 501c3eb3-be62-407b-91d0-eaf690254466 with its peer run 7b9af233-615f-478d-9652-61a6667b88d2;
  - 88d9db32: final assessment 21469f52-c13e-46b2-afcb-1aaf63a55c61; Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2 with its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6; Fable's run 437e6278-4bbc-4b0b-b4a9-727482b7fdbf with its peer run d6a8101c-14fe-4136-ab10-1cabe93a336d.

  The real runs queue one assess job each, and the worker makes them from the retained answers:
  - nothing is sent: runs 174 sent 163 exchanges 147 toolcalls 100 before and after;
  - tables: studio_assessment 123->127 (+4); studio_auditevent 925->933 (+8); studio_job 433->437 (+4); studio_proposal
    1643->1712 (+69); studio_routingrun 83->87 (+4). No other table moves; no decision is invalidated;
  - **39f0ac49** stays ready_for_review: ready 43239, 45380, 45385, 43247, all selected;
  - **d44a77b3** stays ready_for_review: ready 43239, 45385, 45381, 43247, all selected;
  - **e888f9ce** stays ready_for_review: ready 45385, 45380, with no incompleteness flag; its two decisions stay as they
    are (invalidated by the previous install);
  - **88d9db32** stays ready_for_review: ready 45380, 45381, 43239, 43249, 45390, 45385, all selected;
  - no open question on any of the four; the alternatives are informational.

The predictions hold only while the re-read baseline shows no live activity on the four encounters.

## Baseline (read-only, 2026-11-07T08:48:44Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-07T08:48:44Z
    transaction_read_only on
    encounters 68
    revisions 69
    source_files 62
    contexts 85
    routing_runs 83
    provider_runs 174
    provider_runs_sent 163
    assessments 123
    proposals 1643
    clarifications 191
    decisions 51
    decision_invalidations 2
    audit_events 925
    reports 163
    jobs 433
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 84
    reference_sources 2
    reference_facts 34665
    studio_migrations 13
    studio_migration_last 0013_completion_answer_binding
    studio_providerexchange 147
    studio_toolcall 100
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 16
    studio_memberanswerrevocation 1
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
    member_answers_by_value not_documented 9
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 23
    run_participant astra peer_review succeeded 25
    run_participant fable independent succeeded 24
    run_participant fable peer_review succeeded 20
    credits_sum 3.529651999999999851
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 32
    encounter_state no_codes 4
    encounter_state ready_for_review 8
    encounter_state reviewed 23
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded t f 23
    run astra peer_review succeeded f t 1
    run astra peer_review succeeded t f 24
    run corti primary not_sent f f 4
    run corti primary succeeded f t 4
    run corti primary succeeded t f 69
    run corti second_review succeeded t f 2
    run fable independent succeeded t f 24
    run fable peer_review succeeded f t 1
    run fable peer_review succeeded t f 19
    job analyze succeeded 68
    job assess succeeded 123
    job astra cancelled 3
    job astra succeeded 24
    job astra_peer succeeded 25
    job extract succeeded 69
    job fable cancelled 2
    job fable succeeded 24
    job fable_peer succeeded 20
    job predict succeeded 73
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit assessment.created 2026-11-07T05:21:19Z 12445
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
    assessments_by_engine cpt-studio-validation@9 23

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:73dcf8b4b40a, built from git archive of 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 cpt-studio/, labelled with the
  revision, user 10150, CPT_STUDIO_RELEASE_SHA=73dcf8b4b40a63a1bb8d95882d4ebc571732be13; the apt, user, WORKDIR, requirements and pip steps CACHED (as
  measured above); pypdf 6.21.2 and the `dpkg-query` list identical to cpt-studio:6f306af1b030's, checked offline after
  the phase. A build log showing apt or pip ran is a stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database
  through the database container's own pg_dump to /home/claude/cpt-studio-install-20261023/pre-app-73dcf8b4b40a-<UTC>.dump
  (0600); its `pg_restore --list` shows 39 TABLE DATA entries. Kept until a separate, recorded decision removes it.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network; **migrate (a one-shot) applies nothing** ("No migrations to apply"); the queue read finds 0 stages this
    revision cannot run;
  - S1 to S5 as the installer runs them (the incoming web on the idle port answering /health/ with release 73dcf8b4b40a63a1bb8d95882d4ebc571732be13, the
    old worker parked, the vhost's proxy_pass switched, nginx -t clean and a graceful reload, the new worker, the old web
    drained and parked, the incoming renamed);
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    6f306af1b03049b7adf289bb22918b2dcb765819 then 73dcf8b4b40a63a1bb8d95882d4ebc571732be13; non_200_count 0;
  - **states_recomputed {"encounters": <the baseline's encounters>, "changed": {}}** (predicted above). The parked pair
    is removed;
  - nothing is sent: no access check, the one-shots run with every provider disabled;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act (identified
    read-only by encounter and acting account, recorded, set aside); studio_migrations stays 13, last
    0013_completion_answer_binding; studio_workerbeat stays one row named 'worker', its revision 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 once the new
    worker beats.
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line;
  https://cpt.quillmd.com/health/ serves 73dcf8b4b40a63a1bb8d95882d4ebc571732be13 under normal certificate verification, the security headers once each.
- **reassess (the four encounters, one run each for the dry run and the real one):**
  - each dry run names its plan (the final assessment, Astra's and Fable's first readings and peer reviews by id) and
    queues nothing;
  - each real run queues exactly one assess job, which the running worker makes from the retained answers: nothing is
    sent (provider runs, sent runs, provider exchanges, tool calls and credits_sum unchanged); tables together, as
    predicted: studio_assessment +4, studio_auditevent +8, studio_job +4, studio_proposal +69, studio_routingrun +4; no
    other table moves, and **no decision is created, removed or invalidated**;
  - the encounters then read: 39f0ac49 ready_for_review (ready 43239, 45380, 45385, 43247); d44a77b3 ready_for_review
    (ready 43239, 45385, 45381, 43247); e888f9ce ready_for_review (ready 45385, 45380, no incompleteness flag); 88d9db32
    ready_for_review (ready 45380, 45381, 43239, 43249, 45390, 45385); no open question on any.
- Image cpt-studio:6f306af1b030 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessments
build and send no request (their participants' readings are the retained ones). Immediately before app: jobs_active 0;
no provider run reserved or sending; no unreconciled unknown outcome; no audit event newer than 10 minutes. Checked
after app and after each reassess: provider runs, sent runs, provider exchanges, tool calls and credits_sum equal their
pre-app reading; no provider run has a created_at at or after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

The directive's item 7 runs as ordinary use of the installed service, after verify and reassess, by the synthetic agent
accounts review-agent (the customer page) and ops-agent (the operator views).
- **Its inputs:** sealed sets of synthetic documents, each checked by hash before anything reads it:
  - **c3, the independent acceptance evidence:** three documents written by an agent blind to the walk round (it read
    nothing under /opt/meddoc-pro or the session's directory), sealed (mode 0400, directory 0500) at 2026-11-07T03:12:06Z
    in /home/claude/cpt-studio-completion-20261106/acceptance/sealed-c3/. sha256: c3a.txt
    4e6ce67fa4ebbcabcc6f3fbf868da0910d05313c4f4c5b6d55435d8ac06bd66d, c3b.txt
    351f52bab9132695a720cffcde192c14738904548107f75605f6356e42cb6e3a, c3c.txt
    fa812cde2c203f73816cbd0f70a28511f5beb0359f73444be01681b4a3b5095c, expectations-c3.json
    ac58b36736605f203ac53ba84ebce6c18c99e9a26832813679cc81d293bcb075. Nobody read it before the code was frozen. Its
    manifest was built from its expectations alone (acceptance/tools/build_c3_manifest.py, which verifies the four sha256
    values first) at 2026-11-07T08:25:25Z, after this revision was merged and its image precheck and predictions were read; its
    documents are rendered by ops/verification/generate.py (c3a PDF, c3b Word, c3c PDF). One correction was made to that builder
    before c3 was read: its EUS branch could never run, so an EUS code would have been required as the EGD family
    (catalogue.py files it under gi.eus); tested on a fake set.
  - **c1, walked beside it as regression:** three documents written and sealed by this session at 2026-11-06T08:39Z to
    08:40Z (sha256 prefixes c1a 976be07404d0fe93, c1b 477dbbd5679ac420, c1c 2e59f3a1c00fa967, expectations-c1.json
    f131fd2a0bce250a); it exercises a Stop and Resume (c1b), a member's "Not documented" answer and the physician's
    addendum as a new revision (c1c). The session that wrote it also built the repair, so it is never the independent
    evidence.
  - **c2 is not walked again:** offline, c2a and c2b hold 43248 and 43247 exactly as 6f306af1 does (findings 2 and 4,
    open and recorded) and c2c reads as installed; the directive says "Do not repeat identical failing paid attempts".
- **What it sends:** real requests to Corti, Astra and Fable through the existing authorized accounts, one document at a
  time (concurrency one), with the product's own deadlines, Stop and duplicate prevention; its usage and cost are recorded
  from the provider runs it creates.
- **What it claims:** every approval is labelled an agent-executed synthetic review; no human clinical review is claimed.
  A c3 document that carries the shape of an open finding (2, 3 or 4) fails the walk all the same; it is reported as that
  open finding, not hidden.

## Must not change

- Every other encounter's assessments, proposals, clarifications, decisions, reports and audit rows, including the
  six encounters of the 6f306af1 walk and the encounter the owner's account created at 2026-11-07T05:19:12Z
  (840f2215, not opened by this session).
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
- app: the installer's own undo restores the 6f306af1b030 web and worker (rollback-app) and the vhost's proxy_pass. No
  schema changes, so the rolled-back revision reads the database as it does today; its states recompute is predicted
  above.
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting rows.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy and
billing readiness are not claimed, and this act establishes neither.
- Walk findings 2, 3 and 4 stay OPEN (U15, U14, U16): a site-less dilation past the binding's cut in a report of both
  examinations, a coordinated reach after a relative aside, and a bolus "captured and brought out through the mouth" read as
  installed (held, or READY with a false incompleteness warning); completion is not claimed while they are open.
- U17, found by the round's fourth lens and pre-existing on the installed release (the head reads it exactly as
  6f306af1 does): inside a label's binding, "A Savary-Gilliard guide wire was passed ..." with no dilation done, and
  "Savary dilation is usually performed for such strictures", read 43248 READY; recorded, for the next round.
- NCCI PTP stays unconnected: modifiers are considerations only (limitation L2). D3 to D5 and decision (m) stay open.
- The recorded residuals stand (HARNESS.md and ACCURACY-RESIDUALS.md, "The walk round (2026-11-07): what it leaves").
- The cpt-studio workflow's dependency audit stays red on pypdf 6.21.2's seven advisories (limitation L1), accounted for
  in docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved; it is not a required check; no
  readiness for wider or untrusted uploads is claimed.

## Stop conditions

Any of these stops the act: an undeclared count movement; any migration applied; a provider run, exchange or tool call
created by app, verify or reassess; a non-200 availability sample, or a releases_seen other than the two declared;
states_recomputed naming any changed encounter; a build log showing apt or pip ran; a leftover *-previous or *-next
container after app; a dry run that queues a job, or a reassess that queues more than one; any decision invalidated; any
of the four encounters not reading as predicted.
