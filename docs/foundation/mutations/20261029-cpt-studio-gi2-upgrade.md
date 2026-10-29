# Prospective declaration: CPT Studio GI round 2 upgrade at cpt.quillmd.com (2b82889f to 90377ec6f413ac6cf1601836a286f45e2af53e37), and the demo reviewer account

Authority: the owner's directive of 2026-10-28 recorded verbatim in docs/foundation/rulings/2026-10-23-cpt-studio-gi.md
("Owner directive, 2026-10-28": "Finish with verified fixes, installed revision, remaining limitations and whether a
complete doctor-facing synthetic demo is ready", "Use parallel agents for independent investigation and verification,
with one integration/deployment owner", "Reuse retained evidence first, then run targeted fresh synthetic checks and
actual reviewed downloads", "Keep rollback protections intact"). The same file records the owner's two decisions of
2026-10-28: "Narrow source rule (Recommended)", which this revision implements, and "Separate demo reviewer
(Recommended)" ("I provision one new reviewer account in the GI workspace via manage.py provision, with a generated
password stored 0600 on the server for you; decisions are attributed to it, not to you. A new credential (class d), so
only with your yes."), which step D below carries out. Session interpretation 30 makes session 7c8d38da the single
integration and deployment owner of this round. The install itself is governed by the 2026-10-23 directive cited in
docs/foundation/mutations/20261023-cpt-studio-install.md: a protected synthetic demonstration that uses the existing
authorized Corti account, keeps provider credentials server-side and preserves app.quillmd.com and unrelated services
("Keep app.quillmd.com, VoiceAssistMain and unrelated server resources unchanged", 2026-10-27). CPT Studio stays
standalone: no QuillMD source, database, users, files, units or environment are shared, promoted or edited. No
purchase, agreement, new ACME account, new key, payment change or real-patient processing is part of this act. The
installer sends no provider request (see "What the install sends").

Revision to install: 90377ec6f413ac6cf1601836a286f45e2af53e37, the merge commit of PR #1445 (branch fix/cpt-studio-gi-interpretation-20261028); image
tag cpt-studio:90377ec6f413. It replaces the live revision 2b82889fea5870921062cf31eefa0c0ad78a1c31, installed
2026-10-28 18:58:01Z-19:00:13Z from 5dbf6b5e7 under docs/foundation/mutations/20261027-cpt-studio-gi-core-upgrade.md
(declaration commit bc5886fa7). It runs image cpt-studio:2b82889fea58 (sha256:544d8dd263ef), web 3c2129631ff1, worker
d85c72b252a0 and database 1c5498b3aacc. That declaration and its receipts stay as they are.

Execute each install phase separately through scripts/run-ruled-mutation.sh with
`python3 -B cpt-studio/ops/install.py --phase <phase> --revision 90377ec6f413ac6cf1601836a286f45e2af53e37 --receipts /home/claude/cpt-studio-install-20261023`,
in this order: preflight, image, app (with `--provider-mode live --authorization-ref
docs/foundation/rulings/2026-10-23-cpt-studio-gi.md`), verify. Then step D (below), once. Run them from a clean,
detached checkout of the merge commit that lands this declaration: a descendant of the revision that changes nothing
under cpt-studio/, scripts/run-ruled-mutation.sh or scripts/lib/. Read each receipt before the next phase. The
receipts directory is the live install's own (ops/INSTALL.md, "Reinstalling a new revision"). No receipt there is
changed: each file is created once.

Not run, because their objects exist and this revision does not change them: secrets, db, reference, provision,
http-vhost, cert and https-vhost. Between 2b82889f and 90377ec6f413 these files are byte-identical: cpt-studio/deploy/
(Dockerfile, entrypoint, gunicorn, nginx templates, .dockerignore), cpt-studio/ops/install.py, cpt-studio/ops/INSTALL.md,
cpt-studio/requirements.txt, cpt-studio/cptstudio/ (settings), scripts/run-ruled-mutation.sh and scripts/lib/. So the
installer, the image recipe, the vhost and the rollback rules are those that installed 2b82889f.

## Delta shipped (2b82889f to 90377ec6f413)

PR #1445: the round's interpretation repairs (extent, negation, service date, conflicts, attribution and support), the
controlled recovery of conclusively not-sent requests, the second-review wording and screen, and the walk's tooling.
Its body and cpt-studio/ACCURACY-RESIDUALS.md ("GI round 2") list every change with its before and after. For this act:

- No migration: `makemigrations --check` reports no changes, and cpt-studio/studio/migrations/ is byte-identical.
  studio_migrations stays 6.
- cpt-studio/studio/models.py, review.py (the stored list state's derivation), audit.py and types.py are byte-identical,
  so the stored states recompute as they are (predicted below).
- New readings apply to new uploads, new addenda and new reads only. No existing encounter is re-assessed or re-sent
  by the install.
- `manage.py provision` gains `--reviewer-username`, `--reviewer-display-name` and `--reviewer-password-file`. It adds a
  human reviewer to an existing workspace, never demotes an owner, reads the password from a file and never prints it
  (tests/test_provision.py). Step D uses it.

## Baseline (read-only, 2026-10-29; re-read immediately before the commit that lands this declaration; this act's preflight receipt is binding)

- Live database (bc7df129's tools/live_counts.sh, SELECT only, 2026-10-29T06:11:48Z, and identical at the re-read of
  06:45:09Z): encounters 22, revisions 22,
  source_files 19, provider_runs 23, provider_runs_sent 23, assessments 23, proposals 297, decisions 17,
  clarifications 21, audit_events 193, reports 60, jobs 90, jobs_active 0, users 2, reference_sources 2,
  reference_facts 34665, studio_migrations 6, credits_sum 1.053376.
- States (SELECT only, the same reading):
  - provider runs: 23, all succeeded and sent (22 primary, 1 second review: ho-06's, 2026-10-28 21:51:54Z); none
    reserved or sending; no unreconciled unknown outcome;
  - encounters: needs_clarification 11, reviewed 8, no_codes 2, ready_for_review 1;
  - the last audit event is ho-06's second review, 2026-10-28T21:52:07Z (idle 31,982 s at the 06:45:09Z re-read);
  - accounts: users 2 and memberships 2 (the owner, human; review-agent, agent, reviewer), both active; no account
    named demo-reviewer; the Gastroenterology category (slug gastroenterology) reads profiles_version gi-profiles@2;
    workspace ac7def49-7a0e-4db2-bf1b-8efe9fbfa0a8.
- Containers and images (docker inspect, read-only):
  - cpt-studio-web 3c2129631ff1 and cpt-studio-worker d85c72b252a0 on image 544d8dd263ef (cpt-studio:2b82889fea58);
  - cpt-studio-db 1c5498b3aacc (postgres:17.11-alpine pinned, 127.0.0.1:55451);
  - images kept: cpt-studio:2b82889fea58 (544d8dd263ef), cpt-studio:2734a6f31ce0 (36c5bf19ff2a), cpt-studio:29e4d1f52939,
    cpt-studio-fixcheck:8a06fd08c9a2, cpt-studio:dev-build and cpt-studio:emulation-stub;
  - the disposable test database cpt-studio-test-pg (127.0.0.1:55452), not part of the service and touched by no phase.
- nginx, routing, DNS, ACME, co-tenants and host resources: read by the preflight phase, whose receipt is binding. The
  quillmd-cpt vhost must still be 259b895dd1307e81b8fbcb5439874477daf71eba63c9b996b3bdfc572bf71a0c (the https-vhost receipt
  of 2026-10-26, unchanged by the 2b82889f install) and quillmd e9aa049d9190713b60e8243b56e082c3fe59e068c205e0d595407f7d08a97638.
  scripts/check-cotenants.sh at 2026-10-29T06:00Z and 06:45Z: rc 0 (quillmd.com 200, www 200, app 302, admin 503,
  pro 410).
- Host at 2026-10-29T06:45Z: 31 GiB RAM, 4 GiB swap, 14 CPUs; 61 GiB free on / (90% used, after this session reaped its
  own scratch). The preflight phase requires at least 10 GiB free.

## Expected changes, per phase

- preflight: none. One random ACME probe file is written to /var/www/certbot/.well-known/acme-challenge/ and removed.
- image: a new local image, cpt-studio:90377ec6f413, built from git archive of 90377ec6f413ac6cf1601836a286f45e2af53e37 cpt-studio/. It carries label
  revision 90377ec6f413ac6cf1601836a286f45e2af53e37, user 10150 and CPT_STUDIO_RELEASE_SHA=90377ec6f413ac6cf1601836a286f45e2af53e37.
  - Expected: the Dockerfile's dependency steps are CACHED (the build cache of the 2b82889f build is present: 0.5 GB at
    06:00Z), so the new image's RootFS layers up to the COPY equal those of 544d8dd263ef; only the COPY and
    collectstatic layers are new.
  - If the build cache was pruned meanwhile, apt and pip run again (pip pinned with ==, apt unpinned; no provider), and
    the receipt's build log shows it; the image's own checks decide.
- Before app, outside the installer and read-only on the database: one `pg_dump -Fc` of the cptstudio database through
  the database container's own pg_dump, written to
  /home/claude/cpt-studio-install-20261023/pre-app-90377ec6f413-YYYYMMDDTHHMMSSZ.dump (0600); its `pg_restore --list` must
  show the table data. It is the only data-level way back. It holds synthetic documents, provider responses and both
  accounts' password hashes, and is kept until removed by a separate, recorded decision.
- app (provider mode live; the same authorization reference as now):
  - the application's own loader parses the Corti credentials in the worker's mount layout, with no network;
  - migrate applies nothing: its log (details.migrate_log, app-<stamp>-01-migrate.log) reads "No migrations to apply."
    (the installer checks only its exit code, so this is the operator's reading of the log);
  - the queue read finds 0 stages this revision cannot run;
  - the 2b82889f pair (worker d85c72b252a0, web 3c2129631ff1) is stopped (worker first, up to 150 s) and parked as
    *-previous; it is removed (retire_parked) only after the new pair is ready and the stored states are recomputed;
  - a new cpt-studio-web and cpt-studio-worker run on the new image with the same hardening, mounts, limits, labels and
    ports (127.0.0.1:9150; worker 1.5 GiB with the read-only Corti mount; web 768 MiB with the credentials path only);
  - /health/ reports release 90377ec6f413ac6cf1601836a286f45e2af53e37;
  - every encounter's stored list state is recomputed with this revision's derivation, the provider disabled
    (RECOMPUTE_STATES). Expected receipt `states_recomputed`: {"encounters": 22, "changed": {}}. Predicted by running
    this revision's derivation (at the PR head 76596ebf9, whose cpt-studio/ the merge commit carries) over the live rows
    dumped read-only at 2026-10-29T06:12Z, in a scratch test database: RECOMPUTE {"encounters": 22, "changed": {}},
    with a positive control (a planted unknown outcome turned that encounter's state from ready_for_review to
    provider_unknown). The derivation's code is byte-identical to 2b82889f's, whose own install recomputed the then 12
    encounters unchanged. The prediction holds only while the re-read baseline shows no live activity after ho-06's
    second review;
  - if the phase stops after the swap with an error or an interrupt, the receipt is ok false, details.states_recomputed
    says whether the states were recomputed, and its message says what is left to do (after_swap_failure); an installer
    killed outright (for example by the door's 3600 s ceiling, exit 124) writes no receipt (ops/INSTALL.md, Recovery
    notes). Each such case is a stop under this declaration, judged before any rerun (the 2b82889f app phase took 27 s).

  Counts after app: every count equals the pre-app reading (no migration, nothing re-assessed).
- verify: none.
- Image 544d8dd263ef (cpt-studio:2b82889fea58) is kept: it is the rollback image. Nothing removes it or any other image.

## Step D: the demo reviewer account (once, after verify passes)

The owner's decision of 2026-10-28 ("Separate demo reviewer"). One human reviewer account for a doctor's
demonstrations, in the one GI workspace, so decisions made in a demonstration are attributed to it, not to the owner.

- The password is generated on the server, never printed, never committed, never sent anywhere:
  `install -d -m 0700 /home/claude/.cpt-studio` and then, refusing to overwrite an existing file,
  `(set -o noclobber; umask 077; python3 -c 'import secrets; print(secrets.token_urlsafe(32))' > /home/claude/.cpt-studio/demo-reviewer-password)`.
  The file is mode 0600, owned by this user; the owner reads it on the server.
- The act, through the door, with the door's whole output captured by the operator (`| tee` to a 0600 file in the
  session scratch, since the door keeps no transcript):
  `bash scripts/run-ruled-mutation.sh --declaration <this file> -- bash -c 'docker exec -i cpt-studio-web sh -c "umask 077; f=\$(mktemp); cat >\"\$f\"; python manage.py provision --reviewer-username demo-reviewer --reviewer-display-name \"Demo reviewer (synthetic demonstration)\" --reviewer-password-file \"\$f\"; rc=\$?; rm -f \"\$f\"; exit \$rc" < /home/claude/.cpt-studio/demo-reviewer-password'`.
  The password reaches the container on fd 0 and is copied to a mode-0600 file in the web container's /tmp (a 256 MB
  tmpfs: RAM), which is removed whatever provision returns. provision opens its password file by path, and a
  uid-10150 process with no capabilities cannot reopen the root-owned stdin pipe of `docker exec -i` as /dev/stdin, so
  the path is that copy. provision validates the password with the service's validators (minimum length 12, common,
  numeric, user-attribute similarity; a 43-character token passes) and stores only its Argon2 hash. The quoting was
  tested locally with a stand-in for provision: the arguments arrive as written and the copy is gone afterwards.
- Expected output of the command itself - the lines between the door's "starting at" line and its "RULED MUTATION -
  FINISHED" line (the door's gate, the declaration text and its banners are its own) - and nothing else:
  "created human account demo-reviewer (reviewer)" and "workspace ac7def49-7a0e-4db2-bf1b-8efe9fbfa0a8
  (Gastroenterology, gastroenterology)". The captured output must not contain the password: the operator byte-searches
  the capture against the password file, printing only found / not found, then shreds the capture.
- Expected changes: users 2 -> 3 (actor kind human); memberships 2 -> 3 (one new membership, role reviewer, active,
  in workspace ac7def49-7a0e-4db2-bf1b-8efe9fbfa0a8); audit_events +1 (account.provisioned, actor none, created true);
  and the Gastroenterology category's profiles_version gi-profiles@2 -> gi-profiles@3 (provision brings it to the
  image's PROFILES_VERSION; only provision writes it, last run under 2734a6f3; it is shown in the session JSON). Read
  by SELECT before and after. Nothing else moves: no encounter, provider run, job or report, and the owner's and the
  agent's accounts and memberships are unchanged.
- Refusals, each rolled back whole (provision's handle is one transaction): "Account demo-reviewer exists with a
  different actor kind", an owner-demotion refusal, a password-validator refusal, or the password copy failing.
  "kept human account demo-reviewer" is no refusal: it would mean an account of that name already existed, its
  password was not set (so the file does not open it), and the run committed audit_events +1 with created false (and
  made that account an active reviewer). The baseline - 2 users, owner and review-agent, and no demo-reviewer at
  2026-10-29T06:45:09Z - rules it out; it is a stop.
- Undo: the account is deactivated (its membership's active false) by a separate declared act. Deleting the account
  or its audit rows is a deletion of data (class d) and only the owner may order it.

## What the install sends to the provider: nothing

- install.py sends no request. Its one-shot containers (credentials parse, migrate, queue reads) run with
  CPT_STUDIO_PROVIDER_MODE=disabled, and the credentials parse has --network none. Step D sends nothing.
- Only work in flight at the swap could send. The new worker claims whatever is queued and settles whatever is
  running, under the new rules. Since 8985dde42 no assessment queues a second review: only a workspace reviewer's
  explicit request does, and the install makes none.
- So, immediately before app, all of these must hold: jobs_active (queued plus running) is 0; no provider run is
  reserved or sending; no unknown provider outcome is unreconciled; no audit event is newer than 10 minutes. CPT Studio
  has no maintenance mode, so a member could still act. The window is short and is measured, not assumed.
- Checked after app: provider_runs, provider_runs_sent, credits_sum, jobs and audit_events equal their pre-app
  reading, and no provider run has a created_at at or after the app receipt's started_at. Any difference is the
  finding, whatever explains it.

## After the install: the acceptance walk (ordinary use, not a phase)

- After verify and step D, the agent account review-agent walks through https://cpt.quillmd.com with
  ops/verify_browser.cjs --allow-live-provider:
  - the fresh synthetic acceptance set h2-01..h2-10 (interpretation 29: written by an author who read neither the
    application code nor the repairs; read by this session only after the code was frozen);
  - ho-01..ho-04 again, as regressions of the documents this round repaired.

  One document per invocation (`--only <id>`, `--deadline-seconds 900`), strictly in sequence; the next starts only
  when jobs_active is 0 again. The manifests are amended copies of the authors' (the integration owner added
  review_plan.approve_codes, chosen after reading each source, and the two exercises below; nothing else):
  /home/claude/cpt-studio-gi2-walk-90377ec6f413/h2/manifest.json (sha256
  07092d12cb171bd31816db0fc6737aaf188e8deaad7276df0b42e850e53662ac; from the author's ef42d4e6...) and .../ho/manifest.json
  (d71055867bb70be96a2b69ecb53c93ff527b2a9b60942bfc63e5e50e52f84091; ho-01..ho-04 of 135258c4...). Their documents were
  regenerated with this revision's ops/verification/generate.py (generated.json binds each manifest); the ten h2 files
  are byte-identical to the author's render. Decisions are recorded and labelled as agent review; approvals use
  `--no-auto-approve` with each document's review_plan.approve_codes (on h2-09 also review_plan.second_review.approve_codes
  for a code the second review adds); a ready code left unnamed stays undecided and withholds that document's reviewed
  report. CPT Studio renders TXT and CSV reports (Word and PDF are upload formats only): ops/verify_downloads.py
  re-checks, file by file, the draft TXT and CSV, and the reviewed TXT and CSV where the review was complete
  (readiness.reviewed); where it was not, the walk records reviewed_withheld with its blockers and asserts that the
  reviewed export is not offered.
- Two exercises inside the walk, each labelled synthetic in the manifest and the evidence:
  - h2-10, the controlled recovery: uploaded with the member service date 2026-10-24 (the signature date) where the
    document states 2026-10-23, so the primary request is held (a not-sent run, purpose primary, scope
    {"held": "member_date_conflict"}, no request hash, nothing sent); then one context save (review_plan.context_edit
    {"service_date": "2026-10-23"}) settles the date and makes that request once, for 2026-10-23; the identical second
    save sends nothing and records no run;
  - h2-09, the reviewer-requested second review (review_plan.second_review {"ask": true, "approve_codes": ["43238"]}):
    asked once, explicitly, through the screen's button, only if the encounter offers it after the primary run (the
    walk never forces it; the API takes no note, so the label is the agent account and its labelled decisions,
    interpretation 34); no unsupported alternative is promoted, and its raw result, decisions and usage are kept.
- Bounds for each document uploaded (database counts, SELECT only, before and after each document; the walk tool's own
  "sent" is derived from the API, which serves no sent flag):
  - encounters +1 and revisions +1; source_files +1, or 0 for a paste;
  - an ordinary document: provider_runs +1 (one primary run: sent, or a reuse of a retained answer with nothing sent)
    and provider_runs_sent +1 at most; jobs +4 (extract, analyze, predict, assess), fewer when a stage fails;
  - h2-10: provider_runs +2 (the hold at upload, then the settling save's one primary run for 2026-10-23; the identical
    save adds none), provider_runs_sent +1 at most; jobs +6 (upload: extract, analyze, assess - the analyze stage records
    the hold and queues no predict; the settling save: predict, assess; the identical save: assess);
  - h2-09: provider_runs +2 at most (the primary and one purpose 'second_review' run) and provider_runs_sent +2 at most;
    jobs +6 at most (upload +4; the ask: review2, then the assess that reads the second review);
  - second-review runs (purpose 'second_review') +0, except h2-09: +1 at most, none when the encounter does not offer
    the ask or the review2 stage records no run; at most one per revision and service date whatever its outcome;
  - jobs_active back to 0; users, reference_sources, reference_facts and studio_migrations +0;
  - decisions and reports +(what the walk's evidence records as HTTP 201).
- For the whole walk (14 documents): jobs +60, provider_runs +16 and provider_runs_sent +15 at most (13 primary requests
  sent at upload, h2-10's one after its settling save, and h2-09's second review). credits_sum rises by the provider's
  own reported usage; the 23 requests so far used 1.053376, about 0.046 each. That is a record, not a gate.

## Must not change

- The quillmd vhost (e9aa049d…7638) and every other sites-available file, quillmd-cpt (259b895d…) included.
- nginx.conf and conf.d, and every sites-enabled entry.
- The local routing of every co-tenant name/port pair and of an unknown host (status and certificate per SNI).
- app.quillmd.com /health/ (status and release) and the check-cotenants.sh results.
- Every container outside CPT Studio running at preflight (same id, still running), and every existing volume.
- Every Let's Encrypt lineage and renewal config, and the ACME account set (verify compares the other lineages and
  renewal configs with preflight; cpt.quillmd.com's lineage and the account set are read by preflight only; this act
  touches neither).
- The QuillMD rebuild, its database, users and files. /etc/cpt-studio/ and its files.
- cpt-studio-db: the same container, image, port and restart policy, running throughout. The volumes cpt-studio-pg and
  cpt-studio-files, and network cpt-studio-net.
- The two ReferenceSource rows and 34,665 reference facts; the two existing accounts and their memberships (step D adds
  one account and changes none).
- Every existing encounter, revision, source file, provider run, assessment, proposal, decision, clarification, audit
  event, report and job: no migration, nothing re-assessed, and every stored state recomputed unchanged.
- No `nginx -t` warning may be added. No phase after preflight runs `nginx -t`: the operator runs the installer's
  read-only nginx_test probe after verify and compares it with the two known warnings.

## Validation per phase

Each phase's own checks (ops/INSTALL.md) must pass and its receipt must say ok. Every receipt must also show:
tree.mode descendant-without-runtime-change; tree.head equal to the merge commit that lands this declaration;
door.declaration equal to this file; door.declaration_commit equal to the commit that last touched it.

- preflight: the nginx files above; exactly the two known warnings; check-cotenants exit 0; app.quillmd.com 200 JSON;
  ports 9150 and 55451 published only by cpt-studio-web and cpt-studio-db; no task outside CPT Studio as uid 10150; A
  147.189.172.8 only; one ACME account; at least 10 GiB free.
- image: the revision label, user 10150, the baked release, English OCR, pdftoppm, `manage check`, and a WSGI load as
  its own user on a read-only root; then the layer comparison above.
- app: the migrate log reads "No migrations to apply."; unrunnable_stages.stuck is 0 and its known kinds include review2; replaced
  names the two 2b82889f container ids; states_recomputed {"encounters": 22, "changed": {}}; ok true. Then, by the
  operator: /health/ through 127.0.0.1:9150 is {status ok, service cpt-studio, data_mode synthetic-only, database ok,
  release 90377ec6f413ac6cf1601836a286f45e2af53e37}, and `docker ps` shows the new worker up.
- verify: no difference from the preflight baseline; the deployed containers' hardening; https://cpt.quillmd.com/health/
  serves 90377ec6f413ac6cf1601836a286f45e2af53e37 under normal certificate verification; one copy each of HSTS, nosniff, Referrer-Policy and
  X-Robots-Tag; a mismatched SNI is closed (444): details.evidence.sni_mismatch.error is RemoteDisconnected, as on
  2026-10-28 (verify passes on any probe error, so the operator reads which).
- step D: the output and the counts above, by a SELECT-only reading before and after.

## Rollback per phase, and its limits

The installer is byte-identical to the one that installed 2b82889f, so its rollback rules are unchanged, and they still
read every hazard as 057a7d39 (2734a6f3's tree) reads the rows (install.py; ops/INSTALL.md, "Reinstalling an older
revision"), not as 2b82889f does. For a return to 2b82889f, which shares review.py and models.py with this revision and
reads second reviews, that is conservative: the failure path and rollback-app refuse or hold for second_review,
second_review_refused and second_review_unread although 2b82889f would act on and show those correctly.
- preflight, image and verify change nothing that serves. A failed image leaves at most an unused image.
- app fails inside the phase: the new pair is stopped, the stages it queued, ran or left resumable since the swap are
  closed as failed naming the revision, the provider runs it left unsettled are settled as the stale-stage sweep settles
  them, and only then is the 2b82889f pair restored (web, and the worker unless the close names unknown, outcome,
  conflict or second_review, as 057a7d39 would act on them: an unknown outcome, a failed request it could make again, a
  conflicting member date under a stopped stage, a code only a second review selected), with the receipt naming the
  encounters. If the stages cannot be closed, the put-back fails, or the close names an encounter for
  second_review_refused or second_review_unread (no pair of another revision is restored over those), the new pair is
  left stopped and the old pair parked, and the receipt names the encounters: run rollback-app under this declaration,
  then rename the parked pair back and start it (`docker rename cpt-studio-worker-previous cpt-studio-worker && docker
  start cpt-studio-worker`, then web; or the worker left stopped where the receipt names such records). Expected
  afterwards: health release 2b82889f and no *-previous container. On today's shape none of the six reasons applies
  (read from the read-only dump of 2026-10-29T06:12Z as JSON): no run is unsettled, failed or not sent, no encounter is
  stopped, and the one second review (c158bce7, ho-06) is read by its current assessment, with no failed provider check
  and every one of its proposals an alternative.
- After a successful app there is no parked pair. Going back to 2b82889f is three steps: reconcile every unknown
  provider outcome; run rollback-app under this declaration (cpt.quillmd.com answers 502 until step 3), which refuses,
  naming the encounters and stopping nothing, while the installer's hazard read names any encounter (it puts
  relabelled states back with 057a7d39's derivation, which the reinstall's app recomputes); then a
  separately declared reinstall of 2b82889f (preflight, app, verify) from a checkout whose cpt-studio/ is 2b82889f's.
  Image 544d8dd263ef and its image receipt (image-20261028T185838644401Z.json) are kept for it.
- Step D: the account is deactivated by a separate declared act; its audit row stays.
- Limits: records the new revision made stay, and 2b82889f reads them under its own rules (the schema is the same);
  requests already sent and their usage stay; rollback-app and the failure path are proven by ops tests only, never
  exercised on this host; restoring the pre-app dump would delete data, so it is a separate declared act;
  rollback-vhost is not part of this act.

## What is not claimed

- No coding-accuracy figure. The walk's assertions are browser, persistence and export checks plus the author's
  provisional expectations. No qualified GI-coder adjudication exists, and passing checks are not an accuracy
  percentage. The ten held-out documents ho-01..ho-10 were this round's development documents (interpretation 29).
- The install prevents no member action: "nothing sent" is measured over the install window only.
- The 22 existing encounters are neither re-assessed nor re-sent. How the new screens present them is not verified by
  the walk, which creates new encounters only.
- The known limits of cpt-studio/ACCURACY-RESIDUALS.md ("GI round 2") and the items PR #1445 lists for the owner stay
  open. The reviewer decides every code. READY is advisory.
- CPT edition, descriptors and NCCI PTP stay not verified (interpretations 1-3). Data at rest is unencrypted and there is
  no scheduled database backup; the one-off pre-app dump is not a backup scheme.
- Co-tenants and app.quillmd.com are judged only by routing, health and check-cotenants equality.
- verify skips every cpt-studio-* container when it checks that the containers running at preflight still run, so
  cpt-studio-db's id and the disposable cpt-studio-test-pg are compared by nothing in this act, and a leftover
  *-previous container would appear only in details.containers_appeared_elsewhere. The operator checks these by hand
  after verify (`docker ps -a`).
- Step D's password reaches the owner only on the server; this act does not deliver it elsewhere. Whether the demo
  account opens is not shown by this act (a login would need the password read by a session tool); its existence, role
  and membership are read by SELECT.

## Stop conditions

Stop and diagnose on any of the following. Do not rerun a phase, and do not upload the next walk document:
- any non-zero phase exit or a receipt that does not say ok;
- a tree mode other than descendant-without-runtime-change;
- a routing, health, check-cotenants or file-hash difference, or any new nginx warning;
- a quillmd vhost sha256 other than e9aa049d…7638;
- DNS other than A 147.189.172.8 alone, or anything other than exactly one ACME account;
- a migrate log that applies any migration;
- a stage this revision cannot run;
- before app: jobs_active not 0, a reserved or sending run, an unreconciled unknown outcome, or an audit event under
  10 minutes old;
- across app: any count moving, or a provider run created during the install;
- the app receipt's states_recomputed naming any changed encounter (predicted none);
- a leftover *-previous container;
- ports 9150 or 55451 held by anything but cpt-studio-web and cpt-studio-db;
- any task outside CPT Studio running as uid 10150;
- step D: any command output (between the door's banners) other than the two expected lines, the password found in
  the captured output, or any change other than users, memberships, audit_events and the category's
  profiles_version;
- during the walk:
  - more than one primary request sent for one document (h2-10: its one request after the settling save);
  - h2-10: any of the walk's context_edit.held_before, nothing_sent_before, one_request, sent_at_most_once or
    identical_save failing - a run other than the hold before the settling save (a request built, reused or sent while
    the member date conflict held); no request, or another hold, after the save; a request for any date but
    2026-10-23; or any run sent or held by the identical second save;
  - a second-review run on any document but h2-09, or more than one on h2-09;
  - an unknown provider outcome: stop. Reconciling it is a separate, recorded decision: it queues one new attempt at
    once, which for a primary run sends that document's request again (beyond the walk's bounds), so the bounds are
    restated before it is made;
  - a provider authentication, quota or payment failure;
  - jobs_active not returning to 0 within the stage deadlines (Stop that encounter in the UI; the walk tool stops
    nothing);
  - a /health/ release other than 90377ec6f413ac6cf1601836a286f45e2af53e37, or any 5xx from the site;
  - a downloaded report that misstates the persisted decisions.
