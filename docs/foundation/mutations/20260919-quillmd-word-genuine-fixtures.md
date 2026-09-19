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

A difference outside these tables is the finding. Public maintenance, synthetic-only operation and every
prior finalization and evidence file are preserved.
