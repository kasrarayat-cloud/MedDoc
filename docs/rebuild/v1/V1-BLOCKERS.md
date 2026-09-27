# V1 blockers — the single list

Last updated 2026-09-27. One list. Each row is a demonstrated blocker to "real patients, invited doctors, US"
with its evidence and what clears it. **E** = engineering in this programme; **O** = owner action;
**L** = legal representative / counsel; **V** = outside vendor. Items are closed only with evidence.

## Product

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-W1 | **Custom Word automatic compatibility** and independent-corpus evidence fail the gate | historical engine proxy dev 3/40, **holdout 0/20**; incomplete workflow/checkbox/native evidence; 60 files but 44 declared lineages; old reserved qualification20files/12lineages preserved; separate fresh20/20 frozen with sealed original-only maps, but three legacyDOC refusals cap current candidate at17/20. Bounded158inventory cannot supply development10: optimistic source-capped ceiling8 | preserve every first-pass result; establish independent authorship; complete mapping work offline; satisfy 54/60 overall, 18/20 holdout and ≥75% per family through the app. Holdout-informed repairs also need ≥18/20 on a separately predeclared unseen cohort. Model calls need eligible authority | E + O (spend / native access) |
| B-W2 | Word v3 in the app: mapping review with corrections, confirmation before use, answers for choice/checkbox/table kinds, export | reviewed detector/mapping/export repairs locally integrated; combined74workflow tests pass; bounded mapping assistance now independently refuted and locally integrated with both flags off | built, refuted (clinical path), installed | E |
| B-W3 | Native Microsoft Word acceptance of holdout/qualification outputs | LibreOffice renders are evidence, not native acceptance | the owner opens the exported files in desktop Word and records the result | O |
| B-G1 | **Ordinary typed/dictated notes, including the qualified WM form**, lack acceptable end-to-end evidence | reviewed correction/consent and required WM path locally integrated; remaining ordinary-source context excessive holds undergoing bounded repair. Live exact-model usefulness still unverified | integrate necessary reviewed WM path and generic repairs; verify useful positives plus missing/denied/corrected/side/row cases through worker → correction → finalization → export; exact-model synthetic verification. Labelled-note workaround does not close this | E + O (eligible live spend) |
| B-R1 | Shared review defects: a stale/crafted POST can generate over reviewed answers; WM statement decisions lost on an employee save; `&` export rewrite | reviewed repair locally integrated; original1,224core plus final79focused tests pass | ported on `v1/review-guards`, refuted, installed | E |
| B-M1 | Sonnet 5 is prepared, not served | native account model metadata and free token counts verified 2026-09-27; installed app remains 4.6 | configuration cutover after candidate gates; eligible bounded check proves served worker request/response model, stop, usage, reservation/charge and clinical behavior; account agreement separately required | E + O (eligible spend / account) |
| B-S1 | Real-mode funding and payment evidence must remain trustworthy | reviewed R5 repair locally integrated; 71finalfocused tests plus independently closed statement-trigger counterexample | final reviewed repair integrated; fail-before/pass-after evidence; fresh-install and supported upgrade checks, immutable settled history | E |
| B-S2 | Live payments need a live Stripe account, restricted key, webhook registration and ingress | no live account configured | owner provides them; bounded live payment test | O |
| B-P1 | Production metadata-denial launcher repair | repaired in candidate; containerised BPF probe evidence retained | prepared code gate passed; deployment-target configuration and startup still require verification after provisioning | E; target blocked by B-H1 |

## Hosting and agreements (real patient data cannot move before these)

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-H1 | The current VPS cannot hold PHI | Hostinger Hosting Agreement (2026-08-28) disclaims HIPAA use, VPS included | production runs on a BAA-covered host (AWS proposal: `production-hosting.md`, `production-cost.md` on `v1/prodprofile`) | O + L |
| B-L1 | AWS BAA | accepted only in AWS Artifact by the management-account admin | owner/legal representative accepts it for the production account/Organization | L |
| B-L2 | Anthropic BAA / HIPAA-ready organization | BAA must be accepted after 2026-04-01 to cover structured outputs; HIPAA readiness cannot be turned off, so dev stays in a separate org | legal representative executes it; organization ID recorded | L |
| B-L3 | Deepgram BAA (Enterprise only per its pricing page) and the price effect of `mip_opt_out` | vendor pages; refuter R5 | BAA signed; opt-out enforced account-wide; price confirmed | L + O |
| B-L4 | Backup storage under a BAA | Backblaze's BAA wording names covered entities; QuillMD is a business associate | use AWS Backup/S3 under the AWS BAA (proposal), or Backblaze confirms a subcontractor BAA | O |
| B-L5 | Email vendor | Resend offers no BAA | account email stays PHI-free (enforced by test) **or** move to Amazon SES under the AWS BAA | E (enforced) / O (choice) |
| B-L6 | Retention/deletion controls, breach procedures and downstream agreements | read-only catalog/policy validator/aggregate readiness tool prepared; policy unset; no hold/tombstone/purge workflow | counsel/owner supply schedule, start events, hold authority and procedures; engineering still implements reviewed hold enforcement and tombstone/deletion workflow with backup/downstream reconciliation; readiness counts do not close this gate. See `retention-deletion-readiness.md`. | L + E |

## Operations on the production target

| id | blocker | evidence | clears when | who |
|---|---|---|---|---|
| B-O1 | Backups with a **verified restore** on the production host | no production host yet | scheduled encrypted capture + restore drill into isolation with measured RPO/RTO | E (after B-H1) |
| B-O2 | Independent recovery access and key custody | one custodian; LUKS key beside the data on the VPS | two custodians or an offline copy, each proven by retrieval and restore | O |
| B-O3 | Delivered alerts, including **escalation inside an open incident** | escalation/reminder repair completed on branch (`alerts-round3-recovery-20260927.md`); installed incident and delivery remain unverified | integrate reviewed repair, then confirm recipient delivery and escalation from the actual production host | E + O |
| B-O4 | Outside-host monitoring | adapter built, no check URL | a heartbeat service account; missed-heartbeat test passes | O + E |
| B-O5 | Independent penetration test | none has run | vendor test of the production host and release; findings retested | V + O |
| B-O6 | Whole-host recovery drill | only unplanned reboots survived | fresh-instance rebuild from vaulted material, measured | E (after B-H1) |

## Current synthetic system (not a V1 gate, recorded so it is not lost)

- Offsite (B2) backups have been refused daily since 2026-09-24. The admission lease lapsed at 2026-09-23T22:05:53Z
  and needs the existing custody/admission process. Latest Sep27 offsite attempt refused before provider
  calls, with no pending publication; no ticket was replayed or lock cleared. Local Sep27 capture passed an isolated restore at 16:44 UTC: 36 tables, 226,187 rows, 64 files, all hashes
  matched, zero provider actions; temporary container removed. This is same-host/local-key recovery, not
  independent custody or offsite recovery proof (see `astra-recovery-20260927.md`). Production scheduling needs renewable admission instead
  of a daily manual action.
