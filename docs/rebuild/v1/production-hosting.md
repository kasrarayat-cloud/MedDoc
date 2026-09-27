# QuillMD V1 production hosting (AWS, BAA-covered)

Prepared 2026-09-27 for the invited, real-patient V1. **Nothing is provisioned.** This document, the
production profile and the files under `rebuild/deploy/production/` are the package a declared
activation will execute. The Hostinger VPS stays synthetic-only: Hostinger's Hosting Agreement
(last revised 2026-08-28, section 4) says its services "should not be used or considered as" a HIPAA
environment, and it covers VPS explicitly. HHS guidance (cloud computing FAQ, Q1/Q5) makes any cloud
provider that stores ePHI a business associate even when it only holds encrypted data, so every
storage and processing provider below needs a signed BAA before the first real record.

Companion documents: `production-cost.md` (monthly and per-encounter cost),
`production-security-checklist.md` (configuration checklist with a "verified by" column) and
`cutover-plan.md` (gates, order, timings and rollback).

## 1. Decisions at a glance

| Question | Decision | Section |
| --- | --- | --- |
| Region | `us-east-1`, one VPC, two AZs for the load balancer and the database subnet group | 3 |
| Compute | one EC2 `m7i.large` (2 vCPU, 8 GiB, x86_64), Ubuntu 24.04 LTS | 3 |
| Database | **Amazon RDS for PostgreSQL 16**, Single-AZ at launch, PITR, KMS, deletion protection | 4 |
| Host state | encrypted EBS gp3 volume at `/var/lib/quillmd-production` (KMS CMK), no LUKS | 7 |
| Operator access | SSM Session Manager only; no SSH port, sshd disabled; no Docker on the host | 8 |
| TLS | ACM certificate on an Application Load Balancer; TLS again from ALB to host | 9 |
| DNS | keep the existing DNS provider; add CNAMEs for `app` and `admin` | 10 |
| Secrets | AWS Secrets Manager, rendered at boot to a root-only tmpfs file | 11 |
| Logs | CloudWatch receives metrics, CloudTrail and AWS service events only; application logs stay on the host | 12 |
| Backups | RDS automated backups (PITR, 35 days) + AWS Backup (RDS daily, EBS hourly) copied to a vault-locked vault in a separate backup account | 13 |
| Alerts | CloudWatch alarms and EventBridge rules to SNS email; outside-host heartbeat (Healthchecks.io) | 15 |
| Email | keep Resend with the enforced no-PHI rule for V1; Amazon SES is the ready fallback | 16 |

## 2. The production profile in code

Every host-specific value is bound in ONE reviewed record, `rebuild/ops/production_profile.json`,
validated by `rebuild/ops/deployment_profile.py`:

| Bound value | Production | Private (unchanged, never read from the record) |
| --- | --- | --- |
| install root | `/opt/quillmd-production` (app at `rebuild/`) | `/opt/meddoc-pro` |
| state root | `/var/lib/quillmd-production` (mounted EBS volume) | `/var/lib/quillmd` (LUKS loop file) |
| configuration | `/etc/quillmd-production` (`operator/`, `ingress/` root 0700) | `rebuild/.env`, `.runtime/` |
| environment file | `/run/quillmd-production/application.env` (tmpfs, from Secrets Manager) | `/opt/meddoc-pro/rebuild/.env` |
| service identity | `quillmd-production-app`, uid = gid = 931, non-login | `quillmd-app` (996/988) |
| units | `quillmd-production-{environment,doctor,admin,worker,heartbeat}` | `quillmd-fresh-*` |
| loopback ports | doctor 9140, admin 9141 | 9130, 9131 |
| database | RDS `quillmd-production`, db `quillmd_production`, port 5432, `sslmode=verify-full` with a pinned CA bundle | container `quillmd-fresh-postgres` on 127.0.0.1:55438 |
| roles | `quillmd_production_{owner,runtime,migrator,backup}` | `quillmd_{owner,runtime,migrator,backup}` |
| public origins | `https://app.quillmd.com`, `https://admin.quillmd.com` | preview `:9443` |
| modes | data `real-patient`, payment `stripe-live`, email `resend` (no-PHI fixed templates), AI `anthropic`/`live` | synthetic-only, Stripe test, file or allowlisted Resend |

Refusals, all with fixed labels and all tested:

- **Missing or unactivated record.** The RDS endpoint cannot be known before provisioning, and the
  RDS CA bundle hash is pinned together with it from the bundle fetched for the host; both are
  `null` in the checked-in record and `load_production()` refuses it (`profile_not_activated`). The activation commit pins both, so
  production services cannot start from an unreviewed value.
- **Mixed record.** Any path overlapping a private path, the private account, identity numbers,
  unit prefix, ports, database or role names is `profile_mixed`; the preview origin (it carries a
  port) and any other malformed origin is `profile_value`. Unknown or missing keys, wrong types and
  values outside the fixed vocabulary refuse too.
- **Mixed environment.** The production launcher (`service_launcher.py --profile production`)
  refuses an environment file without `QUILLMD_DEPLOYMENT_PROFILE=production`, with another runtime
  user/database/endpoint, a Stripe key that is not a restricted live key, another email mode or
  origin, fixture AI mode, HTTPS or trusted proxy off, any private-preview setting, or any inherited
  `PG*` variable. A production environment file cannot start the private units (wrong runtime user).
- **Mixed host.** The production launcher refuses when Docker exists (a denied socket counts as
  present), when `/opt/meddoc-pro` exists, when the state root is not a mounted volume, or when the
  CA bundle is not root-owned and byte-identical to the pinned hash.
- **Instance metadata.** The primary control is the units' `IPAddressDeny=169.254.169.254/32
  fd00:ec2::254/128`, a cgroup egress drop on both protocols. A test reads each shipped unit and
  any drop-in the package ships the way systemd applies `IPAddressAllow=`/`IPAddressDeny=` (in
  order, an empty assignment resets that list, an allow entry overrides a deny, `any`,
  `localhost`, `link-local` and `multicast` expand as systemd expands them) and fails if any unit
  but the root secret renderer could reach either address. It sees only the package: a drop-in or
  slice configured on the host is outside it. The heartbeat unit has no launcher, so for it this
  test is the only check.
- **The launcher's own check** (doctor, admin and worker, at start). For 169.254.169.254 an empty
  UDP datagram must fail with EPERM AND a TCP connect must not complete within 2.5 s (a connect the
  kernel completed before the deadline but had not reported counts as completed).
  fd00:ec2::254 must pass the same test or have no route from this host (no IPv6 path, IPv6
  disabled, or no IPv6 stack). That is what the units' egress drop produces (UDP fails with EPERM,
  TCP only times out), and it adds 2.5 s to each start; the whole check takes at most 3 s. A
  UDP-only or TCP-only block, or an open IPv6 path, refuses. **Its limit:** a TCP handshake that
  completes only after 2.5 s is not seen, so a UDP-only rule in front of an IMDS that slow would be
  accepted (measured: accepted when the handshake completed after the window, refused at 1.86 s
  and at 2.03 s). The check proves what this process could reach at start; the unit deny is what
  keeps it true.

The private launcher path is proven unchanged by a differential test against a byte-identical copy
of the launcher as it was before profiles existed (`rebuild/ops/fixtures/`), and the same for the
role wrapper. The Word processor's managed-root check now pairs each launcher-fixed state root with
its reviewed Word installation, so the qualified engine runs from `/opt/quillmd-production` on the
production host and exactly as before on the VPS.

## 3. Architecture

```
            Internet
               |
   Route: app.quillmd.com, admin.quillmd.com (CNAME at the existing DNS provider)
               |
   +-----------v-------------------------------------------- VPC 10.40.0.0/16, us-east-1 ---+
   |  public subnets 10.40.0.0/24 (1a), 10.40.1.0/24 (1b)                                   |
   |   [ALB :443, ACM cert, TLS1.2+/1.3]  -- listener rules: app host -> target group        |
   |        |                                        admin host + source-IP allowlist -> TG  |
   |        | TLS to target :8443 (sg-alb -> sg-app)       otherwise fixed 403/404            |
   |   [EC2 m7i.large, Ubuntu 24.04, public IPv4 for egress only, no inbound from Internet]  |
   |     nginx :8443 -> 127.0.0.1:9140 doctor / :9141 admin (gunicorn, launcher-proven)       |
   |     worker; Word engine (.NET 8, sandboxed); ffmpeg; heartbeat timer                     |
   |     EBS root 30 GB gp3 (KMS) + EBS state 100 GB gp3 (KMS) at /var/lib/quillmd-production |
   |        | 5432, TLS verify-full (sg-app -> sg-db)                                          |
   |  private subnets 10.40.10.0/24 (1a), 10.40.11.0/24 (1b): no route to the Internet        |
   |   [RDS PostgreSQL 16 db.t4g.medium, Single-AZ, KMS, PITR, not publicly accessible]       |
   |  S3 gateway endpoint (free) for release artifacts and logical backups                   |
   +------------------------------------------------------------------------------------------+
        egress 443: Anthropic, Deepgram, Stripe, Resend, AWS APIs, Healthchecks.io; 80: Ubuntu apt
   Backup account (same Organization): AWS Backup vault with Vault Lock, cross-account copies
```

The instance sits in a public subnet with a public IPv4 address **for egress only**; its security
group admits nothing from the Internet. This avoids a NAT gateway ($32.85/month plus $0.045/GB).
The ALB needs two AZs; the instance and the RDS primary sit in the same AZ (1a) so application
database traffic stays inside one AZ.

**Capacity assumptions (expected case).** 10 invited doctors, 15 encounters per doctor per working
day, 22 working days: about 3,300 encounters a month, 70% with voice at 8 minutes each (about 18,500
audio minutes a month, transcribed by Deepgram, not on the host), one Word fill and export per
encounter. Low: 3 doctors, about 800 encounters. High: 25 doctors, about 11,000 encounters.

**Memory (the host no longer runs PostgreSQL).** The units cap doctor 768 MiB, admin 512 MiB and
worker 1024 MiB (the qualified Word engine and ffmpeg run inside those cgroups; the Word helper's
measured peak resident memory was about 85.5 MiB, `sdk-boundary.md`). Nginx, the SSM and CloudWatch
agents and the OS need about 1.5 GiB. That is about 3.8 GiB at the caps, leaving about 4 GiB of page
cache on 8 GiB. An optional LibreOffice render service (evidence rendering for Word review) would add
about 1 to 1.5 GiB per concurrent render; if it becomes part of production, move to `m7i.xlarge`
(16 GiB). `m7i.large` is chosen over `t3.large` because the Word fill and audio normalisation are
bursty CPU work and a burstable instance adds CPU-credit charges ($0.05 per vCPU-hour in unlimited
mode) and throttling risk; Graviton types are excluded because the qualified Word engine is a
self-contained x86_64 .NET build and an ARM build would need its own qualification.

**Storage growth.** Uploads are capped at 15 MB (`core/audio.py`, `core/security.py`); a browser
recording of 8 minutes is typically 2 to 4 MB, and exports and provider receipts add about 0.2 MB per
encounter. Nothing is deleted today (retention is an open, counsel-owned item), so state grows by
roughly 3 MB per voice encounter: about 2.5 GB/month (low), 10 GB/month (expected), 33 GB/month
(high). The 100 GB state volume covers about ten months at the expected rate and gp3 volumes grow
online; the disk alarm fires at 80%. The database is small (rows, not files): 20 GB gp3 with storage
autoscaling to 100 GB.

## 4. Database decision: RDS for PostgreSQL (option B)

Evidence from `rebuild/ops` and `rebuild/deploy` (tree at this branch). Every database operation the
private tools perform goes through Docker:

| Tool | Docker or host pin | Under A (container on EBS) | Under B (RDS) |
| --- | --- | --- | --- |
| `ops/database_roles.py:27-39` | `docker exec -i <container> psql` for every role statement | works | must connect directly (psycopg, verify-full) |
| `ops/database_roles.py:47-65` | identity = container ID + port binding 127.0.0.1:55438; maintenance role must be `rolsuper` | works after renaming | identity from `rds describe-db-instances`; the RDS master user is **not** a superuser (`rds_superuser`), so the check and possibly the `NOSUPERUSER/NOREPLICATION/NOBYPASSRLS` clauses (line 113) must change; verify on a drill instance |
| `ops/database_roles.py:226-228` | `docker exec … pg_dump` as the backup role | works | host `pg_dump` (postgresql-client-16) over TLS |
| `ops/backup_restore.py:160-204` | source pinned to 127.0.0.1:55438 and the container's ID/image | works after re-pinning | source from the profile; identity = RDS `DbiResourceId` |
| `ops/backup_restore.py:247-249` | `docker exec … pg_dump --snapshot` | works | host `pg_dump --snapshot` over TLS |
| `ops/backup_restore.py:276-440` | restore-check starts a networkless container and runs `pg_restore`/`psql` inside it | works (needs Docker on the production host) | restore to a drill RDS instance and run `ops/production_restore_check.py` (added) |
| `ops/activate_runtime_role.py:24-48` | container ID, port 55438, rewrites the private `.env` | works after re-pinning | not needed: credentials live in Secrets Manager |
| `ops/private_storage.py:391`, `ops/managed_helper.py:21-143`, `ops/install_*` | root actions through `docker run --pid=host` helpers | the operator must be in the docker group (root-equivalent) | not used: root actions run through SSM, audited in CloudTrail |
| `ops/install_unit_policy.py:67` | installs units with a Docker chroot | same | replaced by `deploy/production/bootstrap-host.sh` |
| `deploy/quillmd-fresh-database.service:13-17`, `quillmd-fresh-volume.sh:97` | `docker start/stop/exec` on the container | works | not used |
| `ops/with_db_role.py` (private target) | 127.0.0.1:55438, `quillmd_fresh` | re-pin | **done**: `--profile production` |
| `ops/service_launcher.py` | probes `/run/docker.sock` denial, DB user/name | re-pin | **done**: `--profile production` requires Docker absent |

| Criterion | A: PostgreSQL container on encrypted EBS | B: Amazon RDS for PostgreSQL |
| --- | --- | --- |
| Recovery point | daily logical capture (24 h) unless WAL archiving is added (new tooling) | PITR from continuous backups, typically within five minutes; automated backups up to 35 days |
| Host loss | database lost with the host unless the volume survives | unaffected; the host is stateless apart from the state volume |
| Docker on the production host | required (container, restore-check, all root helpers); the docker group is root-equivalent, a standing risk in `storage-encryption.md` and `pentest-scope.md` | not needed; the production launcher refuses a host that has it |
| Patching | manual image updates | minor versions in a maintenance window |
| Encryption | EBS with KMS | RDS with KMS; snapshots inherit it |
| Tool reuse | high, but every tool still needs a production target and the Docker root path stays | role tool and capture need a direct-connection path (specified below); restore check added |
| Monthly cost (expected) | $0 database line, but a larger instance for PostgreSQL memory | $47.45 (db.t4g.medium Single-AZ) + $2.30 storage |

**Recommendation: B.** It removes Docker, and with it the root-equivalent operator path, from the
production host; it gives a five-minute recovery point instead of 24 hours; host loss no longer
threatens the database; and its backups are admitted by AWS-enforced policy rather than by a local
lease. Its cost is about $50/month. Multi-AZ doubles the database line ($94.17) and is deferred until
the doctor count or an availability commitment needs it; the RTO below is written for Single-AZ.

**Implemented here:** the production profile (RDS endpoint pinned at activation, `verify-full` TLS,
CA bundle hash), the launcher path, the role wrapper's production target
(`with_db_role.py --profile production`), the Word root pairing, and the drill check
`ops/production_restore_check.py` (triggers, invariants and every referenced file against a restored
volume, counts only).

**Specified, not implemented (must land before the step that uses it):**

1. `database_roles.py --profile production`: execute through `psycopg.connect(host=<profile host>,
   sslmode='verify-full', sslrootcert=<profile CA>)` instead of `docker exec`; identify the target by
   `aws rds describe-db-instances --db-instance-identifier quillmd-production` requiring
   `Endpoint.Address` = profile host, `StorageEncrypted` true with the data key, `PubliclyAccessible`
   false, `DeletionProtection` true, engine major 16; accept the master user as maintenance role by
   membership in `rds_superuser` instead of `rolsuper`; create roles with only `LOGIN`/`NOLOGIN` and
   let the existing verify step assert that no managed role has a privileged flag; take role names
   from the profile; run `verify` only against a drill instance (never live). Needed at cutover G4.
2. `backup_restore.py` logical capture for production: source and identity from the profile and RDS;
   host `pg_dump --snapshot` over TLS; read files as root in a sandboxed oneshot (the private helper
   uses Docker); stream-encrypt so the 256 MiB Fernet plaintext limit does not cap growth; upload
   each file object once (the object name is per path and files are write-once) to the backup
   account's S3 bucket with Object Lock; key in the backup account's Secrets Manager plus a sealed
   offline copy. This is the provider-independent logical layer; it is required within 30 days of
   go-live, not at go-live, because AWS Backup already provides a locked, separate-account copy.
3. The admin console's backup panel (`publish_operations_status`) reads the private B2 status; in
   production it should publish AWS Backup job results and RDS latest-restorable-time through a
   read-only role. Until then the panel reads "never published", which the console already shows
   honestly, and the SNS alarms are the backup signal.

## 5. AWS services and HIPAA eligibility

Source: AWS "HIPAA Eligible Services Reference", <https://aws.amazon.com/compliance/hipaa-eligible-services-reference/>,
page "Last Updated: September 3, 2026", retrieved 2026-09-27 (sha256 of the saved page recorded in the
investigation evidence). Each name below appears on that list verbatim. "All features of HIPAA
Eligible services are also eligible … unless specifically noted otherwise", so CloudWatch alarms,
Session Manager and Parameter Store are covered as features of their listed services (inference from
that clause).

| Service | Used for | Listed |
| --- | --- | --- |
| Amazon EC2 | application host | yes |
| Amazon EBS | root and state volumes, snapshots | yes |
| Amazon RDS (PostgreSQL engine) | database | yes, "[… PostgreSQL … engines only]" |
| Amazon S3 | release artifacts, logical backups, CloudTrail logs | yes |
| AWS KMS | all encryption keys | yes |
| AWS Backup | RDS and EBS backups, cross-account copy, Vault Lock | yes |
| Amazon CloudWatch, CloudWatch Logs | metrics, alarms, AWS service logs (no application logs) | yes |
| Amazon SNS | alert email | yes |
| Amazon SES | fallback transactional email (not used at launch) | yes |
| Elastic Load Balancing | ALB | yes |
| AWS Secrets Manager | application environment, role credentials | yes |
| AWS Systems Manager | Session Manager, Run Command | yes |
| AWS Certificate Manager | public TLS certificate | yes |
| Amazon Route 53 | health check (and DNS if moved later) | yes |
| AWS WAF | managed and rate-based rules on the ALB | yes |
| Amazon GuardDuty, AWS Config, AWS CloudTrail | detection, configuration history, API audit | yes |
| Amazon VPC, Amazon EventBridge, IAM Identity Center | network, alert routing, operator sign-in | yes |

AWS Organizations and IAM are not on the list; they hold no PHI and must never be given any (no
patient data in names, tags, descriptions or policy text). **PHI is processed and stored only in the
listed services, in the account(s) the BAA covers.**

Outside AWS, each with its own agreement: Anthropic (HIPAA-ready API organization, BAA accepted after
2026-04-01 so structured outputs are covered), Deepgram (BAA offered to Enterprise customers per
deepgram.com/pricing on 2026-09-27; the transcription call must also carry the model-improvement
opt-out, currently missing at `core/jobs.py:495`), Stripe (no PHI by contract, Services Agreement
section 4.5), Resend (no BAA; no PHI, section 16), Healthchecks.io (receives a body-less ping only).

## 6. The AWS BAA, accounts and identities

- **Who accepts.** The AWS BAA is accepted in AWS Artifact > Agreements by a user with administrative
  permissions after accepting the Artifact NDA; AWS recommends consulting legal first. Accept it **at
  the Organization level from the management account** ("all features" must be enabled): "All
  existing and subsequent member accounts are automatically covered". The acceptor is the owner as
  the company's authorized representative. This is an owner act (a contract, and the keys to the
  accounts it covers).
- **Accounts.** `quillmd-management` (Organization, billing, Artifact, Identity Center; no workloads),
  `quillmd-production` (all PHI resources), `quillmd-backup` (backup vault with Vault Lock, logical
  backup bucket with Object Lock, CloudTrail archive). A compromise of production credentials cannot
  delete the backup account's copies.
- **Guardrails (SCPs on production and backup):** deny leaving the Organization, deny disabling
  CloudTrail/GuardDuty/Config, deny `kms:ScheduleKeyDeletion` and `kms:DisableKey` outside the
  break-glass role, deny regions other than us-east-1, deny `ec2:ModifyInstanceMetadataOptions` that
  re-enables IMDSv1, deny public S3 ACLs and policies (S3 Block Public Access at account level).
- **People.** IAM Identity Center users with phishing-resistant MFA (hardware keys), two
  permission sets: `Operator` (SSM Session Manager to the instance, read-only elsewhere, no Secrets
  Manager read of the application secret) and `Administrator` (time-bound, used for declared acts).
  A Session Manager shell can use sudo, so anyone with `Operator` is trusted with everything on the
  host, including the rendered secrets and the state volume; the two sets differ in AWS API reach,
  not in host reach. Keep the `Operator` group to the two custodians.
  No IAM users except break-glass. Root user of every account: hardware MFA, no access keys,
  credentials sealed under two-person custody (section 14).
- **Machine identities.** Instance role: the `AmazonSSMManagedInstanceCore` managed policy, `secretsmanager:GetSecretValue`
  on `quillmd-production/application-environment` only, `kms:Decrypt` via the secrets key,
  `s3:GetObject` on the release bucket, CloudWatch agent put-metric. During bootstrap only,
  `ec2:DescribeVolumes` and `kms:DescribeKey` (removed after). The application identity cannot use
  this role: the units deny the metadata address and the launcher proves the denial.

## 7. Encryption and keys

| Key (customer managed, KMS, account) | Protects | Rotation |
| --- | --- | --- |
| `alias/quillmd-production-data` (production) | EBS root and state volumes (EBS encryption by default enabled for the region), RDS storage and snapshots, AWS Backup recovery points in the production vault | automatic yearly |
| `alias/quillmd-production-secrets` (production) | Secrets Manager secrets | automatic yearly |
| `alias/quillmd-backup-vault` (backup) | the backup account's vault copies, the logical backup bucket (SSE-KMS), CloudTrail archive | automatic yearly |

Key policies grant use to the specific roles only; `ScheduleKeyDeletion` is denied by SCP except to
the break-glass role, with a 30-day window if ever used. EBS encryption by default is enabled before
the instance is launched, so no unencrypted volume can be created in the region. RDS is created with
`StorageEncrypted=true` and the data key (it cannot be added later). S3 buckets use SSE-KMS, Block
Public Access, versioning and TLS-only bucket policies. In transit: TLS 1.2+ at the ALB, TLS from the
ALB to the host, `sslmode=verify-full` to RDS (`rds.force_ssl=1`), HTTPS to every provider. The LUKS
design of the VPS is not carried over: its key file sat beside the data; KMS keeps the key off the
host and still allows unattended boot.

## 8. Network, security groups and operator access

| Group | Inbound | Outbound |
| --- | --- | --- |
| `sg-alb` | 443 and 80 (redirect only) from 0.0.0.0/0 and ::/0 | 8443 to `sg-app` |
| `sg-app` | 8443 from `sg-alb` only. **No 22.** | 443 to 0.0.0.0/0 (providers, AWS APIs), 80 to 0.0.0.0/0 (Ubuntu apt), 5432 to `sg-db` |
| `sg-db` | 5432 from `sg-app` (a drill instance gets its own group admitting only the drill runner) | none |

Operators reach the host only through **SSM Session Manager** (IAM-authorized, logged in CloudTrail,
session transcripts to the backup account's S3 bucket with PHI-conscious retention); `sshd` is
disabled by `cloud-init.yaml` and `bootstrap-host.sh`. No operator account is in a docker group
because there is no Docker. IMDSv2 is required (`HttpTokens=required`, hop limit 1). RDS is not
publicly accessible and lives in subnets without an Internet route. The host is single-tenant: no
other workload, project or co-tenant runs on it or in the production account.

## 9. TLS: ACM on an Application Load Balancer

Chosen over Let's Encrypt on the host because:

1. the public certificate's private key never exists on the host, so a host compromise cannot take
   it (the host holds only the self-signed key of the ALB-to-host hop, which proves nothing to a
   browser); ACM renews automatically (host certbot also needs a working reload hook, which this programme has already
   had to repair once on the VPS);
2. the instance has no Internet-facing port at all, only 8443 from the ALB;
3. AWS WAF attaches to the ALB: managed rule groups and a per-IP rate-based rule protect login,
   registration and recovery at the edge, independently of the application's own limits;
4. listener rules can restrict `admin.quillmd.com` to operator source addresses before any request
   reaches the host (nginx repeats the allowlist, `deny all;` until reviewed addresses are added);
5. target health checks and ALB metrics feed the alarms and make host replacement a target swap.

Cost: about $16.43/month plus LCUs and two public IPv4 addresses ($7.30); see `production-cost.md`.

Configuration: HTTPS listener with the ACM certificate for `app.quillmd.com` and `admin.quillmd.com`,
security policy `ELBSecurityPolicy-TLS13-1-2-2021-06`, HTTP listener redirecting to HTTPS; rules
`host=app` → target group, `host=admin AND source-ip in allowlist` → target group, other admin → fixed
403, default → fixed 404. Target group HTTPS:8443, health check `GET /health/` expecting 200 (nginx
sends it to the doctor application). ALB access logs stay **off**: URLs carry verification,
invitation and recovery capability tokens. Nginx on the host takes the client address from the
ALB's `X-Forwarded-For` only when the previous hop is inside the VPC and passes it as `X-Real-IP`.

## 10. DNS

Keep the existing DNS provider for V1. `app.quillmd.com` and `admin.quillmd.com` are subdomains, so a
CNAME to the ALB's DNS name works at any provider, and the ACM validation CNAMEs can live there too;
moving the whole `quillmd.com` zone (marketing site, mail records for Resend) to Route 53 would add
risk to the cutover without adding a control. Required: MFA and registrar lock on the DNS/registrar
account (a hijacked record would phish doctors' credentials), TTL 300 on the two records from the
day before cutover. Route 53 is used for the outside health check (section 15); moving the zone later
is a separate, reversible change.

## 11. Secrets

AWS Secrets Manager, KMS key `quillmd-production-secrets`:

| Secret | Contents | Read by |
| --- | --- | --- |
| `quillmd-production/application-environment` | JSON of the application's environment names (only names in `deployment_profile.ENVIRONMENT_NAMES`) | the instance role, through `quillmd-production-environment.service` at boot |
| RDS-managed master secret | master user (maintenance only) | break-glass and declared role acts |
| `quillmd-production/database-roles` | migrator and backup role credentials (the wrapper's credential file shape) | operators during declared acts, written to `operator/` for the act and shredded after |
| `quillmd-production/heartbeat-url` | the outside check's ping URL | written to `operator/heartbeat-url` at activation |

At boot, the environment unit renders the application secret into `/run/quillmd-production/`
(tmpfs, root 0700, file 0600) and systemd removes it when the unit stops. The application identity
cannot read that file or reach the metadata service, both proven by the launcher at every start.
Rotation: the Django secret key, provider keys and the runtime role password rotate by updating the
secret and restarting the units (a declared act); the RDS master password rotates through RDS.

## 12. Logging without PHI

- **Leaves the host:** CloudWatch agent metrics (memory, swap, disk, iowait), ALB/RDS/EC2/AWS Backup
  metrics and events, CloudTrail (organization trail, all regions, log file validation, to the backup
  account's bucket with Object Lock), GuardDuty findings, AWS Config history.
- **Stays on the host (KMS-encrypted root volume):** the application journal. Application logs are
  not shipped because they are not proven free of capability tokens (Django's CSRF warning logs
  `request.path`, which can be `/verify/<token>/`). Journald is persistent, capped at 2 GB and 30 days
  (`journald-quillmd-production.conf`). No request logs anywhere (gunicorn without an access log,
  nginx `access_log off`, ALB access logs off). RDS PostgreSQL logs are not exported and Performance
  Insights stays off (statement text is not reviewed for PHI).
- The launcher's startup proofs (fixed-format JSON) stay in `proofs/` on the state volume.

## 13. Backups, restore drill, RPO and RTO

| Layer | What | Where | Retention |
| --- | --- | --- | --- |
| RDS automated backups | continuous, point-in-time restore | production account | 35 days |
| AWS Backup, RDS | daily snapshot | production vault, copied to the backup account's vault | 35 days daily, 12 monthly |
| AWS Backup, EBS state volume | hourly snapshot | same, copied | 48 hourly, 35 daily, 12 monthly |
| Logical capture (within 30 days of go-live, section 4 item 2) | encrypted pg_dump plus every referenced file, consistency-checked | backup account S3, Object Lock (compliance mode) | 35 days of dumps; file objects once |

The backup account's vault has **AWS Backup Vault Lock** in compliance mode after a cooling-off
period: no one, including root, can delete recovery points before their retention ends.

**Pairing rule.** State files are written once and never modified (templates, exports, recordings,
receipts; nothing is deleted today). A database restored to time T is therefore paired with the
first state-volume snapshot taken **at or after** T (or with the surviving live volume, when only the
database is being rewound). `production_restore_check.py` proves the pairing: every referenced file
present and hash-identical.

**Targets.** RPO: database 5 minutes (PITR); state files 0 when the volume survives (instance loss),
1 hour when the volume itself is lost (hourly snapshots). RTO: 4 hours for instance loss or a database
rewind; 8 hours for loss of the Availability Zone (restore both into 1b). These are targets; the
drill measures them before go-live and quarterly.

**Restore drill (before go-live, then quarterly), declared, never touching production:**

1. Pick a restore time T; record it and the latest-restorable-time in the declaration.
2. Restore RDS to T as `quillmd-production-drill-<YYYYMMDD>t<HHMM>` into the private subnets with
   a drill security group; restore the first EBS snapshot at or after T as a new volume.
3. Launch a drill instance (same AMI) without the production role, attach the volume read-only at
   `/mnt/quillmd-drill-<same stamp>`.
4. As root on the drill instance (the restored files are 0600 for uid 931), run
   `ops/production_restore_check.py --expected-triggers 9` (the number recorded at activation) with
   the backup role; it refuses the live endpoint and live mount and prints counts only.
5. Record: restore start/end times (RTO), T versus the last write before the incident simulation
   (RPO), the check's counts. Delete the drill instance, volume and database; keep the record.
6. Quarterly, also restore from the **backup account's** copies with the break-glass custodians, so
   recovery is proven without the production account.

**Backup admission without a daily owner desktop action.** The private system's B2 offsite leg is
admitted by a 24-hour lease bound to an account-wide observation that only the owner's desktop can
make (`offsite_allocation.py:89-91`, `automatic_offsite.py:85`). It lapsed on 2026-09-23 and three
scheduled uploads were refused; the same gate also blocks download-only recovery, and it depends on
this VPS's ledger, so recovery on a replacement host would be refused too. That design compensated
for a provider where the uploader could not see or constrain the account. On AWS the guards are
**structural and enforced by the provider**: the copy lands in a separate account whose vault lock
forbids deletion, the production account's roles cannot touch it (SCP and vault access policy), and
every change to those policies is a CloudTrail event with an alarm. Evidence is therefore a
configuration that does not expire (checked daily by AWS Config rules and the Backup job events),
not an observation that must be renewed. Recovery uses AWS Backup and RDS restore APIs directly and
never waits on an upload lease.

## 14. Independent recovery access and key custody

- **Two custodians** (the owner and a named second person under a confidentiality agreement) each
  hold: an Identity Center admin identity with a hardware key; half of the sealed break-glass
  material for the management and backup accounts (root and a break-glass IAM user with hardware
  MFA, stored in two sealed envelopes in two locations); the offline copy of the logical backup key.
- Any break-glass sign-in, root sign-in, KMS key policy change or Backup vault policy change raises
  an SNS alarm to both custodians (EventBridge rules on CloudTrail).
- Recovery material is recorded outside the host: AMI ID, release artifact sha256 and bucket,
  profile hash, account IDs, vault ARNs and key ARNs in the deploy declaration and in the
  custodians' sealed kit. The private repository must remain available to both custodians.
- Proven by the quarterly drill from the backup account (section 13, step 6), not by assertion.

## 15. Alerts

SNS topic `quillmd-production-alerts` with confirmed email subscriptions for both custodians. Alerts
carry resource names and metric values only, never patient data.

| Signal | Condition |
| --- | --- |
| EC2 status check | `StatusCheckFailed_System` → alarm plus EC2 auto-recover action; `StatusCheckFailed_Instance` → alarm |
| Host resources | `mem_used_percent` > 85% for 10 min; disk `used_percent` > 80% on `/` or the state root; swap used > 0 |
| ALB | `UnHealthyHostCount` ≥ 1 for 5 min; target 5XX > 10 in 5 min; p95 target response > 10 s |
| RDS | CPU > 80% 15 min; `FreeStorageSpace` < 20%; `FreeableMemory` < 256 MiB; event subscription for failures, low storage, backup and maintenance |
| Backups | AWS Backup job FAILED/EXPIRED/ABORTED and copy-job failures (EventBridge) |
| Security | root or break-glass sign-in, KMS disable/deletion scheduling, vault/bucket policy change, security group change, GuardDuty findings of medium or higher |
| Outside the host | Healthchecks.io check fed by `quillmd-production-heartbeat.timer` every 5 minutes (only after both surfaces answer 200), period 5 min, grace 10 min, alerting both custodians outside AWS; Route 53 health check on `https://app.quillmd.com/health/` with a CloudWatch alarm |

Tests before go-live (cutover gate G6): publish a labelled test message to the SNS topic and record
**inbox receipt** by both custodians (provider acceptance is not delivery); stop the heartbeat timer
for 20 minutes and record the missed-heartbeat alert arriving at both custodians, then restart it;
fail the ALB health check by stopping the doctor unit on a drill target and record the alarm.

## 16. Email: Resend (V1) or Amazon SES

| | Resend (current) | Amazon SES |
| --- | --- | --- |
| BAA | none: "cannot sign a Business Associate Agreement" (resend.com/security) | covered by the AWS BAA (listed service) |
| Code | implemented and qualified (`core/email_backend.py`, fixed templates in `core/email_delivery.py`) | new backend needed; the profile deliberately refuses `ses` until it exists |
| What is sent | verification, invitation and recovery links with fixed text; no department name or clinical text (verified from code) | same |
| Setup | sender domain verification | domain identity with DKIM, a production-access request out of the SES sandbox (AWS review, lead time), bounce/complaint handling via SNS |
| Cost | existing plan | about $0.10 per 1,000 messages (not verified here) |

**Decision for V1: keep Resend under the enforced no-PHI rule.** The messages go to doctors (the
customers), contain no patient information by construction, and are fixed templates; that is not
PHI, so no BAA is required for them. The production launcher requires `QUILLMD_EMAIL_MODE=resend` and
refuses the preview credentials that the private resend mode appends. **Switch to SES** before any
message would carry patient-related content, or if counsel requires a BAA for all transactional
mail; the profile's email mode is the single switch and the launcher enforces it. Backup and
operational alerts do not use Resend in production (SNS).

## 17. Host recovery and patching

- **Rebuild, never repair in place.** A lost or suspect host is replaced: launch the recorded AMI
  with `cloud-init.yaml`, attach the surviving state volume (or one restored from the latest
  snapshot), run `bootstrap-host.sh --existing-state-volume` with the recorded release artifact,
  confirm the fixed identity number owns the volume, start the units, re-point the target group,
  then terminate the old instance. EC2 auto-recover covers hardware failure without a rebuild.
- **Rebuild drill** before go-live and after any change to the bootstrap: time it (RTO), record the
  receipt hashes, and confirm the launcher proofs on the new host.
- **Patching.** Security updates install daily through unattended-upgrades without automatic reboot;
  a monthly declared maintenance window reboots (post-reboot verification: launcher proofs, heartbeat,
  health, a synthetic smoke on the smoke account only). RDS minor versions apply in the RDS
  maintenance window. Python dependencies move only through a reviewed release; the release job runs
  `pip-audit`. Before activation, `requirements.txt` must gain hashes (`pip install --require-hashes`)
  so the host installs exactly the reviewed wheels (checklist item).

## 18. Open items owned outside this package

Owner (money, keys, contracts): AWS Organization and accounts, the AWS BAA in Artifact, Anthropic
HIPAA-ready organization and BAA, Deepgram Enterprise BAA and account-wide model-improvement
opt-out, the second custodian, Healthchecks.io account, independent penetration test, counsel's
retention schedule and breach procedure, any Savings Plan. Engineering, other V1 streams: real-patient
data gate (`SYNTHETIC_ONLY`), live Stripe path, admin surface behind a TLS proxy, client address for
rate limits, invitation-only registration, the Deepgram opt-out parameter. Engineering, this package:
the role tool and logical capture production paths (section 4), hashed requirements, and the
production backup status publisher.
