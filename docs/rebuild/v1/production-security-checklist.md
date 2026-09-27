# QuillMD V1 production secure-configuration checklist

Prepared 2026-09-27. Filled in at activation (cutover gates G1 to G8, `cutover-plan.md`). Every row
names the evidence that proves it; a row without evidence is **not** verified, however obvious it
seems. "Verified by" is a person and a UTC date; the evidence is stored with the deploy declaration.
No row may be verified by looking at or changing a real patient's record: verification is structural,
or on the synthetic smoke account, or on a drill restore.

## A. Agreements, accounts and identities

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| A1 | AWS BAA accepted at the Organization level from the management account ("all features" on) | AWS Artifact > Agreements shows the BAA active for the organization; PDF saved outside the host | |
| A2 | Anthropic: HIPAA-ready API organization, BAA version accepted after 2026-04-01; a separate non-HIPAA organization for development | Console screenshot/PDF; production key belongs to the HIPAA-ready organization | |
| A3 | Deepgram Enterprise BAA signed; model-improvement opt-out enforced account-wide in writing, or `mip_opt_out=true` on every request | signed BAA; written confirmation; code check of `core/jobs.py` transcription call | |
| A4 | Stripe live account identity verified; no PHI in any Stripe object (Services Agreement 4.5) | payments checklist evidence; code review of metadata (payment id only) | |
| A5 | Resend used only for fixed no-PHI templates; production launcher refuses any other email mode | `core/email_delivery.py` review; launcher test `email_mode` | |
| A6 | Downstream BAA template ready for each practice (QuillMD as business associate) | counsel-approved template | |
| A7 | Root user of every account: hardware MFA, no access keys, credentials sealed under two-person custody | IAM credential report; sealed-envelope log | |
| A8 | Operators use IAM Identity Center with phishing-resistant MFA; no IAM users except break-glass | Identity Center MFA settings; `aws iam list-users` shows only break-glass | |
| A9 | Break-glass identities (management and backup accounts) with hardware MFA, tested once, alarmed on use | test sign-in record; SNS alert received | |
| A10 | SCPs: deny leaving the organization, disabling CloudTrail/GuardDuty/Config, KMS key deletion/disable, other regions, public S3, IMDSv1 re-enable | `aws organizations list-policies-for-target`; a denied test call | |
| A11 | Instance role has only SSM core, one secret, its KMS decrypt, release bucket read, CloudWatch agent; bootstrap-only EC2/KMS describe removed after G2 | IAM policy JSON reviewed; Access Analyzer | |
| A12 | Least privilege in PostgreSQL: runtime DML only, no DDL/TRUNCATE/trigger control/owner membership; backup SELECT only; owner NOLOGIN; migrator explicit SET ROLE; PUBLIC connect revoked | role verify run on a drill restore (all assertions) | |
| A13 | No shared tenants: nothing but QuillMD production runs in the production account or on the host | resource inventory (AWS Config); `systemctl list-units` | |

## B. Encryption and keys

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| B1 | EBS encryption by default ON in us-east-1 with `alias/quillmd-production-data` before any instance | `aws ec2 get-ebs-encryption-by-default`, `get-ebs-default-kms-key-id` | |
| B2 | Root and state volumes encrypted with the data key | `describe-volumes` (bootstrap receipt also checks the state volume) | |
| B3 | RDS `StorageEncrypted=true` with the data key; not publicly accessible; deletion protection on | `describe-db-instances` | |
| B4 | RDS TLS enforced (`rds.force_ssl=1`); application connects `verify-full` with the pinned CA bundle | parameter group; launcher proof (`database_ca_bundle`, sslmode) | |
| B5 | S3 buckets: SSE-KMS, Block Public Access (account and bucket), versioning, TLS-only policy; backup bucket Object Lock compliance mode | `get-bucket-encryption`, `get-public-access-block`, `get-object-lock-configuration` | |
| B6 | Secrets Manager secrets encrypted with the secrets key; only the instance role reads the application secret | resource policy; CloudTrail `GetSecretValue` principals | |
| B7 | KMS automatic rotation enabled on all three customer keys | `get-key-rotation-status` | |
| B8 | ALB TLS policy `ELBSecurityPolicy-TLS13-1-2-2021-06`; HTTP redirects to HTTPS; ALB-to-target TLS on 8443 | listener description; `curl -I http://app…` shows 301 | |
| B9 | HSTS sent by the application (HTTPS mode) | response header on `/login/` | |

## C. Network

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| C1 | `sg-app` admits only 8443 from `sg-alb`; no port 22 anywhere | security group rules; external port scan shows nothing on the instance address | |
| C2 | `sg-db` admits 5432 only from `sg-app`; RDS subnets have no Internet route | rules; route tables | |
| C3 | IMDSv2 required, hop limit 1 | `describe-instances` metadata options; bootstrap precondition | |
| C4 | Operators use SSM Session Manager; `sshd` disabled | `systemctl is-enabled ssh.service`; Session Manager logs | |
| C5 | Admin surface: ALB rule restricts `admin.quillmd.com` to reviewed source addresses; nginx include lists the same addresses | listener rules; `admin-allow.conf` reviewed; request from another address gets 403 | |
| C6 | WAF on the ALB: AWS managed common rules and a per-IP rate-based rule on `/login/`, `/register/`, recovery paths | web ACL; a rate-limit test from a synthetic client | |
| C7 | No NAT gateway, no public database, no other listener on the instance | VPC inventory; `ss -ltnp` on the host shows 8443 and loopback only | |

## D. Host and operating system

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| D1 | Ubuntu 24.04 LTS from a recorded AMI ID; x86_64 | bootstrap receipt; AMI ID in the declaration | |
| D2 | No Docker installed; no docker group; no operator in any privileged group except via SSM sudo | launcher proof (`docker_socket` absent); `getent group docker` empty | |
| D3 | Swap off and removed; `MemorySwapMax=0` on the units | `swapon --show` empty; unit files | |
| D4 | Core dumps disabled (`core_pattern`, systemd-coredump `Storage=none`, `LimitCORE=0`) | `sysctl kernel.core_pattern`; coredump.conf | |
| D5 | Journal persistent, 2 GB and 30 days maximum, not forwarded | `journalctl --disk-usage`; journald drop-in | |
| D6 | Security updates unattended daily, no automatic reboot; monthly declared reboot window | apt configuration; maintenance log | |
| D7 | Service identity `quillmd-production-app` uid = gid = 931, non-login, no home, no supplementary groups | `id quillmd-production-app`; launcher proof (`service_identity_number`) | |
| D8 | Install root root-owned, no group/other write; state root root:app 0710 on the mounted volume; subdirectories app 0700; mount point immutable underneath | `stat`; `lsattr -d` on the unmounted directory; launcher proof | |
| D9 | `requirements.txt` hash-pinned and installed with `--require-hashes` | release diff; bootstrap log | |
| D10 | Kernel/sysctl hardening from `sysctl-quillmd-production.conf` active | `sysctl -a` extract | |

## E. Application boundary (proven at every start)

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| E1 | All three units start through `service_launcher.py --profile production` and the proof passes | `proofs/{doctor,admin,worker}.json` with `passed: true`, the profile sha and release SHA | |
| E2 | The profile activation commit pins the RDS endpoint and CA bundle hash; the installed profile hash equals the reviewed one | commit diff; proof `profile_sha256` | |
| E3 | Application identity cannot read the environment file, the operator or ingress directories, write code or the profile, reach IMDS, or find Docker | proof checks | |
| E4 | Real-patient data gate: `SYNTHETIC_ONLY` lifted only by the reviewed release change, in the same declared act that lifts maintenance | release diff; `/health/` `data_mode` before/after | |
| E5 | Invitation-only registration and no promotional credit for self-registration, per the owner's V1 decision | route test on production (synthetic address) | |
| E6 | Admin surface works behind the TLS proxy (no redirect loop, CSRF passes) | heartbeat admin check 200; MFA sign-in on the smoke admin | |
| E7 | Per-client rate limits use the real client address from the proxy | two synthetic clients do not share a bucket | |
| E8 | Preview gate, preview credentials and email recipient shortcuts absent in production | launcher `private_only_setting` test; secret key list | |

## F. Logging and PHI

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| F1 | No request logs: gunicorn without access log, nginx `access_log off`, ALB access logs off | configs; ALB attributes | |
| F2 | Application logs never leave the host; CloudWatch receives metrics and AWS service logs only | CloudWatch log group inventory | |
| F3 | RDS logs not exported; Performance Insights off | instance description | |
| F4 | CloudTrail organization trail, all regions, log file validation, to the backup account bucket with Object Lock | trail status; validation digest check | |
| F5 | Alerts, SNS messages, heartbeat pings and email carry no patient data | message samples reviewed | |
| F6 | SSM session logs stored in the backup account with retention matching the PHI schedule | Session Manager preferences | |

## G. Backups and recovery

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| G1 | RDS automated backups 35 days; latest restorable time within 5 minutes | `describe-db-instances` | |
| G2 | AWS Backup plan: RDS daily, EBS state hourly; copies to the backup account | plan JSON; first successful jobs and copy jobs | |
| G3 | Backup account vault: Vault Lock compliance mode, cooling-off completed; production roles cannot delete | `describe-backup-vault`; a denied delete attempt | |
| G4 | Restore drill passed: PITR + paired EBS snapshot, `production_restore_check.py` all checks passed, RTO and RPO measured | drill record (counts only) | |
| G5 | Restore from the backup account's copies by the custodians | drill record | |
| G6 | Host rebuild drill: new instance, `--existing-state-volume`, proofs pass, target swap | bootstrap receipt; timings | |
| G7 | Logical capture (within 30 days of go-live): streaming, incremental objects, Object Lock, key in two custodies | first capture and restore records | |

## H. Monitoring and alerting

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| H1 | SNS topic with confirmed subscriptions for both custodians; labelled test received in both inboxes | inbox receipt recorded by each custodian | |
| H2 | CloudWatch alarms from `production-hosting.md` section 15 exist and point at SNS | `describe-alarms` | |
| H3 | Outside-host heartbeat: missed-heartbeat alert received by both custodians after a 20-minute stop | alert timestamps | |
| H4 | Route 53 health check alarm on `https://app.quillmd.com/health/` | alarm state change during the drill | |
| H5 | EC2 system status alarm with auto-recover action | alarm configuration | |
| H6 | GuardDuty, Config and security EventBridge rules (root, break-glass, KMS, vault, security groups) alert | test events | |

## I. Security testing and key rotation

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| I1 | Independent penetration test of the production host and release **before real data**, every finding retested or accepted in writing | report; retest letter | |
| I2 | Tenant isolation retested independently (department/organization, files, exports) | report section | |
| I3 | Rotation schedule: Django secret key, provider API keys, runtime/migrator/backup role passwords, RDS master (managed), heartbeat URL | rotation log with dates; next due dates | |
| I4 | Dependency audit (`pip-audit`) clean for the release | CI output | |

## J. Retention, deletion and incident response

| ID | Control | Evidence | Verified by |
| --- | --- | --- | --- |
| J1 | Retention schedule agreed with counsel for originals, exports, audio, provider output, audit rows, email and backups | signed schedule | |
| J2 | Deletion procedure that preserves the immutable ledger and audit (tombstones) and never deletes inside backup retention | reviewed procedure | |
| J3 | Backup lifecycle matches the schedule (vault lock and Object Lock retention set to it, not longer by accident) | plan and bucket configuration | |
| J4 | Data-subject request procedure (access, amendment, accounting of disclosures via the practice) | procedure | |
| J5 | Incident response plan: contacts, severity, containment runbook (stop units, rotate keys, preserve evidence), HIPAA breach notification clock and roles | plan; tabletop exercise record | |
| J6 | Offboarding of operators and custodians revokes Identity Center, break-glass shares and Healthchecks.io access | checklist | |
