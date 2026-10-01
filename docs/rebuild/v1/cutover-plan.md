# QuillMD V1 cutover and rollback plan: from nothing to invited real-patient V1

Prepared 2026-09-27. It carries forward the principles of the inactive
`docs/rebuild/production-activation-checklist-20260921.md` (empty production database, nothing
synthetic copied, declared first-administrator bootstrap, reference data re-imported, templates
re-uploaded, Stripe live bound separately, maintenance lifted last) and moves them from a second
namespace on the VPS to the dedicated AWS target in `production-hosting.md`. Nothing in this plan has
been executed. Every irreversible step runs through `scripts/run-ruled-mutation.sh` with a committed
declaration (`docs/foundation/mutations/`), and every deploy has its §2.5 declaration
(`docs/foundation/deploys/`) written before it runs.

## Principles

1. **The production database starts empty** and receives only migrations, the recorded public
   ICD-10-CM releases, and what invited users create. Never copied: synthetic users, departments,
   patients, templates, filled documents, wallets, ledger, welcome grants, payments, Stripe objects,
   provider receipts, audit rows, backups, keys, passwords, TOTP secrets or session keys.
2. **No PHI touches a host or provider without a signed BAA**, and never the VPS. After go-live,
   rollback never points DNS back at the VPS: maintenance is served by the ALB instead.
3. **Maintenance is lifted last**, only after every gate below is green, by switching the ALB
   listener from its fixed maintenance response to the target group.
4. **Verification is structural or synthetic.** Production is proven by launcher proofs, receipts,
   AWS configuration, drills on restored copies and the synthetic smoke account; never by opening,
   editing, finalizing or exporting a real patient's record.
5. **Once real data exists, nothing is restored over it and nothing is dropped.** Recovery is
   forward (a schema-compatible release) or a point-in-time restore into a NEW instance followed by a
   reviewed reconciliation.

## External prerequisites (owner unless stated)

| # | Prerequisite | Needed by |
| --- | --- | --- |
| P1 | AWS Organization (management, production, backup accounts), billing, "all features" on | G1 |
| P2 | AWS BAA accepted in AWS Artifact for the Organization (after legal review) | G1 |
| P3 | Anthropic HIPAA-ready API organization with the BAA accepted (version after 2026-04-01) and a production API key from it | G5 |
| P4 | Deepgram Enterprise agreement with BAA; account-wide model-improvement opt-out in writing; production API key | G5 |
| P5 | Stripe live account identity, restricted live key (Checkout Sessions write only), webhook endpoint `https://app.quillmd.com/billing/webhook/` with its signing secret, and written authority for one bounded real-payment acceptance | G8 |
| P6 | Resend sender domain verified for the production sender; production API key (send only) | G5 |
| P7 | A named second custodian; two sealed break-glass kits; hardware MFA keys for both | G1 |
| P8 | Independent penetration tester engaged (scope: `docs/rebuild/pentest-scope.md` updated for AWS), window agreed | G7 |
| P9 | Counsel: retention schedule, deletion procedure, breach-notification procedure, downstream BAA template for practices | G7 |
| P10 | Healthchecks.io (or equivalent outside monitor) account owned by the company, alerting both custodians | G6 |
| P11 | DNS/registrar account with MFA and registrar lock; ability to add CNAMEs for `app` and `admin` | G1 (ACM validation), G9 |
| P12 | Engineering, other V1 streams, merged and cited on `main`: real-patient data gate bound to the profile's data mode; live Stripe path; admin surface behind a TLS proxy; client address for rate limits; invitation-only registration (owner's V1 policy); Deepgram opt-out parameter; Sonnet 5 configuration | G3 |
| P13 | Prepared engineering: production database-role transport and read-only verifier, hashed production dependency lock, and declared first-admin create/elevate command. See `host-readiness-20260927.md` and `dependency-lock-20260927/REPORT.md`; actual AWS/installed-target verification is still required. Synthetic seed commands remain forbidden. | G4, G8 |

A missing prerequisite stops the plan at the gate that needs it. None of them is replaced by a
synthetic stand-in.

## Gates, steps and timings

Times are working estimates for the act itself; G0 and G7 are dominated by third parties.

### G0 Decisions and contracts (unscheduled; duration unknown)

Record in `docs/foundation/RULINGS.md`: AWS us-east-1, RDS Single-AZ, ALB/ACM, Resend with no-PHI
rule, V1 registration policy, second custodian. **Go** when P1, P2 (at least signed-ready), P3, P4,
P7 and P9 are in hand or scheduled with dates. **No-go** if any BAA is refused.

No launch date is inferred from the implementation-time estimates below. Contract/account availability,
independent review and native Word sessions need actual dates before the critical path can be scheduled.
Necessary Word and ordinary-narrative engineering remains ahead of qualification and real-data admission.

The final V1 configuration must explicitly name `claude-sonnet-5` with its reviewed rates/profile and enable
the qualified `QUILLMD_WORD_ENGINE=v3`, `QUILLMD_WM_NARRATIVE=1`, `QUILLMD_MAPPING_ASSISTANCE=1` and
`QUILLMD_MAPPING_ASSISTANCE_LIVE=1` paths after their acceptance gates clear. These flags are currently off;
their presence in the renderer is preparation, not activation authority. Record actual worker request and
response identity, limits, stop reason, usage and billing for both ordinary generation and blank mapping.
Neither an environment-file edit nor an admin configuration row proves the served worker used that model.
Do not enable an unqualified path merely to satisfy this configuration list; V1 stays blocked instead.

### G1 AWS foundation (1 to 2 days)

1. Organization, accounts, SCPs, Identity Center with hardware MFA, root lockdown (checklist A7-A10).
2. Accept the BAA in AWS Artifact from the management account (P2); save the PDF off-host.
3. CloudTrail organization trail, GuardDuty, Config, S3 Block Public Access, EBS encryption by
   default with `alias/quillmd-production-data`; the two other keys.
4. VPC 10.40.0.0/16, subnets, route tables, S3 gateway endpoint, security groups
   (`production-hosting.md` section 8).
5. Backup account: vault, Vault Lock (compliance, cooling-off starts), logical-backup bucket with
   Object Lock, CloudTrail archive bucket. Production: AWS Backup plan (RDS daily, EBS hourly, copy).
6. RDS: PostgreSQL 16, `quillmd-production`, db.t4g.medium Single-AZ in 1a, 20 GB gp3 with
   autoscaling to 100 GB, private subnet group, `sg-db`, KMS data key, deletion protection,
   automated backups 35 days, parameter group `rds.force_ssl=1`, Performance Insights off,
   RDS-managed master secret, auto minor upgrades in a declared window. Database `quillmd_production`.
7. SNS topic and confirmed subscriptions; ACM certificate (DNS validation CNAMEs at the provider);
   ALB with the HTTPS listener whose **default action is a fixed 503 maintenance response**, with one
   exception rule forwarding `POST /billing/webhook/` (added only at G8); target group not yet
   registered.

**Go** when checklist rows A1 and A7-A10, B1, B3, B5-B8, C2 and the rule sets of C1 have evidence
(C1's port scan, C3 and A11 follow at G3, when the instance exists).
**Rollback:** delete nothing but empty, task-owned resources; the BAA and accounts stay.

### G2 Profile activation commit (half a day, reviewed PR)

1. Read the RDS endpoint (`describe-db-instances`) and download the RDS global CA bundle
   (`https://truststore.pki.rds.amazonaws.com/global/global-bundle.pem`); compute its sha256.
2. PR: set `database.host` and `database.tls.ca_bundle_sha256` in
   `rebuild/ops/production_profile.json`; nothing else. `deployment_profile.py --require-activation`
   must now pass and the test suite stay green. Merge through `scripts/merge-pr.sh`, cite CI on the
   merge commit.
3. Build the release artifact from the merge commit (`build-release.sh <sha> <dir>`), record its
   sha256 in the deploy declaration, upload it to the release bucket. Download the AWS CLI v2 bundle
   for a named version (`awscli-exe-linux-x86_64-<version>.zip`), verify its PGP signature as AWS
   documents, record its sha256, upload it beside the release (the bootstrap installs this bundle,
   not the snap).

**Go** when the artifact's and the CLI bundle's sha256 values are recorded and CI on that exact commit
is green.

### G3 Host bootstrap (2 to 4 hours)

1. Launch the instance: recorded Ubuntu 24.04 AMI ID, m7i.large, subnet 1a, `sg-app`, instance role,
   IMDSv2 required hop limit 1, EBS root 30 GB encrypted, user data `cloud-init.yaml`. Create the
   100 GB gp3 state volume with the data key in 1a and attach it.
2. Through SSM: fetch the release artifact and the AWS CLI bundle, check both sha256 values, extract
   the release to a root staging directory, run `bootstrap-host.sh` **dry run**, read the plan, then
   `--execute` under the committed declaration.
3. Save `/var/lib/quillmd-bootstrap/receipt.json` with the declaration. Remove the bootstrap-only
   `ec2:DescribeVolumes`/`kms:DescribeKey` permissions from the instance role.

**Go** when the receipt shows the release, profile and artifact hashes expected, units installed
and not enabled, the RDS CA hash equal to the profile's, and checklist D1-D5, D7, D8, D10 have
evidence. **Rollback:** terminate the instance and delete the unused volume (no data yet).

### G4 Database initialization (2 to 3 hours, ruled mutation)

1. Record the baseline: the new RDS database has no QuillMD tables and no roles but the master.
2. `database_roles.py --profile production apply` against the live target (P13) creates the four
   production roles; credentials go to `quillmd-production/database-roles` in Secrets Manager and to
   `operator/` only for the act.
3. `with_db_role.py --profile production --role migrator -- migrate --noinput`, then
   `showmigrations` and `check`. Record the migration head and the number of QuillMD integrity
   triggers and their release-bound definitions (107 in this candidate, `len(ops.integrity_contract.GUARDS)`; the installed legacy revision has nine). The restored drill must match the selected release contract and the recorded count; a matching count alone is insufficient.
4. Re-import the recorded public ICD-10-CM releases with `import_terminology` through the wrapper,
   using the exact files, sha256 values and counts from the private import records (FY2026 and
   FY2027). CPT stays disabled.
5. Take a manual RDS snapshot "empty-schema-<sha>"; restore it as a drill instance and run the role
   `verify` (P13) and `production_restore_check.py --expected-triggers <recorded>` there. Delete the
   drill instance.

**Go** when all core business tables are empty except terminology, the triggers are the recorded
number and enabled, and the role verification passed on the drill. **Rollback:** before real data,
the database may be left as is; recreating it is a deletion decision for the owner.

### G5 Services up, still in maintenance (1 hour)

1. Fill `quillmd-production/application-environment` (names only from
   `deployment_profile.ENVIRONMENT_NAMES`): profile declaration, secret key, runtime role
   credentials, pinned DB host/port/name, release SHA, HTTPS and trusted proxy on, Resend (P6),
   Anthropic (P3, `claude-sonnet-5` and its rates), Deepgram (P4), Word runtime manifest hash. **No
   Stripe key yet.**
2. Write `operator/heartbeat-url` (P10). Enable and start the environment unit, then doctor, admin,
   worker; enable nginx; start the heartbeat timer. Register the instance in the target group.
3. Evidence: three launcher proofs with `passed: true`, profile hash and release SHA; target healthy;
   `/health/` through the ALB still answers the fixed 503 (maintenance) from outside, and 200 from the
   host.

**Go** when checklist E1-E3 and E8 have evidence. **Rollback:** stop and disable the units; nothing
has been created by users.

### G6 Operations proven (1 to 2 days)

1. Alerts: labelled SNS test; both custodians record inbox receipt (H1).
2. Missed heartbeat: stop the heartbeat timer for 20 minutes; both custodians record the alert;
   restart (H3). Route 53 health check alarm observed (H4).
3. First AWS Backup jobs and copy jobs succeed (G2 of the checklist); Vault Lock cooling-off ended.
4. Restore drill: PITR to T plus the paired EBS snapshot, `production_restore_check.py` passes;
   measure RTO and RPO (checklist G4). Repeat from the backup account's copies (G5).
5. Host rebuild drill: new instance, attach a volume restored from the latest snapshot,
   `bootstrap-host.sh --existing-state-volume`, proofs pass, target swap, old instance terminated
   (G6); time it.

**Go** when every H row and G1-G6 of the checklist have evidence and the measured RTO is within the
target (4 hours). **No-go** on any alert not received in an inbox.

### G7 Security review (1 to 3 weeks, external)

Independent penetration test against the production target (still in maintenance for the public; the
tester's addresses are allowlisted at the ALB for the window), including tenant isolation and the
admin surface. Every finding retested or accepted in writing by the owner (I1, I2). Counsel's
retention, deletion, data-subject and breach procedures approved (J1-J5). **Go** when the whole
checklist, except rows that only G8/G9 can produce, has evidence.

### G8 Accounts, content and payments (1 day, synthetic content only)

1. First administrator: the declared `bootstrap_first_admin create` makes the exact owner UUID/mailbox
   unverified and nonstaff, with no clinic or welcome credit. The owner uses normal verification-resend,
   verifies the mailbox, signs in on the doctor origin and enrolls TOTP. Declared `elevate` then grants
   staff to that sole account only after both proofs exist and invalidates prior sessions. The owner
   signs in again with MFA on the admin origin. See `host-readiness-20260927.md`; registration stays
   invite-only. Record the account UUID in the declaration. The
   operator recovery procedure for a lost authenticator is signed off (`account-recovery.md`).
2. Templates: the owner re-uploads each authorized blank template (DOCX/AcroForm) from the originals
   he holds; review and approve mappings in production. No filled document is ever uploaded as a
   template.
3. Smoke, synthetic content only, on a dedicated synthetic smoke doctor account created for this and
   kept: one typed and one short voice encounter with synthetic text and synthetic audio, generation,
   review, finalize, export; check usage, ledger and receipts. The smoke account's rows stay (audit
   rows are never deleted). No real patient.
4. Stripe live binding: add the restricted live key and webhook secret to the application secret,
   restart; add the ALB rule forwarding `POST /billing/webhook/` during maintenance; perform the one
   owner-authorized bounded real payment and correlate account, mode, session, event and one paid
   ledger credit (P5).

**Go** when checklist E4-E7 have evidence on production and the payment acceptance is recorded.

### G9 Go-live (2-hour window, then 24-hour watch)

1. Day before: TTL of `app` and `admin` records lowered to 300 seconds.
2. Point `app.quillmd.com` and `admin.quillmd.com` CNAMEs at the ALB. From outside, both answer the
   ALB's maintenance 503 over the ACM certificate. The VPS's Caddy no longer receives traffic for
   these names.
3. **Lift maintenance last:** change the listener default action from the fixed 503 to the target
   group (admin rule keeps its source allowlist). Check `/health/` 200 from outside, the admin MFA
   sign-in from an allowlisted address, the heartbeat, and the smoke account's dashboard (read only).
4. Invite the first doctor. Watch alarms, heartbeat, job states, reconciliation and backups for 24
   hours; the on-call custodian is named in the declaration.

**Go/no-go for step 3:** every earlier gate green; no open alarm; the latest restorable time within
5 minutes; the last backup copy job succeeded; both custodians reachable.

## Rollback

### Before any real data exists (up to G9 step 3)

- Stop at the failing gate; keep what exists; diagnose; retry the gate. Task-owned empty resources
  may be removed after identity verification. The ALB stays in maintenance and DNS may still point
  at the VPS's 503 (no PHI has been sent anywhere).
- The production database holds only schema, terminology, the smoke account and the owner's account.
  Recreating it is an owner decision (deletion), never a shortcut to make a gate pass.

### After real data exists (from the first invited doctor on)

Data-preserving, in this order:

1. **Stop new work at the edge:** set the ALB default action back to the fixed 503 maintenance
   response (seconds; DNS unchanged). Keep the `POST /billing/webhook/` rule so paid funds are still
   credited (Stripe also retries for days). Do **not** point DNS at the VPS: it has no BAA.
2. **Freeze processing:** stop the worker unit (no new provider calls); remove the Stripe key from the
   application secret and restart doctor/admin if Checkout must stop.
3. **Inventory in-flight work:** jobs in `running` or `reconciliation`, held reservations, pending
   payments, through the admin console; nothing is replayed, refunded or discarded automatically.
4. **Fix forward.** Install a schema-compatible release by host replacement (the rebuild path:
   new instance, same state volume moved over, `--existing-state-volume`, `migrate` only forward).
   A code rollback is allowed only to a release whose migrations are a prefix of those applied, that
   enforces real-data mode, and only within the limits in *Code rollback onto a newer schema* below;
   there are no down-migrations. **dedac162 is never a rollback target once real data exists** (next
   section): it is synthetic-only by construction and drops the per-request transcription opt-out.
5. **Data damage** (wrong writes, corruption): restore RDS to a point in time as a **new** instance,
   run `production_restore_check.py`, compare and reconcile the affected rows into the live database
   through a reviewed, declared correction that appends (ledger and audit are immutable). Never
   restore over the live instance and never drop it. A restored instance is never served directly:
   one that must take the live database's place goes through *Restoring a database into service*
   below, and stays quarantined until its admission is recorded.
6. **Host loss:** EC2 auto-recover, or the rebuild path with the surviving volume (RPO 0 for files)
   or the latest snapshot (RPO up to 1 hour for files; database unaffected on RDS).
7. **Suspected PHI exposure:** follow the incident response plan (checklist J5): preserve evidence,
   rotate keys, assess breach notification with counsel on the HIPAA clock.
8. Lift maintenance again only through the G9 step 3 checks.

### Restoring a database into service (quarantine, replay, admission)

Added 2026-09-30 with the restore-admission build (branch `fix/v1-retention-holds`). A restored
database can be older than a disposition instruction or a preservation hold recorded after its
restore point. Both are signed into the independent journal (outside the clinical database and the
state volume) before their database rows commit; a hold release is signed there only after its row
commits, so a release the application reported as not recorded never ends a hold in a restore.
Nothing inside a restored database says it was restored, so the operator selects it, and the
application stays quarantined until an admission record for that selection exists and for as long
as the database lacks anything the journal preserves. No step below deletes restored content, and
none needs a retention period, schedule or duration.

1. Restore RDS (and, if needed, the state volume) as **new** resources; never over the live ones.
   Record a new UUID as the restore instance id in the declaration.
2. Start the restored target with `QUILLMD_RESTORE_QUARANTINE=1`,
   `QUILLMD_RESTORE_INSTANCE_ID=<that UUID>` and the independent journal configured (path, journal
   and checkpoint public keys; the journal file may be read-only for this host). Quarantine answers
   503 for clinical routes and refuses workers and file cleanup.
3. Obtain from the independent checkpoint signer, not from the host, an unexpired signed checkpoint
   of the journal's current head (sequence and head sha256).
4. **Replay.** A verified administrator runs the replay action at `/console/disposition-execution/`
   (the only action offered while quarantined) with that checkpoint. It imports a tombstone for
   every journaled disposition instruction and every journaled hold, each release only after its
   hold. Restored rows are kept. A hold whose target was created after the restore point is
   recorded as `target_absent`; if that target is later put back with its id (a data-damage
   reconcile), the database applies the hold, and its journaled release, as the row is inserted.
   Every journaled release was committed at its source, so it is imported and the hold ends as it
   did there; a hold or release whose custodian's account is absent from the restored database is
   recorded by the administrator running the replay, and its marker keeps the signed entry.
   Every journaled redaction (`core/redaction.py`) is re-applied in journal order with the holds and
   releases: the restored document's content is emptied again, its code suggestions removed, its
   tombstone imported from the signed entry, and the listed file bytes removed from the restored
   volume when they still have the journaled digest. A release journaled after its target was put
   back is applied too (NEW-1, 2026-10-01).
5. **Check:** `manage.py restore_admission --instance-id <UUID> --custodian <administrator email>
   --checkpoint <checkpoint file> --expected-triggers <release count> --check-only`. It prints a
   counts-only report and exits non-zero naming any blocker: `restore_check_failed` (the release's
   production restore check, including every journaled hold being present or recorded absent),
   `tombstone_replay_incomplete`, `hold_replay_incomplete`, `release_replay_incomplete`,
   `redaction_replay_incomplete`, `journal_target_visible`. The release count for this build is 107
   (`len(ops.integrity_contract.GUARDS)`: 92 plus 0033's ten redaction guards and 0034's five coding-ledger guards).
6. **Admit:** the same command without `--check-only` writes the one append-only `RestoreAdmission`
   record for that instance (the database refuses its update, deletion or truncation, and refuses a
   report it can disprove). If the journal grew after the replay, for example a new hold, replay
   again with a fresh checkpoint first.
7. **Lift quarantine:** set `QUILLMD_RESTORE_QUARANTINE=0` and **keep**
   `QUILLMD_RESTORE_INSTANCE_ID` unchanged. Make the journal file **writable** for this host (step 2
   allowed it read-only) and stop the old host's access to it: from here this target is the only
   writer. The application lifts quarantine only while a `RestoreAdmission` exists for that
   instance id **and** the database accounts for every hold and release the journal names (re-read
   whenever the journal file changes); the flag alone does not. If the journal grows past the
   database (another host's hold or release, or a hold here whose database commit failed after its
   journal append), or the journal becomes unreadable or unconfigured, the target answers 503 again:
   repeat step 3 and step 4 (replay stays available while quarantined) and it lifts by itself once
   the replay has imported what was missing; the admission record stands. Removing the instance id
   as well also removes the quarantine, because nothing else identifies the database as restored:
   never remove it from a restored target.
8. Record the instance id, the admission record id, its `report_sha256`, and the journal sequence and
   head in the declaration.

Limits: a hold recorded while no journal was configured, or while the configured journal could not
take the entry (missing, read-only, unverifiable, or at its 1000-entry or 8 MiB bound), is still recorded and
enforced in the database that recorded it, with an error logged and `journaled: false` in its audit
row; until its exact retry (same request key) or its release journals it, a restore older than that
database loses it. A release whose journal copy failed after its commit is logged the same way; a
restore older than it keeps the hold active until the custodian's exact retry journals it. A target
without a configured, verifiable journal cannot be admitted and stays quarantined; the
`production_restore_check.py` drill tool does not read the journal, so the journaled-hold check runs
through `restore_admission` on the target.

### Code rollback onto a newer schema (image rollback without a schema rollback)

Verified 2026-09-28 for the installed private-beta release `dedac162` (core migrations 0001-0018,
byte-identical in V1) on the V1 schema (core 0001-0031): dedac162's own code (`git archive`) was run
against synthetic databases migrated to 0031, and dedac162's own core suite was run on that schema.
Nothing here was tried on a database holding real data. A release older than dedac162 is not verified.

**Before real data only.** Everything in this section applies to an image rollback to dedac162 while
the database holds synthetic data. After real data exists, dedac162 is not a rollback target: fix
forward (step 4 above) or roll back only to a release that enforces real-data mode. Reproduced
2026-09-28 on throwaway synthetic databases, with the provider call replaced by a recorder and the
network denied (MIG-R-1):

- dedac162 is synthetic-only by construction (`SYNTHETIC_ONLY = True` in its settings). Its `/health/`
  reports `synthetic-only` whatever `QUILLMD_DATA_MODE` says, and it refuses to start any document
  without the "These are synthetic clinical notes." attestation. A clinician could continue working
  under it only by attesting that real notes are synthetic.
- dedac162's worker sends every transcription with fixed parameters and never reads the job's
  recorded `deepgram_parameters`, so a recording V1 queued with `mip_opt_out=true` goes to the
  provider **without** it and the job is marked succeeded. V1 in real-data mode refuses to send a
  transcription without the opt-out ("Nothing was sent."). Every new dictation made under dedac162
  would go out without it as well, so draining alone does not close the gap; the account-wide opt-out
  (P4) reduces the exposure but does not restore the per-request control.

- **Never reverse a migration to make an older release work.** 0020, 0021, 0022, 0025 to 0028, 0030
  and 0031 refuse to reverse while their evidence exists (live payments or Stripe events; v3 mapping
  confirmations, contracts or corrections; mapping jobs; retention holds and preserved records;
  generation batches; disposition rows; for 0031, the same v3 mapping evidence as 0021). A refusal is
  atomic for that one migration only: every later migration has already been reversed and committed,
  so the database is left at an intermediate node (the refusals of 0020, 0021 and 0031 say so: "has
  already been reversed and stays reversed"; the database-side refusals of 0022, 0025 to 0028 and 0030
  do not). Run `migrate` forward again before starting any release.
- **0031 refuses first.** It is the first migration reversed by any rollback toward dedac162's schema
  (`migrate core 0018`, `0020`, `0030`, or any target before it), so on a database holding v3 mapping
  evidence such a rollback is refused before anything core owns is dropped: 0031 stays applied, and so
  does the database's confirmation gate. **Never target `zero`.** `otp_totp` depends on core 0001
  (through the user model), so `migrate core zero` unapplies `otp_totp` 0003 to 0001 **before** 0031
  refuses: every TOTP enrollment is dropped, `migrate` forward recreates the table empty, and every
  clinician is offered enrollment again without the old second factor (MIG-R-2, measured 2026-09-28).
  The supported target is `migrate core 0018`, which does not touch `otp_totp`; 0031's refusal message
  says this. Before this, 0021 refused only after 0022 to 0031 had been reversed and
  committed while its message said "Nothing was changed."; 0031's gate was gone, dedac162 started a
  draft on a never-confirmed v3 mapping, re-applying 0031 did not look at that draft, and V1 finalized
  and exported it (R1). A migration added after 0031 is reversed before 0031 is reached; if it drops
  anything a rollback cannot give back, it needs its own guard.
- **Why 0031 exists.** 0021 and 0022 added `core_templateversion.contract`, `corrections` and
  `assistance` NOT NULL with no database default. On a 0030 schema dedac162's template upload and
  mapping edit therefore failed with IntegrityError (a 500), and every failed upload left its stored
  original behind in `originals/` (dedac162 removes it only on a validation or document error). 0031
  gives the three columns database defaults (`''`, `{}`, `{}`), so dedac162's versions are recorded as
  the legacy mappings they are. `core.tests.test_migration_rollback_safety` fails if a later migration
  adds a NOT NULL column without a database default to any table dedac162 writes; move its
  `PREVIOUS_RELEASE` when the installed release changes.
- **What works under dedac162 on 0031** (measured by driving its views, and by its own core suite on
  this schema): uploading a blank form; editing the labels of a legacy mapping (a new version);
  starting, generating, reviewing, finalizing and exporting documents on legacy mappings. dedac162's
  core suite on this schema: 1122 tests, 5 errors. Four also error on dedac162's own schema in the
  test environment (two modules that do not import; two terminology imports that refuse a database
  not named `quillmd_*`). The fifth is a test fixture that changes an existing job's `kind`, which
  0022's job-scope trigger refuses; dedac162's application code never changes a job's kind.
  Measured again after R1's repair with a test-harness shim, which changes only the test flush:
  dedac162's test flush TRUNCATEs only its own tables, which Postgres
  refuses on this schema (V1-only tables such as `core_retentionhold` and `core_clinicinvitation`
  reference `core_patient` and `core_user`) and which V1's TRUNCATE guards refuse, so the shim lifts
  those guards for the flush as V1's own `core/tests/__init__.py` does and adds CASCADE. Without it
  the same run has 27 errors: the 5 above, 14 failed flushes and 8 duplicate keys left behind by
  them, test for test the same on the schema before R1's repair. Production never flushes, so this is
  not an application behavior.
- **What the database refuses under dedac162, by design** (the request fails with a 500 and writes
  nothing):
  1. editing the labels of a contract v3 mapping. dedac162 knows no contract and copies the v3 fields
     into a new version; CHECK `mapping_v3_fields_record_v3_contract` refuses it, because the row
     would otherwise read as a legacy mapping that needs no confirmation once V1 is installed again;
  2. starting a document on a contract v3 mapping that no clinician has confirmed. dedac162 has no
     confirmation gate; `quillmd_encounter_guard` refuses it. Without this guard the draft dedac162
     started was saved, finalized and exported after V1 was re-installed, with the mapping still
     unconfirmed (V1 checked confirmation only when a document was started).
- **A document on an unconfirmed v3 mapping is held, never finalized.** The same guard refuses any
  move to `finalized` of a document whose mapping is contract v3 with no confirmation, whoever writes
  it, and V1's finalize refuses it first with a message naming the mapping version ("has not been
  confirmed by a clinician ... Nothing was finalized"), before anything is filled. Such a document can
  exist only if it was started while 0031's gate was missing (0031 reversed on a database without v3
  evidence, a v3 mapping recorded afterwards, and dedac162 run on it). Re-applying 0031 does not refuse
  it: the draft and its review are kept, and it finalizes once a clinician confirms that mapping
  version (V1 confirms only a form's current mapping version; for an older one, start a new document
  from the confirmed mapping). After any `migrate` forward from a rollback, count them:

      SELECT count(*) FROM core_encounter e JOIN core_templateversion v ON v.id = e.template_version_id
       WHERE v.contract = 'v3' AND e.status <> 'finalized'
         AND NOT EXISTS (SELECT 1 FROM core_mappingconfirmation c WHERE c.version_id = v.id);

  A non-zero count is not an error; tell the department's clinicians which forms need confirming.
- **What cannot work under dedac162:** a document on a *confirmed* v3 mapping can be started and
  generated (measured in fixture mode; live-mode charging was not exercised), but dedac162's export
  refuses every v3 mapping ("The field mapping does not match this original"), so such documents stay
  in review until V1 is installed again. Before an image rollback, count what would be stranded:

      SELECT count(*) FROM core_templateversion WHERE contract = 'v3';
      SELECT count(*) FROM core_encounter e JOIN core_templateversion v ON v.id = e.template_version_id
       WHERE v.contract = 'v3' AND e.status <> 'finalized';

  If either is non-zero, v3 forms cannot be exported while dedac162 runs; fix forward instead.
- **Drain every job except generation first.** dedac162's worker takes the oldest queued job of any
  kind. It failed a queued blank-mapping job (kind `mapping`, no document) with the misleading error
  "Access was revoked before processing." (measured in fixture mode, which holds no funds), and it
  sends a queued V1 transcription without its recorded opt-out (above). Batch-generation children
  (kind `generation_part`, off unless `QUILLMD_V3_GENERATION_BATCHES=1`) were not exercised. Before
  an image rollback this must return no rows (it counts `queued` transcriptions, which the earlier
  version of this query excluded; step 3's inventory counts only `running` and `reconciliation`):

      SELECT kind, state, count(*) FROM core_job
       WHERE kind <> 'generation' AND state IN ('queued', 'running', 'reconciliation')
       GROUP BY kind, state;

### Release updates after go-live

Every later release is installed the way recovery works: a new instance from the recorded AMI and
the new release artifact, the state volume moved over in a declared maintenance window, forward
migrations through the wrapper, proofs, target swap. The recovery path is therefore exercised on
every release instead of only in drills.


### Production backup panel preparation (2026-09-27)

The root operator AWS metadata collector, explicit production publisher and disabled service/timer
are prepared. Use [the configuration, read-role and publication-exclusion steps](aws-backup-status-20260927.md)
during the authorized target cutover. Validate the real account and exact installed profile first;
run one publisher and inspect its row before enabling the timer. A capture-current warning still
requires the independent restore drill and delivered-alert gates. This package provides no actual
AWS execution, restore or alert-delivery evidence.
