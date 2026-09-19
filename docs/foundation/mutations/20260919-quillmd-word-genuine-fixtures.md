# Declaration — two genuine Word documents through the real export path

**Date:** 2026-09-19
**Act:** two synthetic encounters created, reviewed, finalized and exported through the deployed
application at `127.0.0.1:9130`, release `6d73c5e9026d974053365468101c2f7921544c6c`.
**Why it is declared:** finalizing an encounter is irreversible by design — a finalized document is
immutable and its export is hashed into the record. Rows cannot be un-created.

## Why these two documents have to be produced this way

The 2026-09-18 review package's files 04 and 05 are **SDK qualification fixtures**, not exports, and both
are misnamed at their source (recorded in `CHECKPOINT.md`, 2026-09-19). `all-blanks.docx` fills every
template blank; `long-answer.docx` adds a 19,931-character BODY paragraph while its longest mapped answer
is 89 characters. Neither demonstrates what its label claims.

A genuine missing-answer document and a genuine long-answer document can only come from the real export
path. ⚠️ **That path cannot run here or in CI**: `ops/sdk_sandbox` refuses a Word processor owned by the
calling account, and on both hosts the account that runs the tests is the account that owns the runtime.
The deployed service is the only place it runs, so these two documents are produced through the
application's own HTTP surface as the synthetic doctor.

**No provider call is made.** `save_answers` accepts clinician values directly and `finalize` requires only
that every field is reviewed — neither needs a generation. `providerJobs` must be zero.

## Baseline, measured 2026-09-19 before the act

| quantity | value |
|---|---|
| encounters | 12 |
| finalized encounters | 7 |
| encounters with an export | 7 |
| patients | 3 |
| templates | 11 |
| jobs | 14 |
| usage rows | 14 |
| provider receipts | 11 |
| total charged | 0.217724101050 |
| total configured-rate cost | 0.145149400700 |
| reservations / held | 12 / 0 |
| users | 10 |
| promotional balance, all wallets | 99.782275898950 |
| paid balance, all wallets | 0 |
| departments | 3 |
| invitations | 7 |
| audit events | 426 |

## What MUST change

| quantity | from | to |
|---|---|---|
| encounters | 12 | **14** — one missing-answer, one long-answer |
| finalized encounters | 7 | **9** |
| encounters with an export | 7 | **9** |
| audit events | 426 | **grows** — `encounter.create`, `encounter.finalize`, `encounter.export` and answer-save rows for these two encounters, and nothing else |

## What MUST NOT change

| quantity | value |
|---|---|
| jobs | 14 |
| usage rows | 14 |
| provider receipts | 11 |
| total charged | 0.217724101050 |
| total configured-rate cost | 0.145149400700 |
| reservations / held | 12 / 0 |
| promotional balance, all wallets | 99.782275898950 |
| paid balance, all wallets | 0 |
| users | 10 |
| patients | 3 |
| templates | 11 |
| departments | 3 |
| invitations | 7 |
| **provider calls** | **0** |
| **the 7 existing finalized encounters** | untouched — same export paths, same `export_sha256` |
| **the uploaded original template** | untouched — same bytes, same sha256 |

## What the two documents must demonstrate

**Missing-answer document.** Every one of the 90 mapped fields is reviewed and left EMPTY. Independently
verified afterwards by reading the exported DOCX: no content control carries an answer, every dropdown
still offers its original options, and the measurement cells are empty. ⚠️ The claim to check is that
unsupported answers remain UNFILLED — not merely that the document opens.

**Long-answer document.** Long text goes only where the mapping supports it:

- the **6 table-location cells** (`location_11`, `_12`, `_13`, `_25`, `_26`, `_27`) — the
  `<<insert location>>` cells in the measurement table;
- the free-text demographic `patient_name`.

⚠️ **The other two kinds are respected rather than stressed.** The 28 dropdowns receive a VALID ORIGINAL
OPTION — a dropdown that accepted arbitrary text would be the defect, not the demonstration. The 52
measurement cells receive VALID NUMBERS — they are numeric fields and long text there is not a supported
case. Verified afterwards: the complete long text is present, character for character.

## Amendment, 2026-09-19 — the first attempt failed at the save step, and what it left

The run of `09:15:20Z → 09:15:26Z` passed two checks and stopped with **HTTP 403 saving answers**: Django
rejects a POST without its CSRF token, and Playwright's `page.request` does not add one. It is a harness
defect, not application behaviour — the 403 is the protection working.

**Judged against the table above before anything else ran.** It left exactly ONE draft encounter
(`2a22f21f`) and nothing else: encounters 12 → 13, audit 426 → 428 (one `encounter.create`, one
`auth.login`). **Every MUST-NOT-CHANGE row held** — finalized 7, exports 7, jobs 14, usage 14, receipts
11, charged and cost identical to the digit, reservations 12/0, patients 3, templates 11, users 10,
promotional balance unchanged, provider calls 0.

⚠️ **THE RETRY REUSES THAT DRAFT RATHER THAN CREATING A SECOND.** Creating another would take the
encounter count past what this declaration says, and a delta that overshoots because of a retry is
indistinguishable in the record from one nobody predicted. The declared end state is unchanged:
**encounters 14, finalized 9, exports 9.**

## Amendment 2, 2026-09-19 — four attempts, what they left, and the corrected end state

Attempts at `09:15`, `09:22`, `09:28` and `09:37` each failed on a different detail and each is recorded
in the commit that fixed it: a missing CSRF token; a CSRF cookie whose name this deployment changes per
surface; a revision read from the first of three `[name=revision]` inputs, plus the 14 `claim_reviewed_*`
boxes omitted; and finally the real one —

> ⚠️ **`encounter.template_review_saved complete=False`.** `save_answers` runs each prewritten statement
> through `source_quote_evidence`, which demands a COMPLETE SOURCE LINE from the notes for that exact
> label. A claim it cannot evidence is forced back to `reviewed=false`, the review is recorded incomplete,
> and the finalization helper refuses it. **That is the application being right**, and reading it as a form
> problem three times was mine: a statement nobody can point at in the notes has not been reviewed.

The resolution carries the truth in the VARIANT rather than inventing a quotation. These synthetic notes
document none of the prewritten findings and most claims offer exactly that answer — `not_documented` or
`not_assessed` — which assert nothing and therefore need no evidence. The `trusted` claims (signer
identity, signature timestamp, interpreting physician) are server-supplied and left as rendered.

**Judged against the tables above.** Encounters reached the declared **14**, but as TWO
missing-answer drafts rather than one of each kind: the reuse predicate matched only `status='draft'`, and
the first encounter had already moved to `review`. **Finalized stayed 7 and exports stayed 7 — none of the
declared finalizations happened.** Every MUST-NOT-CHANGE row held exactly: jobs 14, usage 14, receipts 11,
charged `0.217724101050`, cost `0.145149400700`, reservations 12/0, patients 3, templates 11, users 10,
promotional balance `99.782275898950`, **provider calls 0**. Audit rose 426 → 456, all encounter and
authentication actions.

⚠️ **THE CORRECTED END STATE, AND WHY IT IS NOT A LARGER BUDGET.** The two existing encounters are REUSED —
the predicate now matches `draft` or `review` — so one becomes the missing-answer document and the second
is re-purposed rather than a third being created. **Encounters stay at 14. Finalized becomes 9, exports 9.**
Nothing else in the MUST-NOT-CHANGE table moves.

A difference outside these tables is the finding. Public maintenance, synthetic-only operation and every
prior finalization and evidence file are preserved.
