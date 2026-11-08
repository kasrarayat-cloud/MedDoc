# Prospective declaration: CPT Studio structure round at cpt.quillmd.com (aeae34bebbe5 to c2e53f8e7d33), installed blue/green with the demo kept serving, no migration, and the four retained encounters re-assessed from their retained responses

Authority: the owner's directive of 2026-11-06 ("Continue the existing CPT Studio GI project through completion of the
remaining core repair"), recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md with this session's
interpretations. Its required outcome: "a working website where an uploaded GI PDF or Word document is assessed by
Corti, Astra and Fable, supported proposals reach review, decisions persist, and the downloaded report matches those
decisions." Its item 8 asks to "install via the established process with rollback" and to verify the served revision,
worker, records, privacy and workflow; its rules keep cpt.quillmd.com accessible. The owner's decision of 2026-11-07 (the
date forms) is unchanged by this revision. The installed recall round (aeae34bebbe5) failed its blind c4 walk 0 of 3 on
holds only, each on a recorded open finding (U18 c4a, U16 c4b, U14 c4c), with no false READY
(docs/deploy-reports/20261108-cpt-studio-aeae34be-install-and-walk.md). Session 30a58364 is the integration and
deployment owner.

The install is also governed by the 2026-10-23 directive cited in docs/foundation/mutations/20261023-cpt-studio-install.md
(a protected synthetic demonstration; provider credentials server-side; app.quillmd.com and unrelated services
preserved). CPT Studio stays standalone. No purchase, agreement, new key or payment change is part of this act. D3 to D5
stay open, D7 stays off, and decision (m), checklist item 4.6 and the questions Q1 and Q2 stay the owner's.

Revision to install: c2e53f8e7d33732d5badd4ce9b681f274eb5c471, the merge commit of PR #1489 (branch
fix/cpt-studio-structure-round-20261108, head 676ab3525399f63d9507cce7b406c128fc13522c; the merge commit's tree
65836ed87918877261427a6ae1b148b9b83659b6 equals the head's). Image tag cpt-studio:c2e53f8e7d33. Its citation:
on c2e53f8e7d33732d5badd4ce9b681f274eb5c471: CI run 42525880976 success (Fresh application tests; Marketing build;
Private browser and accessibility) on its second attempt. Its first attempt failed one job only:
rebuild/ops/test_docx_preview_browser.cjs, the QuillMD rebuild's Word preview browser test, timed out on a 12 s
page.waitForFunction. Nothing under rebuild/ changes in this revision, and the same job passed on the PR head's
identical tree. The failed job alone was re-run once at 22:07Z, and every job passed. secrets-scan run 42525880908
success. cpt-studio run 42525881017: its checks, migrations and every test pass (6,607 Django, 524 ops, 43
verification, 136 browser verifier), and its dependency audit is red only on pypdf 6.21.2's seven advisories.
The PR head carries the same tree and the same citation: CI run 42523523177 success (Fresh application tests; Marketing
build; Private browser and accessibility); secrets-scan run 42523523373 success; cpt-studio run 42523523097, whose checks,
migrations and every test pass (6,607 Django, 524 ops, 43 verification, 136 browser verifier) and whose dependency audit
is red only on pypdf 6.21.2's seven advisories (CVE-2026-119203 to CVE-2026-119209, each accounted for in
docs/cpt-harness/repair3-20261105/pypdf-advisories-accounting.md, not resolved). cpt-studio is not a required check.

It replaces the live revision aeae34bebbe57d907ac7870e2456904a6515a2a0, installed 2026-11-08 under
docs/foundation/mutations/20261108-cpt-studio-recall-round-install.md (image cpt-studio:aeae34bebbe5, kept as the
rollback image).

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision c2e53f8e7d33732d5badd4ce9b681f274eb5c471 --receipts /home/claude/cpt-studio-install-20261023`.

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

Between aeae34bebbe57d907ac7870e2456904a6515a2a0 and c2e53f8e7d33732d5badd4ce9b681f274eb5c471, these are byte-identical:
cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore); cpt-studio/requirements.txt,
requirements.in and requirements-dev.txt; cpt-studio/cptstudio/; cpt-studio/studio/models.py, cpt-studio/studio/migrations/
and cpt-studio/studio/management/; cpt-studio/studio/api.py and cpt-studio/studio/jobs.py; cpt-studio/studio/gi/context.py,
gi/cues.py, gi/catalogue.py and gi/sections.py; cpt-studio/studio/validation/engine.py and validation/checks.py;
cpt-studio/ops/install.py (the installer itself); scripts/run-ruled-mutation.sh, scripts/lib/ and
scripts/check-cotenants.sh. These change, and are named here: cpt-studio/studio/gi/detect.py, gi/services.py and
gi/structure.py, and cpt-studio/studio/validation/reconcile.py (its inventory label only) - the readings and labels below;
and the tooling no phase runs: ops/verify_browser.cjs with ops/verification/test_verify_browser.cjs (the walk waits for a
withdrawn answer's row to be served again before an addendum: the recall round's c1c race).

Before preflight the operator runs, in the act's checkout,
`git diff --quiet aeae34bebbe57d907ac7870e2456904a6515a2a0 HEAD -- scripts/check-cotenants.sh scripts/run-ruled-mutation.sh scripts/lib cpt-studio/deploy cpt-studio/requirements.txt cpt-studio/requirements.in cpt-studio/requirements-dev.txt cpt-studio/cptstudio cpt-studio/studio/migrations cpt-studio/studio/models.py cpt-studio/studio/management cpt-studio/studio/api.py cpt-studio/studio/jobs.py cpt-studio/studio/gi/context.py cpt-studio/studio/gi/cues.py cpt-studio/studio/gi/catalogue.py cpt-studio/studio/gi/sections.py cpt-studio/studio/validation/engine.py cpt-studio/studio/validation/checks.py cpt-studio/ops/install.py`.
Any difference is a stop.

## No migration

The revision adds none: studio_migrations stays 13, last 0013_completion_answer_binding. The app phase's migrate one-shot
applies nothing.

## Delta shipped (aeae34bebbe5 to c2e53f8e7d33)

    git diff --stat aeae34bebbe57d907ac7870e2456904a6515a2a0 c2e53f8e7d33732d5badd4ce9b681f274eb5c471 -- cpt-studio: 18 files changed, 4373 insertions(+), 67 deletions(-)

The files that change what the service does are four, all under cpt-studio/studio/: gi/detect.py, gi/services.py,
gi/structure.py and validation/reconcile.py (its label). The rest are tests, the documents and tooling no phase runs.

The structure round (cpt-studio/HARNESS.md "The structure round (2026-11-08)"; CPT-HARNESS-CHECKLIST.md U14, U16, U18 and
U24 to U28). Each repair was designed against a twin-parity bar - the installed release's own reading of the same document
written in a form it already reads - and refuted by fresh lenses under the two-cycle rule:
- **studio/gi/detect.py (U14, walk c4c):** a long reach told with asides is read through its direct-reach twin ("<subject>
  was advanced to <endpoint>."), routed with the motion reader off. The words before the scope noun are read in a closed
  form (a list mark; then, subsequently, thereafter or today; an article with at most three plain words, none of them an
  article); any other lead reads no motion.
- **studio/gi/services.py (U16, walk c4b):** a food bolus removal that today's narrative and Impression corroborate is read
  as its full twin reads it; food introduced in a dated or occasion sentence never binds.
- **studio/gi/structure.py and services.py (U18, walk c4a):** a held labelled paragraph is released only where this tree's
  readers, run on the document's heading twin ("PROCEDURE: <L>" on its own line), read every compared fact exactly as the
  document reads with the release; any difference withdraws every corroborated release. The guard runs only where the
  released paragraphs meet at most 300 sentences and clauses, and clears the services reader's caches at both of its ends.
- **Labels:** gi-routing@11 to @12; gi-services@6 to @7 (with reconcile's source). cpt-studio-validation@10,
  gi-catalogue@2 and gi-context@5 are unchanged; no context is remade or retired. Every engine-parity digest moves with the
  labels alone (byte-identical to the walk round's pins at the installed labels).
- **Withdrawn, recorded open:** U24 (both of its hold forms were integrated and then refuted; reverted before merge), U25,
  U26 and U27 (installed false READYs; every approach refuted or unsound), U28 (an installed blind spot).
- **The mandatory refutation pass over the integrated diff** (four lenses) and **its focused second pass** (two lenses): the
  findings that broke a claim were repaired before merge; the rest are bounded by their twins and recorded in
  cpt-studio/ACCURACY-RESIDUALS.md, "The structure round".
- **Measured offline on the merge commit's tree:** the judge (design-r2/judge-r2.sh) equals the installed release in every
  figure (development corpus 31 of 45 held, 5 careless false READYs, the 2,568-input scan 0 gained and 0 lost, the corpus
  pins 0 moved, the H2 freeze holds, 6 declared H4 movements, 14 replay differences); the walked c4 documents, each expected
  code citing its own act: c4b 43247 and 43239 READY, c4c 43239 READY at D3, c4a 45385 READY with its 43239, 43248 and
  45381 held as its heading twin holds them.

## Measured before this declaration

**Image precheck** (2026-11-08T21:35Z, /home/claude/cpt-studio-ux-tools-20261105/precheck_image.py, which builds exactly as
the installer's image phase does):
- the image is cpt-studio-precheck:c2e53f8e7d33
  (sha256:42cc553aea182af190cc0c6c5a00a9e680437120c2143bde6b9a40fb6f282b30), built from the merge commit;
- steps 2/8 to 6/8 (apt, user, WORKDIR, requirements, pip) are CACHED; only the application copy and collectstatic ran;
- its package list (`dpkg-query -W -f '${Package} ${Version}\n' | sort`: 166 packages, sha256 prefix 0201a269fab18f06)
  is identical to cpt-studio:aeae34bebbe5's under the same command;
- pypdf is 6.21.2 and the user is 10150:10150.

**The gi-context@4 comparison** (install/cmp/cmp_ctx.py with this revision's code, on the predictions' dump below; the
recall round's standing stop condition, repeated at each install):
- 35 contexts were recorded under gi-context@4, 31 of them current;
- **0 read differently under @5** (current 0, not current 0); 6 current contexts store no document date (recorded before
  migration 0012);
- the planted control is detected.
The same comparison runs on the pre-app dump of this act; any difference is a stop before app.

**Offline predictions** with this revision's own code (/home/claude/cpt-studio-completion-20261106/install/predict_s.sh
c2e53f8e7d33732d5badd4ce9b681f274eb5c471; output install/predict-merge-c2e53f8e.out):
- **the input:** one read-only `pg_dump -Fc` of the live database, through the database container's own pg_dump in a
  read-only transaction at 2026-11-08T21:34:52Z (sha256 prefix 4518da24e23e3029, 39 TABLE DATA entries);
- **where they ran:** throwaway databases restored from it on the test server gi4-cpt-test-pg (127.0.0.1:55461), never
  the live port, and dropped afterwards;
- **how:** the installer's own one-shot scripts, run as its app phase runs them, with every provider disabled.

What they predict:
- **migrate:** "No migrations to apply"; the schema stays at 13 migrations, last 0013.
- **RECOMPUTE_STATES:** {"encounters": 79, "changed": {}} in every reading: with this revision, with aeae34bebbe5's code,
  again after the four reassessments below, and as the rolled-back revision reads the database.
- **The control:** one sent run of a reviewed encounter planted 'unknown' turns that encounter (fd5c0059) to
  provider_unknown, so the measurement can see a change.
- **Current contexts by version:** gi-context@1 12, @2 24, @3 7, @4 31, @5 4; one encounter has none.
- **The reassessments of the four encounters,** as the reassess phase makes them (reassess_retained --participants
  astra,fable, then run_worker --once with Astra and Fable live and no credential file, Corti disabled). Each dry run
  names its plan and queues nothing:
  - 39f0ac49: final assessment 9cc29bb6-f039-442f-b2f4-590093b93c3e; Astra's run a873ac6a-d28d-4c55-bd1c-923bb6f3c8b1 with its peer run 6b3e413f-a546-4ca6-8fcc-27d316868b98; Fable's run cc217632-5157-4bbf-96b3-e94775de1471 with its peer run 6053cb63-d2fa-4d2a-8b91-c81c1bf0c06c
  - d44a77b3: final assessment 2987690a-bdee-40b1-8afc-606a11a4583d; Astra's run a377a00c-ef75-4b2f-afeb-3fbdda4acad4 with its peer run 233a73f1-10d3-48da-bb13-d4b6a16b8b6f; Fable's run e90a4825-9c96-4f65-844c-1f5f26bd3e17 with its peer run af396ad5-b234-40ea-9db0-f02571b82bae
  - e888f9ce: final assessment 671378f8-48e2-495b-8e1b-62aa36d51570; Astra's run 1f17208c-202e-4893-9ff7-6d1e533082c2 with its peer run 3c626b74-bbfd-418b-b8a8-126e4fda49e5; Fable's run 501c3eb3-be62-407b-91d0-eaf690254466 with its peer run 7b9af233-615f-478d-9652-61a6667b88d2
  - 88d9db32: final assessment a9799415-4187-4277-999d-9d202a44cf3d; Astra's run f4167034-2d38-4688-a4e1-034b1d11bef2 with its peer run 3fc81ee9-9c2b-4123-bd4c-8a7916ecc5e6; Fable's run 437e6278-4bbc-4b0b-b4a9-727482b7fdbf with its peer run d6a8101c-14fe-4136-ab10-1cabe93a336d

  The real runs queue one assess job each, and the worker makes them from the retained answers:
  - nothing is sent: runs 229, sent 204, exchanges 204 and tool calls 140, before and after;
  - tables: studio_assessment 157->161 (+4); studio_auditevent 1170->1178 (+8); studio_job 545->549 (+4);
    studio_proposal 2157->2226 (+69); studio_routingrun 102->106 (+4). No other table moves, and no decision is
    invalidated;
  - **39f0ac49** stays ready_for_review: ready 43239, 45380, 45385, 43247, all selected;
  - **d44a77b3** stays ready_for_review: ready 43239, 45385, 45381, 43247, all selected;
  - **e888f9ce** stays ready_for_review: ready 45385, 45380; its two decisions stay as they are;
  - **88d9db32** stays ready_for_review: ready 45380, 45381, 43239, 43249, 45390, 45385, all selected;
  - no open question on any of the four; the alternatives are informational.

The predictions hold only while the re-read baseline shows no live activity on the four encounters.

## Baseline (read-only, 2026-11-08T22:13:47Z; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

    read_at 2026-11-08T22:13:47Z
    transaction_read_only on
    encounters 79
    revisions 80
    source_files 73
    contexts 96
    routing_runs 102
    provider_runs 229
    provider_runs_sent 204
    assessments 157
    proposals 2157
    clarifications 259
    decisions 60
    decision_invalidations 2
    audit_events 1170
    reports 189
    jobs 545
    jobs_active 0
    users 5
    memberships 3
    workspaces 1
    login_attempts 96
    reference_sources 2
    reference_facts 34665
    studio_migrations 13
    studio_migration_last 0013_completion_answer_binding
    studio_providerexchange 204
    studio_toolcall 140
    studio_findingconfirmation 0
    studio_passagesource 3
    studio_referencepassage 62
    studio_memberanswer 18
    studio_memberanswerrevocation 3
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
    member_answers_by_value not_documented 11
    run_participant astra independent failed 2
    run_participant astra independent not_sent 1
    run_participant astra independent succeeded 34
    run_participant astra peer_review succeeded 36
    run_participant fable independent succeeded 35
    run_participant fable peer_review succeeded 31
    credits_sum 4.062491999999999826
    usage_keys astra input_tokens,input_tokens_details,output_tokens,output_tokens_details,total_tokens
    usage_keys corti creditsConsumed
    usage_keys fable cache_creation,cache_creation_input_tokens,cache_read_input_tokens,inference_geo,input_tokens,output_tokens,output_tokens_details,service_tier,speed
    encounter_state extraction_failed 1
    encounter_state needs_clarification 40
    encounter_state no_codes 4
    encounter_state ready_for_review 8
    encounter_state reviewed 26
    run astra independent failed t f 2
    run astra independent not_sent f f 1
    run astra independent succeeded f t 4
    run astra independent succeeded t f 30
    run astra peer_review succeeded f t 2
    run astra peer_review succeeded t f 34
    run corti primary not_sent f f 4
    run corti primary succeeded f t 8
    run corti primary succeeded t f 76
    run corti second_review succeeded t f 2
    run fable independent succeeded f t 4
    run fable independent succeeded t f 31
    run fable peer_review succeeded f t 2
    run fable peer_review succeeded t f 29
    job analyze succeeded 79
    job assess succeeded 157
    job astra cancelled 3
    job astra succeeded 35
    job astra_peer succeeded 36
    job extract succeeded 80
    job fable cancelled 3
    job fable succeeded 35
    job fable_peer succeeded 31
    job predict succeeded 84
    job review2 succeeded 2
    runs_unreconciled_unknown 0
    runs_reserved_or_sending 0
    last_audit report.generated 2026-11-08T07:13:30Z 54017
    account demo-reviewer human t reviewer t
    account ops-agent agent t  
    account owner human t owner t
    account platform-operator human t  
    account review-agent agent t reviewer t
    reference_source cms-mue-practitioner-2026q4 cms-mue-practitioner 2026-Q4 15212 40a09bcd128dd18569a0a01e4fc4cffe
    reference_source cms-pfs-rvu26d cms-pfs RVU26D 19453 40a09bcd128dd18569a0a01e4fc4cffe
    assessments_by_engine cpt-studio-validation@10 34
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
    contexts_by_version gi-context@5 4
    current_context_by_version gi-context@1 12
    current_context_by_version gi-context@2 24
    current_context_by_version gi-context@3 7
    current_context_by_version gi-context@4 31
    current_context_by_version gi-context@5 4
    current_context_by_version none 1
    routing_by_version gi-routing@10 11
    routing_by_version gi-routing@11 8
    routing_by_version gi-routing@3 12
    routing_by_version gi-routing@4 38
    routing_by_version gi-routing@5 7
    routing_by_version gi-routing@6 7
    routing_by_version gi-routing@7 7
    routing_by_version gi-routing@9 12

## Expected changes, per phase

- **preflight:** none. One random ACME probe file is written and removed.
- **image:** a new local image cpt-studio:c2e53f8e7d33, built from git archive of c2e53f8e7d33732d5badd4ce9b681f274eb5c471
  cpt-studio/. It is labelled with the revision, user 10150 and CPT_STUDIO_RELEASE_SHA=c2e53f8e7d33732d5badd4ce9b681f274eb5c471.
  The apt, user, WORKDIR, requirements and pip steps are CACHED, as measured above. pypdf 6.21.2 and the `dpkg-query` list
  are identical to cpt-studio:aeae34bebbe5's, checked offline after the phase. A build log showing apt or pip ran is a
  stop before app.
- **Before app, outside the installer and read-only on the database:** one `pg_dump -Fc` of the cptstudio database,
  through the database container's own pg_dump, to
  /home/claude/cpt-studio-install-20261023/pre-app-c2e53f8e7d33-<UTC>.dump (0600). Its `pg_restore --list` shows 39 TABLE
  DATA entries. It is kept until a separate, recorded decision removes it. The gi-context@4 comparison
  (install/cmp/cmp_ctx.py with this revision's code) runs on a restore of it on the test server, never the live port:
  0 contexts differing and the planted control detected, or a stop before app. The restore is dropped afterwards.
- **app (the blue/green switch; ops/INSTALL.md "Phases"):**
  - the loader parses the Corti credentials and each participant's credentials file in the worker's mount layout, with
    no network;
  - **migrate (a one-shot) applies nothing** ("No migrations to apply");
  - the queue read finds 0 stages this revision cannot run;
  - S1 to S5 as the installer runs them: the incoming web on the idle port answering /health/ with release
    c2e53f8e7d33732d5badd4ce9b681f274eb5c471; the old worker parked; the vhost's proxy_pass switched, nginx -t clean and
    a graceful reload; the new worker; the old web drained and parked; the incoming renamed;
  - availability (the public /health/ every 0.5 s, from before S1 to the end): every sample 200; releases_seen
    aeae34bebbe57d907ac7870e2456904a6515a2a0 then c2e53f8e7d33732d5badd4ce9b681f274eb5c471; non_200_count 0;
  - **states_recomputed {"encounters": <the baseline's encounters>, "changed": {}}** (predicted above). The parked
    pair is removed;
  - nothing is sent: no access check is run, and the one-shots run with every provider disabled. No stage is queued and
    no context is remade: the contexts by version and the current contexts by version equal the pre-app reading;
  - counts after app: every count equals the pre-app reading, apart from a member's own use during the act (identified
    read-only by encounter and acting account, recorded, set aside). studio_migrations stays 13, last
    0013_completion_answer_binding. studio_workerbeat stays one row named 'worker'; its revision becomes
    c2e53f8e7d33732d5badd4ce9b681f274eb5c471 once the new worker beats.
- **verify:** no difference from the preflight baseline except the quillmd-cpt vhost's proxy_pass line.
  https://cpt.quillmd.com/health/ serves c2e53f8e7d33732d5badd4ce9b681f274eb5c471 under normal certificate verification,
  with each security header once.
- **reassess (the four encounters, one run each for the dry run and the real one):**
  - each dry run names its plan (the final assessment, Astra's and Fable's first readings and peer reviews by id, as
    listed above) and queues nothing;
  - each real run queues exactly one assess job, which the running worker makes from the retained answers: nothing is
    sent (provider runs, sent runs, provider exchanges, tool calls and credits_sum unchanged);
  - tables together, as predicted: studio_assessment +4, studio_auditevent +8, studio_job +4, studio_proposal +69,
    studio_routingrun +4. No other table moves, and **no decision is created, removed or invalidated**;
  - the encounters then read: 39f0ac49 ready_for_review (ready 43239, 45380, 45385, 43247); d44a77b3 ready_for_review
    (ready 43239, 45385, 45381, 43247); e888f9ce ready_for_review (ready 45385, 45380); 88d9db32 ready_for_review (ready
    45380, 45381, 43239, 43249, 45390, 45385); no open question on any. These are the readings aeae34bebbe5 gives, and the
    structure round leaves them as they are.
- Image cpt-studio:aeae34bebbe5 is kept: it is the rollback image. Nothing removes any image.

## What the install sends

Nothing. No access check is run, every one-shot runs with Corti and the participants disabled, and the reassessments
build and send no request (their participants' readings are the retained ones). Immediately before app: jobs_active 0;
no provider run reserved or sending; no unreconciled unknown outcome; no audit event newer than 10 minutes. Checked after
app, after verify and after each reassess: provider runs, sent runs, provider exchanges, tool calls and credits_sum equal
their pre-app reading; no provider run has a created_at at or after the app receipt's started_at.

## After the install: the acceptance walk (ordinary use, not a phase)

The directive's item 7 runs as ordinary use of the installed service, after verify, by the synthetic agent accounts
review-agent (the customer page) and ops-agent (the operator views).
- **Its inputs:** sealed sets of synthetic documents, each checked by hash before anything reads it:
  - **c5, the independent acceptance evidence.** Three documents written by an agent blind to the repair (it read
    nothing under /opt/meddoc-pro or the session's directory), sealed (mode 0400, directory 0500) at
    2026-11-08T08:07:40Z in /home/claude/cpt-studio-completion-20261106/acceptance/sealed-c5/. sha256: c5a.txt
    5c9b8a60731dbece00980708f3f935de0aaeb5ac4b9a2cc588a1a6625da1aec9, c5b.txt
    f01f38e062f1e2130b920cd2511ff2778fd26d9415b8d48f600bf2b119bad636, c5c.txt
    0c7e0b3fd3a741157285faa9f533125377880bda6f61812f47f43b688c21b12f, expectations-c5.json
    4341e64130a7c8799485dff2ba56dcd381b13ad318d563713e6a23f66449005e. Deliveries: c5a a PDF, c5b a Word document, c5c
    a PDF.
    - Nobody has read it. The structure round's designs, lenses and probes never opened it.
    - Its manifest is built from its expectations alone, after this revision is installed, by
      acceptance/tools/build_c5_manifest.py (C5_SEALED_AT=2026-11-08T08:07:40Z), which verifies the four sha256 values
      first.
    - A question the author expects is answered "Not documented" through the details panel, naming its code.
  - **c4, walked again as the repairs' evidence.** The same bytes reuse the retained Corti, Astra and Fable results for
    the first revision (duplicate prevention), so nothing is sent for them: the walk reads them under this revision's
    readers. Offline, c4b and c4c read every code their walk expects; c4a's 45385 reads READY and its 43239, 43248 and
    45381 stay held (other open classes), so c4a is expected to fail again on those three.
- **What it sends:** real requests to Corti, Astra and Fable for c5 through the existing authorized accounts, one document
  at a time (concurrency one), with the product's own deadlines, Stop and duplicate prevention. Its usage and cost are
  recorded from the provider runs it creates.
- **What it claims:** every approval is labelled an agent-executed synthetic review, and no human clinical review is
  claimed. A c5 document that carries the shape of an open finding fails the walk all the same; it is reported as that
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
- app: the installer's own undo restores the aeae34bebbe5 web and worker (rollback-app) and the vhost's proxy_pass.
  The schema does not change, so the rolled-back revision reads the database as it does today; its states recompute is
  predicted above ({"encounters": 79, "changed": {}}). The contexts are untouched by this revision (gi-context@5 on both).
- reassess: an added assessment is never removed; a wrong reassessment is answered by a new one, never by deleting rows.
  Assessments made under gi-routing@12 and gi-services@7 keep those labels after a rollback; the rolled-back revision
  reads them as stored records.

## What is not claimed

Functional completion on the installed site is judged by verify, reassess and the acceptance walk. Clinical accuracy and
billing readiness are not claimed, and this act establishes neither.
- The structure round's residuals stand (cpt-studio/ACCURACY-RESIDUALS.md, "The structure round" and its final-pass
  sections), among them releases bounded by their twins: U14's endpoint asides and a dated fragment before the motion,
  U16's later events, U18's rider codes, sibling codes a release exposes (c4a's 43450 and 43453, c4b's 43215).
- U24, U25, U26 and U27 (installed false READYs) and U28 (an installed blind spot) stay OPEN and read as installed. U15,
  U17, U19 (c4a's organ-list reach), U20, U22 and U23 stay OPEN. c4a is not expected to walk.
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
