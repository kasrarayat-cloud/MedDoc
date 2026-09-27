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
   triggers (nine today; the recorded number is what drills expect).
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
   A code rollback is allowed only to a release whose migrations are a prefix of those applied; there
   are no down-migrations.
5. **Data damage** (wrong writes, corruption): restore RDS to a point in time as a **new** instance,
   run `production_restore_check.py`, compare and reconcile the affected rows into the live database
   through a reviewed, declared correction that appends (ledger and audit are immutable). Never
   restore over the live instance and never drop it.
6. **Host loss:** EC2 auto-recover, or the rebuild path with the surviving volume (RPO 0 for files)
   or the latest snapshot (RPO up to 1 hour for files; database unaffected on RDS).
7. **Suspected PHI exposure:** follow the incident response plan (checklist J5): preserve evidence,
   rotate keys, assess breach notification with counsel on the HIPAA clock.
8. Lift maintenance again only through the G9 step 3 checks.

### Release updates after go-live

Every later release is installed the way recovery works: a new instance from the recorded AMI and
the new release artifact, the state volume moved over in a declared maintenance window, forward
migrations through the wrapper, proofs, target swap. The recovery path is therefore exercised on
every release instead of only in drills.
