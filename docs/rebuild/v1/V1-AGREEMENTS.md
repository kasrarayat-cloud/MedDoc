# V1 — agreements and account settings for every provider that would handle patient data

Researched 2026-09-27 from each vendor's own pages (raw downloads and SHA256 manifests preserved in
`rebuild/.runtime/v1-astra-recovery-20260927/hosting-source-snapshots/` as well as the original scratch;
Wayback copies used where the live site refused automated access). **A provider advertising a BAA is not proof
that our account has one.** No account console was opened, and no agreement was accepted, inferred or clicked.

| provider | would handle PHI? | agreement offered (vendor source) | our account has it? | account setting to verify | status |
|---|---|---|---|---|---|
| Hostinger (current VPS) | would, if used | **No** — its Hosting Agreement (2026-08-28) says the services should not be used as a HIPAA environment, VPS included | n/a | — | **excluded for PHI**; stays synthetic-only |
| AWS (proposed host: EC2/EBS/RDS/S3/Backup/KMS/SES) | yes | yes — accepted in AWS Artifact by an admin; for an Organization by the management account ("all features") | **unknown** — no AWS account for QuillMD established | Artifact acceptance record; HIPAA-eligible services only (all 18 proposed are on the 2026-09-03 list) | owner/legal action (B-L1) |
| Anthropic (language model) | yes | yes — first-party API, via the Console (sources disagree: self-serve vs sign-then-contact-sales) | **unknown** | HIPAA-ready organization (irreversible; keep development separate); BAA accepted **after 2026-04-01** so structured outputs are covered | owner/legal action (B-L2) |
| Deepgram (transcription) | yes (audio + transcript) | on request via sales; Enterprise per the pricing page | **unknown** | account-wide Model Improvement Program opt-out; our requests will send `mip_opt_out=true` in real mode (price effect unverified) | owner/legal action (B-L3) |
| Backup storage | yes (encrypted) | Backblaze: BAA wording names covered entities only; AWS Backup/S3: under the AWS BAA | **unknown** | — | choose AWS (proposed) or confirm a Backblaze subcontractor BAA (B-L4) |
| Resend (account email) | **must not** | **no BAA** | n/a | account email carries only a link: invitation, verification, recovery and alerts contain no clinical content (enforced by test) | acceptable only while PHI-free; Amazon SES is the BAA-covered alternative (B-L5) |
| Stripe (payments) | **must not** | Stripe's terms forbid sending PHI | n/a | payment metadata carries no patient details (verified in code) | acceptable; live account pending (B-S2) |
| GitHub (source, CI) | must not | — | n/a | tests use synthetic data only; clinical artefacts gitignored; pre-commit allowlist | acceptable |
| Development assistant sessions | must not | — | n/a | no real patient data is ever sent into sessions or tools | standing rule |

## Code facts that the agreements depend on (verified in this repository)

- **Structured-output schema carries no form or patient data.** `Selections`/`UnitSelections` are static
  classes (`key`, `quotes` or `unit_ids`, `conflict`); notes and labels travel only in the message payload.
- **Account email is PHI-free.** Templates substitute only `{link}` (blockers stream, `d97bd05e`, tested).
- **Payment metadata is PHI-free** (inventory, verified).
- **Deepgram opt-out.** Real mode requires `QUILLMD_DEEPGRAM_MIP_OPT_OUT=true`. The synthetic system keeps
  today's request (repair in progress).
- **Logs.** Clinical text is not logged. One residue: a CSRF failure warning can log a request path that contains
  a capability token (not PHI).

## Account verification limit at continuation

Native Anthropic model metadata returned `claude-sonnet-5`; this is account endpoint access only. No Console
agreement, HIPAA-ready organization setting, retention policy, US geography default or rate tier was verified.
The exact model and structured-output feature must be covered by the actual executed agreement before PHI.
The AWS, Deepgram and backup account agreement statuses above remain unknown, not implicitly accepted.
