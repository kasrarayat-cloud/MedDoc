# V1 — the one consolidated request for inputs only the owner, counsel or a vendor can provide

Prepared 2026-09-27, after the engineering that does not depend on these inputs was done or is in flight.
Nothing here is assumed, clicked or accepted on the owner's behalf.

## 1. Spending authority (Anthropic API, synthetic or blank inputs only — no patient data)

| purpose | bound | unblocks |
|---|---|---|
| Sonnet 5 live check (`sonnet5-migration.md`, ≤ 10 generation requests on fresh synthetic encounters) | **$5** | B-M1: Sonnet 5 configured and verified, and the thinking/effort ruling |
| Model-assisted Word mapping on blank forms (`model-assisted-mapping.md`) | **$25** | B-W1: the only realistic route to the Word gate; judged on the qualification cohort |
| Ordinary-notes path evaluation on synthetic notes, after it is built and refuted | **$10** | B-G1 |
| **total cap** | **$40** | each run stops at its own cap; every attempt is reported |

## 2. Configuration only the owner can apply (the environment file is never read by sessions)

- After the Sonnet 5 check passes: set the values in `sonnet5-migration.md` (model, three rates, profile), then
  restart doctor, admin and worker. Rollback values are in the same file.
- Decide `QUILLMD_WORD_ENGINE=v3` for new uploads once the Word review screens are installed.

## 3. Agreements (legal representative — each is a signature only the owner's company can give)

| agreement | where | note |
|---|---|---|
| AWS BAA | AWS Artifact, by the management-account admin (for the Organization) | prerequisite for the production host, backups and SES |
| Anthropic BAA + HIPAA-ready organization | Anthropic Console | accept after 2026-04-01 so structured outputs are covered; keep development in a separate organization |
| Deepgram BAA | sales (Enterprise) | also confirm the `mip_opt_out` price effect and account-wide opt-out |
| Backup storage | AWS Backup/S3 under the AWS BAA (proposed), or a Backblaze subcontractor BAA | Backblaze's wording names covered entities only |

## 4. Accounts and money (owner)

- AWS Organization with management, production and backup accounts. Infrastructure budget at verified
  us-east-1 prices (`production-cost.md`): **$152.08 low / $179.34 expected / $453.40 high per month**, plus
  about $15–25/month of unverified allowances (WAF, GuardDuty, Config, custom metrics). Capacity assumption
  (expected): 10 invited doctors, 15 encounters per doctor per working day. Provider usage (model,
  transcription) is passed through to doctors at 1.5×. This is an approval, not a purchase made here.
- Stripe live: verified account, restricted live key, webhook endpoint registration, and one bounded live payment
  (≤ $5) to prove crediting.
- An outside-host heartbeat account (for example Healthchecks.io) and its check URL.
- A second key custodian or an offline break-glass copy of the backup and storage credentials.

## 5. People (owner, counsel, vendor)

- Counsel: the retention schedule, deletion procedure, breach-notification procedure and downstream-BAA
  documents.
- An independent penetration-test vendor for the production host and release.
- The owner: one desktop Microsoft Word session to open the holdout/qualification exports and record native
  acceptance.

## 6. Product decisions (owner)

- The promotional credit at signup (amount, or none) for invited clinicians.
- Sonnet 5 thinking mode and effort, taken on the measured check.
- Whether custom Word upload may go live as **assisted completion** (every mapping reviewed and confirmed by a
  clinician) while automatic compatibility is below the gate. As declared, V1 is not complete while the gate is
  unmet. This decision only governs what may be offered in the meantime.
