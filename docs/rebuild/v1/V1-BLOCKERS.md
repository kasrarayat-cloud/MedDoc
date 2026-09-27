# V1 blockers — the single list

Last updated 2026-09-27. One list. Each row is a demonstrated blocker to "real patients, invited doctors, US"
with its evidence and what clears it. **E** = engineering in this programme; **O** = owner action;
**L** = legal representative / counsel; **V** = outside vendor. Items are closed only with evidence.

## Product

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-W1 | **Custom Word automatic compatibility** is far below the gate (≥90% documents) | frozen candidate 1: dev 3/40, **holdout 0/20** (`word-holdout-first-pass-1.md`) | a candidate reaches ≥18/20 on the predeclared qualification cohort **and** ≥75% per family. The realistic route is a bounded model-assisted mapping layer on blank forms (design: `model-assisted-mapping.md`), measured only after spend approval | E + O (spend) |
| B-W2 | Word v3 in the app: mapping review with corrections, confirmation before use, answers for choice/checkbox/table kinds, export | engine wired (`66aef05e`); app side in progress | built, refuted (clinical path), installed | E |
| B-W3 | Native Microsoft Word acceptance of holdout/qualification outputs | LibreOffice renders are evidence, not native acceptance | the owner opens the exported files in desktop Word and records the result | O |
| B-G1 | **Ordinary (unlabelled) typed or dictated notes on custom forms** return every answer as a conflict | `validate_selections`: any unlabelled line → inherited context → conflict (inventory, VERIFIED) | a generic sentence-selection contract for custom forms (extend the colonoscopy "natural" contract beyond tab forms), refuted in rounds, then a bounded live synthetic evaluation | E + O (spend) |
| B-R1 | Shared review defects: a stale/crafted POST can generate over reviewed answers; WM statement decisions lost on an employee save; `&` export rewrite | PR #1287 analysis (VERIFIED by reading) | ported on `v1/review-guards`, refuted, installed | E |
| B-M1 | Sonnet 5 is prepared, not active | `v1/sonnet5` built + refuted; 4 LOW repairs in progress | owner sets the model/rates/profile values (`sonnet5-migration.md`), approves the bounded live check, and it passes (model echo, stop reason, tokens vs bound, latency) | E + O |
| B-S1 | Real mode could accept sandbox payments as real credit (HIGH); live Stripe behind the preview gate never credits | refuter R1/R2 on `v1/blockers` (confirmed by reading) | repairs merged with fail-before/pass-after tests | E |
| B-S2 | Live payments need a live Stripe account, restricted key, webhook registration and ingress | no live account configured | owner provides them; bounded live payment test | O |
| B-P1 | Production launcher would refuse to start under its own metadata block (TCP timeout, not EPERM) | refuter F1 (kernel-level reproduction) | repair on `v1/prodprofile` proven with the containerised BPF probe | E |

## Hosting and agreements (real patient data cannot move before these)

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-H1 | The current VPS cannot hold PHI | Hostinger Hosting Agreement (2026-08-28) disclaims HIPAA use, VPS included | production runs on a BAA-covered host (AWS proposal: `production-hosting.md`, `production-cost.md` on `v1/prodprofile`) | O + L |
| B-L1 | AWS BAA | accepted only in AWS Artifact by the management-account admin | owner/legal representative accepts it for the production account/Organization | L |
| B-L2 | Anthropic BAA / HIPAA-ready organization | BAA must be accepted after 2026-04-01 to cover structured outputs; HIPAA readiness cannot be turned off, so dev stays in a separate org | legal representative executes it; organization ID recorded | L |
| B-L3 | Deepgram BAA (Enterprise only per its pricing page) and the price effect of `mip_opt_out` | vendor pages; refuter R5 | BAA signed; opt-out enforced account-wide; price confirmed | L + O |
| B-L4 | Backup storage under a BAA | Backblaze's BAA wording names covered entities; QuillMD is a business associate | use AWS Backup/S3 under the AWS BAA (proposal), or Backblaze confirms a subcontractor BAA | O |
| B-L5 | Email vendor | Resend offers no BAA | account email stays PHI-free (enforced by test) **or** move to Amazon SES under the AWS BAA | E (enforced) / O (choice) |
| B-L6 | Retention, deletion, breach-notification and downstream-BAA documents | none exist | counsel provides the schedule and procedures; engineering implements deletion with tombstones | L + E |

## Operations on the production target

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-O1 | Backups with a **verified restore** on the production host | no production host yet | scheduled encrypted capture + restore drill into isolation with measured RPO/RTO | E (after B-H1) |
| B-O2 | Independent recovery access and key custody | one custodian; LUKS key beside the data on the VPS | two custodians or an offline copy, each proven by retrieval and restore | O |
| B-O3 | Delivered alerts, including **escalation inside an open incident** | today an escalating incident sends nothing after its first warning (demonstrated 09-23..09-26) | owner-confirmed inbox receipt from the production host; escalation re-notifies | E + O |
| B-O4 | Outside-host monitoring | adapter built, no check URL | a heartbeat service account; missed-heartbeat test passes | O + E |
| B-O5 | Independent penetration test | none has run | vendor test of the production host and release; findings retested | V + O |
| B-O6 | Whole-host recovery drill | only unplanned reboots survived | fresh-instance rebuild from vaulted material, measured | E (after B-H1) |

## Current synthetic system (not a V1 gate, recorded so it is not lost)

- Offsite (B2) backups have been refused daily since 2026-09-24. The admission lease lapsed at 2026-09-23T22:05:53Z
  and needs the owner-desktop renewal. Local encrypted backups continue daily (latest verified 2026-09-26
  04:31Z). A healthy status row is not taken as proof of a completed backup.
