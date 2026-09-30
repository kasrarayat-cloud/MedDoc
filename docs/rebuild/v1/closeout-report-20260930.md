# QuillMD V1 — private close-out milestone, consolidated report (2026-09-30)

**Not a V1-readiness claim.** Private and synthetic-only throughout; nothing was deployed, no real patient data was
touched, and every real-patient gate stays in place.

## 1. Revisions

| what | revision |
|---|---|
| installed release | `dedac162` on `main` (Sonnet 4.6, synthetic-only); not deployed to, not restarted |
| candidate | `v1/release-integration` (draft PR #1291) at `630b6185`, CI six jobs + secrets-scan green; this report and its records are a documentation-only descendant |
| integrated since `debaefd9` | incident record + amendments (`d492cff9`); field-relations v2 + remainder runner (`691e27d0`) and per-field hold (`1f1a4932`); account-email domains (`d38bbf83`); recorded scratch reaper (`c258cd6b`); tightening-only note holds (`1d22d0a5`); relations amendment and diagnoses |
| kept unintegrated, pushed | `fix/v1-mapping-authority` (`6ad0451c`), `fix/v1-mapping-partial` (`48aa5e8d`) |

## 2. Cleanup incidents, loss and recovery

Reconciled in `cleanup-incidents-20260929.md` (evidence beside it). Event 1 (00:58Z, a subagent): 227 shredded, 197 its
own and 30 other agents'. Event 2 (09:42Z, the lead): 6,537 shredded including its own logs; the itemised record is
irretrievably lost and 6,536 files are reconstructed from transcripts. Irretrievably lost evidence: the per-mutant
records behind `a68ee3ec`'s "74 of 74" (now evidenced in aggregate only), the mapping verifier's raw log, the raw
explorer JSON and full core log (summaries committed). Eight committed claims carry dated amendments. The stray shell
was this session's own 2026-09-27 wait loop (its `pgrep -f` matched itself); identified by command and owner and
terminated by PID. The cleanup path was repaired: `scripts/scratch-ledger.sh` + `scripts/reap-recorded-scratch.sh`
shred only files the caller recorded, unchanged, owned, unlinked elsewhere and not in use; bulk sweeps need a
stated declaration. One MEDIUM remains recorded (retain is read once per run).

**Owner-requested cleanup (2026-09-30), all this session's own files, every step logged in
`rebuild/.runtime/v1-closeout-20260929/closeout-ledgers/`:** 5,747 files shredded through the recorded reaper
(synthetic documents, a derived transcript index, test temp files, agent fixtures; 0 refused among those recorded);
47,482 repository copies removed only after proving their exact bytes are in git; 18,532 files of throwaway test
repositories and fixtures removed; 12 test databases dropped. Kept: the evidence outputs, the campaign's QA
database, the 42 `ubuntu`-owned PDFs (not shreddable by this account; not force-deleted), and temp directories that
predate this session or belong to other tools.

## 3. Paid requests and accounting

All under "Approve the staged $40 maximum" (`quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk`), one
campaign, cumulative limits, no new allowance. Every attempt's manifest, cost and QA-database receipt verify (23 of
23, 0 problems); no unknown outcome.

| stage | attempts | calculated cost | remaining | state |
|---|---|---|---|---|
| model check | 1 | $0.002860 | $4.997140 | passed |
| mapping | 1 | $0.009840 | $24.990160 | failed-1, not reopened |
| ordinary notes | 21 (14 default, 7 relations) | $0.099404 | $9.900596 | failed-3 (remainder cannot pass) |
| **total** | **23** | **$0.112104** | **$39.887896** | |

These are calculated costs (pinned rates × provider-reported usage). **Provider billing evidence is not available
here**: the campaign key is a Messages key, and usage/cost reports need an Admin key or the console (external
dependency). Application charges (1.5× reservations) are separate.

## 4. Mapping: before and after

- Candidate: no place-based signing/attestation authority. Measured on synthetic shapes: model additions into
  signing boxes, Signature-column cells, signature lines and initials boxes are adopted and filled; manual edits can
  put a text field on a signing place. Both paths are behind default-off flags; the legacy default fill writes by
  label identity only.
- One invalid model change discards the whole proposal at the candidate (reproduced from the retained attempt 2).
- `fix/v1-mapping-authority`: a structure-based authority and a dependence-graph adoption (valid independent changes
  adopted, dependent ones held, order-independent, frozen field-dict contract kept). Four refutation rounds: each
  closed the previous findings and produced new HIGH ones, leaks (e.g. blank-completed declarations, continued-table
  captions) and regressions (initials instructions made answerable, signed checklist rows refusing the legacy export).
  **Not integrated; the protection requirement is not met in the candidate.** Next design recorded in V1-DECISIONS.
- Provider-facing mapping diagnosis used only authorised synthetic structural analogues; no development original
  marked "no provider upload" was sent anywhere.

## 5. Ordinary notes: before and after

| retained 14 default-path responses (76 fields) | candidate | integrated |
|---|---|---|
| supported and correct (automatic) | 7 | 7 |
| held correctly | 40 | 40 |
| over-held (withheld though correct) | 29 | 29 |
| unsafe | 0 | 0 |
| frozen default-path leaks (adversarial entries) | 4 | **0** |
| frozen field-relations leaks | 11 | **8** |
| adverse rows held / line-break variants held | 53 of 57 / leaked | **57 of 57 / 318 of 318** |
| app-path walk: finalized, exports preserved | 14, 14 | 14, 14 (byte-identical to candidate) |

The 29 over-holds were each traced to their cause (27 unjustified, 2 justified). Every structural release was refuted
and withdrawn, so usefulness is unchanged; the integrated change only holds. Known over-hold: age-presentation
openers are now held for the clinician. Clinician review remains required and is not counted as automatic success.

**Field-relations path (off by default), live:** N03 1 supported correct + 1 over-held; N10 2 supported correct;
N13–N16 every contradiction flagged by the model and held (N13 after the per-field-hold repair, N14–N16 live). 0
unsafe of 12 fields; 5 of 6 completed review, finalization and authenticated export with read-back and no change
outside the written fields (N13's job failed before the repair). Six cases measure the veto; they do not qualify it.
Consent baseline kept: the model cannot attest or sign; a factual "Consent obtained" field answers only from an
explicit statement and still needs review; ambiguous attestation-like fields stay unresolved.

## 6. Other questions, handled as engineering

- **Email:** a Unicode domain is accepted and stored as its A-label; local part stays ASCII; limits keyed on the
  stored form. Integrated; install precondition `account_email_audit` (counts only) on the target database.
- **27-second tree move:** proven no restart, re-fork or timer run from the candidate tree and no worker exposure;
  a web request inside the window is not provable either way; no symptom; no restart performed.
- **Storage:** preflight blocked heavy work at 11 GB free; the filesystem size did not change, but space was later
  freed (53 GB free). No QuillMD-owned space could be reclaimed before that without touching cited evidence.
- **Retention/deletion:** not advanced in this milestone.

## 7. Remaining blockers

**Engineering:** signing/attestation protection and independent-change adoption for Word mapping (B-W2); useful
ordinary notes (B-G1: structural usefulness gains refuted; the model-judged relations path unqualified); the Word
gate unchanged and unmet (60 independent forms, 54/60 overall and 18/20 unseen, family thresholds, actual workflow);
general retention/deletion workflow; reaper MEDIUM; mapping and notes LOW/MEDIUM residuals recorded in the branches.

**External:** BAA-covered hosting, AWS/Anthropic/Deepgram/backup BAAs, email vendor, live Stripe, native Word
acceptance, independent penetration test, counsel's retention schedule, independently authored corpus, two-custodian
key custody, outside heartbeat, provider billing evidence for this campaign.
