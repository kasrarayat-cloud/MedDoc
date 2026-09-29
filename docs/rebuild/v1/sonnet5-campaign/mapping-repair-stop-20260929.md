# Sonnet 5 mapping stage — repair rounds and stop, 2026-09-29

Campaign `quillmd-v1-sonnet5-staged-40`. Follows `live-stages-20260929.md` (mapping attempt 2 failed on the
contract, $0.00984). **Decision: the mapping stage is NOT reopened. No further mapping send is made under this
campaign.** Its remaining $24.99016 stays unspent and, per the declaration (`unused_stage_budget_transfers: no`),
does not move to another stage.

## Why it stops

The rule stated before the second repair: one bounded repair round follows the first refutation; if the next
refutation finds another verified HIGH, the mapping line stops and is reported rather than looped. That condition
is met.

| round | commit (`fix/v1-mapping-partial`, pushed) | refutation result |
|---|---|---|
| repair 1 | `d40c8689` — one invalid change no longer refuses the whole proposal (design step 4); per-slot reference IDs | **HIGH ×2** (F1: an addition at a signing/consent question box adopted; F2: a replacement moved into an anchored text box), MEDIUM ×3 (F3 caption, F4 protected statement, MP-2 request size), plus F5 and the declaration profile (MP-3) |
| repair 2 | `48aa5e8d` — one place rule for every model change; request back inside the byte bound; profile `claude-sonnet-5-blank-mapping-v5` | **HIGH ×2 reproduced by an independent verifier** (below), LOW ×5 |

Repair 2's own proof: core mapping set 124 OK, documents 573 OK, 33 mutants over the new guards all killed, frozen
diagnostics self-test 22/22. The refutation found what those did not, which is the reason the pass is mandatory.

## The two verified HIGHs at `48aa5e8d`

Both reproduced by the verifier on synthetic blank forms (probe `mp2verify.py`, session scratch, not retained).
Both are model changes that the review surface presents as ordinary answers in a signing area; confirmation is
not blocked, because `v3_confirm` gates only on `assistance['unresolved']` (read from the code, not run).

- **R1 — a signing/consent question box that is not empty loses the hold.** The engine records a question box as
  a signing area only when its cell is empty (`documents/word_v3.py:5002`, the non-empty gate before
  `signing_boxes.add` at `:5029`). A box holding printed guidance (`Use black ink`) or an empty drawing run is not
  held; an addition there is adopted as answerable and `fill_template` writes the synthetic answer into the
  consultant's signing box. The identical empty box is held.
- **R2 — a cell under a `Signature` column header is not a signing area unless the engine made one there.**
  `documents/assistance.py:61-69` reads engine areas, paragraph text and row labels, never the column header; the
  engine makes an area only in an empty cell. With printed guidance or a drawing in the cell, an addition is
  adopted and filled.

LOW, recorded for whoever resumes: R3 (a content control carrying `sdtContentLocked` is not held; one variant fails
closed at export, the other writes inside the locked control — the same gap exists on the manual mapping path),
R4 (a frame defined by style, not direct `framePr`, is not held), R5 (`Countersigned by` does not match the
signature wording), U1/U2 (the adjective *initial* makes an ordinary choice line or narrative box read as an
initials/consent area — fail-closed over-holds; the text-addition capability lost against `d40c8689`).

## What this means for V1

- **Model-assisted mapping is not qualified.** It is off by default (`QUILLMD_MAPPING_ASSISTANCE` and
  `QUILLMD_MAPPING_ASSISTANCE_LIVE` both default `0`) and must stay off.
- **The candidate (`1c4c4233`) has no place rule for model changes at all:** it refuses only a replacement that
  would turn a signing field into another kind (`core/mapping_assistance.py:146`). R1/R2 and repair 1's F1 were
  measured on the repair branch, **not on the candidate**; the candidate is not claimed safe or unsafe here, only
  unqualified and disabled.
- The deterministic engine's mapping (no model) is unchanged by all of this and is what the diagnostics measured.
- `fix/v1-mapping-partial` is **not integrated** into `v1/release-integration`: partial adoption widens what a
  model proposal can place, and the place rule it depends on has two verified HIGHs. It is kept, pushed, as the
  starting point for the next repair, which needs the signing-area rule to hold on the place (header, box, column)
  rather than on whether the engine created an area there.

## Ledger (unchanged by this record — nothing was sent)

| stage | limit | exposure | remaining | decision |
|---|---|---|---|---|
| model_check | $5.00 | $0.00286 | $4.99714 | passed |
| mapping | $25.00 | $0.00984 | $24.99016 | failed-1; **not reopened** (two verified HIGHs after the bounded repair) |
| ordinary_notes | $10.00 | $0.066604 | $9.933396 | failed-1 (contract on the relations path) |
| **total** | **$40.00** | **$0.079304** | **$39.920696** | |
