# Prospective declaration: CPT Studio GI core upgrade at cpt.quillmd.com (2734a6f3 to 2b82889fea5870921062cf31eefa0c0ad78a1c31)

Authority: the owner's directive of 2026-10-27 recorded in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md
("Carry the work through implementation, installation and meaningful verification", "Coordinate deployment through
one owner", "Keep app.quillmd.com, VoiceAssistMain and unrelated server resources unchanged", "After installation,
perform purposeful fresh synthetic tests through the ordinary HTTPS interface: upload, processing, review, saved
decisions, reload and actual report download", "Use the existing standing authority for necessary private synthetic
testing"). The same file records the owner's decision of 2026-10-27 in session ec5e7910, "Narrow, install-first
(Recommended)" ("Then tests, PR, CI, merge, install, and a fresh HTTPS Word/PDF walk with real downloads"), and
session interpretation 25, which made ec5e7910 the single owner of this branch, its install and its live
verification, and interpretation 26 (session 7c8d38da is that single owner from 2026-10-27 19:20Z, after ec5e7910
stopped at its account's weekly limit). The install itself is governed by the 2026-10-23 directive cited in
docs/foundation/mutations/20261023-cpt-studio-install.md: a protected synthetic demonstration that uses the existing
authorized Corti account, keeps provider credentials server-side and preserves app.quillmd.com and unrelated
services. CPT Studio stays standalone: no QuillMD source, database, users, files, units or environment are shared,
promoted or edited. No purchase, agreement, new ACME account, new key, payment change or real-patient processing is
part of this act. The installer sends no provider request (see "What the install sends").

Revision to install: 2b82889fea5870921062cf31eefa0c0ad78a1c31, the merge commit of PR #1440 (branch
fix/cpt-studio-gi-service-core-20261027); image tag cpt-studio:2b82889fea58. It replaces the live revision
2734a6f31ce0e7865a93c3597a09621d16cac0a1. That revision was installed 2026-10-26 22:18:39Z-22:22:25Z from 057a7d398
under docs/foundation/mutations/20261023-cpt-studio-install.md at f6df8aae0. It runs image cpt-studio:2734a6f31ce0
(sha256:36c5bf19ff2a), web ca8c24a2c77f, worker d1dbcddf67e5 and database 1c5498b3aacc. That declaration and its
receipts stay as they are.

Execute each phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 2b82889fea5870921062cf31eefa0c0ad78a1c31
--receipts /home/claude/cpt-studio-install-20261023`, in this order: preflight, image, app (with
`--provider-mode live --authorization-ref docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`), verify. Run them
from a clean, detached checkout of the merge commit that lands this declaration: a descendant of the revision that
changes nothing under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next
phase. The receipts directory is the live install's own (ops/INSTALL.md, "Reinstalling a new revision"), so the
vhost receipts that rollback-vhost needs stay beside the new ones. No receipt there is changed: each file is
created once.

Not run, because their objects exist and this revision does not change them: secrets, db, reference, provision,
http-vhost, cert and https-vhost. cpt-studio/deploy/ (Dockerfile, entrypoint, gunicorn, nginx templates,
.dockerignore) is identical at both revisions. The HTTPS stage rendered from either revision is
259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c, byte-identical to the live
/etc/nginx/sites-available/quillmd-cpt. ops/INSTALL.md describes every check.

## Delta shipped (2734a6f3 to 2b82889fea5870921062cf31eefa0c0ad78a1c31; refresh at commit time)

- Figures at the PR head 518ed7138 (2026-10-28), whose cpt-studio/ tree the merge commit must carry unchanged (checked
  at the merge): 200 branch commits after 057a7d398; 156 files under cpt-studio/, 121 of them under tests/. Outside
  cpt-studio/, only docs/foundation/ files change (the ruling file, RULINGS.md and the bc7df129 handoff). main also
  carries 97abb5959 (#1441: rebuild/requirements.txt msgpack 1.2.2 to 1.2.3, CVE-2026-114613), outside cpt-studio/
  and outside this act.
- Runtime changes: studio/jobs.py, api.py, serializers.py, review.py, reports.py (report format @4), models.py,
  types.py, static/studio/app.js, gi/ (context, cues, detect, profiles, sections; new services.py and catalogue.py)
  and validation/ (checks, engine, rationale; new reconcile.py). cptstudio/settings.py adds 'review2': 180 to
  JOB_DEADLINE_SECONDS. cptstudio/urls.py adds POST api/encounters/<id>/second-review. ops/install.py and
  ops/INSTALL.md add 2af1f834d's queue check and rollback, and refutation phase 1's rollback rules (UNDO_HAZARDS
  'unknown', 'outcome', 'conflict', 'second_review'; a failure path that leaves the restored worker stopped while such
  records exist; stages of a kind the next worker cannot run closed whichever pair created them) and the app phase's
  state recompute (RECOMPUTE_STATES); refutation phase 2 adds the put-back of states the older revision labels
  otherwise (CLOSE_STAGES 'relabel', put_back_states, INSTALLED_STATES), the refusal reasons 'second_review_refused'
  and 'second_review_unread' (UNDO_HAZARDS, SHOWN_HAZARDS), the recompute before the parked pair's removal
  (retire_parked) and a post-swap failure receipt that says whether the states were recomputed (after_swap_failure).
  ops/verify_browser.cjs and ops/verify_downloads.py read report format @4.
- Unchanged at 518ed7138 (re-checked 2026-10-28), to be re-checked at 2b82889fea5870921062cf31eefa0c0ad78a1c31: deploy/, requirements.txt,
  requirements.in and requirements-dev.in (requirements-dev.txt moves msgpack 1.2.2 to 1.2.3 for CVE-2026-114613: a
  dev and CI pin, never installed in the image, whose Dockerfile installs requirements.txt only),
  studio/providers/ (so the Corti request contract and credential loader are the installed ones),
  studio/reference/, studio/management/, studio/ingest/, intake.py, storage.py, bounded.py, audit.py, access.py,
  views.py, templates/ and cptstudio/wsgi.py. No new environment variable, secret, mount, port or container
  limit.
- Migrations. The live database has applied studio 0001-0005 (django_migrations: 5 rows for studio). Every
  migration after the installed one is listed here, and there is exactly one:
  0006_services_completeness_second_review. It adds:
  - studio_assessment.completeness, JSON, default {};
  - studio_assessment.second_run, a nullable FK to studio_providerrun (PROTECT);
  - studio_assessment.services, JSON, default {};
  - studio_proposal.support, JSON, default {};
  - studio_providerrun.purpose, varchar(16), default 'primary';
  - studio_providerrun.scope, JSON, default {}.
  It then sets database-level defaults on the five non-null columns ('{}'::jsonb four times, 'primary' once), so
  any row the 2734a6f3 pair inserts between the migration and the swap stays valid. It is schema-only: there is no
  RunPython and no new model, so no row is added, removed or rewritten, and no contenttype or permission row
  appears. Existing rows read the new columns' defaults. At commit time,
  `git ls-tree --name-only 2b82889fea5870921062cf31eefa0c0ad78a1c31 cpt-studio/studio/migrations/` must list 0001-0006 and `__init__.py` only.
  If it lists more, this section is wrong and must be rewritten before the commit.

## Baseline (read-only, re-read 2026-10-28T18:08Z before the commit; this act's preflight receipt is binding)

- Live database (bc7df129's tools/live_counts.sh, SELECT only, 18:08:56Z): encounters 12, revisions 12,
  source_files 10, provider_runs 12, provider_runs_sent 12, assessments 12, proposals 148, decisions 15,
  clarifications 3, audit_events 113, reports 36, jobs 48, jobs_active 0, users 2, reference_sources 2,
  reference_facts 34665, studio_migrations 5, credits_sum 0.600300. Against the 2026-10-27T16:23Z reading one
  encounter was added: 6906e06f, the Elena PDF uploaded again on 2026-10-27 at 23:51Z with a member service date of
  1990-11-11, which the installed revision sent (its one run, succeeded); its state is needs_clarification. Nothing
  else moved.
- States (SELECT only):
  - jobs: 12 each of extract, analyze, predict and assess, all succeeded;
  - provider runs: 12, all succeeded and sent; none reserved or sending; no unreconciled unknown outcome;
  - encounters: reviewed 7, needs_clarification 3, ready_for_review 1, no_codes 1;
  - last job created 2026-10-27T23:51:21Z; last audit event 2026-10-27T23:51:21Z (idle 18 hours at the reading).
- /etc/nginx (this revision's installer, nginx_file_state, read-only): sites-available sha256 identical to the
  2026-10-27 draft and the 2026-10-26 preflight:
  - dealhunter cbc089226d5f9f55f3543ee277f16e7e91f08f2ea6737141d7471e155b3c4ebd;
  - dealmason 6fd1916b6444caf394d30f49fe7d3e943b5cdf322e0bfe009bb5bd7724979c74;
  - default ce0901350a021608139b5639cf4ccd7717bef8c3a9e4f79031eb46386b67b03f;
  - leathererp 31988a1ddea72ae44c7dd92aa707424e5a64c8ddd692721476ef3a5a6221e791;
  - quillmd e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638;
  - quillmd-cpt 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c;
  - quillmd-email-preview c212671e1f33b5b8cbde914e67f546d72ab1241fa829de3ec2587f4b8cfa9b1a;
  - quillmd-staging 965e41b7398c0dfd667826a2fa2f18f4d61fc323a87234981dbd33379c5275ad;
  - voice.kasitcorp.com 051f70eaec42aa7c7736cefb59668b9b082989ca076c31924a320635600f96eb;
  - quillmd-email-preview.htpasswd: unreadable, presence only.

  nginx.conf 196a622ce459de81985338b381d55f5ba357bfa3d7a22a56551c76a4b5504dca; conf.d empty; `nginx -t` ok with
  exactly the two existing warnings ("protocol options redefined for 0.0.0.0:443" in sites-enabled/quillmd:24 and
  sites-enabled/voice.kasitcorp.com:28).
- sites-enabled: dealhunter, dealmason, leathererp, quillmd (../sites-available/quillmd), quillmd-cpt
  (/etc/nginx/sites-available/quillmd-cpt), quillmd-email-preview, quillmd-staging, voice.kasitcorp.com.
- Network (the installer's own read-only probes, 2026-10-28 ~18:10Z): 55 local routing entries; app.quillmd.com
  /health/ 200, release 67acb2628b84; scripts/check-cotenants.sh rc 0 (quillmd.com 200, www 200, app 302, admin
  503, pro 410); cpt.quillmd.com /health/ {status ok, service cpt-studio, data_mode synthetic-only, database ok,
  release 2734a6f31ce0e7865a93c3597a09621d16cac0a1}; DNS for cpt.quillmd.com A 147.189.172.8 only, no AAAA. At this
  reading the co-tenant voice.kasitcorp.com answers 502 on 443 (its own state); verify compares the routing with
  preflight, not with this reading.
- Docker: 60 containers (21 running), 41 volumes, 14 networks, the same counts as the 2026-10-27 reading. CPT Studio
  objects:
  - cpt-studio-db 1c5498b3aacc (postgres:17.11-alpine pinned, 127.0.0.1:55451);
  - cpt-studio-web ca8c24a2c77f (127.0.0.1:9150) and cpt-studio-worker d1dbcddf67e5, both on 36c5bf19ff2a;
  - volumes cpt-studio-pg and cpt-studio-files; network cpt-studio-net;
  - images cpt-studio:2734a6f31ce0 (36c5bf19ff2a), cpt-studio:29e4d1f52939, cpt-studio-fixcheck:8a06fd08c9a2,
    cpt-studio:dev-build and cpt-studio:emulation-stub;
  - the disposable test database cpt-studio-test-pg (127.0.0.1:55452), not part of the service and not touched by
    any phase.

  The build cache holds 487.8 MB.
- Let's Encrypt renewal configs: not re-read for this declaration (the session's read of /etc/letsencrypt is not
  permitted); the 2026-10-27 draft read cpt.quillmd.com.conf 473797910f15b53b9aec2d43a7c1ef41ea0e5e1afd6a8fe2a34d8ae739694b8c,
  quillmd.com.conf 914ac296954368647b20a35d295b43cc568b51061ffd63e6007d97548c292973, staging.quillmd.com.conf
  6e5e5b5b2e1920be1d983616537b7b893ecaa4bd79cf8f8e6bc24dd20925c350 and voice.kasitcorp.com.conf
  767af7a57466e7612d2b12de91f1b3960efe050c461bc715c25b7a0ee3da000e. The preflight receipt reads them and is binding.
- Host: 31 GiB RAM with 26 GiB available, 4 GiB swap of which 3.3 GiB used, 77 GiB free on / (87% used), 14 CPUs,
  load 1.15.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written to /var/www/certbot/.well-known/acme-challenge/ and removed.
- image: a new local image, cpt-studio:2b82889fea58, built from git archive of 2b82889fea5870921062cf31eefa0c0ad78a1c31 cpt-studio/. It
  carries label revision 2b82889fea5870921062cf31eefa0c0ad78a1c31, user 10150 and CPT_STUDIO_RELEASE_SHA=2b82889fea5870921062cf31eefa0c0ad78a1c31. The base is
  python:3.12-slim-bookworm@sha256:6a0e06f5….
  - Expected: Dockerfile steps 2/8-6/8 (OCR packages, user, workdir, requirements, pip) are CACHED, and the new
    image's RootFS layers 0-8 equal those of 36c5bf19. Only the COPY and collectstatic layers are new.
  - If the build cache was pruned since 2026-10-26, apt and pip run again against the Debian mirror and PyPI
    (versions pinned, no hashes; no provider), and layers 4-8 differ. The receipt's build log shows which case
    happened, and the image's own checks decide.
- Before app, outside the installer and read-only on the database:
  - one `pg_dump -Fc` of the cptstudio database through the database container's own pg_dump;
  - written to /home/claude/cpt-studio-install-20261023/pre-app-2b82889fea58-YYYYMMDDTHHMMSSZ.dump (0600);
  - its `pg_restore --list` must show the table data.

  It is the only data-level way back from a migration that damages rows. It holds the synthetic documents,
  provider responses and both accounts' password hashes. It is kept until removed by a separate, recorded
  decision.
- app (provider mode live; the same authorization reference as now):
  - the application's own loader parses the Corti credentials in the worker's mount layout, with no network;
  - migrate applies exactly studio.0006_services_completeness_second_review;
  - the queue read finds 0 stages this revision cannot run;
  - the 2734a6f3 pair (worker d1dbcddf67e5, web ca8c24a2c77f) is stopped (worker first, up to 150 s) and parked as
    *-previous; it is removed (retire_parked) only after the new pair is ready and the stored states are recomputed;
  - a new cpt-studio-web and cpt-studio-worker run on the new image with today's hardening, mounts, limits, labels
    and ports (127.0.0.1:9150; worker 1.5 GiB with the read-only Corti mount; web 768 MiB with the credentials path
    only);
  - /health/ reports release 2b82889fea5870921062cf31eefa0c0ad78a1c31;
  - once the new pair runs, and before the parked pair is removed, every encounter's stored list state is recomputed with
    this revision's derivation, the provider disabled (RECOMPUTE_STATES; only a changed state is written, nothing is
    sent). Expected receipt `states_recomputed`: {"encounters": 12, "changed": {}}. This was predicted by running this
    revision's derivation (at the PR head 518ed7138) over the live rows as dumped read-only 2026-10-28 ~17:55Z (12
    encounters: the 11 of the 2026-10-27 dump plus 6906e06f, the Elena PDF uploaded again on 2026-10-27 at 23:51Z
    with a member date of 1990-11-11, which the installed revision sent; needs_clarification; the last audit event
    23:51:21Z) in a scratch test database, with a positive control (a planted unknown outcome turned that encounter's
    state to provider_unknown). The prediction holds only while the re-read baseline shows no live activity after
    23:51:21Z. The final refutation's rollback lens ran this revision's real phase_app (Docker stubbed) over the 11
    encounters of the 2026-10-27 dump restored with 2734a6f3's models: {"encounters": 11, "changed": {}}, every state
    and updated_at unchanged.
  - if the phase stops after the swap (the parked pair's removal fails, an interrupt), the receipt is ok false and
    its details.states_recomputed says whether the states were recomputed; the recovery is to rerun app
    (ops/INSTALL.md, Recovery notes).

  Counts after app: studio_migrations 6. Every other count equals the pre-app reading. All 12 provider runs read
  purpose 'primary' and scope {}; all 12 assessments read services {}, completeness {} and second_run null; all
  148 proposals read support {} (figures as of the 2026-10-28 ~17:55Z read; the step-6 baseline re-read is binding).
- verify: none.
- Image 36c5bf19 (cpt-studio:2734a6f31ce0) is kept: it is the rollback image. Nothing removes it,
  cpt-studio:29e4d1f52939, cpt-studio-fixcheck:8a06fd08c9a2 or any other image.

## What the install sends to the provider: nothing

- install.py sends no request. Its one-shot containers (credentials parse, migrate, queue reads) run with
  CPT_STUDIO_PROVIDER_MODE=disabled, and the credentials parse has --network none. Migration 0006 is schema-only.
- Only work in flight at the swap could send. The new worker claims whatever is queued and settles whatever is
  running, under the new rules, so a queued predict would be sent. Since 8985dde42 no assessment queues a second
  review: only a workspace reviewer's explicit request does, and the install makes none.
- So, immediately before app, all of these must hold:
  - jobs_active (queued plus running) is 0;
  - no provider run is reserved or sending;
  - no unknown provider outcome is unreconciled;
  - no audit event is newer than 10 minutes.

  CPT Studio has no maintenance mode, so a member could still act. The window is short and is measured, not
  assumed.
- Checked after app:
  - provider_runs, provider_runs_sent, credits_sum, jobs and audit_events equal their pre-app reading;
  - no provider run has a created_at at or after the app receipt's started_at.

  Any difference is the finding (a request was queued or sent during the install), whatever explains it.

## After the install: the held-out acceptance walk (ordinary use, not a phase)

- After verify passes, the agent account review-agent walks the ten held-out synthetic documents, ho-01 to ho-10,
  through https://cpt.quillmd.com with ops/verify_browser.cjs --allow-live-provider. The set is three Word, three
  digital PDF, two scanned PDF, one text upload and one paste. The walk is one document per invocation, strictly in
  sequence, and the next starts only when jobs_active is 0 again. ops/verify_downloads.py checks each run's
  downloads. Decisions are recorded and labelled as agent review.
- Bounds for each document uploaded:
  - encounters +1 and revisions +1;
  - source_files +1, or 0 for the paste;
  - provider_runs +1 at most and provider_runs_sent +1 at most (one primary request);
  - second-review runs (purpose 'second_review') +0: the walk never asks for one;
  - jobs +4 when processing completes (extract, analyze, predict, assess), fewer when a stage fails;
  - jobs_active back to 0;
  - users, reference_sources, reference_facts and studio_migrations +0;
  - decisions +(the decisions the walk's evidence records as HTTP 201);
  - reports +(the report creations its evidence records as HTTP 201).
- For the whole walk, provider_runs_sent rises by 10 at most. credits_sum rises by the provider's own reported
  usage. The 12 requests so far used 0.600300, about 0.050 each; that is a record, not a gate.

## Must not change

- The quillmd vhost (e9aa049d…7638) and every other sites-available file listed above, quillmd-cpt (259b895d…)
  included.
- nginx.conf and conf.d, and every sites-enabled entry.
- The local routing of every co-tenant name/port pair and of an unknown host (status and certificate per SNI),
  55 entries on 2026-10-26 and again on 2026-10-28.
- app.quillmd.com /health/ (status and release) and the check-cotenants.sh results.
- Every container outside CPT Studio running at preflight (same id, still running), and every existing volume.
- Every Let's Encrypt lineage and renewal config (cpt.quillmd.com's included), and the ACME account set.
- The QuillMD rebuild, its database, users and files.
- /etc/cpt-studio/ and its files.
- cpt-studio-db: the same container, image, port and restart policy, running throughout.
- The volumes cpt-studio-pg and cpt-studio-files, and network cpt-studio-net.
- The two ReferenceSource rows and 34,665 reference facts; the two accounts.
- Every existing encounter, revision, source file, provider run, assessment, proposal, decision, clarification,
  audit event, report and job. They gain the new columns' defaults and nothing else.
- No `nginx -t` warning may be added.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok. Every receipt must also show:
- tree.mode descendant-without-runtime-change;
- tree.head equal to the merge commit that lands this declaration;
- door.declaration equal to this file;
- door.declaration_commit equal to the commit that last touched it.

In particular:
- preflight: the nginx files above; exactly the two known warnings; check-cotenants exit 0;
  app.quillmd.com 200 JSON; ports 9150 and 55451 published only by cpt-studio-web and cpt-studio-db; no task
  outside CPT Studio as uid 10150; A 147.189.172.8 only; one ACME account; at least 10 GiB free.
- image: the revision label, user 10150, the baked release, English OCR, pdftoppm, `manage check`, and a WSGI load
  as its own user on a read-only root. Then the layer comparison above.
- app:
  - the migrate log applies studio.0006 and nothing else;
  - unrunnable_stages.stuck is 0 and its known kinds include review2;
  - replaced names the two 2734a6f3 container ids;
  - health is {status ok, service cpt-studio, data_mode synthetic-only, database ok, release 2b82889fea5870921062cf31eefa0c0ad78a1c31}
    through 127.0.0.1:9150;
  - the new worker stayed up.
- verify:
  - no difference from the preflight baseline;
  - the deployed containers' hardening;
  - https://cpt.quillmd.com/health/ serves 2b82889fea5870921062cf31eefa0c0ad78a1c31 under normal certificate verification;
  - one copy each of HSTS, nosniff, Referrer-Policy and X-Robots-Tag;
  - a mismatched SNI is closed (444).

## Rollback per phase, and its limits

- preflight, image and verify change nothing that serves. A failed image leaves at most an unused image.
- app fails inside the phase (2af1f834d and refutation phase 1): the new pair is stopped; every stage it queued,
  ran or left resumable since the swap, and every stage of a kind the parked worker cannot run whichever pair created
  it, is closed as failed, naming the revision. The provider runs it left unsettled are settled as the stale-stage
  sweep settles them, and only then is the 2734a6f3 pair restored: its web is started, and its worker too unless the
  close names records 2734a6f3 would act on wrongly (ops/INSTALL.md, "Reinstalling an older revision": an unknown
  outcome, a failed request it could make again, a conflicting member date under a stopped stage, a code only a
  second review selected); then the worker is left stopped (nothing can be sent) and the receipt names the
  encounters. Before the rows are handed over, each stored state this revision labels from more than the state is
  given the state the parked image derives for it (the put-back); an encounter whose shown assessment read a bounded
  second review's response refused whole, or left a second review unread (second_review_refused,
  second_review_unread), has no state 2734a6f3 reads truthfully, so the old pair is not restored over it: the new
  pair is left stopped, the old pair parked, and the receipt names the encounters. If the stages cannot be closed,
  the new pair is left stopped and the old pair parked: run rollback-app under this declaration, then rename the
  parked pair back (ops/INSTALL.md, Recovery notes). Expected afterwards: health release 2734a6f3 and no *-previous
  container. On the baseline shape (12 encounters, 12 succeeded and sent runs, no second review, nothing queued) no
  such record exists, so the restored worker would start; measured on that shape (final refutation, rollback lens),
  the failure path's close names no hazard and relabels one encounter, gi-09 (fcfbba8f-8dd0-426e-b298-63e692f56e39,
  labelled 'No code selected for approval'), whose put-back changes nothing: {"encounters": 1, "changed": {}}. On
  this route those values are written to the phase's app-<stamp>-04-undo.log, not to its receipt, whose details are
  the original failure's.
- After a successful app there is no parked pair. Going back to 2734a6f3 is three steps:
  1. reconcile every unknown provider outcome on the new web;
  2. run rollback-app under this declaration (cpt.quillmd.com answers 502 from here until step 3). It reads first,
     with the pair's own image, the records 2734a6f3 would act on, or show, wrongly (including a second review
     refused whole or left unread), and refuses, naming the encounters and stopping nothing, while any exists; they
     are cleared on this revision's web as ops/INSTALL.md says (reconcile, Resume, answer the date question, or an
     addendum), or this revision stays installed. Otherwise it closes the stages, puts back the states this revision
     labels from more than the state, and removes the pair. On the baseline shape, measured (final refutation,
     rollback lens, nothing parked and with 2734a6f3's pair parked): ok true, details.stages_closed {"closed": 0,
     "encounters": 0, "hazards": {}, "kinds": [], "relabel": ["fcfbba8f-8dd0-426e-b298-63e692f56e39"],
     "runs_not_sent": 0, "runs_unknown": 0}, details.states_put_back {"encounters": 1, "changed": {}}, every state
     and updated_at unchanged. That was measured on the 11 encounters of the 2026-10-27 dump; the twelfth, 6906e06f,
     is needs_clarification, a review-queue state, which the close never names in relabel (ops/INSTALL.md), so the
     same values are expected on today's shape;
  3. run a separately declared reinstall of 2734a6f3 (preflight, app, verify).

  Step 3 must run from a checkout whose cpt-studio/ is 2734a6f3's: a branch from 057a7d398 carrying that
  declaration. This installer refuses a revision whose cpt-studio/ differs from HEAD's. Image 36c5bf19 and its
  image receipt (image-20261026T221926074316Z.json) are kept for it. If the image is gone, that act reruns image
  for 2734a6f3. ops/INSTALL.md, "Reinstalling an older revision", applies.
- Limits:
  - Migration 0006 is not reversed: its columns and database defaults stay, and 2734a6f3's inserts depend on those
    defaults.
  - Records the new revision made stay, and the old code reads them under its own rules.
  - Requests already sent and their usage stay.
  - rollback-app and the failure path are proven by ops tests only, never exercised on this host.
  - Restoring the pre-app dump would delete data, so it is a separate declared act.
  - rollback-vhost is not part of this act: deploy/nginx did not change.

## What is not claimed

- No coding-accuracy figure. The walk's assertions are browser, persistence and export checks plus the author's
  provisional expectations (interpretations 12 and 16). No qualified GI-coder adjudication exists. Passing checks
  are not an accuracy percentage.
- The install prevents no member action: "nothing sent" is measured over the install window only.
- The 12 existing encounters are neither re-assessed nor re-sent. Their stored assessments carry empty services
  and completeness. Their stored list states are recomputed at app and predicted unchanged (see app above). How the new screens and reports present them is not verified by the walk, which creates new
  encounters only.
- The confirmed refutation-round misreadings that are not must-fix remain known limits
  (cpt-studio/ACCURACY-RESIDUALS.md and PR #1440's body). The reviewer decides every code. READY is advisory.
- The following stay not verified (interpretations 1-3): CPT edition, descriptors and NCCI PTP.
- Data at rest is unencrypted and there is no scheduled database backup (ops/INSTALL.md known limits). The one-off
  pre-app dump is not a backup scheme.
- If the build cache was pruned, the image's OS packages are not those of 36c5bf19.
- Co-tenants and app.quillmd.com are judged only by routing, health and check-cotenants equality.

## Stop conditions

Stop and diagnose on any of the following. Do not rerun a phase, and do not upload the next walk document:
- any non-zero phase exit or a receipt that does not say ok;
- a tree mode other than descendant-without-runtime-change;
- a routing, health, check-cotenants or file-hash difference, or any new nginx warning;
- a quillmd vhost sha256 other than e9aa049d…7638;
- DNS other than A 147.189.172.8 alone, or anything other than exactly one ACME account;
- a migrate log that applies anything but studio.0006;
- a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event
  under 10 minutes old;
- across app: any count other than studio_migrations moving, or a provider run created during the install;
- the app receipt's states_recomputed naming any changed encounter (predicted none);
- a leftover *-previous container;
- ports 9150 or 55451 held by anything but cpt-studio-web and cpt-studio-db;
- any task outside CPT Studio running as uid 10150;
- during the walk:
  - more than one request sent for one document;
  - any second-review run;
  - an unknown provider outcome (reconcile it first);
  - a provider authentication, quota or payment failure;
  - jobs_active not returning to 0 within the stage deadlines (Stop that encounter in the UI);
  - a /health/ release other than 2b82889fea5870921062cf31eefa0c0ad78a1c31;
  - any 5xx from the site.
