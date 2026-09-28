# Large Word form generation — bounded implementation proposal

**Internal engineering proposal, not implemented or qualified.** Source examined:
Word workflow branch based on `4caa34431a60e6ce3409ecadbbb6989b50659d7b`.
No provider calls, spending authority, changed denominator or new corpus campaign.
Only authorized original-development expected maps and current code were read.

## Measured need

The Word engine accepts at most 1,500 fields. The app refuses more than 100
answerable areas on upload/manual addition; generation and its quote repeat the
100-field check. That can make a valid large form unusable before a doctor sees it.
Removing detection extras cannot by itself close this limit.

| Original DEV form | Independent historical areas | Stable physical grouping, not semantic independence | Proposed requests of at most 100 fields |
| --- | ---: | --- | --- |
| D03 | 88 | 30 row groups; largest 13 | 88: one request |
| D10 | 198 | 60 row groups; largest 10 | 99 + 99: two requests |
| D11 | 559 | 100 row groups; largest 7 | 99 + 96 + 97 + 98 + 97 + 72: six requests |
| D28 | 227 | 133 row groups; largest 77 | 100 + 100 + 27: three requests |
| D29 | 125 | 77 row groups; largest 5 | 100 + 25: two requests |

These counts use complete independently mapped areas, preserving an area's
multiple locations and all areas sharing a physical row. They are not claims of
correct current recognition, authorized provider requests, or sufficient answer
capacity. Historical maps/results remain untouched. D03's newly sealed 86-area map
has the same physical answer coverage as its old 88 groups. D28's newly sealed
291-area map separates diagnosed selection from priority and merges some composite
values; it also preserves the old physical answer coverage. Its measured partition
and exact IDs are retained separately, without rewriting 227.

D28 proves why sections cannot be treated independently: 76 diagnosis rows across
four tables share a maximum of three diagnoses and unique priorities. Respondent,
visit/program eligibility, N/A exclusions, and unrecorded clinical facts remain
binding across every request. A row partition is transport only.

## Smallest coherent application change

1. Add a versioned, immutable generation plan for one encounter revision, bound to
   original SHA, template-version/mapping digest, the complete ordered field-ID set,
   complete source-unit IDs/offsets, all question/context labels, model/profile,
   prompt/schema digests, rates, geography and reservation calculation. Never split
   an individual answer area, options or repeated row identity to fit a request.
2. Keep the original document and one encounter/review/export. Partition only the
   requested IDs into bounded groups. Each request sees the full unchanged source
   units and complete question/context catalogue, with its requested IDs named
   separately. Validate the returned exact subset, then validate the assembled
   complete result once against the original full form. Cross-question/repeated-row
   guards must never be run on a reduced catalogue that hides a conflicting question.
3. Use a parent batch and existing per-request jobs/receipts/reservations rather than
   pretending several provider requests produced one receipt. A proposed initial
   ceiling is **eight requests, at most 100 requested fields each**. This covers the
   measured six-request largest development form with finite headroom. It is a
   declared engineering bound, not a new spending allowance or universal coverage.
   A group over 100 or a plan over eight requests remains an explicit refusal until
   a separately reviewed path exists; no question is dropped or combined to pass.
4. Compile every request and price the sum before admission. Bind the clinician's
   quoted total ceiling to the exact plan. Reserve all child ceilings atomically;
   settle each actual request using its own unchanged model/usage receipt and retail
   multiplier. Release only demonstrably unsent child holds. Unknown outcomes stay
   in reconciliation and are never retried automatically. The exact request index
   and hash make recovery/resumption idempotent; consumed attempts are not reused.
5. Stage successful child selections. Do not partially replace the encounter or
   report success until every planned field is accounted for and complete combined
   validation passes. Preserve failed/partial artifacts and existing clinician
   decisions. A changed source, mapping, mode, profile or price invalidates the
   plan before the next request and requires a fresh quote; it cannot silently
   extend an existing authorization. Explicit user cancellation stops unsent work.
6. Show the original complete form, requested/completed/pending/failed coverage and
   total charge ceiling. Keep ordinary notes as the input. Do not require doctors
   to split their Word file, recreate its layout or add labels to their notes.
   Finalization remains subject to normal clinician and signing/consent rules.

## Concrete affected code and separate limits

- `core/views.py`: upload/add admission, quote, generation action and review progress.
- `core/v3_mapping.py`: the 100-field message/admission contract.
- `core/generation.py`: quote/request compiler, full source-unit catalogue, exact
  subset response validation and one final full-form adoption. Existing narrative
  and historical single-request contracts stay versioned and unchanged.
- `core/jobs.py`, `core/models.py`, migration and wallet/receipt integrity checks:
  batch/child identity, staged artifacts, cancellation, atomic holds and crash recovery.
- `core/mapping_assistance.py` and `mapping_wire.py` separately limit assistance to
  200 mapped fields, 1,200 slots and 400,000 payload bytes. Generation partitioning
  does not automatically solve mapping assistance. Do not quietly raise these caps;
  use separately bound outline partitions with complete coverage, or an explicit
  visible refusal until that path is implemented.
- The existing per-request output cap and timeout still apply. Compile/byte/field
  failures can be refused before reserve/send. A provider `max_tokens` stop, refusal
  or malformed/incomplete selection is only known after a request: retain and settle
  its receipt, report incompleteness and apply the existing platform-failure policy.
  Neither 100 fields nor the current byte-bound pricing proves adequate output size.

## Finite offline acceptance before any live authorization

Use synthetic 99/100/101-field, the measured D10 two-request and D11 six-request
plans, shared-label/side/correction/consent controls crossing boundaries, and D28's
independently declared global constraint shape. Prove exact coverage without duplicate
or missing IDs; full-source offsets remain stable; compound questions/options are
not split; unchanged review/export works on the original. Capture unknown provider
outcomes, crashes between receipt and adoption, duplicate enqueue, cancellation,
mode/profile changes, partial failures, holds/settlement and resumed known-success
children. Mock all provider responses; no new paid campaign. Request live validation
only under separately reconciled eligible authority after this implementation passes
independent clinical/accounting refutation.

This is a concrete remaining developer-owned release blocker. Account access or
funding alone does not implement it. Current D10/D11/D28/D29 whole-document
compatibility remains unqualified, and every original failure stays in its original
denominator.

Evidence: private `rebuild/.runtime/word-nested-diagnosis-20260928/` contains
`capacity.py`, `07-large-form-expected-partitions.json` and
`10-D28-new-map-partitions.json`. These are metadata/expected-map calculations,
not engine scoring or provider execution.

D28's separately preserved new 291-area representation partitions into
`100 + 100 + 91` by the same physical grouping instrument. This does not change
its old 227-area denominator or prove those requested IDs are independently valid.
