# Sonnet 5 mapping and ordinary-notes stages — first live runs (QA worker), 2026-09-29

Campaign `quillmd-v1-sonnet5-staged-40` (authority `quillmd-v1-sonnet5-staged-40-call_9fkOp2kqbQ28e17HqXgHFlzk`,
declaration `01ff8c7d`). Runner `631d81af` (candidate code `8e3dcfd0` + the campaign tooling; `rebuild/` outside
`ops/` equals the frozen candidate, as the diagnostics freeze `7a141d05…` requires). Both runs went through
`scripts/run-ruled-mutation.sh`. **QA-worker evidence only**; the installed release was not touched.
Settings: `claude-sonnet-5`, thinking disabled, effort medium, geography unset (metered `global` on every send),
`QUILLMD_WORD_ENGINE=v3`; mapping with assistance and its live flag on and no layout socket (deployed-equivalent);
notes default path with field relations off, relations sends last with the flag on. Every retained transcript and
evidence file was scanned: no key-shaped string.

## Mapping — stopped after its first send (contract), $0.00984

| attempt | form | served | tokens in/out | stop | cost | outcome |
|---|---|---|---|---|---|---|
| 2 | f1 (MAPPA-like guidance form) | claude-sonnet-5 | 4365/111 | end_turn | $0.00984 | job failed: `ValidationError` → stage stopped (contract), 9 sends not made |

**Diagnosis, reproduced read-only from the retained request and response** (the rebuilt request equals the sent
one byte for byte): `mapping_wire.expand → span` raised "Source text belongs to another destination." Sonnet 5
returned a well-formed compact envelope, but its two replacements misused the positional contract:
change 0 labelled answer slot 3 with reference 3 (slot 2's text) where slot 3's own row-label reference 7 held the
same question; change 1 targeted slot 7 — the question paragraph, not the date's answer cell (slot 8) — with
reference 6 (slot 3's heading). The model confused global reference positions with slot numbers and chose a wrong
destination. **The app failed closed correctly** (nothing adopted; the deterministic mapping stays; the charge was
absorbed as a platform failure). **App defect against its own design** (`model-assisted-mapping.md` step 4): one
invalid change discards the whole proposal instead of becoming an unresolved record for that area. Under repair on
`fix/v1-mapping-partial` (per-change degradation to unresolved records; per-slot reference IDs listed in the
request); the stage is reopened only with a committed diagnosis and the repaired runner.

## Ordinary notes — default path complete; field-relations path stopped on its first send, $0.066604

| attempt | send | served | tokens in/out | stop | cost | model selection vs frozen entries | app outcome per field | verdict |
|---|---|---|---|---|---|---|---|---|
| 3 | N01:default | claude-sonnet-5 | 2026/271 | end_turn | $0.006762 | acceptable 11 | held_correct 3, over_held 8 | usefulness |
| 4 | N02:default | claude-sonnet-5 | 1283/86 | end_turn | $0.003426 | acceptable 3 | held_correct 1, over_held 2 | usefulness |
| 5 | N03:default | claude-sonnet-5 | 1268/61 | end_turn | $0.003146 | acceptable 2 | over_held 2 | usefulness |
| 6 | N04:default | claude-sonnet-5 | 1900/268 | end_turn | $0.00648 | acceptable 11 | held_correct 4, over_held 2, supported_correct 5 | usefulness |
| 7 | N05:default | claude-sonnet-5 | 1942/270 | end_turn | $0.006584 | acceptable 9, forbidden 1, unlisted 1 | held_correct 4, over_held 7 | usefulness |
| 8 | N06:default | claude-sonnet-5 | 1800/262 | end_turn | $0.00622 | acceptable 11 | held_correct 9, over_held 2 | usefulness |
| 9 | N07:default | claude-sonnet-5 | 1626/265 | end_turn | $0.005902 | acceptable 5, forbidden 6 | held_correct 11 | usefulness |
| 10 | N08:default | claude-sonnet-5 | 1171/60 | end_turn | $0.002942 | acceptable 2 | held_correct 1, supported_correct 1 | usefulness |
| 11 | N09:default | claude-sonnet-5 | 1169/60 | end_turn | $0.002938 | acceptable 2 | held_correct 1, over_held 1 | usefulness |
| 12 | N10:default | claude-sonnet-5 | 1217/61 | end_turn | $0.003044 | acceptable 2 | over_held 1, supported_correct 1 | usefulness |
| 13 | N11:default | claude-sonnet-5 | 1353/92 | end_turn | $0.003626 | acceptable 3 | held_correct 1, over_held 2 | usefulness |
| 14 | N12:default | claude-sonnet-5 | 1392/89 | end_turn | $0.003674 | acceptable 3 | held_correct 1, over_held 2 | usefulness |
| 15 | N13:default | claude-sonnet-5 | 1352/65 | end_turn | $0.003354 | unlisted 2 | held_correct 2 | usefulness |
| 16 | N16:default | claude-sonnet-5 | 1336/70 | end_turn | $0.003372 | unlisted 2 | held_correct 2 | usefulness |
| 17 | N02:field_relations | claude-sonnet-5 | 1897/134 | end_turn | $0.005134 | — | job failed: ValidationError | contract |
Not sent (stage stopped on attempt 17): the field-relations sends N03, N10, N13, N14, N15, N16.

### What the default path (the shippable one) showed — 14 sends, 76 fields

| | fields |
|---|---|
| Sonnet 5's selection matched a frozen **acceptable** answer | 64 (84%) |
| matched a frozen **forbidden** answer (a model error) | 7 |
| unlisted | 5 |
| app **supported and correct** | 7 |
| app **held correctly** (incl. all 7 model errors caught, the contradiction and missing controls) | 40 |
| app **over-held** — an acceptable model selection withheld (`application_over_hold`) | **29** |
| **unsafe** adoptions (unsupported, wrong side, denial, contradiction) | **0** |

- **The offline replay predicted every one of the 76 application outcomes exactly** from the same selections, so the
  frozen replay is a faithful predictor of the app's behaviour.
- **Contradiction controls (N13, N16):** Sonnet 5 set `conflict: true` on both pairs in both notes; the app held all 4
  fields. Direct live evidence that, on this set, the model flags the contradictions the default path relies on it to
  flag — 4 fields, not a rate.
- **Exports:** 14/14 authenticated exports completed their workflow, read back as reviewed, changed no part other
  than the document body.
- **The limit on usefulness here is the application's default-path hold rules, not the model**: 29 of 36 fields that
  should be supported were correct model selections the app held. They fall in the documented REMAINING-51 groups
  (history spans, patient predicate, SOAP roles, caregiver relation, encounter subject, post-family ownership). The
  same holds caught all 7 model errors. Loosening them needs a bounded causal hypothesis per group and must keep those
  catches — not a wording campaign.

### Field-relations path (paused, default-off) — contract failure on its first send

Attempt 17 (N02, three `Other` write-in fields): served `claude-sonnet-5`, `end_turn`, then
`v3_field_relations.records` refused: "Ordinary relations must cover the exact source and original options." Replayed
read-only with the rebuilt request (equal to the sent one): the contract requires one `context` relation **per source
unit** (2 units); Sonnet 5 returned one entry per selected unit. The Sonnet 5 request compiler moves array-length
constraints into schema descriptions (`transform_schema`), so structured output does not enforce them. Fails closed;
no answer adopted. Defaulting missing relations would weaken the contradiction veto, so the safe repair is a
unit-keyed contract; the veto stays paused and its six evaluation sends were not made.

## Ledger after these runs

| stage | limit | exposure | remaining | decision |
|---|---|---|---|---|
| model_check | $5.00 | $0.00286 | $4.99714 | passed |
| mapping | $25.00 | $0.00984 | $24.99016 | failed-1 (contract; reopen after repair) |
| ordinary_notes | $10.00 | $0.066604 | $9.933396 | failed-1 (contract on the relations path) |
| **total** | **$40.00** | **$0.079304** | **$39.920696** | |

## Amendment, 2026-09-29 (appended; the rows above are kept as written)

The mapping row's "reopen after repair" did not happen. Two repair rounds on `fix/v1-mapping-partial`
(`d40c8689`, `48aa5e8d`) each drew verified HIGH refutation findings, so under the bounded-repair rule the mapping
stage is **not reopened** and no further mapping send is made in this campaign. Record:
`mapping-repair-stop-20260929.md`.

## Amendment, 2026-09-29 — the field-relations diagnosis (appended)

The diagnosis above says the Sonnet 5 schema transform moved an array-length constraint into the description. More
precisely: the schema that was sent had **no** length constraint on `context` at all (a length that depends on the
request cannot be written into the static model); had one been emitted, the transform would indeed have moved it.
The conclusion is unchanged: the positional contract is not enforced by structured output, and the repair is a
contract the schema itself enforces (per-request keyed context).
